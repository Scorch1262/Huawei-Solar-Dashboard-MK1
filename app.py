#!/usr/bin/env python3
"""Huawei-Solar-Dashboard-MK1

Liest einen Huawei SUN2000-(5-12)K-MAP0 Hybrid-Wechselrichter mit LUNA2000-Akku
und Smart Meter per Modbus TCP aus, zeigt alle Werte auf einer Webseite im
lokalen Netzwerk und sendet jeden Wert als eigenes MQTT-Topic an einen Broker.

Nur Python-Standardbibliothek – läuft als exe (PyInstaller), unter Linux,
auf dem Raspberry Pi oder auf OpenWrt-Routern mit python3.
"""

import copy
import hmac
import json
import os
import queue
import socket
import sys
import threading
import time
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

from solar.control import ControlError, EINSPEISE_KEYS, make_executor, model_ok, plan, write_guard
from solar.inverter import History, InverterPoller, test_connection
from solar.modbus import ModbusError
from solar.mqtt import MqttPublisher, test_broker
from solar.registers import REGISTERS, DERIVED, STATIC_GROUPS, ARBEITSMODUS, EINSPEISE_MODUS
from solar.internet import ZONEN, FetchError, geocode
from solar.smart import SmartCharger, Stats
from solar.webui import PAGE

APP_NAME = "Huawei-Solar-Dashboard-MK1"
APP_VERSION = "1.3.2"


def base_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


BASE = base_dir()
DATA_DIR = os.path.join(BASE, "daten")
CONFIG_PATH = os.path.join(BASE, "config.json")
HISTORY_PATH = os.path.join(DATA_DIR, "verlauf.json")
LOGFILE_PATH = os.path.join(DATA_DIR, "protokoll.log")
STATS_PATH = os.path.join(DATA_DIR, "statistik.json")
SMART_STATE_PATH = os.path.join(DATA_DIR, "smart_zustand.json")
CONFIG_VERSION = 2

DEFAULT_CONFIG = {
    "web": {"port": 8095, "titel": "Solaranlage"},
    "wechselrichter": {"host": "", "port": 502, "unit_id": 1, "intervall_s": 10,
                       "timeout_s": 15, "verbindungs_pause_s": 1.5},
    "mqtt": {"aktiv": False, "host": "", "port": 1883, "benutzer": "", "passwort": "",
             "client_id": "huawei-solar-dashboard", "basis_topic": "huawei_solar",
             "retain": True, "nur_aenderungen": False, "erzwingen_s": 60, "json_topic": True},
    "steuerung": {"aktiv": False, "pin": "", "geraet_sn": "", "geraet_modell": "", "einspeisung_erlaubt": False},
    "smart": {"aktiv": False, "preis_max_ct": 10, "ziel_soc": 80,
              "ladeleistung_w": 3000, "pv_vertrauen_pct": 80, "horizont_h": 24,
              "aufschlag_ct": 0, "mwst_pct": 0, "zone": "DE-LU",
              "ort_name": "", "lat": 0.0, "lon": 0.0, "kwp": 10, "neigung": 30, "ausrichtung": 0,
              "wirkungsgrad_pct": 85, "grundlast_w": 500, "prognose": "wetter", "kalibrierung": True,
              "probebetrieb": True},
    "system": {"standby_verhindern": True},
    "config_version": CONFIG_VERSION,
}

