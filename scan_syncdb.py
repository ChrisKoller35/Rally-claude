"""Untersucht die Logitech Sync SQLite-Datenbanken."""
import sqlite3
import os

def scan_db(path):
    print("=== %s ===" % os.path.basename(path))
    if not os.path.exists(path):
        print("  Datei nicht gefunden!")
        return
    try:
        conn = sqlite3.connect(path)
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cur.fetchall()
        print("Tabellen: %s" % [t[0] for t in tables])
        
        for (table_name,) in tables:
            print()
            print("--- Tabelle: %s ---" % table_name)
            cur.execute('SELECT * FROM "%s" LIMIT 20' % table_name)
            rows = cur.fetchall()
            cols = [d[0] for d in cur.description]
            print("Spalten: %s" % cols)
            for row in rows:
                # Truncate long values
                display = []
                for val in row:
                    s = str(val)
                    if len(s) > 200:
                        s = s[:200] + "..."
                    display.append(s)
                print("  %s" % display)
        
        conn.close()
    except Exception as e:
        print("FEHLER: %s" % e)

scan_db(r"C:\ProgramData\Logitech\LogiSync\sync.db")
print()
scan_db(r"C:\ProgramData\Logitech\LogiSync\LogiSyncCoreServiceStorage.db")
