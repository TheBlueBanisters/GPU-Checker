import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import json
from PySide6.QtWidgets import QApplication, QFileDialog
import app as ui
import backend
import profiles


def test_import_export_and_fresh_machine_import(tmp_path, monkeypatch):
    application = QApplication.instance() or QApplication([])
    ui.configure_app(application)
    original = tmp_path / "original"
    original.mkdir()
    for module in (ui, profiles, backend):
        monkeypatch.setattr(module, "DATA", original)
    config = tmp_path / "config"
    config.write_text("Host cluster\n HostName example.test\n User alice\n IdentityFile ~/.ssh/id_ed25519\n", encoding="utf-8")
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *a, **k: (str(config), ""))
    monkeypatch.setattr(ui.Window, "notify", lambda *a: None)
    w = ui.Window(autostart=False)
    w.import_ssh()
    assert w.selected.profile['host'] == "cluster"
    assert (original / "ssh_config").exists()
    w.selected.password='never-export-this'
    exported = tmp_path / "migration.json"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a, **k: (str(exported), ""))
    w.export_bundle()
    blob = exported.read_text(encoding="utf-8")
    assert "never-export-this" not in blob
    assert "User alice" in json.loads(blob)["ssh_config"]
    w.close()
    moved = tmp_path / "moved"
    moved.mkdir()
    for module in (ui, profiles, backend):
        monkeypatch.setattr(module, "DATA", moved)
    fresh = ui.Window(autostart=False)
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *a, **k: (str(exported), ""))
    fresh.import_ssh()
    assert fresh.selected.profile['host'] == "cluster"
    assert (moved / "profiles.json").exists()
    assert "Host cluster" in (moved / "ssh_config").read_text()
    assert not fresh.selected.password
    fresh.close()
