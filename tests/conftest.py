import sys
import os,types
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
if os.name=='nt':
    sys.modules.setdefault('pwd',types.SimpleNamespace(getpwuid=lambda uid:types.SimpleNamespace(pw_name='test')))


import pytest
@pytest.fixture(autouse=True)
def deterministic_halo_preview(monkeypatch):
    import card_halo
    monkeypatch.setattr(card_halo,'PREVIEW_ALL',False)
