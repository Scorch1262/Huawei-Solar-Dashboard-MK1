"""Smart-Laden: Akku bei günstigem Börsenstrompreis aus dem Netz laden –
aber nur so weit, dass der erwartete PV-Überschuss später noch Platz hat.

Ablauf
1. Preise (EPEX Day-Ahead) und PV-Prognose (Open-Meteo) werden regelmäßig geholt.
2. Eigene Statistik: Hausverbrauch und PV-Leistung je Stunde (letzte 21 Tage).
   Daraus Verbrauchsprofil, PV-Statistik (Ersatz für die Wetterprognose) und
   eine Kalibrierung der Prognose auf die eigene Anlage.
3. Planer: Viertelstunden-Simulation des Akkustands über den Vorausschau-Horizont.
   Netzladung wird den günstigsten Zeitfenstern im Preisbereich zugeteilt –
   jeweils höchstens so viel, wie später NICHT zu verlorenem PV-Überschuss führt
   (Akku voll, PV muss eingespeist werden) und bis maximal zum Ziel-SOC.
4. Ausführung: Zwangsladen (Dauer-Modus, max. 60 min, wird verlängert) über die
   einzige Modbus-Verbindung. Läuft das Programm nicht mehr, endet das Laden
   spätestens nach Ablauf der Dauer von selbst.
"""

import json
import math
import os
import threading
import time

from .control import ControlError, make_executor
from .internet import FetchError, fetch_prices, fetch_pv_forecast
from .modbus import ModbusError

STEP = 900                       # 15 Minuten
MAX_CMD_MIN = 60                 # Zwangsladen höchstens 60 min am Stück beauftragen


TAGE = ("Mo", "Di", "Mi", "Do", "Fr", "Sa", "So")


def fmt_tag_zeit(ts):
    lt = time.localtime(ts)
    heute = time.localtime()
    pre = "" if lt.tm_yday == heute.tm_yday else TAGE[lt.tm_wday] + " "
    return pre + time.strftime("%H:%M", lt)


def hour_key(ts):
    return time.strftime("%Y-%m-%d %H", time.localtime(ts))


class Stats:
    """Stundenwerte: Hausverbrauch, PV, PV-Prognose (für Profile und Kalibrierung)."""

    KEEP_DAYS = 21

    def __init__(self, path):
        self.path = path
        self.lock = threading.Lock()
        self.h = {}              # "YYYY-MM-DD HH" -> {"pv":[sum,n], "haus":[sum,n], "prog": w}
        self._saved = time.time()
        try:
            with open(path, "r", encoding="utf-8") as f:
                self.h = json.load(f).get("stunden", {})
        except (OSError, ValueError):
            self.h = {}

    def save(self):
        with self.lock:
            cutoff = hour_key(time.time() - self.KEEP_DAYS * 86400)
            self.h = {k: v for k, v in self.h.items() if k >= cutoff}
            data = json.dumps({"stunden": self.h}, separators=(",", ":"))
        tmp = self.path + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                f.write(data)
            os.replace(tmp, self.path)
        except OSError:
            pass

    def add(self, ts, pv, haus):
        k = hour_key(ts)
        with self.lock:
            e = self.h.setdefault(k, {})
            for name, v in (("pv", pv), ("haus", haus)):
                if v is not None:
                    s = e.setdefault(name, [0.0, 0])
                    s[0] += float(v)
                    s[1] += 1
        if time.time() - self._saved > 600:
            self._saved = time.time()
            self.save()

    def set_forecast(self, ts, w):
        k = hour_key(ts)
        with self.lock:
            self.h.setdefault(k, {})["prog"] = round(w)

    def _profile(self, name, days):
        cutoff = hour_key(time.time() - days * 86400)
        now_k = hour_key(time.time())
        acc = {}
        with self.lock:
            for k, e in self.h.items():
                if k < cutoff or k >= now_k or name not in e:
                    continue
                s, n = e[name]
                if n < 20:                     # Stunde nicht ausreichend erfasst
                    continue
                hr = int(k[-2:])
                a = acc.setdefault(hr, [0.0, 0])
                a[0] += s / n
                a[1] += 1
        return {hr: a[0] / a[1] for hr, a in acc.items()}

    def load_profile(self):
        return self._profile("haus", 14)

    def pv_profile(self):
        return self._profile("pv", 14)

    def days_with_data(self):
        with self.lock:
            return len({k[:10] for k, e in self.h.items() if "haus" in e and e["haus"][1] >= 20})

    def calibration(self):
        """Verhältnis gemessene PV / Prognose (letzte 14 Tage), sonst None."""
        cutoff = hour_key(time.time() - 14 * 86400)
        now_k = hour_key(time.time())
        act = prog = 0.0
        n = 0
        with self.lock:
            for k, e in self.h.items():
                if k < cutoff or k >= now_k or "prog" not in e or "pv" not in e:
                    continue
                s, c = e["pv"]
                if c < 20 or e["prog"] < 300:
                    continue
                act += s / c
                prog += e["prog"]
                n += 1
        if n < 12 or prog <= 0:
            return None, n
        return max(0.5, min(1.3, act / prog)), n


