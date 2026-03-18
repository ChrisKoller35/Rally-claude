"""
rightsight_ws_client.py - LogiSync WebSocket client for RightSight control.

Connects to the LogiSync WebSocket API (wss://127.0.0.1:9506) and sends
Protobuf-encoded messages to enable or disable RightSight on Logitech
Rally Camera devices.

KEY INSIGHT: The RightSight API only works for ~15 seconds after USB connect.
After that, CropAssistIsEnabled returns error 40400 and all commands fail.
So we must either:
  1. Time our command during the initialization window, or
  2. Monitor for device events and send immediately after LogiSync enables

Wire protocol: Binary Protobuf over WSS (not JSON - the JSON in logs is
just the Proxy's internal logging format).

Dependencies: websockets (pip install websockets)
"""

import asyncio
import ssl
import struct
import time
import uuid as uuid_mod
import json

import websockets


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

LOGISYNC_WS_URL = "wss://127.0.0.1:9506"

# Rally system product UUID (from LogiSync logs - varies per USB port)
DEFAULT_PRODUCT_UUID = "usb|vid=46d|pid=88b|location=6de23f302"
CAMERA_SERIAL = "404ED540"


# ---------------------------------------------------------------------------
# Protobuf encoding helpers
# ---------------------------------------------------------------------------

def _varint(v):
    parts = []
    while v > 0x7F:
        parts.append((v & 0x7F) | 0x80)
        v >>= 7
    parts.append(v & 0x7F)
    return bytes(parts)

def _tag(fn, wt):
    return _varint((fn << 3) | wt)

def _varint_field(fn, v):
    return _tag(fn, 0) + _varint(v)

def _double_field(fn, v):
    return _tag(fn, 1) + struct.pack('<d', v)

def _bytes_field(fn, d):
    return _tag(fn, 2) + _varint(len(d)) + d

def _string_field(fn, s):
    return _bytes_field(fn, s.encode('utf-8'))

def _submsg_field(fn, inner):
    return _bytes_field(fn, inner)


# ---------------------------------------------------------------------------
# Protobuf decoding helpers
# ---------------------------------------------------------------------------

def _decode_varint(data, offset):
    result = 0
    shift = 0
    while offset < len(data):
        byte = data[offset]
        offset += 1
        result |= (byte & 0x7F) << shift
        if (byte & 0x80) == 0:
            return result, offset
        shift += 7
    raise ValueError("Truncated varint")


def _decode_fields(data):
    """Decode all protobuf fields, returns list of (field_number, wire_type, value)."""
    fields = []
    offset = 0
    while offset < len(data):
        tag_val, offset = _decode_varint(data, offset)
        fn = tag_val >> 3
        wt = tag_val & 0x07
        if wt == 0:
            v, offset = _decode_varint(data, offset)
            fields.append((fn, wt, v))
        elif wt == 1:
            v = data[offset:offset + 8]
            offset += 8
            fields.append((fn, wt, v))
        elif wt == 2:
            length, offset = _decode_varint(data, offset)
            v = data[offset:offset + length]
            offset += length
            fields.append((fn, wt, v))
        elif wt == 5:
            v = data[offset:offset + 4]
            offset += 4
            fields.append((fn, wt, v))
        else:
            break
    return fields


def _extract_strings(data):
    """Extract all readable ASCII strings from binary data."""
    strings = []
    i = 0
    while i < len(data):
        if 32 <= data[i] < 127:
            start = i
            while i < len(data) and 32 <= data[i] < 127:
                i += 1
            s = data[start:i].decode('ascii')
            if len(s) >= 3:
                strings.append(s)
        else:
            i += 1
    return strings


def _parse_response(data):
    """Parse a protobuf response, extract error info if present."""
    result = {"success": False, "error_code": None, "error_message": None, "strings": []}
    result["strings"] = _extract_strings(data)

    try:
        top = _decode_fields(data)
        for fn, wt, v in top:
            if fn == 4 and wt == 2:  # response field
                resp_fields = _decode_fields(v)
                for rfn, rwt, rv in resp_fields:
                    if rfn == 5 and rwt == 2:  # videoSettingsResponse
                        vs_fields = _decode_fields(rv)
                        for vfn, vwt, vv in vs_fields:
                            if vfn == 1 and vwt == 2:  # setRightSightConfigurationResponse
                                sr_fields = _decode_fields(vv)
                                has_error = False
                                for sfn, swt, sv in sr_fields:
                                    if sfn == 1 and swt == 2:  # errors sub-message
                                        err_fields = _decode_fields(sv)
                                        for efn, ewt, ev in err_fields:
                                            if efn == 1 and ewt == 0:
                                                result["error_code"] = ev
                                                has_error = True
                                            elif efn == 2 and ewt == 2:
                                                result["error_message"] = ev.decode('utf-8', errors='replace')
                                                has_error = True
                                if not has_error:
                                    result["success"] = True
    except Exception as e:
        result["parse_error"] = str(e)

    return result