# Prüfregeln für Einstellungen: (Typ, min, max)
RULES = {
    ("web", "port"): (int, 1, 65535), ("web", "titel"): (str, 0, 60),
    ("wechselrichter", "host"): (str, 0, 255), ("wechselrichter", "port"): (int, 1, 65535),
    ("wechselrichter", "unit_id"): (int, 0, 255), ("wechselrichter", "intervall_s"): (float, 2, 3600),
    ("wechselrichter", "timeout_s"): (float, 3, 60), ("wechselrichter", "verbindungs_pause_s"): (float, 0, 10),
    ("mqtt", "aktiv"): (bool, 0, 0), ("mqtt", "host"): (str, 0, 255), ("mqtt", "port"): (int, 1, 65535),
    ("mqtt", "benutzer"): (str, 0, 255), ("mqtt", "passwort"): (str, 0, 255),
    ("mqtt", "client_id"): (str, 1, 64), ("mqtt", "basis_topic"): (str, 1, 128),
    ("mqtt", "retain"): (bool, 0, 0), ("mqtt", "nur_aenderungen"): (bool, 0, 0),
    ("mqtt", "erzwingen_s"): (float, 0, 86400), ("mqtt", "json_topic"): (bool, 0, 0),
    ("steuerung", "aktiv"): (bool, 0, 0), ("steuerung", "pin"): (str, 0, 32),
    ("steuerung", "geraet_sn"): (str, 0, 40), ("steuerung", "geraet_modell"): (str, 0, 40),
    ("steuerung", "einspeisung_erlaubt"): (bool, 0, 0),
    ("system", "standby_verhindern"): (bool, 0, 0),
    ("smart", "aktiv"): (bool, 0, 0),
    ("smart", "preis_max_ct"): (float, 0, 60), ("smart", "ziel_soc"): (float, 10, 100),
    ("smart", "ladeleistung_w"): (float, 300, 30000), ("smart", "pv_vertrauen_pct"): (float, 0, 150),
    ("smart", "horizont_h"): (float, 4, 40), ("smart", "aufschlag_ct"): (float, 0, 60),
    ("smart", "mwst_pct"): (float, 0, 30), ("smart", "zone"): (str, 1, 10),
    ("smart", "ort_name"): (str, 0, 120), ("smart", "lat"): (float, -90, 90), ("smart", "lon"): (float, -180, 180),
    ("smart", "kwp"): (float, 0.3, 100), ("smart", "neigung"): (float, 0, 90),
    ("smart", "ausrichtung"): (float, -180, 180), ("smart", "wirkungsgrad_pct"): (float, 30, 110),
    ("smart", "grundlast_w"): (float, 0, 10000), ("smart", "prognose"): (str, 1, 20),
    ("smart", "kalibrierung"): (bool, 0, 0), ("smart", "probebetrieb"): (bool, 0, 0),
}
LABELS = {
    "web": "Webseite", "wechselrichter": "Wechselrichter", "mqtt": "MQTT",
    "steuerung": "Steuerung", "system": "System", "smart": "Smart-Laden",
}
SECTIONS = ("web", "wechselrichter", "mqtt", "steuerung", "system", "smart")

# --------------------------------------------------------------------------
# Protokoll
# --------------------------------------------------------------------------
LOG = deque(maxlen=500)
_log_lock = threading.Lock()
_log_queue = queue.Queue(maxsize=5000)


def log(msg):
    """Blockiert nie: Konsole und Logdatei werden von einem eigenen Thread beschrieben.
    (Unter Windows hält eine Markierung im Konsolenfenster sonst das ganze Programm an.)"""
    line = time.strftime("%d.%m.%Y %H:%M:%S") + "  " + msg
    with _log_lock:
        LOG.append(line)
    try:
        _log_queue.put_nowait(line)
    except queue.Full:
        pass


def _log_writer():
    while True:
        line = _log_queue.get()
        try:
            print(line, flush=True)
        except Exception:  # noqa: BLE001  (z. B. Konsole ohne UTF-8 oder geschlossen)
            pass
        try:
            if os.path.exists(LOGFILE_PATH) and os.path.getsize(LOGFILE_PATH) > 1_000_000:
                os.replace(LOGFILE_PATH, LOGFILE_PATH + ".1")
            with open(LOGFILE_PATH, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        except OSError:
            pass


def windows_setup():
    """Windows: QuickEdit der Konsole aus (Mausklick ins Fenster würde das Programm
    anhalten) und optional Standby verhindern."""
    if os.name != "nt":
        return
    try:
        import ctypes
        k32 = ctypes.windll.kernel32
        h = k32.GetStdHandle(-10)                       # STD_INPUT_HANDLE
        mode = ctypes.c_uint32()
        if k32.GetConsoleMode(h, ctypes.byref(mode)):
            new = (mode.value & ~0x0040) | 0x0080       # ~ENABLE_QUICK_EDIT_MODE | ENABLE_EXTENDED_FLAGS
            k32.SetConsoleMode(h, new)
            log("Windows: Schnellbearbeitung der Konsole deaktiviert (verhindert Anhalten durch Mausklick)")
    except Exception as e:  # noqa: BLE001
        log(f"Windows-Konsole: {e}")
    set_standby_block(get_config()["system"]["standby_verhindern"])
    try:
        import ctypes
        from ctypes import wintypes

        @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.DWORD)
        def _on_close(event):
            # 2 = Fenster geschlossen, 5 = Abmelden, 6 = Herunterfahren: Netzladung sauber beenden
            if event in (0, 1, 2, 5, 6):
                log("Programm wird beendet – laufende Netzladung wird gestoppt")
                try:
                    if smart is not None:
                        smart.shutdown()
                    if history is not None:
                        history.save()
                except Exception:  # noqa: BLE001
                    pass
            return False
        ctypes.windll.kernel32.SetConsoleCtrlHandler(_on_close, True)
        globals()["_close_handler"] = _on_close          # Referenz halten
    except Exception as e:  # noqa: BLE001
        log(f"Windows-Beenden-Handler: {e}")


