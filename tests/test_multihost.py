import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import time
import pytest
from PySide6.QtCore import QObject,Signal
from PySide6.QtWidgets import QApplication
import app as ui
import backend
import profiles
from sessions import HostSession


class FakeMonitor(QObject):
    data=Signal(dict)
    status=Signal(str)
    failed=Signal(str)
    trust=Signal(str,str)
    finished=Signal()

    def __init__(self,profile,password='',passphrase=''):
        super().__init__()
        self.running=False
        self.stops=0

    def isRunning(self):
        return self.running

    def start(self):
        self.running=True

    def stop(self):
        self.stops+=1
        if self.running:
            self.running=False
            self.finished.emit()

    def accept_key(self,accepted):
        self.accepted=accepted


def snapshot(index):
    g={'index':0,'uuid':f'GPU-{index}','name':'NVIDIA test','state':'P0','util':index*10,
       'used':1024.,'total':24576.,'temp':50.,'power':100.,'fan':'40 %'}
    p={'gpu':0,'uuid':g['uuid'],'pid':str(100+index),'user':f'user{index}','kind':'C','memory':1024.,
       'name':'/bin/python','cwd':f'/host{index}/work','exe':'/bin/python','start':'1','ppid':'1'}
    return {'gpus':[g],'processes':[p],'driver':'test','cuda':'test'}


@pytest.fixture
def window(tmp_path,monkeypatch):
    application=QApplication.instance() or QApplication([])
    ui.configure_app(application)
    for module in (ui,backend,profiles):
        monkeypatch.setattr(module,'DATA',tmp_path)
    profiles.save([profiles.clean({'name':f'host{i}','host':f'host{i}.test'}) for i in (1,2)])
    factory=lambda p,parent: HostSession(p,parent,factory=FakeMonitor)
    w=ui.Window(autostart=False,session_factory=factory)
    yield w
    w.close()
    application.processEvents()


def test_switching_keeps_background_sessions_and_history(window):
    w=window
    w.connect_all()
    a,b=list(w.sessions.values())
    aw,bw=a.worker,b.worker
    for _ in range(70):
        aw.data.emit(snapshot(1))
        bw.data.emit(snapshot(2))
    assert w.current[0]['cwd']=='/host1/work'
    assert len(b.history['GPU-2'])==60
    for _ in range(10):
        old_cards=list(w.cards.values())
        w.host_list.setCurrentRow(1)
        assert w.current[0]['cwd']=='/host2/work'
        assert all(card.isHidden() for card in old_cards)
        w.host_list.setCurrentRow(0)
    assert aw is a.worker and bw is b.worker
    assert aw.stops==bw.stops==0
    assert a.sample_count==b.sample_count==70


def test_failure_and_stop_are_isolated(window):
    w=window
    w.connect_all()
    a,b=list(w.sessions.values())
    aw,bw=a.worker,b.worker
    aw.failed.emit('network lost')
    aw.running=False
    aw.finished.emit()
    assert a.retry_timer.isActive()
    assert b.worker is bw and bw.isRunning()
    a.retry_timer.stop()
    a._launch()
    assert a.worker is not aw
    a.worker.data.emit(snapshot(1))
    bw.data.emit(snapshot(2))
    a.stop()
    assert not a.desired and bw.isRunning() and b.fresh


def test_password_auth_failure_does_not_retry_or_leak(window):
    p=profiles.clean({'host':'pw.test','mode':profiles.MODES[2]})
    s=HostSession(p,factory=FakeMonitor)
    s.start()
    assert s.state=='待认证' and s.worker is None
    s.start('secret')
    worker=s.worker
    worker.failed.emit('认证失败')
    worker.running=False
    worker.finished.emit()
    assert not s.desired and not s.retry_timer.isActive() and not s.password


def test_stale_one_host_does_not_mark_other_host_stale(window):
    w=window
    w.connect_all()
    a,b=list(w.sessions.values())
    a.worker.data.emit(snapshot(1))
    b.worker.data.emit(snapshot(2))
    a.received=time.monotonic()-100
    w.tick()
    assert a.state=='数据过期' and b.fresh
    a.worker.data.emit(snapshot(1))
    assert a.fresh


def test_edit_dialog_does_not_put_form_in_sidebar(window):
    from dialogs import HostDialog,ConfigDialog
    d=HostDialog(window,window.selected.profile)
    assert d.host.text()=='host1.test'
    assert not hasattr(window,'host')
    c=ConfigDialog(window)
    c.editor.setPlainText('Host lab\n HostName gpu.test\n User alice\n')
    assert c.check()
    c.editor.setPlainText('Host lab\n HostName gpu.test\n')
    assert not c.check() and 'User' in c.report.text()
    c.close()
    d.close()


def test_pause_is_restored_on_next_launch(window):
    w=window
    w.connect_all()
    first,second=list(w.sessions.values())
    w.toggle_selected()
    assert first.state=='已暂停' and second.running
    stored=profiles.load()
    assert stored[0]['autoconnect'] is False and stored[1]['autoconnect'] is True
    fresh=ui.Window(autostart=False,session_factory=w.session_factory)
    fresh.autostart()
    a,b=list(fresh.sessions.values())
    assert not a.running and a.state=='已暂停' and b.running
    fresh.close()
