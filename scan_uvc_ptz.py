"""
UVC PTZ Lock Test
Testet ob wir die Rally Kamera per UVC/OpenCV PTZ-Steuerung sperren koennen.
"""

import cv2
import time
import sys

def section(title):
    print()
    print("=" * 70)
    print(title)
    print("=" * 70)

# 1. Alle Kameras finden und identifizieren
section("1. KAMERAS IDENTIFIZIEREN")
kameras = []
for cam_id in range(10):
    cap = cv2.VideoCapture(cam_id, cv2.CAP_DSHOW)
    if cap.isOpened():
        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        pan = cap.get(cv2.CAP_PROP_PAN)
        tilt = cap.get(cv2.CAP_PROP_TILT)
        zoom = cap.get(cv2.CAP_PROP_ZOOM)
        fps = cap.get(cv2.CAP_PROP_FPS)
        fourcc = int(cap.get(cv2.CAP_PROP_FOURCC))
        backend = cap.getBackendName()
        
        info = {
            "id": cam_id, "w": w, "h": h,
            "pan": pan, "tilt": tilt, "zoom": zoom,
            "fps": fps, "backend": backend
        }
        kameras.append(info)
        
        print("Kamera %d: %dx%d @ %.0ffps" % (cam_id, w, h, fps))
        print("  Pan=%.1f  Tilt=%.1f  Zoom=%.1f" % (pan, tilt, zoom))
        
        # Alle verfuegbaren Properties auslesen
        props = [
            ("BRIGHTNESS", cv2.CAP_PROP_BRIGHTNESS),
            ("CONTRAST", cv2.CAP_PROP_CONTRAST),
            ("SATURATION", cv2.CAP_PROP_SATURATION),
            ("HUE", cv2.CAP_PROP_HUE),
            ("GAIN", cv2.CAP_PROP_GAIN),
            ("EXPOSURE", cv2.CAP_PROP_EXPOSURE),
            ("WHITE_BALANCE", cv2.CAP_PROP_WB_TEMPERATURE),
            ("FOCUS", cv2.CAP_PROP_FOCUS),
            ("AUTOFOCUS", cv2.CAP_PROP_AUTOFOCUS),
            ("AUTO_EXPOSURE", cv2.CAP_PROP_AUTO_EXPOSURE),
            ("PAN", cv2.CAP_PROP_PAN),
            ("TILT", cv2.CAP_PROP_TILT),
            ("ZOOM", cv2.CAP_PROP_ZOOM),
            ("ROLL", cv2.CAP_PROP_ROLL),
            ("IRIS", cv2.CAP_PROP_IRIS),
            ("BACKLIGHT", cv2.CAP_PROP_BACKLIGHT),
        ]
        print("  Alle Properties:")
        for name, prop_id in props:
            val = cap.get(prop_id)
            if val != 0 or name in ["PAN", "TILT", "ZOOM", "FOCUS", "EXPOSURE"]:
                print("    %-20s = %.2f" % (name, val))
        
        cap.release()
    else:
        cap.release()

# 2. Rally Kamera identifizieren (die mit Pan/Tilt != 0 oder Zoom != 100)
section("2. RALLY KAMERA IDENTIFIZIEREN")
rally_id = None
for k in kameras:
    # Rally hat typisch grosse PTZ-Werte
    if abs(k["pan"]) > 10 or abs(k["tilt"]) > 10 or k["zoom"] > 100:
        rally_id = k["id"]
        print("Rally erkannt als Kamera %d (Pan=%.0f Tilt=%.0f Zoom=%.0f)" % (k["id"], k["pan"], k["tilt"], k["zoom"]))
        break

if rally_id is None:
    # Fallback: letzte Kamera (Rally ist meist die letzte)
    if kameras:
        rally_id = kameras[-1]["id"]
        print("Rally nicht eindeutig erkannt, versuche Kamera %d" % rally_id)
    else:
        print("FEHLER: Keine Kameras gefunden!")
        sys.exit(1)

# 3. PTZ LESEN mit verschiedenen Methoden
section("3. PTZ WERTE DETAILLIERT LESEN")
cap = cv2.VideoCapture(rally_id, cv2.CAP_DSHOW)
if not cap.isOpened():
    print("FEHLER: Kann Rally Kamera %d nicht oeffnen!" % rally_id)
    sys.exit(1)

pan = cap.get(cv2.CAP_PROP_PAN)
tilt = cap.get(cv2.CAP_PROP_TILT)
zoom = cap.get(cv2.CAP_PROP_ZOOM)
print("Aktuelle PTZ: Pan=%.2f Tilt=%.2f Zoom=%.2f" % (pan, tilt, zoom))

# 4. PTZ SCHREIBEN TESTEN
section("4. PTZ SCHREIBEN TESTEN")

