from card_halo import ZeroGpuTracker,REQUIRED_SECONDS,active
from PySide6.QtCore import QRectF
from PySide6.QtGui import QImage,QPainter
from PySide6.QtWidgets import QApplication
from test_multihost import window,snapshot
from visuals import GPUCard
from availability import result
import card_halo


def test_zero_gpu_needs_two_hours_and_accepts_short_gaps_and_restart():
    tracker=ZeroGpuTracker();gpu={'uuid':'a','util':0.}
    for now in range(0,REQUIRED_SECONDS,30):tracker.observe([gpu],now)
    assert not tracker.eligible('a',REQUIRED_SECONDS-1)
    tracker.observe([gpu],REQUIRED_SECONDS);assert tracker.eligible('a',REQUIRED_SECONDS)
    # Restart after 59 seconds uses the checkpoint from the final successful sample.
    fresh=ZeroGpuTracker();fresh.restore([dict(gpu)],REQUIRED_SECONDS+59)
    fresh.observe([gpu],REQUIRED_SECONDS+59);assert fresh.eligible('a',REQUIRED_SECONDS+59)
    gpu['util']=None;fresh.observe([gpu],REQUIRED_SECONDS+90)
    assert fresh.eligible('a',REQUIRED_SECONDS+90)
    gpu['util']=0.;fresh.observe([gpu],REQUIRED_SECONDS+119)
    assert fresh.eligible('a',REQUIRED_SECONDS+119)
    fresh.observe([gpu],REQUIRED_SECONDS+180);assert not fresh.eligible('a',REQUIRED_SECONDS+180)


def test_any_positive_value_resets_and_missing_is_never_zero():
    tracker=ZeroGpuTracker();gpu={'uuid':'a','util':None,'mem_util':0.}
    tracker.observe([gpu],100);assert not tracker.states
    gpu['util']=0.;tracker.observe([gpu],101)
    gpu['util']=.1;tracker.observe([gpu],102);assert not tracker.states
    gpu['util']=0.;tracker.observe([gpu],103)
    tracker.observe([gpu],90);assert tracker.states['a']==(90,90)  # Clock reversal restarts proof.
    restored=ZeroGpuTracker();restored.restore([dict(gpu)],200);assert not restored.states


def test_all_card_halo_preview_moves_without_changing_bounds(window,monkeypatch):
    monkeypatch.setattr(card_halo,'PREVIEW_ALL',True)
    card=GPUCard(snapshot(1)['gpus'][0],availability=result('busy','test'));card.setFixedSize(270,270)
    try:
        assert active(card)
        images=[]
        for now in (100.,101.):
            image=QImage(290,290,QImage.Format.Format_ARGB32_Premultiplied);image.fill(0)
            painter=QPainter(image);painter.translate(10,10);card_halo.paint(painter,card,1,now);painter.end();images.append(image)
        assert images[0]!=images[1] and card.size().toTuple()==(270,270)
        for image in images:
            assert image.pixelColor(130,130).alpha()==0
        card.setProperty('_haloPreview',False);assert not active(card)
        card.setProperty('idleHaloEligible',True);assert active(card)
    finally:card.close()

def test_zero_timing_survives_host_session_snapshot_restart(window,monkeypatch):
    import sessions,history_cache
    from sessions import HostSession
    from test_multihost import FakeMonitor
    clock=[10900.];monkeypatch.setattr(sessions.time,'time',lambda:clock[0])
    window.connect_all();session=window.selected
    session.zero_gpu.states['GPU-1']=(100.,10870.)
    data=snapshot(1);data['gpus'][0]['util']=0.
    session.worker.data.emit(data);assert session.gpu_availability('GPU-1')['idle_glow']
    session.pause();clock[0]+=59
    fresh=HostSession(session.profile,factory=FakeMonitor)
    try:
        fresh.start();fresh.worker.data.emit(data)
        assert fresh.gpu_availability('GPU-1')['idle_glow']
        data['gpus'][0]['util']=1.;clock[0]+=2;fresh.worker.data.emit(data)
        assert not fresh.gpu_availability('GPU-1')['idle_glow']
    finally:fresh.stop();history_cache.flush()

