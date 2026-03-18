"""
Rally HID Discovery Tool
Sucht gezielt nach HID-Befehlen zum Deaktivieren von RightSight.

ACHTUNG: Dieses Script sendet Test-Befehle an die Kamera.
         Nur verwenden wenn die Kamera gerade nicht gebraucht wird!

Strategie:
  1. Alle 3 HID-Collections auflisten
  2. Collection 0 (0xFF00): Status-Reports lesen, verschiedene Report IDs testen
  3. Collection 1 (0xFF90): Camera Control Befehle proben
  4. Antworten protokollieren und Muster erkennen
"""

import hid
import time
import sys
import os
from datetime import datetime

VENDOR_ID = 0x046D
PRODUCT_ID = 0x0881

LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "discovery_log.txt")


def log(msg, file_handle=None):
    """Gibt Nachricht aus und schreibt in Log-Datei."""
    zeitstempel = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    zeile = f"[{zeitstempel}] {msg}"
    print(zeile)
    if file_handle:
        file_handle.write(zeile + "\n")
        file_handle.flush()


def hex_dump(data):
    """Formatiert Bytes als Hex-String."""
    if not data:
        return "(leer)"
    return " ".join(f"{b:02X}" for b in data)


def enumerate_collections():
    """Listet alle HID-Collections der Rally Kamera auf."""
    devices = hid.enumerate(vendor_id=VENDOR_ID, product_id=PRODUCT_ID)
    collections = []
    for i, d in enumerate(devices):
        collections.append({
            'index': i,
            'usage_page': d['usage_page'],
            'usage': d['usage'],
            'path': d['path'],
            'interface': d.get('interface_number', -1),
            'product': d.get('product_string', 'N/A'),
        })
    return collections


def open_collection(collections, usage_page):
    """Öffnet eine HID-Collection nach Usage Page."""
    for c in collections:
        if c['usage_page'] == usage_page:
            h = hid.device()
            h.open_path(c['path'])
            h.set_nonblocking(1)
            return h
    return None


def test_lesen_ohne_senden(device, dauer=5, logf=None):
    """Liest eingehende Reports ohne etwas zu senden (spontane Daten)."""
    log(f"--- Lausche {dauer}s auf spontane Reports ---", logf)
    start = time.time()
    count = 0
    while time.time() - start < dauer:
        data = device.read(64)
        if data:
            count += 1
            log(f"  Spontan empfangen [{len(data)} Bytes]: {hex_dump(data)}", logf)
        time.sleep(0.05)
    log(f"  => {count} spontane Reports empfangen in {dauer}s", logf)
    return count


def test_report_id_lesen(device, report_id, logf=None):
    """Sendet einen Report und liest die Antwort."""
    cmd = [report_id] + [0x00] * 64
    try:
        device.write(cmd[:65])
        time.sleep(0.1)
        antwort = device.read(64)
        if antwort:
            log(f"  Report 0x{report_id:02X} -> Antwort [{len(antwort)} Bytes]: {hex_dump(antwort)}", logf)
            return antwort
        else:
            log(f"  Report 0x{report_id:02X} -> Keine Antwort", logf)
            return None
    except Exception as e:
        log(f"  Report 0x{report_id:02X} -> FEHLER: {e}", logf)
        return None


def test_collection0_reports(device, logf=None):
    """Testet verschiedene Report IDs auf Collection 0 (0xFF00)."""
    log("=== Collection 0 (0xFF00) - Report IDs testen ===", logf)
    log("Sende jeweils Report mit Null-Payload und lese Antwort...", logf)

    ergebnisse = {}
    # Bekannte und wahrscheinliche Report IDs testen
    test_ids = list(range(0x01, 0x20))  # 0x01 bis 0x1F

    for rid in test_ids:
        antwort = test_report_id_lesen(device, rid, logf)
        if antwort:
            ergebnisse[rid] = antwort
        time.sleep(0.2)  # Sanft zur Kamera sein

    log(f"\n=> {len(ergebnisse)} von {len(test_ids)} Report IDs bekamen Antwort", logf)
    return ergebnisse


def test_report_0c_varianten(device, logf=None):
    """Testet Report 0x0C mit verschiedenen Byte-Mustern."""
    log("\n=== Report 0x0C - Verschiedene Payloads testen ===", logf)
    log("Report 0x0C ist der bekannte Steuer-Report.", logf)
    log("Teste verschiedene Byte-Muster im ersten Datenbyte...", logf)

    ergebnisse = {}
    # Erste Position (Byte 1 nach Report ID) variieren
    for wert in [0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x10, 0x20, 0x40, 0x80, 0xFF]:
        cmd = [0x0C, wert] + [0x00] * 63
        try:
            device.write(cmd[:65])
            time.sleep(0.15)
            antwort = device.read(64)
            if antwort:
                log(f"  0x0C [01]={wert:02X} -> {hex_dump(antwort)}", logf)
                ergebnisse[wert] = antwort
            else:
                log(f"  0x0C [01]={wert:02X} -> Keine Antwort", logf)
        except Exception as e:
            log(f"  0x0C [01]={wert:02X} -> FEHLER: {e}", logf)
        time.sleep(0.3)

    # Stopp senden um Kamera wieder zu beruhigen
    device.write([0x0C] + [0x00] * 64)

    log(f"\n=> {len(ergebnisse)} Varianten bekamen Antwort", logf)
    return ergebnisse


