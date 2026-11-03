"""List-owned feedback keeps passive host tiles clickable as ordinary list items."""
from PySide6.QtCore import QTimer,QEvent,QPointF
from PySide6.QtWidgets import QListWidget


class HostList(QListWidget):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.hovered_item=None
        self.hover_point=QPointF()
        self.wave_timer=QTimer(self)
        self.wave_timer.setSingleShot(True)
        self.wave_timer.timeout.connect(self._wave)
        self.setMouseTracking(True)
        self.viewport().setMouseTracking(True)

    def reset_hover(self):
        self.wave_timer.stop()
        if self.hovered_item:
            tile=self.itemWidget(self.hovered_item)
            if tile:
                tile._hover_to(0.)
                tile.click_animation.stop()
                tile.click_progress=1.
                tile.update()
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
        self.reset_hover()
        super().hideEvent(event)

    def clear(self):
        if hasattr(self,'wave_timer'):
            self.reset_hover()
        super().clear()
