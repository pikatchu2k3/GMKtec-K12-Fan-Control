#!/usr/bin/env bash
# install.sh – K12 Fan Control Installation
#
# Installiert:
#   1. k12-fan-helper  → /usr/lib/k12-fan/k12-fan-helper  (SUID root)
#   2. Python-Venv     → ~/.local/share/k12-fan/venv/
#   3. Desktop-Eintrag → ~/.local/share/applications/
#   4. Autostart       → optional (über GUI)
#
# PEP 668-konform: Verwendet venv statt system-pip.
# Kein Root für Python-Teil nötig.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_NAME="k12-fan"
INSTALL_DIR="/usr/lib/${APP_NAME}"

# Wenn via sudo ausgeführt, für den richtigen User installieren
if [ -n "${SUDO_USER}" ] && [ "${SUDO_USER}" != "root" ]; then
    REAL_USER="${SUDO_USER}"
    REAL_HOME="$(getent passwd "${SUDO_USER}" | cut -d: -f6)"
else
    REAL_USER="${USER}"
    REAL_HOME="${HOME}"
fi

VENV_DIR="${REAL_HOME}/.local/share/${APP_NAME}/venv"
DESKTOP_DIR="${REAL_HOME}/.local/share/applications"
BIN_DIR="${REAL_HOME}/.local/bin"
HELPER_BIN="${INSTALL_DIR}/k12-fan-helper"
GUI_SCRIPT="${SCRIPT_DIR}/k12-fan-gui.py"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log()  { echo -e "${GREEN}✓${NC} $1"; }
warn() { echo -e "${YELLOW}⚠${NC} $1"; }
err()  { echo -e "${RED}✗${NC} $1"; }

echo "=========================================="
echo "  K12 Fan Control – Installation"
echo "=========================================="
echo ""

# ─── Prüfungen ────────────────────────────────────────────

# 1. Python 3 vorhanden?
if ! command -v python3 &>/dev/null; then
    err "Python 3 nicht gefunden. Bitte installieren:"
    err "  Fedora: sudo dnf install python3"
    err "  Ubuntu/Debian: sudo apt install python3 python3-venv python3-tk"
    exit 1
fi

# 2. tkinter verfügbar?
python3 -c "import tkinter" 2>/dev/null || {
    err "tkinter nicht gefunden. Bitte installieren:"
    err "  Fedora: sudo dnf install python3-tkinter"
    err "  Ubuntu/Debian: sudo apt install python3-tk"
    err "  Arch: sudo pacman -S tk"
    exit 1
}

# 3. GCC verfügbar?
if ! command -v gcc &>/dev/null; then
    err "GCC nicht gefunden. Bitte installieren:"
    err "  Fedora: sudo dnf install gcc"
    err "  Ubuntu/Debian: sudo apt install build-essential"
    err "  Arch: sudo pacman -S base-devel"
    exit 1
fi

# 4. Polkit verfügbar (für pkexec – optional aber empfohlen)?
HAVE_POLKIT=false
if command -v pkexec &>/dev/null; then
    HAVE_POLKIT=true
fi

# 5. Root für Helper-Installation
if [ "$(id -u)" -eq 0 ]; then
    IS_ROOT=true
else
    IS_ROOT=false
    warn "Nicht als root ausgeführt. Helper-Installation benötigt sudo."
fi

# ─── Installation Helper (erfordert root) ─────────────────
echo ""
echo "--- Schritt 1: C-Helfer kompilieren ---"

cd "$SCRIPT_DIR"
gcc -O2 -s -Wall -Wextra -o k12-fan-helper k12-fan-helper.c
log "k12-fan-helper kompiliert (11 KB)"

echo ""
echo "--- Schritt 2: Helper installieren (sudo) ---"

if [ "$IS_ROOT" = true ]; then
    mkdir -p "$INSTALL_DIR"
    cp k12-fan-helper "$HELPER_BIN"
    chown root:root "$HELPER_BIN"
    chmod u+s "$HELPER_BIN"
    chmod 755 "$HELPER_BIN"
    log "Helper nach ${HELPER_BIN} installiert (SUID root)"
else
    sudo mkdir -p "$INSTALL_DIR"
    sudo cp k12-fan-helper "$HELPER_BIN"
    sudo chown root:root "$HELPER_BIN"
    sudo chmod u+s "$HELPER_BIN"
    sudo chmod 755 "$HELPER_BIN"
    log "Helper nach ${HELPER_BIN} installiert (SUID root)"
fi

# Optional: Polkit-Regel (damit pkexec ohne Passwort funktioniert)
if [ "$HAVE_POLKIT" = true ]; then
    POLKIT_FILE="/usr/share/polkit-1/actions/com.k12fan.helper.policy"
    POLKIT_CONTENT='<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE policyconfig PUBLIC
 "-//freedesktop//DTD PolicyKit Policy Configuration 1.0//EN"
 "http://www.freedesktop.org/standards/PolicyKit/1/policyconfig.dtd">
