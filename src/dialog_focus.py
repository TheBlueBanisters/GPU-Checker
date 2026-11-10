"""App-owned dialog focus: one blurred body snapshot; title bar stays crisp."""
from contextlib import contextmanager
from PySide6.QtCore import QObject,QEvent,Qt,QRectF,QPointF,QVariantAnimation,QEasingCurve,QTimer
from PySide6.QtGui import QImage,QPainter,QColor
from PySide6.QtWidgets import QWidget,QDialog,QApplication,QGraphicsScene,QGraphicsBlurEffect
from shiboken6 import isValid
from themes import color as themed


def blurred_frame(content):
    source=content.grab();ratio=source.devicePixelRatio()
    scene=QGraphicsScene();item=scene.addPixmap(source)
    blur=QGraphicsBlurEffect();blur.setBlurRadius(13*ratio)
    blur.setBlurHints(QGraphicsBlurEffect.BlurHint.PerformanceHint);item.setGraphicsEffect(blur)
    target=QRectF(0,0,content.width(),content.height());scene.setSceneRect(target)
    result=QImage(source.size(),QImage.Format.Format_ARGB32_Premultiplied)
    result.setDevicePixelRatio(ratio);result.fill(themed('#080f1e'))
    painter=QPainter(result);scene.render(painter,target,target);painter.end();scene.clear()
    return result


class FocusShade(QWidget):
    def __init__(self,manager,frame):
        super().__init__(manager.content);self.manager=manager;self.frame=frame;self.amount=0.
        self.setGeometry(manager.content.rect());self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self.animation=QVariantAnimation(self);self.animation.setDuration(160)
        self.animation.setStartValue(0.);self.animation.setEndValue(1.)
        self.animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.animation.valueChanged.connect(self.advance)
    def advance(self,value):self.amount=float(value);self.update()
    def mousePressEvent(self,event):
        for dialog in reversed(list(self.manager.dialogs.values())):
            if dialog is not None and isValid(dialog) and dialog.isVisible():dialog.raise_();dialog.activateWindow();break
        event.accept()
    def paintEvent(self,event):
        p=QPainter(self);p.setOpacity(self.amount);p.drawImage(QPointF(),self.frame)
        ink=themed('#080f1e');ink.setAlpha(72);p.fillRect(self.rect(),ink)


class DialogFocus(QObject):
    def __init__(self,owner,content):
        super().__init__(owner);self.owner=owner;self.content=content;self.dialogs={};self.overlay=None
        content.installEventFilter(self)
    def ensure_overlay(self):
        if self.owner is not None and self.overlay is None and self.owner.isVisible():
            self.overlay=FocusShade(self,blurred_frame(self.content));self.overlay.show();self.overlay.raise_();self.overlay.animation.start()
    def add(self,dialog):
        key=id(dialog)
        if key not in self.dialogs:
            self.dialogs[key]=dialog;dialog.destroyed.connect(lambda *args,k=key:self.remove(k))
        self.ensure_overlay()
    @contextmanager
    def modal(self):
        token=object();key=id(token);self.dialogs[key]=None;self.ensure_overlay()
        try:yield
        finally:self.remove(key)
    def eventFilter(self,watched,event):
        content=getattr(self,'content',None)
        if content is None or not isValid(content):return False
        if watched is content and event.type() in (QEvent.Type.Resize,QEvent.Type.DevicePixelRatioChange):
            if getattr(self,'overlay',None):QTimer.singleShot(0,self,self.refresh)
        return False
    def remove(self,key):
        dialogs=getattr(self,'dialogs',None)
        if dialogs is None:return
        dialogs.pop(key,None)
        if not dialogs and getattr(self,'overlay',None):
            shade=self.overlay;self.overlay=None
            if isValid(shade):shade.animation.stop();shade.hide();shade.frame=QImage();shade.deleteLater()
    def dispose(self):
        content=getattr(self,'content',None)
        if content is not None and isValid(content):content.removeEventFilter(self)
        self.dialogs.clear()
        self.remove(None)
        self.content=None;self.owner=None

    def refresh(self):
        if not self.overlay or not isValid(self.overlay) or not isValid(self.content):return
        self.overlay.hide();frame=blurred_frame(self.content)
        if self.overlay:
            self.overlay.frame=frame;self.overlay.setGeometry(self.content.rect());self.overlay.show();self.overlay.raise_();self.overlay.update()
