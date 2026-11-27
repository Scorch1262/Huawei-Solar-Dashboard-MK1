"""Steuerbefehle für SUN2000 + LUNA2000.

Alle Befehle werden geprüft, dann im Abfrage-Thread (einzige Modbus-Verbindung)
geschrieben und anschließend zurückgelesen. Registeradressen/Typen wie
huawei-solar-lib 3.x (writeable=True).
"""

from .modbus import ModbusException
from .registers import BY_KEY, ARBEITSMODUS, EINSPEISE_MODUS, decode, encode


class ControlError(Exception):
    pass


ERLAUBTE_MODI = (0, 1, 2, 4, 5)       # 3 (LG-Akku) und 6 (Fremdsteuerung) nicht anbieten


def _num(params, name, lo, hi, label, integer=True):
    try:
        v = float(params.get(name))
    except (TypeError, ValueError):
        raise ControlError(f"{label}: keine gültige Zahl")
    if not lo <= v <= hi:
        raise ControlError(f"{label}: erlaubt {lo:g} bis {hi:g}")
    return int(round(v)) if integer else round(v, 1)


def _power_cap(values, key_max):
    cap = values.get(key_max)
    return int(cap) if cap and cap > 0 else 25000


def plan(action, params, values):
    """Liefert (Beschreibung, [(reg_key, wert), ...]) – noch ohne zu schreiben."""
    soc = values.get("akku_soc")
    if action == "modus":
        m = _num(params, "wert", 0, 6, "Arbeitsmodus")
        if m not in ERLAUBTE_MODI:
            raise ControlError("Dieser Arbeitsmodus wird nicht unterstützt")
        return f"Arbeitsmodus: {ARBEITSMODUS[m]}", [("st_modus", m)]
    if action == "max_laden":
        cap = _power_cap(values, "akku_max_laden")
        w = _num(params, "wert", 0, cap, "Max. Ladeleistung")
        return f"Max. Ladeleistung: {w} W", [("st_max_laden", w)]
    if action == "max_entladen":
        cap = _power_cap(values, "akku_max_entladen")
        w = _num(params, "wert", 0, cap, "Max. Entladeleistung")
        return f"Max. Entladeleistung: {w} W", [("st_max_entladen", w)]
    if action == "ladeschluss":
        v = _num(params, "wert", 90, 100, "Ladeschluss-SOC", integer=False)
        return f"Ladeschluss-SOC: {v:g} %", [("st_ladeschluss", v)]
    if action == "entladeschluss":
        v = _num(params, "wert", 0, 20, "Entladeschluss-SOC", integer=False)
        return f"Entladeschluss-SOC: {v:g} %", [("st_entladeschluss", v)]
    if action == "netzladen":
        on = bool(params.get("wert"))
        return f"Laden aus dem Netz: {'an' if on else 'aus'}", [("st_netzladen", 1 if on else 0)]
    if action == "netzladen_soc":
        v = _num(params, "wert", 20, 100, "Netzladen bis SOC", integer=False)
        return f"Netzladen bis SOC: {v:g} %", [("st_netzladen_soc", v)]
    if action == "netzladen_leistung":
        cap = _power_cap(values, "akku_max_laden")
        w = _num(params, "wert", 0, cap, "Max. Netzladeleistung")
        return f"Max. Netzladeleistung: {w} W", [("st_netzladen_leistung", w)]
    if action == "pv_tou":
        v = _num(params, "wert", 0, 1, "PV-Überschuss im Zeitmodus")
        return ("PV-Überschuss im Zeitmodus: " + ("Akku laden" if v else "einspeisen")), [("st_pv_tou", v)]
    if action == "zwang_start":
        art = params.get("art")
        if art not in ("laden", "entladen"):
            raise ControlError("Art muss 'laden' oder 'entladen' sein")
        key_max = "akku_max_laden" if art == "laden" else "akku_max_entladen"
        w = _num(params, "leistung", 100, _power_cap(values, key_max), "Leistung")
        vorgabe = params.get("vorgabe")
        writes = []
        if vorgabe == "dauer":
            d = _num(params, "dauer", 1, 1440, "Dauer (min)")
            writes.append(("st_zwang_modus", 0))
            ziel = f"{d} min"
        elif vorgabe == "soc":
            z = _num(params, "ziel_soc", 12, 100, "Ziel-SOC")
            if soc is not None and art == "laden" and z <= soc:
                raise ControlError(f"Ziel-SOC muss über dem aktuellen SOC ({soc:g} %) liegen")
            if soc is not None and art == "entladen" and z >= soc:
                raise ControlError(f"Ziel-SOC muss unter dem aktuellen SOC ({soc:g} %) liegen")
            writes.append(("st_zwang_modus", 1))
            ziel = f"bis {z} %"
        else:
            raise ControlError("Vorgabe muss 'dauer' oder 'soc' sein")
        writes.append(("st_zwang_ladeleistung" if art == "laden" else "st_zwang_entladeleistung", w))
        if vorgabe == "dauer":
            writes.append(("st_zwang_dauer", d))
        else:
            writes.append(("st_zwang_soc", z))
        writes.append(("st_zwang", 1 if art == "laden" else 2))      # zuletzt: startet den Vorgang
        return f"Zwangs{art} mit {w} W, {ziel}", writes
    if action == "zwang_stop":
        return "Zwangsladen/-entladen beenden", [("st_zwang", 0)]
    if action == "einspeisung":
        m = _num(params, "modus", 0, 7, "Wirkleistungsregelung")
        if m not in (0, 5, 6, 7):
            raise ControlError("Diese Regelungsart wird nicht unterstützt")
        writes = []
        txt = EINSPEISE_MODUS[m]
        if m == 6:
            w = _num(params, "max_w", 0, 100000, "Max. Einspeiseleistung (W)")
            writes.append(("st_einspeise_w", w))
            txt += f" auf {w} W"
        if m == 7:
            p = _num(params, "max_pct", 0, 100, "Max. Einspeiseleistung (%)", integer=False)
            writes.append(("st_einspeise_pct", p))
            txt += f" auf {p:g} %"
        writes.append(("st_einspeise_modus", m))
        return f"Wirkleistungsregelung: {txt}", writes
    raise ControlError("Unbekannte Aktion")


def make_executor(writes):
    """Erzeugt die Funktion, die im Abfrage-Thread schreibt und zurückliest."""

    def run(client):
        result = []
        for key, value in writes:
            reg = BY_KEY[key]
            words = encode(reg, value)
            try:
                client.write(reg.addr, words)
            except ModbusException as e:
                if e.code in (0x80, 2):
                    raise ControlError(
                        f"Keine Schreibberechtigung für {reg.label} (Register {reg.addr}). "
                        "Schreiben ist meist nur über den SDongle bzw. mit freigegebenem "
                        "Modbus TCP (uneingeschränkt) möglich.") from e
                if e.code == 3:
                    raise ControlError(f"{reg.label}: Wert {value} wird vom Wechselrichter abgelehnt") from e
                raise
            try:
                back = decode(reg, client.read_holding(reg.addr, reg.size))
            except ModbusException:
                back = None
            result.append({"register": reg.addr, "bezeichnung": reg.label, "geschrieben": value,
                           "gelesen": back,
                           "ok": back is None or abs(float(back) - float(value)) <= 1 / reg.gain + 1e-9})
        return result

    return run
