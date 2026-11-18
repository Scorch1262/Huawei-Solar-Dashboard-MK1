#!/usr/bin/env python3
"""Huawei-Solar-Dashboard-MK1

Liest einen Huawei SUN2000-(5-12)K-MAP0 Hybrid-Wechselrichter mit LUNA2000-Akku
und Smart Meter per Modbus TCP aus, zeigt alle Werte auf einer Webseite im
lokalen Netzwerk und sendet jeden Wert als eigenes MQTT-Topic an einen Broker.

Nur Python-Standardbibliothek – läuft als exe (PyInstaller), unter Linux,
auf dem Raspberry Pi oder auf OpenWrt-Routern mit python3.
"""

import copy
import json
import os
import socket
import sys
import threading
import time
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

from solar.inverter import History, InverterPoller, test_connection
from solar.mqtt import MqttPublisher, test_broker
from solar.registers import REGISTERS, DERIVED, STATIC_GROUPS
from solar.webui import PAGE

APP_NAME = "Huawei-Solar-Dashboard-MK1"
APP_VERSION = "1.0.0"


def base_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


BASE = base_dir()
DATA_DIR = os.path.join(BASE, "daten")
CONFIG_PATH = os.path.join(BASE, "config.json")
HISTORY_PATH = os.path.join(DATA_DIR, "verlauf.json")

DEFAULT_CONFIG = {
    "web": {"port": 8095, "titel": "Solaranlage"},
    "wechselrichter": {"host": "", "port": 502, "unit_id": 1, "intervall_s": 10,
                       "timeout_s": 5, "verbindungs_pause_s": 1.5},
    "mqtt": {"aktiv": False, "host": "", "port": 1883, "benutzer": "", "passwort": "",
             "client_id": "huawei-solar-dashboard", "basis_topic": "huawei_solar",
             "retain": True, "nur_aenderungen": False, "erzwingen_s": 60, "json_topic": True},
}

# Prüfregeln für Einstellungen: (Typ, min, max)
RULES = {
    ("web", "port"): (int, 1, 65535), ("web", "titel"): (str, 0, 60),
    ("wechselrichter", "host"): (str, 0, 255), ("wechselrichter", "port"): (int, 1, 65535),
    ("wechselrichter", "unit_id"): (int, 0, 255), ("wechselrichter", "intervall_s"): (float, 2, 3600),
    ("wechselrichter", "timeout_s"): (float, 1, 60), ("wechselrichter", "verbindungs_pause_s"): (float, 0, 10),
    ("mqtt", "aktiv"): (bool, 0, 0), ("mqtt", "host"): (str, 0, 255), ("mqtt", "port"): (int, 1, 65535),
    ("mqtt", "benutzer"): (str, 0, 255), ("mqtt", "passwort"): (str, 0, 255),
    ("mqtt", "client_id"): (str, 1, 64), ("mqtt", "basis_topic"): (str, 1, 128),
    ("mqtt", "retain"): (bool, 0, 0), ("mqtt", "nur_aenderungen"): (bool, 0, 0),
    ("mqtt", "erzwingen_s"): (float, 0, 86400), ("mqtt", "json_topic"): (bool, 0, 0),
}
LABELS = {
    "web": "Webseite", "wechselrichter": "Wechselrichter", "mqtt": "MQTT",
}

# --------------------------------------------------------------------------
# Protokoll
# --------------------------------------------------------------------------
LOG = deque(maxlen=300)
_log_lock = threading.Lock()


def log(msg):
    line = time.strftime("%d.%m.%Y %H:%M:%S") + "  " + msg
    with _log_lock:
        LOG.append(line)
    try:
        print(line, flush=True)
    except Exception:  # noqa: BLE001  (z. B. Konsole ohne UTF-8)
        pass


# --------------------------------------------------------------------------
# Konfiguration
# --------------------------------------------------------------------------
_cfg_lock = threading.Lock()
CONFIG = copy.deepcopy(DEFAULT_CONFIG)


def merge(dst, src):
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
    return (not errors), "; ".join(errors), out


# --------------------------------------------------------------------------
# Programmteile
# --------------------------------------------------------------------------
history = None
poller = None
mqtt = None

META = []
for r in REGISTERS:
    META.append({"key": r.key, "label": r.label, "unit": r.unit, "group": r.group, "topic": r.topic,
                 "reg": r.addr, "dec": 0 if r.gain == 1 else len(str(int(r.gain))) - 1})
for key, unit, label, group, topic in DERIVED:
    META.append({"key": key, "label": label, "unit": unit, "group": group, "topic": topic,
                 "reg": None, "dec": 1 if unit == "%" else 0})
GROUP_ORDER = {"geraet": 0, "pv": 1, "wr": 2, "akku": 3, "netz": 4, "haus": 5}
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
            return self._send(200, {
                "version": APP_VERSION, "titel": cfg["web"]["titel"] or "Solaranlage",
                "werte": vals, "geraet": static, "wechselrichter": st,
                "mqtt": dict(mqtt.state, aktiv=cfg["mqtt"]["aktiv"]),
                "basis_topic": cfg["mqtt"]["basis_topic"]})
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
            return self._send(200, {"config": cfg, "datei": CONFIG_PATH})
        if p == "/api/log":
            with _log_lock:
                lines = list(LOG)
            return self._send(200, {"zeilen": lines})
        return self._send(404, {"fehler": "nicht gefunden"})

    def do_POST(self):
        p = urlparse(self.path).path
        try:
            data = self._json_body()
        except (ValueError, UnicodeDecodeError) as e:
            return self._send(400, {"ok": False, "fehler": f"Ungültige Anfrage: {e}"})
        if p == "/api/config":
            return self._save_config(data)
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
            ids = [uid] + [i for i in (1, 0, 100) if i != uid]
            res = test_connection(host, port, ids, timeout=min(timeout, 8), delay=delay)
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

    def _save_config(self, data):
        global CONFIG
        new = copy.deepcopy(get_config())
        for sec in ("web", "wechselrichter", "mqtt"):
            if isinstance(data.get(sec), dict):
                for k, v in data[sec].items():
                    if (sec, k) in RULES:
                        new[sec][k] = v
        ok, err, cleaned = validate(new)
        if not ok:
            return self._send(200, {"ok": False, "fehler": err})
        old = get_config()
        with _cfg_lock:
            CONFIG = cleaned
        save_config()
        log("Einstellungen gespeichert")
        if cleaned["wechselrichter"] != old["wechselrichter"]:
            poller.reload()
        if cleaned["mqtt"] != old["mqtt"]:
            mqtt.reload()
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
def main():
    global history, poller, mqtt
    os.makedirs(DATA_DIR, exist_ok=True)
    log(f"{APP_NAME} v{APP_VERSION} startet")
    load_config()
    log(f"Einstellungen: {CONFIG_PATH}")
    history = History(HISTORY_PATH)
    poller = InverterPoller(get_config, history, log)
    mqtt = MqttPublisher(get_config, log)
    poller.listeners.append(on_new_values)
    mqtt.start()
    poller.start()

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
            time.sleep(1)
    except KeyboardInterrupt:
        log("Beende …")
    finally:
        history.save()
        mqtt.stop()
        poller.stop()
    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