def test_comet_uses_translucent_sky_blue_for_every_card_state(window,monkeypatch):
    from PySide6.QtGui import QColor
    monkeypatch.setattr(card_halo,'PREVIEW_ALL',True)
    card=GPUCard(snapshot(1)['gpus'][0]);card.setFixedSize(270,270)
    try:
        path,length=card_halo.orbit(270,270)
        head=path.pointAtPercent(path.percentAtLength(((100/8.5)+1/37)%1*length))
        for state in ('idle','available','light','busy','blocked'):
            data=result(state,'test');card.set_availability(data)
            image=QImage(290,290,QImage.Format.Format_ARGB32_Premultiplied);image.fill(0)
            painter=QPainter(image);painter.translate(10,10);card_halo.paint(painter,card,1,100.);painter.end()
            pixel=image.pixelColor(round(head.x())+10,round(head.y())+10);expected=QColor('#70cfff')
            difference=abs(pixel.hue()-expected.hue())
            assert min(difference,360-difference)<8
            assert 100<pixel.alpha()<210
            visible=sum(image.pixelColor(x,y).alpha()>25 for y in range(290) for x in range(290))
            assert visible>600
    finally:card.close()

def test_halo_is_a_transparent_sibling_outside_card_and_hides_during_burst(window,monkeypatch):
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    monkeypatch.setattr(card_halo,'PREVIEW_ALL',True)
    window.show();window.connect_all();window.selected.worker.data.emit(snapshot(1))
    QApplication.processEvents();QTest.qWait(40)
    card=next(iter(window.cards.values()));overlay=card.halo_overlay
    before=(card.geometry(),window.table.geometry())
    assert overlay.parentWidget() is card.parentWidget()
    assert overlay.geometry().contains(card.geometry()) and overlay.geometry()!=card.geometry()
    assert overlay.testAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
    assert card.motion.timer.interval()==16
    image=overlay.grab().toImage();pad=round(card_halo.PAD*image.devicePixelRatio())
    # The bloom can escape the frame even though its trajectory matches the line.
    exterior=[]
    for region in ((0,0,image.width(),pad),(0,image.height()-pad,image.width(),image.height()),
                   (0,0,pad,image.height()),(image.width()-pad,0,image.width(),image.height())):
        x0,y0,x1,y1=region
        exterior.extend(image.pixelColor(x,y).alpha() for y in range(y0,y1) for x in range(x0,x1))
    assert sum(alpha>25 for alpha in exterior)>200
    previous=card.motion.burst
    try:
        card.motion.burst=object();card_halo.sync(card);assert not overlay.isVisible()
    finally:card.motion.burst=previous
    card_halo.sync(card);assert overlay.isVisible()
    QTest.qWait(80)
    assert (card.geometry(),window.table.geometry())==before
    card.hide();assert not overlay.isVisible()

def test_production_halo_requires_gpu_zero_not_memory_zero(window):
    assert REQUIRED_SECONDS==7200 and card_halo.PREVIEW_ALL is False
    tracker=ZeroGpuTracker();gpu={'uuid':'a','util':100.,'mem_util':0.}
    for now in range(0,7201,30):tracker.observe([gpu],now)
    assert not tracker.eligible('a',7200)
    gpu.update(util=0.,mem_util=50.)
    for now in range(7201,14402,30):tracker.observe([gpu],now)
    assert tracker.eligible('a',14401)
    card=GPUCard(snapshot(1)['gpus'][0]);assert not active(card)
    card.setProperty('idleHaloEligible',True);assert active(card);card.close()
    old={'uuid':'a','util':0.,'mem_zero_since':0.,'mem_zero_last':14401.}
    tracker.restore([old],14401);assert not tracker.states
