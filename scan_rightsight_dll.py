"""
Versuche RightSight direkt ueber die DLL und WebSocket zu deaktivieren.
"""
import ctypes
import os
import sys
import json
import ssl
import time
import struct

def section(title):
    print()
    print("=" * 70)
    print(title)
    print("=" * 70)

# 1. RightSightAPI.dll Exports pruefen
section("1. RIGHTSIGHT DLL EXPORTS")
dll_path = r"C:\Program Files (x86)\Logitech\LogiSync\sync-agent\rightsight\RightSightAPI.dll"

if not os.path.exists(dll_path):
    print("DLL nicht gefunden: %s" % dll_path)
else:
    print("DLL gefunden: %s" % dll_path)
    
    # PE Header parsen um Exports zu finden
    try:
        import struct
        with open(dll_path, "rb") as f:
            # DOS Header
            f.seek(0x3C)
            pe_offset = struct.unpack("<I", f.read(4))[0]
            
            # PE Header
            f.seek(pe_offset + 4 + 20)  # nach PE signature + COFF header
            optional_header_start = f.tell()
            
            # Optional Header - Magic (2 bytes)
            magic = struct.unpack("<H", f.read(2))[0]
            is_pe32plus = (magic == 0x20B)
            
            # Zum Export-Directory RVA
            if is_pe32plus:
                f.seek(optional_header_start + 112)  # Export Table RVA in PE32+
            else:
                f.seek(optional_header_start + 96)  # Export Table RVA in PE32
            
            export_rva = struct.unpack("<I", f.read(4))[0]
            export_size = struct.unpack("<I", f.read(4))[0]
            
            if export_rva == 0:
                print("  Keine Exports gefunden!")
            else:
                print("  Export RVA: 0x%X, Size: %d" % (export_rva, export_size))
                
                # Sections lesen um RVA zu File Offset zu konvertieren
                f.seek(pe_offset + 4 + 16)  # SizeOfOptionalHeader
                size_opt = struct.unpack("<H", f.read(2))[0]
                num_sections_pos = pe_offset + 4 + 2
                f.seek(num_sections_pos)
                num_sections = struct.unpack("<H", f.read(2))[0]
                
                sections_start = optional_header_start + size_opt
                sections = []
                for i in range(num_sections):
                    f.seek(sections_start + i * 40)
                    name = f.read(8).rstrip(b'\x00').decode('ascii', errors='replace')
                    vsize = struct.unpack("<I", f.read(4))[0]
                    vrva = struct.unpack("<I", f.read(4))[0]
                    rsize = struct.unpack("<I", f.read(4))[0]
                    roff = struct.unpack("<I", f.read(4))[0]
                    sections.append((name, vrva, vsize, roff, rsize))
                
                def rva_to_offset(rva):
                    for name, vrva, vsize, roff, rsize in sections:
                        if vrva <= rva < vrva + vsize:
                            return roff + (rva - vrva)
                    return None
                
                export_offset = rva_to_offset(export_rva)
                if export_offset:
                    f.seek(export_offset + 24)  # NumberOfNames
                    num_names = struct.unpack("<I", f.read(4))[0]
                    addr_funcs = struct.unpack("<I", f.read(4))[0]
                    addr_names = struct.unpack("<I", f.read(4))[0]
                    addr_ordinals = struct.unpack("<I", f.read(4))[0]
                    
                    names_offset = rva_to_offset(addr_names)
                    print("  %d exportierte Funktionen:" % num_names)
                    
                    for i in range(num_names):
                        f.seek(names_offset + i * 4)
                        name_rva = struct.unpack("<I", f.read(4))[0]
                        name_offset = rva_to_offset(name_rva)
                        if name_offset:
                            f.seek(name_offset)
                            name = b""
                            while True:
                                c = f.read(1)
                                if c == b'\x00' or not c:
                                    break
                                name += c
                            print("    %s" % name.decode('ascii', errors='replace'))
    except Exception as e:
        print("  PE Parse Fehler: %s" % e)

