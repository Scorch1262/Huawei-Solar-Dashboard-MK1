#!/usr/bin/env python3
"""Einfacher Huawei-SUN2000-Simulator (Modbus TCP) zum Testen des Dashboards
ohne echten Wechselrichter.

    python tools/huawei_simulator.py --port 5502
    python tools/huawei_simulator.py --port 5502 --ohne-akku --ohne-zaehler
    python tools/huawei_simulator.py --port 5502 --aussetzer 0.05   # langsame/fehlende Antworten
    python tools/huawei_simulator.py --port 5502 --schreibschutz    # Schreiben verweigern (0x80)

Nachgebildet wird auch die Dongle-Sperre: mehr als 6 Verbindungsaufbauten pro Minute
-> neue Verbindungen werden 2 Minuten lang abgewiesen.

Im Dashboard dann Wechselrichter = 127.0.0.1, Port 5502, Unit-ID 1 eintragen.
"""

import argparse
import math
import random
import socketserver
import struct
import threading
import time
from collections import deque


def u16(v): return [int(v) & 0xFFFF]
def i16(v): return [int(v) & 0xFFFF]
def u32(v): v = int(v) & 0xFFFFFFFF; return [v >> 16, v & 0xFFFF]
def i32(v): return u32(int(v) & 0xFFFFFFFF)
def string(s, n): b = s.encode().ljust(n * 2, b"\0"); return [int.from_bytes(b[i:i + 2], "big") for i in range(0, n * 2, 2)]


class Sim:
    def __init__(self, akku=True, zaehler=True):
        self.akku, self.zaehler = akku, zaehler
        self.soc = 55.0
        self.t0 = time.time()
        self.e_day = 3.2
        self.lock = threading.Lock()
        self.hold = {   # schreibbare Einstellungen (Rohwerte)
            47075: u32(5000), 47077: u32(5000), 47081: u16(1000), 47082: u16(50), 47083: u16(0),
            47086: u16(2), 47087: u16(0), 47088: u16(800), 47100: u16(0), 47101: u16(1000),
            47244: u32(2500), 47246: u16(0), 47247: u32(0), 47249: u32(0), 47299: u16(0),
            47415: u16(0), 47416: i32(0), 47418: i16(1000),
        }
        self.zwang_bis = 0

    def hw(self, addr, size=1):
        w = []
        for a in range(addr, addr + size):
            for base, words in self.hold.items():
                if base <= a < base + len(words):
                    w.append(words[a - base]); break
            else:
                w.append(0)
        return w[0] if size == 1 else (w[0] << 16) | w[1]

    def write(self, addr, words):
        for i, w in enumerate(words):
            a = addr + i
            for base, ws in self.hold.items():
                if base <= a < base + len(ws):
                    ws[a - base] = w; break
            else:
                return False
        if addr == 47100 and words[0] in (1, 2):
            self.zwang_bis = time.time() + (self.hw(47083) * 60 if self.hw(47246) == 0 else 86400)
        return True

    def regs(self):
        t = time.time() - self.t0
        sun = max(0.0, math.sin(t / 120.0) * 0.5 + 0.55)          # schwankt in ~12 min
        pv1_u, pv2_u = 380 + 20 * sun, 365 + 18 * sun
        pv1_i, pv2_i = 9.5 * sun + random.uniform(-.1, .1), 8.2 * sun + random.uniform(-.1, .1)
        pv = pv1_u * pv1_i + pv2_u * pv2_i
        haus = 650 + 400 * (math.sin(t / 37.0) + 1) / 2 + random.uniform(-30, 30)
        bat = 0
        if self.akku:
            surplus = pv * 0.97 - haus
            bat = max(-self.hw(47077, 2), min(self.hw(47075, 2), surplus * 0.8))
            z = self.hw(47100)
            if z and time.time() > self.zwang_bis:
                self.hold[47100] = u16(0); z = 0
            if z == 1:
                bat = self.hw(47247, 2)
                if self.hw(47246) == 1 and self.soc * 10 >= self.hw(47101): self.hold[47100] = u16(0)
            elif z == 2:
                bat = -self.hw(47249, 2)
                if self.hw(47246) == 1 and self.soc * 10 <= self.hw(47101): self.hold[47100] = u16(0)
            if self.soc * 10 >= self.hw(47081) and bat > 0: bat = 0
            if self.soc * 10 <= self.hw(47082) and bat < 0: bat = 0
            self.soc = max(0, min(100, self.soc + bat / 10000 * 0.02))
        wr = pv * 0.97 - bat
        grid = wr - haus                       # + Einspeisung
        self.e_day += max(pv, 0) / 3600000
        m = {}
        m[30000] = string("SUN2000-10K-MAP0", 15)
        m[30015] = string("HV2399999999", 10)
        m[30071] = u16(2); m[30072] = u16(2); m[30073] = u32(10000)
        m[32008] = u16(0); m[32009] = u16(0); m[32010] = u16(0)
        m[32016] = i16(pv1_u * 10); m[32017] = i16(pv1_i * 100)
        m[32018] = i16(pv2_u * 10); m[32019] = i16(pv2_i * 100)
        m[32020] = i16(0); m[32021] = i16(0); m[32022] = i16(0); m[32023] = i16(0)
        m[32064] = i32(pv)
        m[32066] = u16(4005); m[32067] = u16(4011); m[32068] = u16(3998)
        m[32069] = u16(2312); m[32070] = u16(2305); m[32071] = u16(2318)
        for k, a in ((32072, 0), (32074, 1), (32076, 2)):
            m[k] = i32(wr / 3 / 231 * 1000)
        m[32078] = i32(7420); m[32080] = i32(wr); m[32082] = i32(12)
        m[32084] = i16(999); m[32085] = u16(5001); m[32086] = u16(9812)
        m[32087] = i16(412); m[32088] = u16(3000); m[32089] = u16(0x0200 if pv > 50 else 0xA000)
        m[32106] = u32(1234567); m[32114] = u32(self.e_day * 100)
        if self.akku:
            m[37022] = i16(234); m[37046] = u32(5000); m[37048] = u32(5000)
            m[37758] = u32(10000); m[37760] = u16(self.soc * 10)
            m[37762] = u16(2); m[37763] = u16(4521); m[37764] = i16(bat / 452 * 10)
            m[37765] = i32(bat); m[37780] = u32(165432); m[37782] = u32(151234)
            m[37784] = u32(412); m[37786] = u32(377)
        if self.zaehler:
            m[37100] = u16(1)
            for k, v in ((37101, 2311), (37103, 2304), (37105, 2319)): m[k] = i32(v)
            for k in (37107, 37109, 37111): m[k] = i32(grid / 3 / 231 * 100)
            m[37113] = i32(grid); m[37115] = i32(-80); m[37117] = i16(985); m[37118] = i16(5000)
            m[37119] = i32(987654); m[37121] = i32(456789)
            for k in (37132, 37134, 37136): m[k] = i32(grid / 3)
        else:
            m[37100] = u16(0)
        if self.akku:
            m.update({k: list(v) for k, v in self.hold.items()})
        else:
            for k in (47415, 47416, 47418):
                m[k] = list(self.hold[k])
        flat = {}
        for a, words in m.items():
            for i, w in enumerate(words):
                flat[a + i] = w
        return flat

    def known(self, addr):
        if not self.akku and (37000 <= addr < 37099 or 37700 <= addr < 37800 or 47000 <= addr < 47400):
            return False
        return 30000 <= addr < 50000


