"""
Logitech Sync Untersuchung
Wo sind die Config-Dateien? Kann man RightSight darueber abschalten?
"""

import subprocess
import os
import json
import glob

def section(title):
    print()
    print("=" * 70)
    print(title)
    print("=" * 70)

def safe_read(path, max_lines=50):
    """Liest eine Datei sicher und gibt Inhalt zurueck."""
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
        if len(lines) > max_lines:
            return "".join(lines[:max_lines]) + "\n... (%d weitere Zeilen)" % (len(lines) - max_lines)
        return "".join(lines)
    except Exception as e:
        return "FEHLER: %s" % e

# 1. Logitech Sync Prozesse - Details
section("1. LOGITECH SYNC PROZESSE - DETAILS")
try:
    result = subprocess.run(
        ["powershell", "-Command",
         "Get-Process | Where-Object { $_.ProcessName -like '*Logi*' } | Select-Object ProcessName,Id,Path,StartTime,Company | Format-List"],
        capture_output=True, text=True, timeout=10
    )
    print(result.stdout)
except Exception as e:
    print("FEHLER: %s" % e)

# 2. Logitech Sync Installationsort
section("2. LOGITECH SYNC INSTALLATIONSORT")
search_paths = [
    os.path.expandvars(r"%ProgramFiles%\Logitech"),
    os.path.expandvars(r"%ProgramFiles%\LogiSync"),
    os.path.expandvars(r"%ProgramFiles(x86)%\Logitech"),
    os.path.expandvars(r"%LOCALAPPDATA%\Logitech"),
    os.path.expandvars(r"%APPDATA%\Logitech"),
    os.path.expandvars(r"%ProgramData%\Logitech"),
    os.path.expandvars(r"%LOCALAPPDATA%\LogiSync"),
    os.path.expandvars(r"%APPDATA%\LogiSync"),
    os.path.expandvars(r"%ProgramData%\LogiSync"),
    os.path.expandvars(r"%ProgramFiles%\Logi"),
    os.path.expandvars(r"%LOCALAPPDATA%\Logi"),
    os.path.expandvars(r"%APPDATA%\Logi"),
    os.path.expandvars(r"%ProgramData%\Logi"),
]

found_dirs = []
for p in search_paths:
    if os.path.exists(p):
        print("GEFUNDEN: %s" % p)
        found_dirs.append(p)
        try:
            for item in os.listdir(p):
                full = os.path.join(p, item)
                typ = "[DIR]" if os.path.isdir(full) else "[FILE]"
                print("  %s %s" % (typ, item))
        except Exception as e:
            print("  Kann nicht lesen: %s" % e)
    else:
        print("  nicht vorhanden: %s" % p)

