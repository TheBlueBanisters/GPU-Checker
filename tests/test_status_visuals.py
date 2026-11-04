from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from test_multihost import window,snapshot
from visuals import GPUCard
from availability import result
from themes import color
from PySide6.QtCore import QRectF,QPointF
import time


def test_workload_border_keeps_its_own_color_during_hover(window):
    for status in ('idle','available','light','busy'):
        state=result(status,'test')
        card=GPUCard(snapshot(1)['gpus'][0],availability=state)
        try:
            card.setFixedSize(270,270);card.show();QApplication.processEvents()
            expected=color(state['color'])
            for hover in (0.,1.):
                card._hover_to(hover);QTest.qWait(260)
                actual=card.grab().toImage().pixelColor(1,130)
                assert sum(abs(a-b) for a,b in zip(actual.getRgb()[:3],expected.getRgb()[:3]))<40
        finally:
            card.close();card.deleteLater()


def test_paused_chassis_is_cut_open_without_changing_card_geometry(window):
    card=GPUCard(snapshot(1)['gpus'][0],availability=result('busy','test'))
    try:
        card.setFixedSize(270,270)
        before=card.geometry()
        rect=QRectF(1.4,1.4,267.2,267.2)
        probe=QPointF(rect.left()+rect.width()*.72,rect.top()+3)
        assert card.panel_path(rect).contains(probe)
        state=result('busy','last sample');state.update(visual='paused',historical=True)
        card.set_availability(state)
        assert not card.panel_path(rect).contains(probe)
        assert card.geometry()==before
    finally:
        card.close();card.deleteLater()


def test_paused_particle_burst_is_sparse_and_has_a_quiet_interval(window):
    state=result('busy','last');state.update(visual='paused',historical=True)
    card=GPUCard(snapshot(1)['gpus'][0],availability=state)
    try:
        card.setFixedSize(270,270);card.feedback_enabled=False;card.show();QApplication.processEvents()
        period=3.8+(card.motion.seed%5)*.31
        def frame(age):
            card.motion.transition=time.monotonic()-age-(card.motion.seed%19)*.11
            return card.grab().toImage()
        quiet=frame(3.1)
        assert frame(.2)!=quiet
        assert frame(1.5)!=quiet
        assert frame(1.9)!=quiet  # Molten trails survive beyond the initial firework.
        assert frame(3.3)==quiet
        assert card.size().toTuple()==(270,270)
    finally:
        card.close();card.deleteLater()

def test_unknown_uses_single_unavailable_legend_and_upgrades_frozen_label(window):
    from PySide6.QtWidgets import QLabel
    from availability import result
    labels=[entry.text() for entry in window.availability_legend.findChildren(QLabel)]
    assert labels.count('◆ 不可用')==1
    assert len(labels)==5 and all('未知' not in text for text in labels)
    missing=result('unknown','进程查询缺失')
    assert missing['label']=='不可用' and not missing['available']
    window.connect_all();session=window.selected
    session.worker.data.emit(snapshot(1));session.pause()
    old=dict(missing,label='未知')
    session.last_gpu_states['GPU-1']=old
    frozen=session.gpu_availability('GPU-1')
    assert frozen['label']=='不可用' and frozen['historical'] and not frozen['available']
