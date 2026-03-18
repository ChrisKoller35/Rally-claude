"""PTZ test via DirectShow COM (IAMCameraControl) - bypasses OpenCV."""
import subprocess
import sys

# First, let's try to find the Rally Camera and check what works
import cv2
import time

print("=== Test 1: Zoom-Wert als Kamera-Identifikation ===")
for dev_id in range(3):
    for backend_name, backend in [("DSHOW", cv2.CAP_DSHOW), ("MSMF", cv2.CAP_MSMF)]:
        cap = cv2.VideoCapture(dev_id, backend)
        if not cap.isOpened():
            continue
        zoom = cap.get(cv2.CAP_PROP_ZOOM)
        w = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
        h = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
        focus = cap.get(cv2.CAP_PROP_FOCUS)
        print(f"  Dev {dev_id} [{backend_name}]: Zoom={zoom} Focus={focus} {int(w)}x{int(h)}")
        cap.release()

print("\n=== Test 2: Zoom aendern (sichtbare Aenderung) ===")
# Rally Camera had zoom=269 in LogiSync log. Try to zoom in/out.
for dev_id in [0, 1]:
    cap = cv2.VideoCapture(dev_id, cv2.CAP_DSHOW)
    if not cap.isOpened():
        continue

    zoom = cap.get(cv2.CAP_PROP_ZOOM)
    print(f"\nDev {dev_id}: Current zoom={zoom}")

    # Try zooming to 200
    print(f"  Zoom auf 200...")
    cap.set(cv2.CAP_PROP_ZOOM, 200)
    time.sleep(2)
    print(f"  Zoom readback: {cap.get(cv2.CAP_PROP_ZOOM)}")

    # Try zooming to 500
    print(f"  Zoom auf 500...")
    cap.set(cv2.CAP_PROP_ZOOM, 500)
    time.sleep(2)
    print(f"  Zoom readback: {cap.get(cv2.CAP_PROP_ZOOM)}")

    # Reset
    print(f"  Zoom zurueck auf {zoom}...")
    cap.set(cv2.CAP_PROP_ZOOM, zoom)
    time.sleep(1)

    cap.release()

print("\n=== Test 3: MSMF Backend PTZ ===")
for dev_id in [0, 1]:
    cap = cv2.VideoCapture(dev_id, cv2.CAP_MSMF)
    if not cap.isOpened():
        continue

    tilt = cap.get(cv2.CAP_PROP_TILT)
    print(f"\nDev {dev_id} [MSMF]: Current tilt={tilt}")

    print(f"  Tilt auf 30...")
    cap.set(cv2.CAP_PROP_TILT, 30)
    time.sleep(2)
    print(f"  Tilt readback: {cap.get(cv2.CAP_PROP_TILT)}")

    # Reset
    cap.set(cv2.CAP_PROP_TILT, tilt)
    time.sleep(1)

    cap.release()

print("\nDone. Hat sich die Kamera bewegt?")
