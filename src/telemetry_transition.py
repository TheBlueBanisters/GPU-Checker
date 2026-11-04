"""Native-size region fades and staggered GPU power handoffs."""
from PySide6.QtCore import QObject,Signal,QEvent,QRect,QRectF,QPoint,QPointF,Qt,QTimer,QVariantAnimation,QEasingCurve
from PySide6.QtGui import QPainter,QPixmap,QRadialGradient,QColor
import math
import random
from themes import color as themed
from PySide6.QtWidgets import QWidget
from shiboken6 import isValid
from card_motion import paint_spark_burst,spark_origin


def electric_shock(progress,seed=0):
    pulse=max(math.exp(-((progress-centre)/.045)**2) for centre in (.14,.34,.62,.82))
    if pulse<.10 or not 0<progress<1:return QPointF()
    return QPointF(5*pulse*math.sin(progress*241+seed*.01),
                   2.6*pulse*math.sin(progress*317+.7+seed*.01))


class FrameFade(QWidget):
    finished=Signal(object)
    def __init__(self,region,pixmap,duration,mode,show_cue=False):
        super().__init__(region)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.frame=pixmap
        self.target_frame=QPixmap()
        self.shock_displacement=QPointF()
        self.card_sequence=region.objectName()=='card'
        self.done=False
        self.delay_ms=0
        self.mode=mode
        self.show_cue=show_cue
        self.progress=0.
        self.spark_seed=random.randrange(1,10000000)
        self.animation=QVariantAnimation(self)
        self.animation.setDuration(duration)
        self.animation.setStartValue(0.)
        self.animation.setEndValue(1.)
        self.animation.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self.animation.valueChanged.connect(self.advance)
        self.animation.finished.connect(self.finish)
        self.setGeometry(region.rect())

    def advance(self,value):
        self.progress=float(value)
        if self.card_sequence:
            self.shock_displacement=electric_shock(self.progress,self.parentWidget().motion.seed)
        self.update()

    def begin(self,delay=0):
        self.delay_ms=delay
        if delay:QTimer.singleShot(delay,self,self._start)
        else:self._start()

    def _start(self):
        if self.done:return
        if self.card_sequence:
            # Capture the target without yielding or moving any real widget.
            self.hide()
            region=self.parentWidget();window=region.window()
            canvas=window.grab();ratio=canvas.devicePixelRatio()
            point=region.mapTo(window,QPoint())
            self.target_frame=canvas.copy(QRect(round(point.x()*ratio),round(point.y()*ratio),
                                               round(region.width()*ratio),round(region.height()*ratio)))
            self.target_frame.setDevicePixelRatio(ratio)
            self.show();self.raise_()
        self.animation.start()

    def finish(self):
        if self.done: return
        self.done=True
        if self.card_sequence and self.progress>=.999:
            self.parentWidget().motion.continue_sparks(.99,self.spark_seed)
        self.hide()
        self.frame=QPixmap()
        self.target_frame=QPixmap()
        self.finished.emit(self)
        self.deleteLater()

    def paintEvent(self,event):
        painter=QPainter(self)
        if self.card_sequence:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if self.card_sequence and (self.frame is None or self.frame.isNull()):
            painter.setClipPath(self.parentWidget().panel_path(QRectF(self.rect())))
        painter.setOpacity(1-self.progress)
        if self.frame is not None and not self.frame.isNull():
            painter.drawPixmap(QPoint(0,0),self.frame)
        elif self.card_sequence:
            painter.fillRect(self.rect(),themed('#0b1424'))
        if self.card_sequence and not self.shock_displacement.isNull() and not self.target_frame.isNull():
            # Raster-only tremor: chassis bounds, children and neighbors stay put.
            painter.save()
            painter.setClipRect(QRectF(self.rect()).adjusted(8,8,-8,-8),Qt.ClipOperation.IntersectClip)
            painter.setOpacity(1.)
            if self.frame is not None and not self.frame.isNull():
                painter.drawPixmap(self.shock_displacement,self.frame)
            else:painter.fillRect(self.rect(),themed('#0b1424'))
            painter.setOpacity(self.progress)
            painter.drawPixmap(self.shock_displacement,self.target_frame)
            painter.restore()
        if self.card_sequence and 0<self.progress<1:
            painter.setOpacity(1.)
            painter.setClipPath(self.parentWidget().panel_path(QRectF(self.rect())))
            strength=math.sin(math.pi*self.progress)
            tint=themed(self.parentWidget().property('availabilityColor') or '#859faf')
            centre=spark_origin(QRectF(self.rect()),self.spark_seed)
            glow=QRadialGradient(centre,self.width()*.48)
            for stop,alpha in ((0,25),(.25,12),(.65,4),(1,0)):
                ink=QColor(tint);ink.setAlpha(round(alpha*strength));glow.setColorAt(stop,ink)
            painter.fillRect(self.rect(),glow)
            paint_spark_burst(painter,centre,(self.progress-.10)*1.1,self.spark_seed)


