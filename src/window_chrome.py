"""App-drawn title bar; Qt delegates movement and resizing to the OS."""
from PySide6.QtCore import Qt,QRectF,QPointF,QSize
from PySide6.QtGui import QColor,QPainter,QPen
from PySide6.QtWidgets import QWidget,QFrame,QLabel,QHBoxLayout,QAbstractButton


class WindowControl(QAbstractButton):
    def __init__(self,kind,window):
        super().__init__()
        self.kind,self.owner=kind,window
        self.setFixedSize(46,38)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAccessibleName({'min':'最小化','max':'最大化或还原','close':'关闭窗口'}[kind])
        self.setToolTip(self.accessibleName())
        self.clicked.connect(self.activate)

    def activate(self):
        if self.kind=='min': self.owner.showMinimized()
        elif self.kind=='max': self.owner.showNormal() if self.owner.isMaximized() else self.owner.showMaximized()
        else: self.owner.close()

    def enterEvent(self,event): self.update()
    def leaveEvent(self,event): self.update()

    def paintEvent(self,event):
        p=QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        if self.underMouse() or self.isDown():
            p.setBrush(QColor('#aa3f53' if self.kind=='close' else '#22374d'))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawRoundedRect(QRectF(3,4,self.width()-6,self.height()-8),7,7)
        p.setPen(QPen(QColor('#e1edf7' if self.underMouse() else '#8fa5ba'),1.35))
        x,y=self.width()/2,self.height()/2
        if self.kind=='min': p.drawLine(QPointF(x-5,y+3),QPointF(x+5,y+3))
        elif self.kind=='close':
            p.drawLine(QPointF(x-4,y-4),QPointF(x+4,y+4));p.drawLine(QPointF(x-4,y+4),QPointF(x+4,y-4))
        elif self.owner.isMaximized():
            p.drawRect(QRectF(x-3,y-5,8,8));p.fillRect(QRectF(x-5,y-3,8,8),QColor('#101d30'));p.drawRect(QRectF(x-5,y-3,8,8))
        else: p.drawRoundedRect(QRectF(x-5,y-5,10,10),1,1)


class TitleBar(QFrame):
    def __init__(self,window):
        super().__init__()
        self.owner=window
        self.setObjectName('titleBar')
        self.setFixedHeight(48)
        self.setStyleSheet('QFrame#titleBar {background:#0c1728;border-bottom:1px solid #203249;}')
        row=QHBoxLayout(self)
        row.setContentsMargins(19,0,8,0)
        row.setSpacing(12)
        icon=QLabel()
        icon.setPixmap(window.windowIcon().pixmap(QSize(23,23)))
        title=QLabel('GPU Checker')
        title.setStyleSheet('font-size:13px;font-weight:600;color:#d3e8f5')
        subtitle=QLabel('多主机算力监控')
        subtitle.setStyleSheet('font-size:11px;color:#708ba3')
        for widget in (icon,title,subtitle):
            widget.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            row.addWidget(widget)
        row.addStretch()
        for kind in ('min','max','close'):
            row.addWidget(WindowControl(kind,window))

    def mousePressEvent(self,event):
        if event.button()==Qt.MouseButton.LeftButton and self.owner.windowHandle():
            self.owner.windowHandle().startSystemMove()

    def mouseDoubleClickEvent(self,event):
        if event.button()==Qt.MouseButton.LeftButton:
            self.owner.showNormal() if self.owner.isMaximized() else self.owner.showMaximized()


class ResizeHandle(QWidget):
    def __init__(self,window,edges,cursor):
        super().__init__(window)
        self.owner,self.edges=window,edges
        self.setCursor(cursor)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)

    def mousePressEvent(self,event):
        if event.button()==Qt.MouseButton.LeftButton and self.owner.windowHandle():
            self.owner.windowHandle().startSystemResize(self.edges)


def install_handles(window):
    E=Qt.Edge
    C=Qt.CursorShape
    return [ResizeHandle(window,edge,cursor) for edge,cursor in (
        (E.LeftEdge,C.SizeHorCursor),(E.RightEdge,C.SizeHorCursor),(E.TopEdge,C.SizeVerCursor),(E.BottomEdge,C.SizeVerCursor),
        (E.TopEdge|E.LeftEdge,C.SizeFDiagCursor),(E.TopEdge|E.RightEdge,C.SizeBDiagCursor),
        (E.BottomEdge|E.LeftEdge,C.SizeBDiagCursor),(E.BottomEdge|E.RightEdge,C.SizeFDiagCursor))]


def layout_handles(window):
    w,h=window.width(),window.height()
    d,c=5,11
    rects=[(0,c,d,h-2*c),(w-d,c,d,h-2*c),(c,0,w-2*c,d),(c,h-d,w-2*c,d),
           (0,0,c,c),(w-c,0,c,c),(0,h-c,c,c),(w-c,h-c,c,c)]
    for handle,rect in zip(window.resize_handles,rects):
        handle.setGeometry(*rect)
        handle.setVisible(not window.isMaximized())
        handle.raise_()
