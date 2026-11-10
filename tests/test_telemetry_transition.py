from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from shiboken6 import isValid
from test_multihost import window,snapshot
from PySide6.QtCore import QPoint
import pytest


def live(window):
    window.show();QApplication.processEvents();window.connect_all()
    session=window.selected
    session.worker.data.emit(snapshot(1))
    return session


def test_empty_live_fade_is_passive_and_normal_samples_do_not_restart(window):
    s=live(window);worker=s.worker;t=window.telemetry_transition
    assert t.last_transition==('empty','live') and t.pending is not None
    assert t.overlays and all(o.progress==0 for o in t.overlays)
    QApplication.processEvents();QTest.qWait(120)
    assert t.started_count==1 and any(0<o.progress<1 for o in t.overlays)
    assert all(o.testAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents) for o in t.overlays)
    assert s.worker is worker and worker.stops==0
    QTest.qWait(850)
    assert not t.overlays and t.pending is None
    for _ in range(3):worker.data.emit(snapshot(1))
    QApplication.processEvents()
    assert t.started_count==1 and not t.overlays


def test_live_frozen_live_animates_both_directions_without_changing_data(window):
    s=live(window);QApplication.processEvents();QTest.qWait(950)
    t=window.telemetry_transition
    data=s.snapshot;history=list(s.history['GPU-1'])
    s.pause();QApplication.processEvents()
    assert t.last_transition==('live','frozen') and t.overlays
    assert s.snapshot is data and list(s.history['GPU-1'])==history
    assert '历史快照' in window.badge.text() and s.availability_counts() is None
    QTest.qWait(950)
    s.start();worker=s.worker
    current=snapshot(1);current['gpus'][0]['util']=37
    worker.data.emit(current);QApplication.processEvents()
    assert t.last_transition==('frozen','live') and t.overlays
    assert next(iter(window.cards.values())).metric_label.text()=='37%'
    assert s.worker is worker and worker.stops==0
    QTest.qWait(950)
    assert not t.overlays and t.started_count==3


def test_same_tick_bounce_collapses_and_host_switch_clears_old_frames(window):
    s=live(window);QApplication.processEvents();QTest.qWait(950)
    t=window.telemetry_transition;count=t.started_count
    s.worker.failed.emit('network unavailable')
    s.worker.data.emit(snapshot(1))
    QApplication.processEvents()
    assert t.mode=='live' and t.started_count==count and not t.overlays
    s.worker.failed.emit('network unavailable');QApplication.processEvents();QTest.qWait(80)
    old=list(t.overlays)
    assert old
    window.host_list.setCurrentRow(1);QApplication.processEvents()
    assert not t.overlays and t.host_id==window.selected_id
    assert all(not isValid(o) or not o.isVisible() for o in old)


def test_interrupted_fade_and_close_release_frames(window):
    s=live(window);QApplication.processEvents();QTest.qWait(100)
    t=window.telemetry_transition;old=list(t.overlays)
    s.worker.failed.emit('network unavailable');QApplication.processEvents()
    assert t.mode=='frozen' and t.overlays
    assert all(not isValid(o) or not o.isVisible() for o in old)
    window.close();QApplication.processEvents()
    assert not t.overlays and t.pending is None


def test_disk_snapshot_to_live_starts_from_the_restored_frame(window):
    live(window)
    fresh=type(window)(autostart=False,session_factory=window.session_factory)
    try:
        fresh.show();QApplication.processEvents()
        t=fresh.telemetry_transition
        assert fresh.selected.historical and t.mode=='frozen' and not t.overlays
        fresh.selected.start()
        fresh.selected.worker.data.emit(snapshot(1))
        QApplication.processEvents()
        assert t.last_transition==('frozen','live') and t.overlays
        assert '历史快照' not in fresh.badge.text()
        QTest.qWait(950)
        assert not t.overlays and t.started_count==1
    finally:
        fresh.close()


def test_process_click_takes_priority_over_fade(window):
    s=live(window);QApplication.processEvents();QTest.qWait(80)
    assert window.telemetry_transition.overlays
    point=window.table.visualItemRect(window.table.item(0,1)).center()
    QTest.mouseClick(window.table.viewport(),Qt.MouseButton.LeftButton,pos=point)
    assert not window.telemetry_transition.overlays
    assert window.table.currentRow()==0 and 'PID 101' in window.details.toPlainText()
    assert s.worker.stops==0


def test_restart_autostart_hands_off_saved_snapshot_after_first_sample(window):
    live(window)
    factory=window.session_factory
    window.close()
    fresh=type(window)(autostart=True,session_factory=factory)
    try:
        fresh.show();QApplication.processEvents()
        t=fresh.telemetry_transition
        assert fresh.selected.historical and t.mode=='frozen'
        assert not t.overlays  # Startup may already have run during a slow first render.
        QTest.qWait(420)  # exercise the real startup timer, never an SSH worker
        assert fresh.selected.desired and fresh.selected.worker.isRunning()
        assert t.mode=='frozen' and not t.overlays  # connecting is not live data
        fresh.selected.worker.data.emit(snapshot(1))
        QApplication.processEvents();QTest.qWait(150)
        assert t.last_transition==('frozen','live') and t.started_count==1
        assert any(o.show_cue and 0<o.progress<1 for o in t.overlays)
        QTest.qWait(950)
        assert not t.overlays
    finally:
        fresh.close()


