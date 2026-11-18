"""Registertabelle Huawei SUN2000-(5-12)K-MAP0 mit LUNA2000-Akku und Smart Meter.

Quelle der Adressen: Huawei "Solar Inverter Modbus Interface Definitions"
(gleiche Adressen wie in der verbreiteten huawei-solar-lib).

Jeder Eintrag:
    key, Adresse, Typ, Faktor (Rohwert / Faktor), Einheit, Bezeichnung, Gruppe, MQTT-Topic
Typen: U16, I16, U32, I32, STR<n> (n = Anzahl Register)
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Reg:
    key: str
    addr: int
    typ: str
    gain: float
    unit: str
    label: str
    group: str
    topic: str

    @property
    def size(self) -> int:
        if self.typ in ("U16", "I16"):
            return 1
        if self.typ in ("U32", "I32"):
            return 2
        if self.typ.startswith("STR"):
            return int(self.typ[3:])
        raise ValueError(self.typ)


R = Reg
REGISTERS = [
    # ---------------- Gerät (nur einmal beim Verbinden gelesen) -----------
    R("modell", 30000, "STR15", 1, "", "Modell", "geraet", "geraet/modell"),
    R("seriennummer", 30015, "STR10", 1, "", "Seriennummer", "geraet", "geraet/seriennummer"),
    R("pv_strings", 30071, "U16", 1, "", "Anzahl PV-Strings", "geraet", "geraet/pv_strings"),
    R("mpp_tracker", 30072, "U16", 1, "", "Anzahl MPP-Tracker", "geraet", "geraet/mpp_tracker"),
    R("nennleistung", 30073, "U32", 1, "W", "Nennleistung", "geraet", "geraet/nennleistung_w"),

    # ---------------- PV-Strings ------------------------------------------
    R("pv1_u", 32016, "I16", 10, "V", "String 1 Spannung", "pv", "pv/string1/spannung_v"),
    R("pv1_i", 32017, "I16", 100, "A", "String 1 Strom", "pv", "pv/string1/strom_a"),
    R("pv2_u", 32018, "I16", 10, "V", "String 2 Spannung", "pv", "pv/string2/spannung_v"),
    R("pv2_i", 32019, "I16", 100, "A", "String 2 Strom", "pv", "pv/string2/strom_a"),
    R("pv3_u", 32020, "I16", 10, "V", "String 3 Spannung", "pv", "pv/string3/spannung_v"),
    R("pv3_i", 32021, "I16", 100, "A", "String 3 Strom", "pv", "pv/string3/strom_a"),
    R("pv4_u", 32022, "I16", 10, "V", "String 4 Spannung", "pv", "pv/string4/spannung_v"),
    R("pv4_i", 32023, "I16", 100, "A", "String 4 Strom", "pv", "pv/string4/strom_a"),

    # ---------------- Wechselrichter --------------------------------------
    R("alarm1", 32008, "U16", 1, "", "Alarm 1 (Bitfeld)", "wr", "wechselrichter/alarm1"),
    R("alarm2", 32009, "U16", 1, "", "Alarm 2 (Bitfeld)", "wr", "wechselrichter/alarm2"),
    R("alarm3", 32010, "U16", 1, "", "Alarm 3 (Bitfeld)", "wr", "wechselrichter/alarm3"),
    R("pv_leistung", 32064, "I32", 1, "W", "PV-Eingangsleistung", "pv", "pv/leistung_w"),
    R("u_l1l2", 32066, "U16", 10, "V", "Spannung L1-L2", "wr", "wechselrichter/spannung_l1_l2_v"),
    R("u_l2l3", 32067, "U16", 10, "V", "Spannung L2-L3", "wr", "wechselrichter/spannung_l2_l3_v"),
    R("u_l3l1", 32068, "U16", 10, "V", "Spannung L3-L1", "wr", "wechselrichter/spannung_l3_l1_v"),
    R("u_l1", 32069, "U16", 10, "V", "Spannung L1", "wr", "wechselrichter/spannung_l1_v"),
    R("u_l2", 32070, "U16", 10, "V", "Spannung L2", "wr", "wechselrichter/spannung_l2_v"),
    R("u_l3", 32071, "U16", 10, "V", "Spannung L3", "wr", "wechselrichter/spannung_l3_v"),
    R("i_l1", 32072, "I32", 1000, "A", "Strom L1", "wr", "wechselrichter/strom_l1_a"),
    R("i_l2", 32074, "I32", 1000, "A", "Strom L2", "wr", "wechselrichter/strom_l2_a"),
    R("i_l3", 32076, "I32", 1000, "A", "Strom L3", "wr", "wechselrichter/strom_l3_a"),
    R("spitze_heute", 32078, "I32", 1, "W", "Spitzenleistung heute", "wr", "wechselrichter/spitzenleistung_heute_w"),
    R("wr_leistung", 32080, "I32", 1, "W", "Ausgangsleistung (Wirkleistung)", "wr", "wechselrichter/leistung_w"),
    R("wr_blind", 32082, "I32", 1, "var", "Blindleistung", "wr", "wechselrichter/blindleistung_var"),
    R("wr_pf", 32084, "I16", 1000, "", "Leistungsfaktor", "wr", "wechselrichter/leistungsfaktor"),
    R("wr_freq", 32085, "U16", 100, "Hz", "Netzfrequenz", "wr", "wechselrichter/frequenz_hz"),
    R("wr_eff", 32086, "U16", 100, "%", "Wirkungsgrad", "wr", "wechselrichter/wirkungsgrad_pct"),
    R("wr_temp", 32087, "I16", 10, "°C", "Innentemperatur", "wr", "wechselrichter/temperatur_c"),
    R("wr_iso", 32088, "U16", 1000, "MΩ", "Isolationswiderstand", "wr", "wechselrichter/isolation_mohm"),
    R("wr_status", 32089, "U16", 1, "", "Gerätestatus (Code)", "wr", "wechselrichter/status_code"),
    R("ertrag_gesamt", 32106, "U32", 100, "kWh", "Gesamtertrag", "wr", "wechselrichter/ertrag_gesamt_kwh"),
    R("ertrag_heute", 32114, "U32", 100, "kWh", "Tagesertrag", "wr", "wechselrichter/ertrag_heute_kwh"),

    # ---------------- Akku (LUNA2000, Summe aller Akkus) ------------------
    R("akku_temp", 37022, "I16", 10, "°C", "Akkutemperatur (Einheit 1)", "akku", "akku/temperatur_c"),
    R("akku_max_laden", 37046, "U32", 1, "W", "Max. Ladeleistung", "akku", "akku/max_ladeleistung_w"),
    R("akku_max_entladen", 37048, "U32", 1, "W", "Max. Entladeleistung", "akku", "akku/max_entladeleistung_w"),
    R("akku_kapazitaet", 37758, "U32", 1, "Wh", "Nennkapazität", "akku", "akku/kapazitaet_wh"),
    R("akku_soc", 37760, "U16", 10, "%", "Ladezustand (SOC)", "akku", "akku/soc_pct"),
    R("akku_status", 37762, "U16", 1, "", "Betriebsstatus (Code)", "akku", "akku/status_code"),
    R("akku_bus_u", 37763, "U16", 10, "V", "Bus-Spannung", "akku", "akku/bus_spannung_v"),
    R("akku_bus_i", 37764, "I16", 10, "A", "Bus-Strom", "akku", "akku/bus_strom_a"),
    R("akku_leistung", 37765, "I32", 1, "W", "Lade-/Entladeleistung (+ laden)", "akku", "akku/leistung_w"),
    R("akku_geladen_gesamt", 37780, "U32", 100, "kWh", "Gesamt geladen", "akku", "akku/geladen_gesamt_kwh"),
    R("akku_entladen_gesamt", 37782, "U32", 100, "kWh", "Gesamt entladen", "akku", "akku/entladen_gesamt_kwh"),
    R("akku_geladen_heute", 37784, "U32", 100, "kWh", "Heute geladen", "akku", "akku/geladen_heute_kwh"),
    R("akku_entladen_heute", 37786, "U32", 100, "kWh", "Heute entladen", "akku", "akku/entladen_heute_kwh"),

    # ---------------- Netz (Smart Meter DTSU666-H / DDSU666-H) -----------
    R("zaehler_status", 37100, "U16", 1, "", "Zählerstatus (1 = normal)", "netz", "netz/zaehler_status"),
    R("netz_u_l1", 37101, "I32", 10, "V", "Spannung L1", "netz", "netz/spannung_l1_v"),
    R("netz_u_l2", 37103, "I32", 10, "V", "Spannung L2", "netz", "netz/spannung_l2_v"),
    R("netz_u_l3", 37105, "I32", 10, "V", "Spannung L3", "netz", "netz/spannung_l3_v"),
    R("netz_i_l1", 37107, "I32", 100, "A", "Strom L1", "netz", "netz/strom_l1_a"),
    R("netz_i_l2", 37109, "I32", 100, "A", "Strom L2", "netz", "netz/strom_l2_a"),
    R("netz_i_l3", 37111, "I32", 100, "A", "Strom L3", "netz", "netz/strom_l3_a"),
    R("netz_leistung", 37113, "I32", 1, "W", "Netzleistung (+ Einspeisung)", "netz", "netz/leistung_w"),
    R("netz_blind", 37115, "I32", 1, "var", "Blindleistung", "netz", "netz/blindleistung_var"),
    R("netz_pf", 37117, "I16", 1000, "", "Leistungsfaktor", "netz", "netz/leistungsfaktor"),
    R("netz_freq", 37118, "I16", 100, "Hz", "Frequenz", "netz", "netz/frequenz_hz"),
    R("netz_eingespeist", 37119, "I32", 100, "kWh", "Eingespeist gesamt", "netz", "netz/eingespeist_gesamt_kwh"),
    R("netz_bezogen", 37121, "I32", 100, "kWh", "Bezogen gesamt", "netz", "netz/bezogen_gesamt_kwh"),
    R("netz_p_l1", 37132, "I32", 1, "W", "Leistung L1", "netz", "netz/leistung_l1_w"),
    R("netz_p_l2", 37134, "I32", 1, "W", "Leistung L2", "netz", "netz/leistung_l2_w"),
    R("netz_p_l3", 37136, "I32", 1, "W", "Leistung L3", "netz", "netz/leistung_l3_w"),
]

BY_KEY = {r.key: r for r in REGISTERS}
STATIC_GROUPS = {"geraet"}

# Berechnete Werte (kein eigenes Register) – werden nach jedem Lesezyklus gebildet
DERIVED = [
    # key, Einheit, Bezeichnung, Gruppe, Topic
    ("pv1_p", "W", "String 1 Leistung", "pv", "pv/string1/leistung_w"),
    ("pv2_p", "W", "String 2 Leistung", "pv", "pv/string2/leistung_w"),
    ("pv3_p", "W", "String 3 Leistung", "pv", "pv/string3/leistung_w"),
    ("pv4_p", "W", "String 4 Leistung", "pv", "pv/string4/leistung_w"),
    ("wr_status_text", "", "Gerätestatus", "wr", "wechselrichter/status"),
    ("akku_status_text", "", "Betriebsstatus", "akku", "akku/status"),
    ("akku_laden", "W", "Ladeleistung", "akku", "akku/ladeleistung_w"),
    ("akku_entladen", "W", "Entladeleistung", "akku", "akku/entladeleistung_w"),
    ("netz_bezug", "W", "Bezug aus dem Netz", "netz", "netz/bezug_w"),
    ("netz_einspeisung", "W", "Einspeisung ins Netz", "netz", "netz/einspeisung_w"),
    ("haus_verbrauch", "W", "Hausverbrauch", "haus", "haus/verbrauch_w"),
    ("eigenverbrauch_pct", "%", "Eigenverbrauchsquote (aktuell)", "haus", "haus/eigenverbrauch_pct"),
    ("autarkie_pct", "%", "Autarkiegrad (aktuell)", "haus", "haus/autarkie_pct"),
]

WR_STATUS = {
    0x0000: "Standby: Initialisierung",
    0x0001: "Standby: Isolationsprüfung",
    0x0002: "Standby: Einstrahlungsprüfung",
    0x0003: "Standby: Netzprüfung",
    0x0100: "Start",
    0x0200: "Am Netz",
    0x0201: "Am Netz: Leistung begrenzt",
    0x0202: "Am Netz: Selbst-Derating",
    0x0203: "Inselbetrieb",
    0x0300: "Abgeschaltet: Fehler",
    0x0301: "Abgeschaltet: Befehl",
    0x0302: "Abgeschaltet: OVGR",
    0x0303: "Abgeschaltet: Kommunikation getrennt",
    0x0304: "Abgeschaltet: Leistung begrenzt",
    0x0305: "Abgeschaltet: manueller Start nötig",
    0x0306: "Abgeschaltet: DC-Schalter aus",
    0x0307: "Abgeschaltet: Schnellabschaltung",
    0x0308: "Abgeschaltet: Eingangsleistung zu gering",
    0x0401: "Netzsteuerung: cos φ-P-Kurve",
    0x0402: "Netzsteuerung: Q-U-Kurve",
    0x0403: "Netzsteuerung: PF-U-Kurve",
    0x0404: "Netzsteuerung: Trockenkontakt",
    0x0405: "Netzsteuerung: Q-P-Kurve",
    0x0500: "Stichprobe bereit",
    0x0501: "Stichprobe läuft",
    0x0600: "Inspektion",
    0x0700: "AFCI-Selbsttest",
    0x0800: "I-U-Kennlinien-Scan",
    0x0900: "DC-Eingangserkennung",
    0x0A00: "Inselbetrieb: Laden",
    0xA000: "Standby: keine Einstrahlung",
}

AKKU_STATUS = {0: "Offline", 1: "Standby", 2: "In Betrieb", 3: "Fehler", 4: "Ruhemodus"}


def build_blocks(regs, max_span=60):
    """Fasst nahe beieinanderliegende Register zu Leseblöcken zusammen."""
    regs = sorted(regs, key=lambda r: r.addr)
    blocks = []
    cur = []
    start = end = None
    for r in regs:
        if cur and (r.addr - end > 8 or r.addr + r.size - start > max_span):
            blocks.append((start, end - start, cur))
            cur = []
        if not cur:
            start = r.addr
            end = r.addr
        cur.append(r)
        end = max(end, r.addr + r.size)
    if cur:
        blocks.append((start, end - start, cur))
    return blocks


def decode(reg: Reg, words):
    """Wandelt Register-Rohdaten in einen Wert um. Ungültige Markerwerte -> None."""
    t = reg.typ
    if t == "U16":
        raw = words[0]
        if raw == 0xFFFF:
            return None
    elif t == "I16":
        raw = words[0]
        if raw == 0x7FFF:
            return None
        if raw >= 0x8000:
            raw -= 0x10000
    elif t == "U32":
        raw = (words[0] << 16) | words[1]
        if raw == 0xFFFFFFFF:
            return None
    elif t == "I32":
        raw = (words[0] << 16) | words[1]
        if raw == 0x7FFFFFFF:
            return None
        if raw >= 0x80000000:
            raw -= 0x100000000
    elif t.startswith("STR"):
        b = b"".join(w.to_bytes(2, "big") for w in words)
        return b.split(b"\x00", 1)[0].decode("ascii", "replace").strip() or None
    else:
        return None
    if reg.gain == 1:
        return raw
    val = raw / reg.gain
    digits = len(str(int(reg.gain))) - 1
    return round(val, digits)
