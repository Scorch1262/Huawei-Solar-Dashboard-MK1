"""Schlanker Modbus-TCP-Client speziell für Huawei SUN2000 (FC 0x03, 0x06, 0x10).

Erfahrungen mit Huawei (SDongle / WLAN-FE):
- Der SDongle antwortet teils sehr langsam -> großzügiger Timeout (Standard 15 s).
- Eine einzelne Zeitüberschreitung ist KEIN Grund, die Verbindung zu trennen:
  Ständiges Neu-Verbinden führt dazu, dass der Dongle neue Verbindungen eine Zeit
  lang abweist (halboffene Verbindungen belegen seine wenigen Plätze).
  Erst nach mehreren Zeitüberschreitungen in Folge wird neu verbunden.
- Verspätete Antworten werden anhand der Transaktions-ID verworfen.
- Nach dem Verbindungsaufbau braucht das Gerät eine kurze Pause.
- Es wird nur EIN Modbus-TCP-Client gleichzeitig zuverlässig bedient.
"""

import socket
import struct
import threading
import time


class ModbusError(Exception):
    """Verbindungs-/Protokollfehler – Verbindung ist danach ungültig."""


class ModbusTimeout(ModbusError):
    """Gerät hat nicht rechtzeitig geantwortet – Verbindung bleibt bestehen."""


class ModbusException(ModbusError):
    """Der Wechselrichter hat mit einem Modbus-Ausnahmecode geantwortet."""

    TEXT = {
        1: "Ungültige Funktion",
        2: "Ungültige Registeradresse",
        3: "Ungültiger Datenwert",
        4: "Gerätefehler",
        6: "Gerät beschäftigt",
        0x0A: "Gateway-Pfad nicht verfügbar",
        0x0B: "Zielgerät antwortet nicht (Unit-ID prüfen)",
        0x80: "Keine Schreibberechtigung",
    }
    # Diese Codes sind vorübergehend: Verbindung behalten, später erneut versuchen
    TRANSIENT = {4, 6, 0x0A, 0x0B}

    def __init__(self, code):
        self.code = code
        super().__init__(f"Modbus-Ausnahme {code}: {self.TEXT.get(code, 'unbekannt')}")


def friendly(e):
    """Netzwerkfehler in verständliche deutsche Meldungen übersetzen."""
    if isinstance(e, ModbusError):
        return str(e)
    if isinstance(e, ConnectionRefusedError):
        return "Verbindung abgelehnt – Adresse/Port prüfen und Modbus TCP im Wechselrichter freigeben"
    if isinstance(e, (socket.timeout, TimeoutError)):
        return "Zeitüberschreitung – Gerät antwortet nicht"
    if isinstance(e, ConnectionResetError):
        return "Verbindung vom Gerät zurückgesetzt (anderer Modbus-Client aktiv?)"
    if isinstance(e, ConnectionAbortedError):
        return "Verbindung abgebrochen"
    if isinstance(e, socket.gaierror):
        return "Hostname nicht auflösbar"
    if isinstance(e, OSError) and e.errno in (101, 113, 10051, 10065):
        return "Netzwerk/Gerät nicht erreichbar"
    return str(e) or e.__class__.__name__


def _enable_keepalive(s):
    """TCP-Keepalive, damit tote Verbindungen erkannt werden (alle Plattformen)."""
    try:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
        if hasattr(socket, "SIO_KEEPALIVE_VALS"):            # Windows
            s.ioctl(socket.SIO_KEEPALIVE_VALS, (1, 30000, 10000))
        else:
            for name, val in (("TCP_KEEPIDLE", 30), ("TCP_KEEPINTVL", 10), ("TCP_KEEPCNT", 3)):
                if hasattr(socket, name):
                    s.setsockopt(socket.IPPROTO_TCP, getattr(socket, name), val)
    except OSError:
        pass


