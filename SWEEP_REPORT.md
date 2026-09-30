# Codebase Sweep Report — k12-fan

Date: 2026-09-07 · Scope: `k12-fan-gui.py`, `k12-fan-helper.c`, `install.sh`, `requirements.txt`, `README.md`, `anleitung.md`

---

## 1. TODO / FIXME / XXX Markers

**None found.** The only regex hit is a false positive: `k12-fan-helper.c:131` — the comment `/* nicht druckbare Steuerzeichen → \uXXXX */` contains "XXXX" as part of the `\uXXXX` escape notation, not a marker.

---

## 2. Dead Code / Unused Imports

### k12-fan-gui.py
| Item | Location | Note |
|------|----------|------|
| `import platform` | line 22 | Never used. |
| `self.last_status` | lines 113, 405 | Write-only; assigned but never read anywhere. |
| `theme = style.theme_use("clam")` | line 162 | Return value never used. |
| `result = call_helper(...)` | lines 475, 485 | Return values in `set_mode()` / `set_fan()` never used. |
| `def on_click(icon, item)` | lines 568–575 | Defined inside `_minimize_to_tray()` but never referenced — the tray menu is built with separate lambdas. Dead code. |
| Style configs `Mode.TButton`, `Active.TButton`, `Danger.TButton` | lines 177–194 | Configured but never applied to any widget (mode buttons are plain `tk.Button` with direct `bg=`). Dead styles. |
| `Image, ImageDraw` imports in `_check_tray()` | line 539 | Imported only as an availability probe and unused in that scope (linters will flag). |

### k12-fan-helper.c
| Item | Location | Note |
|------|----------|------|
| `#include <sys/types.h>` | line 28 | Redundant; required types come via `stdint.h`/`unistd.h`. |

### Repo hygiene
- A compiled `k12-fan-helper` binary and `__pycache__/` exist in the worktree. Both are correctly covered by `.gitignore` (git status is clean), but the binary is a local build artifact that could be removed.

---

## 3. Bugs & Improvement Opportunities

### Bugs

1. **install.sh: unbound variable crash at the end** — `POLKIT_FILE` is only assigned when `HAVE_POLKIT=true` (line 126), but the final uninstall hint echoes `${POLKIT_FILE}` (line 236). With `set -u` (line 13) on a system **without pkexec**, the script aborts with "POLKIT_FILE: unbound variable" after everything else already succeeded. Fix: initialize `POLKIT_FILE=""` upfront or guard the echo.

2. **Helper exits 0 on failure → GUI shows bogus status** — `cmd_status()`/`cmd_mode()`/`cmd_fan()` print the error JSON to stderr and return; `main()` then returns **0**. In `call_helper()` (gui lines 88–93), exit code 0 + empty stdout + stderr triggers `json.loads(proc.stderr)` and **returns the error dict as valid status data**. The GUI then renders 0 °C / 0 RPM with no error banner. Fix: return non-zero from `main()` on EC failure, and/or have the GUI reject payloads containing an `"error"` key.

3. **Sudo fallback mostly unreachable** — in `call_helper()` (gui lines 74–104), if `pkexec` exists but denies/fails (non-zero exit, e.g. user cancels auth), the code raises `HelperError` immediately (line 98) instead of `continue`-ing to the `sudo -n` attempt. Only a missing `pkexec` binary (`OSError`) reaches the fallback.

4. **Thread-safety of tray "Beenden"** — the pystray menu lambda (gui line 579) runs in the tray thread and calls `self.root.after(0, ...)`. Calling into Tcl from a non-main thread is not guaranteed safe (works on CPython usually, but is a known crash source). Same pattern, lower risk, in the outer `on_click` (dead code anyway).

5. **`--helper` as last argument silently ignored** — hand-rolled parsing in `__main__` (gui lines 619–623) requires a following token; `python3 k12-fan-gui.py --helper` with no value fails silently. Unknown args are ignored too. Use `argparse`.

6. **Slider release ordering** — each `ttk.Scale` binds `<ButtonRelease-1>` twice (gui lines 330–336). The first handler calls `set_fan()` → `refresh()` while `fan_dragging[fid]` is still `True`, so the fresh manual value is skipped and the slider only syncs on the next 2 s tick. Harmless but fragile; collapse to one handler that clears the flag first.

7. **README references two missing files** — `![Screenshot](.github/screenshot.png)` (README:12) and `[LICENSE](LICENSE)` (README:151) do not exist in the repo. Broken links/badges.

8. **install.sh minor robustness** — `REAL_USER="${USER}"` (line 24) can trigger the same `set -u` unbound-variable error when run as root without `SUDO_USER` (e.g. via `su`). Also, the compiled binary is left behind in the source directory after install.

### Improvement opportunities

- **GUI**: broad `except Exception` duplicated for `HelperError` (gui lines 458–463) — collapse into one handler. `_on_slider` configures the label twice when pct == 0. `refresh_timer` guard in `_on_close` (line 606) uses `hasattr`, but the attribute is always present (possibly `None`) — `after_cancel(None)` would raise; check truthiness instead.
- **Helper**: consider a `--version`/`-v` command; the JSON escape buffer arithmetic in `json_escape()` is correct but delicate — a bounded `snprintf`-based writer would be simpler to audit.
- **requirements.txt**: unpinned (`pystray`, `Pillow`) — pin minimum versions for reproducible venvs.
- **install.sh**: log message claims a hardcoded size "kompiliert (11 KB)" (line 97); the installed GUI copy in `/usr/lib/k12-fan/` goes stale when the repo script changes — worth a note or a reinstall reminder.
- **README**: "80-line C helper" (README:29 and README:128) — actual size is **330 lines**. Update the claim.

---

## 4. README.md vs anleitung.md Consistency

**Consistent:** CLI command block, uninstall commands, temperature color thresholds (< 50 green, < 65 yellow, else red), 2 s refresh, tray/pystray caveat, autostart option, mode names/codes (0/1/2), prerequisites tables (except the FAQ bug below).

**Inconsistencies:**

1. **Download source & folder name** — README: `git clone https://github.com/pikatchu2k3/GMKtec-K12-Fan-Control.git` → `cd GMKtec-K12-Fan-Control`. anleitung.md:26–35: download folder `k12-fan-control` "von Nextcloud". Different source, different casing/name. Align or explain the Nextcloud channel.
2. **Install step list granularity** — README lists 6 steps (venv, optional pystray deps, icon, Polkit rule); anleitung lists 4 and **never mentions the Polkit rule or the optional Python deps**. Not contradictory, but anleitung users can't connect the "Polkit" uninstall line to anything.
3. **anleitung FAQ bug (line 194)** — "Installiere `python3-tk` (Fedora) oder `python3-tk` (Ubuntu)": the Fedora package is **`python3-tkinter`**, as anleitung's own prerequisites table (line 22) and install.sh (line 62) correctly state.
4. **README "80-line C helper"** — vs. 330 actual lines (also a factual error, see §3).
5. **anleitung FAQ overstatement** — "Ein Neustart setzt alles auf die BIOS-Standards zurück" (line 188): a restart restores *automatic* control but nothing in the code guarantees BIOS defaults; and README explicitly warns manual EC writes are persistent-ish. Minor, but the two docs' tone differs on how "safe" manual mode is.

---

### Summary

No markers; a handful of dead-code items (mostly in the GUI); two real defects worth fixing first: the **install.sh `POLKIT_FILE` unbound-variable crash** and the **helper's exit-0-on-failure masking EC errors in the GUI**. Doc fixes: Fedora package name in the anleitung FAQ, the "80-line" claim, and the GitHub-vs-Nextcloud discrepancy.
