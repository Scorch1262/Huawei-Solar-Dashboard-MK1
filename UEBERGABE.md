# Übergabe – Huawei-Solar-Dashboard-MK1

Technische Notizen für die Weiterentwicklung.

## Aufbau
- **Keine Fremdpakete.** Modbus-TCP-Client (`solar/modbus.py`) und MQTT-3.1.1-Client (`solar/mqtt.py`, nur QoS 0 senden) sind selbst geschrieben. Dadurch baut PyInstaller ohne Zusatzoptionen und das Programm läuft auch auf Routern/Raspberry Pi mit nacktem `python3`.
- Webserver: `http.server.ThreadingHTTPServer` auf `0.0.0.0`. Portwechsel: neuer Server startet, alter wird nach 1,5 s beendet, die Seite leitet um.
- Threads: `InverterPoller` (Modbus), `MqttPublisher` (Verbindung + Ping), Webserver.
- Nach jedem erfolgreichen Lesezyklus ruft der Poller `on_new_values()` in `app.py` auf → MQTT.

## Verbindungsverhalten (ab v1.1.0)
- Timeout Standard 15 s (Referenz huawei-solar-lib: SDongle reagiert teils sehr langsam). Alte Konfigurationen ohne `config_version` mit < 15 s werden beim Start angehoben.
- `ModbusTimeout` = weiche Störung: Verbindung bleibt offen, verspätete Antworten werden per Transaktions-ID verworfen. Erst nach 5 Zeitüberschreitungen in Folge wird getrennt.
- Ausnahmecodes 4, 6, 0x0A, 0x0B gelten als vorübergehend (Verbindung bleibt).
- Harte Fehler: sauber schließen (`shutdown` + `close`), dann Backoff 5/10/20/40/60 s. Früher: bis zu 3 Neuverbindungen pro fehlgeschlagener Anfrage → Dongle hat neue Verbindungen minutenlang abgewiesen (im Simulator nachgestellt).
- Der Abfrage-Thread fängt jede Ausnahme; der Hauptthread überwacht ihn (Watchdog: Lebenszeichen, Neustart toter Threads, Abbruch hängender Anfragen).
- MQTT ist entkoppelt: Der Abfrage-Thread legt nur den neuesten Stand ab, der MQTT-Thread sendet.
- Protokoll: eigener Schreib-Thread (Konsole + `daten/protokoll.log`), damit eine angehaltene Windows-Konsole nichts blockiert. QuickEdit wird beim Start ausgeschaltet, Standby optional verhindert (`SetThreadExecutionState`).
- Verbindungstest auf der Webseite baut keine zweite Verbindung auf, solange die bestehende passt; sonst wird die laufende Verbindung währenddessen pausiert.

## Steuerung
- `solar/control.py`: `plan()` prüft Aktion + Wertebereich und liefert die Schreibliste, `make_executor()` schreibt im Abfrage-Thread (FC 0x06 für 1 Register, 0x10 für mehrere – wie huawei-solar-lib) und liest zurück.
- Zwangsladen: Reihenfolge 47246 (Vorgabe) → 47247/47249 (Leistung) → 47083 (Dauer) bzw. 47101 (Ziel-SOC) → zuletzt 47100 (Start).
- Ausnahme 0x80 bzw. 2 beim Schreiben → „Keine Schreibberechtigung“ (Installateur-Login über WLAN-FE ist nicht umgesetzt).
- Freigabe `steuerung.aktiv` (Standard aus), optionale PIN (`hmac.compare_digest`, nach 5 Fehlversuchen 60 s Sperre).
- Steuerregister (Gruppe `steuerung`) werden alle 60 s und direkt nach jedem Schreibbefehl gelesen.

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
Getestet wurde mit `tools/huawei_simulator.py` (mit/ohne Akku und Zähler, Aussetzer, Dongle-Sperre, Schreibschutz), einem echten MQTT-Broker und im Browser (Desktop + iPhone-Größe). Offen am echten Gerät:
- Schreibrechte je nach Anbindung (SDongle vs. WLAN-FE) und Verhalten der Firmware bei Zwangsladen/Einspeisebegrenzung.
- Ob alle Blöcke in einem Rutsch gelesen werden können (SDongle-Firmware-abhängig). Falls nicht, greift die Einzel-Lese-Logik.
- Vorzeichen/Einheiten der Zählerregister bei einphasigem Zähler (DDSU666-H).
- Register 37022 (Akkutemperatur) bezieht sich nur auf Akku-Einheit 1.
