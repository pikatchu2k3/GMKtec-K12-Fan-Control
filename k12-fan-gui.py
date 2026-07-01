#!/usr/bin/env python3
"""
k12-fan-gui.py – Grafische Lüftersteuerung für GMKtec NucBox K12
===============================================================

Aufruf:
  python3 k12-fan-gui.py                    # GUI starten
  python3 k12-fan-gui.py --helper PFAAD     # Eigener Helper-Pfad

Abhängigkeiten:
  - Python 3 + tkinter (python3-tk)
  - Optional: pystray + Pillow (für System Tray)
"""

import tkinter as tk
from tkinter import ttk
import json
import subprocess
import os
import sys
import time
import platform

# ─── Konfiguration ───────────────────────────────────────────────────────────
HELPER_PATHS = [
    "/usr/lib/k12-fan/k12-fan-helper",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "k12-fan-helper"),
    "./k12-fan-helper",
]
REFRESH_MS = 2000  # 2 Sekunden Refresh-Intervall

# ─── Farben (Catppuccin Mocha inspiriert) ────────────────────────────────────
COLORS = {
    "bg":        "#1e1e2e",
    "surface":   "#2a2a3e",
    "surface2":  "#313244",
    "text":      "#cdd6f4",
    "text_dim":  "#6c7086",
    "accent":    "#89b4fa",
    "green":     "#a6e3a1",
    "yellow":    "#f9e2af",
    "red":       "#f38ba8",
    "error_bg":  "#3a1a1a",
    "error_fg":  "#f38ba8",
}


# ─── Helper-Kommunikation ────────────────────────────────────────────────────
class HelperError(Exception):
    pass


def find_helper():
    """Findet den k12-fan-helper im System."""
    for path in HELPER_PATHS:
        if os.path.isfile(path) and os.access(path, os.X_OK):
            return path
    return None


def call_helper(helper_path, *args):
    """Ruft den Helper auf und parst JSON-Antwort.
    
    Versucht:
    1. Direkten Aufruf (SUID-Binary)
    2. pkexec (Polkit-Regel)
    3. sudo (Passwortabfrage)
    """
    if not helper_path:
        raise HelperError("k12-fan-helper nicht gefunden. install.sh ausführen!")

    cmd = [helper_path] + list(args)

    for attempt_name, run_cmd in [
        ("direkt", cmd),
        ("pkexec", ["pkexec"] + cmd),
        ("sudo", ["sudo", "-n"] + cmd),
    ]:
        try:
            proc = subprocess.run(
                run_cmd,
                capture_output=True,
                text=True,
                timeout=5,
            )
            if proc.returncode == 0 and proc.stdout:
                return json.loads(proc.stdout)
            elif proc.returncode == 0 and proc.stderr:
                # Fallback: Fehler in stderr als JSON
                try:
                    return json.loads(proc.stderr)
                except json.JSONDecodeError:
                    raise HelperError(proc.stderr.strip())
            else:
                if attempt_name == "direkt" and proc.returncode != 0:
                    continue  # Nächste Methode versuchen
                err = proc.stderr.strip() or f"Exit-Code {proc.returncode}"
                raise HelperError(err)
        except FileNotFoundError:
            continue  # pkexec/sudo nicht vorhanden
        except subprocess.TimeoutExpired:
            raise HelperError("Helper-Aufruf abgelaufen (Timeout)")
        except json.JSONDecodeError:
            raise HelperError(f"Ungültiges JSON: {proc.stdout[:200]}")

    raise HelperError("Keine Methode gefunden, Helper auszuführen (SUID/pkexec/sudo)")


