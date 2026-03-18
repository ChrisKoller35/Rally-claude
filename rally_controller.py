"""
Rally PTZ Kamera Controller
Steuert Logitech Rally PTZ Kameras über USB (UVC-Protokoll).
"""

import tkinter as tk
from tkinter import ttk, messagebox
import threading
import sys
import os

try:
    import cv2
except ImportError:
    print("FEHLER: opencv-python ist nicht installiert!")
    print("Bitte führe zuerst 'install.bat' aus oder tippe:")
    print("  pip install opencv-python")
    input("\nDrücke Enter zum Beenden...")
    sys.exit(1)


class KameraFinder:
    """Findet angeschlossene Kameras und erkennt die Rally PTZ."""

    @staticmethod
    def finde_kameras():
        """Sucht alle angeschlossenen Kameras und gibt eine Liste zurück."""
        kameras = []
        for index in range(10):  # Prüfe bis zu 10 Kamera-Indizes
            cap = cv2.VideoCapture(index, cv2.CAP_DSHOW)
            if cap.isOpened():
                name = f"Kamera {index}"
                # Versuche den Kameranamen auszulesen
                backend = cap.getBackendName()
                breite = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                hoehe = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                kameras.append({
                    "index": index,
                    "name": name,
                    "backend": backend,
                    "breite": breite,
                    "hoehe": hoehe,
                    "info": f"Kamera {index} ({breite}x{hoehe}, {backend})"
                })
                cap.release()
        return kameras


class PTZController:
    """Steuert Pan, Tilt und Zoom einer UVC-Kamera über OpenCV / DirectShow."""

    def __init__(self, kamera_index=0):
        self.kamera_index = kamera_index
        self.cap = None
        self.verbunden = False

    def verbinden(self):
        """Verbindet sich mit der Kamera."""
        try:
            # DirectShow-Backend für beste Kompatibilität auf Windows
            self.cap = cv2.VideoCapture(self.kamera_index, cv2.CAP_DSHOW)
            if self.cap.isOpened():
                self.verbunden = True
                return True
            else:
                self.verbunden = False
                return False
        except Exception as e:
            print(f"Verbindungsfehler: {e}")
            self.verbunden = False
            return False

    def trennen(self):
        """Trennt die Verbindung zur Kamera."""
        if self.cap and self.cap.isOpened():
            self.cap.release()
        self.verbunden = False

    def _sende_befehl(self, eigenschaft, wert):
        """Sendet einen Steuerbefehl an die Kamera."""
        if not self.verbunden or not self.cap:
            return False
        try:
            erfolg = self.cap.set(eigenschaft, wert)
            return erfolg
        except Exception as e:
            print(f"Befehl fehlgeschlagen: {e}")
            return False

    def stopp(self):
        """Stoppt alle Bewegungen der Kamera."""
        ergebnisse = []
        # Pan auf 0 setzen (Bewegung stoppen)
        ergebnisse.append(self._sende_befehl(cv2.CAP_PROP_PAN, 0))
        # Tilt auf 0 setzen (Bewegung stoppen)
        ergebnisse.append(self._sende_befehl(cv2.CAP_PROP_TILT, 0))
        return any(ergebnisse)

    def home(self):
        """Fährt die Kamera in die Home-Position (Mitte, kein Zoom)."""
        ergebnisse = []
        ergebnisse.append(self._sende_befehl(cv2.CAP_PROP_PAN, 0))
        ergebnisse.append(self._sende_befehl(cv2.CAP_PROP_TILT, 0))
        ergebnisse.append(self._sende_befehl(cv2.CAP_PROP_ZOOM, 100))
        return any(ergebnisse)

    def pan_links(self, geschwindigkeit=5):
        """Schwenkt die Kamera nach links."""
        aktuell = self.cap.get(cv2.CAP_PROP_PAN) if self.cap else 0
        return self._sende_befehl(cv2.CAP_PROP_PAN, aktuell - geschwindigkeit)

    def pan_rechts(self, geschwindigkeit=5):
        """Schwenkt die Kamera nach rechts."""
        aktuell = self.cap.get(cv2.CAP_PROP_PAN) if self.cap else 0
        return self._sende_befehl(cv2.CAP_PROP_PAN, aktuell + geschwindigkeit)

    def tilt_hoch(self, geschwindigkeit=5):
        """Neigt die Kamera nach oben."""
        aktuell = self.cap.get(cv2.CAP_PROP_TILT) if self.cap else 0
        return self._sende_befehl(cv2.CAP_PROP_TILT, aktuell + geschwindigkeit)

    def tilt_runter(self, geschwindigkeit=5):
        """Neigt die Kamera nach unten."""
        aktuell = self.cap.get(cv2.CAP_PROP_TILT) if self.cap else 0
        return self._sende_befehl(cv2.CAP_PROP_TILT, aktuell - geschwindigkeit)

    def zoom_rein(self, schritt=10):
        """Zoomt hinein."""
        aktuell = self.cap.get(cv2.CAP_PROP_ZOOM) if self.cap else 100
        return self._sende_befehl(cv2.CAP_PROP_ZOOM, aktuell + schritt)

    def zoom_raus(self, schritt=10):
        """Zoomt heraus."""
        aktuell = self.cap.get(cv2.CAP_PROP_ZOOM) if self.cap else 100
        return self._sende_befehl(cv2.CAP_PROP_ZOOM, max(0, aktuell - schritt))

    def status(self):
        """Liest den aktuellen PTZ-Status aus."""
        if not self.verbunden or not self.cap:
            return None
        try:
            return {
                "pan": self.cap.get(cv2.CAP_PROP_PAN),
                "tilt": self.cap.get(cv2.CAP_PROP_TILT),
                "zoom": self.cap.get(cv2.CAP_PROP_ZOOM),
            }
        except:
            return None


