import json
from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QApplication
from test_multihost import window,snapshot,FakeMonitor
from sessions import HostSession
import snapshots
import profiles


def sample(window):
    window.connect_all()
    session=window.selected
    for _ in range(65): session.worker.data.emit(snapshot(1))
    return session


def test_restart_restores_frozen_gpu_curve_and_process_directory(window):
    old=sample(window)
    fresh=type(window)(autostart=False,session_factory=window.session_factory)
    try:
        fresh.show();QApplication.processEvents()
        s=fresh.sessions[old.id]
        assert next(iter(fresh.cards.values())).width()==round(270*fresh.property('uiDensity'))
        assert s.snapshot['gpus'][0]['used']==old.snapshot['gpus'][0]['used']
        assert s.snapshot['processes'][0]['cwd']=='/host1/work'
        assert list(s.history['GPU-1'])==list(old.history['GPU-1']) and len(s.history['GPU-1'])==60
        assert s.sampled_at==old.sampled_at and s.received==0 and not s.fresh
        assert s.historical and s.availability_counts() is None
        assert not s.gpu_availability('GPU-1')['available']
        assert fresh.table.rowCount()==1 and len(fresh.cards)==1
        assert '历史快照' in fresh.badge.text() and s.snapshot_time in fresh.status_text.text()
        assert '历史快照' in fresh.tiles[s.id].summary.text()
        s.start();s.worker.failed.emit('network unavailable')
        assert s.snapshot['processes'][0]['cwd']=='/host1/work' and s.historical
        s.worker.data.emit(snapshot(2))
        assert s.fresh and not s.historical and '历史快照' not in fresh.badge.text()
        assert fresh.current[0]['cwd']=='/host2/work'
    finally:
        fresh.close()


def test_sampling_error_or_gpu_unavailable_keeps_last_good_cache(window):
    s=sample(window);path=snapshots.path_for(s.profile)
    good=path.read_bytes();when=s.sampled_at
    s.worker.data.emit({'error':'driver failure'})
    assert path.read_bytes()==good and s.historical
    s.worker.data.emit({'gpus':[],'processes':[],'driver':'N/A','cuda':'N/A','gpu_status':'unavailable','notice':'query failed'})
    assert path.read_bytes()==good and s.sampled_at==when
    assert s.snapshot['gpus'] and s.historical and s.availability_counts() is None


def test_endpoint_change_and_corrupt_cache_do_not_load_wrong_host(window):
    s=sample(window)
    changed=dict(s.profile,host='another.test')
    assert snapshots.load(changed) is None
    path=snapshots.path_for(s.profile);path.write_text('{invalid',encoding='utf-8')
    fresh=HostSession(s.profile,factory=FakeMonitor)
    assert fresh.snapshot is None
    fresh.start();assert fresh.running
    fresh.stop()


def test_pause_keeps_last_status_color_across_restart_without_advertising_capacity(window):
    s=sample(window)
    assert window.cards['GPU-1'].pause_note.text()==''
    before=dict(s.gpu_availability('GPU-1'))
    s.pause();window.persist_session_preferences()
    card=window.cards['GPU-1']
    assert card.state_label.text()==before['label']
    assert card.state_label.tone.name()==before['color']
    assert not card.pause_note.isHidden() and card.pause_note.text()=='（暂停监控）'
    assert card.state_label.diamond_size==12
    assert s.availability_counts() is None and not s.gpu_availability('GPU-1')['available']
    fresh=type(window)(autostart=False,session_factory=window.session_factory)
    try:
        restored=fresh.selected
        badge=fresh.cards['GPU-1'].state_label
        assert restored.state=='已暂停' and restored.historical
        assert badge.text()==before['label'] and badge.tone.name()==before['color']
        assert not fresh.cards['GPU-1'].pause_note.isHidden()
        assert restored.availability_counts() is None
        assert not restored.gpu_availability('GPU-1')['available']
    finally:
        fresh.close()


def test_light_status_is_counted_live_but_only_shown_as_history_after_pause(window,monkeypatch):
    import sessions
    from test_availability import gpu
    clock=[100.]
    monkeypatch.setattr(sessions.time,'monotonic',lambda:clock[0])
    window.connect_all();s=window.selected
    data=snapshot(1)
    data['gpus'][0].update(gpu(uuid='GPU-1',used=410.,free=24166.))
    data['processes'][0]['memory']=410.
    for now in (100.,105.,110.):
        clock[0]=now;s.worker.data.emit(data)
    assert s.gpu_availability('GPU-1')['status']=='light'
    assert s.availability_counts()['available']==s.availability_counts()['light']==1
    assert s.availability_counts()['idle']==0
    s.pause()
    restored=HostSession(s.profile,factory=FakeMonitor)
    state=restored.gpu_availability('GPU-1')
    assert state['label']=='轻量占用' and state['historical'] and not state['available']
    assert restored.availability_counts() is None


def test_cache_write_failure_does_not_stop_live_monitor(window,monkeypatch):
    s=sample(window);worker=s.worker
    good=snapshots.path_for(s.profile).read_bytes()
    monkeypatch.setattr(snapshots,'save',lambda *a: (_ for _ in ()).throw(OSError('read only')))
    worker.data.emit(snapshot(2))
    assert s.fresh and s.worker is worker and worker.stops==0
    assert s.cache_error and s.snapshot['processes'][0]['cwd']=='/host2/work'
    assert snapshots.path_for(s.profile).read_bytes()==good


def test_no_gpu_restores_as_history_and_credentials_are_not_cached(window):
    s=window.selected;window.connect_all()
    data={'gpus':[],'processes':[],'driver':'N/A','cuda':'N/A','gpu_status':'no_gpu','notice':'CPU only','password':'never-cache-this'}
    s.worker.data.emit(data)
    content=snapshots.path_for(s.profile).read_text(encoding='utf-8')
    assert 'never-cache-this' not in content
    fresh=HostSession(s.profile,factory=FakeMonitor)
    assert fresh.snapshot['gpus']==[] and fresh.historical and fresh.gpu_hint=='no_gpu'
    window.remove_host()
    assert not snapshots.path_for(s.profile).exists()


def test_host_card_right_edge_stays_inside_viewport(window):
    window.show();QApplication.processEvents()
    listing=window.host_list
    for width in (1080,1480):
        window.resize(width,900);QApplication.processEvents()
        tile=listing.itemWidget(listing.item(0))
        right=tile.mapTo(listing.viewport(),QPoint(tile.width(),0)).x()
        assert right<=listing.viewport().width()-2
        image=tile.grab().toImage()
        # Actual right-edge pixels differ from the adjacent panel interior.
        y=image.height()//2
        edge=image.pixelColor(image.width()-1,y)
        inside=image.pixelColor(image.width()-5,y)
        assert edge!=inside