def test_collection1(collections, logf=None):
    """Testet Collection 1 (0xFF90) - Camera Control."""
    log("\n=== Collection 1 (0xFF90) - Camera Control ===", logf)

    device = open_collection(collections, 0xFF90)
    if not device:
        log("Collection 1 (0xFF90) nicht gefunden!", logf)
        return {}

    ergebnisse = {}
    # Bekannte Report IDs für diese Collection
    test_ids = [0x40, 0x41, 0x42, 0x43, 0x44, 0x45, 0x46, 0x47, 0x48]

    for rid in test_ids:
        # 5-Byte Reports (bekannte Größe für diese Collection)
        cmd = [rid] + [0x00] * 4
        try:
            device.write(cmd[:5])
            time.sleep(0.15)
            antwort = device.read(64)
            if antwort:
                log(f"  Report 0x{rid:02X} -> [{len(antwort)} Bytes]: {hex_dump(antwort)}", logf)
                ergebnisse[rid] = antwort
            else:
                log(f"  Report 0x{rid:02X} -> Keine Antwort", logf)
        except Exception as e:
            log(f"  Report 0x{rid:02X} -> FEHLER: {e}", logf)
        time.sleep(0.3)

    device.close()
    log(f"\n=> {len(ergebnisse)} Report IDs bekamen Antwort", logf)
    return ergebnisse


def test_feature_reports(collections, logf=None):
    """Versucht Feature Reports zu lesen (Collection 0)."""
    log("\n=== Feature Reports lesen (Collection 0) ===", logf)

    device = open_collection(collections, 0xFF00)
    if not device:
        log("Collection 0 nicht gefunden!", logf)
        return {}

    ergebnisse = {}
    for rid in range(0x01, 0x20):
        try:
            data = device.get_feature_report(rid, 65)
            if data:
                log(f"  Feature 0x{rid:02X} -> [{len(data)} Bytes]: {hex_dump(data)}", logf)
                ergebnisse[rid] = data
        except Exception as e:
            err = str(e)
            if "general failure" not in err.lower() and "not supported" not in err.lower():
                log(f"  Feature 0x{rid:02X} -> {err}", logf)
        time.sleep(0.1)

    device.close()
    log(f"\n=> {len(ergebnisse)} Feature Reports lesbar", logf)
    return ergebnisse


def main():
    print("=" * 60)
    print("  Rally HID Discovery Tool")
    print("  Sucht nach RightSight Steuer-Befehlen")
    print("=" * 60)
    print()
    print(f"Log-Datei: {LOG_FILE}")
    print()

    # Kamera suchen
    collections = enumerate_collections()
    if not collections:
        print("FEHLER: Rally Kamera nicht gefunden!")
        print(f"Gesucht: VID=0x{VENDOR_ID:04X} PID=0x{PRODUCT_ID:04X}")
        input("\nDrücke Enter zum Beenden...")
        return

    with open(LOG_FILE, "w", encoding="utf-8") as logf:
        log(f"Rally HID Discovery - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", logf)
        log(f"Kamera: VID=0x{VENDOR_ID:04X} PID=0x{PRODUCT_ID:04X}", logf)
        log(f"", logf)

        # 1. Collections auflisten
        log("=== HID Collections ===", logf)
        for c in collections:
            log(f"  [{c['index']}] Usage Page 0x{c['usage_page']:04X}, "
                f"Usage 0x{c['usage']:04X}, Interface {c['interface']}", logf)
        log("", logf)

        # 2. Collection 0 öffnen
        device = open_collection(collections, 0xFF00)
        if not device:
            log("FEHLER: Collection 0 (0xFF00) nicht gefunden!", logf)
            return

        # 3. Spontane Reports lauschen
        test_lesen_ohne_senden(device, dauer=3, logf=logf)

        # 4. Feature Reports lesen
        device.close()
        test_feature_reports(collections, logf=logf)

        # 5. Collection 0 Report IDs testen
        device = open_collection(collections, 0xFF00)
        if device:
            test_collection0_reports(device, logf)

            # 6. Report 0x0C Varianten
            test_report_0c_varianten(device, logf)
            device.close()

        # 7. Collection 1 testen
        test_collection1(collections, logf)

        log("\n" + "=" * 60, logf)
        log("Discovery abgeschlossen!", logf)
        log(f"Vollständiges Log: {LOG_FILE}", logf)
        log("", logf)
        log("Nächste Schritte:", logf)
        log("  - Log analysieren: Welche Report IDs antworten?", logf)
        log("  - Antworten vergleichen: gleich oder unterschiedlich?", logf)
        log("  - Auffällige Muster → gezielt weiter testen", logf)

    print("\nFertig! Log gespeichert.")
    input("\nDrücke Enter zum Beenden...")


if __name__ == "__main__":
    main()
