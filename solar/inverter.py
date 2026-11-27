"""Abfrage-Schleife für den Wechselrichter: liest Register, bildet abgeleitete Werte,
führt den Verlauf und meldet neue Daten an Abonnenten (z. B. MQTT)."""

import json
import os
import queue
import socket
import threading
import time
import traceback

from .modbus import ModbusTcpClient, ModbusError, ModbusException, ModbusTimeout, friendly
from .registers import (REGISTERS, STATIC_GROUPS, SLOW_GROUPS, WR_STATUS, AKKU_STATUS,
                        ARBEITSMODUS, ZWANG, EINSPEISE_MODUS, build_blocks, decode)


class History:
    """Minutenwerte (Mittelwerte) der wichtigsten Leistungen, max. 48 h."""

    KEYS = ("pv", "haus", "akku", "netz", "soc")
    MAX_POINTS = 48 * 60

    def __init__(self, path):
        self.path = path
        self.lock = threading.Lock()
        self.points = []          # [minute_ts, pv, haus, akku, netz, soc]
        self._bucket = None
        self._acc = {}
        self._last_save = time.time()
        self.load()

    def load(self):
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
            pts = data.get("points", [])
            cutoff = time.time() - self.MAX_POINTS * 60
            self.points = [p for p in pts if isinstance(p, list) and len(p) == 6 and p[0] >= cutoff]
        except (OSError, ValueError):
            self.points = []

    def save(self):
        with self.lock:
            data = {"points": list(self.points)}
        tmp = self.path + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, separators=(",", ":"))
            os.replace(tmp, self.path)
        except OSError:
            pass

    def add(self, ts, values):
        minute = int(ts // 60) * 60
        with self.lock:
            if self._bucket is not None and minute != self._bucket:
                self._flush()
            self._bucket = minute
            for k in self.KEYS:
                v = values.get(k)
                if v is None:
                    continue
                s, n = self._acc.get(k, (0.0, 0))
                self._acc[k] = (s + v, n + 1)
        if time.time() - self._last_save > 300:
            self._last_save = time.time()
            self.save()

    def _flush(self):
        row = [self._bucket]
        for k in self.KEYS:
            s, n = self._acc.get(k, (0.0, 0))
            row.append(round(s / n, 1) if n else None)
        self._acc = {}
        self.points.append(row)
        if len(self.points) > self.MAX_POINTS:
            del self.points[: len(self.points) - self.MAX_POINTS]

    def get(self, hours):
        cutoff = time.time() - hours * 3600
        with self.lock:
            pts = [p for p in self.points if p[0] >= cutoff]
            if self._bucket is not None and self._acc:
                row = [self._bucket]
                for k in self.KEYS:
                    s, n = self._acc.get(k, (0.0, 0))
                    row.append(round(s / n, 1) if n else None)
                pts.append(row)
        return pts


class InverterPoller(threading.Thread):
    """Hält die (einzige) Modbus-Verbindung zum Wechselrichter.

    Alle Zugriffe – auch Schreibbefehle der Steuerung – laufen über diesen Thread,
    damit nie zwei Verbindungen gleichzeitig zum Gerät bestehen.
    """

    SLOW_INTERVAL = 60          # Steuer-Einstellungen alle 60 s lesen

    def __init__(self, cfg_getter, history, log):
        super().__init__(daemon=True, name="Wechselrichter")
        self.cfg_getter = cfg_getter
        self.history = history
        self.log = log
        self.lock = threading.Lock()
        self.values = {}
        self.static = {}
        self.slow = {}
        self.state = {
            "verbunden": False, "fehler": "", "letzte_abfrage": 0, "dauer_ms": 0, "zyklen": 0,
            "akku_vorhanden": None, "zaehler_vorhanden": None,
            "verbunden_seit": 0, "abbrueche": 0, "letzter_abbruch": 0, "letzte_ursache": "",
            "zeitueberschreitungen": 0, "verbindungsaufbauten": 0, "naechster_versuch": 0,
            "pausiert": False,
        }
        self.listeners = []
        self.beat = time.time()            # Lebenszeichen für den Watchdog
        self._stop_ev = threading.Event()
        self._wake = threading.Event()
        self._reload = False
        self._suspend = 0
        self._cmds = queue.Queue()
        self._client = None
        self._cfg_key = None
        self._skip = set()
        self._blocks_fast = []
        self._blocks_slow = []
        self._slow_due = 0
        self._fails = 0
        self._next_try = 0
        self._soft_in_row = 0
        self._lost_at = 0

    # ------------------------------------------------------------------ API
    def stop(self):
        self._stop_ev.set()
        self._wake.set()

    def reload(self):
        """Nach Änderung der Einstellungen neu verbinden."""
        self._reload = True
        self._next_try = 0
        self._wake.set()

    def snapshot(self):
        with self.lock:
            return dict(self.values), dict(self.static), dict(self.state)

    def execute(self, fn, timeout=90):
        """Führt fn(client) im Abfrage-Thread aus (für Schreibbefehle)."""
        if not self.is_alive():
            raise ModbusError("Abfrage-Thread läuft nicht")
        box = {"ev": threading.Event()}
        self._cmds.put((fn, box))
        self._wake.set()
        if not box["ev"].wait(timeout):
            raise ModbusError("Zeitüberschreitung beim Ausführen")
        if "err" in box:
            raise box["err"]
        return box.get("res")

    def suspend(self):
        """Verbindung vorübergehend freigeben (z. B. für Verbindungstest)."""
        self._suspend += 1
        self._wake.set()
        t0 = time.time()
        while time.time() - t0 < 20 and self._client is not None and self._client.connected:
            time.sleep(0.1)

    def resume(self):
        self._suspend = max(0, self._suspend - 1)
        self._next_try = 0
        self._wake.set()

    def watchdog(self):
        """Vom Hauptthread regelmäßig aufgerufen. Löst hängende Anfragen."""
        c = self.cfg_getter()["wechselrichter"]
        limit = float(c["timeout_s"]) * 6 + float(c["intervall_s"]) + 120
        if time.time() - self.beat > limit and self._client is not None:
            self.log(f"Watchdog: Abfrage hängt seit {int(time.time() - self.beat)} s – Verbindung wird neu aufgebaut")
            self.beat = time.time()
            self._client.abort()

    # ------------------------------------------------------------------ Schleife
    def run(self):
        while not self._stop_ev.is_set():
            self.beat = time.time()
            try:
                self._loop_once()
            except Exception as e:  # noqa: BLE001 – der Thread darf NIE sterben
                tb = traceback.extract_tb(e.__traceback__)
                where = f" ({os.path.basename(tb[-1].filename)}:{tb[-1].lineno})" if tb else ""
                self.log(f"Unerwarteter Fehler in der Abfrage: {type(e).__name__}: {e}{where}")
                self._hard_fail(e)
                self._sleep(5)
        if self._client:
            self._client.close()

    def _sleep(self, s):
        if s > 0 and not self._stop_ev.is_set():
            self._wake.wait(s)
            self._wake.clear()

    def _fail_commands(self, msg):
        while True:
            try:
                _fn, box = self._cmds.get_nowait()
            except queue.Empty:
                return
            box["err"] = ModbusError(msg)
            box["ev"].set()

    def _loop_once(self):
        cfg = self.cfg_getter()
        c = cfg["wechselrichter"]

        if self._suspend:
            if self._client:
                self._client.close()
            with self.lock:
                self.state.update(pausiert=True)
            self._fail_commands("Verbindung ist gerade pausiert")
            self._sleep(0.3)
            return
        if self.state.get("pausiert"):
            with self.lock:
                self.state["pausiert"] = False

        if not c["host"]:
            self._set_state(verbunden=False, fehler="Keine Wechselrichter-Adresse eingestellt")
            self._fail_commands("Kein Wechselrichter eingestellt")
            self._sleep(2)
            return

        key = (c["host"], c["port"], c["unit_id"], c["timeout_s"], c["verbindungs_pause_s"])
        if self._client is None or self._reload or key != self._cfg_key:
            self._reload = False
            if self._client:
                self._client.close()
            self._make_client(c, key)

        if not self._client.connected:
            wait = self._next_try - time.time()
            if wait > 0:
                self._fail_commands(f"Nicht verbunden – nächster Versuch in {int(wait) + 1} s")
                self._sleep(min(wait, 5))
                return
            try:
                self._client.connect()
                with self.lock:
                    self.state["verbindungsaufbauten"] += 1
            except OSError as e:
                self._hard_fail(e)
                return

        # Steuerbefehle zuerst (zwischen den Lesezyklen)
        self._run_commands()

        t0 = time.time()
        try:
            if not self.static:
                self._read_static()
            vals = self._read_cycle()
        except ModbusTimeout as e:
            self._soft_fail(e)
            return
        except ModbusException as e:
            if e.code in ModbusException.TRANSIENT:
                self._soft_fail(e)
                return
            self._hard_fail(e)
            return
        except (ModbusError, OSError) as e:
            self._hard_fail(e)
            return

        self._success(vals, t0)
        wait = max(0.5, float(c["intervall_s"]) - (time.time() - t0))
        self._sleep(wait)

    # ------------------------------------------------------------------
    def _make_client(self, c, key):
        self._client = ModbusTcpClient(c["host"], c["port"], c["unit_id"], timeout=c["timeout_s"],
                                       connect_delay=c["verbindungs_pause_s"])
        self._cfg_key = key
        self._skip = set()
        self._rebuild_blocks()
        self._slow_due = 0
        self._fails = 0
        self._next_try = 0
        with self.lock:
            self.static = {}
            self.values = {}
            self.slow = {}

    def _rebuild_blocks(self):
        fast = [r for r in REGISTERS if r.group not in STATIC_GROUPS | SLOW_GROUPS and r.key not in self._skip]
        slow = [r for r in REGISTERS if r.group in SLOW_GROUPS and r.key not in self._skip]
        self._blocks_fast = build_blocks(fast)
        self._blocks_slow = build_blocks(slow)

    def _run_commands(self):
        while True:
            try:
                fn, box = self._cmds.get_nowait()
            except queue.Empty:
                return
            try:
                box["res"] = fn(self._client)
                self._slow_due = 0          # Einstellungen sofort neu lesen
            except Exception as e:  # noqa: BLE001
                box["err"] = e
                if isinstance(e, ModbusError) and not isinstance(e, (ModbusException, ModbusTimeout)):
                    self._client.close()
            box["ev"].set()

    def _success(self, vals, t0):
        now = time.time()
        reconnected = not self.state["verbunden"]
        dur = int((now - t0) * 1000)
        if reconnected:
            if self._lost_at:
                self.log(f"Verbindung wiederhergestellt nach {fmt_dauer(now - self._lost_at)}")
            self._lost_at = 0
        self._fails = 0
        self._soft_in_row = 0
        with self.lock:
            self.values = vals
            self.state.update(verbunden=True, fehler="", letzte_abfrage=now, dauer_ms=dur,
                              zyklen=self.state["zyklen"] + 1, naechster_versuch=0,
                              akku_vorhanden=vals.get("_akku"), zaehler_vorhanden=vals.get("_zaehler"))
            if reconnected:
                self.state["verbunden_seit"] = now
        self.history.add(now, {
            "pv": vals.get("pv_leistung"), "haus": vals.get("haus_verbrauch"),
            "akku": vals.get("akku_leistung") if vals.get("_akku") else None,
            "netz": vals.get("netz_leistung") if vals.get("_zaehler") else None,
            "soc": vals.get("akku_soc") if vals.get("_akku") else None})
        for fn in list(self.listeners):
            try:
                fn(vals, dict(self.static))
            except Exception as e:  # noqa: BLE001
                self.log(f"Fehler beim Weiterleiten: {e}")

    def _soft_fail(self, e):
        """Zeitüberschreitung / Gerät beschäftigt: Verbindung behalten, gleich erneut versuchen."""
        self._soft_in_row += 1
        msg = friendly(e)
        with self.lock:
            self.state["zeitueberschreitungen"] += 1
            self.state["fehler"] = msg
        if self._soft_in_row == 1:
            self.log(f"Wechselrichter: {msg} (Verbindung bleibt bestehen)")
        self._run_commands()
        self._sleep(min(5, 1 + self._soft_in_row))

    def _hard_fail(self, e):
        now = time.time()
        msg = friendly(e)
        if self._client:
            self._client.close()
        self._fails += 1
        delay = min(60, 5 * 2 ** min(self._fails - 1, 4))      # 5,10,20,40,60 s
        self._next_try = now + delay
        with self.lock:
            was = self.state["verbunden"]
            self.state.update(verbunden=False, fehler=msg, naechster_versuch=self._next_try)
            if was:
                self.state["abbrueche"] += 1
                self.state["letzter_abbruch"] = now
                self.state["letzte_ursache"] = msg
        if was:
            self._lost_at = now
            self.log(f"Verbindung verloren: {msg} – neuer Versuch in {delay} s")
        elif self._fails == 1 or self._fails % 10 == 0:
            self.log(f"Wechselrichter nicht erreichbar: {msg} (Versuch {self._fails}, nächster in {delay} s)")
        if not self._lost_at:
            self._lost_at = now
        self._fail_commands(f"Nicht verbunden: {msg}")

    def _set_state(self, **kw):
        with self.lock:
            self.state.update(kw)

    # ------------------------------------------------------------------
    def _read_static(self):
        st = {}
        for r in REGISTERS:
            if r.group not in STATIC_GROUPS:
                continue
            try:
                st[r.key] = decode(r, self._client.read_holding(r.addr, r.size))
            except ModbusException as e:
                if e.code in (2, 3):
                    st[r.key] = None
                else:
                    raise
        with self.lock:
            self.static = st
        self.log(f"Verbunden mit {st.get('modell') or 'Wechselrichter'} (SN {st.get('seriennummer') or '?'})")

    def _read_blocks(self, blocks):
        vals = {}
        skipped_before = len(self._skip)
        for start, count, regs in blocks:
            regs = [r for r in regs if r.key not in self._skip]
            if not regs:
                continue
            try:
                words = self._client.read_holding(start, count)
                for r in regs:
                    off = r.addr - start
                    vals[r.key] = decode(r, words[off:off + r.size])
            except ModbusException as e:
                if e.code not in (2, 3):
                    raise
                # Block enthält unbekannte Register -> einzeln lesen
                for r in regs:
                    try:
                        vals[r.key] = decode(r, self._client.read_holding(r.addr, r.size))
                    except ModbusException as e2:
                        if e2.code in (2, 3):
                            self._skip.add(r.key)
                            vals[r.key] = None
                        else:
                            raise
        if len(self._skip) != skipped_before:
            self._rebuild_blocks()
            self.log(f"Vom Gerät nicht unterstützt: {', '.join(sorted(self._skip))}")
        return vals

    def _read_cycle(self):
        vals = self._read_blocks(self._blocks_fast)
        if time.time() >= self._slow_due:
            slow = self._read_blocks(self._blocks_slow)
            self.slow = slow
            self._slow_due = time.time() + self.SLOW_INTERVAL
        vals.update(self.slow)
        for k in self._skip:
            vals[k] = None
        self._derive(vals)
        return vals

    def _derive(self, v):
        n_str = self.static.get("pv_strings") or 2
        for i in range(1, 5):
            u, a = v.get(f"pv{i}_u"), v.get(f"pv{i}_i")
            if i > n_str:
                v[f"pv{i}_u"] = v[f"pv{i}_i"] = v[f"pv{i}_p"] = None
                continue
            v[f"pv{i}_p"] = round(u * a) if u is not None and a is not None else None

        code = v.get("wr_status")
        v["wr_status_text"] = WR_STATUS.get(code, f"Unbekannt (0x{code:04X})") if code is not None else None

        akku = bool(v.get("akku_kapazitaet")) or (v.get("akku_status") not in (None, 0))
        v["_akku"] = akku
        ak = v.get("akku_status")
        v["akku_status_text"] = AKKU_STATUS.get(ak, f"Code {ak}") if ak is not None else None
        p = v.get("akku_leistung")
        v["akku_laden"] = max(p, 0) if p is not None else None
        v["akku_entladen"] = max(-p, 0) if p is not None else None

        zaehler = v.get("zaehler_status") == 1
        v["_zaehler"] = zaehler
        g = v.get("netz_leistung") if zaehler else None
        v["netz_einspeisung"] = max(g, 0) if g is not None else None
        v["netz_bezug"] = max(-g, 0) if g is not None else None

        wr = v.get("wr_leistung")
        if wr is not None and g is not None:
            haus = max(wr - g, 0)
            v["haus_verbrauch"] = haus
            pv = v.get("pv_leistung") or 0
            bezug = v["netz_bezug"] or 0
            v["autarkie_pct"] = round(100 * (haus - bezug) / haus, 1) if haus > 0 else None
            einsp = v["netz_einspeisung"] or 0
            v["eigenverbrauch_pct"] = round(100 * max(pv - einsp, 0) / pv, 1) if pv > 50 else None
        else:
            v["haus_verbrauch"] = None
            v["autarkie_pct"] = None
            v["eigenverbrauch_pct"] = None

        m = v.get("st_modus")
        v["st_modus_text"] = ARBEITSMODUS.get(m, f"Code {m}") if m is not None else None
        z = v.get("st_zwang")
        v["st_zwang_text"] = ZWANG.get(z, f"Code {z}") if z is not None else None
        e = v.get("st_einspeise_modus")
        v["st_einspeise_text"] = EINSPEISE_MODUS.get(e, f"Code {e}") if e is not None else None


def fmt_dauer(s):
    s = int(s)
    if s < 120:
        return f"{s} s"
    if s < 7200:
        return f"{s // 60} min"
    return f"{s // 3600} h {(s % 3600) // 60} min"


def test_connection(host, port, unit_ids, timeout=8.0, delay=1.5):
    """Probiert die Unit-IDs nacheinander und liefert die erste, die antwortet."""
    from .registers import BY_KEY
    results = []
    for uid in unit_ids:
        c = ModbusTcpClient(host, port, uid, timeout=timeout, connect_delay=delay, max_timeouts=1)
        try:
            c.connect()
            m = decode(BY_KEY["modell"], c.read_holding(30000, 15, retries=1))
            sn = decode(BY_KEY["seriennummer"], c.read_holding(30015, 10, retries=1))
            results.append({"unit_id": uid, "ok": True, "modell": m, "seriennummer": sn})
            return {"ok": True, "unit_id": uid, "modell": m, "seriennummer": sn, "versuche": results}
        except (ModbusError, OSError) as e:
            results.append({"unit_id": uid, "ok": False, "fehler": friendly(e)})
            if isinstance(e, OSError) and not isinstance(e, (socket.timeout, TimeoutError)):
                break           # Verbindung grundsätzlich nicht möglich -> weitere IDs sinnlos
        finally:
            c.close()
    return {"ok": False, "versuche": results}
