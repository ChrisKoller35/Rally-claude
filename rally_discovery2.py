"""
Rally HID Deep Discovery - Phase 2
Vertieft die Untersuchung basierend auf Phase 1 Ergebnissen:
  - Feature Report 0x1A genauer untersuchen (lesen + schreiben versuchen)
  - Weitere Feature Report IDs testen (0x20-0xFF)
  - Report 0x0C mit laengerer Wartezeit testen
  - Collection 1 mit bekannten Datenmustern testen
"""

import hid
import time
import sys
import os
from datetime import datetime

VENDOR_ID = 0x046D
PRODUCT_ID = 0x0881
USAGE_PAGE_MAIN = 0xFF00
USAGE_PAGE_CAM = 0xFF90

LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "discovery_phase2_log.txt")


def log(msg, file_handle=None):
    zeitstempel = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    zeile = "[%s] %s" % (zeitstempel, msg)
    try:
        print(zeile)
    except UnicodeEncodeError:
        print(zeile.encode("ascii", errors="replace").decode())
    if file_handle:
        file_handle.write(zeile + "\n")
        file_handle.flush()


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


def read_all_responses(device, timeout=0.5):
    """Liest alle wartenden Antworten aus."""
    responses = []
    start = time.time()
    while time.time() - start < timeout:
        data = device.read(64)
        if data:
            responses.append(data)
        time.sleep(0.02)
    return responses


def test_feature_report_0x1A(logf):
    """Untersucht Feature Report 0x1A im Detail."""
    log("\n" + "=" * 60, logf)
    log("=== Feature Report 0x1A - Detailuntersuchung ===", logf)
    log("=" * 60, logf)

    device = open_collection(USAGE_PAGE_MAIN)
    if not device:
        log("FEHLER: Collection 0 nicht geoeffnet!", logf)
        return

    # 1. Mehrmals lesen - aendert sich der Wert?
    log("\n--- 0x1A mehrmals lesen (Wert stabil?) ---", logf)
    werte = []
    for i in range(5):
        try:
            data = device.get_feature_report(0x1A, 65)
            werte.append(bytes(data))
            log("  Lesung %d: %s" % (i + 1, hex_dump(data)), logf)
        except Exception as e:
            log("  Lesung %d: FEHLER %s" % (i + 1, e), logf)
        time.sleep(0.3)

    if len(set(werte)) == 1:
        log("  => Wert ist STABIL (gleich bei allen Lesungen)", logf)
    else:
        log("  => Wert AENDERT sich!", logf)

    # 2. Verschiedene Leselaengen testen
    log("\n--- 0x1A mit verschiedenen Leselaengen ---", logf)
    for length in [3, 4, 5, 8, 16, 32, 64, 65]:
        try:
            data = device.get_feature_report(0x1A, length)
            log("  Laenge %2d: %s" % (length, hex_dump(data)), logf)
        except Exception as e:
            log("  Laenge %2d: FEHLER %s" % (length, e), logf)
        time.sleep(0.1)

    # 3. Feature Report 0x1A schreiben versuchen
    log("\n--- 0x1A schreiben versuchen ---", logf)
    log("  VORSICHT: Teste nur sichere Werte!", logf)

    # Erst aktuellen Wert lesen
    try:
        original = device.get_feature_report(0x1A, 65)
        log("  Original-Wert: %s" % hex_dump(original), logf)
    except Exception as e:
        log("  Kann Original nicht lesen: %s" % e, logf)
        original = None

    # Versuche den gleichen Wert zurueckzuschreiben (sicher)
    if original:
        try:
            device.send_feature_report(bytes(original))
            log("  Gleichen Wert zurueckgeschrieben: OK", logf)
            # Nochmal lesen
            check = device.get_feature_report(0x1A, 65)
            log("  Kontrolle nach Schreiben: %s" % hex_dump(check), logf)
        except Exception as e:
            log("  Schreiben FEHLGESCHLAGEN: %s" % e, logf)
            log("  => Feature Report ist vermutlich READ-ONLY", logf)

    device.close()


