"""Tests für k12-fan-helper.c: Argument-Validierung und Exit-Codes.

Das Binary wird (ohne Root, ohne /dev/mem-Zugriff) einmal pro Session
kompiliert. Alle getesteten Kommandos scheitern in der Argument-Validierung
BEVOR ec_init()/mmap ausgeführt wird — außer 'status', das ohne Root-Rechte
erwartungsgemäß an open("/dev/mem") scheitert (Exit != 0).
"""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
HELPER_SRC = REPO_ROOT / "k12-fan-helper.c"
HELPER_BIN = Path(__file__).resolve().parent / "helper_bin"

requires_root = pytest.mark.skipif(
    os.geteuid() == 0,
    reason="ohne /dev/mem-Test nur als Nicht-Root sinnvoll",
)


@pytest.fixture(scope="session")
def helper_bin():
    """Kompiliert den C-Helper nach tests/helper_bin und räumt auf."""
    gcc = shutil.which("gcc")
    if gcc is None:
        pytest.skip("gcc nicht verfügbar")
    proc = subprocess.run(
        [gcc, "-O2", "-Wall", "-Wextra", "-o", str(HELPER_BIN), str(HELPER_SRC)],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )
    assert proc.returncode == 0, f"Kompilierung fehlgeschlagen:\n{proc.stderr}"
    assert HELPER_BIN.is_file()
    yield str(HELPER_BIN)
    HELPER_BIN.unlink(missing_ok=True)


def run_helper(helper_bin, *args):
    return subprocess.run(
        [helper_bin, *args],
        capture_output=True,
        text=True,
        timeout=10,
    )


# ─── Ungültige Mode-Werte ────────────────────────────────────────────────────

@pytest.mark.parametrize("bad_mode", ["3", "7", "-1", "99", "abc", "1x", ""])
def test_invalid_mode_value_exits_nonzero(helper_bin, bad_mode):
    proc = run_helper(helper_bin, "mode", bad_mode)
    assert proc.returncode != 0, f"mode {bad_mode!r} muss fehlschlagen"
    assert '"error"' in proc.stderr


def test_mode_without_argument_exits_nonzero(helper_bin):
    proc = run_helper(helper_bin, "mode")
    assert proc.returncode != 0
    assert '"error"' in proc.stderr


# ─── Ungültige Fan-Werte ─────────────────────────────────────────────────────

@pytest.mark.parametrize("bad_pct", ["101", "255", "-1", "-100", "abc", "1.5", "50%"])
def test_invalid_fan_value_exits_nonzero(helper_bin, bad_pct):
    for cmd in ("fan1", "fan2"):
        proc = run_helper(helper_bin, cmd, bad_pct)
        assert proc.returncode != 0, f"{cmd} {bad_pct!r} muss fehlschlagen"
        assert '"error"' in proc.stderr


@pytest.mark.parametrize("cmd", ["fan1", "fan2"])
def test_fan_without_argument_exits_nonzero(helper_bin, cmd):
    proc = run_helper(helper_bin, cmd)
    assert proc.returncode != 0
    assert '"error"' in proc.stderr


# ─── Unbekannte Kommandos ────────────────────────────────────────────────────

@pytest.mark.parametrize("unknown", ["nonsense", "fan3", "set-mode", "STATUS", ""])
def test_unknown_command_exits_nonzero(helper_bin, unknown):
    proc = run_helper(helper_bin, unknown)
    assert proc.returncode != 0, f"unbekanntes Kommando {unknown!r} muss fehlschlagen"
    assert '"error"' in proc.stderr
    assert "Unknown command" in proc.stderr


def test_no_arguments_exits_nonzero(helper_bin):
    proc = run_helper(helper_bin)
    assert proc.returncode != 0
    assert "Usage:" in proc.stdout


# ─── status ohne /dev/mem-Zugriff (Nicht-Root) ───────────────────────────────

@requires_root
def test_status_without_devmem_access_exits_nonzero(helper_bin):
    """Ohne Root kann open("/dev/mem") nicht gelingen → cmd_status() liefert 1."""
    proc = run_helper(helper_bin, "status")
    assert proc.returncode != 0
    assert '"error"' in proc.stderr


@requires_root
@pytest.mark.parametrize("cmd_args", [["mode", "1"], ["fan1", "50"], ["auto"]])
def test_ec_commands_fail_without_devmem(helper_bin, cmd_args):
    """Auch gültige Argumente scheitern ohne /dev/mem-Zugriff (ec_init fehlgeschlagen)."""
    proc = run_helper(helper_bin, *cmd_args)
    assert proc.returncode != 0
    assert '"error"' in proc.stderr


# ─── --help ──────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("flag", ["--help", "-h"])
def test_help_exits_zero(helper_bin, flag):
    proc = run_helper(helper_bin, flag)
    assert proc.returncode == 0, f"{flag} muss Exit-Code 0 liefern"
    assert "Usage:" in proc.stdout
    for expected in ("status", "mode", "fan1", "fan2", "auto"):
        assert expected in proc.stdout
