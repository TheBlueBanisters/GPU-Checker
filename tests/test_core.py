import ast
import json
from pathlib import Path
import sys
import types
from unittest.mock import patch

import pytest
import backend
import profiles

# pwd exists only on remote Linux; allow pure parser tests on Windows.
sys.modules.setdefault("pwd", types.SimpleNamespace(getpwuid=lambda uid: types.SimpleNamespace(pw_name="test")))
import remote_probe as probe


def test_modern_driver_graphics_compute_and_na():
    xml = '''<nvidia_smi_log><driver_version>580</driver_version><gpu>
    <uuid>GPU-A</uuid><product_name>Example</product_name><utilization><gpu_util>N/A</gpu_util></utilization>
    <gpu_power_readings><instant_power_draw>30.50 W</instant_power_draw></gpu_power_readings>
    <processes><process_info><pid>123</pid><type>C+G</type><used_memory>N/A</used_memory>
    <process_name>/path with spaces/python</process_name></process_info></processes></gpu></nvidia_smi_log>'''
    data = probe.parse_xml(xml, lambda pid: {"cwd": "无权限", "user": "alice"})
    assert data["gpus"][0]["power"] == 30.5
    assert data["gpus"][0]["util"] is None
    assert data["processes"][0]["kind"] == "C+G"
    assert data["processes"][0]["memory"] is None
    assert data["processes"][0]["cwd"] == "无权限"


def test_permission_is_reported_not_escalated():
    with patch("builtins.open", side_effect=PermissionError):
        assert probe.process_details(123)["user"] == "无权限"


def test_pid_reuse_is_detected():
    from unittest.mock import mock_open
    a = "123 (name) " + " ".join(["S", "1"] + ["0"] * 17 + ["100"])
    b = a[:-3] + "200"
    opened = mock_open()
    opened.side_effect = [mock_open(read_data=a).return_value, mock_open(read_data=b).return_value]
    with patch("builtins.open", opened), patch.object(probe.os, "stat", return_value=types.SimpleNamespace(st_uid=1)), patch.object(probe.os, "readlink", return_value="/work"):
        assert probe.process_details(123)["user"] == "进程已变化"


@pytest.mark.parametrize("host", ["-oProxyCommand=bad", "server; touch foo", "server\nwhoami", "$(id)", "host name"])
def test_host_cannot_inject_command(host):
    with pytest.raises(ValueError):
        backend.validate({"host": host})


def test_profiles_drop_secrets_and_portable_paths(tmp_path, monkeypatch):
    monkeypatch.setattr(profiles, "DATA", tmp_path)
    profiles.save([{"host": "server", "password": "do-not-save", "passphrase": "do-not-save", "key": "keys/id"}])
    saved = (tmp_path / "profiles.json").read_text()
    assert "do-not-save" not in saved
    assert json.loads(saved)[0]["key"] == "keys/id"
    assert backend.resolve_path("keys/id") == str(backend.BASE / "keys/id")


def test_import_config_and_backup(tmp_path, monkeypatch):
    monkeypatch.setattr(profiles, "DATA", tmp_path / "data")
    f = tmp_path / "config"
    f.write_text('Host cluster\n HostName 127.0.0.1\n User alice\n IdentityFile ~/.ssh/id_ed25519\nHost *.lab\n User bob\n')
    assert profiles.import_config(f)[0] == ["cluster"]
    profiles.import_config(f)
    assert (tmp_path / "data/ssh_config.backup").exists()


def test_probe_does_not_control_workload():
    tree = ast.parse(Path(probe.__file__).read_text(encoding="utf-8"))
    attrs = {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
    assert not {"kill", "killpg", "ptrace", "chmod", "chown", "unlink", "remove"} & attrs
    assert "cmdline" not in {n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str)}


def test_native_uses_config_and_quoted_argv(tmp_path, monkeypatch):
    monkeypatch.setattr(backend, "DATA", tmp_path)
    monkeypatch.setattr(backend, "ssh_executable", lambda: "ssh.exe")
    (tmp_path / "ssh_config").write_text("Host sample")
    (tmp_path / "known_hosts").touch()
    p = profiles.clean({"host": "sample", "key": "keys/key with spaces"})
    args = backend.native_args(p)
    assert args[args.index("-F")+1] == str(tmp_path / "ssh_config")
    assert "StrictHostKeyChecking=yes" in args
    assert args[args.index("-i")+1].endswith("key with spaces")
    assert args[-2] == "sample"


def test_new_install_has_no_personal_or_automatic_hosts(tmp_path,monkeypatch):
    monkeypatch.setattr(profiles,"DATA",tmp_path)
    assert profiles.load()==[]
    profiles.save(profiles.load())
    assert profiles.load()==[]
