import math
from PySide6.QtCore import QPoint,Qt
from PySide6.QtGui import QHelpEvent
from PySide6.QtWidgets import QApplication,QToolTip,QWidget
from PySide6.QtTest import QTest
from test_multihost import window,snapshot
from card_motion import cylinder_state


def test_hover_information_popups_suppressed_globally(window):
    w=window;w.show();w.connect_all()
    w.selected.worker.data.emit(snapshot(1));QApplication.processEvents()
    card=next(iter(w.cards.values()))
    from dialogs import HostDialog
    dialog=HostDialog(w,w.selected.profile)
    try:
        for target in (card,card.state_label,card.name,w.title_bar.theme_button,w.table.viewport(),dialog.host):
            target.setToolTip('This must never become a popup')
            point=QPoint(5,5)
            event=QHelpEvent(QHelpEvent.Type.ToolTip,point,target.mapToGlobal(point))
            QApplication.sendEvent(target,event)
            QApplication.processEvents()
            assert not QToolTip.isVisible()
        QTest.mouseMove(card.metric_label,QPoint(10,10));QTest.qWait(280)
        assert card.hover_amount>.9
    finally:
        dialog.close()


def test_combustion_near_compression_tdc_and_once_per_two_revolutions():
    for i in range(4):
        samples=[cylinder_state(n/1440,i) for n in range(1440)]
        hottest=max(samples,key=lambda s:s[3])
        top=min(s[2] for s in samples)
        bottom=max(s[2] for s in samples)
        assert hottest[2]<top+(bottom-top)*.02
        assert all(s[3]==0 for s in samples if s[2]>top+(bottom-top)*.8)
        # Both TDC positions have identical geometry; only compression TDC fires.
        compression=(-((0,math.pi,3*math.pi,2*math.pi)[i]))/(4*math.pi)%1
        firing=cylinder_state(compression,i)
        exhaust=cylinder_state((compression+.5)%1,i)
        assert abs(firing[2]-exhaust[2])<1e-8
        assert firing[3]>.7 and exhaust[3]==0


def test_four_cylinder_firing_order():
    order=[]
    for phase in (0,.25,.5,.75):
        order.append(max(range(4),key=lambda i:cylinder_state(phase,i)[3])+1)
    assert order==[1,3,4,2]


def test_repeated_gpu_clicks_overlap_then_expire_independently(window):
    w=window;w.show();w.connect_all()
    s=w.selected;s.worker.data.emit(snapshot(1));QApplication.processEvents()
    worker=s.worker
    card=next(iter(w.cards.values()))
    QTest.mouseClick(card.metric_label,Qt.MouseButton.LeftButton,pos=QPoint(10,10))
    original=card.ripples[0]
    QTest.qWait(400)
    QTest.mouseClick(card.memory,Qt.MouseButton.LeftButton,pos=QPoint(40,5))
    assert len(card.ripples)==2 and card.ripples[0]==original
    assert card.ripples[1][0]!=original[0] and card.ripples[1][1]>original[1]
    QTest.qWait(2070)
    assert len(card.ripples)==1 and card.ripples[0][1]>original[1]
    assert s.worker is worker and worker.stops==0
    QTest.qWait(450)
    assert not card.ripples and card.click_progress==1
    QTest.mouseClick(card.metric_label,Qt.MouseButton.LeftButton,pos=QPoint(10,10))
    QTest.mouseDClick(card.metric_label,Qt.MouseButton.LeftButton,pos=QPoint(10,10))
    assert len(card.ripples)==2
    card.hide()
    assert not card.ripples
