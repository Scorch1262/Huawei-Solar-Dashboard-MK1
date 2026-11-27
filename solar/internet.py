"""Abrufe aus dem Internet (nur Standardbibliothek).

- EPEX Day-Ahead-Preis: Energy-Charts (Fraunhofer ISE, CC BY 4.0),
  Ersatz für DE-LU/AT: aWATTar
- PV-Prognose: Open-Meteo, Einstrahlung auf die geneigte Modulfläche (GTI)
- Ortssuche: Open-Meteo Geocoding

Für Tests ohne Internet lassen sich die Adressen per Umgebungsvariable umleiten:
HSD_URL_ENERGYCHARTS, HSD_URL_AWATTAR_DE, HSD_URL_AWATTAR_AT, HSD_URL_OPENMETEO, HSD_URL_GEOCODING
"""

import email.utils
import json
import os
import time
import urllib.parse
import urllib.request

UA = "Huawei-Solar-Dashboard-MK1 (privat, Heimnetz)"

URL_ENERGYCHARTS = os.environ.get("HSD_URL_ENERGYCHARTS", "https://api.energy-charts.info/price")
URL_AWATTAR = {
    "DE-LU": os.environ.get("HSD_URL_AWATTAR_DE", "https://api.awattar.de/v1/marketdata"),
    "AT": os.environ.get("HSD_URL_AWATTAR_AT", "https://api.awattar.at/v1/marketdata"),
}
URL_OPENMETEO = os.environ.get("HSD_URL_OPENMETEO", "https://api.open-meteo.com/v1/forecast")
URL_GEOCODING = os.environ.get("HSD_URL_GEOCODING", "https://geocoding-api.open-meteo.com/v1/search")

ZONEN = {"DE-LU": "Deutschland/Luxemburg", "AT": "Österreich", "CH": "Schweiz", "NL": "Niederlande",
         "BE": "Belgien", "FR": "Frankreich", "CZ": "Tschechien", "PL": "Polen", "DK1": "Dänemark West",
         "DK2": "Dänemark Ost"}


class FetchError(Exception):
    pass


# Uhrzeit-Kontrolle: Abweichung der PC-Uhr zur Serverzeit (aus dem HTTP-Date-Kopf)
CLOCK = {"abweichung_s": None, "zeit": 0}


def _note_server_time(headers):
    try:
        d = headers.get("Date")
        if d:
            server = email.utils.parsedate_to_datetime(d).timestamp()
            CLOCK["abweichung_s"] = round(time.time() - server, 1)
            CLOCK["zeit"] = time.time()
    except (TypeError, ValueError, OverflowError):
        pass


def get_json(url, params=None, timeout=20):
    if params:
        url += ("&" if "?" in url else "?") + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            _note_server_time(r.headers)
            return json.loads(r.read(5_000_000).decode("utf-8"))
    except Exception as e:  # noqa: BLE001
        raise FetchError(f"{urllib.parse.urlsplit(url).netloc}: {e}") from e


def _day(ts):
    return time.strftime("%Y-%m-%d", time.localtime(ts))


# --------------------------------------------------------------------------
def check_price_slots(slots):
    """Plausibilitätsprüfung. Wirft FetchError, wenn die Daten nicht vertrauenswürdig sind."""
    if not slots:
        raise FetchError("keine Preisdaten")
    last_end = None
    for s, e, v in slots:
        if not (e > s and 300 <= e - s <= 3600):
            raise FetchError("unplausible Zeitraster in den Preisdaten")
        if last_end is not None and s < last_end:
            raise FetchError("Preisdaten überlappen sich")
        if not -1000.0 <= v <= 5000.0:            # EUR/MWh; Börsenlimits liegen in diesem Bereich
            raise FetchError(f"unplausibler Preis {v} EUR/MWh")
        last_end = e
    return slots


def check_pv_slots(slots):
    for s, e, g in slots:
        if e - s != 3600 or not 0.0 <= g <= 1500.0:
            raise FetchError("unplausible Strahlungswerte")
    return slots


def fetch_prices(zone="DE-LU"):
    """Liefert (quelle, [(start, ende, eur_mwh), ...]) für heute und – falls schon
    veröffentlicht – morgen. Zeitstempel in Unix-Sekunden."""
    now = time.time()
    err = None
    try:
        d = get_json(URL_ENERGYCHARTS, {"bzn": zone, "start": _day(now - 3600), "end": _day(now + 2 * 86400)})
        ts, pr = d.get("unix_seconds") or [], d.get("price") or []
        if ts and len(ts) == len(pr):
            slots = []
            for i, t in enumerate(ts):
                if pr[i] is None:
                    continue
                end = ts[i + 1] if i + 1 < len(ts) else t + (ts[i] - ts[i - 1] if i else 3600)
                slots.append((int(t), int(end), float(pr[i])))
            if slots:
                return "Energy-Charts", check_price_slots(slots)
        err = "Energy-Charts: keine Preisdaten"
    except FetchError as e:
        err = str(e)
    if zone in URL_AWATTAR:
        try:
            start_ms = int((now - 3600) // 3600 * 3600 * 1000)
            d = get_json(URL_AWATTAR[zone], {"start": start_ms, "end": start_ms + 3 * 86400 * 1000})
            slots = [(int(x["start_timestamp"] // 1000), int(x["end_timestamp"] // 1000), float(x["marketprice"]))
                     for x in d.get("data", []) if x.get("marketprice") is not None]
            if slots:
                return "aWATTar", check_price_slots(slots)
            err += " / aWATTar: keine Preisdaten"
        except (FetchError, KeyError, TypeError, ValueError) as e:
            err += f" / aWATTar: {e}"
    raise FetchError(err)


def fetch_pv_forecast(lat, lon, tilt, azimuth):
    """Open-Meteo: Einstrahlung auf die Modulfläche je Stunde.
    Liefert [(start, ende, w_m2)]. Open-Meteo mittelt über die VORANGEGANGENE Stunde,
    der Wert mit Zeitstempel T gilt also für [T-1h, T]."""
    d = get_json(URL_OPENMETEO, {
        "latitude": f"{lat:.4f}", "longitude": f"{lon:.4f}",
        "hourly": "global_tilted_irradiance", "tilt": int(tilt), "azimuth": int(azimuth),
        "forecast_days": 3, "past_days": 1, "timeformat": "unixtime", "timezone": "auto"})
    h = d.get("hourly") or {}
    ts, gti = h.get("time") or [], h.get("global_tilted_irradiance") or []
    if not ts or len(ts) != len(gti):
        raise FetchError("Open-Meteo: keine Strahlungsdaten")
    return check_pv_slots([(int(t) - 3600, int(t), float(g)) for t, g in zip(ts, gti) if g is not None])


def geocode(name):
    d = get_json(URL_GEOCODING, {"name": name, "count": 8, "language": "de", "format": "json"})
    out = []
    for r in d.get("results") or []:
        parts = [r.get("name"), r.get("postcodes", [None])[0] if r.get("postcodes") else None,
                 r.get("admin1"), r.get("country")]
        out.append({"name": r.get("name"), "beschreibung": ", ".join(p for p in parts if p),
                    "lat": r.get("latitude"), "lon": r.get("longitude")})
    return out