<policyconfig>
  <action id="com.k12fan.helper">
    <description>K12 Fan Control EC Helper</description>
    <message>Zugriff auf die Lüftersteuerung des GMKtec K12</message>
    <defaults>
      <allow_any>auth_admin</allow_any>
      <allow_inactive>auth_admin</allow_inactive>
      <allow_active>yes</allow_active>
    </defaults>
    <annotate key="org.freedesktop.policykit.exec.path">/usr/lib/k12-fan/k12-fan-helper</annotate>
  </action>
</policyconfig>'

    if [ "$IS_ROOT" = true ]; then
        echo "$POLKIT_CONTENT" > "$POLKIT_FILE"
    else
        echo "$POLKIT_CONTENT" | sudo tee "$POLKIT_FILE" > /dev/null
    fi
    log "Polkit-Regel installiert (${POLKIT_FILE})"
fi

# ─── Python-Umgebung (User, kein Root) ────────────────────
echo ""
echo "--- Schritt 3: Python-Umgebung einrichten ---"

# Venv erstellen (als User, nicht root)
if [ ! -d "$VENV_DIR" ]; then
    if [ -n "${SUDO_USER}" ] && [ "${SUDO_USER}" != "root" ]; then
        sudo -u "${REAL_USER}" python3 -m venv "$VENV_DIR"
    else
        python3 -m venv "$VENV_DIR"
    fi
    log "Venv erstellt: ${VENV_DIR}"
else
    log "Venv existiert bereits"
fi

# Abhängigkeiten installieren (als User)
if [ -f "${SCRIPT_DIR}/requirements.txt" ]; then
    if [ -n "${SUDO_USER}" ] && [ "${SUDO_USER}" != "root" ]; then
        sudo -u "${REAL_USER}" "${VENV_DIR}/bin/pip" install -q -r "${SCRIPT_DIR}/requirements.txt" 2>/dev/null && \
            log "Python-Abhängigkeiten installiert" || \
            warn "Einige Pakete konnten nicht installiert werden (optional)"
    else
        "${VENV_DIR}/bin/pip" install -q -r "${SCRIPT_DIR}/requirements.txt" 2>/dev/null && \
            log "Python-Abhängigkeiten installiert" || \
            warn "Einige Pakete konnten nicht installiert werden (optional)"
    fi
fi

# ─── Desktop-Eintrag ──────────────────────────────────────
echo ""
echo "--- Schritt 4: Desktop-Eintrag ---"

mkdir -p "$DESKTOP_DIR"
mkdir -p "$BIN_DIR"

# Starter-Script in ~/.local/bin
STARTER="${BIN_DIR}/k12-fan-gui"
cat > "$STARTER" << STARTEREOF
#!/usr/bin/env bash
exec "${VENV_DIR}/bin/python" "${GUI_SCRIPT}"
STARTEREOF
chmod +x "$STARTER"
log "Starter: ${STARTER}"

# .desktop-Datei
DESKTOP_FILE="${DESKTOP_DIR}/k12-fan-gui.desktop"
cat > "$DESKTOP_FILE" << DESKTOPEOF
[Desktop Entry]
Type=Application
Name=K12 Fan Control
Comment=GMKtec NucBox K12 Lüftersteuerung
Exec=${STARTER}
Icon=k12-fan
Terminal=false
Categories=System;Hardware;
Keywords=fan;cooling;k12;gmktec;
DESKTOPEOF
chmod +x "$DESKTOP_FILE"

# Icon für Desktop-Eintrag
ICON_DIR="${HOME}/.local/share/icons/hicolor/64x64/apps"
mkdir -p "$ICON_DIR"
# Minimales SVG-Icon
cat > "${ICON_DIR}/k12-fan.svg" << 'ICONEOF'
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
  <circle cx="32" cy="32" r="28" fill="#89b4fa"/>
  <circle cx="32" cy="32" r="20" fill="#1e1e2e"/>
  <text x="32" y="40" text-anchor="middle" font-size="24" font-weight="bold" fill="#89b4fa" font-family="sans-serif">K</text>
</svg>
ICONEOF
log "Icon installiert"

# Desktop-DB aktualisieren (wenn verfügbar)
if command -v update-desktop-database &>/dev/null; then
    update-desktop-database "$DESKTOP_DIR" 2>/dev/null || true
fi

# ─── Fertig ───────────────────────────────────────────────
echo ""
echo "=========================================="
echo "  Installation abgeschlossen!"
echo "=========================================="
echo ""
echo "Start:"
echo "  GUI:    ${STARTER}"
echo "  Oder:   K12 Fan Control im Anwendungsmenü"
echo ""
echo "Deinstallation:"
echo "  sudo rm -rf ${INSTALL_DIR}"
echo "  sudo rm -f ${POLKIT_FILE}"
echo "  rm -rf ${VENV_DIR}"
echo "  rm -f ${STARTER}"
echo "  rm -f ${DESKTOP_FILE}"
echo "  rm -f ${ICON_DIR}/k12-fan.svg"
echo ""
