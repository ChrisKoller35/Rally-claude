"""
Rally Deep Scan - Sucht nach RightSight-Deaktivierung
Testet ALLE moeglichen HID-Befehle systematisch.
Mit mehr Rechten koennen wir jetzt auch UVC und andere Wege testen.
"""

import hid
import time
import sys
import os
import subprocess
from datetime import datetime

VENDOR_ID = 0x046D
PRODUCT_ID = 0x0881

LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "deep_scan_log.txt")

def log(msg, f=None):
    ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    line = "[%s] %s" % (ts, msg)
    print(line)
    if f:
        f.write(line + "\n")
        f.flush()

def hex_dump(data):
    if not data:
        return "(leer)"
    return " ".join("%02X" % b for b in data)

def open_collection(usage_page):
    devices = hid.enumerate(vendor_id=VENDOR_ID, product_id=PRODUCT_ID)
    for d in devices:
        if d['usage_page'] == usage_page:
            h = hid.device()
            h.open_path(d['path'])
            h.set_nonblocking(1)
            return h
    return None

def scan_feature_reports(device, name, logf):
    """Liest ALLE Feature Reports (0x00 - 0xFF)."""
    log("", logf)
    log("=== Feature Reports auf %s ===" % name, logf)
    found = []
    for rid in range(0x00, 0x100):
        try:
            data = device.get_feature_report(rid, 65)
            if data and len(data) > 0:
                # Pruefen ob nicht nur Nullen
                if any(b != 0 for b in data[1:]):
                    log("  Feature 0x%02X [%d Bytes]: %s" % (rid, len(data), hex_dump(data[:32])), logf)
                    found.append((rid, data))
                else:
                    log("  Feature 0x%02X [%d Bytes]: (nur Nullen)" % (rid, len(data)), logf)
        except Exception:
            pass
    log("  => %d Feature Reports mit Daten gefunden" % len(found), logf)
    return found

def scan_output_reports(device, name, logf):
    """Testet Output Reports und liest Antworten."""
    log("", logf)
    log("=== Output Report Scan auf %s ===" % name, logf)
    found = []
    for rid in range(0x00, 0x20):
        try:
            # Sende leeren Report mit dieser ID
            cmd = [rid] + [0x00] * 64
            device.write(cmd)
            time.sleep(0.1)
            # Antwort lesen
            resp = device.read(65)
            if resp:
                log("  Output 0x%02X -> Antwort: %s" % (rid, hex_dump(resp[:20])), logf)
                found.append((rid, resp))
        except Exception as e:
            pass
    log("  => %d Output Reports mit Antwort" % len(found), logf)
    return found