# 2. Auch RightSightCtl.dll und RightSight.dll pruefen
for dll_name in ["RightSightCtl.dll", "RightSight.dll", "RightSightCore.dll"]:
    dll_p = os.path.join(os.path.dirname(dll_path), dll_name)
    if os.path.exists(dll_p):
        print()
        print("--- %s ---" % dll_name)
        try:
            with open(dll_p, "rb") as f:
                f.seek(0x3C)
                pe_offset = struct.unpack("<I", f.read(4))[0]
                f.seek(pe_offset + 4 + 20)
                optional_header_start = f.tell()
                magic = struct.unpack("<H", f.read(2))[0]
                is_pe32plus = (magic == 0x20B)
                
                if is_pe32plus:
                    f.seek(optional_header_start + 112)
                else:
                    f.seek(optional_header_start + 96)
                
                export_rva = struct.unpack("<I", f.read(4))[0]
                export_size = struct.unpack("<I", f.read(4))[0]
                
                if export_rva == 0:
                    print("  Keine Exports")
                    continue
                
                f.seek(pe_offset + 4 + 16)
                size_opt = struct.unpack("<H", f.read(2))[0]
                num_sections_pos = pe_offset + 4 + 2
                f.seek(num_sections_pos)
                num_sections = struct.unpack("<H", f.read(2))[0]
                
                sections_start = optional_header_start + size_opt
                sections = []
                for i in range(num_sections):
                    f.seek(sections_start + i * 40)
                    name = f.read(8).rstrip(b'\x00').decode('ascii', errors='replace')
                    vsize = struct.unpack("<I", f.read(4))[0]
                    vrva = struct.unpack("<I", f.read(4))[0]
                    rsize = struct.unpack("<I", f.read(4))[0]
                    roff = struct.unpack("<I", f.read(4))[0]
                    sections.append((name, vrva, vsize, roff, rsize))
                
                def rva_to_offset2(rva):
                    for name, vrva, vsize, roff, rsize in sections:
                        if vrva <= rva < vrva + vsize:
                            return roff + (rva - vrva)
                    return None
                
                export_offset = rva_to_offset2(export_rva)
                if export_offset:
                    f.seek(export_offset + 24)
                    num_names = struct.unpack("<I", f.read(4))[0]
                    addr_funcs = struct.unpack("<I", f.read(4))[0]
                    addr_names = struct.unpack("<I", f.read(4))[0]
                    addr_ordinals = struct.unpack("<I", f.read(4))[0]
                    
                    names_offset = rva_to_offset2(addr_names)
                    print("  %d Exports:" % num_names)
                    for i in range(min(num_names, 50)):
                        f.seek(names_offset + i * 4)
                        name_rva = struct.unpack("<I", f.read(4))[0]
                        name_offset = rva_to_offset2(name_rva)
                        if name_offset:
                            f.seek(name_offset)
                            name = b""
                            while True:
                                c = f.read(1)
                                if c == b'\x00' or not c:
                                    break
                                name += c
                            print("    %s" % name.decode('ascii', errors='replace'))
        except Exception as e:
            print("  Fehler: %s" % e)

# 3. WebSocket Test
section("3. WEBSOCKET API TEST (Port 9506)")
try:
    import websocket
    HAS_WS = True
except ImportError:
    HAS_WS = False
    print("websocket-client nicht installiert, installiere...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "websocket-client"],
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    import websocket
    HAS_WS = True

if HAS_WS:
    try:
        # Verbinde zu LogiSync Proxy WebSocket
        ws = websocket.create_connection(
            "wss://127.0.0.1:9506",
            sslopt={"cert_reqs": ssl.CERT_NONE},
            timeout=5
        )
        print("WebSocket verbunden!")
        
        # Empfange initiale Nachrichten
        ws.settimeout(2)
        for i in range(5):
            try:
                msg = ws.recv()
                if isinstance(msg, bytes):
                    print("  Empfangen (binary, %d bytes): %s" % (len(msg), msg[:100]))
                else:
                    print("  Empfangen: %s" % str(msg)[:200])
            except:
                break
        
        # Sende RightSight-Anfrage
        import uuid
        request = {
            "header": {
                "guid": str(uuid.uuid4()),
                "timestamp": int(time.time() * 1000),
                "userContext": ""
            },
            "internalApiId": 1,
            "request": {
                "setRightSightSettingRequest": {
                    "serialNumber": "404ED540",
                    "rightSightEnabled": False,
                    "rightSightMode": "off"
                }
            }
        }
        print()
        print("Sende RightSight-Deaktivierung:")
        print("  %s" % json.dumps(request)[:200])
        ws.send(json.dumps(request))
        
        # Antwort abwarten
        ws.settimeout(3)
        try:
            resp = ws.recv()
            print("  Antwort: %s" % str(resp)[:300])
        except:
            print("  Keine Antwort erhalten")
        
        ws.close()
    except Exception as e:
        print("WebSocket Fehler: %s" % e)

# 4. Versuche RightSightAPI.dll direkt zu laden
section("4. RIGHTSIGHT API DLL LADEN")
try:
    # Setze DLL-Suchpfad
    rs_dir = r"C:\Program Files (x86)\Logitech\LogiSync\sync-agent\rightsight"
    os.environ["PATH"] = rs_dir + ";" + os.environ.get("PATH", "")
    os.add_dll_directory(rs_dir)
    
    # Lade die DLL
    rs_api = ctypes.CDLL(dll_path)
    print("RightSightAPI.dll geladen!")
    
    # Versuche bekannte Funktionen aufzurufen
    # CropAssistInit
    try:
        init_func = rs_api.CropAssistInit
        print("  CropAssistInit gefunden!")
    except:
        print("  CropAssistInit nicht gefunden")
    
    try:
        set_enabled = rs_api.CropAssistSetEnabled
        print("  CropAssistSetEnabled gefunden!")
    except:
        print("  CropAssistSetEnabled nicht gefunden")
        
except Exception as e:
    print("DLL laden fehlgeschlagen: %s" % e)

print()
print("FERTIG!")