def set_standby_block(on):
    if os.name != "nt":
        return
    try:
        import ctypes
        ES_CONTINUOUS, ES_SYSTEM_REQUIRED = 0x80000000, 0x00000001
        flags = ES_CONTINUOUS | (ES_SYSTEM_REQUIRED if on else 0)
        ctypes.windll.kernel32.SetThreadExecutionState(ctypes.c_uint32(flags))
        if on:
            log("Windows: Standby wird verhindert, solange das Programm läuft")
    except Exception as e:  # noqa: BLE001
        log(f"Standby-Einstellung: {e}")


# --------------------------------------------------------------------------
# Konfiguration
# --------------------------------------------------------------------------
_cfg_lock = threading.Lock()
CONFIG = copy.deepcopy(DEFAULT_CONFIG)


def merge(dst, src):
    if not isinstance(src, dict):
        return
    for k, v in src.items():
        if k in dst and isinstance(dst[k], dict) and isinstance(v, dict):
            merge(dst[k], v)
        elif k in dst:
            dst[k] = v


def load_config():
    global CONFIG
    cfg = copy.deepcopy(DEFAULT_CONFIG)
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                merge(cfg, json.load(f))
        except (OSError, ValueError) as e:
            log(f"config.json fehlerhaft ({e}) – verwende Standardwerte")
    raw_version = 0
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            raw_version = int(json.load(f).get("config_version", 0) or 0)
    except (OSError, ValueError, AttributeError, TypeError):
        pass
    if os.path.exists(CONFIG_PATH) and raw_version < 2:
        # v1.0.x: Timeout 5 s war für den SDongle zu knapp
        if float(cfg["wechselrichter"].get("timeout_s") or 0) < 15:
            log(f"Timeout von {cfg['wechselrichter']['timeout_s']} s auf 15 s erhöht (SDongle antwortet teils langsam)")
            cfg["wechselrichter"]["timeout_s"] = 15
    # v1.3.2: Preisgrenze 0–60 ct. Ältere Werte zur vorsichtigen Seite begrenzen (nie großzügiger machen)
    try:
        pm = float(cfg["smart"].get("preis_max_ct"))
        if pm < 0 or pm > 60:
            neu = 0 if pm < 0 else 60
            log(f"Smart-Laden: Preisgrenze {pm:g} ct auf {neu} ct begrenzt (erlaubt 0–60 ct)")
            cfg["smart"]["preis_max_ct"] = neu
    except (TypeError, ValueError):
        pass
    cfg["config_version"] = CONFIG_VERSION
    ok, err, cleaned = validate(cfg)
    if not ok:
        log(f"config.json: {err} – betroffene Werte auf Standard gesetzt")
        cfg = cleaned
    CONFIG = cfg
    save_config()


def save_config():
    tmp = CONFIG_PATH + ".tmp"
    with _cfg_lock:
        data = copy.deepcopy(CONFIG)
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")
    os.replace(tmp, CONFIG_PATH)


def get_config():
    with _cfg_lock:
        return CONFIG


def validate(cfg):
    """Prüft alle Felder; liefert (ok, fehlertext, bereinigte Konfiguration)."""
    out = copy.deepcopy(cfg)
    errors = []
    for (sec, key), (typ, lo, hi) in RULES.items():
        val = out.get(sec, {}).get(key)
        default = DEFAULT_CONFIG[sec][key]
        try:
            if typ is bool:
                if not isinstance(val, bool):
                    raise ValueError
            elif typ is int:
                if isinstance(val, bool) or val is None or float(val) != int(float(val)):
                    raise ValueError
                val = int(float(val))
                if not lo <= val <= hi:
                    raise ValueError
            elif typ is float:
                if isinstance(val, bool) or val is None:
                    raise ValueError
                val = float(val)
                if not lo <= val <= hi:
                    raise ValueError
                if val == int(val):
                    val = int(val)
            elif typ is str:
                if not isinstance(val, str):
                    raise ValueError
                val = val.strip()
                if not lo <= len(val) <= hi:
                    raise ValueError
            out[sec][key] = val
        except (ValueError, TypeError):
            errors.append(f"{LABELS[sec]} → {key} ungültig")
            out[sec][key] = default
    t = out["mqtt"]["basis_topic"].strip("/")
    if any(ch in t for ch in "#+") or not t:
        errors.append("MQTT → Basis-Topic darf weder leer sein noch # oder + enthalten")
        t = DEFAULT_CONFIG["mqtt"]["basis_topic"]
    out["mqtt"]["basis_topic"] = t
    stg = out["steuerung"]
    if stg["aktiv"] and len(stg["pin"]) < 4:
        errors.append("Steuerung → für die Steuerung ist eine PIN mit mindestens 4 Zeichen Pflicht")
        stg["aktiv"] = False
    if stg["aktiv"] and not stg["geraet_sn"]:
        errors.append("Steuerung → die Anlage muss zuerst bestätigt werden")
        stg["aktiv"] = False
    sm = out["smart"]
    if sm["zone"] not in ZONEN:
        errors.append("Smart-Laden → Gebotszone unbekannt")
        sm["zone"] = "DE-LU"
    if sm["prognose"] not in ("wetter", "statistik"):
        errors.append("Smart-Laden → Prognosequelle unbekannt")
        sm["prognose"] = "wetter"
    return (not errors), "; ".join(errors), out