class TelemetryTransition(QObject):
    def __init__(self,owner,regions):
        super().__init__(owner)
        self.owner=owner
        self.regions=regions  # (widget, duration_ms); status labels remain immediate.
        self.host_id=None
        self.mode=None
        self.overlays=[]
        self.pending=None
        self.pending_from=None
        self.ticket=0
        self.started_count=0
        self.last_transition=None
        self.resource_states={}
        self.status_started_count=0
        for region,_ in regions: region.installEventFilter(self)

    def cancel(self):
        self.ticket+=1
        self.pending=None
        self.pending_from=None
        for overlay in list(self.overlays):
            if isValid(overlay):
                overlay.animation.stop()
                overlay.finish()
        self.overlays=[]

    def observe(self,session):
        host_id=session.id if session else None
        mode='empty' if not session or session.snapshot is None else 'frozen' if session.historical else 'live'
        resources={g['uuid']:session.gpu_availability(g['uuid'])['status'] for g in session.snapshot['gpus']} if session and session.snapshot else {}
        old_resources=self.resource_states
        self.resource_states=resources
        if host_id!=self.host_id:
            self.cancel()
            self.host_id,self.mode=host_id,mode
            return mode
        if mode==self.mode:
            if mode=='live':
                powered={'idle','available','light','busy'}
                cards=[self.owner.cards[uuid] for uuid,status in resources.items()
                       if uuid in self.owner.cards and old_resources.get(uuid) not in powered and status in powered]
                self.animate_status(cards)
            return mode
        previous=self.mode
        self.mode=mode
        if self.owner.closing or not self.owner.isVisible() or self.owner.isMinimized():
            self.cancel()
            return mode
        if self.pending is not None:
            # Collapse changes that happen within one event-loop turn; never flash
            # an intermediate state which the user did not see.
            if mode==self.pending_from: self.cancel()
            else: self.last_transition=(self.pending_from,mode)
            return mode
        # Capture each region at its native size, including unfinished fades.
        # All pixels come from this app's own Qt rendering, never other windows.
        canvas=self.owner.grab()
        ratio=canvas.devicePixelRatio()
        pictures=[]
        regions=[(region,duration) for region,duration in self.regions
                 if region is not self.owner.card_scroll.viewport() or not self.owner.cards]
        regions.extend((card,650) for card in self.owner.cards.values())
        for region,duration in regions:
            if not isValid(region) or not region.isVisible() or region.size().isEmpty(): continue
            point=region.mapTo(self.owner,QPoint(0,0))
            crop=QRect(round(point.x()*ratio),round(point.y()*ratio),round(region.width()*ratio),round(region.height()*ratio))
            picture=canvas.copy(crop)
            picture.setDevicePixelRatio(ratio)
            pictures.append((region,picture,duration))
        self.cancel()
        self.pending=pictures
        self.pending_from=previous
        self.last_transition=(previous,mode)
        # Install the identical old image before changing child widgets, so the
        # new frame cannot briefly flash before the queued animation starts.
        for region,picture,duration in pictures:
            region.installEventFilter(self)
            overlay=FrameFade(region,picture,duration,self.mode,region is self.owner.card_scroll.viewport() or region.objectName()=='card')
            self.overlays.append(overlay)
            overlay.finished.connect(self.release)
            overlay.show();overlay.raise_()
        ticket=self.ticket
        QTimer.singleShot(0,self,lambda:self.present(ticket))
        return mode

    def animate_status(self,cards):
        if not cards or self.pending is not None or self.owner.closing or not self.owner.isVisible() or self.owner.isMinimized():return
        covered={overlay.parentWidget() for overlay in self.overlays if isValid(overlay)}
        cards=[card for card in cards if card not in covered and card.isVisible()]
        if not cards:return
        canvas=self.owner.grab();ratio=canvas.devicePixelRatio();batch=[]
        for card in cards:
            point=card.mapTo(self.owner,QPoint())
            picture=canvas.copy(QRect(round(point.x()*ratio),round(point.y()*ratio),round(card.width()*ratio),round(card.height()*ratio)))
            picture.setDevicePixelRatio(ratio)
            overlay=FrameFade(card,picture,900,'live',True)
            card.installEventFilter(self);overlay.finished.connect(self.release)
            self.overlays.append(overlay);batch.append(overlay)
            overlay.show();overlay.raise_()
        ticket=self.ticket
        QTimer.singleShot(0,self,lambda:self.present_status(ticket,batch))

    def present_status(self,ticket,batch):
        if ticket!=self.ticket or self.owner.closing or not self.owner.isVisible() or self.owner.isMinimized():return
        batch=sorted([overlay for overlay in batch if isValid(overlay) and not overlay.done],
                     key=lambda overlay:(overlay.parentWidget().y(),overlay.parentWidget().x()))
        step=min(130,800/max(1,len(batch)-1))
        for index,overlay in enumerate(batch):overlay.begin(round(index*step))
        if batch:
            self.started_count+=1;self.status_started_count+=1

    def release(self,overlay):
        if overlay in self.overlays: self.overlays.remove(overlay)

    def present(self,ticket):
        if ticket!=self.ticket or self.pending is None: return
        if self.owner.closing or not self.owner.isVisible() or self.owner.isMinimized():
            self.cancel();return
        self.pending=None
        self.pending_from=None
        # On the very first sample the old empty viewport masks construction.
        # Replace it atomically with per-card unpowered frames before painting.
        if self.owner.cards:
            self.owner.card_layout.activate()
            covered={overlay.parentWidget() for overlay in self.overlays if overlay.card_sequence}
            for card in self.owner.cards.values():
                if card in covered or self.mode!='live':continue
                card.installEventFilter(self)
                boot=FrameFade(card,None,650,self.mode,True)
                boot.finished.connect(self.release)
                self.overlays.append(boot);boot.show();boot.raise_()
            for overlay in list(self.overlays):
                if overlay.parentWidget() is self.owner.card_scroll.viewport(): overlay.finish()
        cards=sorted([overlay for overlay in self.overlays if overlay.card_sequence],
                     key=lambda overlay:(overlay.parentWidget().y(),overlay.parentWidget().x()))
        step=min(130,800/max(1,len(cards)-1))
        for overlay in list(self.overlays):
            if not isValid(overlay): continue
            if overlay.parentWidget().isVisible():
                overlay.begin(round(cards.index(overlay)*step) if overlay in cards else 0)
            else: overlay.finish()
        if self.overlays: self.started_count+=1

    def eventFilter(self,watched,event):
        if event.type() in (QEvent.Type.Wheel,QEvent.Type.MouseButtonPress,QEvent.Type.MouseButtonDblClick,QEvent.Type.KeyPress):
            self.cancel()
        elif event.type()==QEvent.Type.Resize:
            for overlay in list(self.overlays):
                if isValid(overlay) and overlay.parentWidget() is watched:
                    if overlay.card_sequence:
                        overlay.animation.stop();overlay.finish()
                    else:overlay.setGeometry(watched.rect())
        elif event.type()==QEvent.Type.Hide:
            for overlay in list(self.overlays):
                if isValid(overlay) and overlay.parentWidget() is watched:
                    overlay.animation.stop();overlay.finish()
        return False
