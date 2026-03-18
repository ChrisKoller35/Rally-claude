"""
Rally HID Discovery - Phase 3
Gezieltes Untersuchen von Feature Report 0x9A auf Collection 2 (0xFF99).

Dieser Report hat die Bytes: 9A 00 00 01 01 00 00...
Die 01 01 koennten Feature-Flags sein (RightSight an/an?).

Strategie:
  1. Report mehrmals lesen, Stabilitaet pruefen
  2. Einzelne Bytes aendern und zurueckschreiben
  3. Nach jeder Aenderung pruefen ob sie "haengen bleibt"
  4. Kameraverhalten beobachten
"""

import hid
import time
import sys
import os
from datetime import datetime

VENDOR_ID = 0x046D
PRODUCT_ID = 0x0881

LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "discovery_phase3_log.txt")


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


def hex_dump(data, max_bytes=None):
    if not data:
        return "(leer)"
    d = data[:max_bytes] if max_bytes else data
    suffix = "..." if max_bytes and len(data) > max_bytes else ""
    return " ".join("%02X" % b for b in d) + suffix


def open_collection(usage_page):
    devices = hid.enumerate(vendor_id=VENDOR_ID, product_id=PRODUCT_ID)
    for d in devices:
        if d['usage_page'] == usage_page:
            h = hid.device()
            h.open_path(d['path'])
            h.set_nonblocking(1)
            return h
    return None


def lese_0x9A(device):
    """Liest Feature Report 0x9A und gibt die Daten zurueck."""
    try:
        data = device.get_feature_report(0x9A, 65)
        return list(data) if data else None
    except Exception as e:
        return None


def schreibe_0x9A(device, daten):
    """Schreibt Feature Report 0x9A."""
    try:
        device.send_feature_report(bytes(daten))
        return True
    except Exception as e:
        return str(e)


def vergleiche(a, b):
    """Vergleicht zwei Byte-Listen und zeigt Unterschiede."""
    if a is None or b is None:
        return "Vergleich nicht moeglich"
    diffs = []
    for i in range(min(len(a), len(b))):
        if a[i] != b[i]:
            diffs.append("Byte %d: %02X -> %02X" % (i, a[i], b[i]))
    if not diffs:
        return "IDENTISCH"
    return ", ".join(diffs)


