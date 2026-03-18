"""
Rally RightSight Controller - Tkinter GUI
Automatically disables RightSight on startup.
Manual enable/disable buttons available.
"""

import tkinter as tk
from tkinter import messagebox, scrolledtext
import threading
import time
from datetime import datetime

# Try importing the WebSocket client module
try:
    import rightsight_ws_client
    WS_CLIENT_AVAILABLE = True
    WS_IMPORT_ERROR = None
except ImportError as e:
    WS_CLIENT_AVAILABLE = False
    WS_IMPORT_ERROR = str(e)

try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False


class RightSightApp:
    """Main application class for the RightSight Controller GUI."""

    # Theme colors
    BG = "#1a1a2e"
    PANEL = "#16213e"
    ACCENT = "#0f3460"
    RED = "#e94560"
    GREEN = "#4ecca3"
    YELLOW = "#f0c929"
    ORANGE = "#ff8c42"
    TEXT = "#eaeaea"
    DIM = "#8899aa"

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Rally RightSight Controller")
        self.root.configure(bg=self.BG)
        self.root.resizable(False, False)

        # Window size and centering
        win_w, win_h = 480, 650
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        x = (screen_w - win_w) // 2
        y = (screen_h - win_h) // 2
        self.root.geometry(f"{win_w}x{win_h}+{x}+{y}")

        self._command_running = False
        self._build_ui()

        # Check for missing dependencies on startup
        if not WS_CLIENT_AVAILABLE:
            self.root.after(200, self._show_import_error)
        else:
            # Auto-disable on startup
            self.root.after(500, self._auto_disable)

    def _show_import_error(self):
        if "websockets" in (WS_IMPORT_ERROR or ""):
            messagebox.showerror(
                "Fehlende Abhängigkeit",
                "Das Modul 'websockets' ist nicht installiert.\n\n"
                "Bitte ausführen:\n  pip install websockets\n\n"
                "Dann die Anwendung neu starten."
            )
        else:
            messagebox.showerror(
                "Import-Fehler",
                f"rightsight_ws_client konnte nicht importiert werden:\n\n"
                f"{WS_IMPORT_ERROR}"
            )
        self._set_status("Modul nicht verfügbar", self.RED)

    def _build_ui(self):
        font_normal = ("Segoe UI", 10)
        font_small = ("Segoe UI", 9)
        font_large = ("Segoe UI", 16, "bold")
        font_button_big = ("Segoe UI", 14, "bold")
        font_button = ("Segoe UI", 11)

        # Title
        tk.Label(
            self.root, text="Rally RightSight Controller",
            font=font_large, fg=self.TEXT, bg=self.BG
        ).pack(pady=(18, 4))

        # Status indicator
        self.status_label = tk.Label(
            self.root, text="Status: Starte...",
            font=font_normal, fg=self.YELLOW, bg=self.BG
        )
        self.status_label.pack(pady=(2, 10))

        # === DIRECT MODE ===
        direct_frame = tk.LabelFrame(
            self.root, text="  RightSight Steuerung  ",
            font=font_normal, fg=self.TEXT, bg=self.PANEL,
            padx=12, pady=8
        )
        direct_frame.pack(fill="x", padx=18, pady=(0, 8))

        tk.Label(
            direct_frame,
            text="Beim Start wird RightSight automatisch deaktiviert.\n"
                 "Manuell umschalten mit den Buttons:",
            font=font_small, fg=self.DIM, bg=self.PANEL, justify="left"
        ).pack(anchor="w")

        btn_row = tk.Frame(direct_frame, bg=self.PANEL)
        btn_row.pack(fill="x", pady=(6, 2))

        self.btn_disable = tk.Button(
            btn_row, text="DEAKTIVIEREN",
            font=font_button_big, fg="#ffffff", bg=self.RED,
            activebackground="#c0374d",
            relief="flat", cursor="hand2", padx=8, pady=6,
            command=self._on_disable
        )
        self.btn_disable.pack(side="left", fill="x", expand=True, padx=(0, 4))

        self.btn_enable = tk.Button(
            btn_row, text="Aktivieren",
            font=font_button, fg=self.BG, bg=self.GREEN,
            activebackground="#3daa88",
            relief="flat", cursor="hand2", padx=8, pady=4,
            command=self._on_enable
        )
        self.btn_enable.pack(side="left", fill="x", expand=True, padx=(4, 0))

        # === CAMERA TEST (PTZ) ===
        ptz_frame = tk.LabelFrame(
            self.root, text="  Kamera-Test  ",
            font=font_normal, fg=self.TEXT, bg=self.PANEL,
            padx=12, pady=8
        )
        ptz_frame.pack(fill="x", padx=18, pady=(0, 8))

        tk.Label(
            ptz_frame,
            text="Bewegt die Kamera kurz nach oben und zurück.",
            font=font_small, fg=self.DIM, bg=self.PANEL, justify="left"
        ).pack(anchor="w")

        self.btn_ptz_test = tk.Button(
            ptz_frame, text="Kamera bewegen",
            font=font_button, fg="#ffffff", bg="#5b6abf",
            activebackground="#4a59a0",
            relief="flat", cursor="hand2", padx=8, pady=4,
            command=self._on_ptz_test
        )
        self.btn_ptz_test.pack(fill="x", pady=(6, 2))

        # === CAMERA ACCESS BLOCK ===
        cam_frame = tk.LabelFrame(
            self.root, text="  Kamera-Zugriff (Windows)  ",
            font=font_normal, fg=self.TEXT, bg=self.PANEL,
            padx=12, pady=8
        )
        cam_frame.pack(fill="x", padx=18, pady=(0, 8))

        tk.Label(
            cam_frame,
            text="Belegt die Kamera exklusiv — andere Apps (Teams,\n"
                 "Zoom) können nicht zugreifen. Vor Call freigeben!",
            font=font_small, fg=self.DIM, bg=self.PANEL, justify="left"
        ).pack(anchor="w")

        self.btn_cam_toggle = tk.Button(
            cam_frame, text="Kamera SPERREN",
            font=font_button, fg="#ffffff", bg=self.RED,
            activebackground="#c0374d",
            relief="flat", cursor="hand2", padx=8, pady=4,
            command=self._on_cam_toggle
        )
        self.btn_cam_toggle.pack(fill="x", pady=(6, 2))

        self._cam_blocked = False
        self._cam_capture = None  # Holds the OpenCV capture when locked

        # Info
        tk.Label(
            self.root,
            text="Kamera: Logi Rally Camera | Serial: 404ED540",
            font=font_small, fg=self.DIM, bg=self.BG
        ).pack(pady=(2, 4))

        # Log area
        log_frame = tk.Frame(self.root, bg=self.PANEL, bd=1, relief="solid")
        log_frame.pack(fill="both", expand=True, padx=18, pady=(0, 14))

        self.log_text = scrolledtext.ScrolledText(
            log_frame, font=("Consolas", 8), fg=self.DIM, bg=self.PANEL,
            insertbackground=self.DIM, relief="flat", height=7, wrap="word",
            state="disabled", borderwidth=4
        )
        self.log_text.pack(fill="both", expand=True)

        self._log("App gestartet. Sende Auto-Disable...")

    def _set_status(self, text, color):
        self.status_label.config(text=f"Status: {text}", fg=color)

    def _log(self, message):
        ts = datetime.now().strftime("%H:%M:%S")
        self.log_text.config(state="normal")
        self.log_text.insert("end", f"[{ts}] {message}\n")
        self.log_text.see("end")
        self.log_text.config(state="disabled")

    def _set_buttons(self, enabled):
        state = "normal" if enabled else "disabled"
        self.btn_disable.config(state=state)
        self.btn_enable.config(state=state)

    # --- Auto disable on startup ---

    def _auto_disable(self):
        self._set_buttons(False)
        self._set_status("Sende Disable...", self.YELLOW)
        thread = threading.Thread(target=self._run_auto_disable, daemon=True)
        thread.start()

    def _run_auto_disable(self):
        """Background: continuously try disable, retry every 5s."""
        was_connected = False
        while True:
            result = rightsight_ws_client.disable_rightsight_sync()
            if result.get("success"):
                if not was_connected:
                    self.root.after(0, self._on_camera_connected)
                    was_connected = True
            else:
                if was_connected:
                    self.root.after(0, self._on_camera_disconnected)
                    was_connected = False
                elif not was_connected:
                    self.root.after(0, self._on_camera_waiting)
            time.sleep(5)

    def _on_camera_connected(self):
        self._set_buttons(True)
        self._set_status("RightSight AUS", self.GREEN)
        self._log("RightSight automatisch deaktiviert!")

    def _on_camera_disconnected(self):
        self._set_status("Kamera getrennt", self.RED)
        self._log("Kamera nicht mehr erreichbar. Warte auf Reconnect...")

    def _on_camera_waiting(self):
        self._set_status("Warte auf Kamera...", self.ORANGE)

    # --- Direct mode ---

    def _on_disable(self):
        if not WS_CLIENT_AVAILABLE:
            self._show_import_error()
            return
        self._run_direct("disable")

    def _on_enable(self):
        if not WS_CLIENT_AVAILABLE:
            self._show_import_error()
            return
        self._run_direct("enable")

    def _run_direct(self, action):
        if self._command_running:
            return
        self._command_running = True
        self._set_buttons(False)
        self._set_status("Sende...", self.YELLOW)

        label = "Deaktivieren" if action == "disable" else "Aktivieren"
        self._log(f"{label}-Befehl wird gesendet...")

        thread = threading.Thread(
            target=self._execute_direct, args=(action,), daemon=True
        )
        thread.start()

    def _execute_direct(self, action):
        try:
            if action == "disable":
                result = rightsight_ws_client.disable_rightsight_sync()
            else:
                result = rightsight_ws_client.enable_rightsight_sync()
            self.root.after(0, self._on_direct_complete, action, result)
        except Exception as e:
            self.root.after(0, self._on_direct_error, str(e))

    def _on_direct_complete(self, action, result):
        self._command_running = False
        self._set_buttons(True)

        if result.get("success"):
            if action == "disable":
                self._set_status("RightSight AUS", self.GREEN)
            else:
                self._set_status("RightSight AN", self.ORANGE)
            self._log(result["message"])
        else:
            self._set_status("Fehler", self.RED)
            self._log(f"Fehler: {result['message']}")

    def _on_direct_error(self, error_msg):
        self._command_running = False
        self._set_buttons(True)
        self._set_status("Fehler", self.RED)
        self._log(f"Fehler: {error_msg}")

    # --- PTZ test ---

    def _on_ptz_test(self):
        if not CV2_AVAILABLE:
            messagebox.showerror(
                "Fehlende Abhängigkeit",
                "Das Modul 'cv2' (OpenCV) ist nicht installiert.\n\n"
                "Bitte ausführen:\n  pip install opencv-python\n\n"
                "Dann die Anwendung neu starten."
            )
            return
        self.btn_ptz_test.config(state="disabled")
        self._log("Kamera-Test: Tilt hoch...")
        thread = threading.Thread(target=self._run_ptz_test, daemon=True)
        thread.start()

    def _find_rally_camera(self):
        """Find the Rally Camera by checking for Zoom=269 on DSHOW devices."""
        for dev_id in range(5):
            cap = cv2.VideoCapture(dev_id, cv2.CAP_DSHOW)
            if not cap.isOpened():
                continue
            zoom = cap.get(cv2.CAP_PROP_ZOOM)
            if zoom > 200:  # Rally Camera has zoom ~269, laptops have 100
                return cap, dev_id
            cap.release()
        return None, -1

    def _run_ptz_test(self):
        try:
            cap, dev_id = self._find_rally_camera()
            if cap is None:
                self.root.after(0, self._on_ptz_done, False,
                                "Rally Camera nicht gefunden (kein DSHOW-Device mit Zoom>200)")
                return

            self.root.after(0, self._log, f"Rally Camera auf Device {dev_id} gefunden")

            # Save original tilt
            original_tilt = cap.get(cv2.CAP_PROP_TILT)

            # Tilt up
            cap.set(cv2.CAP_PROP_TILT, original_tilt + 15)
            time.sleep(1.5)

            # Tilt back
            cap.set(cv2.CAP_PROP_TILT, original_tilt)
            time.sleep(0.5)

            cap.release()
            self.root.after(0, self._on_ptz_done, True, "Kamera-Test abgeschlossen!")
        except Exception as e:
            self.root.after(0, self._on_ptz_done, False, str(e))

    def _on_ptz_done(self, success, message):
        self.btn_ptz_test.config(state="normal")
        self._log(message)

    # --- Camera access block ---

    def _on_cam_toggle(self):
        if not CV2_AVAILABLE:
            messagebox.showerror(
                "Fehlende Abhängigkeit",
                "Das Modul 'cv2' (OpenCV) ist nicht installiert.\n\n"
                "Bitte ausführen:\n  pip install opencv-python"
            )
            return

        if self._cam_blocked:
            # Release camera
            if self._cam_capture is not None:
                self._cam_capture.release()
                self._cam_capture = None
            self._cam_blocked = False
            self.btn_cam_toggle.config(text="Kamera SPERREN", bg=self.RED)
            self._log("Kamera freigegeben — Apps können wieder zugreifen")
        else:
            # Grab camera exclusively in background thread
            self.btn_cam_toggle.config(state="disabled")
            self._log("Kamera wird gesperrt...")
            thread = threading.Thread(target=self._lock_camera, daemon=True)
            thread.start()

    def _lock_camera(self):
        """Background: open camera, wait for init, reset position."""
        # Try up to 3 times with short delay
        cap, dev_id = None, -1
        for attempt in range(3):
            cap, dev_id = self._find_rally_camera()
            if cap is not None:
                break
            time.sleep(1)
        if cap is None:
            self.root.after(0, self._log, "Rally Camera nicht gefunden!")
            self.root.after(0, lambda: self.btn_cam_toggle.config(state="normal"))
            return

        # Read original position right after open
        original_tilt = cap.get(cv2.CAP_PROP_TILT)
        original_pan = cap.get(cv2.CAP_PROP_PAN)

        # Wait for camera to finish initializing (it moves during init)
        time.sleep(2)

        # Reset to original position
        cap.set(cv2.CAP_PROP_TILT, original_tilt)
        cap.set(cv2.CAP_PROP_PAN, original_pan)
        time.sleep(0.5)

        self._cam_capture = cap
        def _update_ui():
            self._cam_blocked = True
            self.btn_cam_toggle.config(
                text="Kamera FREIGEBEN", bg=self.GREEN, state="normal"
            )
            self._log(f"Kamera gesperrt (Device {dev_id}) — andere Apps blockiert")
        self.root.after(0, _update_ui)


def main():
    root = tk.Tk()
    app = RightSightApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
