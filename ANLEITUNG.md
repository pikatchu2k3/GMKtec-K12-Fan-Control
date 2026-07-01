# K12 Fan Control – Bedienungsanleitung

## Was ist das?

Ein Programm für den **GMKtec NucBox K12** Mini-PC, mit dem du die Lüftergeschwindigkeit und den Leistungsmodus einstellen kannst – per Mausklick oder Terminal.

---

## Installation

### 1. Voraussetzungen

Dein K12 braucht:
- **Linux** (Fedora, Ubuntu, Arch – egal)
- **Python 3** (ist bei Linux immer dabei)
- **GCC** (C-Compiler) – zum Übersetzen des Helfer-Programms

**Fehlt etwas?** Dann öffne ein Terminal und installiere es:

| Distro | Befehl |
|--------|--------|
| **Fedora** | `sudo dnf install python3 python3-tkinter gcc` |
| **Ubuntu** | `sudo apt install python3 python3-venv python3-tk build-essential` |
| **Arch** | `sudo pacman -S python tk base-devel` |

### 2. Herunterladen

Lade den Ordner `k12-fan-control` von Nextcloud herunter oder kopiere ihn auf deinen K12.

### 3. Installieren

Öffne ein Terminal, wechsle in den Ordner und führe aus:

```bash
cd k12-fan-control
chmod +x install.sh
./install.sh
```

Das Installations-Script:
1. Übersetzt den C-Helfer
2. Installiert ihn systemweit (mit SUID – du brauchst später kein `sudo`)
3. Erstellt eine Python-Umgebung (venv)
4. Legt einen Menü-Eintrag an

**Wichtig:** Das Script fragt nach deinem Passwort (`sudo`) – das ist normal, es muss Root-Dateien anlegen.

**Nach der Installation** findest du **K12 Fan Control** in deinem Anwendungsmenü.

---

## Programm starten

| Weg | Anleitung |
|-----|-----------|
| **Menü** | Klick auf "Aktivitäten" (oder Windows-Taste) → tipp "K12 Fan Control" → Enter |
| **Terminal** | Tippe `~/.local/bin/k12-fan-gui` und drück Enter |

Das Fenster öffnet sich in der Bildschirmmitte.

---

## Der Bildschirm (GUI)

```
┌─ K12 Fan Control ──────────────────────────┐
│                                             │
│ ┌── Status ───────────────────────────────┐ │
│ │  CPU: 42°C          Fan 1:  792 RPM     │ │
│ │  GPU: 38°C          Fan 2:  346 RPM     │ │
│ │  Mode: Balanced     Fan 1:   0%  ↺      │ │
│ │                      Fan 2:   0%  ↺      │ │
│ └──────────────────────────────────────────┘ │
│                                              │
│  Modus:   [⚖ Balanced] [⚡ Performance] [🌙 Silent]  │
│                                              │
│  Fan 1:  ──────────●─────────────  50%  [Auto] │
│  Fan 2:  ─────●────────────────  20%  [Auto] │
│                                              │
│  Optionen:                                   │
│  ☐ Autostart (nach Login)                    │
│  ☐ In Tray minimieren                        │
│                                              │
│  ────────────────────────────────────────    │
│  ✓ OK  |  22:35:42               [Schließen] │
└──────────────────────────────────────────────┘
```

---

## Funktionen im Detail

### 🔴 Status-Anzeige (oben)

Hier siehst du live, was dein K12 gerade macht:

| Anzeige | Bedeutung | Farbe |
|---------|-----------|-------|
| **CPU: 42°C** | Temperatur des Prozessors | Grün < 50°C · Gelb < 65°C · Rot ≥ 65°C |
| **Fan 1: 792 RPM** | Drehzahl Lüfter 1 (Umdrehungen pro Minute) | Weiß |
| **Fan 2: 346 RPM** | Drehzahl Lüfter 2 | Weiß |
| **Mode: Balanced** | Aktueller Leistungsmodus | Blau |
| **Fan 1: 0% ↺** | Lüfter 1: 0% = Auto (↺) | Grau |

