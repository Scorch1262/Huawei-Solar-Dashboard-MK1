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

## Sicherheitskonzept (ab v1.3.0)
- `control.ENTLADESCHLUSS_MIN = 5`: Entladeschluss-SOC per Programm nie unter 5 % (Wechselrichter erlaubt 0–20 %). Bestehende kleinere Werte am Gerät werden nicht automatisch geändert, nur angezeigt.
- `control.write_guard()`: Freigabe, PIN (≥ 4), bestätigte SN, Modellfamilie (MAP0, KTL-M1), Verbindung, Messwerte aktuell. Wird von Steuerung UND Automatik genutzt.
- `control.make_executor(writes, expected_sn, strict)`: Whitelist `WRITABLE` (nur Gruppe „steuerung“), Kodierung vorab, SN wird im Abfrage-Thread direkt vor dem Schreiben gelesen, strenge Rücklese-Prüfung (47100 ausgenommen, das Gerät darf selbst beenden).
- `inverter.execute()`: Befehle mit Frist; aufgegebene/verfallene Befehle werden nie ausgeführt. Nach jedem Neuverbinden werden Gerätedaten (SN) neu gelesen.
- `smart.safety_checks()`: reine Funktion, alle Bedingungen für eine Netzladung; Ergebnis im Reiter sichtbar. Probebetrieb (Standard) schreibt nie.
- Zustand in `daten/smart_zustand.json` (laufende Ladung, `netzladen_vorher`, Störung) → nach Absturz wird beim nächsten Lauf gestoppt/zurückgesetzt.
- Start/Stopp unter `RLock`; Störung bei Rücklesefehler, Budget-Überschreitung, internem Fehler während Ladung, Zwangsladen länger als beauftragt.
- Windows: `SetConsoleCtrlHandler` beendet die Netzladung beim Schließen des Fensters/Abmelden/Herunterfahren.
- Webserver: POST nur mit `Content-Type: application/json` und passendem `Origin` (CSRF).
- PIN-Regeln: Freigeben, Einspeisebegrenzung freigeben, PIN ändern → aktuelle PIN; Smart-Laden scharf → PIN; Ausschalten/Probebetrieb → ohne PIN.
- Tests: `tests/test_sicherheit.py` (Unit, u. a. 2000 Zufallsszenarien – fand einen echten Fehler: Netzladung konnte über den Ziel-SOC gehen, wenn eine frühere Viertelstunde nachträglich belegt wurde; behoben durch harte Begrenzung in der Simulation), `tests/test_integration.py` (Programm + Simulator). In GitHub Actions Pflicht vor dem Build.

## Smart-Laden (ab v1.2.0)
- `solar/internet.py`: Energy-Charts `/price?bzn=…&start=…&end=…` (unix_seconds + price in EUR/MWh, 15 min), Ersatz aWATTar `/v1/marketdata` (ms-Zeitstempel). Open-Meteo `hourly=global_tilted_irradiance`, `tilt`, `azimuth` (0 Süd, −90 Ost, 90 West), `timeformat=unixtime`; Werte sind über die vorangegangene Stunde gemittelt → Wert mit Zeitstempel T gilt für [T−1h, T]. Adressen per Umgebungsvariable `HSD_URL_*` umleitbar (Tests).
- `solar/smart.py`: `build_plan()` ist frei von Seiteneffekten (auch für die Live-Vorschau). Greedy nach Preis aufsteigend; je Viertelstunde wird die Netzenergie so weit reduziert, dass die simulierte „verlorene PV-Energie“ (Überschuss bei vollem Akku) nicht steigt. 3 % Hysterese gegen ständiges Nachladen am Ziel-SOC.
- Ausführung im Thread `SmartCharger`: alle 30 s planen; Zwangsladen 47246=0, 47247=Leistung, 47083=Dauer (≤ 30 min), 47100=1; Stopp 47100=0. Neu beauftragt wird nur bei Leistungsänderung ≥ 300 W, Restdauer < 5 min oder früherem Blockende, höchstens einmal pro Minute.
- Abrufe: Preise stündlich, ab 13 Uhr alle 15 min bis die Preise für morgen da sind, bei Fehler nach 5 min; Wetter stündlich, bei Fehler nach 10 min.
- Statistik `daten/statistik.json`: je Stunde Summe/Anzahl von PV und Hausverbrauch sowie die letzte Prognose; Profile über 14 Tage (nur Stunden mit ≥ 20 Messungen).

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
- Smart-Laden: echte Dienste (Energy-Charts, aWATTar, Open-Meteo) nur gegen Nachbauten mit gleichem Antwortformat getestet; Verhalten des Wechselrichters beim wiederholten Verlängern des Zwangsladens.
- Schreibrechte je nach Anbindung (SDongle vs. WLAN-FE) und Verhalten der Firmware bei Zwangsladen/Einspeisebegrenzung.
- Ob alle Blöcke in einem Rutsch gelesen werden können (SDongle-Firmware-abhängig). Falls nicht, greift die Einzel-Lese-Logik.
- Vorzeichen/Einheiten der Zählerregister bei einphasigem Zähler (DDSU666-H).
- Register 37022 (Akkutemperatur) bezieht sich nur auf Akku-Einheit 1.
