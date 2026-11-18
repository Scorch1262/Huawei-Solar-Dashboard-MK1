"""Schlanker Modbus-TCP-Client (nur Funktion 0x03) speziell für Huawei SUN2000.

Besonderheiten Huawei:
- Nach dem Verbindungsaufbau braucht der Wechselrichter/SDongle eine kurze Pause,
  bevor er die erste Anfrage beantwortet (Standard 1,5 s).
- Es wird nur EIN Modbus-TCP-Client gleichzeitig zuverlässig bedient.
  Die Verbindung bleibt deshalb dauerhaft offen.
- Ausnahme 0x06 ("Slave busy") -> kurz warten und wiederholen.
"""

import socket
import struct
import threading
import time


class ModbusError(Exception):
    pass


def friendly(e):
    """Netzwerkfehler in verständliche deutsche Meldungen übersetzen."""
    if isinstance(e, ConnectionRefusedError):
        return "Verbindung abgelehnt – Adresse/Port prüfen und Modbus TCP im Wechselrichter freigeben"
    if isinstance(e, (socket.timeout, TimeoutError)):
        return "Zeitüberschreitung – Gerät antwortet nicht"
    if isinstance(e, ConnectionResetError):
        return "Verbindung vom Gerät zurückgesetzt (anderer Modbus-Client aktiv?)"
    if isinstance(e, socket.gaierror):
        return "Hostname nicht auflösbar"
    if isinstance(e, OSError) and e.errno in (101, 113, 10051, 10065):
        return "Netzwerk/Gerät nicht erreichbar"
    return str(e) or e.__class__.__name__


class ModbusException(ModbusError):
    """Der Wechselrichter hat mit einem Modbus-Ausnahmecode geantwortet."""

    TEXT = {
        1: "Ungültige Funktion",
        2: "Ungültige Registeradresse",
        3: "Ungültiger Datenwert",
        4: "Gerätefehler",
        6: "Gerät beschäftigt",
        0x0B: "Zielgerät antwortet nicht (Unit-ID prüfen)",
    }

    def __init__(self, code):
        self.code = code
        super().__init__(f"Modbus-Ausnahme {code}: {self.TEXT.get(code, 'unbekannt')}")


class ModbusTcpClient:
    def __init__(self, host, port=502, unit=1, timeout=5.0, connect_delay=1.5, request_gap=0.05):
        self.host = host
        self.port = int(port)
        self.unit = int(unit)
        self.timeout = float(timeout)
        self.connect_delay = float(connect_delay)
        self.request_gap = float(request_gap)
        self._sock = None
        self._tid = 0
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    def connect(self):
        self.close()
        s = socket.create_connection((self.host, self.port), timeout=self.timeout)
        s.settimeout(self.timeout)
        s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self._sock = s
        if self.connect_delay > 0:
            time.sleep(self.connect_delay)

    def close(self):
        if self._sock is not None:
            try:
                self._sock.close()
            except OSError:
                pass
        self._sock = None

    @property
    def connected(self):
        return self._sock is not None

    # ------------------------------------------------------------------
    def _recv_exact(self, n):
        buf = b""
        while len(buf) < n:
            chunk = self._sock.recv(n - len(buf))
            if not chunk:
                raise ModbusError("Verbindung vom Wechselrichter geschlossen")
            buf += chunk
        return buf

    def read_holding(self, addr, count, retries=2):
        with self._lock:
            last = None
            for attempt in range(retries + 1):
                try:
                    if self._sock is None:
                        self.connect()
                    return self._read(addr, count)
                except ModbusException as e:
                    last = e
                    if e.code == 6 and attempt < retries:
                        time.sleep(1.0)
                        continue
                    raise
                except (OSError, ModbusError) as e:
                    last = e
                    self.close()
                    if attempt < retries:
                        time.sleep(0.5)
                        continue
                    raise ModbusError(friendly(e)) from e
            raise ModbusError(str(last))

    def _read(self, addr, count):
        self._tid = (self._tid + 1) & 0xFFFF
        tid = self._tid
        pdu = struct.pack(">BHH", 0x03, addr, count)
        mbap = struct.pack(">HHHB", tid, 0, len(pdu) + 1, self.unit)
        if self.request_gap:
            time.sleep(self.request_gap)
        self._sock.sendall(mbap + pdu)
        # Antworten mit falscher Transaktions-ID (Altlasten) überspringen
        for _ in range(5):
            head = self._recv_exact(7)
            rtid, proto, length, unit = struct.unpack(">HHHB", head)
            if length < 2 or length > 260:
                raise ModbusError(f"Ungültige Antwortlänge {length}")
            body = self._recv_exact(length - 1)
            if rtid != tid:
                continue
            fc = body[0]
            if fc == 0x83:
                raise ModbusException(body[1])
            if fc != 0x03:
                raise ModbusError(f"Unerwarteter Funktionscode {fc}")
            n = body[1]
            data = body[2:2 + n]
            if n != count * 2 or len(data) != n:
                raise ModbusError(f"Antwort unvollständig ({len(data)} statt {count * 2} Bytes)")
            return list(struct.unpack(f">{count}H", data))
        raise ModbusError("Keine passende Antwort erhalten")
