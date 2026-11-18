"""Minimaler MQTT-3.1.1-Client (nur Senden, QoS 0) ohne Fremdbibliotheken.

- Benutzername/Passwort
- Last Will: <basis>/status = offline (retained), nach Verbindung online
- automatischer Neuaufbau der Verbindung
"""

import socket
import struct
import threading
import time

from .modbus import friendly


def _enc_str(s):
    b = s.encode("utf-8")
    return struct.pack(">H", len(b)) + b


def _enc_len(n):
    out = bytearray()
    while True:
        d = n % 128
        n //= 128
        if n:
            d |= 0x80
        out.append(d)
        if not n:
            return bytes(out)


CONNACK_TEXT = {
    1: "Protokollversion abgelehnt",
    2: "Client-ID abgelehnt",
    3: "Broker nicht verfügbar",
    4: "Benutzername oder Passwort falsch",
    5: "Nicht autorisiert",
}


class MqttError(Exception):
    pass


class MqttConnection:
    def __init__(self, host, port, client_id, user="", password="", keepalive=60,
                 will_topic=None, will_payload=b"offline", timeout=5.0):
        self.host, self.port = host, int(port)
        self.client_id = client_id
        self.user, self.password = user, password
        self.keepalive = keepalive
        self.will_topic, self.will_payload = will_topic, will_payload
        self.timeout = timeout
        self.sock = None
        self.lock = threading.Lock()
        self.last_tx = 0

    def connect(self):
        s = socket.create_connection((self.host, self.port), timeout=self.timeout)
        s.settimeout(self.timeout)
        flags = 0x02  # clean session
        payload = _enc_str(self.client_id)
        if self.will_topic:
            flags |= 0x04 | 0x20  # Will, QoS0, Retain
            payload += _enc_str(self.will_topic) + struct.pack(">H", len(self.will_payload)) + self.will_payload
        if self.user:
            flags |= 0x80
            payload += _enc_str(self.user)
            if self.password:
                flags |= 0x40
                payload += _enc_str(self.password)
        var = _enc_str("MQTT") + bytes([4, flags]) + struct.pack(">H", self.keepalive)
        body = var + payload
        s.sendall(b"\x10" + _enc_len(len(body)) + body)
        resp = b""
        while len(resp) < 4:
            chunk = s.recv(4 - len(resp))
            if not chunk:
                s.close()
                raise MqttError("Broker hat die Verbindung geschlossen")
            resp += chunk
        if resp[0] != 0x20:
            s.close()
            raise MqttError("Ungültige Antwort vom Broker")
        if resp[3] != 0:
            s.close()
            raise MqttError(CONNACK_TEXT.get(resp[3], f"Verbindung abgelehnt (Code {resp[3]})"))
        s.settimeout(None)
        self.sock = s
        self.last_tx = time.time()

    def publish(self, topic, payload, retain=False):
        if isinstance(payload, str):
            payload = payload.encode("utf-8")
        body = _enc_str(topic) + payload
        hdr = 0x30 | (0x01 if retain else 0)
        pkt = bytes([hdr]) + _enc_len(len(body)) + body
        with self.lock:
            if not self.sock:
                raise MqttError("nicht verbunden")
            self.sock.sendall(pkt)
            self.last_tx = time.time()

    def ping(self):
        with self.lock:
            if self.sock:
                self.sock.sendall(b"\xc0\x00")
                self.last_tx = time.time()

    def disconnect(self):
        with self.lock:
            if self.sock:
                try:
                    self.sock.sendall(b"\xe0\x00")
                except OSError:
                    pass
                try:
                    self.sock.close()
                except OSError:
                    pass
            self.sock = None


