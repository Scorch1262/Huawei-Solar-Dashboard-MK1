"""Smart-Laden: Akku bei günstigem Börsenstrompreis aus dem Netz laden –
aber nur so weit, dass der erwartete PV-Überschuss später noch Platz hat.

Ablauf
1. Preise (EPEX Day-Ahead) und PV-Prognose (Open-Meteo) werden regelmäßig geholt.
2. Eigene Statistik: Hausverbrauch und PV-Leistung je Stunde (letzte 21 Tage).
   Daraus Verbrauchsprofil, PV-Statistik (Ersatz für die Wetterprognose) und
   eine Kalibrierung der Prognose auf die eigene Anlage.
3. Planer: Viertelstunden-Simulation des Akkustands über den Vorausschau-Horizont.
   Netzladung wird den günstigsten Zeitfenstern unter der Preisgrenze zugeteilt –
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

from collections import deque

from .control import ControlError, make_executor, write_guard
from .internet import CLOCK, FetchError, fetch_prices, fetch_pv_forecast
from .modbus import ModbusError

STEP = 900                       # 15 Minuten
MAX_CMD_MIN = 30                 # Zwangsladen höchstens 30 min am Stück beauftragen (endet dann von selbst)
MAX_CMDS_HOUR = 12               # Schreib-Budget der Automatik
MAX_CMDS_DAY = 80
MAX_PRICE_AGE = 3 * 3600         # Preisdaten höchstens 3 h alt
MAX_PV_AGE = 6 * 3600            # Wetterprognose höchstens 6 h alt
MAX_CLOCK_DIFF = 300             # PC-Uhr darf höchstens 5 min abweichen
MIN_STAT_DAYS = 3                # PV-Statistik als Ersatz erst ab 3 Tagen Messwerten
SCHNELL_MIN = 30                 # Schnellaktion: 30 min aus dem Netz laden
SCHNELL_MAX_SOC = 80             # ... nur unterhalb von 80 % SOC, endet spätestens bei 80 %


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
                      # eine Obergrenze: alles darunter zählt – auch negative Börsenpreise (günstigste Zeiten)
                      "im_bereich": ct is not None and ct <= float(p["preis_max_ct"]),
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
        """Liefert (verlorene PV-Energie, SOC je Schritt, tatsächliche Netzladung je Schritt).
        Netzladung wird hier hart auf den Ziel-SOC begrenzt – egal in welcher Reihenfolge
        der Planer die Schritte belegt hat."""
        soc = s0
        spill = 0.0
        socs = []
        eff = [0.0] * len(steps)
        for i, st in enumerate(steps):
            socs.append(soc)
            net = (st["pv_plan_w"] - st["last_w"]) * dt_h            # Wh in diesem Schritt
            gi = min(g[i], max(0.0, ziel - soc), pc) if g[i] > 0 else 0.0
            if gi > 0:
                # Zwangsladen: Hauslast kommt aus dem Netz, PV-Überschuss + Netz laden den Akku
                eff[i] = gi
                pv_in = min(max(net, 0.0), max(0.0, pc - gi), max(0.0, smax - soc - gi))
                spill += max(net, 0.0) - pv_in
                soc += gi + pv_in
            elif net >= 0:
                ch = min(net, pc, max(0.0, smax - soc))
                spill += net - ch
                soc += ch
            else:
                soc -= min(-net, pdis, max(0.0, soc - smin))
        return spill, socs, eff

    g = [0.0] * n
    spill0, socs, eff = sim(g)
    base_socs = socs
    spill_base = spill0
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
            sp, s2, e2 = sim(g)
            extra = sp - spill0
            if extra <= 5:
                ok = True
                spill0, socs, eff = sp, s2, e2
                break
            g[i] -= x
            x = x - extra
            if x < 25:
                break
        if not ok:
            steps[i]["grund"] = "PV-Überschuss erwartet"
    g = eff                                            # nur die tatsächlich wirksame Netzladung zählt
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
        "verlust_ohne_wh": round(spill_base, 1), "verlust_mit_wh": round(spill0, 1),
    }


# --------------------------------------------------------------------------
def safety_checks(cfg, vals, static, st, prices, price_at, pv_slots, pv_at, stat_days, clock, now,
                  fault, budget_ok, own_charge):
    """Alle Voraussetzungen für eine Netzladung. Liefert Liste (Bezeichnung, ok, Hinweis).
    Rein funktional – wird auch in den automatischen Tests geprüft."""
    p = cfg["smart"]
    out = []

    def add(name, ok, info=""):
        out.append((name, bool(ok), info))

    add("Automatik eingeschaltet", p["aktiv"], "" if p["aktiv"] else "aus")
    add("Keine Störung", not fault, fault or "")
    if p["probebetrieb"]:
        add("Schreibfreigabe", True, "Probebetrieb – es wird nichts geschrieben")
    else:
        reason = write_guard(cfg, static, st, now)
        add("Schreibfreigabe (PIN, bestätigte Anlage, Verbindung)", reason is None, reason or "")
    soc, cap = vals.get("akku_soc"), vals.get("akku_kapazitaet")
    akku_ok = bool(vals.get("_akku")) and soc is not None and 0 <= soc <= 100 and cap and 1000 <= cap <= 100000
    add("Akku erkannt und Werte plausibel", akku_ok,
        f"SOC {soc} %, Kapazität {cap} Wh" if not akku_ok else "")
    cur = [v for s, e, v in prices if s <= now < e]
    fresh = now - (price_at or 0) <= MAX_PRICE_AGE
    add("Aktueller Strompreis vorhanden", bool(cur) and fresh,
        "" if cur and fresh else ("Preisdaten zu alt" if cur else "kein Preis für jetzt"))
    if p["prognose"] == "wetter" and p["ort_name"]:
        ok = bool(pv_slots) and now - (pv_at or 0) <= MAX_PV_AGE and any(s > now + 3 * 3600 for s, _e, _g in pv_slots)
        add("PV-Prognose aktuell", ok, "" if ok else "Wetterprognose fehlt oder ist älter als 6 h")
    else:
        add("PV-Statistik ausreichend", stat_days >= MIN_STAT_DAYS,
            "" if stat_days >= MIN_STAT_DAYS else f"erst {stat_days} von {MIN_STAT_DAYS} Tagen Messwerte")
    off = clock.get("abweichung_s")
    clock_ok = off is not None and abs(off) <= MAX_CLOCK_DIFF and now - (clock.get("zeit") or 0) < 6 * 3600
    add("PC-Uhrzeit stimmt", clock_ok, "" if clock_ok else
        ("noch nicht geprüft" if off is None else f"Abweichung {off:+.0f} s zur Serverzeit"))
    zw = vals.get("st_zwang")
    add("Kein manuelles Zwangsladen aktiv", not zw or own_charge, "" if (not zw or own_charge) else "manuell gestartet")
    add("Schreib-Budget nicht erschöpft", budget_ok, "" if budget_ok else "zu viele Befehle – Störung")
    return out


class SmartCharger(threading.Thread):
    def __init__(self, cfg_getter, poller, stats, log, state_path=None):
        super().__init__(daemon=True, name="Smart-Laden")
        self.cfg_getter = cfg_getter
        self.poller = poller
        self.stats = stats
        self.log = log
        self.state_path = state_path
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
        self.checks = []
        self.fault = ""             # Störung -> Automatik gesperrt bis zum Quittieren
        self.active = False         # von uns gestartetes Zwangsladen läuft
        self.cmd_end = 0
        self.cmd_power = 0
        self.last_cmd = 0
        self.netzladen_vorher = None
        self.manual_until = 0          # Schnellaktion läuft bis
        self.sim_note = ""
        self.cmds = deque(maxlen=200)
        self._io = threading.RLock()        # Start/Stopp nie gleichzeitig
        self._wake = threading.Event()
        self._stop_ev = threading.Event()
        self._next_price = 0
        self._next_pv = 0
        self._load_state()

    # ------------------------------------------------------------------ Zustand
    def _load_state(self):
        if not self.state_path:
            return
        try:
            with open(self.state_path, "r", encoding="utf-8") as f:
                d = json.load(f)
            self.active = bool(d.get("aktiv_laden"))
            self.cmd_end = float(d.get("cmd_end") or 0)
            self.netzladen_vorher = d.get("netzladen_vorher")
            self.fault = d.get("stoerung") or ""
            self.manual_until = float(d.get("schnell_bis") or 0)
            if self.active:
                self.log("Smart-Laden: beim letzten Beenden lief noch eine Netzladung – wird nach dem Verbinden beendet")
        except (OSError, ValueError, TypeError):
            pass

    def _save_state(self):
        if not self.state_path:
            return
        tmp = self.state_path + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump({"aktiv_laden": self.active, "cmd_end": self.cmd_end,
                           "netzladen_vorher": self.netzladen_vorher, "stoerung": self.fault,
                           "schnell_bis": self.manual_until}, f)
            os.replace(tmp, self.state_path)
        except OSError:
            pass

    def _set_fault(self, text):
        if not self.fault:
            self.log(f"Smart-Laden: STÖRUNG – {text}. Automatik gesperrt bis zum Quittieren.")
        self.fault = text
        self._save_state()

    def acknowledge(self):
        self.fault = ""
        self.cmds.clear()
        self._save_state()
        self._wake.set()

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

    def shutdown(self):
        """Beim Programmende: eigene Netzladung beenden, Einstellung wiederherstellen."""
        if self.active or self.netzladen_vorher == 0:
            self._stop_charge("Programm wird beendet")

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

    def price_ct_at(self, ts):
        """Endpreis (ct/kWh) zu einem Zeitpunkt aus den geladenen Preisdaten, sonst None."""
        p = self.cfg_getter()["smart"]
        with self.lock:
            for s, e, v in self.prices:
                if s <= ts < e:
                    return round(end_price(v, p), 2)
        return None

    def price_slots_ct(self, t_from, t_to):
        """Endpreise (ct/kWh) als [[start, ende, ct], ...] im Zeitraum – für den Verlauf."""
        p = self.cfg_getter()["smart"]
        with self.lock:
            return [[s, e, round(end_price(v, p), 2)] for s, e, v in self.prices if e > t_from and s < t_to]

    def price_now(self):
        now = time.time()
        with self.lock:
            for s, e, v in self.prices:
                if s <= now < e:
                    return v
        return None

    def budget_ok(self, now=None):
        now = now or time.time()
        h = sum(1 for t in self.cmds if now - t < 3600)
        d = sum(1 for t in self.cmds if now - t < 86400)
        return h < MAX_CMDS_HOUR and d < MAX_CMDS_DAY

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
            "status": self.status, "aktiv_laden": self.active, "stoerung": self.fault,
            "probebetrieb": bool(p["probebetrieb"]), "probe_hinweis": self.sim_note,
            "pruefungen": [{"name": n, "ok": ok, "info": info} for n, ok, info in self.checks],
            "befehle_stunde": sum(1 for t in self.cmds if now - t < 3600),
            "uhr_abweichung_s": CLOCK.get("abweichung_s"),
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
        p = self.cfg_getter()["smart"]
        return [
            ("strompreis/aktuell_ct", s["preis_ct"]), ("strompreis/boerse_ct", s["preis_boerse_ct"]),
            ("strompreis/heute_min_ct", s["heute_min_ct"]), ("strompreis/heute_max_ct", s["heute_max_ct"]),
            ("strompreis/heute_mittel_ct", s["heute_mittel_ct"]),
            ("prognose/pv_rest_heute_kwh", s["pv_rest_heute_kwh"]), ("prognose/pv_morgen_kwh", s["pv_morgen_kwh"]),
            ("smartladen/automatik", bool(p["aktiv"])), ("smartladen/probebetrieb", bool(p["probebetrieb"])),
            ("smartladen/laedt", bool(self.active)), ("smartladen/status", s["status"]),
            ("smartladen/schnellladen", bool(self.manual_until > time.time() and self.active)),
            ("smartladen/stoerung", self.fault or "keine"),
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
                # unerwarteter Fehler -> sicherer Zustand: eigene Ladung beenden
                if self.active:
                    self._set_fault(f"interner Fehler ({type(e).__name__})")
                    try:
                        self._stop_charge("interner Fehler")
                    except Exception:  # noqa: BLE001
                        pass
            self._wake.wait(5)

    def _fetch(self):
        p = self.cfg_getter()["smart"]
        now = time.time()
        lt = time.localtime(now)
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
        key = (p["lat"], p["lon"], p["neigung"], p["ausrichtung"])
        if p["ort_name"] and (now >= self._next_pv or key != self.pv_key):
            try:
                slots = fetch_pv_forecast(p["lat"], p["lon"], p["neigung"], p["ausrichtung"])
                with self.lock:
                    self.pv, self.pv_err, self.pv_at, self.pv_key = slots, "", now, key
                self._wake.set()
                kwp_w = p["kwp"] * 1000 * p["wirkungsgrad_pct"] / 100
                for s, e, g in slots:
                    if s >= now - 60 and s < now + 86400:
                        self.stats.set_forecast(s, g / 1000 * kwp_w)
                self._next_pv = now + 3600
            except FetchError as e:
                if self.pv_err != str(e):
                    self.log(f"PV-Prognose: {e}")
                self.pv_err = str(e)
                with self.lock:
                    if key != self.pv_key:        # Standort geändert -> alte Prognose verwerfen
                        self.pv, self.pv_at = [], 0
                self.pv_key = key
                self._next_pv = now + 600
        elif not p["ort_name"]:
            self.pv_err = "Kein Standort eingestellt – PV aus eigener Statistik"
            with self.lock:
                self.pv, self.pv_at = [], 0

    # ------------------------------------------------------------------
    def _step(self):
        cfg = self.cfg_getter()
        p = cfg["smart"]
        now = time.time()
        vals, static, st = self.poller.snapshot()
        if st["verbunden"] and vals.get("_akku"):
            self.plan = self.compute()
        with self.lock:
            prices, pv = list(self.prices), list(self.pv)
        own = self.active
        self.checks = safety_checks(cfg, vals, static, st, prices, self.price_at, pv, self.pv_at,
                                    self.stats.days_with_data(), CLOCK, now, self.fault, self.budget_ok(now), own)
        failed = [n for n, ok, _i in self.checks if not ok]

        # Hängengebliebene Ladung aus einem früheren Lauf / Wechselrichter hat beendet
        if self.active and vals.get("st_zwang") == 0 and now > self.last_cmd + 90:
            self.log("Smart-Laden: Zwangsladen ist beendet (vom Wechselrichter oder abgelaufen)")
            self.active = False
            self._save_state()
        if self.active and now > self.cmd_end + 120 and vals.get("st_zwang") not in (None, 0):
            # sollte vom Gerät längst beendet sein -> Störung
            self._set_fault("Zwangsladen läuft länger als beauftragt")

        # Schnellaktion hat Vorrang – Automatik pausiert solange
        if self._quick_step(vals, static, st, now):
            return

        pl = self.plan
        price_eur = self.price_now()
        price_ct = end_price(price_eur, p) if price_eur is not None else None
        in_range = price_ct is not None and price_ct <= float(p["preis_max_ct"])
        soc = vals.get("akku_soc") or 0
        want = (not failed and pl is not None and pl["jetzt_w"] > 0 and in_range and soc < float(p["ziel_soc"]))

        if failed:
            reason = next(f"{n}: {i}" if i else n for n, ok, i in self.checks if not ok)
            self.status = ("Automatik aus" if not p["aktiv"] else
                           ("STÖRUNG – " + self.fault if self.fault else "Gesperrt – " + reason))
            self.sim_note = ""
            if self.active or self.netzladen_vorher == 0:
                self._stop_charge("Prüfung nicht bestanden: " + reason)
            return

        if p["probebetrieb"]:
            if self.active or self.netzladen_vorher == 0:
                self._stop_charge("Probebetrieb eingeschaltet")
            if want:
                note = (f"Probebetrieb: würde jetzt mit {pl['jetzt_w']} W aus dem Netz laden "
                        f"(Preis {price_ct:.2f} ct/kWh, SOC {soc:.0f} %)")
                if note.split("(")[0] != self.sim_note.split("(")[0]:
                    self.log(note)
                self.sim_note = note
                self.status = note
            else:
                if self.sim_note:
                    self.log("Probebetrieb: würde jetzt NICHT laden")
                self.sim_note = ""
                self.status = "Probebetrieb – " + self._idle_text(pl, soc, p)
            return

        if want:
            end = min(pl["block_ende"], now + MAX_CMD_MIN * 60)
            minutes = max(1, int(math.ceil((end - now) / 60)))
            power = int(min(pl["jetzt_w"], float(p["ladeleistung_w"]), vals.get("akku_max_laden") or 1e9))
            need = (not self.active or abs(power - self.cmd_power) >= 300
                    or self.cmd_end - now < 300 or self.cmd_end > pl["block_ende"] + 180)
            if need and now - self.last_cmd > 60:
                self._start_charge(power, minutes, vals, price_ct)
            if self.active:
                self.status = (f"Lädt aus dem Netz mit {self.cmd_power} W bis "
                               f"{time.strftime('%H:%M', time.localtime(min(pl['block_ende'], self.cmd_end)))}")
        else:
            if self.active or self.netzladen_vorher == 0:
                self._stop_charge("Ladefenster vorbei" if self.active else "Einstellung wiederherstellen")
            self.status = self._idle_text(pl, soc, p)

    @staticmethod
    def _idle_text(pl, soc, p):
        if pl is None:
            return "Kein Plan (Akku nicht verbunden)"
        if pl["naechste_ladung"]:
            return "Wartet – nächste Netzladung " + fmt_tag_zeit(pl["naechste_ladung"])
        if pl["pv_gesperrt"]:
            return "Wartet – günstige Zeiten vorhanden, aber PV-Überschuss erwartet"
        if soc >= float(p["ziel_soc"]):
            return "Ziel-SOC erreicht"
        return "Wartet – kein Zeitfenster unter der Preisgrenze"

    # ------------------------------------------------------------------ Schnellaktion
    def quick_state(self):
        """Zustand für den Knopf „30 min aus dem Netz laden“ (moeglich + Grund)."""
        cfg = self.cfg_getter()
        vals, static, st = self.poller.snapshot()
        now = time.time()
        running = self.manual_until > now and self.active
        power = int(min(float(cfg["smart"]["ladeleistung_w"]), vals.get("akku_max_laden") or 1e9))
        soc = vals.get("akku_soc")
        reason = None
        if running:
            reason = "läuft bereits"
        else:
            reason = write_guard(cfg, static, st, now)
            if not reason and not vals.get("_akku"):
                reason = "Kein Akku erkannt"
            if not reason and (soc is None or not 0 <= soc <= 100):
                reason = "Ladezustand unbekannt"
            if not reason and soc >= SCHNELL_MAX_SOC:
                reason = f"Akku bereits bei {soc:.0f} % (ab {SCHNELL_MAX_SOC} % nicht möglich)"
            if not reason and self.fault:
                reason = "Störung – bitte erst quittieren"
            if not reason and self.active:
                reason = "Automatik lädt gerade aus dem Netz"
            if not reason and vals.get("st_zwang"):
                reason = "Zwangsladen/-entladen läuft bereits"
            if not reason and not self.budget_ok(now):
                reason = "Schreib-Budget erschöpft"
        return {"moeglich": reason is None, "grund": reason or "", "laeuft": running,
                "bis": self.manual_until if running else 0, "leistung_w": power,
                "minuten": SCHNELL_MIN, "max_soc": SCHNELL_MAX_SOC}

    def quick_start(self, who=""):
        with self._io:
            q = self.quick_state()
            if not q["moeglich"]:
                raise ControlError(q["grund"])
            vals, _static, _st = self.poller.snapshot()
            self.log(f"Schnellaktion von {who}: {SCHNELL_MIN} min aus dem Netz laden mit {q['leistung_w']} W")
            self._start_charge_locked(q["leistung_w"], SCHNELL_MIN, vals, self.price_ct_at(time.time()))
            if not self.active:
                raise ControlError(self.status or "Start fehlgeschlagen")
            self.manual_until = time.time() + SCHNELL_MIN * 60
            self._save_state()
            self._wake.set()

    def quick_stop(self, who=""):
        with self._io:
            self.log(f"Schnellaktion beendet von {who}")
            self.manual_until = 0
            self._stop_charge_locked("Schnellaktion beendet")
            self._save_state()
            self._wake.set()

    def _quick_step(self, vals, static, st, now):
        """Während der Schnellaktion: nur überwachen, Automatik pausiert. True = Schnellaktion aktiv."""
        if not self.manual_until:
            return False
        cfg = self.cfg_getter()
        soc = vals.get("akku_soc") or 0
        end_reason = None
        if now >= self.manual_until:
            end_reason = "30 min abgelaufen"
        elif soc >= SCHNELL_MAX_SOC:
            end_reason = f"{SCHNELL_MAX_SOC} % erreicht"
        elif write_guard(cfg, static, st, now):
            end_reason = "Prüfung nicht bestanden: " + write_guard(cfg, static, st, now)
        elif self.fault:
            end_reason = "Störung"
        elif not self.active:
            end_reason = "vom Wechselrichter beendet"
        if end_reason:
            self.log(f"Schnellaktion: Ende ({end_reason})")
            self.manual_until = 0
            with self._io:
                self._stop_charge_locked("Schnellaktion: " + end_reason)
            self._save_state()
            return False
        self.status = (f"Schnellaktion: lädt aus dem Netz mit {self.cmd_power} W bis "
                       f"{time.strftime('%H:%M', time.localtime(self.manual_until))} (höchstens bis {SCHNELL_MAX_SOC} %)")
        return True

    # ------------------------------------------------------------------ Schreiben
    def _write(self, writes):
        cfg = self.cfg_getter()
        self.cmds.append(time.time())
        if not self.budget_ok():
            self._set_fault("Schreib-Budget überschritten (mögliche Fehlfunktion)")
        return self.poller.execute(make_executor(writes, cfg["steuerung"]["geraet_sn"], strict=True), timeout=120)

    def _start_charge(self, power, minutes, vals, price_ct):
        with self._io:
            self._start_charge_locked(power, minutes, vals, price_ct)

    def _start_charge_locked(self, power, minutes, vals, price_ct):
        self.last_cmd = time.time()
        if not self.budget_ok():
            self._set_fault("Schreib-Budget überschritten (mögliche Fehlfunktion)")
            return
        try:
            if vals.get("st_netzladen") == 0:
                self.netzladen_vorher = 0
                self._save_state()
                self._write([("st_netzladen", 1)])
                self.log("Smart-Laden: „Laden aus dem Netz“ vorübergehend eingeschaltet (wird danach zurückgesetzt)")
            minutes = max(1, min(MAX_CMD_MIN, int(minutes)))
            self._write([("st_zwang_modus", 0), ("st_zwang_ladeleistung", int(power)),
                         ("st_zwang_dauer", minutes), ("st_zwang", 1)])
            if not self.active:
                preis = f"{price_ct:.2f} ct/kWh" if price_ct is not None else "unbekannt"
                self.log(f"Netzladung gestartet ({power} W, {minutes} min, Preis {preis})")
            self.active = True
            self.cmd_end = time.time() + minutes * 60
            self.cmd_power = int(power)
            self._save_state()
        except (ControlError, ModbusError, OSError) as e:
            self.status = f"Fehler beim Starten: {e}"
            self.log(f"Smart-Laden: Start fehlgeschlagen: {e}")
            if isinstance(e, ControlError):
                self._set_fault(str(e))
            self._stop_charge("Start fehlgeschlagen")

    def _stop_charge(self, reason):
        with self._io:
            self._stop_charge_locked(reason)

    def _stop_charge_locked(self, reason):
        self.last_cmd = time.time()
        sn = self.cfg_getter()["steuerung"]["geraet_sn"]
        if not sn:
            self.active = False
            return
        try:
            if self.active:
                self.poller.execute(make_executor([("st_zwang", 0)], sn, strict=False), timeout=120)
                self.log(f"Smart-Laden: Netzladung beendet ({reason})")
            self.active = False
            if self.netzladen_vorher == 0:
                self.poller.execute(make_executor([("st_netzladen", 0)], sn, strict=True), timeout=120)
                self.log(f"Smart-Laden: „Laden aus dem Netz“ wieder ausgeschaltet ({reason})")
                self.netzladen_vorher = None
            self._save_state()
        except (ControlError, ModbusError, OSError) as e:
            if str(e) != getattr(self, "_last_stop_err", None):
                self.log(f"Smart-Laden: Stopp fehlgeschlagen ({e}) – wird wiederholt; der Wechselrichter "
                         f"beendet das Zwangsladen spätestens nach Ablauf der Dauer (max. {MAX_CMD_MIN} min) selbst")
            self._last_stop_err = str(e)
            if time.time() > self.cmd_end + 60:
                self.active = False
            self._save_state()