# --------------------------------------------------------------------------
# Programmteile
# --------------------------------------------------------------------------
history = None
poller = None
mqtt = None
smart = None
stats = None

META = []
for r in REGISTERS:
    META.append({"key": r.key, "label": r.label, "unit": r.unit, "group": r.group, "topic": r.topic,
                 "reg": r.addr, "dec": 0 if r.gain == 1 else len(str(int(r.gain))) - 1})
for key, unit, label, group, topic in DERIVED:
    META.append({"key": key, "label": label, "unit": unit, "group": group, "topic": topic,
                 "reg": None, "dec": 1 if unit == "%" else 0})
GROUP_ORDER = {"geraet": 0, "pv": 1, "wr": 2, "akku": 3, "netz": 4, "haus": 5, "steuerung": 6}
META.sort(key=lambda m: (GROUP_ORDER[m["group"]], m["reg"] if m["reg"] is not None else 99999))
TOPICS = [(m["key"], m["topic"], m["group"] in STATIC_GROUPS) for m in META]


def on_new_values(values, static):
    """Wird nach jeder erfolgreichen Abfrage aufgerufen -> MQTT."""
    if not mqtt:
        return
    cfg = get_config()["mqtt"]
    if not cfg["aktiv"]:
        return
    items = []
    for key, topic, is_static in TOPICS:
        val = static.get(key) if is_static else values.get(key)
        if key.startswith("akku") and not values.get("_akku"):
            continue
        if (key.startswith("netz") or key in ("zaehler_status", "haus_verbrauch", "autarkie_pct",
                                              "eigenverbrauch_pct")) and not values.get("_zaehler"):
            if key != "zaehler_status":
                continue
        items.append((topic, val))
    if smart is not None:
        try:
            items.extend(smart.mqtt_items())
        except Exception as e:  # noqa: BLE001
            log(f"Smart-Laden MQTT: {e}")
    items.append(("akku/vorhanden", bool(values.get("_akku"))))
    items.append(("netz/zaehler_vorhanden", bool(values.get("_zaehler"))))
    if cfg["json_topic"]:
        data = {k: v for k, v in values.items() if not k.startswith("_")}
        data.update({k: v for k, v in static.items()})
        data["zeit"] = int(time.time())
        items.append(("json", json.dumps(data, ensure_ascii=False, separators=(",", ":"))))
    mqtt.publish_values(items)


