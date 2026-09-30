"""Pytest-Konfiguration für die k12-fan Test-Suite.

Wichtig: k12-fan-gui.py importiert tkinter auf Modulebene. Für den
Headless-Testlauf wird daher VOR dem Import ein minimaler tkinter-Stub
in sys.modules injiziert. Danach wird k12-fan-gui.py (Dateiname enthält
Bindestriche → normaler Import unmöglich) via importlib geladen und als
sys.modules["k12_fan_gui"] registriert.
"""

import importlib.util
import sys
import types
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# ─── tkinter-Stub (vor JEDEM Import von k12-fan-gui injizieren) ─────────────
# Die GUI verwendet tk/ttk erst zur Laufzeit (K12FanGUI.__init__ etc.);
# auf Modulebene reicht ein leeres Modul mit einem ttk-Attribut aus.
if "tkinter" not in sys.modules or not hasattr(sys.modules["tkinter"], "__k12_stub__"):
    tkinter_stub = types.ModuleType("tkinter")
    tkinter_stub.__k12_stub__ = True
    ttk_stub = types.ModuleType("tkinter.ttk")
    tkinter_stub.ttk = ttk_stub
    sys.modules["tkinter"] = tkinter_stub
    sys.modules["tkinter.ttk"] = ttk_stub

# ─── k12-fan-gui.py laden (Bindestrich-Dateiname → importlib) ───────────────
_SPEC = importlib.util.spec_from_file_location("k12_fan_gui", REPO_ROOT / "k12-fan-gui.py")
k12_fan_gui = importlib.util.module_from_spec(_SPEC)
sys.modules["k12_fan_gui"] = k12_fan_gui
_SPEC.loader.exec_module(k12_fan_gui)


@pytest.fixture
def gui():
    """Das importierte k12-fan-gui Modul (ohne GUI-Instanz)."""
    return k12_fan_gui
