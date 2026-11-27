"""Integrationstests: echtes Programm + Wechselrichter-Simulator + Nachbau der Internetdienste.

Geprüft wird, was tatsächlich in den (simulierten) Wechselrichter geschrieben wird – und vor allem,
dass in allen Sperrfällen NICHTS geschrieben wird. Laufzeit ca. 2–3 Minuten.
"""

import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.error
import urllib.request

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PY = sys.executable
SN = "HV2399999999"
PIN = "4711"


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


class Integration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="hsd-test-")
        cls.web, cls.mb, cls.dienst = free_port(), free_port(), free_port()
        cls.procs = []
        cls.mock = cls.start([PY, os.path.join(ROOT, "tools", "dienste_nachbau.py"), str(cls.dienst), "--kein-pv"], "dienste")
        cls.sim = cls.start_sim()
        app_dir = os.path.join(cls.tmp, "app")
        shutil.copytree(ROOT, app_dir, ignore=shutil.ignore_patterns("tests", ".git", "daten", "config.json", "__pycache__"))
        with open(os.path.join(app_dir, "config.json"), "w", encoding="utf-8") as f:
            json.dump({"web": {"port": cls.web},
                       "wechselrichter": {"host": "127.0.0.1", "port": cls.mb, "intervall_s": 3, "verbindungs_pause_s": 0.2},
                       "smart": {"ort_name": "Test", "lat": 51.5, "lon": 7.5, "preis_max_ct": 10, "ziel_soc": 95},
                       "config_version": 2}, f)
        env = dict(os.environ)
        u = f"http://127.0.0.1:{cls.dienst}"
        env.update(HSD_URL_ENERGYCHARTS=u + "/price", HSD_URL_AWATTAR_DE=u + "/awattar",
                   HSD_URL_OPENMETEO=u + "/forecast", HSD_URL_GEOCODING=u + "/search", PYTHONUNBUFFERED="1",
                   PYTHONIOENCODING="utf-8")
        cls.app_log = open(os.path.join(cls.tmp, "app.log"), "w", encoding="utf-8")
        cls.app = subprocess.Popen([PY, os.path.join(app_dir, "app.py")], cwd=app_dir, env=env,
                                   stdout=cls.app_log, stderr=subprocess.STDOUT)
        cls.procs.append(cls.app)
        cls.wait(lambda: cls.get("/api/data")["wechselrichter"]["verbunden"], 30, "Verbindung")

    @classmethod
    def tearDownClass(cls):
        for p in cls.procs:
            p.terminate()
            try:
                p.wait(10)
            except subprocess.TimeoutExpired:
                p.kill()
        cls.app_log.close()
        if not os.environ.get("HSD_TEST_BEHALTEN"):
            shutil.rmtree(cls.tmp, ignore_errors=True)

    # ------------------------------------------------------------------ Helfer
    @classmethod
    def start(cls, args, name):
        log = open(os.path.join(cls.tmp, name + ".log"), "w", encoding="utf-8")
        p = subprocess.Popen(args, stdout=log, stderr=subprocess.STDOUT,
                             env=dict(os.environ, PYTHONUNBUFFERED="1", PYTHONIOENCODING="utf-8"))
        p.logfile = log.name
        cls.procs.append(p)
        time.sleep(0.8)
        return p

    @classmethod
    def start_sim(cls, *extra, sn=SN):
        return cls.start([PY, os.path.join(ROOT, "tools", "huawei_simulator.py"), "--port", str(cls.mb),
                          "--sn", sn, *extra], f"sim-{sn}-{len(cls.procs)}")

    @classmethod
    def restart_sim(cls, *extra, sn=SN):
        cls.sim.terminate()
        cls.sim.wait(10)
        time.sleep(1)
        cls.sim = cls.start_sim(*extra, sn=sn)

    @classmethod
    def get(cls, path):
        with urllib.request.urlopen(f"http://127.0.0.1:{cls.web}{path}", timeout=30) as r:
            return json.load(r)

    @classmethod
    def post(cls, path, obj, ctype="application/json", origin=None):
        h = {"Content-Type": ctype}
        if origin:
            h["Origin"] = origin
        req = urllib.request.Request(f"http://127.0.0.1:{cls.web}{path}", data=json.dumps(obj).encode(), headers=h)
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.status, json.load(r)
        except urllib.error.HTTPError as e:
            return e.code, json.load(e)

    @classmethod
    def wait(cls, cond, timeout, what):
        t0 = time.time()
        while time.time() - t0 < timeout:
            try:
                if cond():
                    return
            except Exception:  # noqa: BLE001
                pass
            time.sleep(0.5)
        try:
            z = cls.get("/api/smart")["zustand"]
            info = z["status"] + " | " + "; ".join(c["name"] + ": " + c["info"] for c in z["pruefungen"] if not c["ok"])
        except Exception as e:  # noqa: BLE001
            info = str(e)
        try:
            cls.app_log.flush()
            with open(cls.app_log.name, encoding="utf-8") as f:
                tail = "".join(f.readlines()[-15:])
        except OSError:
            tail = ""
        raise AssertionError(f"Zeitüberschreitung: {what} – Zustand: {info}\n--- Protokoll ---\n{tail}")

    def writes(self, proc=None):
        with open((proc or self.sim).logfile, encoding="utf-8") as f:
            return [line.strip() for line in f if "geschrieben" in line]

    def connected_sn(self):
        d = self.get("/api/data")
        return d["geraet"].get("seriennummer") if d["wechselrichter"]["verbunden"] else None

    def smart(self):
        return self.get("/api/smart")["zustand"]

    # ------------------------------------------------------------------ Tests (Reihenfolge wichtig)
    def test_1_fremde_herkunft_wird_abgewiesen(self):
        code, _ = self.post("/api/steuern", {"aktion": "netzladen", "werte": {"wert": True}}, ctype="text/plain")
        self.assertEqual(code, 403)
        code, _ = self.post("/api/config", {"steuerung": {"aktiv": True}}, origin="http://boese.example")
        self.assertEqual(code, 403)

    def test_2_freigabe_nur_mit_pin_und_bestaetigung(self):
        _, r = self.post("/api/steuern", {"aktion": "netzladen", "werte": {"wert": True}})
        self.assertFalse(r["ok"], "ohne Freigabe darf nicht gesteuert werden")
        _, r = self.post("/api/config", {"steuerung": {"aktiv": True}})
        self.assertFalse(r["ok"], "Freigabe ohne PIN muss scheitern")
        _, r = self.post("/api/config", {"steuerung": {"aktiv": True, "pin": PIN}})
        self.assertFalse(r["ok"], "Freigabe ohne Bestätigung der Anlage muss scheitern")
        _, r = self.post("/api/config", {"steuerung": {"aktiv": True, "pin": PIN, "geraet_bestaetigen": True}})
        self.assertTrue(r["ok"], r)
        cfg = self.get("/api/config")["config"]["steuerung"]
        self.assertEqual(cfg["geraet_sn"], SN)
        self.assertEqual(self.writes(), [], "Freigeben allein darf nichts schreiben")
        # PIN ändern ohne aktuelle PIN -> abgelehnt
        _, r = self.post("/api/config", {"steuerung": {"pin": "9999"}})
        self.assertFalse(r["ok"])

    def test_3_probebetrieb_schreibt_nie(self):
        _, r = self.post("/api/smart", {"smart": {"aktiv": True, "probebetrieb": True}})
        self.assertTrue(r["ok"], r)
        self.wait(lambda: self.smart()["status"].startswith("Probebetrieb: würde jetzt"), 40, "Probebetrieb-Entscheidung")
        time.sleep(8)
        self.assertEqual(self.writes(), [], "im Probebetrieb darf NICHTS geschrieben werden")

    def test_4_scharf_nur_mit_pin(self):
        _, r = self.post("/api/smart", {"smart": {"aktiv": True, "probebetrieb": False}, "pin": "0000"})
        self.assertFalse(r["ok"])
        self.assertEqual(self.writes(), [])
        _, r = self.post("/api/smart", {"smart": {"aktiv": True, "probebetrieb": False}, "pin": PIN})
        self.assertTrue(r["ok"], r)
        self.wait(lambda: any("47100 = [1]" in w for w in self.writes()), 120, "Start Zwangsladen")
        w = self.writes()
        dauer = [x for x in w if "47083 =" in x]
        self.assertTrue(dauer and all(int(x.rsplit("[", 1)[1].rstrip("]")) <= 30 for x in dauer), "max. 30 min je Auftrag")
        self.assertTrue(self.smart()["aktiv_laden"])

    def test_5_stopp_und_wiederherstellen(self):
        _, r = self.post("/api/smart", {"smart": {"preis_max_ct": 1}, "pin": PIN})
        self.assertTrue(r["ok"], r)
        self.wait(lambda: any("47100 = [0]" in w for w in self.writes()), 40, "Stopp")
        self.wait(lambda: any("47087 = [0]" in w for w in self.writes()), 40, "Netzladen zurückgesetzt")
        self.assertFalse(self.smart()["aktiv_laden"])
        # Ausschalten geht ohne PIN
        _, r = self.post("/api/smart", {"smart": {"aktiv": False, "preis_max_ct": 10}})
        self.assertTrue(r["ok"], r)

    def test_6_fremdes_geraet_wird_nie_beschrieben(self):
        self.restart_sim(sn="FREMD000001")
        self.wait(lambda: self.connected_sn() == "FREMD000001", 90, "neues Gerät")
        _, r = self.post("/api/steuern", {"aktion": "netzladen", "werte": {"wert": True}, "pin": PIN})
        self.assertFalse(r["ok"])
        self.assertIn("SN", r["fehler"])
        _, r = self.post("/api/smart", {"smart": {"aktiv": True, "probebetrieb": False}, "pin": PIN})
        self.assertTrue(r["ok"])
        time.sleep(12)
        self.assertEqual(self.writes(), [], "ein nicht bestätigtes Gerät darf nie beschrieben werden")
        self.assertFalse(self.smart()["aktiv_laden"])
        _, r = self.post("/api/smart", {"smart": {"aktiv": False}})

    def test_7_ruecklesefehler_fuehrt_zu_stoerung(self):
        self.restart_sim("--falsch-zurueck")
        self.wait(lambda: self.connected_sn() == SN, 90, "Originalgerät")
        _, r = self.post("/api/smart", {"smart": {"aktiv": True, "probebetrieb": False}, "pin": PIN})
        self.assertTrue(r["ok"], r)
        self.wait(lambda: self.smart()["stoerung"], 120, "Störung nach Rücklesefehler")
        self.wait(lambda: any("47100 = [0]" in w for w in self.writes()) or not any("47100 = [1]" in w for w in self.writes()),
                  20, "kein laufendes Zwangsladen")
        self.assertFalse(any("47100 = [1]" in w for w in self.writes()), "nach Rücklesefehler darf nicht gestartet werden")
        _, r = self.post("/api/smart/quittieren", {"pin": PIN})
        self.assertTrue(r["ok"])
        _, r = self.post("/api/smart", {"smart": {"aktiv": False}})
        self.assertEqual(self.smart()["stoerung"], "")


if __name__ == "__main__":
    unittest.main(verbosity=2)