# Pan setzen
print("\n--- Pan Test ---")
for val in [0, 10, -10, pan]:
    ok = cap.set(cv2.CAP_PROP_PAN, val)
    readback = cap.get(cv2.CAP_PROP_PAN)
    print("  set(PAN, %.0f) -> %s, readback=%.2f" % (val, ok, readback))
    time.sleep(0.3)

# Tilt setzen
print("\n--- Tilt Test ---")
for val in [0, 10, -10, tilt]:
    ok = cap.set(cv2.CAP_PROP_TILT, val)
    readback = cap.get(cv2.CAP_PROP_TILT)
    print("  set(TILT, %.0f) -> %s, readback=%.2f" % (val, ok, readback))
    time.sleep(0.3)

# Zoom setzen
print("\n--- Zoom Test ---")
for val in [100, 150, 200, zoom]:
    ok = cap.set(cv2.CAP_PROP_ZOOM, val)
    readback = cap.get(cv2.CAP_PROP_ZOOM)
    print("  set(ZOOM, %.0f) -> %s, readback=%.2f" % (val, ok, readback))
    time.sleep(0.3)

# 5. PTZ Stabilitaetstest - Position halten
section("5. PTZ STABILITAETSTEST (10 Sekunden)")
print("Setze feste Position und beobachte ob sie haelt...")
target_pan = 0
target_tilt = 0
target_zoom = 100

cap.set(cv2.CAP_PROP_PAN, target_pan)
cap.set(cv2.CAP_PROP_TILT, target_tilt)
cap.set(cv2.CAP_PROP_ZOOM, target_zoom)

start = time.time()
changes = 0
last_vals = None
while time.time() - start < 10:
    p = cap.get(cv2.CAP_PROP_PAN)
    t = cap.get(cv2.CAP_PROP_TILT)
    z = cap.get(cv2.CAP_PROP_ZOOM)
    vals = (round(p, 1), round(t, 1), round(z, 1))
    if vals != last_vals:
        elapsed = time.time() - start
        print("  [%.1fs] Pan=%.1f Tilt=%.1f Zoom=%.1f %s" % (elapsed, p, t, z, "(GEAENDERT!)" if last_vals else "(Start)"))
        changes += 1
        last_vals = vals
    time.sleep(0.5)

if changes <= 1:
    print("  => Position blieb stabil!")
else:
    print("  => Position hat sich %dx geaendert!" % (changes - 1))

# 6. Autofocus und Auto-Exposure deaktivieren
section("6. AUTO-FUNKTIONEN DEAKTIVIEREN")

autofocus = cap.get(cv2.CAP_PROP_AUTOFOCUS)
auto_exp = cap.get(cv2.CAP_PROP_AUTO_EXPOSURE)
print("  AutoFocus: %.0f" % autofocus)
print("  AutoExposure: %.0f" % auto_exp)

# Autofocus aus
ok = cap.set(cv2.CAP_PROP_AUTOFOCUS, 0)
print("  set(AUTOFOCUS, 0) -> %s, readback=%.0f" % (ok, cap.get(cv2.CAP_PROP_AUTOFOCUS)))

# Auto-Exposure aus (1=manual, 3=auto bei manchen Kameras)
ok = cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 1)
print("  set(AUTO_EXPOSURE, 1) -> %s, readback=%.0f" % (ok, cap.get(cv2.CAP_PROP_AUTO_EXPOSURE)))

cap.release()

# 7. MSMF Backend auch testen
section("7. MSMF BACKEND TEST")
cap2 = cv2.VideoCapture(rally_id, cv2.CAP_MSMF)
if cap2.isOpened():
    pan = cap2.get(cv2.CAP_PROP_PAN)
    tilt = cap2.get(cv2.CAP_PROP_TILT)
    zoom = cap2.get(cv2.CAP_PROP_ZOOM)
    print("MSMF: Pan=%.2f Tilt=%.2f Zoom=%.2f" % (pan, tilt, zoom))
    
    ok_p = cap2.set(cv2.CAP_PROP_PAN, 0)
    ok_t = cap2.set(cv2.CAP_PROP_TILT, 0)
    ok_z = cap2.set(cv2.CAP_PROP_ZOOM, 100)
    print("MSMF set(0,0,100): Pan=%s Tilt=%s Zoom=%s" % (ok_p, ok_t, ok_z))
    print("MSMF readback: Pan=%.2f Tilt=%.2f Zoom=%.2f" % (
        cap2.get(cv2.CAP_PROP_PAN), cap2.get(cv2.CAP_PROP_TILT), cap2.get(cv2.CAP_PROP_ZOOM)))
    cap2.release()
else:
    print("MSMF konnte Rally nicht oeffnen")
    cap2.release()

print("\n\nFERTIG!")