# 3. Alle Logitech-Dateien auf dem System finden (via where.exe der Prozesse)
section("3. LOGITECH SYNC EXE PFADE")
try:
    result = subprocess.run(
        ["powershell", "-Command",
         "Get-Process | Where-Object { $_.ProcessName -like '*LogiSync*' } | ForEach-Object { $_.Path } | Sort-Object -Unique"],
        capture_output=True, text=True, timeout=10
    )
    print(result.stdout if result.stdout.strip() else "(keine Pfade gefunden)")
    
    # Fuer jeden Pfad: den Ordner auflisten
    for exe_path in result.stdout.strip().split("\n"):
        exe_path = exe_path.strip()
        if exe_path and os.path.exists(exe_path):
            folder = os.path.dirname(exe_path)
            print("\nInhalt von: %s" % folder)
            try:
                for item in sorted(os.listdir(folder)):
                    full = os.path.join(folder, item)
                    typ = "[DIR]" if os.path.isdir(full) else "[FILE %dKB]" % (os.path.getsize(full) // 1024)
                    print("  %s %s" % (typ, item))
            except:
                pass
except Exception as e:
    print("FEHLER: %s" % e)

# 4. Config/JSON/XML Dateien in Logitech-Ordnern
section("4. KONFIGURATIONSDATEIEN")
for base_dir in found_dirs:
    for root, dirs, files in os.walk(base_dir):
        for fname in files:
            ext = os.path.splitext(fname)[1].lower()
            if ext in [".json", ".xml", ".ini", ".cfg", ".config", ".yaml", ".yml", ".toml", ".conf", ".db", ".sqlite"]:
                full_path = os.path.join(root, fname)
                size = os.path.getsize(full_path)
                print("\n--- %s (%d Bytes) ---" % (full_path, size))
                if ext in [".json", ".xml", ".ini", ".cfg", ".config", ".yaml", ".yml", ".toml", ".conf"]:
                    content = safe_read(full_path, max_lines=80)
                    # Suche nach RightSight
                    if "rightsight" in content.lower() or "right_sight" in content.lower() or "autoframe" in content.lower() or "auto_frame" in content.lower() or "speakertrack" in content.lower():
                        print("*** RIGHTSIGHT REFERENZ GEFUNDEN! ***")
                    print(content)
                else:
                    print("(Binaer-Datei, uebersprungen)")

# 5. Registry nach Logitech Sync Einstellungen
section("5. REGISTRY - LOGITECH SYNC")
reg_paths = [
    r"HKLM\Software\Logitech",
    r"HKCU\Software\Logitech",
    r"HKLM\Software\LogiSync",
    r"HKCU\Software\LogiSync",
    r"HKLM\Software\Logi",
    r"HKCU\Software\Logi",
]
for reg_path in reg_paths:
    try:
        result = subprocess.run(
            ["reg", "query", reg_path, "/s"],
            capture_output=True, text=True, timeout=10
        )
        if result.stdout.strip():
            print("GEFUNDEN: %s" % reg_path)
            # Filter fuer RightSight
            lines = result.stdout.strip().split("\n")
            if len(lines) > 100:
                print("(%d Zeilen, zeige erste 100)" % len(lines))
                print("\n".join(lines[:100]))
            else:
                print(result.stdout)
            
            # RightSight suchen
            lower = result.stdout.lower()
            if "rightsight" in lower or "autoframe" in lower or "auto_frame" in lower:
                print("\n*** RIGHTSIGHT REFERENZ IN REGISTRY! ***")
    except:
        pass

# 6. Logitech Sync Services
section("6. LOGITECH SERVICES")
try:
    result = subprocess.run(
        ["powershell", "-Command",
         "Get-Service | Where-Object { $_.DisplayName -like '*Logi*' -or $_.Name -like '*Logi*' } | Format-List Name,DisplayName,Status,StartType"],
        capture_output=True, text=True, timeout=10
    )
    print(result.stdout if result.stdout.strip() else "(keine Logitech-Services)")
except:
    pass

# 7. Autostart-Eintraege
section("7. AUTOSTART - LOGITECH")
try:
    result = subprocess.run(
        ["powershell", "-Command",
         r"Get-ItemProperty 'HKLM:\Software\Microsoft\Windows\CurrentVersion\Run','HKCU:\Software\Microsoft\Windows\CurrentVersion\Run' 2>$null | Format-List"],
        capture_output=True, text=True, timeout=10
    )
    lower = result.stdout.lower()
    if "logi" in lower:
        print("Logitech Autostart-Eintraege:")
        for line in result.stdout.split("\n"):
            if "logi" in line.lower() or ":" in line:
                print("  %s" % line.strip())
    else:
        print("(keine Logitech Autostart-Eintraege in Run-Keys)")
except:
    pass

# Scheduled Tasks
try:
    result = subprocess.run(
        ["powershell", "-Command",
         "Get-ScheduledTask | Where-Object { $_.TaskName -like '*Logi*' } | Format-List TaskName,State,TaskPath"],
        capture_output=True, text=True, timeout=10
    )
    if result.stdout.strip():
        print("\nScheduled Tasks:")
        print(result.stdout)
except:
    pass

print("\n\nFERTIG!")