def test_actual_pause_resume_buttons_keep_animation_after_saving_preferences(window):
    s=live(window);QApplication.processEvents();QTest.qWait(950)
    t=window.telemetry_transition
    first=s.worker
    QTest.mouseClick(window.connect_button,Qt.MouseButton.LeftButton)
    QApplication.processEvents();QTest.qWait(120)
    assert not s.desired and first.stops==1
    assert t.last_transition==('live','frozen') and t.overlays
    assert any(o.show_cue and 0<o.progress<1 for o in t.overlays)
    QTest.qWait(950)
    QTest.mouseClick(window.connect_button,Qt.MouseButton.LeftButton)
    assert s.desired and s.worker is not first
    s.worker.data.emit(snapshot(1))  # identical values must still visibly hand off
    QApplication.processEvents();QTest.qWait(120)
    assert t.last_transition==('frozen','live')
    assert any(o.show_cue and o.mode=='live' for o in t.overlays)
    QTest.qWait(950)
    assert not t.overlays and window.selected is s


def test_cards_switch_in_sequence_without_resizing_or_moving_their_contents(window):
    window.show();window.resize(1600,1000);QApplication.processEvents();window.connect_all()
    s=window.selected;data=snapshot(1)
    data['gpus']=[dict(data['gpus'][0],uuid=f'GPU-{i}',index=i) for i in (0,2,7)]
    s.worker.data.emit(data);QApplication.processEvents();QTest.qWait(1200)
    t=window.telemetry_transition
    fields=('title','name','metric_label','spark','memory','bar','thermal')
    def geometry():
        return [(card.geometry().getRect(),[getattr(card,name).geometry().getRect() for name in fields])
                for card in window.cards.values()]
    baseline=geometry()
    for mode in ('frozen','live'):
        if mode=='frozen':s.pause()
        else:
            s.start();s.worker.data.emit(data)
        QApplication.processEvents();QTest.qWait(180)
        overlays=sorted([o for o in t.overlays if o.card_sequence],key=lambda o:o.delay_ms)
        assert [o.delay_ms for o in overlays]==[0,130,260]
        assert overlays[0].progress>overlays[-1].progress
        assert all(o.frame.size()/o.frame.devicePixelRatio()==o.parentWidget().size() for o in overlays)
        overlays[0].animation.setCurrentTime(420)
        shock=overlays[0].shock_displacement
        assert .02<abs(shock.x())+abs(shock.y())
        assert abs(shock.x())<=5 and abs(shock.y())<=2.6
        assert geometry()==baseline
        for _ in range(12):
            assert geometry()==baseline
            QTest.qWait(80)
        assert not t.overlays
    assert t.started_count==3


@pytest.mark.parametrize('size',[(800,650),(1280,900)])
def test_table_and_surrounding_layout_remain_pixel_still_during_gpu_shocks(window,size):
    window.show();window.resize(*size);QApplication.processEvents();window.connect_all()
    s=window.selected
    s.profile.update(host='research-compute-gpu-node.example.invalid',user='researcher')
    data=snapshot(1);data.update(driver='580.178.04',cuda='13.0')
    data['gpus']=[dict(data['gpus'][0],uuid=f'GPU-{i}',index=i) for i in range(5)]
    s.worker.data.emit(data);QTest.qWait(1400)
    bar=window.dashboard_scroll.verticalScrollBar();bar.setValue(bar.maximum())
    QApplication.processEvents()
    widgets=(window.table,window.table.horizontalHeader(),window.details,window.search,window.process_title,
             window.status_text,window.card_scroll,*[value.parentWidget() for value in window.stats])
    def geometry():
        return [(widget.mapTo(window,QPoint()).toTuple(),widget.size().toTuple()) for widget in widgets],bar.value(),bar.maximum()
    baseline=geometry();table_image=window.table.viewport().grab().toImage()
    for active in (False,True):
        if active:
            s.start();s.worker.data.emit(data)
        else:s.pause()
        QApplication.processEvents()
        assert all(overlay.card_sequence for overlay in window.telemetry_transition.overlays)
        for frame in range(16):
            QTest.qWait(80)
            assert geometry()==baseline
            if frame in (0,5,15):assert window.table.viewport().grab().toImage()==table_image


def test_resume_observing_to_confirmed_status_has_its_own_color_handoff(window,monkeypatch):
    import sessions
    from test_availability import gpu
    clock=[100.]
    monkeypatch.setattr(sessions.time,'monotonic',lambda:clock[0])
    window.show();window.resize(1600,1000);QApplication.processEvents();window.connect_all()
    s=window.selected;data=snapshot(1)
    data['gpus'][0].update(gpu(uuid='GPU-1',used=410.,free=24166.))
    data['processes'][0]['memory']=410.
    for now in (100.,105.,110.):
        clock[0]=now;s.worker.data.emit(data)
    QApplication.processEvents();QTest.qWait(1000)
    s.pause();QApplication.processEvents();QTest.qWait(1000)
    s.start();clock[0]=200.;s.worker.data.emit(data)
    QApplication.processEvents();QTest.qWait(1000)
    assert window.cards['GPU-1'].state_label.text()=='观察中'
    t=window.telemetry_transition;count=t.status_started_count
    clock[0]=205.;s.worker.data.emit(data)
    assert t.status_started_count==count
    table_pos=window.table.mapTo(window,QPoint())
    clock[0]=210.;s.worker.data.emit(data)
    assert s.gpu_availability('GPU-1')['status']=='light' and t.overlays
    QApplication.processEvents();QTest.qWait(200)
    assert t.status_started_count==count+1
    assert len(t.overlays)==1 and t.overlays[0].parentWidget() is window.cards['GPU-1']
    assert 0<t.overlays[0].progress<1 and t.overlays[0].animation.duration()==900
    assert window.table.mapTo(window,QPoint())==table_pos
    QTest.qWait(1000)
    assert not t.overlays and window.cards['GPU-1'].state_label.text()=='轻量占用'
    clock[0]=212.;s.worker.data.emit(data);QApplication.processEvents()
    assert t.status_started_count==count+1 and not t.overlays
