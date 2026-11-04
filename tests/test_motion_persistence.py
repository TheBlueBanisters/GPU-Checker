import time
from PySide6.QtCore import QRectF
from PySide6.QtWidgets import QApplication,QWidget
from PySide6.QtTest import QTest
from test_multihost import window,snapshot
from availability import result
from visuals import GPUCard
import profiles


def test_external_hosts_appear_and_paused_hosts_survive_stale_save(window):
    w=window
    before=list(w.items)
    extra=profiles.clean({'name':'additional-cpu','host':'cpu.test','autoconnect':False})
    profiles.save(before+[extra])
    assert w.save_items(before)
    assert extra['id'] in w.sessions
    w.rebuild_list()
    assert w.host_list.count()==3
    assert not w.sessions[extra['id']].running
    later=profiles.clean({'name':'additional-gpu','host':'gpu.test','autoconnect':False})
    profiles.save(w.items+[later])
    w.tick()
    assert w.host_list.count()==4 and later['id'] in w.sessions
    fresh=type(w)(autostart=False,session_factory=w.session_factory)
    try:
        assert fresh.host_list.count()==4
        assert not fresh.sessions[extra['id']].profile['autoconnect']
        assert not fresh.host_list.item(2).isHidden()
    finally:
        fresh.close()


def test_bad_external_write_keeps_existing_fleet(window):
    (profiles.DATA/'profiles.json').write_text('{broken',encoding='utf-8')
    window.tick()
    assert window.host_list.count()==2 and len(window.sessions)==2


def test_engine_motion_speeds_and_visibility(window):
    card=GPUCard(snapshot(1)['gpus'][0],availability=result('busy','test'))
    card.resize(240,240);card.show();QApplication.processEvents()
    try:
        assert card.motion.timer.isActive()
        first=card.grab().toImage()
        QTest.qWait(260)
        assert first!=card.grab().toImage()
        busy=card.motion.phase
        card.set_availability(result('idle','test'))
        QTest.qWait(260)
        idle=(card.motion.phase-busy)%1
        assert .12<busy<.4 and 0<idle<.05
        card.hide()
        assert not card.motion.timer.isActive()
        card.show();QApplication.processEvents()
        assert card.motion.timer.isActive()
        card.set_availability(result('blocked','test'))
        assert card.property('availabilityColor')=='#78909f'
        QTest.qWait(1700)
        assert not card.motion.timer.isActive()
        first=card.grab().toImage();QTest.qWait(100)
        assert first==card.grab().toImage()
        card.set_availability(result('busy','test'))
        assert card.motion.timer.isActive()
    finally:
        card.close()


def test_disconnect_fractures_and_pause_only_animates_electrical_artwork(window):
    w=window;w.show();w.connect_all()
    s=w.selected;s.worker.data.emit(snapshot(1));QApplication.processEvents()
    card=next(iter(w.cards.values()))
    previous=card.state_label.text()
    s.state='连接异常';s.received=time.monotonic()-100
    s.changed.emit(s.id)
    assert card.motion.state=='disconnected'
    assert card.state_label.text()=='连接中断'
    s.pause()
    assert card.motion.state=='paused' and card.motion.timer.isActive()
    assert card.state_label.text()==previous
    assert s.availability_counts() is None
    phase=card.motion.phase
    period=3.8+(card.motion.seed%5)*.31
    card.motion.transition=time.monotonic()-.08-(card.motion.seed%19)*.11
    values=(card.metric_label.text(),card.memory.text(),card.thermal.text())
    frames=[]
    for _ in range(12):
        QTest.qWait(100)
        frames.append(card.grab().toImage())
    assert any(frame!=frames[0] for frame in frames[1:])
    assert card.motion.phase==phase
    assert values==(card.metric_label.text(),card.memory.text(),card.thermal.text())
    card.hide();assert not card.motion.timer.isActive()
