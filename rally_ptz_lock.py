"""
Rally PTZ Lock v3 - DSHOW Fokussiert
Nutzt DirectShow Device 0 um die Kameraposition zu fixieren.

WICHTIG: Bitte Teams-Call mit Kamera starten BEVOR dieses Script laeuft!

Beenden mit Ctrl+C.
"""

import cv2
import time
import sys
import os
from datetime import datetime

LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ptz_lock_log.txt")


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


def main():
    print("=" * 60)
    print("  Rally PTZ Lock v3 - DSHOW")
    print("  Fixiert Kameraposition via DirectShow UVC")
    print("=" * 60)
    print()

    with open(LOG_FILE, "w", encoding="utf-8") as logf:
        log("PTZ Lock v3 gestartet - %s" % datetime.now().strftime("%Y-%m-%d %H:%M:%S"), logf)
        log("", logf)

        # Beide DSHOW Devices testen
        log("=== Teste DSHOW Devices ===", logf)

        beste = None
        for idx in range(3):
            cap = cv2.VideoCapture(idx, cv2.CAP_DSHOW)
            if not cap.isOpened():
                continue

            pan = cap.get(cv2.CAP_PROP_PAN)
            tilt = cap.get(cv2.CAP_PROP_TILT)
            zoom = cap.get(cv2.CAP_PROP_ZOOM)
            w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

            log("Device %d: %dx%d | Pan=%.1f Tilt=%.1f Zoom=%.1f" % (
                idx, w, h, pan, tilt, zoom), logf)

            # Schreibtest: Pan um 1 verschieben
            orig_pan = pan
            cap.set(cv2.CAP_PROP_PAN, orig_pan + 1)
            time.sleep(0.3)
            new_pan = cap.get(cv2.CAP_PROP_PAN)

            if new_pan != orig_pan:
                log("  >>> Pan aendert sich! (%.1f -> %.1f) <<<" % (orig_pan, new_pan), logf)
                # Zuruecksetzen
                cap.set(cv2.CAP_PROP_PAN, orig_pan)
                time.sleep(0.2)
                if beste is None:
                    beste = {"idx": idx, "pan": orig_pan, "tilt": tilt, "zoom": zoom}
            else:
                log("  Pan aendert sich nicht (%.1f)" % new_pan, logf)

            cap.release()

        log("", logf)

        if not beste:
            log("FEHLER: Kein Device reagiert auf PTZ-Befehle!", logf)
            log("", logf)
            log("Versuche trotzdem Device 0 zu locken...", logf)
            beste = {"idx": 0, "pan": 0, "tilt": 0, "zoom": 100}

        # === PTZ Lock ===
        idx = beste["idx"]
        log("=== PTZ Lock auf Device %d ===" % idx, logf)

        cap = cv2.VideoCapture(idx, cv2.CAP_DSHOW)
        if not cap.isOpened():
            log("FEHLER: Device %d kann nicht geoeffnet werden!" % idx, logf)
            return

        # Aktuelle Position als Ziel merken
        ziel_pan = cap.get(cv2.CAP_PROP_PAN)
        ziel_tilt = cap.get(cv2.CAP_PROP_TILT)
        ziel_zoom = cap.get(cv2.CAP_PROP_ZOOM)

        log("Zielposition: Pan=%.1f Tilt=%.1f Zoom=%.1f" % (ziel_pan, ziel_tilt, ziel_zoom), logf)
        log("Kamera wird jetzt fixiert. Ctrl+C zum Beenden.", logf)
        log("", logf)

        try:
            count = 0
            korrekturen = 0

            while True:
                count += 1

                # Aktuelle Position lesen
                pan = cap.get(cv2.CAP_PROP_PAN)
                tilt = cap.get(cv2.CAP_PROP_TILT)
                zoom = cap.get(cv2.CAP_PROP_ZOOM)

                # Bei Abweichung korrigieren
                abweichung = (pan != ziel_pan or tilt != ziel_tilt or zoom != ziel_zoom)

                if abweichung:
                    korrekturen += 1
                    log("Korrektur #%d: Pan %.1f->%.1f, Tilt %.1f->%.1f, Zoom %.1f->%.1f" % (
                        korrekturen, pan, ziel_pan, tilt, ziel_tilt, zoom, ziel_zoom), logf)

                # Position immer setzen (auch wenn gleich) um RightSight zu ueberschreiben
                cap.set(cv2.CAP_PROP_PAN, ziel_pan)
                cap.set(cv2.CAP_PROP_TILT, ziel_tilt)
                cap.set(cv2.CAP_PROP_ZOOM, ziel_zoom)

                # Status alle 10 Sekunden
                if count % 20 == 0:
                    log("--- %ds | Korrekturen: %d | Aktuell: Pan=%.1f Tilt=%.1f Zoom=%.1f ---" % (
                        count // 2, korrekturen, pan, tilt, zoom), logf)

                time.sleep(0.5)

        except KeyboardInterrupt:
            log("", logf)
            log("=== PTZ Lock gestoppt ===", logf)
            log("Laufzeit: %d Sekunden" % (count // 2), logf)
            log("Korrekturen: %d" % korrekturen, logf)
        finally:
            cap.release()

        log("Log: %s" % LOG_FILE, logf)

    print("\nFertig!")


if __name__ == "__main__":
    main()