def test_extended_feature_reports(logf):
    """Testet Feature Reports 0x20-0xFF."""
    log("\n" + "=" * 60, logf)
    log("=== Feature Reports 0x20-0xFF testen ===", logf)
    log("=" * 60, logf)

    device = open_collection(USAGE_PAGE_MAIN)
    if not device:
        log("FEHLER: Collection 0 nicht geoeffnet!", logf)
        return

    gefunden = {}
    for rid in range(0x20, 0x100):
        try:
            data = device.get_feature_report(rid, 65)
            if data:
                log("  Feature 0x%02X: %s" % (rid, hex_dump(data)), logf)
                gefunden[rid] = data
        except Exception:
            pass
        # Nicht zu schnell
        if rid % 32 == 0:
            time.sleep(0.1)

    log("\n=> %d weitere Feature Reports gefunden" % len(gefunden), logf)
    device.close()
    return gefunden


def test_report_0c_deep(logf):
    """Testet Report 0x0C gruendlicher mit laengerer Wartezeit."""
    log("\n" + "=" * 60, logf)
    log("=== Report 0x0C - Gruendlicherer Test ===", logf)
    log("=" * 60, logf)

    device = open_collection(USAGE_PAGE_MAIN)
    if not device:
        log("FEHLER: Collection 0 nicht geoeffnet!", logf)
        return

    # Erst Baseline: Standard-Stop senden
    log("\n--- Baseline: Standard-Stop (alles Nullen) ---", logf)
    cmd = [0x0C] + [0x00] * 64
    device.write(cmd[:65])
    time.sleep(0.3)
    responses = read_all_responses(device, timeout=1.0)
    for r in responses:
        log("  Baseline Antwort: %s" % hex_dump(r), logf)

    # Verschiedene Byte-Positionen testen
    log("\n--- Byte 1 variieren (mit laengerer Wartezeit) ---", logf)
    for wert in [0x00, 0x01, 0x02, 0x04, 0x08, 0x10, 0x20, 0x40, 0x80, 0xFF]:
        cmd = [0x0C, wert] + [0x00] * 63
        device.write(cmd[:65])
        time.sleep(0.5)
        responses = read_all_responses(device, timeout=0.5)
        if responses:
            for r in responses:
                log("  [01]=0x%02X -> %s" % (wert, hex_dump(r)), logf)
        else:
            log("  [01]=0x%02X -> Keine Antwort" % wert, logf)

    log("\n--- Byte 2 variieren ---", logf)
    for wert in [0x01, 0x02, 0x04, 0x08, 0x10, 0x80, 0xFF]:
        cmd = [0x0C, 0x00, wert] + [0x00] * 62
        device.write(cmd[:65])
        time.sleep(0.5)
        responses = read_all_responses(device, timeout=0.5)
        if responses:
            for r in responses:
                log("  [02]=0x%02X -> %s" % (wert, hex_dump(r)), logf)
        else:
            log("  [02]=0x%02X -> Keine Antwort" % wert, logf)

    # Sicher: Stop senden am Ende
    device.write(([0x0C] + [0x00] * 64)[:65])
    device.close()


