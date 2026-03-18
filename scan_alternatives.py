"""Alternative Wege testen um RightSight zu deaktivieren."""
import subprocess
import os

def run_ps(cmd):
    """PowerShell Befehl ausfuehren."""
    r = subprocess.run(["powershell", "-Command", cmd], capture_output=True, text=True, timeout=15)
    return r.stdout.strip(), r.stderr.strip()

print("=== ALTERNATIVE WEGE ===")
print()

# 1. Admin-Status
print("--- 1. Admin-Status ---")
out, err = run_ps("([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)")
print("Ist Admin: %s" % out)

# 2. HKCU Override
print()
print("--- 2. HKCU Override versuchen ---")
r = subprocess.run(
    ["reg", "add", r"HKCU\Software\Logitech\CropAssist\404ED540", "/v", "CropAssistEnabled", "/t", "REG_SZ", "/d", "false", "/f"],
    capture_output=True, text=True
)
print("HKCU CropAssist: %s" % (r.stdout.strip() or r.stderr.strip()))

r = subprocess.run(
    ["reg", "add", r"HKCU\Software\Logitech\CropAssist\404ED540", "/v", "SACAEnabled", "/t", "REG_SZ", "/d", "false", "/f"],
    capture_output=True, text=True
)
print("HKCU SACA: %s" % (r.stdout.strip() or r.stderr.strip()))

# 3. LogiSync Prozesse killbar?
print()
print("--- 3. LogiSync Prozesse killbar? ---")
for proc in ["LogiSyncHandler", "LogiSyncMiddleware", "LogiSyncProxy", "LogiSyncStub"]:
    r = subprocess.run(["taskkill", "/IM", proc + ".exe", "/F"], capture_output=True, text=True)
    msg = r.stdout.strip() or r.stderr.strip()
    print("  kill %s: %s" % (proc, msg))

# 4. LogiSync lokaler Port/API?
print()
print("--- 4. LogiSync Netzwerk-Ports ---")
out, err = run_ps(
    "Get-NetTCPConnection -State Listen 2>$null | "
    "ForEach-Object { $proc = Get-Process -Id $_.OwningProcess -ErrorAction SilentlyContinue; "
    "if ($proc.ProcessName -like '*Logi*') { "
    "'Port=' + $_.LocalPort + ' Process=' + $proc.ProcessName } }"
)
print(out if out else "(keine Ports)")

# 5. Pruefen ob LogiSync wirklich tot ist
print()
print("--- 5. Laufen LogiSync Prozesse noch? ---")
out, err = run_ps("Get-Process LogiSync* -ErrorAction SilentlyContinue | Select-Object ProcessName,Id | Format-Table")
print(out if out else "Alle LogiSync Prozesse gestoppt!")

# 6. Jetzt HKLM nochmal versuchen (vielleicht geht es jetzt ohne LogiSync Lock?)
print()
print("--- 6. HKLM nochmal versuchen ---")
r = subprocess.run(
    ["reg", "add", r"HKLM\Software\Logitech\CropAssist\404ED540", "/v", "CropAssistEnabled", "/t", "REG_SZ", "/d", "false", "/f"],
    capture_output=True, text=True
)
print("HKLM CropAssist: %s" % (r.stdout.strip() or r.stderr.strip()))

# 7. LogiSync Installationsordner - gibt es eine CLI oder Config?
print()
print("--- 7. LogiSync Ordner-Inhalt ---")
base = r"C:\Program Files (x86)\Logitech\LogiSync"
if os.path.exists(base):
    for item in sorted(os.listdir(base)):
        full = os.path.join(base, item)
        if os.path.isdir(full):
            print("  [DIR]  %s" % item)
        else:
            size = os.path.getsize(full)
            print("  [%dKB] %s" % (size // 1024, item))
else:
    print("  Ordner nicht gefunden!")

stub = r"C:\Program Files (x86)\Logitech\LogiSyncStub"
if os.path.exists(stub):
    print()
    print("LogiSyncStub:")
    for item in sorted(os.listdir(stub)):
        full = os.path.join(stub, item)
        if os.path.isdir(full):
            print("  [DIR]  %s" % item)
        else:
            size = os.path.getsize(full)
            print("  [%dKB] %s" % (size // 1024, item))

print()
print("--- 8. Gibt es eine LogiSync Config-Datei die wir bearbeiten koennen? ---")
for root, dirs, files in os.walk(r"C:\ProgramData\Logitech\LogiSync"):
    for f in files:
        path = os.path.join(root, f)
        size = os.path.getsize(path)
        print("  [%d Bytes] %s" % (size, path))

print()
print("FERTIG!")