# --------------------------------------------------------------------------
# Webserver
# --------------------------------------------------------------------------
class Handler(BaseHTTPRequestHandler):
    server_version = "HuaweiSolarDashboard/" + APP_VERSION
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):  # keine Zugriffsprotokolle in der Konsole
        pass

    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        if isinstance(body, (dict, list)):
            body = json.dumps(body, ensure_ascii=False).encode("utf-8")
        elif isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json_body(self):
        n = int(self.headers.get("Content-Length") or 0)
        if n > 100_000:
            raise ValueError("Anfrage zu groß")
        raw = self.rfile.read(n) if n else b"{}"
        data = json.loads(raw.decode("utf-8"))
        if not isinstance(data, dict):
            raise ValueError("JSON-Objekt erwartet")
        return data

    # ------------------------------------------------------------------
    def do_GET(self):
        u = urlparse(self.path)
        p = u.path
        if p in ("/", "/index.html"):
            cfg = get_config()
            title = (cfg["web"]["titel"] or "Solaranlage").replace("<", "&lt;").replace(">", "&gt;")
            html = PAGE.replace("__TITLE__", title).replace("__VERSION__", APP_VERSION)
            return self._send(200, html, "text/html; charset=utf-8")
        if p == "/api/data":
            vals, static, st = poller.snapshot()
            cfg = get_config()
            st["jetzt"] = time.time()
            st["programm_start"] = START_TIME
            return self._send(200, {
                "version": APP_VERSION, "titel": cfg["web"]["titel"] or "Solaranlage",
                "werte": vals, "geraet": static, "wechselrichter": st,
                "mqtt": dict(mqtt.state, aktiv=cfg["mqtt"]["aktiv"]),
                "basis_topic": cfg["mqtt"]["basis_topic"],
                "steuerung": {"aktiv": cfg["steuerung"]["aktiv"], "pin": bool(cfg["steuerung"]["pin"]),
                              "sperre": write_guard(cfg, static, st),
                              "einspeisung_erlaubt": cfg["steuerung"]["einspeisung_erlaubt"],
                              "modi": {str(k): v for k, v in ARBEITSMODUS.items() if k in (0, 1, 2, 4, 5)},
                              "einspeise_modi": {str(k): v for k, v in EINSPEISE_MODUS.items() if k in (0, 5, 6, 7)}}})
        if p == "/api/meta":
            return self._send(200, {"werte": META})
        if p == "/api/history":
            try:
                h = float(parse_qs(u.query).get("h", ["24"])[0])
            except ValueError:
                h = 24
            h = max(0.5, min(48, h))
            return self._send(200, {"punkte": history.get(h)})
        if p == "/api/config":
            cfg = copy.deepcopy(get_config())
            cfg["mqtt"]["passwort_gesetzt"] = bool(cfg["mqtt"]["passwort"])
            cfg["mqtt"]["passwort"] = ""
            cfg["steuerung"]["pin_gesetzt"] = bool(cfg["steuerung"]["pin"])
            cfg["steuerung"]["pin"] = ""
            _v, static, st = poller.snapshot()
            return self._send(200, {"config": cfg, "datei": CONFIG_PATH,
                                    "erkannt": {"modell": static.get("modell"), "seriennummer": static.get("seriennummer"),
                                                "modell_ok": model_ok(static.get("modell")), "verbunden": st["verbunden"]}})
        if p == "/api/smart":
            cfg = get_config()
            return self._send(200, {"zustand": smart.snapshot(), "einstellungen": cfg["smart"],
                                    "steuerung_aktiv": cfg["steuerung"]["aktiv"],
                                    "pin": bool(cfg["steuerung"]["pin"]), "zonen": ZONEN})
        if p == "/api/geo":
            q = (parse_qs(u.query).get("q", [""])[0] or "").strip()
            if len(q) < 2:
                return self._send(200, {"ok": False, "fehler": "Bitte mindestens 2 Zeichen eingeben"})
            try:
                return self._send(200, {"ok": True, "treffer": geocode(q)})
            except FetchError as e:
                return self._send(200, {"ok": False, "fehler": str(e)})
        if p == "/api/log":
            with _log_lock:
                lines = list(LOG)
            return self._send(200, {"zeilen": lines})
        return self._send(404, {"fehler": "nicht gefunden"})

    def _same_origin(self):
        """Schutz gegen Anfragen, die eine fremde Webseite im Browser auslöst (CSRF)."""
        ctype = (self.headers.get("Content-Type") or "").split(";")[0].strip().lower()
        if ctype != "application/json":
            return False            # erzwingt bei fremden Seiten eine CORS-Vorabprüfung
        origin = self.headers.get("Origin")
        if origin:
            host = (self.headers.get("Host") or "").lower()
            if urlparse(origin).netloc.lower() != host:
                return False
        return True

    def do_POST(self):
        p = urlparse(self.path).path
        if not self._same_origin():
            log(f"Abgewiesen: Anfrage an {p} von {self.client_address[0]} (fremde Herkunft/kein JSON)")
            return self._send(403, {"ok": False, "fehler": "Anfrage abgewiesen (Herkunft)"})
        try:
            data = self._json_body()
        except (ValueError, UnicodeDecodeError) as e:
            return self._send(400, {"ok": False, "fehler": f"Ungültige Anfrage: {e}"})
        if p == "/api/config":
            return self._save_config(data)
        if p == "/api/steuern":
            return self._control(data)
        if p == "/api/smart/vorschau":
            return self._send(200, _smart_preview(data))
        if p == "/api/smart":
            return self._send(200, _smart_save(self, data))
        if p == "/api/smart/quittieren":
            return self._send(200, _smart_ack(self, data))
        if p == "/api/test_wr":
            try:
                host = str(data.get("host") or "").strip()
                port = int(data.get("port") or 502)
                uid = int(data.get("unit_id") if data.get("unit_id") is not None else 1)
                timeout = float(data.get("timeout_s") or 5)
                delay = float(data.get("verbindungs_pause_s") or 1.5)
            except (TypeError, ValueError):
                return self._send(200, {"ok": False, "versuche": [{"unit_id": "-", "fehler": "Eingaben ungültig"}]})
            if not host:
                return self._send(200, {"ok": False, "versuche": [{"unit_id": "-", "fehler": "keine Adresse"}]})
            cur = get_config()["wechselrichter"]
            _v, static, st = poller.snapshot()
            if (host, port, uid) == (cur["host"], cur["port"], cur["unit_id"]) and st["verbunden"] and static:
                # läuft bereits – keine zweite Verbindung aufbauen (Huawei mag das nicht)
                return self._send(200, {"ok": True, "unit_id": uid, "modell": static.get("modell"),
                                        "seriennummer": static.get("seriennummer"), "versuche": [],
                                        "hinweis": "bestehende Verbindung"})
            ids = [uid] + [i for i in (1, 0, 100) if i != uid]
            same_device = host == cur["host"]
            if same_device:
                poller.suspend()        # laufende Verbindung freigeben
            try:
                res = test_connection(host, port, ids, timeout=min(max(timeout, 5), 15), delay=delay)
            finally:
                if same_device:
                    poller.resume()
            if res.get("ok"):
                log(f"Verbindungstest OK: {res.get('modell')} (Unit-ID {res['unit_id']})")
            return self._send(200, res)
        if p == "/api/test_mqtt":
            cur = get_config()["mqtt"]
            pw = data.get("passwort") if data.get("passwort") else cur["passwort"]
            try:
                port = int(data.get("port") or 1883)
            except (TypeError, ValueError):
                port = 1883
            host = str(data.get("host") or "").strip()
            if not host:
                return self._send(200, {"ok": False, "fehler": "kein Broker angegeben"})
            return self._send(200, test_broker(host, port, str(data.get("benutzer") or ""), pw,
                                               str(data.get("client_id") or "huawei-solar")))
        return self._send(404, {"ok": False, "fehler": "nicht gefunden"})

    def _control(self, data):
        return self._send(200, _handle_control(self, data))

    def _save_config(self, data):
        global CONFIG
        new = copy.deepcopy(get_config())
        for sec in SECTIONS:
            if isinstance(data.get(sec), dict):
                for k, v in data[sec].items():
                    if (sec, k) in RULES:
                        new[sec][k] = v
        old = get_config()
        dst = data.get("steuerung") if isinstance(data.get("steuerung"), dict) else {}
        # Gerätedaten nie direkt vom Browser übernehmen
        new["steuerung"]["geraet_sn"] = old["steuerung"]["geraet_sn"]
        new["steuerung"]["geraet_modell"] = old["steuerung"]["geraet_modell"]
        if dst.get("pin_loeschen"):
            new["steuerung"]["pin"] = ""
            new["steuerung"]["aktiv"] = False
        if not dst.get("pin"):
            new["steuerung"]["pin"] = "" if dst.get("pin_loeschen") else old["steuerung"]["pin"]
        o, n = old["steuerung"], new["steuerung"]
        # Alles, was die Sicherheit verringert, braucht die AKTUELLE PIN (falls eine gesetzt ist)
        weaker = ((n["aktiv"] and not o["aktiv"]) or (n["einspeisung_erlaubt"] and not o["einspeisung_erlaubt"])
                  or (n["pin"] != o["pin"]))
        if weaker and o["pin"]:
            res = check_pin(str(data.get("pin_aktuell") or ""), o["pin"], self.client_address[0])
            if res:
                return self._send(200, res)
        if dst.get("geraet_bestaetigen") and n["aktiv"]:
            _v, static, st = poller.snapshot()
            if not st["verbunden"] or not static.get("seriennummer"):
                return self._send(200, {"ok": False, "fehler": "Zum Bestätigen muss der Wechselrichter verbunden sein"})
            if not model_ok(static.get("modell")):
                return self._send(200, {"ok": False, "fehler": f"Modell {static.get('modell')} wird für die Steuerung nicht unterstützt"})
            n["geraet_sn"], n["geraet_modell"] = static["seriennummer"], static.get("modell") or ""
        if not n["aktiv"]:
            n["einspeisung_erlaubt"] = False
        ok, err, cleaned = validate(new)
        if not ok:
            return self._send(200, {"ok": False, "fehler": err})
        with _cfg_lock:
            CONFIG = cleaned
        save_config()
        log("Einstellungen gespeichert")
        if cleaned["wechselrichter"] != old["wechselrichter"]:
            poller.reload()
        if cleaned["mqtt"] != old["mqtt"]:
            mqtt.reload()
        if cleaned["system"] != old["system"]:
            set_standby_block(cleaned["system"]["standby_verhindern"])
        if cleaned["steuerung"]["aktiv"] != old["steuerung"]["aktiv"]:
            log(f"Steuerung über die Webseite {'ERLAUBT' if cleaned['steuerung']['aktiv'] else 'gesperrt'} "
                f"(von {self.client_address[0]}, Anlage SN {cleaned['steuerung']['geraet_sn'] or '-'})")
            smart.poke()
        if cleaned["steuerung"]["einspeisung_erlaubt"] != old["steuerung"]["einspeisung_erlaubt"]:
            log("Einspeisebegrenzung änderbar: " + ("ja" if cleaned["steuerung"]["einspeisung_erlaubt"] else "nein"))
        new_port = cleaned["web"]["port"]
        if new_port != old["web"]["port"]:
            if not port_free(new_port):
                with _cfg_lock:
                    CONFIG["web"]["port"] = old["web"]["port"]
                save_config()
                return self._send(200, {"ok": False, "fehler": f"Port {new_port} ist bereits belegt"})
            self._send(200, {"ok": True, "neuer_port": new_port})
            threading.Thread(target=switch_port, args=(new_port,), daemon=True).start()
            return None
        return self._send(200, {"ok": True})