def test_collection1_deep(logf):
    """Testet Collection 1 mit bekannten Datenmustern."""
    log("\n" + "=" * 60, logf)
    log("=== Collection 1 (0xFF90) - Camera Control Deep Test ===", logf)
    log("=" * 60, logf)

    device = open_collection(USAGE_PAGE_CAM)
    if not device:
        log("FEHLER: Collection 1 nicht geoeffnet!", logf)
        return

    # Aus der Zusammenfassung: Report 0x41 mit Direction 4 und 7 bekamen Antworten
    log("\n--- Report 0x41 mit Direction-Werten ---", logf)
    for direction in range(0, 16):
        cmd = [0x41, direction, 0x00, 0x00, 0x00]
        try:
            device.write(cmd)
            time.sleep(0.3)
            responses = read_all_responses(device, timeout=0.5)
            if responses:
                for r in responses:
                    log("  0x41 Dir=%d -> %s" % (direction, hex_dump(r)), logf)
            else:
                log("  0x41 Dir=%d -> Keine Antwort" % direction, logf)
        except Exception as e:
            log("  0x41 Dir=%d -> FEHLER: %s" % (direction, e), logf)

    # Report 0x44 testen (auch bekannt)
    log("\n--- Report 0x44 testen ---", logf)
    for byte1 in [0x00, 0x01, 0x02, 0x04, 0x08, 0x10]:
        cmd = [0x44, byte1, 0x00, 0x00, 0x00]
        try:
            device.write(cmd)
            time.sleep(0.3)
            responses = read_all_responses(device, timeout=0.5)
            if responses:
                for r in responses:
                    log("  0x44 [01]=0x%02X -> %s" % (byte1, hex_dump(r)), logf)
            else:
                log("  0x44 [01]=0x%02X -> Keine Antwort" % byte1, logf)
        except Exception as e:
            log("  0x44 [01]=0x%02X -> FEHLER: %s" % (byte1, e), logf)

    # Feature Reports auf Collection 1 testen
    log("\n--- Feature Reports auf Collection 1 ---", logf)
    for rid in range(0x01, 0x50):
        try:
            data = device.get_feature_report(rid, 65)
            if data:
                log("  Feature 0x%02X: %s" % (rid, hex_dump(data)), logf)
        except Exception:
            pass

    device.close()


def test_collection2(logf):
    """Testet Collection 2 (0xFF99)."""
    log("\n" + "=" * 60, logf)
    log("=== Collection 2 (0xFF99) - Feature Reports ===", logf)
    log("=" * 60, logf)

    devices = hid.enumerate(vendor_id=VENDOR_ID, product_id=PRODUCT_ID)
    target = None
    for d in devices:
        if d['usage_page'] == 0xFF99:
            target = d
            break

    if not target:
        log("Collection 2 (0xFF99) nicht gefunden!", logf)
        return

    try:
        device = hid.device()
        device.open_path(target['path'])
        device.set_nonblocking(1)
    except Exception as e:
        log("Kann Collection 2 nicht oeffnen: %s" % e, logf)
        return

    log("Collection 2 geoeffnet.", logf)

    # Feature Reports testen
    gefunden = {}
    for rid in range(0x01, 0x100):
        try:
            data = device.get_feature_report(rid, 65)
            if data:
                log("  Feature 0x%02X: %s" % (rid, hex_dump(data)), logf)
                gefunden[rid] = data
        except Exception:
            pass
        if rid % 32 == 0:
            time.sleep(0.05)

    log("\n=> %d Feature Reports auf Collection 2 gefunden" % len(gefunden), logf)
    device.close()
    return gefunden


def main():
    print("=" * 60)
    print("  Rally HID Deep Discovery - Phase 2")
    print("  Basierend auf Phase 1 Ergebnissen")
    print("=" * 60)
    print()
    print("Log: %s" % LOG_FILE)
    print()

    # Pruefen ob Kamera da ist
    devices = hid.enumerate(vendor_id=VENDOR_ID, product_id=PRODUCT_ID)
    if not devices:
        print("FEHLER: Rally Kamera nicht gefunden!")
        input("\nDruecke Enter zum Beenden...")
        return

    with open(LOG_FILE, "w", encoding="utf-8") as logf:
        log("Rally HID Deep Discovery Phase 2 - %s" % datetime.now().strftime("%Y-%m-%d %H:%M:%S"), logf)
        log("", logf)

        # 1. Feature Report 0x1A untersuchen
        test_feature_report_0x1A(logf)

        # 2. Erweiterte Feature Reports (0x20-0xFF)
        test_extended_feature_reports(logf)

        # 3. Report 0x0C gruendlicher
        test_report_0c_deep(logf)

        # 4. Collection 1 mit bekannten Mustern
        test_collection1_deep(logf)

        # 5. Collection 2 komplett
        test_collection2(logf)

        log("\n" + "=" * 60, logf)
        log("Phase 2 Discovery abgeschlossen!", logf)
        log("Log: %s" % LOG_FILE, logf)

    print("\nFertig! Log gespeichert.")
    input("\nDruecke Enter zum Beenden...")


if __name__ == "__main__":
    main()