def try_rightsight_commands(device, logf):
    """Versucht bekannte Logitech-Befehle fuer RightSight."""
    log("", logf)
    log("=== RightSight-spezifische Befehle testen ===", logf)
    
    # Bekannte Logitech HID++ und proprietaere Befehle
    tests = [
        # Format: (Beschreibung, Report-Daten)
        # Logitech verwendet oft Report 0x11 fuer lange HID++ Nachrichten
        ("HID++ Short 0x10 SubID=0x0A", [0x10, 0xFF, 0x0A, 0x00, 0x00, 0x00, 0x00]),
        ("HID++ Long 0x11 SubID=0x0A", [0x11, 0xFF, 0x0A] + [0x00] * 17),
        
        # Versuche verschiedene Report 0x0C Payloads (bekannt als Steuer-Report)
        ("Report 0x0C Byte1=0x01 (RightSight Off?)", [0x0C, 0x01] + [0x00] * 63),
        ("Report 0x0C Byte1=0x02 (RightSight Off?)", [0x0C, 0x02] + [0x00] * 63),
        ("Report 0x0C Byte1=0xFF (RightSight Off?)", [0x0C, 0xFF] + [0x00] * 63),
        ("Report 0x0C Byte2=0x01", [0x0C, 0x00, 0x01] + [0x00] * 62),
        ("Report 0x0C Byte2=0x02", [0x0C, 0x00, 0x02] + [0x00] * 62),
        ("Report 0x0C Bytes=0x01,0x01", [0x0C, 0x01, 0x01] + [0x00] * 62),
        
        # Spezielle Logitech Camera Befehle
        ("Report 0x0D (Config?)", [0x0D] + [0x00] * 64),
        ("Report 0x0E (Config?)", [0x0E] + [0x00] * 64),
        ("Report 0x0F (Config?)", [0x0F] + [0x00] * 64),
        
        # RightSight Toggle-Versuch ueber verschiedene Report IDs
        ("Report 0x01 Payload=0x00", [0x01, 0x00] + [0x00] * 63),
        ("Report 0x01 Payload=0x01", [0x01, 0x01] + [0x00] * 63),
        ("Report 0x02 Payload=0x00", [0x02, 0x00] + [0x00] * 63),
        ("Report 0x02 Payload=0x01", [0x02, 0x01] + [0x00] * 63),
        ("Report 0x03 Payload=0x00", [0x03, 0x00] + [0x00] * 63),
        ("Report 0x03 Payload=0x01", [0x03, 0x01] + [0x00] * 63),
    ]
    
    results = []
    for desc, cmd in tests:
        try:
            # Pad to 65 bytes if needed
            while len(cmd) < 65:
                cmd.append(0x00)
            device.write(cmd)
            time.sleep(0.15)
            resp = device.read(65)
            if resp:
                log("  %s -> %s" % (desc, hex_dump(resp[:20])), logf)
                results.append((desc, cmd, resp))
            else:
                log("  %s -> (keine Antwort)" % desc, logf)
        except Exception as e:
            log("  %s -> FEHLER: %s" % (desc, e), logf)
    
    return results

def try_collection1_commands(device, logf):
    """Testet Camera Control Collection (0xFF90) intensiver."""
    log("", logf)
    log("=== Collection 1 (0xFF90) Camera Control Deep Scan ===", logf)
    
    results = []
    # 5-Byte Reports mit verschiedenen Report IDs und Directions
    for rid in range(0x40, 0x50):
        for direction in range(0, 16):
            try:
                cmd = [rid, direction, 0x00, 0x00, 0x00]
                device.write(cmd)
                time.sleep(0.05)
                resp = device.read(64)
                if resp:
                    log("  Report 0x%02X Dir=%d -> %s" % (rid, direction, hex_dump(resp)), logf)
                    results.append((rid, direction, resp))
            except:
                pass
    
    # Auch mit Payload-Variationen
    log("  --- Payload-Variationen fuer bekannte Antwort-Reports ---", logf)
    for payload_b2 in [0x00, 0x01, 0x02, 0x10, 0x20, 0xFF]:
        for payload_b3 in [0x00, 0x01, 0x02, 0x10, 0xFF]:
            try:
                cmd = [0x41, 0x07, payload_b2, payload_b3, 0x00]
                device.write(cmd)
                time.sleep(0.05)
                resp = device.read(64)
                if resp:
                    log("  Report 0x41 Dir=7 P2=0x%02X P3=0x%02X -> %s" % (payload_b2, payload_b3, hex_dump(resp)), logf)
                    results.append((0x41, 7, resp))
            except:
                pass
    
    log("  => %d Antworten gefunden" % len(results), logf)
    return results

