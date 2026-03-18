"""Quick PTZ test - try to move the Rally Camera."""
import cv2
import time

print("=== PTZ Direct Test ===\n")

for dev_id in [0, 1]:
    print(f"--- Device {dev_id} (DSHOW) ---")
    cap = cv2.VideoCapture(dev_id, cv2.CAP_DSHOW)
    if not cap.isOpened():
        print(f"  Konnte nicht geoeffnet werden\n")
        continue

    pan = cap.get(cv2.CAP_PROP_PAN)
    tilt = cap.get(cv2.CAP_PROP_TILT)
    zoom = cap.get(cv2.CAP_PROP_ZOOM)
    print(f"  Pan={pan} Tilt={tilt} Zoom={zoom}")

    # Try big tilt movement
    print(f"  Setze Tilt auf {tilt + 30}...")
    ok = cap.set(cv2.CAP_PROP_TILT, tilt + 30)
    print(f"  set() returned: {ok}")
    time.sleep(2)

    new_tilt = cap.get(cv2.CAP_PROP_TILT)
    print(f"  Tilt nach set: {new_tilt}")

    # Reset
    print(f"  Zurueck auf {tilt}...")
    cap.set(cv2.CAP_PROP_TILT, tilt)
    time.sleep(1)

    cap.release()
    print()

print("Done.")
