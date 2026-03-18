# Rally Camera RightSight Disabler — Projekt-Zusammenfassung

*Stand: 18.03.2026 21:00 — Alles funktioniert!*

---

## Das Problem

Lehrer haben Logitech Rally Kameras. Beim Anstecken per USB-C bewegt sich die Kamera automatisch (RightSight/Auto-Tracking) — auch ohne Teams/Videocall. Das stört den Unterricht.

**Ziel:** Ein einmaliger Befehl der RightSight deaktiviert.

---

## Hardware

| Gerät | VID | PID | Serial/UUID |
|-------|-----|-----|-------------|
| Rally Camera | 0x046D | 0x0881 | Serial: **404ED540** |
| Rally System (Product) | 0x046D | 0x088B | UUID: **usb\|vid=46d\|pid=88b\|location=6de23f302** |
| Rally Table Hub | 0x046D | 0x088F | — |
| Rally Audio | 0x046D | 0x0885 | — |

Kamera über Rally Table Hub per USB-C am HP EliteBook x360 (Windows 11, kein Admin).

---

## Root Cause

LogiSync Software (`C:\Program Files (x86)\Logitech\LogiSync\`) liest beim USB-Connect:
```
HKLM\Software\Logitech\CropAssist\404ED540\CropAssistEnabled = true
```
Kamera startet mit RightSight=OFF → LogiSync liest Registry → Erzwingt RightSight AN.

Registry kann nicht geändert werden (HKLM = Access Denied, kein Admin).

---

## Lösung: WebSocket Protobuf Disable — FUNKTIONIERT!

### Architektur
```
rightsight_ws_client.py
    ↓ WebSocket (wss://127.0.0.1:9506, binary Protobuf)
LogiSyncProxy (Port 9506)
    ↓ intern (Port 5835)
LogiSyncMiddleware
    ↓ RightSightAPI.dll → WinUSB → Rally Camera
```

### Was passiert
1. Script verbindet per WSS zu LogiSyncProxy (self-signed cert ignorieren)
2. Sendet Protobuf-encoded `SetRightSightConfigurationRequest(enabled=false)`
3. Middleware ruft `CropAssistSetEnabled(false)` auf der Kamera auf
4. RightSight wird deaktiviert

### Protobuf-Nachrichtenstruktur
```
LogiSyncMessage {
  field 1 (submsg): Header {
    field 1 (double): timestamp (ms)
    field 2 (string): userContext ("rally-claude-client")
    field 3 (string): guid (UUID)
    field 4 (varint): status (0)
  }
  field 3 (submsg): Request {
    field 5 (submsg): VideoSettingsRequest {
      field 1 (submsg): SetRightSightConfigurationRequest {
        field 1 (string): productUuid → "usb|vid=46d|pid=88b|location=6de23f302"
        field 2 (varint): productModel → 20 (RALLY)
        field 3 (varint): enabled → 0 (false) oder 1 (true)
        field 4 (varint): mode → 0
      }
    }
  }
}
```

**WICHTIG:** `productUuid` ist die Rally-System-UUID (pid=88b), NICHT die Kamera-Serial "404ED540"!

### Beweis aus Middleware-Log (19:05:41)
```
CropAssistIsEnabled 404ED540: Result: 0  Enabled:true        ← War noch AN
CropAssistSetEnabled 404ED540: Result: 0 Disabled RightSight ← Unser Disable: ERFOLG!
RightSightEvent: {"enabled":"Disabled","state":"Ok"}          ← Bestätigt
```

Beim zweiten Aufruf (19:09:05):
```
CropAssistIsEnabled 404ED540: Result: 0  Enabled:false       ← War schon AUS (erster Disable hat gewirkt!)
```

---

## Aktueller Status: FUNKTIONIERT

- [x] RightSight Disable per WebSocket — funktioniert zuverlässig
- [x] Auto-Disable beim App-Start mit Reconnect-Monitoring
- [x] Kamera sperren/freigeben per OpenCV (blockiert alle Apps)
- [x] PTZ Kamera-Test
- [ ] Überlebt RightSight-Disable einen PC-Neustart? (noch nicht getestet)
- [ ] Falls nein: App im Autostart einrichten

### Korrigierte Annahmen
- **15s-Fenster stimmt NICHT** — API funktioniert solange Kamera verbunden ist
- **40400-Fehler** kommen nur wenn Kamera nicht richtig verbunden ist
- **HKCU Registry-Änderung** blockiert Kamera NICHT auf Windows 11 (braucht HKLM/Admin)
- **OpenCV exklusiver Zugriff** funktioniert als Kamera-Sperre ohne Admin-Rechte

---

## Scripts

| Datei | Beschreibung |
|-------|-------------|
| **`rightsight_ws_client.py`** | WebSocket Protobuf Client — Kernlogik. Sendet Disable/Enable über LogiSync API. Hat Direct-Mode und Monitor-Mode. |
| **`rightsight_app.py`** | Tkinter GUI: Auto-Disable, Kamera sperren/freigeben (OpenCV), PTZ-Test, Status-Monitoring. |
| `rally_stopper.py` | Alter Ansatz v3 — HID Stop-Befehle (funktioniert aber nicht elegant) |
| `rally_controller.py` | PTZ Controller GUI (OpenCV/DirectShow) |

### Benutzung
```bash
# Dependency
pip install websockets

# Direct disable (funktioniert nur im 15s-Fenster nach USB-Connect)
python rightsight_ws_client.py

# Direct enable
python rightsight_ws_client.py enable

# Monitor mode (wartet auf Kamera-Connect, dann auto-disable)
python rightsight_ws_client.py monitor

# GUI
python rightsight_app.py
```

---

## Logs prüfen

### LogiSync Middleware Log (wichtigste!)
```bash
# Letzte RightSight-Aktivitäten:
grep -a "CropAssist\|SetRightSight" "C:/ProgramData/Logitech/LogiSync/LogiSyncMiddleware.log" | tail -20

# Alle Fehler:
grep -a "error.*RightSight\|error.*CropAssist" "C:/ProgramData/Logitech/LogiSync/LogiSyncMiddleware.log" | tail -10
```

### LogiSync Proxy Log (zeigt JSON-formatierte Nachrichten)
```bash
grep -a "setRightSightConfiguration\|rightSightConfiguration" "C:/ProgramData/Logitech/LogiSync/LogiSyncProxy.log" | tail -10
```

### Registry prüfen
```powershell
Get-ChildItem 'HKLM:\Software\Logitech\CropAssist' -Recurse
```

---

## Gescheiterte Ansätze

| Ansatz | Warum gescheitert |
|--------|-------------------|
| HID Report 0x0C (Stop) | Kamera fährt nach 1s zurück (RightSight überschreibt) |
| UVC PTZ Lock (OpenCV) | RightSight überschreibt sofort |
| Registry HKLM ändern | Access Denied (kein Admin) |
| Registry HKCU | LogiSync liest nur HKLM |
| RightSightAPI.dll direkt | LogiSync hat exklusiven WinUSB-Lock |
| LogiSync Prozesse killen | Access Denied (kein Admin) |
| WebSocket mit UUID "404ED540" | Error 10006 "Device not found" (falsche UUID!) |
| WebSocket nach 40400-State | Error 40400 — API nur ~15s nach Connect verfügbar |
| HKCU Registry Deny | Ändert Registry aber blockiert Kamera nicht (Windows 11 liest HKLM) |
| HKLM Registry / Disable-PnpDevice | Access Denied — kein Admin auf Firmen-PC |