def try_feature_report_write(device, name, rid, original_data, logf):
    """Versucht Feature Report zu schreiben und prueft ob es haelt."""
    log("", logf)
    log("=== Feature Report 0x%02X Write-Test auf %s ===" % (rid, name), logf)
    log("  Original: %s" % hex_dump(original_data[:32]), logf)
    
    # Versuche verschiedene Byte-Aenderungen
    for byte_pos in range(1, min(len(original_data), 10)):
        orig_val = original_data[byte_pos]
        for new_val in [0x00, 0x01, 0x02, 0xFF]:
            if new_val == orig_val:
                continue
            modified = list(original_data)
            modified[byte_pos] = new_val
            try:
                device.send_feature_report(modified)
                time.sleep(0.1)
                readback = device.get_feature_report(rid, 65)
                if readback and readback[byte_pos] == new_val:
                    log("  ERFOLG! Byte %d: 0x%02X -> 0x%02X (haelt!)" % (byte_pos, orig_val, new_val), logf)
                    # Zuruecksetzen
                    device.send_feature_report(list(original_data))
                    time.sleep(0.1)
                    return True
            except Exception as e:
                pass
    
    log("  Kein Byte konnte dauerhaft geaendert werden", logf)
    return False

def check_uvc_controls(logf):
    """Prueft ob wir UVC-Zugriff auf die Kamera haben."""
    log("", logf)
    log("=== UVC / DirectShow Check ===", logf)
    
    try:
        import cv2
        log("  OpenCV verfuegbar: %s" % cv2.__version__, logf)
        
        # Versuche verschiedene Backends
        for backend_name, backend_id in [("DSHOW", cv2.CAP_DSHOW), ("MSMF", cv2.CAP_MSMF), ("ANY", cv2.CAP_ANY)]:
            log("  --- Backend: %s ---" % backend_name, logf)
            for cam_id in range(10):
                cap = cv2.VideoCapture(cam_id, backend_id)
                if cap.isOpened():
                    name = cap.getBackendName()
                    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                    
                    # PTZ Controls lesen
                    pan = cap.get(cv2.CAP_PROP_PAN)
                    tilt = cap.get(cv2.CAP_PROP_TILT)
                    zoom = cap.get(cv2.CAP_PROP_ZOOM)
                    
                    log("  Kamera %d: %s %dx%d Pan=%.0f Tilt=%.0f Zoom=%.0f" % (cam_id, name, w, h, pan, tilt, zoom), logf)
                    cap.release()
                else:
                    cap.release()
    except ImportError:
        log("  OpenCV nicht installiert - installiere es...", logf)
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "opencv-python"], 
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            log("  OpenCV installiert!", logf)
        except:
            log("  OpenCV konnte nicht installiert werden", logf)

def check_usb_devices(logf):
    """Listet USB-Geraete auf (mit mehr Rechten moeglich)."""
    log("", logf)
    log("=== USB Geraete-Info ===", logf)
    
    try:
        # PowerShell: USB-Geraete auflisten
        result = subprocess.run(
            ["powershell", "-Command", 
             "Get-PnpDevice -Class Camera -Status OK | Format-List FriendlyName,InstanceId,Status"],
            capture_output=True, text=True, timeout=10
        )
        if result.stdout.strip():
            log("  Kameras:", logf)
            for line in result.stdout.strip().split("\n"):
                log("    %s" % line.strip(), logf)
        else:
            log("  Keine Kameras ueber PnP gefunden", logf)
    except Exception as e:
        log("  PnP-Abfrage fehlgeschlagen: %s" % e, logf)
    
    try:
        # Logitech-spezifische USB-Geraete
        result = subprocess.run(
            ["powershell", "-Command",
             "Get-PnpDevice | Where-Object { $_.FriendlyName -like '*Rally*' -or $_.FriendlyName -like '*Logitech*' } | Format-List FriendlyName,InstanceId,Status"],
            capture_output=True, text=True, timeout=10
        )
        if result.stdout.strip():
            log("  Logitech/Rally Geraete:", logf)
            for line in result.stdout.strip().split("\n"):
                log("    %s" % line.strip(), logf)
    except Exception as e:
        log("  Logitech-Abfrage fehlgeschlagen: %s" % e, logf)