class ModbusTcpClient:
    def __init__(self, host, port=502, unit=1, timeout=15.0, connect_delay=1.5,
                 request_gap=0.05, max_timeouts=5):
        self.host = host
        self.port = int(port)
        self.unit = int(unit)
        self.timeout = float(timeout)
        self.connect_delay = float(connect_delay)
        self.request_gap = float(request_gap)
        self.max_timeouts = int(max_timeouts)
        self._sock = None
        self._tid = 0
        self._timeouts_in_row = 0
        self._lock = threading.Lock()
        self.connects = 0

    # ------------------------------------------------------------------
    def connect(self):
        self.close()
        s = socket.create_connection((self.host, self.port), timeout=min(self.timeout, 10))
        s.settimeout(self.timeout)
        s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        _enable_keepalive(s)
        self._sock = s
        self._timeouts_in_row = 0
        self.connects += 1
        if self.connect_delay > 0:
            time.sleep(self.connect_delay)

    def close(self):
        s, self._sock = self._sock, None
        if s is not None:
            # sauber abmelden, damit der Dongle den Verbindungsplatz sofort freigibt
            try:
                s.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            try:
                s.close()
            except OSError:
                pass

    def abort(self):
        """Von außen (Watchdog) aufrufbar: blockierende Anfrage abbrechen."""
        self.close()

    @property
    def connected(self):
        return self._sock is not None

    # ------------------------------------------------------------------
    def _recv_exact(self, n):
        buf = b""
        while len(buf) < n:
            sock = self._sock
            if sock is None:
                raise ModbusError("Verbindung wurde getrennt")
            try:
                chunk = sock.recv(n - len(buf))
            except (socket.timeout, TimeoutError):
                if buf:
                    # mitten im Telegramm abgebrochen -> Datenstrom nicht mehr synchron
                    raise ModbusError("Antwort unvollständig (Zeitüberschreitung mitten im Telegramm)")
                raise
            if not chunk:
                raise ModbusError("Verbindung vom Wechselrichter geschlossen")
            buf += chunk
        return buf

    def _transact(self, pdu, expect_fc):
        """Sendet eine Anfrage und liefert den Antwort-PDU-Rumpf (ohne Funktionscode)."""
        with self._lock:
            if self._sock is None:
                # Bewusst KEIN automatisches Neuverbinden: jeder Verbindungsaufbau läuft über
                # den Abfrage-Thread, der danach die Gerätedaten (Seriennummer) neu liest.
                # Sonst könnte nach einem Gerätewechsel (z. B. neue IP-Vergabe) mit alten
                # Gerätedaten weitergearbeitet werden.
                raise ModbusError("Nicht verbunden")
            self._tid = (self._tid + 1) & 0xFFFF
            tid = self._tid
            mbap = struct.pack(">HHHB", tid, 0, len(pdu) + 1, self.unit)
            if self.request_gap:
                time.sleep(self.request_gap)
            try:
                self._sock.sendall(mbap + pdu)
                deadline = time.time() + self.timeout
                while True:
                    head = self._recv_exact(7)
                    rtid, _proto, length, _unit = struct.unpack(">HHHB", head)
                    if length < 2 or length > 260:
                        raise ModbusError(f"Ungültige Antwortlänge {length}")
                    body = self._recv_exact(length - 1)
                    if rtid == tid:
                        break
                    # verspätete Antwort auf eine frühere Anfrage -> verwerfen
                    if time.time() > deadline:
                        raise socket.timeout()
            except (socket.timeout, TimeoutError):
                self._timeouts_in_row += 1
                if self._timeouts_in_row >= self.max_timeouts:
                    self.close()
                    raise ModbusError(f"{self._timeouts_in_row} Zeitüberschreitungen in Folge – verbinde neu")
                raise ModbusTimeout("Zeitüberschreitung – Gerät antwortet nicht")
            except ModbusError:
                self.close()
                raise
            except (OSError, struct.error) as e:
                self.close()
                raise ModbusError(friendly(e)) from e
            self._timeouts_in_row = 0
            fc = body[0]
            if fc == (expect_fc | 0x80):
                raise ModbusException(body[1] if len(body) > 1 else 0)
            if fc != expect_fc:
                raise ModbusError(f"Unerwarteter Funktionscode {fc}")
            return body[1:]

    # ------------------------------------------------------------------
    def read_holding(self, addr, count, retries=1):
        last = None
        for attempt in range(retries + 1):
            try:
                data = self._transact(struct.pack(">BHH", 0x03, addr, count), 0x03)
                n = data[0]
                words = data[1:1 + n]
                if n != count * 2 or len(words) != n:
                    raise ModbusError(f"Antwort unvollständig ({len(words)} statt {count * 2} Bytes)")
                return list(struct.unpack(f">{count}H", words))
            except ModbusException as e:
                last = e
                if e.code == 6 and attempt < retries:
                    time.sleep(1.0)
                    continue
                raise
        raise last

    def write_single(self, addr, value):
        data = self._transact(struct.pack(">BHH", 0x06, addr, value & 0xFFFF), 0x06)
        r_addr, r_val = struct.unpack(">HH", data[:4])
        if r_addr != addr or r_val != (value & 0xFFFF):
            raise ModbusError("Schreibbestätigung passt nicht")

    def write_multiple(self, addr, words):
        n = len(words)
        pdu = struct.pack(f">BHHB{n}H", 0x10, addr, n, n * 2, *[w & 0xFFFF for w in words])
        data = self._transact(pdu, 0x10)
        r_addr, r_n = struct.unpack(">HH", data[:4])
        if r_addr != addr or r_n != n:
            raise ModbusError("Schreibbestätigung passt nicht")

    def write(self, addr, words):
        """Huawei: 1 Register -> FC 0x06, mehrere -> FC 0x10 (wie huawei-solar-lib)."""
        if len(words) == 1:
            self.write_single(addr, words[0])
        else:
            self.write_multiple(addr, words)
