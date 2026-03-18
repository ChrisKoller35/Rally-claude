"""
LogiSync API und Frontend untersuchen.
LogiSync hat offene Ports - vielleicht koennen wir RightSight darueber steuern.
"""
import subprocess
import os
import json
import urllib.request
import ssl

def section(title):
    print()
    print("=" * 70)
    print(title)
    print("=" * 70)

# 1. Frontend Ordner untersuchen (wahrscheinlich Electron App)
section("1. FRONTEND ORDNER")
frontend = r"C:\Program Files (x86)\Logitech\LogiSync\frontend"
if os.path.exists(frontend):
    for root, dirs, files in os.walk(frontend):
        level = root.replace(frontend, "").count(os.sep)
        indent = "  " * level
        print("%s[%s]" % (indent, os.path.basename(root)))
        if level < 3:  # Nicht zu tief
            for f in sorted(files)[:30]:
                size = os.path.getsize(os.path.join(root, f))
                print("%s  %s (%dKB)" % (indent, f, size // 1024))
            if len(files) > 30:
                print("%s  ... und %d weitere" % (indent, len(files) - 30))

# 2. sync-agent Ordner
section("2. SYNC-AGENT ORDNER")
agent = r"C:\Program Files (x86)\Logitech\LogiSync\sync-agent"
if os.path.exists(agent):
    for root, dirs, files in os.walk(agent):
        level = root.replace(agent, "").count(os.sep)
        indent = "  " * level
        print("%s[%s]" % (indent, os.path.basename(root)))
        if level < 2:
            for f in sorted(files)[:20]:
                size = os.path.getsize(os.path.join(root, f))
                print("%s  %s (%dKB)" % (indent, f, size // 1024))
            if len(files) > 20:
                print("%s  ... und %d weitere" % (indent, len(files) - 20))

# 3. API Ports testen
section("3. API PORTS TESTEN")
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

for port in [9506, 6110, 5835]:
    print()
    print("--- Port %d ---" % port)
    for proto in ["http", "https"]:
        for path in ["/", "/api", "/api/v1", "/status", "/health", "/devices", "/api/devices", "/api/rightsight", "/rightsight"]:
            url = "%s://127.0.0.1:%d%s" % (proto, port, path)
            try:
                req = urllib.request.Request(url, method="GET")
                req.add_header("Accept", "application/json")
                if proto == "https":
                    resp = urllib.request.urlopen(req, timeout=2, context=ctx)
                else:
                    resp = urllib.request.urlopen(req, timeout=2)
                data = resp.read().decode("utf-8", errors="replace")
                print("  %s -> %d: %s" % (url, resp.status, data[:200]))
            except urllib.error.HTTPError as e:
                body = e.read().decode("utf-8", errors="replace")[:100] if hasattr(e, "read") else ""
                print("  %s -> HTTP %d: %s" % (url, e.code, body))
            except Exception as e:
                err = str(e)
                if "timed out" not in err and "Connection refused" not in err and "actively refused" not in err:
                    print("  %s -> %s" % (url, err[:80]))

# 4. Logs nach API-Hinweisen durchsuchen
section("4. LOGS NACH API/RIGHTSIGHT HINWEISEN")
log_files = [
    r"C:\ProgramData\Logitech\LogiSync\LogiSyncHandler.log",
    r"C:\ProgramData\Logitech\LogiSync\LogiSyncMiddleware.log",
    r"C:\ProgramData\Logitech\LogiSync\LogiSyncProxy.log",
]

keywords = ["rightsight", "cropassist", "crop_assist", "saca", "autoframe", "auto_frame", 
            "right_sight", "api", "grpc", "endpoint", "REST", "websocket"]

for log_path in log_files:
    try:
        with open(log_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        
        found = []
        for kw in keywords:
            if kw.lower() in content.lower():
                found.append(kw)
        
        if found:
            print()
            print("%s:" % os.path.basename(log_path))
            print("  Keywords gefunden: %s" % found)
            
            # Zeilen mit Keywords zeigen
            for line in content.split("\n"):
                lower = line.lower()
                for kw in found:
                    if kw.lower() in lower:
                        print("  >> %s" % line.strip()[:200])
                        break
    except Exception as e:
        print("  %s: FEHLER %s" % (os.path.basename(log_path), e))

# 5. SQLite DBs schreibbar?
section("5. SQLITE SCHREIBTEST")
import sqlite3
for db_path in [r"C:\ProgramData\Logitech\LogiSync\sync.db", 
                r"C:\ProgramData\Logitech\LogiSync\LogiSyncCoreServiceStorage.db"]:
    print()
    print(os.path.basename(db_path))
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        # Versuch: Temporaere Tabelle erstellen und loeschen
        cur.execute("CREATE TABLE IF NOT EXISTS _test_write (x INT)")
        cur.execute("DROP TABLE _test_write")
        conn.commit()
        print("  SCHREIBBAR!")
        conn.close()
    except Exception as e:
        print("  NICHT SCHREIBBAR: %s" % e)

print()
print("FERTIG!")