def check_logitech_software(logf):
    """Prueft welche Logitech-Software laeuft."""
    log("", logf)
    log("=== Logitech Software Check ===", logf)
    
    try:
        result = subprocess.run(
            ["powershell", "-Command",
             "Get-Process | Where-Object { $_.ProcessName -like '*Logi*' } | Select-Object ProcessName,Id,Path | Format-Table -AutoSize"],
            capture_output=True, text=True, timeout=10
        )
        if result.stdout.strip():
            log("  Laufende Logitech-Prozesse:", logf)
            for line in result.stdout.strip().split("\n"):
                log("    %s" % line.strip(), logf)
        else:
            log("  Keine Logitech-Prozesse gefunden", logf)
    except Exception as e:
        log("  Prozess-Abfrage fehlgeschlagen: %s" % e, logf)
    
    # Logitech Sync installiert?
    try:
        result = subprocess.run(
            ["powershell", "-Command",
             "Get-ItemProperty 'HKLM:\\Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\*','HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\*' 2>$null | Where-Object { $_.DisplayName -like '*Logi*' } | Select-Object DisplayName,DisplayVersion | Format-Table -AutoSize"],
            capture_output=True, text=True, timeout=10
        )
        if result.stdout.strip():
            log("  Installierte Logitech-Software:", logf)
            for line in result.stdout.strip().split("\n"):
                log("    %s" % line.strip(), logf)
        else:
            log("  Keine Logitech-Software in Registry gefunden", logf)
    except Exception as e:
        log("  Registry-Abfrage fehlgeschlagen: %s" % e, logf)


def main():
    with open(LOG_FILE, "w", encoding="utf-8") as logf:
        log("=" * 70, logf)
        log("RALLY DEEP SCAN - Suche nach RightSight-Deaktivierung", logf)
        log("=" * 70, logf)
        
        # 1. System-Info
        check_logitech_software(logf)
        check_usb_devices(logf)
        
        # 2. Collection 0 (0xFF00) - Hauptschnittstelle
        log("", logf)
        log("=" * 70, logf)
        log("COLLECTION 0 - Usage Page 0xFF00 (Logitech Proprietaer)", logf)
        log("=" * 70, logf)
        
        dev0 = open_collection(0xFF00)
        if dev0:
            log("  Verbunden!", logf)
            features0 = scan_feature_reports(dev0, "Collection 0", logf)
            try_rightsight_commands(dev0, logf)
            
            # Feature Reports schreibbar?
            for rid, data in features0:
                try_feature_report_write(dev0, "Collection 0", rid, data, logf)
            
            dev0.close()
        else:
            log("  FEHLER: Konnte Collection 0 nicht oeffnen!", logf)
        
        # 3. Collection 1 (0xFF90) - Camera Control
        log("", logf)
        log("=" * 70, logf)
        log("COLLECTION 1 - Usage Page 0xFF90 (Camera Control)", logf)
        log("=" * 70, logf)
        
        dev1 = open_collection(0xFF90)
        if dev1:
            log("  Verbunden!", logf)
            scan_feature_reports(dev1, "Collection 1", logf)
            try_collection1_commands(dev1, logf)
            dev1.close()
        else:
            log("  FEHLER: Konnte Collection 1 nicht oeffnen!", logf)
        
        # 4. Collection 2 (0xFF99) - Feature Reports
        log("", logf)
        log("=" * 70, logf)
        log("COLLECTION 2 - Usage Page 0xFF99 (Status/Config)", logf)
        log("=" * 70, logf)
        
        dev2 = open_collection(0xFF99)
        if dev2:
            log("  Verbunden!", logf)
            features2 = scan_feature_reports(dev2, "Collection 2", logf)
            
            for rid, data in features2:
                try_feature_report_write(dev2, "Collection 2", rid, data, logf)
            
            dev2.close()
        else:
            log("  FEHLER: Konnte Collection 2 nicht oeffnen!", logf)
        
        # 5. UVC/OpenCV
        check_uvc_controls(logf)
        
        log("", logf)
        log("=" * 70, logf)
        log("SCAN ABGESCHLOSSEN", logf)
        log("Log-Datei: %s" % LOG_FILE, logf)
        log("=" * 70, logf)


if __name__ == "__main__":
    main()