# ---------------------------------------------------------------------------
# SSL context
# ---------------------------------------------------------------------------

def _make_ssl_context():
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


# ---------------------------------------------------------------------------
# Message construction
# ---------------------------------------------------------------------------

def _build_set_rightsight_message(enabled, product_uuid, product_model=20, mode=0):
    """
    Build LogiSyncMessage protobuf to set RightSight.

    Structure:
      LogiSyncMessage {
        field 1: Header {timestamp, userContext, guid, status}
        field 3: Request {
          field 5: VideoSettingsRequest {
            field 1: SetRightSightConfigurationRequest {
              field 1: productUuid (string)
              field 2: productModel (int32)
              field 3: enabled (bool)
              field 4: mode (int32)
            }
          }
        }
      }
    """
    inner = b''
    inner += _string_field(1, product_uuid)
    inner += _varint_field(2, product_model)
    inner += _varint_field(3, 1 if enabled else 0)
    inner += _varint_field(4, mode)

    video_settings = _submsg_field(1, inner)
    request = _submsg_field(5, video_settings)

    header = b''
    header += _double_field(1, time.time() * 1000.0)
    header += _string_field(2, "rally-claude-client")
    header += _string_field(3, str(uuid_mod.uuid4()))
    header += _varint_field(4, 0)

    return _submsg_field(1, header) + _submsg_field(3, request)


# ---------------------------------------------------------------------------
# Core send function
# ---------------------------------------------------------------------------

async def _send_command(ws, enabled, product_uuid, product_model=20):
    """Send a RightSight command and wait for response."""
    action = "aktivieren" if enabled else "deaktivieren"
    msg = _build_set_rightsight_message(enabled, product_uuid, product_model)
    await ws.send(msg)

    # Wait for response (skip binary pings)
    deadline = time.time() + 10.0
    while time.time() < deadline:
        try:
            resp = await asyncio.wait_for(ws.recv(), timeout=deadline - time.time())
        except asyncio.TimeoutError:
            return {"success": False, "message": f"Timeout beim {action}."}

        if not isinstance(resp, bytes) or len(resp) < 15:
            continue  # Skip pings

        parsed = _parse_response(resp)
        if parsed.get("error_code"):
            return {
                "success": False,
                "message": f"Fehler {parsed['error_code']}: {parsed.get('error_message', 'Unbekannt')}",
                "error_code": parsed["error_code"],
                "raw_response": resp,
            }
        elif parsed["success"]:
            return {
                "success": True,
                "message": f"RightSight erfolgreich {'aktiviert' if enabled else 'deaktiviert'}!",
                "raw_response": resp,
            }

    return {"success": False, "message": f"Keine Antwort beim {action}."}


# ---------------------------------------------------------------------------
# Direct command (for immediate use - may fail with 40400)
# ---------------------------------------------------------------------------

async def _send_rightsight_direct(enabled, product_uuid=None, ws_url=LOGISYNC_WS_URL, timeout=10.0):
    """Connect, send command directly, return result."""
    if not product_uuid:
        product_uuid = DEFAULT_PRODUCT_UUID

    action = "aktivieren" if enabled else "deaktivieren"

    try:
        ssl_ctx = _make_ssl_context()
        async with websockets.connect(ws_url, ssl=ssl_ctx, open_timeout=timeout) as ws:
            return await _send_command(ws, enabled, product_uuid)
    except ConnectionRefusedError:
        return {"success": False, "message": "Verbindung abgelehnt. Läuft LogiSync?"}
    except OSError as e:
        return {"success": False, "message": f"Netzwerkfehler: {e}"}
    except Exception as e:
        return {"success": False, "message": f"Fehler: {e}"}


# ---------------------------------------------------------------------------
# Monitor mode - waits for USB connect, then disables during init window
# ---------------------------------------------------------------------------

