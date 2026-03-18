"""
Rally HID Live Monitor
Liest kontinuierlich alle HID-Reports und loggt Aenderungen.
Gedacht fuer Ausfuehrung WAEHREND eines aktiven Teams-Calls mit Kamera.

Ueberwacht:
  - Feature Report 0x9A (Collection 2, 0xFF99) - moegliche RightSight-Flags
  - Feature Report 0x1A (Collection 0, 0xFF00) - Geraetename
  - Input Reports auf Collection 0 (0xFF00) - spontane Kamera-Nachrichten
  - Input Reports auf Collection 1 (0xFF90) - Camera Control
  - Report 0x0C ACK auf Collection 0 - Steuer-Antworten

Beenden mit Ctrl+C.
"""

import hid
import time
import sys
import os
from datetime import datetime

VENDOR_ID = 0x046D
PRODUCT_ID = 0x0881

LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "live_monitor_log.txt")


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


def main():
    print("=" * 60)
    print("  Rally HID Live Monitor")
    print("  Ueberwacht HID-Reports waehrend Teams-Call")
    print("=" * 60)
    print()
    print("Starte mit aktivem Teams-Call + Kamera an!")
    print("Beenden mit Ctrl+C")
    print()

    devices = hid.enumerate(vendor_id=VENDOR_ID, product_id=PRODUCT_ID)
    if not devices:
        print("FEHLER: Rally Kamera nicht gefunden!")
        return

    with open(LOG_FILE, "w", encoding="utf-8") as logf:
        log("Live Monitor gestartet - %s" % datetime.now().strftime("%Y-%m-%d %H:%M:%S"), logf)
        log("", logf)

        # Alle 3 Collections oeffnen
        coll0 = open_collection(0xFF00)
        coll1 = open_collection(0xFF90)
        coll2 = open_collection(0xFF99)

        if not coll0:
            log("WARNUNG: Collection 0 (0xFF00) konnte nicht geoeffnet werden", logf)
        if not coll1:
            log("WARNUNG: Collection 1 (0xFF90) konnte nicht geoeffnet werden", logf)
        if not coll2:
            log("WARNUNG: Collection 2 (0xFF99) konnte nicht geoeffnet werden", logf)

        if not coll0 and not coll1 and not coll2:
            log("FEHLER: Keine Collection geoeffnet!", logf)
            return

        # Baselines lesen
        log("=== Baselines lesen ===", logf)

        baseline_9A = None
        if coll2:
            try:
                baseline_9A = list(coll2.get_feature_report(0x9A, 65))
                log("Feature 0x9A Baseline: %s" % hex_dump(baseline_9A, 10), logf)
            except Exception as e:
                log("Feature 0x9A Fehler: %s" % e, logf)

        baseline_1A = None
        if coll0:
            try:
                baseline_1A = list(coll0.get_feature_report(0x1A, 65))
                log("Feature 0x1A Baseline: %s" % hex_dump(baseline_1A, 10), logf)
            except Exception as e:
                log("Feature 0x1A Fehler: %s" % e, logf)

        log("", logf)
        log("=== Ueberwachung laeuft (alle 0.5s Feature Reports + Input Reports) ===", logf)
        log("", logf)

        iteration = 0
        aenderungen_gefunden = 0
        input_reports_coll0 = 0
        input_reports_coll1 = 0

        try:
            while True:
                iteration += 1

                # --- 1. Input Reports lesen (spontane Nachrichten) ---
                if coll0:
                    data = coll0.read(65)
                    while data:
                        input_reports_coll0 += 1
                        log(">>> INPUT Coll0 (0xFF00) #%d: %s" % (
                            input_reports_coll0, hex_dump(data, 20)), logf)
                        data = coll0.read(65)

                if coll1:
                    data = coll1.read(65)
                    while data:
                        input_reports_coll1 += 1
                        log(">>> INPUT Coll1 (0xFF90) #%d: %s" % (
                            input_reports_coll1, hex_dump(data, 20)), logf)
                        data = coll1.read(65)

                # --- 2. Feature Reports lesen (alle 2 Sekunden) ---
                if iteration % 4 == 0:
                    # Feature 0x9A
                    if coll2 and baseline_9A:
                        try:
                            current_9A = list(coll2.get_feature_report(0x9A, 65))
                            if current_9A != baseline_9A:
                                aenderungen_gefunden += 1
                                log("", logf)
                                log("!!! AENDERUNG #%d in Feature 0x9A !!!" % aenderungen_gefunden, logf)
                                log("  Vorher:  %s" % hex_dump(baseline_9A, 15), logf)
                                log("  Jetzt:   %s" % hex_dump(current_9A, 15), logf)
                                for i in range(min(len(baseline_9A), len(current_9A))):
                                    if baseline_9A[i] != current_9A[i]:
                                        log("  Byte %2d: 0x%02X -> 0x%02X" % (i, baseline_9A[i], current_9A[i]), logf)
                                baseline_9A = current_9A
                                log("", logf)
                        except Exception as e:
                            log("Feature 0x9A Lesefehler: %s" % e, logf)

                    # Feature 0x1A
                    if coll0 and baseline_1A:
                        try:
                            current_1A = list(coll0.get_feature_report(0x1A, 65))
                            if current_1A != baseline_1A:
                                aenderungen_gefunden += 1
                                log("", logf)
                                log("!!! AENDERUNG #%d in Feature 0x1A !!!" % aenderungen_gefunden, logf)
                                log("  Vorher:  %s" % hex_dump(baseline_1A, 15), logf)
                                log("  Jetzt:   %s" % hex_dump(current_1A, 15), logf)
                                for i in range(min(len(baseline_1A), len(current_1A))):
                                    if baseline_1A[i] != current_1A[i]:
                                        log("  Byte %2d: 0x%02X -> 0x%02X" % (i, baseline_1A[i], current_1A[i]), logf)
                                baseline_1A = current_1A
                                log("", logf)
                        except Exception as e:
                            log("Feature 0x1A Lesefehler: %s" % e, logf)

                # --- 3. Probe-Befehl auf Coll0 (alle 5 Sekunden) ---
                # Sendet Report 0x0C und liest ACK, um zu sehen ob sich die Antwort aendert
                if iteration % 10 == 0 and coll0:
                    try:
                        # Sende leeren 0x0C (Stop-Befehl)
                        cmd = [0x0C] + [0x00] * 65
                        coll0.write(bytes(cmd))
                        time.sleep(0.05)
                        ack = coll0.read(65)
                        if ack:
                            log("  Probe 0x0C ACK: %s" % hex_dump(ack, 15), logf)
                    except Exception as e:
                        log("  Probe 0x0C Fehler: %s" % e, logf)

                # --- 4. Statuszeile (alle 10 Sekunden) ---
                if iteration % 20 == 0:
                    elapsed = iteration * 0.5
                    log("--- %ds vergangen | Aenderungen: %d | Inputs: Coll0=%d, Coll1=%d ---" % (
                        int(elapsed), aenderungen_gefunden,
                        input_reports_coll0, input_reports_coll1), logf)

                time.sleep(0.5)

        except KeyboardInterrupt:
            log("", logf)
            log("=== Monitor gestoppt (Ctrl+C) ===", logf)
            elapsed = iteration * 0.5
            log("Laufzeit: %d Sekunden" % int(elapsed), logf)
            log("Aenderungen gefunden: %d" % aenderungen_gefunden, logf)
            log("Input Reports empfangen: Coll0=%d, Coll1=%d" % (
                input_reports_coll0, input_reports_coll1), logf)
            log("", logf)

            if aenderungen_gefunden == 0 and input_reports_coll0 == 0 and input_reports_coll1 == 0:
                log("ERGEBNIS: Keine Aenderungen waehrend Teams-Call.", logf)
                log("Die HID-Reports aendern sich auch bei aktiver Kamera nicht.", logf)
                log("RightSight-Status ist ueber HID nicht beobachtbar.", logf)
            elif aenderungen_gefunden > 0:
                log("ERGEBNIS: Feature Reports haben sich geaendert!", logf)
                log("Bitte Log pruefen fuer Details.", logf)
            else:
                log("ERGEBNIS: Nur Input Reports empfangen, keine Feature-Aenderungen.", logf)

            log("Log: %s" % LOG_FILE, logf)
        finally:
            if coll0:
                coll0.close()
            if coll1:
                coll1.close()
            if coll2:
                coll2.close()

    print("\nFertig!")


if __name__ == "__main__":
    main()
