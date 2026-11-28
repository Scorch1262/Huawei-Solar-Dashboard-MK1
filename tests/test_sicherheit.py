"""Sicherheitstests ohne Hardware (python -m unittest discover -s tests).

Geprüft werden feste Regeln, die NIE verletzt werden dürfen – u. a. mit
tausenden Zufallsszenarien für den Ladeplaner.
"""

import math
import os
import random
import socket
import sys
import time
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from solar import control, registers                      # noqa: E402
from solar.control import ControlError, make_executor, plan, write_guard, WRITABLE  # noqa: E402
from solar.internet import FetchError, check_price_slots, check_pv_slots  # noqa: E402
from solar.modbus import ModbusException                  # noqa: E402
from solar.registers import BY_KEY, decode, encode        # noqa: E402
from solar.smart import STEP, build_plan, safety_checks, end_price  # noqa: E402

SMART_DEFAULT = dict(aktiv=True, preis_max_ct=10, ziel_soc=80, ladeleistung_w=3000,
                     pv_vertrauen_pct=80, horizont_h=24, aufschlag_ct=0, mwst_pct=0, zone="DE-LU",
                     ort_name="X", lat=50.0, lon=8.0, kwp=10, neigung=30, ausrichtung=0, wirkungsgrad_pct=85,
                     grundlast_w=500, prognose="wetter", kalibrierung=True, probebetrieb=False)


def cfg(**over):
    c = {"steuerung": {"aktiv": True, "pin": "1234", "geraet_sn": "SN1", "geraet_modell": "SUN2000-10K-MAP0",
                       "einspeisung_erlaubt": False},
         "wechselrichter": {"intervall_s": 10, "timeout_s": 15},
         "smart": dict(SMART_DEFAULT)}
    for k, v in over.items():
        sec, key = k.split("__")
        c[sec][key] = v
    return c


STATIC = {"seriennummer": "SN1", "modell": "SUN2000-10K-MAP0"}


def state(age=1):
    return {"verbunden": True, "letzte_abfrage": time.time() - age}