# --------------------------------------------------------------------------
def end_price(eur_mwh, p):
    """Börsenpreis (EUR/MWh) -> ct/kWh inkl. Aufschlag und MwSt laut Einstellungen."""
    return (eur_mwh / 10.0 + float(p["aufschlag_ct"])) * (1 + float(p["mwst_pct"]) / 100.0)


def build_plan(p, now, price_slots, pv_slots, batt, load_profile, pv_profile, calib):
    """Reiner Rechenteil (ohne Seiteneffekte) – auch für die Live-Vorschau der Regler.

    p      : Einstellungen (smart)
    batt   : dict soc_pct, cap_wh, max_pct, min_pct, p_charge, p_discharge
    """
    t0 = int(now // STEP * STEP)
    n = max(4, int(float(p["horizont_h"]) * 3600 // STEP))
    use_wetter = p["prognose"] == "wetter" and pv_slots
    factor = (calib if (p["kalibrierung"] and calib) else 1.0)
    vertrauen = float(p["pv_vertrauen_pct"]) / 100.0
    kwp_w = float(p["kwp"]) * 1000.0
    eff = float(p["wirkungsgrad_pct"]) / 100.0

    def slot_val(slots, t):
        for s, e, v in slots:
            if s <= t < e:
                return v
        return None

    steps = []
    for i in range(n):
        t = t0 + i * STEP
        mid = t + STEP // 2
        hr = time.localtime(mid).tm_hour
        eur = slot_val(price_slots, mid)
        ct = round(end_price(eur, p), 2) if eur is not None else None
        if use_wetter:
            g = slot_val(pv_slots, mid)
            pv = min(kwp_w, max(0.0, g / 1000.0 * kwp_w * eff * factor)) if g is not None else None
        else:
            pv = pv_profile.get(hr)
        if pv is None:
            pv = 0.0
        load = load_profile.get(hr, float(p["grundlast_w"]))
        steps.append({"t": t, "preis_ct": ct, "pv_w": round(pv), "pv_plan_w": round(pv * vertrauen),
                      "last_w": round(load),
                      "im_bereich": ct is not None and float(p["preis_min_ct"]) <= ct <= float(p["preis_max_ct"]),
                      "netz_wh": 0.0, "grund": ""})

    cap = batt["cap_wh"]
    smax = cap * batt["max_pct"] / 100.0
    smin = cap * batt["min_pct"] / 100.0
    ziel = min(smax, cap * float(p["ziel_soc"]) / 100.0)
    dt_h = STEP / 3600.0
    pc = batt["p_charge"] * dt_h
    pdis = batt["p_discharge"] * dt_h
    s0 = cap * batt["soc_pct"] / 100.0
    pgrid = min(float(p["ladeleistung_w"]), batt["p_charge"]) * dt_h

    def sim(g):
        soc = s0
        spill = 0.0
        socs = []
        for i, st in enumerate(steps):
            socs.append(soc)
            net = (st["pv_plan_w"] - st["last_w"]) * dt_h            # Wh in diesem Schritt
            if g[i] > 0:
                # Zwangsladen: Hauslast kommt aus dem Netz, PV-Überschuss + Netz laden den Akku
                want = g[i] + max(net, 0.0)
                room = max(0.0, smax - soc)
                ch = min(want, pc, room)
                spill += max(0.0, max(net, 0.0) - max(0.0, ch - g[i]))
                soc += ch
            elif net >= 0:
                ch = min(net, pc, max(0.0, smax - soc))
                spill += net - ch
                soc += ch
            else:
                soc -= min(-net, pdis, max(0.0, soc - smin))
        return spill, socs

    g = [0.0] * n
    spill0, socs = sim(g)
    base_socs = socs
    cand = sorted((i for i, st in enumerate(steps) if st["im_bereich"] and st["t"] + STEP > now),
                  key=lambda i: (steps[i]["preis_ct"], i))
    hyst = 0.03 * cap                                  # erst nachladen, wenn 3 % unter dem Ziel
    for i in cand:
        room = ziel - socs[i]
        if room < max(25.0, hyst) and not (i > 0 and g[i - 1] > 0 and room >= 25):
            steps[i]["grund"] = "Ziel-SOC erreicht"
            continue
        x = min(pgrid, room)
        if i == 0:                                   # angebrochene Viertelstunde
            x *= max(0.0, (t0 + STEP - now) / STEP)
        if x < 25:
            continue
        ok = False
        for _ in range(4):
            g[i] += x
            sp, s2 = sim(g)
            extra = sp - spill0
            if extra <= 5:
                ok = True
                spill0, socs = sp, s2
                break
            g[i] -= x
            x = x - extra
            if x < 25:
                break
        if not ok:
            steps[i]["grund"] = "PV-Überschuss erwartet"
    for i, st in enumerate(steps):
        st["netz_wh"] = round(g[i], 1)
        st["soc_pct"] = round(100 * socs[i] / cap, 1) if cap else None
        st["soc_ohne_pct"] = round(100 * base_socs[i] / cap, 1) if cap else None

    # Zusammenfassung
    total = sum(g)
    cost = sum(g[i] * steps[i]["preis_ct"] for i in range(n) if g[i] > 0)
    now_w = 0
    block_end = None
    if g[0] > 0:
        rem = t0 + STEP - now                          # Restzeit der laufenden Viertelstunde (s)
        w = g[0] / (rem / 3600.0) if rem > 30 else float(p["ladeleistung_w"])
        now_w = int(round(min(float(p["ladeleistung_w"]), w) / 100.0) * 100)
        now_w = max(now_w, 300)
        j = 0
        while j < n and g[j] > 0:
            j += 1
        block_end = t0 + j * STEP
    nxt = next((steps[i]["t"] for i in range(n) if g[i] > 0), None)
    pv_blocked = sum(1 for st in steps if st["grund"] == "PV-Überschuss erwartet")
    return {
        "schritte": steps, "geplant_kwh": round(total / 1000, 2),
        "kosten_ct_kwh": round(cost / total, 2) if total > 0 else None,
        "jetzt_w": now_w, "block_ende": block_end, "naechste_ladung": nxt,
        "pv_gesperrt": pv_blocked, "kalibrierung": factor if use_wetter else None,
        "quelle_pv": "Wetterprognose" if use_wetter else "Eigene Statistik",
        "ziel_wh": round(ziel), "kapazitaet_wh": cap,
    }


# --------------------------------------------------------------------------
class SmartCharger(threading.Thread):
    def __init__(self, cfg_getter, poller, stats, log):
        super().__init__(daemon=True, name="Smart-Laden")
        self.cfg_getter = cfg_getter
        self.poller = poller
        self.stats = stats
        self.log = log
        self.lock = threading.Lock()
        self.prices = []            # (start, ende, eur_mwh)
        self.price_src = ""
        self.price_err = ""
        self.price_at = 0
        self.pv = []                # (start, ende, w_m2)
        self.pv_err = ""
        self.pv_at = 0
        self.pv_key = None
        self.plan = None
        self.status = "Automatik aus"
        self.active = False         # von uns gestartetes Zwangsladen läuft
        self.cmd_end = 0
        self.cmd_power = 0
        self.last_cmd = 0
        self._wake = threading.Event()
        self._stop_ev = threading.Event()
        self._next_price = 0
        self._next_pv = 0

    # ------------------------------------------------------------------
    def on_values(self, vals, static):
        try:
            self.stats.add(time.time(), vals.get("pv_leistung"),
                           vals.get("haus_verbrauch") if vals.get("_zaehler") else None)
        except Exception as e:  # noqa: BLE001
            self.log(f"Statistik: {e}")

    def poke(self):
        """Einstellungen geändert -> sofort neu abrufen/planen."""
        self._next_pv = 0
        self._next_price = min(self._next_price, time.time() + 2)
        self._wake.set()

    def stop(self):
        self._stop_ev.set()
        self._wake.set()

    # ------------------------------------------------------------------
    def battery(self, vals):
        cap = vals.get("akku_kapazitaet") or 0
        return {
            "soc_pct": vals.get("akku_soc") or 0.0,
            "cap_wh": float(cap),
            "max_pct": float(vals.get("st_ladeschluss") or 100.0),
            "min_pct": float(vals.get("st_entladeschluss") or 5.0),
            "p_charge": float(vals.get("akku_max_laden") or vals.get("st_max_laden") or 5000),
            "p_discharge": float(vals.get("akku_max_entladen") or vals.get("st_max_entladen") or 5000),
        }

    def compute(self, p=None):
        cfg = self.cfg_getter()
        p = p or cfg["smart"]
        vals, _static, _st = self.poller.snapshot()
        batt = self.battery(vals)
        if not batt["cap_wh"]:
            return None
        calib, _n = self.stats.calibration()
        with self.lock:
            prices, pv = list(self.prices), list(self.pv)
        return build_plan(p, time.time(), prices, pv, batt, self.stats.load_profile(),
                          self.stats.pv_profile(), calib)

    def price_now(self):
        now = time.time()
        with self.lock:
            for s, e, v in self.prices:
                if s <= now < e:
                    return v
        return None

    def snapshot(self):
        p = self.cfg_getter()["smart"]
        now = time.time()
        eur = self.price_now()
        lt = time.localtime(now)
        day0 = time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday, 0, 0, 0, 0, 0, -1))
        with self.lock:
            today = [end_price(v, p) for s, e, v in self.prices if day0 <= s < day0 + 86400]
            morgen = any(s >= day0 + 86400 for s, e, v in self.prices)
            pv = list(self.pv)
        cfgk = p["kwp"] * 1000 * p["wirkungsgrad_pct"] / 100
        calib, n_cal = self.stats.calibration()
        f = (calib if (p["kalibrierung"] and calib) else 1.0)

        def pv_kwh(a, b):
            return round(sum(max(0.0, min(e, b) - max(s, a)) / 3600 * g / 1000 * cfgk * f
                             for s, e, g in pv) / 1000, 1) if pv else None
        return {
            "status": self.status, "aktiv_laden": self.active,
            "preis_boerse_ct": round(eur / 10, 2) if eur is not None else None,
            "preis_ct": round(end_price(eur, p), 2) if eur is not None else None,
            "heute_min_ct": round(min(today), 2) if today else None,
            "heute_max_ct": round(max(today), 2) if today else None,
            "heute_mittel_ct": round(sum(today) / len(today), 2) if today else None,
            "morgen_verfuegbar": morgen,
            "preis_quelle": self.price_src, "preis_fehler": self.price_err, "preis_abruf": self.price_at,
            "pv_fehler": self.pv_err, "pv_abruf": self.pv_at,
            "pv_rest_heute_kwh": pv_kwh(now, day0 + 86400), "pv_morgen_kwh": pv_kwh(day0 + 86400, day0 + 2 * 86400),
            "kalibrierung": round(calib, 2) if calib else None, "kalibrierung_stunden": n_cal,
            "statistik_tage": self.stats.days_with_data(),
            "plan": self.plan,
        }

    def mqtt_items(self):
        s = self.snapshot()
        pl = s["plan"] or {}
        nxt = pl.get("naechste_ladung")
        return [
            ("strompreis/aktuell_ct", s["preis_ct"]), ("strompreis/boerse_ct", s["preis_boerse_ct"]),
            ("strompreis/heute_min_ct", s["heute_min_ct"]), ("strompreis/heute_max_ct", s["heute_max_ct"]),
            ("strompreis/heute_mittel_ct", s["heute_mittel_ct"]),
            ("prognose/pv_rest_heute_kwh", s["pv_rest_heute_kwh"]), ("prognose/pv_morgen_kwh", s["pv_morgen_kwh"]),
            ("smartladen/automatik", bool(self.cfg_getter()["smart"]["aktiv"])),
            ("smartladen/laedt", bool(self.active)), ("smartladen/status", s["status"]),
            ("smartladen/geplant_kwh", pl.get("geplant_kwh")),
            ("smartladen/naechste_ladung", time.strftime("%H:%M", time.localtime(nxt)) if nxt else "keine"),
        ]

    # ------------------------------------------------------------------
    def run(self):
        last_plan = 0
        while not self._stop_ev.is_set():
            try:
                self._fetch()
                if time.time() - last_plan >= 30 or self._wake.is_set() or self.plan is None:
                    self._wake.clear()
                    last_plan = time.time()
                    self._step()
            except Exception as e:  # noqa: BLE001 – Thread darf nicht sterben
                self.log(f"Smart-Laden: unerwarteter Fehler: {type(e).__name__}: {e}")
            self._wake.wait(5)

    def _fetch(self):
        p = self.cfg_getter()["smart"]
        now = time.time()
        lt = time.localtime(now)
        # Preise: stündlich; ab 13 Uhr alle 15 min, bis die Preise für morgen da sind
        if now >= self._next_price:
            try:
                src, slots = fetch_prices(p["zone"])
                with self.lock:
                    self.prices, self.price_src, self.price_err, self.price_at = slots, src, "", now
                self._wake.set()
                day_end = time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday, 23, 59, 59, 0, 0, -1))
                has_tomorrow = any(s > day_end for s, _e, _v in slots)
                self._next_price = now + (900 if (lt.tm_hour >= 13 and not has_tomorrow) else 3600)
            except FetchError as e:
                if self.price_err != str(e):
                    self.log(f"Strompreis: {e}")
                self.price_err = str(e)
                self._next_price = now + 300
        # PV-Prognose: stündlich (nur mit Standort)
        key = (p["lat"], p["lon"], p["neigung"], p["ausrichtung"])
        if p["ort_name"] and (now >= self._next_pv or key != self.pv_key):
            try:
                slots = fetch_pv_forecast(p["lat"], p["lon"], p["neigung"], p["ausrichtung"])
                with self.lock:
                    self.pv, self.pv_err, self.pv_at, self.pv_key = slots, "", now, key
                self._wake.set()
                kwp_w = p["kwp"] * 1000 * p["wirkungsgrad_pct"] / 100
                for s, e, g in slots:            # Prognose für Kalibrierung merken (nur Zukunft)
                    if s >= now - 60 and s < now + 86400:
                        self.stats.set_forecast(s, g / 1000 * kwp_w)
                self._next_pv = now + 3600
            except FetchError as e:
                if self.pv_err != str(e):
                    self.log(f"PV-Prognose: {e}")
                self.pv_err = str(e)
                self.pv_key = key
                self._next_pv = now + 600
        elif not p["ort_name"]:
            self.pv_err = "Kein Standort eingestellt – PV aus eigener Statistik"

    # ------------------------------------------------------------------
    def _step(self):
        cfg = self.cfg_getter()
        p = cfg["smart"]
        vals, _static, st = self.poller.snapshot()
        self.plan = self.compute() if st["verbunden"] and vals.get("_akku") else self.plan

        def stop(reason):
            self.status = reason
            if self.active:
                self._stop_charge(reason)

        if not p["aktiv"]:
            return stop("Automatik aus")
        if not cfg["steuerung"]["aktiv"]:
            return stop("Steuerung ist gesperrt (Einstellungen → Steuerung)")
        if not st["verbunden"]:
            self.status = "Wechselrichter nicht verbunden"
            return
        if not vals.get("_akku"):
            return stop("Kein Akku erkannt")
        if self.price_now() is None:
            return stop("Kein aktueller Strompreis")
        zw = vals.get("st_zwang")
        if zw and not self.active:
            self.status = "Manuelles Zwangsladen/-entladen aktiv – Automatik wartet"
            return
        if self.active and zw == 0 and time.time() < self.cmd_end - 60:
            self.log("Smart-Laden: Wechselrichter hat das Zwangsladen beendet")
            self.active = False
        pl = self.plan
        if pl is None:
            return stop("Kein Plan (Akkukapazität unbekannt)")
        now = time.time()
        if pl["jetzt_w"] > 0 and (vals.get("akku_soc") or 0) < float(p["ziel_soc"]):
            end = min(pl["block_ende"], now + MAX_CMD_MIN * 60)
            minutes = max(1, int(math.ceil((end - now) / 60)))
            need = (not self.active or abs(pl["jetzt_w"] - self.cmd_power) >= 300
                    or self.cmd_end - now < 300 or self.cmd_end > pl["block_ende"] + 180)
            if need and now - self.last_cmd > 60:
                self._start_charge(pl["jetzt_w"], minutes, vals)
            self.status = (f"Lädt aus dem Netz mit {pl['jetzt_w']} W bis "
                           f"{time.strftime('%H:%M', time.localtime(pl['block_ende']))}"
                           if self.active else self.status)
        else:
            if self.active:
                self._stop_charge("Ladefenster vorbei")
            if pl["naechste_ladung"]:
                self.status = "Wartet – nächste Netzladung " + fmt_tag_zeit(pl["naechste_ladung"])
            elif pl["pv_gesperrt"]:
                self.status = "Wartet – günstige Zeiten vorhanden, aber PV-Überschuss erwartet"
            elif (vals.get("akku_soc") or 0) >= float(p["ziel_soc"]):
                self.status = "Ziel-SOC erreicht"
            else:
                self.status = "Wartet – kein Zeitfenster im Preisbereich"

    def _write(self, writes):
        return self.poller.execute(make_executor(writes), timeout=120)

    def _start_charge(self, power, minutes, vals):
        self.last_cmd = time.time()
        try:
            if vals.get("st_netzladen") == 0:
                self._write([("st_netzladen", 1)])
                self.log("Smart-Laden: „Laden aus dem Netz“ eingeschaltet")
            self._write([("st_zwang_modus", 0), ("st_zwang_ladeleistung", power),
                         ("st_zwang_dauer", minutes), ("st_zwang", 1)])
            if not self.active:
                self.log(f"Smart-Laden: Netzladung gestartet ({power} W, {minutes} min, "
                         f"Preis {self.snapshot()['preis_ct']} ct/kWh)")
            self.active = True
            self.cmd_end = time.time() + minutes * 60
            self.cmd_power = power
        except (ControlError, ModbusError, OSError) as e:
            self.status = f"Fehler beim Starten: {e}"
            self.log(f"Smart-Laden: Start fehlgeschlagen: {e}")

    def _stop_charge(self, reason):
        self.last_cmd = time.time()
        try:
            self._write([("st_zwang", 0)])
            self.log(f"Smart-Laden: Netzladung beendet ({reason})")
            self.active = False
        except (ControlError, ModbusError, OSError) as e:
            self.log(f"Smart-Laden: Stopp fehlgeschlagen: {e} – Wechselrichter beendet spätestens "
                     f"nach Ablauf der Dauer selbst")
            if time.time() > self.cmd_end:
                self.active = False