class MqttPublisher(threading.Thread):
    """Hält die Verbindung zum Broker und veröffentlicht die Werte."""

    def __init__(self, cfg_getter, log):
        super().__init__(daemon=True, name="MQTT")
        self.cfg_getter = cfg_getter
        self.log = log
        self.conn = None
        self.state = {"verbunden": False, "fehler": "", "gesendet": 0, "letzte_sendung": 0}
        self._stop = threading.Event()
        self._reload = threading.Event()
        self._last_sent = {}      # topic -> (payload, zeit)
        self._lock = threading.Lock()

    def stop(self):
        self._stop.set()
        self._reload.set()
        if self.conn:
            self._publish_raw(self._status_topic(), "offline", True)
            self.conn.disconnect()

    def reload(self):
        self._reload.set()

    def _status_topic(self):
        return self.cfg_getter()["mqtt"]["basis_topic"].strip("/") + "/status"

    def run(self):
        backoff = 2
        while not self._stop.is_set():
            c = self.cfg_getter()["mqtt"]
            if not c["aktiv"] or not c["host"]:
                self.state.update(verbunden=False, fehler="" if not c["aktiv"] else "Kein Broker eingestellt")
                self._reload.wait(2)
                self._reload.clear()
                continue
            try:
                self.conn = MqttConnection(c["host"], c["port"], c["client_id"], c["benutzer"], c["passwort"],
                                           keepalive=60, will_topic=self._status_topic())
                self.conn.connect()
                self.conn.publish(self._status_topic(), "online", retain=True)
                with self._lock:
                    self._last_sent = {}
                self.state.update(verbunden=True, fehler="")
                self.log(f"MQTT verbunden mit {c['host']}:{c['port']}")
                backoff = 2
                self._serve()
            except (OSError, MqttError) as e:
                msg = str(e) if isinstance(e, MqttError) else friendly(e).replace(" und Modbus TCP im Wechselrichter freigeben", " – läuft der Broker?")
                if self.state.get("fehler") != msg:
                    self.log(f"MQTT: {msg}")
                self.state.update(verbunden=False, fehler=msg)
            finally:
                if self.conn:
                    self.conn.disconnect()
                self.conn = None
                self.state["verbunden"] = False
            if self._reload.is_set():
                self._reload.clear()
                continue
            self._reload.wait(backoff)
            self._reload.clear()
            backoff = min(backoff * 2, 60)

    def _serve(self):
        """Hält die Verbindung (Ping, Erkennen eines Abbruchs)."""
        sock = self.conn.sock
        sock.settimeout(1.0)
        while not self._stop.is_set() and not self._reload.is_set():
            try:
                data = sock.recv(256)
                if data == b"":
                    raise MqttError("Broker hat die Verbindung getrennt")
            except socket.timeout:
                pass
            if time.time() - self.conn.last_tx > 30:
                self.conn.ping()
        if self._reload.is_set():
            try:
                self.conn.publish(self._status_topic(), "offline", retain=True)
            except (OSError, MqttError):
                pass

    def _publish_raw(self, topic, payload, retain):
        try:
            if self.conn and self.conn.sock:
                self.conn.publish(topic, payload, retain)
                return True
        except (OSError, MqttError):
            pass
        return False

    # ------------------------------------------------------------------
    def publish_values(self, items):
        """items: Liste (topic_suffix, wert). Sendet je Wert ein eigenes Topic."""
        c = self.cfg_getter()["mqtt"]
        if not self.state["verbunden"] or not self.conn:
            return
        base = c["basis_topic"].strip("/")
        now = time.time()
        only_changes = c["nur_aenderungen"]
        force = float(c["erzwingen_s"])
        n = 0
        for suffix, val in items:
            if val is None:
                continue
            if isinstance(val, bool):
                payload = "1" if val else "0"
            elif isinstance(val, float):
                payload = (f"{val:.3f}".rstrip("0").rstrip(".")) or "0"
            else:
                payload = str(val)
            topic = f"{base}/{suffix}"
            with self._lock:
                prev = self._last_sent.get(topic)
                if only_changes and prev and prev[0] == payload and now - prev[1] < force:
                    continue
            try:
                self.conn.publish(topic, payload, retain=c["retain"])
            except (OSError, MqttError) as e:
                self.log(f"MQTT senden fehlgeschlagen: {e}")
                self._reload.set()
                return
            with self._lock:
                self._last_sent[topic] = (payload, now)
            n += 1
        self.state["gesendet"] += n
        self.state["letzte_sendung"] = now


def test_broker(host, port, user, password, client_id):
    conn = MqttConnection(host, port, client_id + "-test", user, password, timeout=5)
    try:
        conn.connect()
        conn.disconnect()
        return {"ok": True}
    except (OSError, MqttError) as e:
        return {"ok": False, "fehler": str(e) if isinstance(e, MqttError) else friendly(e).replace(" und Modbus TCP im Wechselrichter freigeben", " – läuft der Broker?")}
