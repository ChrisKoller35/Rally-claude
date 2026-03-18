"""
Rally Kamera Stopper v3
Unterbricht das automatische Bewegen der Logitech Rally PTZ Kamera.

Zwei Modi:
  MANUELL: HID Stop-Befehle (1x/Sek) + UVC PTZ Lock (Dauer-Stopp)
  ECO:     HID Stop-Befehle (1x/3Sek) + UVC PTZ Lock (weniger Belastung)
"""

import tkinter as tk
import threading
import time
import sys

try:
    import hid
except ImportError:
    print("FEHLER: hidapi ist nicht installiert!")
    print("Bitte tippe: pip install hidapi")
    input("\nDruecke Enter zum Beenden...")
    sys.exit(1)

try:
    import cv2
    CV2_VERFUEGBAR = True
except ImportError:
    CV2_VERFUEGBAR = False


# Logitech Rally Camera
VENDOR_ID = 0x046D
PRODUCT_ID = 0x0881

# HID Collection 0 (Usage Page 0xFF00) - Logitech Protokoll
USAGE_PAGE_MAIN = 0xFF00
REPORT_ID_STOP = 0x0C
STOP_CMD = [REPORT_ID_STOP] + [0x00] * 64


class RallyStopperApp:
    """Stoppt die automatische Kamerabewegung der Logitech Rally."""

    # Modi
    MODE_OFF = "off"
    MODE_MANUAL = "manual"
    MODE_ECO = "eco"

    # Farben
    FARBE_BG = "#1a1a2e"
    FARBE_ROT = "#e94560"
    FARBE_GRUEN = "#4ecca3"
    FARBE_GELB = "#f0c929"
    FARBE_BLAU = "#3a86ff"
    FARBE_TEXT = "#eaeaea"
    FARBE_TEXT_DIM = "#8899aa"
    FARBE_INAKTIV = "#2a2a4a"

    # Intervalle
    MANUAL_INTERVALL = 1.0      # Sekunden zwischen Stop-Befehlen (Manuell)
    ECO_INTERVALL = 3.0         # Sekunden zwischen Stop-Befehlen (Eco)
    RECONNECT_INTERVALL = 5.0   # Sekunden zwischen Reconnect-Versuchen

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Rally Kamera Stopper")
        self.root.geometry("420x380")
        self.root.resizable(False, False)
        self.root.configure(bg=self.FARBE_BG)

        self.hid_device = None
        self.cv2_device = None
        self.cv2_device_idx = None
        self.mode = self.MODE_OFF
        self.worker_thread = None
        self.reconnect_thread = None
        self.befehle_gesendet = 0
        self.ptz_korrekturen = 0
        self.verbunden = False
        self.uvc_verbunden = False
        self.ziel_pan = 0.0
        self.ziel_tilt = 0.0
        self.ziel_zoom = 100.0
        self._lock = threading.Lock()

        self._erstelle_gui()
        # Auto-Connect beim Start
        self.root.after(500, self._auto_connect)

    def _erstelle_gui(self):
        # Titel
        tk.Label(
            self.root,
            text="Rally Kamera Stopper",
            font=("Segoe UI", 18, "bold"),
            fg=self.FARBE_TEXT,
            bg=self.FARBE_BG
        ).pack(pady=(15, 3))

        # Verbindungsstatus
        self.verbindung_label = tk.Label(
            self.root,
            text="Verbinde...",
            font=("Segoe UI", 10),
            fg=self.FARBE_GELB,
            bg=self.FARBE_BG
        )
        self.verbindung_label.pack(pady=(0, 3))

        # UVC Status
        self.uvc_label = tk.Label(
            self.root,
            text="",
            font=("Segoe UI", 9),
            fg=self.FARBE_TEXT_DIM,
            bg=self.FARBE_BG
        )
        self.uvc_label.pack(pady=(0, 8))

        # Modus-Status
        self.status_label = tk.Label(
            self.root,
            text="Bereit",
            font=("Segoe UI", 12, "bold"),
            fg=self.FARBE_TEXT_DIM,
            bg=self.FARBE_BG
        )
        self.status_label.pack(pady=(0, 10))

        # Button-Frame
        btn_frame = tk.Frame(self.root, bg=self.FARBE_BG)
        btn_frame.pack(fill="x", padx=25, pady=(0, 10))

        # Manuell-Button
        self.btn_manual = tk.Button(
            btn_frame,
            text="MANUELL\nStoppen",
            font=("Segoe UI", 14, "bold"),
            bg=self.FARBE_ROT,
            fg="#ffffff",
            activebackground="#ff2244",
            relief="flat",
            cursor="hand2",
            height=3,
            command=self._toggle_manual
        )
        self.btn_manual.pack(side="left", fill="both", expand=True, padx=(0, 5))

        # Eco-Button
        self.btn_eco = tk.Button(
            btn_frame,
            text="ECO\nModus",
            font=("Segoe UI", 14, "bold"),
            bg=self.FARBE_BLAU,
            fg="#ffffff",
            activebackground="#5599ff",
            relief="flat",
            cursor="hand2",
            height=3,
            command=self._toggle_eco
        )
        self.btn_eco.pack(side="right", fill="both", expand=True, padx=(5, 0))

        # Info unter Buttons
        uvc_text = " + PTZ Lock" if CV2_VERFUEGBAR else ""
        tk.Label(
            self.root,
            text="Manuell: 1x/Sek  |  Eco: 1x/3Sek%s" % uvc_text,
            font=("Consolas", 9),
            fg=self.FARBE_TEXT_DIM,
            bg=self.FARBE_BG
        ).pack(pady=(0, 5))

        # Statistik
        self.stats_label = tk.Label(
            self.root,
            text="",
            font=("Consolas", 10),
            fg=self.FARBE_TEXT_DIM,
            bg=self.FARBE_BG
        )
        self.stats_label.pack(pady=(0, 3))

        # Log
        log_frame = tk.Frame(self.root, bg="#0d1117")
        log_frame.pack(fill="both", expand=True, padx=25, pady=(5, 15))

        self.log_text = tk.Text(
            log_frame,
            height=5,
            font=("Consolas", 9),
            bg="#0d1117",
            fg=self.FARBE_TEXT_DIM,
            relief="flat",
            wrap="word"
        )
        self.log_text.pack(fill="both", expand=True)

        # Minimieren statt schliessen
        self.root.protocol("WM_DELETE_WINDOW", self._beenden)

    # --- Logging ---

    def _log(self, text):
        zeitstempel = time.strftime("%H:%M:%S")
        self.log_text.insert("end", "[%s] %s\n" % (zeitstempel, text))
        self.log_text.see("end")
        zeilen = int(self.log_text.index("end-1c").split(".")[0])
        if zeilen > 100:
            self.log_text.delete("1.0", "%d.0" % (zeilen - 100))

    def _log_safe(self, text):
        self.root.after(0, lambda: self._log(text))

    # --- HID Verbindung ---

    def _auto_connect(self):
        if self._verbinden_hid():
            self._log("HID verbunden.")
        else:
            self._log("Kamera nicht gefunden. Versuche erneut...")
            self._starte_reconnect()

        if CV2_VERFUEGBAR:
            self._verbinden_uvc()

    def _verbinden_hid(self):
        with self._lock:
            if self.hid_device:
                return True
            devices = hid.enumerate(vendor_id=VENDOR_ID, product_id=PRODUCT_ID)
            for d in devices:
                if d['usage_page'] == USAGE_PAGE_MAIN:
                    try:
                        self.hid_device = hid.device()
                        self.hid_device.open_path(d['path'])
                        self.hid_device.set_nonblocking(1)
                        self.verbunden = True
                        self.root.after(0, lambda: self.verbindung_label.config(
                            text="HID: Verbunden mit Rally Kamera",
                            fg=self.FARBE_GRUEN
                        ))
                        return True
                    except Exception as e:
                        self._log_safe("HID Verbindungsfehler: %s" % e)
                        return False
            self.verbunden = False
            self.root.after(0, lambda: self.verbindung_label.config(
                text="Kamera nicht gefunden",
                fg=self.FARBE_ROT
            ))
            return False

    # --- UVC Verbindung ---

    def _verbinden_uvc(self):
        """Sucht die Rally Kamera ueber DirectShow und prueft PTZ-Support."""
        if not CV2_VERFUEGBAR:
            return False

        for idx in range(3):
            try:
                cap = cv2.VideoCapture(idx, cv2.CAP_DSHOW)
                if not cap.isOpened():
                    continue

                orig_pan = cap.get(cv2.CAP_PROP_PAN)
                cap.set(cv2.CAP_PROP_PAN, orig_pan + 1)
                time.sleep(0.2)
                new_pan = cap.get(cv2.CAP_PROP_PAN)
                cap.set(cv2.CAP_PROP_PAN, orig_pan)

                if new_pan != orig_pan:
                    self.cv2_device = cap
                    self.cv2_device_idx = idx
                    self.ziel_pan = orig_pan
                    self.ziel_tilt = cap.get(cv2.CAP_PROP_TILT)
                    self.ziel_zoom = cap.get(cv2.CAP_PROP_ZOOM)
                    self.uvc_verbunden = True
                    self.root.after(0, lambda: self.uvc_label.config(
                        text="UVC: PTZ Lock bereit (Device %d)" % idx,
                        fg=self.FARBE_GRUEN
                    ))
                    self._log_safe("UVC: PTZ Lock bereit (Pan=%.0f Tilt=%.0f Zoom=%.0f)" % (
                        self.ziel_pan, self.ziel_tilt, self.ziel_zoom))
                    return True
                else:
                    cap.release()
            except Exception:
                pass

        self.root.after(0, lambda: self.uvc_label.config(
            text="UVC: Nicht verfuegbar (nur HID)",
            fg=self.FARBE_TEXT_DIM
        ))
        return False

    def _trennen(self):
        with self._lock:
            if self.hid_device:
                try:
                    self.hid_device.close()
                except Exception:
                    pass
                self.hid_device = None
                self.verbunden = False
            if self.cv2_device:
                try:
                    self.cv2_device.release()
                except Exception:
                    pass
                self.cv2_device = None
                self.uvc_verbunden = False

    def _starte_reconnect(self):
        if self.reconnect_thread and self.reconnect_thread.is_alive():
            return
        self.reconnect_thread = threading.Thread(target=self._reconnect_loop, daemon=True)
        self.reconnect_thread.start()

    def _reconnect_loop(self):
        while not self.verbunden:
            time.sleep(self.RECONNECT_INTERVALL)
            if self.verbunden:
                break
            self._log_safe("Reconnect-Versuch...")
            if self._verbinden_hid():
                self._log_safe("HID wieder verbunden!")
                if CV2_VERFUEGBAR and not self.uvc_verbunden:
                    self._verbinden_uvc()
                if self.mode != self.MODE_OFF:
                    modus = self.mode
                    self.root.after(0, lambda m=modus: self._starte_modus(m))
                break

    def _sende_stop(self):
        with self._lock:
            if not self.hid_device:
                return None
            try:
                self.hid_device.write(STOP_CMD[:65])
                self.hid_device.read(64)
                self.befehle_gesendet += 1
                return True
            except Exception as e:
                self._log_safe("HID Sendefehler: %s" % e)
                self.hid_device = None
                self.verbunden = False
                self.root.after(0, lambda: self.verbindung_label.config(
                    text="Verbindung verloren",
                    fg=self.FARBE_ROT
                ))
                return None

    def _ptz_lock(self):
        """Setzt die PTZ-Position auf den Zielwert zurueck."""
        if not self.cv2_device or not self.uvc_verbunden:
            return

        try:
            pan = self.cv2_device.get(cv2.CAP_PROP_PAN)
            tilt = self.cv2_device.get(cv2.CAP_PROP_TILT)
            zoom = self.cv2_device.get(cv2.CAP_PROP_ZOOM)

            if pan != self.ziel_pan or tilt != self.ziel_tilt or zoom != self.ziel_zoom:
                self.ptz_korrekturen += 1

            self.cv2_device.set(cv2.CAP_PROP_PAN, self.ziel_pan)
            self.cv2_device.set(cv2.CAP_PROP_TILT, self.ziel_tilt)
            self.cv2_device.set(cv2.CAP_PROP_ZOOM, self.ziel_zoom)
        except Exception:
            self.uvc_verbunden = False
            self.root.after(0, lambda: self.uvc_label.config(
                text="UVC: Verbindung verloren",
                fg=self.FARBE_ROT
            ))

    # --- Modus-Steuerung ---

    def _toggle_manual(self):
        if self.mode == self.MODE_MANUAL:
            self._stoppe_modus()
        else:
            self._starte_modus(self.MODE_MANUAL)

    def _toggle_eco(self):
        if self.mode == self.MODE_ECO:
            self._stoppe_modus()
        else:
            self._starte_modus(self.MODE_ECO)

    def _starte_modus(self, modus):
        if self.mode != self.MODE_OFF:
            self.mode = self.MODE_OFF
            time.sleep(0.1)

        if not self.verbunden:
            if not self._verbinden_hid():
                self._log("Keine Verbindung zur Kamera!")
                self._starte_reconnect()
                return

        self.mode = modus
        self.befehle_gesendet = 0
        self.ptz_korrekturen = 0

        if modus == self.MODE_MANUAL:
            uvc_info = " + PTZ Lock" if self.uvc_verbunden else ""
            self.btn_manual.config(text="STOPP\nAufheben", bg=self.FARBE_GRUEN,
                                   activebackground="#66ddbb")
            self.btn_eco.config(bg=self.FARBE_INAKTIV, state="disabled")
            self.status_label.config(text="MANUELL — Kamera wird gestoppt",
                                     fg=self.FARBE_GRUEN)
            self._log("Manuell aktiv (1x/Sek%s)" % uvc_info)
            self.worker_thread = threading.Thread(target=self._stop_loop,
                                                  args=(self.MANUAL_INTERVALL,),
                                                  daemon=True)
            self.worker_thread.start()

        elif modus == self.MODE_ECO:
            uvc_info = " + PTZ Lock" if self.uvc_verbunden else ""
            self.btn_eco.config(text="ECO\nStoppen", bg=self.FARBE_GRUEN,
                                activebackground="#66ddbb")
            self.btn_manual.config(bg=self.FARBE_INAKTIV, state="disabled")
            self.status_label.config(text="ECO — Kamera wird gestoppt (sparsam)",
                                     fg=self.FARBE_BLAU)
            self._log("Eco-Modus aktiv (1x/3Sek%s)" % uvc_info)
            self.worker_thread = threading.Thread(target=self._stop_loop,
                                                  args=(self.ECO_INTERVALL,),
                                                  daemon=True)
            self.worker_thread.start()

    def _stoppe_modus(self):
        alter_modus = self.mode
        self.mode = self.MODE_OFF

        self.btn_manual.config(text="MANUELL\nStoppen", bg=self.FARBE_ROT,
                               activebackground="#ff2244", state="normal")
        self.btn_eco.config(text="ECO\nModus", bg=self.FARBE_BLAU,
                            activebackground="#5599ff", state="normal")
        self.status_label.config(text="Inaktiv — Kamera frei",
                                 fg=self.FARBE_GELB)
        if alter_modus == self.MODE_MANUAL:
            self._log("Manueller Stopp aufgehoben.")
        elif alter_modus == self.MODE_ECO:
            self._log("Eco-Modus deaktiviert.")

    # --- Worker Loop ---

    def _stop_loop(self, intervall):
        """Sendet Stop-Befehle im angegebenen Intervall."""
        while self.mode in (self.MODE_MANUAL, self.MODE_ECO):
            result = self._sende_stop()
            if result is None:
                self._log_safe("Verbindung verloren. Versuche Reconnect...")
                self._starte_reconnect()
                break

            self._ptz_lock()

            if self.befehle_gesendet % 10 == 0:
                self.root.after(0, self._update_stats)

            warte_bis = time.time() + intervall
            while self.mode != self.MODE_OFF and time.time() < warte_bis:
                time.sleep(0.1)

    # --- UI Updates ---

    def _update_stats(self):
        modus_name = "Manuell" if self.mode == self.MODE_MANUAL else "Eco"
        ptz_text = "  |  PTZ: %d" % self.ptz_korrekturen if self.uvc_verbunden else ""
        self.stats_label.config(
            text="HID: %d  |  Modus: %s%s" % (self.befehle_gesendet, modus_name, ptz_text)
        )

    def _beenden(self):
        self.mode = self.MODE_OFF
        self._trennen()
        self.root.destroy()

    def starten(self):
        self.root.update_idletasks()
        x = (self.root.winfo_screenwidth() // 2) - (420 // 2)
        y = (self.root.winfo_screenheight() // 2) - (380 // 2)
        self.root.geometry("420x380+{x}+{y}".format(x=x, y=y))
        self.root.mainloop()


if __name__ == "__main__":
    app = RallyStopperApp()
    app.starten()