class RallyControllerApp:
    """Hauptanwendung mit grafischer Oberfläche."""

    # Farben
    FARBE_BG = "#1a1a2e"
    FARBE_PANEL = "#16213e"
    FARBE_AKZENT = "#0f3460"
    FARBE_ROT = "#e94560"
    FARBE_GRUEN = "#4ecca3"
    FARBE_GELB = "#f0c929"
    FARBE_TEXT = "#eaeaea"
    FARBE_TEXT_DIM = "#8899aa"

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Rally PTZ Kamera Controller")
        self.root.geometry("500x680")
        self.root.resizable(False, False)
        self.root.configure(bg=self.FARBE_BG)

        self.controller = None
        self.kameras = []

        self._erstelle_gui()
        self._suche_kameras()

    def _erstelle_gui(self):
        """Erstellt die gesamte Benutzeroberfläche."""

        # === TITEL ===
        titel_frame = tk.Frame(self.root, bg=self.FARBE_BG)
        titel_frame.pack(fill="x", padx=20, pady=(15, 5))

        tk.Label(
            titel_frame,
            text="🎥 Rally PTZ Controller",
            font=("Segoe UI", 18, "bold"),
            fg=self.FARBE_TEXT,
            bg=self.FARBE_BG
        ).pack(side="left")

        # === STATUS ===
        self.status_label = tk.Label(
            self.root,
            text="⚪ Nicht verbunden",
            font=("Segoe UI", 10),
            fg=self.FARBE_TEXT_DIM,
            bg=self.FARBE_BG
        )
        self.status_label.pack(anchor="w", padx=20)

        # === KAMERA AUSWAHL ===
        auswahl_frame = tk.Frame(self.root, bg=self.FARBE_PANEL, padx=15, pady=12)
        auswahl_frame.pack(fill="x", padx=20, pady=(10, 5))

        tk.Label(
            auswahl_frame,
            text="Kamera auswählen:",
            font=("Segoe UI", 10),
            fg=self.FARBE_TEXT,
            bg=self.FARBE_PANEL
        ).pack(anchor="w")

        auswahl_row = tk.Frame(auswahl_frame, bg=self.FARBE_PANEL)
        auswahl_row.pack(fill="x", pady=(5, 0))

        self.kamera_var = tk.StringVar()
        self.kamera_dropdown = ttk.Combobox(
            auswahl_row,
            textvariable=self.kamera_var,
            state="readonly",
            font=("Segoe UI", 10),
            width=30
        )
        self.kamera_dropdown.pack(side="left", fill="x", expand=True)

        self.refresh_btn = tk.Button(
            auswahl_row,
            text="🔄",
            font=("Segoe UI", 12),
            bg=self.FARBE_AKZENT,
            fg=self.FARBE_TEXT,
            relief="flat",
            cursor="hand2",
            command=self._suche_kameras
        )
        self.refresh_btn.pack(side="left", padx=(8, 0))

        # Verbinden-Button
        self.verbinden_btn = tk.Button(
            auswahl_frame,
            text="Verbinden",
            font=("Segoe UI", 11, "bold"),
            bg=self.FARBE_GRUEN,
            fg="#000000",
            relief="flat",
            cursor="hand2",
            height=1,
            command=self._toggle_verbindung
        )
        self.verbinden_btn.pack(fill="x", pady=(10, 0))

        # === GROSSER STOPP BUTTON ===
        stopp_frame = tk.Frame(self.root, bg=self.FARBE_BG)
        stopp_frame.pack(fill="x", padx=20, pady=10)

        self.stopp_btn = tk.Button(
            stopp_frame,
            text="⛔  STOPP",
            font=("Segoe UI", 28, "bold"),
            bg=self.FARBE_ROT,
            fg="#ffffff",
            activebackground="#ff2244",
            relief="flat",
            cursor="hand2",
            height=2,
            command=self._stopp,
            state="disabled"
        )
        self.stopp_btn.pack(fill="x")

        # === HOME BUTTON ===
        self.home_btn = tk.Button(
            stopp_frame,
            text="🏠  Home-Position",
            font=("Segoe UI", 14, "bold"),
            bg=self.FARBE_GELB,
            fg="#000000",
            activebackground="#ffdd44",
            relief="flat",
            cursor="hand2",
            height=1,
            command=self._home,
            state="disabled"
        )
        self.home_btn.pack(fill="x", pady=(8, 0))

        # === MANUELLE STEUERUNG ===
        steuerung_frame = tk.LabelFrame(
            self.root,
            text="  Manuelle Steuerung  ",
            font=("Segoe UI", 10),
            fg=self.FARBE_TEXT,
            bg=self.FARBE_PANEL,
            padx=15,
            pady=10
        )
        steuerung_frame.pack(fill="x", padx=20, pady=(5, 10))

        # PTZ Richtungen
        ptz_frame = tk.Frame(steuerung_frame, bg=self.FARBE_PANEL)
        ptz_frame.pack()

        btn_style = {
            "font": ("Segoe UI", 14),
            "bg": self.FARBE_AKZENT,
            "fg": self.FARBE_TEXT,
            "activebackground": "#1a4a80",
            "relief": "flat",
            "cursor": "hand2",
            "width": 4,
            "height": 1
        }

        # Hoch
        self.btn_hoch = tk.Button(ptz_frame, text="▲", command=self._tilt_hoch, **btn_style)
        self.btn_hoch.grid(row=0, column=1, padx=3, pady=3)
        self.btn_hoch.config(state="disabled")

        # Links
        self.btn_links = tk.Button(ptz_frame, text="◄", command=self._pan_links, **btn_style)
        self.btn_links.grid(row=1, column=0, padx=3, pady=3)
        self.btn_links.config(state="disabled")

        # Mitte (Stopp klein)
        self.btn_mitte = tk.Button(ptz_frame, text="●", command=self._stopp, **btn_style)
        self.btn_mitte.grid(row=1, column=1, padx=3, pady=3)
        self.btn_mitte.config(state="disabled", bg=self.FARBE_ROT)

        # Rechts
        self.btn_rechts = tk.Button(ptz_frame, text="►", command=self._pan_rechts, **btn_style)
        self.btn_rechts.grid(row=1, column=2, padx=3, pady=3)
        self.btn_rechts.config(state="disabled")

        # Runter
        self.btn_runter = tk.Button(ptz_frame, text="▼", command=self._tilt_runter, **btn_style)
        self.btn_runter.grid(row=2, column=1, padx=3, pady=3)
        self.btn_runter.config(state="disabled")

        # Zoom
        zoom_frame = tk.Frame(steuerung_frame, bg=self.FARBE_PANEL)
        zoom_frame.pack(pady=(10, 0))

        tk.Label(zoom_frame, text="Zoom:", font=("Segoe UI", 10),
                 fg=self.FARBE_TEXT, bg=self.FARBE_PANEL).pack(side="left", padx=(0, 8))

        self.btn_zoom_raus = tk.Button(zoom_frame, text="➖", command=self._zoom_raus, **btn_style)
        self.btn_zoom_raus.pack(side="left", padx=3)
        self.btn_zoom_raus.config(state="disabled", width=6)

        self.btn_zoom_rein = tk.Button(zoom_frame, text="➕", command=self._zoom_rein, **btn_style)
        self.btn_zoom_rein.pack(side="left", padx=3)
        self.btn_zoom_rein.config(state="disabled", width=6)

        # === LOG ===
        log_frame = tk.Frame(self.root, bg=self.FARBE_BG)
        log_frame.pack(fill="both", expand=True, padx=20, pady=(0, 15))

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
        self._log("Programm gestartet. Bitte Kamera auswählen und verbinden.")

    def _log(self, text):
        """Fügt eine Zeile zum Log hinzu."""
        self.log_text.insert("end", f"> {text}\n")
        self.log_text.see("end")

    def _suche_kameras(self):
        """Sucht nach angeschlossenen Kameras."""
        self._log("Suche Kameras...")
        self.kamera_dropdown.set("")
        self.kamera_dropdown["values"] = []

        def suchen():
            self.kameras = KameraFinder.finde_kameras()
            self.root.after(0, self._kameras_gefunden)

        threading.Thread(target=suchen, daemon=True).start()

    def _kameras_gefunden(self):
        """Callback wenn Kamerasuche fertig."""
        if self.kameras:
            namen = [k["info"] for k in self.kameras]
            self.kamera_dropdown["values"] = namen
            self.kamera_dropdown.current(0)
            self._log(f"{len(self.kameras)} Kamera(s) gefunden.")
        else:
            self._log("Keine Kameras gefunden! Ist die Rally angeschlossen?")

    def _toggle_verbindung(self):
        """Verbindet oder trennt die Kamera."""
        if self.controller and self.controller.verbunden:
            self._trennen()
        else:
            self._verbinden()

    def _verbinden(self):
        """Verbindet mit der ausgewählten Kamera."""
        if not self.kameras:
            messagebox.showwarning("Keine Kamera", "Bitte zuerst eine Kamera suchen und auswählen.")
            return

        idx = self.kamera_dropdown.current()
        if idx < 0:
            return

        kamera_index = self.kameras[idx]["index"]
        self._log(f"Verbinde mit Kamera {kamera_index}...")

        self.controller = PTZController(kamera_index)
        if self.controller.verbinden():
            self._log("✅ Verbunden! STOPP-Button ist jetzt aktiv.")
            self.status_label.config(text="🟢 Verbunden", fg=self.FARBE_GRUEN)
            self.verbinden_btn.config(text="Trennen", bg=self.FARBE_ROT)
            self._buttons_aktivieren(True)

            # Status auslesen
            status = self.controller.status()
            if status:
                self._log(f"   Pan={status['pan']}, Tilt={status['tilt']}, Zoom={status['zoom']}")
        else:
            self._log("❌ Verbindung fehlgeschlagen!")
            self.status_label.config(text="🔴 Fehler", fg=self.FARBE_ROT)

    def _trennen(self):
        """Trennt die Verbindung."""
        if self.controller:
            self.controller.trennen()
        self._log("Verbindung getrennt.")
        self.status_label.config(text="⚪ Nicht verbunden", fg=self.FARBE_TEXT_DIM)
        self.verbinden_btn.config(text="Verbinden", bg=self.FARBE_GRUEN)
        self._buttons_aktivieren(False)

    def _buttons_aktivieren(self, aktiv):
        """Aktiviert oder deaktiviert die Steuerungsbuttons."""
        state = "normal" if aktiv else "disabled"
        self.stopp_btn.config(state=state)
        self.home_btn.config(state=state)
        self.btn_hoch.config(state=state)
        self.btn_runter.config(state=state)
        self.btn_links.config(state=state)
        self.btn_rechts.config(state=state)
        self.btn_mitte.config(state=state)
        self.btn_zoom_rein.config(state=state)
        self.btn_zoom_raus.config(state=state)

    def _stopp(self):
        """Stoppt alle Kamerabewegungen."""
        if self.controller:
            erfolg = self.controller.stopp()
            if erfolg:
                self._log("⛔ STOPP — Alle Bewegungen angehalten!")
            else:
                self._log("⚠️ Stopp-Befehl gesendet (Ergebnis unsicher)")

    def _home(self):
        """Fährt die Kamera zur Home-Position."""
        if self.controller:
            erfolg = self.controller.home()
            if erfolg:
                self._log("🏠 Home-Position wird angefahren...")
            else:
                self._log("⚠️ Home-Befehl gesendet (Ergebnis unsicher)")

    def _pan_links(self):
        if self.controller:
            self.controller.pan_links()
            self._log("◄ Pan links")

    def _pan_rechts(self):
        if self.controller:
            self.controller.pan_rechts()
            self._log("► Pan rechts")

    def _tilt_hoch(self):
        if self.controller:
            self.controller.tilt_hoch()
            self._log("▲ Tilt hoch")

    def _tilt_runter(self):
        if self.controller:
            self.controller.tilt_runter()
            self._log("▼ Tilt runter")

    def _zoom_rein(self):
        if self.controller:
            self.controller.zoom_rein()
            self._log("🔍+ Zoom rein")

    def _zoom_raus(self):
        if self.controller:
            self.controller.zoom_raus()
            self._log("🔍- Zoom raus")

    def starten(self):
        """Startet die Anwendung."""
        # Fenster zentrieren
        self.root.update_idletasks()
        x = (self.root.winfo_screenwidth() // 2) - (500 // 2)
        y = (self.root.winfo_screenheight() // 2) - (680 // 2)
        self.root.geometry(f"500x680+{x}+{y}")

        self.root.mainloop()

        # Aufräumen beim Schliessen
        if self.controller:
            self.controller.trennen()


if __name__ == "__main__":
    app = RallyControllerApp()
    app.starten()
