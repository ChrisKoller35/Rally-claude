"""Schneller Check: Welche Rally-Kameras sind angeschlossen?"""
import hid

VENDOR_ID = 0x046D
PRODUCT_ID = 0x0881

print("=== Rally Kamera HID Enumeration ===")
devices = hid.enumerate(vendor_id=VENDOR_ID, product_id=PRODUCT_ID)
print("Gefundene HID-Devices mit VID=0x%04X PID=0x%04X: %d" % (VENDOR_ID, PRODUCT_ID, len(devices)))
print()

for i, d in enumerate(devices):
    print("--- Device %d ---" % i)
    print("  Product:        %s" % d.get("product_string", "N/A"))
    print("  Manufacturer:   %s" % d.get("manufacturer_string", "N/A"))
    print("  Serial:         %s" % d.get("serial_number", "N/A"))
    print("  Usage Page:     0x%04X" % d["usage_page"])
    print("  Usage:          0x%04X" % d["usage"])
    print("  Interface:      %s" % d.get("interface_number", -1))
    print("  Path:           %s" % d["path"].decode("utf-8", errors="replace") if isinstance(d["path"], bytes) else d["path"])
    print()

# Unique Logitech devices
print("=== Alle Logitech HID-Geraete (VID=0x046D) ===")
all_logi = hid.enumerate(vendor_id=VENDOR_ID)
seen = set()
for d in all_logi:
    key = (d["product_id"], d.get("product_string", ""))
    if key not in seen:
        seen.add(key)
        print("  PID=0x%04X  %s" % (d["product_id"], d.get("product_string", "N/A")))

# Auch testen ob wir eine Collection oeffnen koennen
print()
print("=== Verbindungstest ===")
for d in devices:
    up = d["usage_page"]
    try:
        h = hid.device()
        h.open_path(d["path"])
        h.set_nonblocking(1)
        prod = h.get_product_string()
        serial = h.get_serial_number_string()
        print("  Collection 0x%04X: OK (Product=%s, Serial=%s)" % (up, prod, serial))
        h.close()
    except Exception as e:
        print("  Collection 0x%04X: FEHLER - %s" % (up, e))