_pin_lock = threading.Lock()
_pin_fail = {"n": 0, "bis": 0}


def check_pin(given, pin, client):
    """None = PIN richtig, sonst Fehlerantwort. 5 Fehlversuche -> 60 s Sperre."""
    with _pin_lock:
        if time.time() < _pin_fail["bis"]:
            return {"ok": False, "fehler": "Zu viele falsche PIN-Eingaben – bitte 1 Minute warten"}
        if not pin or not hmac.compare_digest(given, pin):
            _pin_fail["n"] += 1
            if _pin_fail["n"] >= 5:
                _pin_fail.update(n=0, bis=time.time() + 60)
            log(f"Falsche PIN von {client}")
            time.sleep(1)
            return {"ok": False, "fehler": "PIN falsch", "pin_falsch": True}
        _pin_fail["n"] = 0
    return None


def _handle_control(handler, data):
    cfg = get_config()
    client = handler.client_address[0]
    values, static, st = poller.snapshot()
    reason = write_guard(cfg, static, st)
    if reason:
        return {"ok": False, "fehler": reason}
    res = check_pin(str(data.get("pin") or ""), cfg["steuerung"]["pin"], client)
    if res:
        return res
    action = str(data.get("aktion") or "")
    params = data.get("werte") if isinstance(data.get("werte"), dict) else {}
    if smart.active and action.startswith("zwang"):
        return {"ok": False, "fehler": "Smart-Laden steuert gerade das Zwangsladen – erst die Automatik ausschalten"}
    try:
        text, writes = plan(action, params, values)
    except ControlError as e:
        return {"ok": False, "fehler": str(e)}
    if any(k in EINSPEISE_KEYS for k, _v in writes) and not cfg["steuerung"]["einspeisung_erlaubt"]:
        return {"ok": False, "fehler": "Änderungen an der Einspeisebegrenzung sind gesperrt (Einstellungen → Steuerung)"}
    log(f"Steuerung von {client}: {text}")
    try:
        result = poller.execute(make_executor(writes, cfg["steuerung"]["geraet_sn"]), timeout=120)
    except ControlError as e:
        log(f"Steuerung fehlgeschlagen: {e}")
        return {"ok": False, "fehler": str(e)}
    except (ModbusError, OSError) as e:
        log(f"Steuerung fehlgeschlagen: {e}")
        return {"ok": False, "fehler": f"Schreiben fehlgeschlagen: {e}"}
    bad = [r for r in result if not r["ok"]]
    if bad:
        log("Steuerung: Gerät meldet abweichende Werte: " +
            ", ".join(f"{r['bezeichnung']}={r['gelesen']}" for r in bad))
    else:
        log(f"Steuerung ausgeführt: {text}")
    return {"ok": True, "text": text, "ergebnis": result, "abweichung": bool(bad)}


