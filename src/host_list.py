"""List-owned feedback keeps passive host tiles clickable as ordinary list items."""
from PySide6.QtCore import QTimer,QEvent,QPointF,QVariantAnimation,QEasingCurve,Qt
from PySide6.QtWidgets import QListWidget,QAbstractItemView,QApplication


class HostList(QListWidget):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.setViewportMargins(0,0,12,0)
        self.scroll_animation=QVariantAnimation(self)
        self.scroll_animation.setDuration(220)
        self.scroll_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.scroll_animation.valueChanged.connect(self._scroll_frame)
        self.scroll_target=0
        self._scroll_write=False
        bar=self.verticalScrollBar()
        bar.setSingleStep(24)
        bar.sliderPressed.connect(self.stop_scroll)
        bar.valueChanged.connect(self._scroll_changed)
        bar.rangeChanged.connect(self.stop_scroll)
        self.hovered_item=None
        self.hover_point=QPointF()
        self.wave_timer=QTimer(self)
        self.wave_timer.setSingleShot(True)
        self.wave_timer.timeout.connect(self._wave)
        self.setMouseTracking(True)
        self.viewport().setMouseTracking(True)

    def fit_tiles(self):
        width=max(1,self.viewport().width()-2)
        for index in range(self.count()):
            tile=self.itemWidget(self.item(index))
            if tile and tile.width()!=width:
                tile.setFixedWidth(width)

    def setItemWidget(self,item,widget):
        super().setItemWidget(item,widget)
        self.fit_tiles()

    def resizeEvent(self,event):
        super().resizeEvent(event)
        self.fit_tiles()

    def stop_scroll(self,*args):
        self.scroll_animation.stop()
        self.scroll_target=self.verticalScrollBar().value()

    def _scroll_changed(self,value):
        if not self._scroll_write:
            self.stop_scroll()

    def _scroll_frame(self,value):
        self._scroll_write=True
        try:
            self.verticalScrollBar().setValue(round(float(value)))
        finally:
            self._scroll_write=False

    def wheelEvent(self,event):
        bar=self.verticalScrollBar()
        self.reset_hover()
        if event.pixelDelta().y():
            # Touchpad input already contains pixel motion and OS momentum.
            self.stop_scroll()
            bar.setValue(bar.value()-event.pixelDelta().y())
            event.accept()
            return
        if not event.angleDelta().y():
            super().wheelEvent(event)
            return
        lines=QApplication.wheelScrollLines()
        distance=min(lines*24,max(24,self.viewport().height()*.9))
        start=bar.value()
        pending=self.scroll_target if self.scroll_animation.state()==QVariantAnimation.State.Running else start
        target=max(bar.minimum(),min(bar.maximum(),pending-event.angleDelta().y()/120*distance))
        self.scroll_animation.stop()
        self.scroll_target=target
        if target!=start:
            self.scroll_animation.setStartValue(float(start))
            self.scroll_animation.setEndValue(float(target))
            self.scroll_animation.start()
        event.accept()

    def mousePressEvent(self,event):
        item=self.itemAt(event.position().toPoint())
        tile=self.itemWidget(item) if item else None
        if tile and event.button()==Qt.MouseButton.LeftButton:
            point=tile.mapFrom(self.viewport(),event.position().toPoint())
            if tile.history_button.rect().contains(tile.history_button.mapFrom(tile,point)):
                self._history_press=True;tile.history_button.click();event.accept();return
        self._history_press=False;super().mousePressEvent(event)

    def mouseReleaseEvent(self,event):
        if getattr(self,'_history_press',False):self._history_press=False;event.accept();return
        super().mouseReleaseEvent(event)

    def reset_hover(self):
        self.wave_timer.stop()
        if self.hovered_item:
            tile=self.itemWidget(self.hovered_item)
            if tile:
                tile.history_button.setAttribute(Qt.WidgetAttribute.WA_UnderMouse,False);tile.history_button.update()
                tile._hover_to(0.)
                tile.clear_ripples()
        self.hovered_item=None

    def _wave(self):
        if self.hovered_item and self.isVisible():
            tile=self.itemWidget(self.hovered_item)
            if tile:
                tile.pulse_at(self.hover_point)
                self.wave_timer.start(4200)

    def mouseMoveEvent(self,event):
        item=self.itemAt(event.position().toPoint())
        if item is not self.hovered_item:
            self.reset_hover()
            self.hovered_item=item
            if item:
                self.wave_timer.start(1400)
        if item:
            tile=self.itemWidget(item)
            if tile:
                self.hover_point=QPointF(tile.mapFrom(self.viewport(),event.position().toPoint()))
                tile.history_button.setAttribute(Qt.WidgetAttribute.WA_UnderMouse,tile.history_button.rect().contains(tile.history_button.mapFrom(tile,self.hover_point.toPoint())));tile.history_button.update()
                tile.feedback_point=self.hover_point
                tile._hover_to(1.)
                tile.update()
        super().mouseMoveEvent(event)

    def viewportEvent(self,event):
        if event.type()==QEvent.Type.Leave and hasattr(self,'wave_timer'):
            self.reset_hover()
        return super().viewportEvent(event)

    def scrollContentsBy(self,dx,dy):
        self.reset_hover()
        super().scrollContentsBy(dx,dy)

    def hideEvent(self,event):
        self.stop_scroll()
        self.reset_hover()
        super().hideEvent(event)

    def clear(self):
        if hasattr(self,'wave_timer'):
            self.stop_scroll()
            self.reset_hover()
        super().clear()