# --------------------------------------------------------------------------
class PlanerInvarianten(unittest.TestCase):
    """Zufallsszenarien: der Planer darf bestimmte Dinge NIE tun."""

    def scenario(self, rnd):
        now = time.time()
        t0 = int(now // 3600 * 3600) - 3600
        prices = []
        for i in range(60 * 4):
            s = t0 + i * 900
            if rnd.random() < 0.03:
                continue                                    # Lücken in den Preisdaten
            prices.append((s, s + 900, rnd.uniform(-100, 600)))
        pv = []
        peak = rnd.choice([0, 50, 200, 500, 900, 1100])
        for i in range(72):
            s = t0 + i * 3600
            h = time.localtime(s + 1800).tm_hour
            g = max(0.0, math.sin((h - 6) / 13 * math.pi)) * peak * rnd.uniform(0.3, 1.0) if 6 <= h <= 19 else 0
            pv.append((s, s + 3600, g))
        p = dict(SMART_DEFAULT)
        p.update(preis_max_ct=round(rnd.uniform(0, 60), 1),
                 ziel_soc=rnd.choice([20, 50, 80, 100]), ladeleistung_w=rnd.choice([300, 1500, 3000, 8000]),
                 pv_vertrauen_pct=rnd.choice([0, 50, 80, 100, 150]), horizont_h=rnd.choice([4, 12, 24, 40]),
                 aufschlag_ct=rnd.choice([0, 15]), mwst_pct=rnd.choice([0, 19]),
                 prognose=rnd.choice(["wetter", "statistik"]), kwp=rnd.uniform(3, 20))
        batt = dict(soc_pct=rnd.uniform(0, 100), cap_wh=rnd.choice([5000, 10000, 15000, 30000]),
                    max_pct=rnd.choice([90, 100]), min_pct=rnd.choice([0, 5, 15]),
                    p_charge=rnd.choice([2500, 5000, 10000]), p_discharge=rnd.choice([2500, 5000]))
        load = {h: rnd.uniform(150, 2500) for h in range(24)} if rnd.random() < 0.7 else {}
        pvprof = {h: rnd.uniform(0, 4000) for h in range(7, 18)} if rnd.random() < 0.5 else {}
        return now, p, prices, pv, batt, load, pvprof

    def test_zufall(self):
        rnd = random.Random(4711)
        for n in range(2000):
            now, p, prices, pv, batt, load, pvprof = self.scenario(rnd)
            r = build_plan(p, now, prices, pv, batt, load, pvprof, rnd.choice([None, 0.7, 1.2]))
            cap = batt["cap_wh"]
            ziel = min(batt["max_pct"], p["ziel_soc"])
            for st in r["schritte"]:
                if st["netz_wh"] > 0:
                    msg = f"Szenario {n}, {time.strftime('%H:%M', time.localtime(st['t']))}"
                    # 1. nur mit bekanntem Preis innerhalb des Bereichs
                    self.assertIsNotNone(st["preis_ct"], msg)
                    self.assertLessEqual(st["preis_ct"], p["preis_max_ct"], msg)
                    # 2. nie in der Vergangenheit
                    self.assertGreater(st["t"] + STEP, now, msg)
                    # 3. nie über den Ziel-SOC
                    self.assertLessEqual(st["soc_pct"] + 100 * st["netz_wh"] / cap, ziel + 0.6, msg)
                    # 4. nie mehr als die eingestellte Ladeleistung
                    self.assertLessEqual(st["netz_wh"], min(p["ladeleistung_w"], batt["p_charge"]) * STEP / 3600 + 0.5, msg)
            # 5. Netzladung darf NIE zusätzlich PV-Energie verdrängen
            self.assertLessEqual(r["verlust_mit_wh"], r["verlust_ohne_wh"] + 5 * max(1, sum(
                1 for s in r["schritte"] if s["netz_wh"] > 0)), f"Szenario {n}")
            # 6. Leistung jetzt im erlaubten Rahmen
            self.assertLessEqual(r["jetzt_w"], p["ladeleistung_w"])
            if r["jetzt_w"]:
                self.assertGreater(r["schritte"][0]["netz_wh"], 0)

    def test_negative_preise_zaehlen(self):
        """Negative Börsenpreise sind die günstigsten Zeiten und müssen genutzt werden können."""
        now = time.time()
        t0 = int(now // 900 * 900)
        prices = [(t0 + i * 900, t0 + (i + 1) * 900, -50.0 if i < 8 else 300.0) for i in range(96)]
        batt = dict(soc_pct=20, cap_wh=10000, max_pct=100, min_pct=5, p_charge=5000, p_discharge=5000)
        r = build_plan(dict(SMART_DEFAULT, preis_max_ct=0, prognose="statistik"), now, prices, [], batt, {}, {}, None)
        self.assertGreater(r["geplant_kwh"], 0)
        self.assertTrue(all(s["preis_ct"] < 0 for s in r["schritte"] if s["netz_wh"] > 0))

    def test_ohne_preise_keine_ladung(self):
        now = time.time()
        r = build_plan(dict(SMART_DEFAULT), now, [], [], dict(soc_pct=10, cap_wh=10000, max_pct=100, min_pct=5,
                                                             p_charge=5000, p_discharge=5000), {}, {}, None)
        self.assertEqual(r["geplant_kwh"], 0)
        self.assertEqual(r["jetzt_w"], 0)

    def test_sonne_nach_billigstrom(self):
        """Das Beispiel aus der Anforderung: 7 Uhr billig, ab 8 Uhr viel Sonne -> nicht laden."""
        lt = time.localtime()
        day = time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday, 0, 0, 0, 0, 0, -1)) + 86400
        now = day + 5 * 3600
        prices = [(day + i * 900, day + i * 900 + 900, 40.0 if 6 <= (i // 4) < 8 else 300.0) for i in range(96)]
        pv = [(day + h * 3600, day + h * 3600 + 3600,
               max(0, math.sin((h - 7) / 10 * math.pi)) * 900 if 8 <= h <= 17 else 0) for h in range(24)]
        batt = dict(soc_pct=20, cap_wh=10000, max_pct=100, min_pct=5, p_charge=5000, p_discharge=5000)
        r = build_plan(dict(SMART_DEFAULT, ziel_soc=100), now, prices, pv, batt, {}, {}, None)
        self.assertEqual(r["geplant_kwh"], 0, "bei viel Sonne darf morgens nicht aus dem Netz geladen werden")
        r2 = build_plan(dict(SMART_DEFAULT, ziel_soc=100), now, prices, [(s, e, g * 0.1) for s, e, g in pv],
                        batt, {}, {}, None)
        self.assertGreater(r2["geplant_kwh"], 0, "an einem trüben Tag soll geladen werden")


# --------------------------------------------------------------------------
class Pruefungen(unittest.TestCase):
    def base(self, **kw):
        now = time.time()
        args = dict(cfg=cfg(), vals={"_akku": True, "akku_soc": 50, "akku_kapazitaet": 10000, "st_zwang": 0},
                    static=STATIC, st=state(), prices=[(now - 100, now + 800, 50.0)], price_at=now - 60,
                    pv_slots=[(now + i * 3600, now + (i + 1) * 3600, 100.0) for i in range(24)], pv_at=now - 60,
                    stat_days=0, clock={"abweichung_s": 1.0, "zeit": now}, now=now, fault="", budget_ok=True,
                    own_charge=False)
        args.update(kw)
        return {n: ok for n, ok, _i in safety_checks(**args)}

    def test_alles_ok(self):
        self.assertTrue(all(self.base().values()))

    def test_jede_bedingung_sperrt(self):
        now = time.time()
        faelle = {
            "aus": dict(cfg=cfg(smart__aktiv=False)),
            "störung": dict(fault="x"),
            "keine PIN": dict(cfg=cfg(steuerung__pin="")),
            "nicht bestätigt": dict(cfg=cfg(steuerung__geraet_sn="")),
            "falsches Gerät": dict(static={"seriennummer": "ANDERS", "modell": "SUN2000-10K-MAP0"}),
            "falsches Modell": dict(static={"seriennummer": "SN1", "modell": "SUN2000-10KTL-M0"}),
            "nicht verbunden": dict(st={"verbunden": False, "letzte_abfrage": now}),
            "Werte alt": dict(st=state(age=600)),
            "kein Akku": dict(vals={"_akku": False, "akku_soc": 50, "akku_kapazitaet": 10000}),
            "SOC unplausibel": dict(vals={"_akku": True, "akku_soc": 140, "akku_kapazitaet": 10000}),
            "Kapazität unplausibel": dict(vals={"_akku": True, "akku_soc": 50, "akku_kapazitaet": 0}),
            "kein Preis": dict(prices=[]),
            "Preis alt": dict(price_at=now - 5 * 3600),
            "Prognose fehlt": dict(pv_slots=[]),
            "Prognose alt": dict(pv_at=now - 7 * 3600),
            "Statistik zu kurz": dict(cfg=cfg(smart__prognose="statistik")),
            "Uhr falsch": dict(clock={"abweichung_s": 900.0, "zeit": now}),
            "Uhr ungeprüft": dict(clock={"abweichung_s": None, "zeit": 0}),
            "manuelles Zwangsladen": dict(vals={"_akku": True, "akku_soc": 50, "akku_kapazitaet": 10000, "st_zwang": 1}),
            "Budget": dict(budget_ok=False),
        }
        for name, kw in faelle.items():
            res = self.base(**kw)
            self.assertFalse(all(res.values()), f"Fall „{name}“ muss sperren")

    def test_probebetrieb_braucht_keine_schreibfreigabe(self):
        res = self.base(cfg=cfg(smart__probebetrieb=True, steuerung__aktiv=False))
        self.assertTrue(all(res.values()))


# --------------------------------------------------------------------------
class Steuerbefehle(unittest.TestCase):
    VALS = {"akku_soc": 50, "akku_max_laden": 5000, "akku_max_entladen": 5000}

    def test_grenzen(self):
        bad = [("modus", {"wert": 3}), ("modus", {"wert": 6}), ("modus", {"wert": 99}),
               ("ladeschluss", {"wert": 89}), ("ladeschluss", {"wert": 101}),
               ("entladeschluss", {"wert": 21}), ("entladeschluss", {"wert": -1}),
               ("entladeschluss", {"wert": 0}), ("entladeschluss", {"wert": 4.9}),
               ("max_laden", {"wert": 5001}), ("max_laden", {"wert": -1}),
               ("netzladen_soc", {"wert": 19}), ("netzladen_leistung", {"wert": 99999}),
               ("zwang_start", {"art": "laden", "leistung": 9000, "vorgabe": "dauer", "dauer": 10}),
               ("zwang_start", {"art": "laden", "leistung": 2000, "vorgabe": "dauer", "dauer": 0}),
               ("zwang_start", {"art": "laden", "leistung": 2000, "vorgabe": "soc", "ziel_soc": 40}),
               ("zwang_start", {"art": "entladen", "leistung": 2000, "vorgabe": "soc", "ziel_soc": 60}),
               ("zwang_start", {"art": "boom", "leistung": 2000, "vorgabe": "dauer", "dauer": 5}),
               ("einspeisung", {"modus": 1}), ("einspeisung", {"modus": 7, "max_pct": 120}),
               ("gibtsnicht", {}), ("modus", {"wert": "abc"}), ("modus", {"wert": None})]
        for action, params in bad:
            with self.assertRaises(ControlError, msg=f"{action} {params} muss abgelehnt werden"):
                plan(action, params, self.VALS)

    def test_entladeschluss_untergrenze(self):
        _t, w = plan("entladeschluss", {"wert": 5}, self.VALS)
        self.assertEqual(w, [("st_entladeschluss", 5)])

    def test_whitelist(self):
        for key in ("akku_soc", "seriennummer", "wr_leistung", "netz_leistung"):
            with self.assertRaises(ControlError):
                make_executor([(key, 1)], "SN1")
        self.assertTrue(all(BY_KEY[k].group == "steuerung" for k in WRITABLE))

    def test_kodierung(self):
        for k in WRITABLE:
            r = BY_KEY[k]
            for v in (0, 1, 50, 100):
                self.assertAlmostEqual(decode(r, encode(r, v)), v, places=3)
        with self.assertRaises(ValueError):
            encode(BY_KEY["st_ladeschluss"], 7000)       # U16 * 10 -> Überlauf

    def test_guard(self):
        self.assertIsNone(write_guard(cfg(), STATIC, state()))
        self.assertIsNotNone(write_guard(cfg(steuerung__aktiv=False), STATIC, state()))
        self.assertIsNotNone(write_guard(cfg(steuerung__pin="12"), STATIC, state()))
        self.assertIsNotNone(write_guard(cfg(), {"seriennummer": "SN2", "modell": "SUN2000-10K-MAP0"}, state()))
        self.assertIsNotNone(write_guard(cfg(), STATIC, state(age=1000)))


class FakeClient:
    def __init__(self, sn="SN1", ignore=()):
        self.mem = {}
        self.writes = []
        self.sn = sn
        self.ignore = ignore
        sn_words = encode_str(sn, 10)
        for i, w in enumerate(sn_words):
            self.mem[30015 + i] = w

    def write(self, addr, words):
        self.writes.append((addr, list(words)))
        if addr in self.ignore:
            return
        for i, w in enumerate(words):
            self.mem[addr + i] = w

    def read_holding(self, addr, count, retries=1):
        return [self.mem.get(addr + i, 0) for i in range(count)]


def encode_str(s, n):
    b = s.encode().ljust(n * 2, b"\0")
    return [int.from_bytes(b[i:i + 2], "big") for i in range(0, n * 2, 2)]


class Ausfuehrung(unittest.TestCase):
    def test_falsches_geraet_schreibt_nichts(self):
        c = FakeClient(sn="FREMD")
        with self.assertRaises(ControlError):
            make_executor([("st_netzladen", 1)], "SN1")(c)
        self.assertEqual(c.writes, [], "bei falscher Seriennummer darf nichts geschrieben werden")

    def test_ruecklesen_streng(self):
        c = FakeClient(ignore=(47247,))
        with self.assertRaises(ControlError):
            make_executor([("st_zwang_ladeleistung", 3000)], "SN1", strict=True)(c)

    def test_normalfall(self):
        c = FakeClient()
        res = make_executor([("st_zwang_modus", 0), ("st_zwang_ladeleistung", 2500), ("st_zwang_dauer", 30),
                             ("st_zwang", 1)], "SN1")(c)
        self.assertTrue(all(r["ok"] for r in res))
        self.assertEqual([a for a, _w in c.writes], [47246, 47247, 47083, 47100])


class Verbindung(unittest.TestCase):
    def test_kein_automatisches_neuverbinden(self):
        """Nach einem Verbindungsabbruch darf der Client NICHT selbst neu verbinden – sonst
        könnten nach einem Gerätewechsel alte Gerätedaten (Seriennummer) weiterverwendet werden."""
        from solar.modbus import ModbusTcpClient, ModbusError
        srv = socket.socket()
        srv.bind(("127.0.0.1", 0))
        srv.listen(5)
        port = srv.getsockname()[1]
        try:
            c = ModbusTcpClient("127.0.0.1", port, 1, timeout=2, connect_delay=0)
            with self.assertRaises(ModbusError):
                c.read_holding(30000, 1)                 # nie verbunden -> Fehler statt Verbindungsaufbau
            self.assertEqual(c.connects, 0)
            srv.settimeout(0.3)
            with self.assertRaises(socket.timeout):
                srv.accept()                             # es kam auch kein Verbindungsversuch an
            c.close()
        finally:
            srv.close()


class Internetdaten(unittest.TestCase):
    def test_preise(self):
        t = 1_800_000_000
        check_price_slots([(t, t + 900, 50.0), (t + 900, t + 1800, -20.0)])
        for bad in ([], [(t, t + 900, 9999.0)], [(t, t, 1.0)], [(t, t + 900, 1.0), (t + 100, t + 1000, 1.0)],
                    [(t, t + 86400, 1.0)]):
            with self.assertRaises(FetchError):
                check_price_slots(bad)

    def test_strahlung(self):
        with self.assertRaises(FetchError):
            check_pv_slots([(0, 3600, 5000.0)])

    def test_endpreis(self):
        p = dict(aufschlag_ct=10, mwst_pct=19)
        self.assertAlmostEqual(end_price(100.0, p), (10 + 10) * 1.19)


if __name__ == "__main__":
    unittest.main()
