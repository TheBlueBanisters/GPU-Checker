import os
import profiles
import vault
import remote_probe
from sessions import HostSession
from test_multihost import FakeMonitor


def test_vault_roundtrip_and_endpoint_binding():
    if os.name!='nt':
        return
    p=profiles.clean({'host':'vault-test.invalid','user':'test','port':'22','mode':profiles.MODES[2]})
    try:
        vault.save_password(p,'test-only-temporary-secret')
        assert vault.get_password(p)=='test-only-temporary-secret'
        assert vault.get_password(dict(p,host='different.invalid'))==''
    finally:
        vault.forget_password(p)
    assert vault.get_password(p)==''


def test_saved_password_is_used_without_dialog(monkeypatch):
    monkeypatch.setattr(vault,'get_password',lambda p:'test-secret')
    s=HostSession(profiles.clean({'host':'pw.test','mode':profiles.MODES[2]}),factory=FakeMonitor)
    s.start()
    assert s.running and s.password=='test-secret'
    s.stop()
    assert s.password==''


def test_no_gpu_is_connected_and_fresh(monkeypatch):
    monkeypatch.setattr(remote_probe.shutil,'which',lambda x:None)
    monkeypatch.setattr(remote_probe.glob,'glob',lambda p:[])
    data=remote_probe.sample()
    assert data['gpu_status']=='no_gpu' and data['gpus']==[] and 'error' not in data
    s=HostSession(profiles.clean({'host':'cpu.test'}),factory=FakeMonitor)
    s.start()
    s.worker.data.emit(data)
    assert s.fresh and s.state=='在线 · 无 GPU'
    s.stop()


def test_driver_missing_is_distinct_from_no_gpu(monkeypatch):
    monkeypatch.setattr(remote_probe.shutil,'which',lambda x:None)
    monkeypatch.setattr(remote_probe.glob,'glob',lambda p:['/dev/nvidia0'] if '/dev/' in p else [])
    assert remote_probe.sample()['gpu_status']=='unavailable'


def test_disconnect_race_does_not_prevent_pause():
    from backend import Monitor
    class ClosedChannel:
        def close(self):
            raise EOFError()
    class Client:
        closed=False
        def close(self):
            self.closed=True
    worker=Monitor(profiles.clean({'host':'test.invalid'}))
    worker.channel=ClosedChannel()
    worker.client=Client()
    worker.stop()
    worker.stop()
    assert worker.client.closed and worker.stop_event.is_set()
