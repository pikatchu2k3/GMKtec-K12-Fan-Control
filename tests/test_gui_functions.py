"""Tests für die Helper-Funktionen aus k12-fan-gui.py.

Das Modul wird in tests/conftest.py mit injiziertem tkinter-Stub geladen
(siehe dort) und über das Fixture `gui` bereitgestellt.
"""

import os

import pytest


# ─── _parse_helper_payload ───────────────────────────────────────────────────

def test_parse_helper_payload_valid_status_json(gui):
    raw = (
        '{"cpu_temp":45,"gpu_temp":39,"fan1_rpm":2100,"fan2_rpm":1800,'
        '"mode":"Balanced","mode_code":0,"fan1_pct":0,"fan2_pct":0,'
        '"fan1_manual":0,"fan2_manual":0}'
    )
    data = gui._parse_helper_payload(raw)
    assert data["cpu_temp"] == 45
    assert data["mode"] == "Balanced"
    assert data["fan1_rpm"] == 2100
    assert data["mode_code"] == 0


def test_parse_helper_payload_valid_ok_json(gui):
    data = gui._parse_helper_payload('{"ok":true,"mode_code":2}')
    assert data == {"ok": True, "mode_code": 2}


def test_parse_helper_payload_error_key_raises_helpererror(gui):
    raw = '{"error":"Cannot open /dev/mem: Permission denied"}'
    with pytest.raises(gui.HelperError) as excinfo:
        gui._parse_helper_payload(raw)
    assert "Cannot open /dev/mem" in str(excinfo.value)


def test_parse_helper_payload_invalid_json_raises_helpererror(gui):
    with pytest.raises(gui.HelperError):
        gui._parse_helper_payload("das ist kein json")


def test_parse_helper_payload_invalid_json_uses_fallback_message(gui):
    with pytest.raises(gui.HelperError) as excinfo:
        gui._parse_helper_payload("{broken", fallback="Helper abgestürzt")
    assert "Helper abgestürzt" in str(excinfo.value)


def test_parse_helper_payload_invalid_json_default_message(gui):
    with pytest.raises(gui.HelperError) as excinfo:
        gui._parse_helper_payload("<html>404</html>")
    assert str(excinfo.value) == "Ungültige Helper-Antwort"


# ─── find_helper / HELPER_PATHS ──────────────────────────────────────────────

def _make_executable(path):
    path.write_text("#!/bin/sh\nexit 0\n")
    os.chmod(path, 0o755)


def test_find_helper_prefers_first_existing_executable(gui, tmp_path, monkeypatch):
    first = tmp_path / "helper-a"
    second = tmp_path / "helper-b"
    missing = tmp_path / "gibt-es-nicht"
    _make_executable(first)
    _make_executable(second)
    monkeypatch.setattr(gui, "HELPER_PATHS", [str(missing), str(first), str(second)])
    assert gui.find_helper() == str(first)


def test_find_helper_skips_non_executable_file(gui, tmp_path, monkeypatch):
    not_exec = tmp_path / "helper-noexec"
    not_exec.write_text("nicht ausführbar")
    exec_helper = tmp_path / "helper-exec"
    _make_executable(exec_helper)
    monkeypatch.setattr(gui, "HELPER_PATHS", [str(not_exec), str(exec_helper)])
    assert gui.find_helper() == str(exec_helper)


def test_find_helper_returns_none_when_nothing_matches(gui, tmp_path, monkeypatch):
    monkeypatch.setattr(
        gui, "HELPER_PATHS", [str(tmp_path / "x"), str(tmp_path / "y")]
    )
    assert gui.find_helper() is None


def test_find_helper_empty_path_list(gui, monkeypatch):
    monkeypatch.setattr(gui, "HELPER_PATHS", [])
    assert gui.find_helper() is None


def test_find_helper_resolves_known_helper_paths(gui):
    """Gegen die echten HELPER_PATHS: Ergebnis muss existierend+ausführbar sein
    und in HELPER_PATHS enthalten (Repo liefert k12-fan-helper an Position 1)."""
    result = gui.find_helper()
    if result is not None:
        assert result in gui.HELPER_PATHS
        assert os.path.isfile(result)
        assert os.access(result, os.X_OK)


def test_known_helper_paths_shape(gui):
    """HELPER_PATHS enthält installierten Pfad, Repo-Pfad neben der GUI und CWD."""
    assert gui.HELPER_PATHS[0] == "/usr/lib/k12-fan/k12-fan-helper"
    expected_repo_path = os.path.join(
        os.path.dirname(os.path.abspath(gui.__file__)), "k12-fan-helper"
    )
    assert gui.HELPER_PATHS[1] == expected_repo_path
    assert gui.HELPER_PATHS[1].endswith("k12-fan-helper")
    assert gui.HELPER_PATHS[2] == "./k12-fan-helper"
