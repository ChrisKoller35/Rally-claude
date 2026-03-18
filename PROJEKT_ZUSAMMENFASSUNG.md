# Rally PTZ Kamera - Projekt Zusammenfassung

## Ziel
Die Logitech Rally PTZ Kamera bewegt sich automatisch ("wie ein Geist") durch **RightSight** (Auto-Framing/Speaker Tracking). RightSight laeuft **in der Kamera-Firmware autonom** — keine externe Software noetig. Wir wollen diese automatische Bewegung unterbinden, ohne Admin-Rechte zu benoetigen (IT-verwalteter Firmen-PC).

## Status: FUNKTIONIERT

### Rally Stopper App v2 (`rally_stopper.py`)
- **Funktioniert!** Kamera bleibt still solange die App aktiv ist.
- Zwei Modi:
  - **MANUELL**: Sendet kontinuierlich Stop-Befehle (1/Sekunde) — zuverlaessig
  - **AUTO**: Sendet Probe-Befehle und versucht Bewegung zu erkennen — **unzuverlaessig** (Kamera-Antworten aendern sich nicht bei Bewegung, siehe Discovery-Ergebnisse)
- Auto-Connect beim Start (kein Klick noetig)
- Auto-Reconnect bei Verbindungsverlust
- Kamera reagiert beim Verbindungsaufbau (faehrt einmal kurz hoch/runter = "Handshake")
- Abhaengigkeit: `pip install hidapi`

### Autostart (`autostart.bat`)
- Erstellt Verknuepfung im Windows Startup-Ordner (kein Admin noetig)
- Nochmal ausfuehren = Autostart entfernen (Toggle)
- `start.bat` nutzt `pythonw` (kein schwarzes Konsolenfenster)

## Was wir herausgefunden haben

### Hardware
- **Kamera:** Logitech Rally PTZ Camera
- **USB Vendor ID:** 0x046D
- **USB Product ID:** 0x0881
- **Anschluss:** Ueber Rally Table Hub (USB-Hub)

### RightSight = Kamera-Firmware
- **Kritische Erkenntnis:** RightSight laeuft autonom in der Kamera-Firmware
- **LogiPresentation ist NICHT die Ursache** — es ist ein Presentation-Remote-Tool (fuer Logitech Spotlight), hat null Referenzen zu Kamera/RightSight/PTZ in seinen Binaerdateien
- LogiPresentation-Prozesse (LogiPresentation.exe, LogiPresentationUI.exe, LogiPresentationMgr.exe) steuern nur den Spotlight-Presenter
- Die Kamera entscheidet selbstaendig wann sie sich bewegt

### HID-Schnittstelle (3 Collections)

#### Collection 0 - Usage Page 0xFF00 (Logitech Proprietaer)
- **Hauptschnittstelle fuer Steuerung**
- Output Reports: 66 Bytes (Report ID + 65 Bytes Daten)
- **Report 0x0C**: Steuerbefehl — alle Nullen = STOP (funktioniert!)
- **Report 0x0A**: ACK von der Kamera: immer `0A AA 00 00 00 00 00 00 00 00 00 00 00`
- ACK ist IMMER identisch, egal welcher Payload in 0x0C (Byte 1 und 2 variiert, kein Unterschied)
- Nur Report 0x0C bekommt eine Antwort (0x01-0x1F getestet)
- **Feature Report 0x1A**: Geraetename "Logi Rally Camera" (USB String Descriptor, READ-ONLY)
- Keine weiteren Feature Reports (0x01-0xFF getestet)

#### Collection 1 - Usage Page 0xFF90 (Camera Control)
- 5-Byte Output Reports
- **Report 0x41 Direction=7**: Einzige Antwort: `40 21 00 00 00`
- Alle anderen Directions (0-6, 8-15) und Reports (0x40-0x48) antworten nicht
- Keine Feature Reports auf dieser Collection

#### Collection 2 - Usage Page 0xFF99
- Nur Feature Reports, keine Output/Input Reports
- **Feature Report 0x9A**: `9A 00 00 01 01 00 00...` (65 Bytes)
  - Bytes 3-4 sind `01 01` (moeglicherweise Status-Flags)
  - **READ-ONLY**: Schreiben wird akzeptiert aber Werte aendern sich nicht
  - Byte 3 auf 0x00: ignoriert, Byte 4 auf 0x00: ignoriert, beide: ignoriert
- Keine weiteren Feature Reports

### Discovery-Ergebnisse komplett
- Keine spontanen Reports (Kamera sendet nichts von sich aus)
- Feature Reports sind alle READ-ONLY (Schreiben wird ignoriert)
- Report 0x0C ACK aendert sich nie (keine Bewegungserkennung moeglich)
- Das HID-Interface erlaubt Bewegungskontrolle aber keine Konfiguration
- **RightSight per HID deaktivieren: mit den verfuegbaren Mitteln nicht moeglich**

### Was NICHT funktioniert hat
- OpenCV (DSHOW + MSMF) findet Rally Kamera nicht (nur HP-Kameras)
- DirectShow COM API Enumeration findet sie nicht
- Windows SetupDi API findet keine Device Interfaces
- `taskkill` auf LogiPresentation: Zugriff verweigert (kein Admin)
- Geraetemanager: Von IT blockiert
- Logitech Sync App: Nicht installiert, braucht wahrscheinlich Admin
- Feature Reports beschreiben: Kamera ignoriert alle Aenderungen
- Bewegungserkennung ueber HID-Antworten: Antworten sind immer identisch
- UVC Extension Unit: Kamera nicht ueber DirectShow/UVC erreichbar

## Loesung

### Aktuell: Rally Stopper (Manueller Modus)
Der manuelle Modus sendet kontinuierlich Stop-Befehle und haelt die Kamera still. Das ist die funktionierende Loesung.

### Theoretisch optimal: RightSight deaktivieren
Wuerde einen einmaligen Befehl erfordern, der nicht ueber das HID-Interface verfuegbar ist. Moeglich waere:
1. **USB-Traffic sniffen** (USBPcap + Wireshark) waehrend Logitech Sync RightSight deaktiviert — braucht Admin
2. **UVC Extension Unit** direkt ansprechen — braucht anderen Treiberansatz
3. **IT bitten** RightSight ueber Logitech Sync zu deaktivieren — IT hat keine Lust

## Technische Umgebung
- **OS:** Windows 11 Education (IT-verwaltet, kein Admin)
- **Python:** Installiert, pip verfuegbar
- **Installierte Pakete:** hidapi, opencv-python, pywinusb
- **Pfad:** `c:\Users\KBZ071644\Work Folders\Documents\Rally claude\`

## Dateien
- `rally_stopper.py` — Stopper App v2 (MANUELL + AUTO Modus) — **Hauptloesung**
- `rally_controller.py` — PTZ Controller (funktioniert nicht mit Rally)
- `rally_discovery.py` — HID Discovery Phase 1
- `rally_discovery2.py` — HID Discovery Phase 2 (Deep Scan)
- `rally_discovery3.py` — HID Discovery Phase 3 (Feature Report 0x9A Schreibtest)
- `discovery_log.txt` — Log Phase 1
- `discovery_phase2_log.txt` — Log Phase 2
- `discovery_phase3_log.txt` — Log Phase 3
- `start.bat` — Start-Script (nutzt pythonw)
- `install.bat` — Installationsscript
- `autostart.bat` — Autostart ein/aus Toggle
- `PROJEKT_ZUSAMMENFASSUNG.md` — Diese Datei
