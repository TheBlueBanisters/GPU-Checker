"""Native-size theme cross-fade; it never animates layout or window geometry."""
from PySide6.QtCore import QObject,Signal,Qt,QPoint,QEvent,QVariantAnimation,QEasingCurve
from PySide6.QtGui import QPainter,QPixmap
from PySide6.QtWidgets import QWidget
from shiboken6 import isValid
import themes


class ThemeCurtain(QWidget):
    finished=Signal(object)
    def __init__(self,owner,frame):
        super().__init__(owner)
        self.frame=frame;self.progress=0.
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setGeometry(owner.rect())
        self.animation=QVariantAnimation(self)
        self.animation.setDuration(600)
        self.animation.setStartValue(0.);self.animation.setEndValue(1.)
        self.animation.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self.animation.valueChanged.connect(self.advance)
        self.animation.finished.connect(lambda:self.finished.emit(self))

    def advance(self,value):
        self.progress=float(value);self.update()

    def paintEvent(self,event):
        p=QPainter(self);p.setOpacity(1-self.progress)
        p.drawPixmap(QPoint(),self.frame)


class ThemeTransition(QObject):
    def __init__(self,owner):
        super().__init__(owner)
        self.owner=owner;self.overlay=None
        owner.installEventFilter(self)

    def switch(self,app,mode,style):
        frame=self.owner.grab() if self.owner.isVisible() and not self.owner.isMinimized() else None
        self.cancel()
        if frame is not None:
            self.overlay=ThemeCurtain(self.owner,frame)
            self.overlay.finished.connect(self.release)
            self.overlay.show();self.overlay.raise_()
        themes.apply(app,mode,style)
        if self.overlay:self.overlay.animation.start()

    def release(self,overlay):
        if self.overlay is overlay:self.overlay=None
        if isValid(overlay):
            overlay.animation.stop();overlay.hide();overlay.frame=QPixmap();overlay.deleteLater()

    def cancel(self):
        if self.overlay:self.release(self.overlay)

    def eventFilter(self,watched,event):
        kind=event.type()
        if kind in (QEvent.Type.Close,QEvent.Type.Hide,QEvent.Type.DevicePixelRatioChange):self.cancel()
        elif kind==QEvent.Type.Resize and self.overlay and self.overlay.size()!=self.owner.size():self.cancel()
        elif kind==QEvent.Type.WindowStateChange and self.owner.isMinimized():self.cancel()
        return False