async def monitor_and_disable(
    product_uuid=None,
    ws_url=LOGISYNC_WS_URL,
    delay_after_detect=8.0,
    callback=None,
):
    """
    Monitor WebSocket for device connect events. When the Rally camera
    comes online, wait for LogiSync to do its initial RightSight enable,
    then send our disable command during the ~15 second API window.

    Args:
        product_uuid: Rally system UUID (auto-discovered if None)
        ws_url: WebSocket URL
        delay_after_detect: Seconds to wait after detecting camera before
                           sending disable (must be after LogiSync enables
                           but before API goes to 40400 state)
        callback: Optional function(status_dict) called on events

    Returns result dict when disable succeeds or camera disconnects.
    """
    if not product_uuid:
        product_uuid = DEFAULT_PRODUCT_UUID

    def _notify(msg, **kwargs):
        info = {"message": msg, **kwargs}
        if callback:
            callback(info)
        print(f"[Monitor] {msg}")

    ssl_ctx = _make_ssl_context()

    _notify("Verbinde mit LogiSync...", state="connecting")

    try:
        async with websockets.connect(ws_url, ssl=ssl_ctx, open_timeout=10) as ws:
            _notify("Verbunden. Warte auf Kamera-Verbindung...", state="waiting")

            while True:
                try:
                    msg = await asyncio.wait_for(ws.recv(), timeout=60.0)
                except asyncio.TimeoutError:
                    _notify("Warte weiter...", state="waiting")
                    continue

                if not isinstance(msg, bytes) or len(msg) < 20:
                    continue

                strings = _extract_strings(msg)

                # Look for camera serial in device events
                if CAMERA_SERIAL in strings or "RALLY_CAMERA" in strings:
                    # Check if this is a connect event (not disconnect)
                    if "SYNC_CONNECTION_STATE_ONLINE" in strings or "BolideVideo" in strings:
                        _notify(
                            f"Kamera {CAMERA_SERIAL} erkannt! "
                            f"Warte {delay_after_detect}s bis LogiSync RightSight aktiviert hat...",
                            state="detected"
                        )
                        await asyncio.sleep(delay_after_detect)

                        _notify("Sende Disable-Befehl...", state="disabling")
                        result = await _send_command(ws, False, product_uuid)

                        if result["success"]:
                            _notify("RightSight erfolgreich deaktiviert!", state="success")
                        else:
                            _notify(f"Disable fehlgeschlagen: {result['message']}", state="error")
                            # Try once more immediately
                            _notify("Versuche erneut...", state="retrying")
                            result = await _send_command(ws, False, product_uuid)
                            if result["success"]:
                                _notify("RightSight beim 2. Versuch deaktiviert!", state="success")
                            else:
                                _notify(f"Auch 2. Versuch fehlgeschlagen: {result['message']}", state="error")

                        return result

    except ConnectionRefusedError:
        return {"success": False, "message": "Verbindung abgelehnt. Läuft LogiSync?"}
    except Exception as e:
        return {"success": False, "message": f"Fehler: {e}"}


# ---------------------------------------------------------------------------
# Public sync API
# ---------------------------------------------------------------------------

def disable_rightsight_sync(product_uuid=None, ws_url=LOGISYNC_WS_URL, timeout=10.0):
    """Synchronous: Try to disable RightSight immediately."""
    return asyncio.run(_send_rightsight_direct(False, product_uuid, ws_url, timeout))


def enable_rightsight_sync(product_uuid=None, ws_url=LOGISYNC_WS_URL, timeout=10.0):
    """Synchronous: Try to enable RightSight immediately."""
    return asyncio.run(_send_rightsight_direct(True, product_uuid, ws_url, timeout))


def monitor_and_disable_sync(product_uuid=None, ws_url=LOGISYNC_WS_URL,
                              delay_after_detect=8.0, callback=None):
    """Synchronous: Monitor for camera connect, then disable RightSight."""
    return asyncio.run(monitor_and_disable(product_uuid, ws_url, delay_after_detect, callback))


# ---------------------------------------------------------------------------
# CLI test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    print("=" * 60)
    print("RightSight WebSocket Client")
    print("=" * 60)

    mode = "direct"
    action = "disable"

    if len(sys.argv) > 1:
        arg = sys.argv[1].lower()
        if arg == "enable":
            action = "enable"
        elif arg == "monitor":
            mode = "monitor"

    if mode == "monitor":
        print("\nMONITOR MODE: Warte auf Kamera-Connect...")
        print("Bitte Kamera ab- und wieder anstecken.")
        print("(Ctrl+C zum Abbrechen)\n")
        result = monitor_and_disable_sync()
    else:
        print(f"\nDIRECT MODE: Versuche RightSight {action}...")
        print(f"Product UUID: {DEFAULT_PRODUCT_UUID}\n")
        if action == "disable":
            result = disable_rightsight_sync()
        else:
            result = enable_rightsight_sync()

    print(f"\n{'='*40}")
    print(f"Ergebnis: {'ERFOLG' if result['success'] else 'FEHLER'}")
    print(f"Message:  {result['message']}")
    if result.get('error_code'):
        print(f"Error:    {result['error_code']}")
    print("=" * 40)
