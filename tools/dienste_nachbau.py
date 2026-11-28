#!/usr/bin/env python3
"""Nachbau der Internetdienste (Energy-Charts, aWATTar, Open-Meteo) für Tests ohne Internet.

    python tools/dienste_nachbau.py 9911 [--kein-pv] [--ec-aus]

Dashboard dann mit Umgebungsvariablen starten:
    HSD_URL_ENERGYCHARTS=http://127.0.0.1:9911/price
    HSD_URL_AWATTAR_DE=http://127.0.0.1:9911/awattar
    HSD_URL_OPENMETEO=http://127.0.0.1:9911/forecast
    HSD_URL_GEOCODING=http://127.0.0.1:9911/search
Szenario: jetzt und die nächsten 2 h günstig (4 ct), in 2–7 h viel Sonne, nachts günstig, morgen trüb.
"""
import json, math, time, sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs
FAIL_EC = "--ec-aus" in sys.argv
KEIN_PV = "--kein-pv" in sys.argv
def day0():
    lt=time.localtime(); return int(time.mktime((lt.tm_year,lt.tm_mon,lt.tm_mday,0,0,0,0,0,-1)))
def price(t):
    now=time.time(); h=time.localtime(t).tm_hour
    if now-1800 <= t < now+2*3600: return 40.0          # jetzt: günstig (4 ct)
    if 1 <= h < 5 and t > now: return 55.0              # nachts günstig
    return 180.0 + 60*math.sin(t/7000)
def gti(t):
    if KEIN_PV: return 0.0
    now=time.time()
    if now+2*3600 <= t < now+7*3600: return 750.0       # in 2-7 h viel Sonne
    lt=time.localtime(t)
    if t > day0()+86400 and 8 <= lt.tm_hour <= 16: return 90.0   # morgen trüb
    return 0.0
class H(BaseHTTPRequestHandler):
    def log_message(self,*a): pass
    def send(self, obj, code=200):
        b=json.dumps(obj).encode(); self.send_response(code); self.send_header("Content-Type","application/json"); self.send_header("Content-Length",str(len(b))); self.end_headers(); self.wfile.write(b)
    def do_GET(self):
        u=urlparse(self.path); q=parse_qs(u.query)
        if u.path=="/price":
            if FAIL_EC: return self.send({"detail":"down"},503)
            d=day0()-86400; ts=list(range(d, d+3*86400, 900))     # ab gestern (wie die echte Abfrage)
            return self.send({"license_info":"CC BY 4.0","unix_seconds":ts,"price":[round(price(t+450),2) for t in ts],"unit":"EUR / MWh","deprecated":False})
        if u.path=="/awattar":
            d=day0()*1000; return self.send({"object":"list","data":[{"start_timestamp":d+i*3600000,"end_timestamp":d+(i+1)*3600000,"marketprice":price((d+i*3600000)/1000+1800),"unit":"Eur/MWh"} for i in range(48)]})
        if u.path=="/forecast":
            d=day0()-86400; ts=list(range(d+3600, d+4*86400+1, 3600))
            return self.send({"hourly":{"time":ts,"global_tilted_irradiance":[gti(t-1800) for t in ts]}})
        if u.path=="/search":
            return self.send({"results":[{"name":"Musterstadt","latitude":51.5,"longitude":7.46,"admin1":"Nordrhein-Westfalen","country":"Deutschland","postcodes":["44135"]}]})
        self.send({"err":"404"},404)
ThreadingHTTPServer(("127.0.0.1",int(sys.argv[1])),H).serve_forever()
