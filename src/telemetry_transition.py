"""Interruptible cross-fades between empty, cached and live telemetry views."""
from PySide6.QtCore import QObject,Signal,QEvent,QRect,QPoint,Qt,QTimer,QVariantAnimation,QEasingCurve
from PySide6.QtGui import QPainter,QPixmap,QLinearGradient,QColor
import math
from themes import color as themed
from PySide6.QtWidgets import QWidget
from shiboken6 import isValid


class FrameFade(QWidget):
    finished=Signal(object)
    def __init__(self,region,pixmap,duration,mode,show_cue=False):
        super().__init__(region)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.frame=pixmap
        self.mode=mode
        self.show_cue=show_cue
        self.progress=0.
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
        self.update()

    def finish(self):
        self.hide()
        self.frame=QPixmap()
        self.finished.emit(self)
        self.deleteLater()

    def paintEvent(self,event):
        painter=QPainter(self)
        painter.setOpacity(1-self.progress)
        painter.drawPixmap(self.rect(),self.frame)
        if self.show_cue and 0<self.progress<1:
            # A quiet link handoff cue remains perceptible even when all numbers
            # are identical before/after the transition (idle GPUs / CPU hosts).
            painter.setOpacity(1.)
            strength=math.sin(math.pi*self.progress)
            span=max(90,self.width()*.22)
            centre=-span+(self.width()+2*span)*self.progress
            gradient=QLinearGradient(centre-span,0,centre+span,0)
            tint=themed('#63dec1' if self.mode=='live' else '#859faf')
            for stop,alpha in ((0,0),(.4,35),(.65,155),(1,0)):
                ink=QColor(tint);ink.setAlpha(round(alpha*strength));gradient.setColorAt(stop,ink)
            painter.fillRect(QRect(0,1,self.width(),2),gradient)
            veil=QLinearGradient(centre-span,0,centre+span,0)
            for stop,alpha in ((0,0),(.55,10),(1,0)):
                ink=QColor(tint);ink.setAlpha(round(alpha*strength));veil.setColorAt(stop,ink)
            painter.fillRect(self.rect(),veil)


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
        if host_id!=self.host_id:
            self.cancel()
            self.host_id,self.mode=host_id,mode
            return mode
        if mode==self.mode: return mode
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
        # Capture the composited old view once, including any unfinished fade.
        # All pixels come from this app's own Qt rendering, never other windows.
        frame=self.owner.grab()
        ratio=frame.devicePixelRatio()
        pictures=[]
        for region,duration in self.regions:
            if not isValid(region) or not region.isVisible() or region.size().isEmpty(): continue
            point=region.mapTo(self.owner,QPoint(0,0))
            rect=QRect(round(point.x()*ratio),round(point.y()*ratio),round(region.width()*ratio),round(region.height()*ratio))
            picture=frame.copy(rect)
            picture.setDevicePixelRatio(ratio)
            pictures.append((region,picture,duration))
        self.cancel()
        self.pending=pictures
        self.pending_from=previous
        self.last_transition=(previous,mode)
        # Install the identical old image before changing child widgets, so the
        # new frame cannot briefly flash before the queued animation starts.
        for region,picture,duration in pictures:
            overlay=FrameFade(region,picture,duration,self.mode,region is self.owner.card_scroll.viewport())
            self.overlays.append(overlay)
            overlay.finished.connect(self.release)
            overlay.show();overlay.raise_()
        ticket=self.ticket
        QTimer.singleShot(0,self,lambda:self.present(ticket))
        return mode

    def release(self,overlay):
        if overlay in self.overlays: self.overlays.remove(overlay)

    def present(self,ticket):
        if ticket!=self.ticket or self.pending is None: return
        if self.owner.closing or not self.owner.isVisible() or self.owner.isMinimized():
            self.cancel();return
        self.pending=None
        self.pending_from=None
        for overlay in list(self.overlays):
            if not isValid(overlay): continue
            if overlay.parentWidget().isVisible(): overlay.animation.start()
            else: overlay.finish()
        if self.overlays: self.started_count+=1

    def eventFilter(self,watched,event):
        if event.type() in (QEvent.Type.Wheel,QEvent.Type.MouseButtonPress,QEvent.Type.MouseButtonDblClick,QEvent.Type.KeyPress):
            self.cancel()
        elif event.type()==QEvent.Type.Resize:
            for overlay in self.overlays:
                if isValid(overlay) and overlay.parentWidget() is watched:
                    overlay.setGeometry(watched.rect())
        elif event.type()==QEvent.Type.Hide:
            for overlay in list(self.overlays):
                if isValid(overlay) and overlay.parentWidget() is watched:
                    overlay.animation.stop();overlay.finish()
        return False
