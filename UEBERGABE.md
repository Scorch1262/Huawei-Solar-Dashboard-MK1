# Übergabe – Huawei-Solar-Dashboard-MK1

Technische Notizen für die Weiterentwicklung.

## Aufbau
- **Keine Fremdpakete.** Modbus-TCP-Client (`solar/modbus.py`) und MQTT-3.1.1-Client (`solar/mqtt.py`, nur QoS 0 senden) sind selbst geschrieben. Dadurch baut PyInstaller ohne Zusatzoptionen und das Programm läuft auch auf Routern/Raspberry Pi mit nacktem `python3`.
- Webserver: `http.server.ThreadingHTTPServer` auf `0.0.0.0`. Portwechsel: neuer Server startet, alter wird nach 1,5 s beendet, die Seite leitet um.
- Threads: `InverterPoller` (Modbus), `MqttPublisher` (Verbindung + Ping), Webserver.
- Nach jedem erfolgreichen Lesezyklus ruft der Poller `on_new_values()` in `app.py` auf → MQTT.

## Register
- Adressen aus Huawei „Solar Inverter Modbus Interface Definitions“ (identisch zur huawei-solar-lib).
- Leseblöcke werden automatisch aus der Registertabelle gebildet (`build_blocks`, max. 60 Register, Lücken ≤ 8).
- Liefert ein Block die Ausnahme 2/3 (unbekannte Adresse), werden die Register einzeln gelesen; nicht unterstützte Register kommen auf eine Sperrliste und die Blöcke werden ohne sie neu gebildet. So laufen Anlagen ohne Akku/Zähler ohne Dauerfehler.
- Ungültig-Marker (0xFFFF, 0x7FFF, 0x7FFFFFFF, 0xFFFFFFFF) → `None`.
- Akku erkannt, wenn Nennkapazität (37758) > 0 oder Akkustatus ≠ 0. Zähler erkannt, wenn 37100 = 1.
- Hausverbrauch = Wechselrichter-Wirkleistung (32080) − Netzleistung (37113, + = Einspeisung). Nur mit Smart Meter.
- Gerätedaten (Modell, SN, Stringanzahl, Nennleistung) werden nur beim Verbinden gelesen.

## Neue Werte ergänzen
1. Eintrag in `REGISTERS` (`solar/registers.py`) – Typ, Faktor, Einheit, Gruppe, Topic.
2. Bei Bedarf Anzeige in `solar/webui.py` (`render()`); in der Tabelle „Werte“ erscheint er automatisch, ebenso als MQTT-Topic.

## Nicht am echten Gerät getestet
Getestet wurde mit `tools/huawei_simulator.py` (mit/ohne Akku und Zähler), einem echten MQTT-Broker und im Browser (Desktop + iPhone-Größe). Offen am echten Gerät:
- Ob alle Blöcke in einem Rutsch gelesen werden können (SDongle-Firmware-abhängig). Falls nicht, greift die Einzel-Lese-Logik.
- Vorzeichen/Einheiten der Zählerregister bei einphasigem Zähler (DDSU666-H).
- Register 37022 (Akkutemperatur) bezieht sich nur auf Akku-Einheit 1.