def main():
    print("=" * 60)
    print("  Rally HID Discovery - Phase 3")
    print("  Feature Report 0x9A Untersuchung")
    print("=" * 60)
    print()

    devices = hid.enumerate(vendor_id=VENDOR_ID, product_id=PRODUCT_ID)
    if not devices:
        print("FEHLER: Rally Kamera nicht gefunden!")
        return

    with open(LOG_FILE, "w", encoding="utf-8") as logf:
        log("Phase 3 - Feature Report 0x9A - %s" % datetime.now().strftime("%Y-%m-%d %H:%M:%S"), logf)
        log("", logf)

        # Collection 2 oeffnen
        device = open_collection(0xFF99)
        if not device:
            log("FEHLER: Collection 2 (0xFF99) nicht geoeffnet!", logf)
            return

        # ============================================
        # 1. Baseline lesen
        # ============================================
        log("=== 1. Baseline: Feature Report 0x9A lesen ===", logf)
        original = lese_0x9A(device)
        if not original:
            log("FEHLER: Kann 0x9A nicht lesen!", logf)
            device.close()
            return

        log("Original: %s" % hex_dump(original), logf)
        log("", logf)

        # Nicht-Null-Bytes identifizieren
        log("Nicht-Null-Bytes:", logf)
        for i, b in enumerate(original):
            if b != 0:
                log("  Byte %2d (0x%02X): Wert = 0x%02X (%d)" % (i, i, b, b), logf)
        log("", logf)

        # Mehrmals lesen zur Stabilitaet
        log("Stabilitaetscheck (5x lesen):", logf)
        alle_gleich = True
        for i in range(5):
            data = lese_0x9A(device)
            gleich = (data == original)
            if not gleich:
                alle_gleich = False
            log("  Lesung %d: %s %s" % (i + 1, hex_dump(data, 10), "OK" if gleich else "ANDERS!"), logf)
            time.sleep(0.3)
        log("  => %s" % ("Stabil" if alle_gleich else "INSTABIL!"), logf)
        log("", logf)

        # ============================================
        # 2. Schreibtest: Gleichen Wert zurueckschreiben
        # ============================================
        log("=== 2. Schreibtest: Original zurueckschreiben ===", logf)
        result = schreibe_0x9A(device, original)
        if result is True:
            log("Schreiben erfolgreich!", logf)
            check = lese_0x9A(device)
            log("Kontrolle: %s" % vergleiche(original, check), logf)
        else:
            log("Schreiben FEHLGESCHLAGEN: %s" % result, logf)
            log("=> Report ist READ-ONLY, weitere Tests nicht moeglich.", logf)
            device.close()
            return
        log("", logf)

        # ============================================
        # 3. Byte 3 aendern (erster 01-Wert)
        # ============================================
        log("=== 3. Byte 3 aendern (aktuell 0x01) ===", logf)
        log("Hypothese: Byte 3 = RightSight an/aus", logf)
        log("", logf)

        # Teste 0x01 -> 0x00
        test_data = list(original)
        test_data[3] = 0x00
        log("Setze Byte 3 = 0x00 ...", logf)
        result = schreibe_0x9A(device, test_data)
        if result is True:
            time.sleep(0.5)
            check = lese_0x9A(device)
            log("  Geschrieben. Zurueckgelesen: %s" % hex_dump(check, 10), logf)
            log("  Vergleich mit gewuenschtem Wert: %s" % vergleiche(test_data, check), logf)
            if check and check[3] == 0x00:
                log("  >>> BYTE 3 HAT SICH GEAENDERT! <<<", logf)
                log("  Warte 5 Sekunden - beobachte die Kamera...", logf)
                time.sleep(5)
                # Nochmal lesen - hat die Kamera den Wert zurueckgesetzt?
                check2 = lese_0x9A(device)
                log("  Nach 5s: %s" % hex_dump(check2, 10), logf)
                if check2 and check2[3] == 0x00:
                    log("  >>> WERT BLEIBT! Kamera hat ihn akzeptiert! <<<", logf)
                else:
                    log("  Kamera hat den Wert zurueckgesetzt.", logf)
            else:
                log("  Byte 3 hat sich NICHT geaendert (Kamera ignoriert es)", logf)
        else:
            log("  Schreiben fehlgeschlagen: %s" % result, logf)

        # Original wiederherstellen
        log("  Stelle Original wieder her...", logf)
        schreibe_0x9A(device, original)
        time.sleep(0.3)
        check = lese_0x9A(device)
        log("  Wiederhergestellt: %s" % vergleiche(original, check), logf)
        log("", logf)

        # ============================================
        # 4. Byte 4 aendern (zweiter 01-Wert)
        # ============================================
        log("=== 4. Byte 4 aendern (aktuell 0x01) ===", logf)
        log("Hypothese: Byte 4 = Speaker Tracking an/aus", logf)
        log("", logf)

        test_data = list(original)
        test_data[4] = 0x00
        log("Setze Byte 4 = 0x00 ...", logf)
        result = schreibe_0x9A(device, test_data)
        if result is True:
            time.sleep(0.5)
            check = lese_0x9A(device)
            log("  Geschrieben. Zurueckgelesen: %s" % hex_dump(check, 10), logf)
            log("  Vergleich: %s" % vergleiche(test_data, check), logf)
            if check and check[4] == 0x00:
                log("  >>> BYTE 4 HAT SICH GEAENDERT! <<<", logf)
                log("  Warte 5 Sekunden - beobachte die Kamera...", logf)
                time.sleep(5)
                check2 = lese_0x9A(device)
                log("  Nach 5s: %s" % hex_dump(check2, 10), logf)
                if check2 and check2[4] == 0x00:
                    log("  >>> WERT BLEIBT! <<<", logf)
                else:
                    log("  Kamera hat den Wert zurueckgesetzt.", logf)
            else:
                log("  Byte 4 hat sich NICHT geaendert", logf)
        else:
            log("  Schreiben fehlgeschlagen: %s" % result, logf)

        # Original wiederherstellen
        log("  Stelle Original wieder her...", logf)
        schreibe_0x9A(device, original)
        time.sleep(0.3)
        check = lese_0x9A(device)
        log("  Wiederhergestellt: %s" % vergleiche(original, check), logf)
        log("", logf)

        # ============================================
        # 5. Beide Bytes aendern
        # ============================================
        log("=== 5. Bytes 3 UND 4 auf 0x00 setzen ===", logf)
        log("Hypothese: Beide Features deaktivieren", logf)
        log("", logf)

        test_data = list(original)
        test_data[3] = 0x00
        test_data[4] = 0x00
        log("Setze Byte 3=0x00, Byte 4=0x00 ...", logf)
        result = schreibe_0x9A(device, test_data)
        if result is True:
            time.sleep(0.5)
            check = lese_0x9A(device)
            log("  Geschrieben. Zurueckgelesen: %s" % hex_dump(check, 10), logf)
            log("  Vergleich: %s" % vergleiche(test_data, check), logf)
            if check and check[3] == 0x00 and check[4] == 0x00:
                log("  >>> BEIDE BYTES GEAENDERT! <<<", logf)
                log("  Warte 10 Sekunden - beobachte die Kamera genau...", logf)
                for s in range(10):
                    time.sleep(1)
                    log("    %d Sekunden..." % (s + 1), logf)
                check2 = lese_0x9A(device)
                log("  Nach 10s: %s" % hex_dump(check2, 10), logf)
                if check2 and check2[3] == 0x00 and check2[4] == 0x00:
                    log("  >>> WERTE BLEIBEN! RightSight koennte deaktiviert sein! <<<", logf)
                else:
                    log("  Kamera hat Werte zurueckgesetzt.", logf)
            else:
                log("  Bytes haben sich NICHT geaendert", logf)
        else:
            log("  Schreiben fehlgeschlagen: %s" % result, logf)

        # Original wiederherstellen
        log("  Stelle Original wieder her...", logf)
        schreibe_0x9A(device, original)
        time.sleep(0.3)
        check = lese_0x9A(device)
        log("  Wiederhergestellt: %s" % vergleiche(original, check), logf)
        log("", logf)

        # ============================================
        # 6. Auch Feature 0x1A auf Collection 0 testen
        # ============================================
        device.close()

        log("=== 6. Feature 0x1A (Collection 0) - Schreibtest ===", logf)
        device0 = open_collection(0xFF00)
        if device0:
            orig_1a = None
            try:
                orig_1a = list(device0.get_feature_report(0x1A, 65))
                log("Original 0x1A: %s" % hex_dump(orig_1a), logf)
            except Exception as e:
                log("Lesen fehlgeschlagen: %s" % e, logf)

            if orig_1a:
                # Versuche Byte 1 zu aendern (0x03 -> 0x00)
                test = list(orig_1a)
                test[1] = 0x00
                log("Setze Byte 1 = 0x00 (war 0x%02X) ..." % orig_1a[1], logf)
                try:
                    device0.send_feature_report(bytes(test))
                    time.sleep(0.5)
                    check = list(device0.get_feature_report(0x1A, 65))
                    log("  Zurueckgelesen: %s" % hex_dump(check), logf)
                    log("  Vergleich: %s" % vergleiche(test, check), logf)
                except Exception as e:
                    log("  Fehler: %s" % e, logf)

                # Original wiederherstellen
                log("  Stelle Original wieder her...", logf)
                try:
                    device0.send_feature_report(bytes(orig_1a))
                    check = list(device0.get_feature_report(0x1A, 65))
                    log("  Wiederhergestellt: %s" % vergleiche(orig_1a, check), logf)
                except Exception as e:
                    log("  Fehler: %s" % e, logf)

            device0.close()
        log("", logf)

        # ============================================
        # Zusammenfassung
        # ============================================
        log("=" * 60, logf)
        log("Phase 3 abgeschlossen!", logf)
        log("Log: %s" % LOG_FILE, logf)
        log("", logf)
        log("Bitte die Kamera waehrend der Tests beobachten!", logf)
        log("Wenn sie bei einem Test aufgehoert hat sich zu bewegen,", logf)
        log("haben wir den RightSight-Schalter gefunden!", logf)

    print("\nFertig!")


if __name__ == "__main__":
    main()
