# K12 Fan Control 🌀

**GUI-Lüftersteuerung für den GMKtec NucBox K12 (und andere Mini-PCs mit ITE IT5570E EC)**

Steuere Lüftergeschwindigkeit und Performance-Modus deines K12 direkt per
Desktop-GUI – ohne BIOS-Einstellungen, ohne Kommandozeile.

![Screenshot](.github/screenshot.png)

> **Nur K12?** Auch kompatibel mit anderen Mini-PCs, die den ITE IT5570E
> Embedded Controller nutzen (z. B. AceMagic W1, MinisForum Modelle mit
> AMD Phoenix APU). Prüfe mit `sensors-detect` ob dein Gerät unterstützt wird.

---

## Features

- **Live-Status** – CPU/GPU-Temperatur, Lüfter-RPM, Modus (2s Refresh)
- **Modus-Umschaltung** – Balanced ⚖, Performance ⚡, Silent 🌙 per Knopfdruck
- **Manuelle Lüftersteuerung** – Slider 0–100 % pro Lüfter, inkl. Auto-Rücksetzung
- **Dark Theme** – Moderne Optik (Catppuccin Mocha), keine 90er-Jahre-Tkinter
- **System Tray** – optionales Minimieren in die Taskleiste (pystray)
- **Autostart** – Direkt in der GUI konfigurierbar
- **SUID Root Helper** – Kein ständiges Passwort, kein sudo im Terminal nötig
- **Open Source** – 80 Zeilen C Helper, auditierbar, keine obskuren Binaries

---

## Installation

### Voraussetzungen

| Paket | Fedora | Ubuntu/Debian | Arch |
|-------|--------|---------------|------|
| Python 3 + venv | `python3` | `python3 python3-venv` | `python` |
| tkinter | `python3-tkinter` | `python3-tk` | `tk` |
| GCC | `gcc` | `build-essential` | `base-devel` |

### Installieren

```bash
git clone https://github.com/dein-user/k12-fan.git
cd k12-fan
chmod +x install.sh
./install.sh
```

Das Script:
1. Kompiliert den C-Helfer (`k12-fan-helper`)
2. Installiert ihn als SUID-root in `/usr/lib/k12-fan/`
3. Legt ein Python-Venv in `~/.local/share/k12-fan/venv/` an
4. Installiert optionale Abhängigkeiten (pystray für Tray)
5. Erstellt Desktop-Eintrag und Icon
6. Polkit-Regel für alternative Berechtigung (optional)

Danach ist **K12 Fan Control** im Anwendungsmenü verfügbar.

---

## Manuelle Nutzung

### GUI starten
```bash
# Aus dem Anwendungsmenü
# Oder Terminal:
~/.local/bin/k12-fan-gui

# Mit eigenem Helper-Pfad:
python3 k12-fan-gui.py --helper /pfad/zum/k12-fan-helper
```

### Helper direkt (CLI)
```bash
# Status abfragen
/usr/lib/k12-fan/k12-fan-helper status

# Modus setzen (0=Balanced, 1=Performance, 2=Silent)
/usr/lib/k12-fan/k12-fan-helper mode 1

# Lüfter manuell (0=Auto, 1-100=%)
/usr/lib/k12-fan/k12-fan-helper fan1 40
/usr/lib/k12-fan/k12-fan-helper fan2 60

# Alles zurücksetzen
/usr/lib/k12-fan/k12-fan-helper auto
```

---

## Deinstallation

```bash
sudo rm -rf /usr/lib/k12-fan/
sudo rm -f /usr/share/polkit-1/actions/com.k12fan.helper.policy
rm -rf ~/.local/share/k12-fan/
rm -f ~/.local/bin/k12-fan-gui
rm -f ~/.local/share/applications/k12-fan-gui.desktop
rm -f ~/.local/share/icons/hicolor/*/apps/k12-fan.svg
```

---

## Sicherheit

Der C-Helfer ist SUID root und greift auf `/dev/mem` zu.
Das klingt dramatisch – ist aber kontrolliert:

| Gefahr | Maßnahme |
|--------|----------|
| Beliebiges /dev/mem lesen | Helper akzeptiert **keine rohen Adressen**. Die EC-Base `0xFE0B0400` ist hardcodiert. |
| EC-Register zerstören | Helper schreibt NUR auf bekannte Lüfter-/Modus-Register (0x31–0x38, 0x70–0x71). |
| Missbrauch durch andere User | Helper kann nur Lüfter steuern – kein Zugriff auf RAM, Kernel oder Dateien. |
| SUID-Binary | Nur **80 Zeilen C**, vollständig auditierbar. Alternativ via Polkit nutzbar. |

**Alternativ ohne SUID:** `pkexec` wird automatisch als Fallback probiert.

---

## EC Register Map

| Addr | R/W | Beschreibung |
|------|-----|-------------|
| 0x31 | R   | Aktueller Modus (0=Balanced, 1=Performance, 2=Silent) |
| 0x32 | W   | Modus setzen (0x80=Balanced, 0x81=Performance, 0x82=Silent) |
| 0x33 | R/W | Fan 1: 0=Auto, 0x80\|%=manuell |
| 0x34 | R/W | Fan 2: 0=Auto, 0x80\|%=manuell |
| 0x35-0x36 | R | Fan 1 RPM (high/low byte) |
| 0x37-0x38 | R | Fan 2 RPM (high/low byte) |
| 0x70 | R   | CPU-Temperatur (°C) |
| 0x71 | R   | GPU-Temperatur (°C) |

---

## Lizenz

GPL-2.0-only – siehe [LICENSE](LICENSE).

---

## Verwandte Projekte

- [passiveEndeavour/it5570-fan](https://github.com/passiveEndeavour/it5570-fan) – Linux Kernel Modul für ITE IT5570
- [coolercontrol](https://gitlab.com/coolercontrol/coolercontrol) – Universelle Lüftersteuerung (nutzt hwmon-Schnittstelle)