def _merge_smart(data):
    new = copy.deepcopy(get_config())
    if isinstance(data.get("smart"), dict):
        for k, v in data["smart"].items():
            if ("smart", k) in RULES:
                new["smart"][k] = v
    return validate(new)


def _smart_preview(data):
    ok, err, cleaned = _merge_smart(data)
    if not ok:
        return {"ok": False, "fehler": err}
    plan = smart.compute(cleaned["smart"])
    if plan is None:
        return {"ok": False, "fehler": "Kein Plan möglich (Wechselrichter/Akku nicht verbunden)"}
    return {"ok": True, "plan": plan}


def _smart_save(handler, data):
    """PIN-Regel: Nur „scharf schalten“ (Automatik an UND Probebetrieb aus) braucht PIN und
    freigegebene Steuerung. Ausschalten, Probebetrieb und Einstellungen im Probebetrieb gehen
    ohne PIN – sie können nichts in den Wechselrichter schreiben."""
    global CONFIG
    cfg = get_config()
    ok, err, cleaned = _merge_smart(data)
    if not ok:
        return {"ok": False, "fehler": err}
    scharf = cleaned["smart"]["aktiv"] and not cleaned["smart"]["probebetrieb"]
    if scharf:
        if not cfg["steuerung"]["aktiv"]:
            return {"ok": False, "fehler": "Steuerung ist gesperrt – unter Einstellungen → Steuerung freigeben "
                                          "(oder Probebetrieb einschalten)"}
        res = check_pin(str(data.get("pin") or ""), cfg["steuerung"]["pin"], handler.client_address[0])
        if res:
            return res
    old = cfg["smart"]
    with _cfg_lock:
        CONFIG = cleaned
    save_config()
    who = handler.client_address[0]
    if (old["aktiv"], old["probebetrieb"]) != (cleaned["smart"]["aktiv"], cleaned["smart"]["probebetrieb"]):
        mode = "aus" if not cleaned["smart"]["aktiv"] else ("PROBEBETRIEB" if cleaned["smart"]["probebetrieb"] else "SCHARF")
        log(f"Smart-Laden von {who}: {mode}")
    else:
        log(f"Smart-Laden: Einstellungen geändert von {who}")
    smart.poke()
    return {"ok": True}