# ─── GUI ─────────────────────────────────────────────────────────────────────
class K12FanGUI:
    def __init__(self, helper_path=None):
        self.helper_path = helper_path or find_helper()
        self.last_status = {}
        self.tray_icon = None
        self.tray_enabled = False
        self._running = True

        # Fenster
        self.root = tk.Tk()
        self.root.title("K12 Fan Control")
        self.root.configure(bg=COLORS["bg"])
        self.root.resizable(False, False)

        # Fenster-Icon (Minimal: farbiger Kreis via PhotoImage)
        self._set_icon()

        # Style
        self._setup_style()

        # Layout
        self._build_ui()

        # Fenster zentrieren
        self.root.update_idletasks()
        w = self.root.winfo_width()
        h = self.root.winfo_height()
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        x = (sw - w) // 2
        y = (sh - h) // 2
        self.root.geometry(f"+{x}+{y}")

        # Tray-Verfügbarkeit prüfen
        self._check_tray()

        # Fenster schließen
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        # Erster Refresh
        self.refresh()

    def _set_icon(self):
        """Erzeugt ein Mini-Icon für das Fenster."""
        icon = tk.PhotoImage(width=16, height=16)
        icon.put("{#89b4fa}", to=(2, 2, 13, 13))
        self.root.iconphoto(True, icon)

    def _setup_style(self):
        """Dark Theme über ttk.Style."""
        style = ttk.Style(self.root)
        theme = style.theme_use("clam")

        style.configure(".", background=COLORS["bg"], foreground=COLORS["text"],
                        fieldbackground=COLORS["surface"], font=("Segoe UI", 10))

        style.configure("TLabel", background=COLORS["bg"], foreground=COLORS["text"])
        style.configure("TFrame", background=COLORS["bg"])
        style.configure("TLabelframe", background=COLORS["bg"], foreground=COLORS["text"])
        style.configure("TLabelframe.Label", background=COLORS["bg"], foreground=COLORS["accent"],
                        font=("Segoe UI", 10, "bold"))

        # Card-Style
        style.configure("Card.TFrame", background=COLORS["surface"], relief="flat")

        # Mode-Buttons
        style.configure("Mode.TButton", background=COLORS["surface"],
                        foreground=COLORS["text"], borderwidth=1, focusthickness=0,
                        font=("Segoe UI", 10))
        style.map("Mode.TButton",
                  background=[("active", COLORS["surface2"]), ("selected", COLORS["accent"])],
                  foreground=[("selected", "#11111b")])

        style.configure("Active.TButton", background=COLORS["accent"],
                        foreground="#11111b", borderwidth=1, focusthickness=0,
                        font=("Segoe UI", 10, "bold"))
        style.map("Active.TButton",
                  background=[("active", "#9dbdfa")])

        # Danger (Auto / Reset)
        style.configure("Danger.TButton", background=COLORS["error_bg"],
                        foreground=COLORS["red"], borderwidth=1, focusthickness=0)
        style.map("Danger.TButton",
                  background=[("active", "#4a2020")])

        # Scale (Slider)
        style.configure("TScale", background=COLORS["bg"],
                        troughcolor=COLORS["surface2"],
                        sliderrelief="flat", sliderlength=20)

        # Checkbutton
        style.configure("TCheckbutton", background=COLORS["bg"], foreground=COLORS["text"])

        # Separator
        style.configure("TSeparator", background=COLORS["surface2"])

    def _build_ui(self):
        """Baut das GUI-Layout."""
        main = ttk.Frame(self.root)
        main.pack(fill="both", expand=True, padx=12, pady=12)

        # ─── Error Banner (zunächst versteckt) ───
        self.error_var = tk.StringVar()
        self.error_banner = tk.Label(
            main, textvariable=self.error_var,
            bg=COLORS["error_bg"], fg=COLORS["error_fg"],
            font=("Segoe UI", 9), wraplength=400, justify="left",
            padx=8, pady=4
        )
        self.error_banner.pack(fill="x", pady=(0, 8))
        self.error_banner.pack_forget()  # Versteckt

        # ─── Status Card ───
        status_frame = ttk.LabelFrame(main, text="Status", style="TLabelframe")
        status_frame.pack(fill="x", pady=(0, 12))

        self.temp_labels = {}
        sensors = [
            ("cpu_temp", "CPU", COLORS["green"]),
            ("gpu_temp", "GPU", COLORS["green"]),
        ]
        for key, label, color in sensors:
            f = ttk.Frame(status_frame, style="Card.TFrame")
            f.pack(fill="x", padx=6, pady=3)

            ttk.Label(f, text=f"{label}:", width=6, anchor="w",
                      style="Card.TFrame").pack(side="left", padx=(6, 2))
            self.temp_labels[key] = tk.Label(
                f, text="--°C", bg=COLORS["surface"], fg=color,
                font=("Segoe UI", 12, "bold"), width=8, anchor="w"
            )
            self.temp_labels[key].pack(side="left", padx=(0, 16))

            if key == "cpu_temp":
                ttk.Label(f, text="Fan 1:", style="Card.TFrame").pack(side="left", padx=(6, 2))
                self.fan1_label = tk.Label(
                    f, text="-- RPM", bg=COLORS["surface"], fg=COLORS["text"],
                    font=("Segoe UI", 12, "bold"), width=10, anchor="w"
                )
                self.fan1_label.pack(side="left")
            elif key == "gpu_temp":
                ttk.Label(f, text="Fan 2:", style="Card.TFrame").pack(side="left", padx=(6, 2))
                self.fan2_label = tk.Label(
                    f, text="-- RPM", bg=COLORS["surface"], fg=COLORS["text"],
                    font=("Segoe UI", 12, "bold"), width=10, anchor="w"
                )
                self.fan2_label.pack(side="left")

        # Modus-Anzeige
        mode_row = ttk.Frame(status_frame, style="Card.TFrame")
        mode_row.pack(fill="x", padx=6, pady=(3, 6))
        ttk.Label(mode_row, text="Mode:", width=6, anchor="w",
                  style="Card.TFrame").pack(side="left", padx=(6, 2))
        self.mode_label = tk.Label(
            mode_row, text="--", bg=COLORS["surface"], fg=COLORS["accent"],
            font=("Segoe UI", 12, "bold"), anchor="w"
        )
        self.mode_label.pack(side="left", padx=(0, 16))

        # Prozent-Anzeige
        ttk.Label(mode_row, text="Fan 1:", style="Card.TFrame").pack(side="left", padx=(6, 2))
        self.pct1_label = tk.Label(
            mode_row, text="--%", bg=COLORS["surface"], fg=COLORS["text_dim"],
            font=("Segoe UI", 11), width=5, anchor="w"
        )
        self.pct1_label.pack(side="left")
        ttk.Label(mode_row, text="Fan 2:", style="Card.TFrame").pack(side="left", padx=(10, 2))
        self.pct2_label = tk.Label(
            mode_row, text="--%", bg=COLORS["surface"], fg=COLORS["text_dim"],
            font=("Segoe UI", 11), width=5, anchor="w"
        )
        self.pct2_label.pack(side="left")

        # ─── Mode Buttons ───
        mode_frame = ttk.LabelFrame(main, text="Modus", style="TLabelframe")
        mode_frame.pack(fill="x", pady=(0, 12))

        self.mode_buttons = {}
        btn_frame = ttk.Frame(mode_frame, style="Card.TFrame")
        btn_frame.pack(padx=6, pady=6)

        for code, name, icon_char in [
            (0, "Balanced", "⚖"),
            (1, "Performance", "⚡"),
            (2, "Silent", "🌙"),
        ]:
            b = tk.Button(
                btn_frame, text=f"  {icon_char} {name}  ",
                bg=COLORS["surface"], fg=COLORS["text"],
                relief="flat", bd=0,
                font=("Segoe UI", 11),
                cursor="hand2",
                command=lambda c=code: self.set_mode(c),
            )
            b.pack(side="left", padx=4, ipadx=8, ipady=4)
            self.mode_buttons[code] = b

        # ─── Fan Slider ───
        fan_frame = ttk.LabelFrame(main, text="Lüfter (manuell)", style="TLabelframe")
        fan_frame.pack(fill="x", pady=(0, 12))

        self.fan_sliders = {}
        self.fan_scale_vars = {}
        self.fan_dragging = {1: False, 2: False}  # True während User slider zieht
        for f_id in [1, 2]:
            row = ttk.Frame(fan_frame, style="Card.TFrame")
            row.pack(fill="x", padx=6, pady=4)

            ttk.Label(row, text=f"Fan {f_id}:", width=7,
                      style="Card.TFrame").pack(side="left")

            var = tk.IntVar(value=0)
            self.fan_scale_vars[f_id] = var

            scale = ttk.Scale(row, from_=0, to=100, orient="horizontal",
                              variable=var, length=200,
                              command=lambda v, fid=f_id: self._on_slider(fid, v))
            scale.pack(side="left", padx=6, fill="x", expand=True)
            # Beim Loslassen an den Helper senden
            scale.bind("<ButtonRelease-1>",
                        lambda e, fid=f_id: self._on_slider_release(fid, self.fan_scale_vars[fid].get()))
            # Drag-Tracking für Refresh-Schutz
            scale.bind("<ButtonPress-1>",
                        lambda e, fid=f_id: self.fan_dragging.__setitem__(fid, True))
            scale.bind("<ButtonRelease-1>",
                        lambda e, fid=f_id: self.fan_dragging.__setitem__(fid, False))
            self.fan_sliders[f_id] = scale

            pct_lbl = tk.Label(row, text="  0%", bg=COLORS["surface"],
                               fg=COLORS["text_dim"],
                               font=("Segoe UI", 10, "bold"),
                               width=5, anchor="w")
            pct_lbl.pack(side="left")
            self.fan_sliders[f_id + 10] = pct_lbl  # offset 10 für Label

            btn = tk.Button(row, text="Auto", bg=COLORS["surface2"],
                            fg=COLORS["text"], relief="flat", bd=0,
                            font=("Segoe UI", 9), cursor="hand2",
                            command=lambda fid=f_id: self.set_fan(fid, 0))
            btn.pack(side="left", padx=(6, 2), ipadx=6)

        # ─── Optionen ───
        opt_frame = ttk.LabelFrame(main, text="Optionen", style="TLabelframe")
        opt_frame.pack(fill="x", pady=(0, 12))

        self.autostart_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(opt_frame, text="Autostart (nach Login)",
                        variable=self.autostart_var,
                        command=self._toggle_autostart).pack(anchor="w", padx=10, pady=4)

        self.tray_var = tk.BooleanVar(value=False)
        self.tray_cb = ttk.Checkbutton(opt_frame, text="In Tray minimieren",
                                       variable=self.tray_var,
                                       command=self._toggle_tray)
        self.tray_cb.pack(anchor="w", padx=10, pady=4)

        # ─── Separator & Statuszeile ───
        ttk.Separator(main, orient="horizontal").pack(fill="x", pady=(0, 6))

        bottom = ttk.Frame(main)
        bottom.pack(fill="x")

        self.status_var = tk.StringVar(value="⏳ Initialisiere…")
        ttk.Label(bottom, textvariable=self.status_var,
                  foreground=COLORS["text_dim"], font=("Segoe UI", 9)).pack(side="left")

        ttk.Button(bottom, text="Schließen",
                   command=self._on_close).pack(side="right")

    def _show_error(self, msg):
        """Zeigt eine Fehlermeldung im Banner an."""
        self.error_var.set("⚠ " + msg)
        self.error_banner.pack(fill="x", pady=(0, 8))

    def _hide_error(self):
        """Versteckt das Error-Banner."""
        self.error_banner.pack_forget()

    def _update_temp_color(self, label, temp):
        """Färbt Temperatur je nach Wert."""
        if temp < 50:
            label.config(fg=COLORS["green"])
        elif temp < 65:
            label.config(fg=COLORS["yellow"])
        else:
            label.config(fg=COLORS["red"])

    def refresh(self):
        """Holt Status vom Helper und aktualisiert die Anzeige."""
        if not self._running:
            return

        try:
            data = call_helper(self.helper_path, "status")
            self.last_status = data
            self._hide_error()

            # Temperaturen
            for key, label in self.temp_labels.items():
                temp = data.get(key, 0)
                label.config(text=f"{temp}°C")
                self._update_temp_color(label, temp)

            # Fan RPM
            fr1 = data.get("fan1_rpm", 0)
            fr2 = data.get("fan2_rpm", 0)
            self.fan1_label.config(text=f"{fr1} RPM")
            self.fan2_label.config(text=f"{fr2} RPM")

            # Mode
            mode = data.get("mode", "??")
            mode_code = data.get("mode_code", -1)
            self.mode_label.config(text=mode)

            # Mode-Buttons hervorheben
            for code, btn in self.mode_buttons.items():
                if code == mode_code:
                    btn.config(bg=COLORS["accent"], fg="#11111b",
                               font=("Segoe UI", 11, "bold"))
                else:
                    btn.config(bg=COLORS["surface"], fg=COLORS["text"],
                               font=("Segoe UI", 11))

            # Prozent
            fp1 = data.get("fan1_pct", 0)
            fp2 = data.get("fan2_pct", 0)
            fm1 = data.get("fan1_manual", 0)
            fm2 = data.get("fan2_manual", 0)

            self.pct1_label.config(text=f"{fp1}%{' ✋' if fm1 else ' ↺'}")
            self.pct2_label.config(text=f"{fp2}%{' ✋' if fm2 else ' ↺'}")

            # Slider (nur aktualisieren wenn nicht gerade vom User bewegt)
            for f_id in [1, 2]:
                pct = data.get(f"fan{f_id}_pct", 0)
                is_manual = data.get(f"fan{f_id}_manual", 0)
                if is_manual and not self.fan_dragging.get(f_id, False):
                    self.fan_scale_vars[f_id].set(pct)
                    self.fan_sliders[f_id + 10].config(text=f"{pct:3d}%")
                elif not is_manual:
                    if not self.fan_dragging.get(f_id, False):
                        self.fan_scale_vars[f_id].set(0)
                    self.fan_sliders[f_id + 10].config(text="  ↺")

            # Status
            self.status_var.set(f"✓ OK  |  {time.strftime('%H:%M:%S')}")

        except HelperError as e:
            self._show_error(str(e))
            self.status_var.set(f"⚠ Fehler: {str(e)[:50]}")
        except Exception as e:
            self._show_error(str(e))
            self.status_var.set(f"⚠ Fehler: {str(e)[:50]}")

        # Nächster Refresh
        if self._running:
            self.refresh_timer = self.root.after(REFRESH_MS, self.refresh)

    def set_mode(self, code):
        """Setzt den Lüftermodus."""
        names = {0: "Balanced", 1: "Performance", 2: "Silent"}
        try:
            result = call_helper(self.helper_path, "mode", str(code))
            self.status_var.set(f"✓ Modus: {names.get(code, str(code))}")
            self.refresh()  # Sofort aktualisieren
        except HelperError as e:
            self._show_error(str(e))

    def set_fan(self, fan_id, pct):
        """Setzt Lüftergeschwindigkeit (0 = Auto)."""
        cmd = f"fan{fan_id}"
        try:
            result = call_helper(self.helper_path, cmd, str(pct))
            if pct == 0:
                self.status_var.set(f"✓ Fan {fan_id}: Auto")
            else:
                self.status_var.set(f"✓ Fan {fan_id}: {pct}%")
            self.refresh()
        except HelperError as e:
            self._show_error(str(e))

    def _on_slider(self, fan_id, value):
        """Wird aufgerufen, während der Slider bewegt wird."""
        pct = int(float(value))
        self.fan_sliders[fan_id + 10].config(text=f"{pct:3d}%")
        if pct == 0:
            self.fan_sliders[fan_id + 10].config(text="  ↺")

    def _on_slider_release(self, fan_id, value):
        """Wird beim Loslassen des Sliders aufgerufen."""
        pct = int(float(value))
        self.set_fan(fan_id, pct)

    def _toggle_autostart(self):
        """Erstellt/Entfernt Autostart-Desktop-Eintrag."""
        autostart_dir = os.path.expanduser("~/.config/autostart")
        desktop_file = os.path.join(autostart_dir, "k12-fan-gui.desktop")
        gui_path = os.path.abspath(__file__)

        if self.autostart_var.get():
            os.makedirs(autostart_dir, exist_ok=True)
            content = (
                "[Desktop Entry]\n"
                "Type=Application\n"
                "Name=K12 Fan Control\n"
                f"Exec={gui_path}\n"
                "Terminal=false\n"
                "X-GNOME-Autostart-enabled=true\n"
                "Categories=System;\n"
            )
            with open(desktop_file, "w") as f:
                f.write(content)
            self.status_var.set("✓ Autostart aktiviert")
        else:
            if os.path.isfile(desktop_file):
                os.remove(desktop_file)
                self.status_var.set("✓ Autostart deaktiviert")

    # ─── System Tray (optional, benötigt pystray + Pillow) ───
    def _check_tray(self):
        """Prüft, ob pystray verfügbar ist."""
        try:
            import pystray
            from PIL import Image, ImageDraw
            self.tray_enabled = True
        except ImportError:
            self.tray_cb.config(state="disabled")
            self.tray_cb.config(text="Tray: pystray nicht installiert")

    def _toggle_tray(self):
        if self.tray_var.get():
            self._minimize_to_tray()
        else:
            self._restore_from_tray()

    def _minimize_to_tray(self):
        """Minimiert das Fenster in den System Tray."""
        if not self.tray_enabled:
            return
        try:
            import pystray
            from PIL import Image, ImageDraw

            # Icon erstellen
            img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
            draw = ImageDraw.Draw(img)
            draw.ellipse([8, 8, 56, 56], fill="#89b4fa")
            draw.ellipse([16, 16, 48, 48], fill="#1e1e2e")
            draw.text((20, 20), "K", fill="#89b4fa")

            def on_click(icon, item):
                root = self.root
                if str(item) == "Beenden":
                    self._running = False
                    icon.stop()
                    root.after(0, root.quit)
                else:
                    root.after(0, self._restore_from_tray)

            menu = pystray.Menu(
                pystray.MenuItem("Fenster anzeigen", lambda: self.root.after(0, self._restore_from_tray)),
                pystray.MenuItem("Beenden", lambda: icon.stop() or self.root.after(0, self._on_close)),
            )

            self.tray_icon = pystray.Icon("k12-fan", img, "K12 Fan Control", menu)
            self.root.withdraw()  # Fenster verstecken

            # Tray in separatem Thread laufen lassen
            import threading
            t = threading.Thread(target=self.tray_icon.run, daemon=True)
            t.start()
        except Exception as e:
            self._show_error(f"Tray-Fehler: {e}")
            self.tray_var.set(False)

    def _restore_from_tray(self):
        """Stellt das Fenster aus dem Tray wieder her.
        Wird via root.after() aus dem Hauptthread aufgerufen – NIEMALS direkt aus pystray-Thread."""
        if self.tray_icon:
            self.tray_icon.stop()
            self.tray_icon = None
        self.root.deiconify()
        self.root.lift()
        self.tray_var.set(False)

    def _on_close(self):
        """Wird beim Schließen des Fensters aufgerufen."""
        self._running = False
        if hasattr(self, "refresh_timer"):
            self.root.after_cancel(self.refresh_timer)
        if self.tray_icon:
            self.tray_icon.stop()
        self.root.destroy()

    def run(self):
        """Startet die GUI-Hauptschleife."""
        self.root.mainloop()


# ─── Hauptprogramm ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    # Kommandozeilen-Argumente
    helper_path = None
    for i, arg in enumerate(sys.argv[1:]):
        if arg == "--helper" and i + 1 < len(sys.argv[1:]):
            helper_path = sys.argv[i + 2]

    app = K12FanGUI(helper_path)
    app.run()
