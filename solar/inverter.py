"""Abfrage-Schleife für den Wechselrichter: liest Register, bildet abgeleitete Werte,
führt den Verlauf und meldet neue Daten an Abonnenten (z. B. MQTT)."""

import json
import os
import threading
import time

from .modbus import ModbusTcpClient, ModbusError, ModbusException, friendly
from .registers import (REGISTERS, DERIVED, STATIC_GROUPS, WR_STATUS, AKKU_STATUS,
                        build_blocks, decode)


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
    def __init__(self, cfg_getter, history, log):
        super().__init__(daemon=True, name="Wechselrichter")
        self.cfg_getter = cfg_getter
        self.history = history
        self.log = log
        self.lock = threading.Lock()
        self.values = {}
        self.static = {}
        self.state = {"verbunden": False, "fehler": "", "letzte_abfrage": 0, "dauer_ms": 0,
                      "zyklen": 0, "akku_vorhanden": None, "zaehler_vorhanden": None}
        self.listeners = []
        self._stop = threading.Event()
        self._reload = threading.Event()
        self._client = None
        self._skip = set()          # Register, die das Gerät nicht kennt
        self._blocks = []

    # ------------------------------------------------------------------
    def stop(self):
        self._stop.set()
        self._reload.set()

    def reload(self):
        """Nach Änderung der Einstellungen neu verbinden."""
        self._reload.set()

    def snapshot(self):
        with self.lock:
            return dict(self.values), dict(self.static), dict(self.state)

    # ------------------------------------------------------------------
    def _make_client(self):
        c = self.cfg_getter()["wechselrichter"]
        self._client = ModbusTcpClient(c["host"], c["port"], c["unit_id"],
                                       timeout=c["timeout_s"], connect_delay=c["verbindungs_pause_s"])
        self._skip = set()
        dyn = [r for r in REGISTERS if r.group not in STATIC_GROUPS]
        self._blocks = build_blocks(dyn)
        with self.lock:
            self.static = {}
            self.values = {}

    def run(self):
        backoff = 2
        while not self._stop.is_set():
            cfg = self.cfg_getter()
            if not cfg["wechselrichter"]["host"]:
                self._set_state(verbunden=False, fehler="Keine Wechselrichter-Adresse eingestellt")
                self._wait(2)
                continue
            if self._client is None or self._reload.is_set():
                self._reload.clear()
                if self._client:
                    self._client.close()
                self._make_client()
            t0 = time.time()
            try:
                if not self.static:
                    self._read_static()
                vals = self._read_dynamic()
                self._derive(vals)
                dur = int((time.time() - t0) * 1000)
                with self.lock:
                    self.values = vals
                    self.state.update(verbunden=True, fehler="", letzte_abfrage=time.time(), dauer_ms=dur,
                                      zyklen=self.state["zyklen"] + 1,
                                      akku_vorhanden=vals.get("_akku"), zaehler_vorhanden=vals.get("_zaehler"))
                self.history.add(time.time(), {
                    "pv": vals.get("pv_leistung"), "haus": vals.get("haus_verbrauch"),
                    "akku": vals.get("akku_leistung") if vals.get("_akku") else None,
                    "netz": vals.get("netz_leistung") if vals.get("_zaehler") else None,
                    "soc": vals.get("akku_soc") if vals.get("_akku") else None})
                for fn in list(self.listeners):
                    try:
                        fn(vals, dict(self.static))
                    except Exception as e:  # noqa: BLE001
                        self.log(f"Fehler beim Weiterleiten: {e}")
                backoff = 2
                wait = max(0.5, float(cfg["wechselrichter"]["intervall_s"]) - (time.time() - t0))
                self._wait(wait)
            except (ModbusError, OSError) as e:
                msg = friendly(e) if not isinstance(e, ModbusError) else str(e)
                if self.state.get("fehler") != msg:
                    self.log(f"Wechselrichter: {msg}")
                self._set_state(verbunden=False, fehler=msg)
                if self._client:
                    self._client.close()
                self._wait(backoff)
                backoff = min(backoff * 2, 30)

    def _wait(self, s):
        if not self._stop.is_set():
            self._reload.wait(s)

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

    def _read_dynamic(self):
        vals = {}
        skipped_before = len(self._skip)
        for start, count, regs in self._blocks:
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
            # Blöcke ohne die unbekannten Register neu bilden
            dyn = [r for r in REGISTERS if r.group not in STATIC_GROUPS and r.key not in self._skip]
            self._blocks = build_blocks(dyn)
            self.log(f"Vom Gerät nicht unterstützt: {', '.join(sorted(self._skip))}")
        for k in self._skip:
            vals[k] = None
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


def test_connection(host, port, unit_ids, timeout=5.0, delay=1.5):
    """Probiert die Unit-IDs nacheinander und liefert die erste, die antwortet."""
    from .registers import BY_KEY
    results = []
    for uid in unit_ids:
        c = ModbusTcpClient(host, port, uid, timeout=timeout, connect_delay=delay)
        try:
            c.connect()
            m = decode(BY_KEY["modell"], c.read_holding(30000, 15, retries=1))
            sn = decode(BY_KEY["seriennummer"], c.read_holding(30015, 10, retries=1))
            results.append({"unit_id": uid, "ok": True, "modell": m, "seriennummer": sn})
            return {"ok": True, "unit_id": uid, "modell": m, "seriennummer": sn, "versuche": results}
        except (ModbusError, OSError) as e:
            results.append({"unit_id": uid, "ok": False,
                            "fehler": str(e) if isinstance(e, ModbusError) else friendly(e)})
            if isinstance(e, OSError) and not isinstance(e, socket_timeout_types()):
                # Verbindung grundsätzlich nicht möglich -> weitere IDs sinnlos
                break
        finally:
            c.close()
    return {"ok": False, "versuche": results}


def socket_timeout_types():
    import socket
    return (socket.timeout, TimeoutError)
