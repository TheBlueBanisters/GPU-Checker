from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from shiboken6 import isValid
from test_multihost import window,snapshot


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
        assert not fresh.selected.desired and not t.overlays
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