class Handler(socketserver.BaseRequestHandler):
    def handle(self):
        sim = self.server.sim
        sock = self.request
        srv = self.server
        now = time.time()
        with srv.clock:
            while srv.connects and now - srv.connects[0] > 60:
                srv.connects.popleft()
            srv.connects.append(now)
            if now < srv.blocked_until or len(srv.connects) > 6:
                if now >= srv.blocked_until:
                    srv.blocked_until = now + 120
                    print(f"[Sim] zu viele Verbindungsaufbauten – sperre 120 s")
                sock.close()
                return
        print(f"[Sim] Verbindung von {self.client_address[0]}")
        while True:
            try:
                head = self._recv(7)
            except ConnectionError:
                return
            tid, proto, length, unit = struct.unpack(">HHHB", head)
            pdu = self._recv(length - 1)
            fc = pdu[0]
            r = random.random()
            if r < srv.aussetzer:
                time.sleep(srv.verzoegerung)      # Antwort kommt zu spät (Timeout beim Client)
            elif r < srv.aussetzer * 1.15:
                print("[Sim] trenne Verbindung")
                sock.close()
                return
            if unit != self.server.unit:
                resp = bytes([fc | 0x80, 0x0B])
            elif fc in (6, 16):
                if fc == 6:
                    addr, val = struct.unpack(">HH", pdu[1:5]); words = [val]
                else:
                    addr, cnt, _n = struct.unpack(">HHB", pdu[1:6]); words = list(struct.unpack(f">{cnt}H", pdu[6:6 + 2 * cnt]))
                if srv.schreibschutz:
                    resp = bytes([fc | 0x80, 0x80])
                else:
                    with sim.lock:
                        ok = sim.akku or addr >= 47415
                        ok = ok and sim.write(addr, words)
                    if not ok:
                        resp = bytes([fc | 0x80, 0x02])
                    else:
                        print(f"[Sim] geschrieben {addr} = {words}")
                        resp = pdu[:5]
            elif fc != 3:
                resp = bytes([fc | 0x80, 0x01])
            else:
                addr, cnt = struct.unpack(">HH", pdu[1:5])
                with sim.lock:
                    regs = sim.regs()
                if not all(sim.known(a) for a in range(addr, addr + cnt)):
                    resp = bytes([0x83, 0x02])
                else:
                    words = [regs.get(a, 0) for a in range(addr, addr + cnt)]
                    resp = bytes([3, cnt * 2]) + struct.pack(f">{cnt}H", *words)
            sock.sendall(struct.pack(">HHHB", tid, 0, len(resp) + 1, unit) + resp)

    def _recv(self, n):
        b = b""
        while len(b) < n:
            c = self.request.recv(n - len(b))
            if not c:
                raise ConnectionError
            b += c
        return b


class Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=5502)
    ap.add_argument("--unit", type=int, default=1)
    ap.add_argument("--ohne-akku", action="store_true")
    ap.add_argument("--ohne-zaehler", action="store_true")
    ap.add_argument("--aussetzer", type=float, default=0.0, help="Anteil verspäteter Antworten (0..1)")
    ap.add_argument("--verzoegerung", type=float, default=20.0, help="Verspätung in s")
    ap.add_argument("--schreibschutz", action="store_true")
    a = ap.parse_args()
    srv = Server(("0.0.0.0", a.port), Handler)
    srv.sim = Sim(akku=not a.ohne_akku, zaehler=not a.ohne_zaehler)
    srv.unit = a.unit
    srv.aussetzer, srv.verzoegerung, srv.schreibschutz = a.aussetzer, a.verzoegerung, a.schreibschutz
    srv.connects, srv.blocked_until, srv.clock = deque(), 0, threading.Lock()
    print(f"Simulator läuft auf Port {a.port}, Unit-ID {a.unit}")
    srv.serve_forever()
