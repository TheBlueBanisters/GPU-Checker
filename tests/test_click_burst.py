import time
from PySide6.QtCore import Qt,QPoint,QPointF,QRectF
from PySide6.QtGui import QImage,QPainter
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from test_multihost import window,snapshot
from visuals import GPUCard
from availability import result
from card_motion import spark_origin


def test_random_sparks_stay_inside_chassis(window):
    state=result('busy','last');state.update(visual='paused',historical=True)
    card=GPUCard(snapshot(1)['gpus'][0],availability=state)
    card.setFixedSize(270,300)
    try:
        rect=QRectF(1,1,268,298);path=card.panel_path(rect)
        origins={tuple(spark_origin(rect,seed).toTuple()) for seed in range(30)}
        assert len(origins)==30
        assert all(path.contains(QPointF(*point)) for point in origins)
        for age in (.15,1.5,2.4):
            image=QImage(270,300,QImage.Format.Format_ARGB32_Premultiplied);image.fill(Qt.GlobalColor.transparent)
            card.motion.transition=time.monotonic()-age-(card.motion.seed%19)*.11
            painter=QPainter(image);card.motion.electric_sparks(painter,rect);painter.end()
            for y in range(300):
                for x in range(270):
                    if not path.contains(QPointF(x+.5,y+.5)):
                        assert image.pixelColor(x,y).alpha()==0
    finally:card.close()


def test_click_overrev_burst_and_reform_keep_geometry_and_data(window):
    w=window;w.show();w.connect_all();session=w.selected
    session.worker.data.emit(snapshot(2));QApplication.processEvents();QTest.qWait(1000)
    card=next(iter(w.cards.values()));worker=session.worker
    geometry=(card.geometry(),w.table.geometry(),w.card_scroll.geometry())
    state=card.state_label.text();title=card.title.text()
    # Test actual child-label routing, not just a direct method call.
    for _ in range(5):QTest.mouseClick(card.name,Qt.MouseButton.LeftButton,pos=QPoint(8,8))
    assert card.motion.click_heat>4 and card.motion.burst is None
    phase=card.motion.phase;QTest.qWait(80)
    assert card.motion.phase!=phase
    for _ in range(2):QTest.mouseClick(card.name,Qt.MouseButton.LeftButton,pos=QPoint(8,8))
    burst=card.motion.burst;assert burst is not None
    for value in (.03,.24,.48,.7,.92):
        burst.animation.pause();burst.advance(value)
        assert not burst.grab().isNull()
        assert geometry==(card.geometry(),w.table.geometry(),w.card_scroll.geometry())
    # Between falling shards and reassembly, no old frame or solid tile remains.
    burst.advance(2.14/3.4)
    from themes import color
    image=burst.grab().toImage()
    assert image.pixelColor(0,0).alpha()==255
    expected=QImage(image.size(),QImage.Format.Format_ARGB32_Premultiplied)
    expected.setDevicePixelRatio(image.devicePixelRatio())
    expected.fill(color('#080f1e'))
    backdrop=card.parentWidget()
    while not hasattr(backdrop,'paint_backdrop'):backdrop=backdrop.parentWidget()
    origin=card.mapTo(backdrop,QPoint())
    painter=QPainter(expected);painter.translate(-origin.x(),-origin.y())
    backdrop.paint_backdrop(painter);painter.end()
    ratio=image.devicePixelRatio();probe=(round(ratio),round((card.height()-24)*ratio))
    assert image.pixelColor(*probe)==expected.pixelColor(*probe)
    assert session.worker is worker and worker.stops==0
    assert card.state_label.text()==state and card.title.text()==title
    burst.advance(1);burst.finish();QApplication.processEvents()
    assert card.motion.burst is None
    card.motion.click_heat=5;card.motion.heat_stamp=time.monotonic()-4;card.motion.frame()
    assert card.motion.click_heat==0
    for _ in range(12):card.pulse_at(QPointF(30,30))
    assert card.motion.burst is not None
    frozen=result('busy','last');frozen.update(visual='paused',historical=True)
    card.set_availability(frozen)
    assert card.motion.burst is None
    for _ in range(20):card.pulse_at(QPointF(30,30))
    assert card.motion.click_heat==0 and card.motion.burst is None

def test_gpu_ripples_follow_live_and_frozen_workload_colors(window):
    from themes import apply,color
    from visuals import STYLE
    card=GPUCard(snapshot(1)['gpus'][0],availability=result('busy','test'))
    card.setFixedSize(300,330);card.show();QApplication.processEvents()
    try:
        for mode in ('night','day'):
            apply(QApplication.instance(),mode,STYLE)
            for status in ('idle','available','light','busy','unknown'):
                for frozen in (False,True):
                    state=result(status,'test')
                    if frozen:state.update(visual='paused',historical=True)
                    card.set_availability(state)
                    card.motion.timer.stop();card.motion.afterglow=None
                    card.motion.transition=time.monotonic()-3.3-(card.motion.seed%19)*.11
                    assert card.ripple_color()==color(state['color'])
                    card.clear_ripples();quiet=card.grab().toImage()
                    card.ripples=[(QPointF(100,140),time.monotonic()-.95)]
                    wave=card.grab().toImage()
                    assert wave!=quiet
    finally:
        card.close();apply(QApplication.instance(),'night',STYLE)