def _smart_ack(handler, data):
    cfg = get_config()
    if cfg["steuerung"]["pin"]:
        res = check_pin(str(data.get("pin") or ""), cfg["steuerung"]["pin"], handler.client_address[0])
        if res:
            return res
    log(f"Smart-Laden: Störung quittiert von {handler.client_address[0]}")
    smart.acknowledge()
    return {"ok": True}


def port_free(port):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(("0.0.0.0", port))
        return True
    except OSError:
        return False
    finally:
        s.close()


class Server(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


_server = None
_server_lock = threading.Lock()


def start_server(port):
    global _server
    srv = Server(("0.0.0.0", port), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True, name=f"Web:{port}").start()
    with _server_lock:
        _server = srv
    log(f"Webseite erreichbar unter http://{local_ip()}:{port}/  (lokal: http://127.0.0.1:{port}/)")
    return srv


def switch_port(new_port):
    time.sleep(0.5)
    with _server_lock:
        old = _server
    try:
        start_server(new_port)
    except OSError as e:
        log(f"Port {new_port} konnte nicht geöffnet werden: {e}")
        return
    time.sleep(1.5)
    if old:
        old.shutdown()
        old.server_close()


def local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except OSError:
        return "127.0.0.1"


# --------------------------------------------------------------------------
START_TIME = time.time()


def main():
    global history, poller, mqtt, smart, stats
    os.makedirs(DATA_DIR, exist_ok=True)
    threading.Thread(target=_log_writer, daemon=True, name="Protokoll").start()
    log(f"{APP_NAME} v{APP_VERSION} startet")
    load_config()
    windows_setup()
    log(f"Einstellungen: {CONFIG_PATH}")
    history = History(HISTORY_PATH)
    poller = InverterPoller(get_config, history, log)
    mqtt = MqttPublisher(get_config, log)
    stats = Stats(STATS_PATH)
    smart = SmartCharger(get_config, poller, stats, log, SMART_STATE_PATH)
    poller.listeners.append(smart.on_values)
    poller.listeners.append(on_new_values)
    mqtt.start()
    poller.start()
    smart.start()

    port = get_config()["web"]["port"]
    try:
        start_server(port)
    except OSError as e:
        log(f"Port {port} ist belegt ({e}). Bitte in config.json einen anderen Port eintragen.")
        if getattr(sys, "frozen", False):
            input("Enter zum Beenden …")
        return 1
    try:
        import signal
        def _term(*_):
            raise KeyboardInterrupt
        signal.signal(signal.SIGTERM, _term)
    except (ImportError, ValueError, AttributeError):
        pass
    if not get_config()["wechselrichter"]["host"]:
        log("Noch kein Wechselrichter eingestellt – bitte auf der Webseite unter EINSTELLUNGEN eintragen.")
    try:
        while True:
            time.sleep(5)
            # Watchdog: Threads überwachen und notfalls neu starten
            poller.watchdog()
            if not poller.is_alive():
                log("Abfrage-Thread war beendet – wird neu gestartet")
                old = poller
                poller = InverterPoller(get_config, history, log)
                poller.listeners = old.listeners
                poller.start()
                smart.poller = poller
            if not smart.is_alive():
                log("Smart-Laden-Thread war beendet – wird neu gestartet")
                smart = SmartCharger(get_config, poller, stats, log, SMART_STATE_PATH)
                poller.listeners[0] = smart.on_values
                smart.start()
            if not mqtt.is_alive():
                log("MQTT-Thread war beendet – wird neu gestartet")
                mqtt = MqttPublisher(get_config, log)
                mqtt.start()
    except KeyboardInterrupt:
        log("Beende …")
    finally:
        history.save()
        stats.save()
        smart.stop()
        try:
            smart.shutdown()            # eigene Netzladung beenden, Einstellung zurücksetzen
        except Exception as e:  # noqa: BLE001
            log(f"Smart-Laden beim Beenden: {e}")
        mqtt.stop()
        poller.stop()
        time.sleep(0.5)          # Protokoll-Thread schreiben lassen
    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
