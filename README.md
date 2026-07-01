# GMKtec K12 Fan Control 🌀

**Fan control GUI + CLI for the GMKtec NucBox K12 Mini-PC (and other Mini-PCs with ITE IT5570E EC)**

Control fan speed and performance mode of your K12 directly from the desktop –
no BIOS tweaking, no command-line knowledge required.

> 🇩🇪 **German version available:** [`anleitung.md`](anleitung.md) – ausführliche Schritt-für-Schritt-Anleitung auf Deutsch.

![Screenshot](.github/screenshot.png)

> **K12 only?** Also compatible with other Mini-PCs using the ITE IT5570E
> Embedded Controller (e.g. AceMagic W1, MinisForum models with AMD Phoenix APU).
> Check with `sensors-detect` to verify your device.

---

## Features

- **Live status** – CPU/GPU temperature, fan RPM, current mode (2s auto-refresh)
- **Mode switching** – Balanced ⚖, Performance ⚡, Silent 🌙 at the click of a button
- **Manual fan control** – Sliders 0–100 % per fan, with auto-reset
- **Dark theme** – Modern look (Catppuccin Mocha), no 90s-style Tkinter
- **System tray** – Optional minimise to tray (requires `pystray`)
- **Autostart** – Configurable right inside the GUI
- **SUID root helper** – No constant password prompts, no sudo in the terminal
- **Open source** – 80-line C helper, fully auditable, no obscure binaries

---

## Quick Start

### Prerequisites

| Package | Fedora | Ubuntu/Debian | Arch |
|---------|--------|---------------|------|
| Python 3 + venv | `python3` | `python3 python3-venv` | `python` |
| tkinter | `python3-tkinter` | `python3-tk` | `tk` |
| GCC | `gcc` | `build-essential` | `base-devel` |

### Install

```bash
git clone https://github.com/pikatchu2k3/GMKtec-K12-Fan-Control.git
cd GMKtec-K12-Fan-Control
chmod +x install.sh
./install.sh
```

The script will:
1. Compile the C helper (`k12-fan-helper`)
2. Install it as SUID-root in `/usr/lib/k12-fan/`
3. Create a Python venv in `~/.local/share/k12-fan/venv/`
4. Install optional dependencies (pystray for system tray)
5. Create a desktop entry and icon
6. Add a Polkit rule for alternative permission handling (optional)

After installation, **K12 Fan Control** appears in your application menu.

---

## Usage

### Launch the GUI

```bash
# From the application menu (search "K12 Fan Control")
# Or from the terminal:
~/.local/bin/k12-fan-gui

# With a custom helper path:
python3 k12-fan-gui.py --helper /path/to/k12-fan-helper
```

### CLI (direct helper commands)

```bash
# Query status
/usr/lib/k12-fan/k12-fan-helper status

# Set mode (0=Balanced, 1=Performance, 2=Silent)
/usr/lib/k12-fan/k12-fan-helper mode 1

# Manual fan control (0=Auto, 1-100=%)
/usr/lib/k12-fan/k12-fan-helper fan1 40
/usr/lib/k12-fan/k12-fan-helper fan2 60

# Reset everything to automatic
/usr/lib/k12-fan/k12-fan-helper auto
```

> **No `sudo` needed** – the SUID binary handles privilege elevation for you.

---

## Uninstall

```bash
sudo rm -rf /usr/lib/k12-fan/
sudo rm -f /usr/share/polkit-1/actions/com.k12fan.helper.policy
rm -rf ~/.local/share/k12-fan/
rm -f ~/.local/bin/k12-fan-gui
rm -f ~/.local/share/applications/k12-fan-gui.desktop
rm -f ~/.local/share/icons/hicolor/*/apps/k12-fan.svg
```

---

## German Manual

There's a **detailed German step-by-step guide** covering the GUI, CLI, and FAQs:

➡️ **[`anleitung.md`](anleitung.md)** (auf Deutsch)

---

## Security

The C helper is SUID root and accesses `/dev/mem`. This sounds dramatic but is tightly controlled:

| Concern | Mitigation |
|---------|-----------|
| Arbitrary /dev/mem reads | Helper accepts **no raw addresses**. The EC base `0xFE0B0400` is hardcoded. |
| EC register damage | Helper writes ONLY to known fan/mode registers (0x31–0x38, 0x70–0x71). |
| Abuse by other users | Helper can only control fans – no access to RAM, kernel, or files. |
| SUID binary | Only **80 lines of C**, fully auditable. Polkit fallback available. |

**Alternative without SUID:** `pkexec` is tried automatically as a fallback.

---

## EC Register Map

| Addr | R/W | Description |
|------|-----|-------------|
| 0x31 | R   | Current mode (0=Balanced, 1=Performance, 2=Silent) |
| 0x32 | W   | Set mode (0x80=Balanced, 0x81=Performance, 0x82=Silent) |
| 0x33 | R/W | Fan 1: 0=Auto, 0x80\|%=manual |
| 0x34 | R/W | Fan 2: 0=Auto, 0x80\|%=manual |
| 0x35-0x36 | R | Fan 1 RPM (high/low byte) |
| 0x37-0x38 | R | Fan 2 RPM (high/low byte) |
| 0x70 | R   | CPU temperature (°C) |
| 0x71 | R   | GPU temperature (°C) |

---

## License

GPL-2.0-only – see [LICENSE](LICENSE).

---

## Related Projects

- [passiveEndeavour/it5570-fan](https://github.com/passiveEndeavour/it5570-fan) – Linux kernel module for ITE IT5570
- [coolercontrol](https://gitlab.com/coolercontrol/coolercontrol) – Universal fan control (uses hwmon interface)