Die Anzeige aktualisiert sich **alle 2 Sekunden** von selbst.

### 🎮 Modus-Umschaltung (Mitte)

Drei Knöpfe für den Leistungsmodus:

| Modus | Wann benutzen? | Wirkung |
|-------|----------------|---------|
| **⚖ Balanced** | Alltag, Surfen, Büro | Ausgewogen zwischen Lautstärke und Kühlung |
| **⚡ Performance** | Zocken, Videoschnitt, Rendern | Lüfter drehen früher hoch – CPU bleibt kühl |
| **🌙 Silent** | Nachts, Filme schauen | Lüfter bleiben lange aus – leiser, aber wärmer |

👉 **Einfach den Knopf drücken** – die Änderung wirkt sofort.

### 🌀 Lüfter manuell steuern (unten)

Mit den Schiebereglern kannst du die Lüfter-Geschwindigkeit **selbst bestimmen**:

- **Schieber nach rechts** → mehr Drehzahl (50% = halbe Kraft, 100% = volle Pulle)
- **Schieber nach links** → weniger Drehzahl
- **Ganz links (0%)** → wieder Automatik (↺)

**Tipp:** Zieh den Schieber langsam – das Programm schickt den Befehl erst, wenn du loslässt.

**"Auto"-Knopf** neben jedem Lüfter → schaltet den Lüfter zurück auf Automatik.

### ⚙️ Optionen (unten)

| Option | Was passiert? |
|--------|---------------|
| **Autostart** | K12 Fan Control startet automatisch, wenn du dich am PC anmeldest |
| **In Tray minimieren** | Schiebt das Fenster in die Taskleiste (Symbol unten rechts) |

> **Tray-Hinweis:** Dafür musst du `pystray` installiert haben. Falls nicht, ist die Option ausgegraut.

---

## Terminal (für Fortgeschrittene)

Du brauchst kein Fenster – alles geht auch im Terminal:

```bash
# Status anzeigen
/usr/lib/k12-fan/k12-fan-helper status

# Modus ändern (0=Balanced, 1=Performance, 2=Silent)
/usr/lib/k12-fan/k12-fan-helper mode 1

# Lüfter 1 auf 40%
/usr/lib/k12-fan/k12-fan-helper fan1 40

# Lüfter 2 auf 60%
/usr/lib/k12-fan/k12-fan-helper fan2 60

# Alles zurück auf Automatik
/usr/lib/k12-fan/k12-fan-helper auto
```

**Kein `sudo` nötig** – das SUID-Binary erledigt das für dich.

---

## Deinstallation

Willst du alles entfernen:

```bash
sudo rm -rf /usr/lib/k12-fan/
sudo rm -f /usr/share/polkit-1/actions/com.k12fan.helper.policy
rm -rf ~/.local/share/k12-fan/
rm -f ~/.local/bin/k12-fan-gui
rm -f ~/.local/share/applications/k12-fan-gui.desktop
rm -f ~/.local/share/icons/hicolor/*/apps/k12-fan.svg
```

---

## Häufige Fragen

**F: Warum stehen die Lüfter, obwohl ich 20% eingestellt habe?**
A: Bei 20% und niedrigen Temperaturen (< 55°C) drehen manche Lüfter gar nicht – das ist normal. Erst bei höherer Last oder mehr Prozent fangen sie an zu laufen.

**F: Kann ich was kaputt machen?**
A: Nein. Das Schlimmste, was passieren kann: Der K12 wird wärmer oder lauter als nötig. Ein Neustart setzt alles auf die BIOS-Standards zurück.

**F: Geht das auch unter Windows?**
A: Nein, nur Linux. Der Helfer greift auf `/dev/mem` zu – das gibt es unter Windows nicht.

**F: Die GUI startet nicht – "tkinter nicht gefunden"?**
A: Installiere `python3-tk` (Fedora) oder `python3-tk` (Ubuntu) – siehe Installation oben.
