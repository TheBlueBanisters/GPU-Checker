from themes import set_style, color as themed, is_day
"""App-drawn title bar; Qt delegates movement and resizing to the OS."""
from PySide6.QtCore import Qt,QRectF,QPointF,QSize
from PySide6.QtGui import QColor,QPainter,QPen,QLinearGradient
from PySide6.QtWidgets import QWidget,QFrame,QLabel,QHBoxLayout,QAbstractButton
from visuals import notch_path


class WindowControl(QAbstractButton):
    def __init__(self,kind,window):
        super().__init__()
        self.kind,self.owner=kind,window
        self.setFixedSize(38,30)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAccessibleName({'min':'最小化','max':'最大化或还原','close':'关闭窗口','theme':'切换日间模式'}[kind])
        self.setToolTip(self.accessibleName())
        self.clicked.connect(self.activate)
        if kind=='theme': self.sync_theme_label()

    def sync_theme_label(self):
        self.setAccessibleName('切换夜间模式' if is_day() else '切换日间模式')
        self.setToolTip(self.accessibleName())

    def activate(self):
        if self.kind=='theme': self.owner.toggle_theme()
        elif self.kind=='min': self.owner.showMinimized()
        elif self.kind=='max': self.owner.showNormal() if self.owner.isMaximized() else self.owner.showMaximized()
        else: self.owner.close()

    def enterEvent(self,event): self.update()
    def leaveEvent(self,event): self.update()

    def paintEvent(self,event):
        p=QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        if self.underMouse() or self.isDown():
            p.setBrush(themed('#aa3f53' if self.kind=='close' else '#22374d'))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawPath(notch_path(QRectF(1,1,self.width()-2,self.height()-2),4))
        p.setPen(QPen(themed('#b7e1eb' if self.underMouse() else '#83a5bb'),1.6))
        x,y=self.width()/2,self.height()/2
        if self.kind=='theme':
            if is_day():
                from PySide6.QtGui import QPainterPath
                moon=QPainterPath();moon.addEllipse(QRectF(x-6,y-6,12,12))
                cut=QPainterPath();cut.addEllipse(QRectF(x-1,y-8,11,11))
                p.fillPath(moon.subtracted(cut),p.pen().color())
            else:
                import math
                p.drawEllipse(QRectF(x-3,y-3,6,6))
                for i in range(8):
                    a=i*math.pi/4
                    p.drawLine(QPointF(x+5*math.cos(a),y+5*math.sin(a)),QPointF(x+7*math.cos(a),y+7*math.sin(a)))
        elif self.kind=='min': p.drawLine(QPointF(x-5,y+3),QPointF(x+5,y+3))
        elif self.kind=='close':
            p.drawLine(QPointF(x-4,y-4),QPointF(x+4,y+4));p.drawLine(QPointF(x-4,y+4),QPointF(x+4,y-4))
        elif self.owner.isMaximized():
            p.drawRect(QRectF(x-3,y-5,8,8));p.fillRect(QRectF(x-5,y-3,8,8),themed('#101d30'));p.drawRect(QRectF(x-5,y-3,8,8))
        else: p.drawRoundedRect(QRectF(x-5,y-5,10,10),1,1)


class TitleBar(QFrame):
    def __init__(self,window,caption=None,compact=False):
        super().__init__()
        self.owner=window
        self.compact=compact
        self.setObjectName('titleBar')
        self.setFixedHeight(42 if compact else 48)
        set_style(self,'QFrame#titleBar {background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #0d1d30,stop:0.5 #0b1727,stop:1 #101d30);border-bottom:1px solid #243b50;}')
        row=QHBoxLayout(self)
        row.setContentsMargins(20,0,12,0)
        row.setSpacing(14)
        icon=QLabel()
        icon.setPixmap(window.windowIcon().pixmap(QSize(22,22)))
        title=QLabel(caption or 'GPU CHECKER')
        set_style(title,"font-family:'Orbitron','ZCOOL QingKe HuangYou';font-size:14px;font-weight:500;letter-spacing:1px;color:#88d5e2")
        subtitle=QLabel('REMOTE MONITOR')
        set_style(subtitle,"font-family:'Orbitron';font-size:9px;letter-spacing:1px;color:#557b96")
        for widget in (icon,title,subtitle):
            widget.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            row.addWidget(widget)
        subtitle.setVisible(not compact)
        row.addStretch()
        self.fleet_label=QLabel('')
        set_style(self.fleet_label,'font-size:11px;color:#79a6ba')
        self.clock_label=QLabel('')
        set_style(self.clock_label,"font-family:'Orbitron';font-size:10px;color:#527d94")
        for label in (self.fleet_label,self.clock_label):
            label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            row.addWidget(label)
            label.setVisible(not compact)
        if not compact:
            self.theme_button=WindowControl('theme',window)
            row.addWidget(self.theme_button)
        row.addSpacing(8)
        controls=QFrame()
        controls.setObjectName('windowControls')
        controls.setFixedHeight(34)
        set_style(controls,'QFrame#windowControls {background:#122638;border:1px solid #31576b;border-radius:1px;}')
        group=QHBoxLayout(controls)
        group.setContentsMargins(2,1,2,1)
        group.setSpacing(2)
        for kind in (('close',) if compact else ('min','max','close')):
            group.addWidget(WindowControl(kind,window))
        row.addWidget(controls)

    def resizeEvent(self,event):
        super().resizeEvent(event)
        self.clock_label.setVisible(not self.compact and event.size().width()>=1200)

    def paintEvent(self,event):
        super().paintEvent(event)
        p=QPainter(self)
        gradient=QLinearGradient(0,0,400,0)
        gradient.setColorAt(0,themed(89,221,217,150))
        gradient.setColorAt(1,themed(89,221,217,0))
        p.fillRect(0,0,400,1,gradient)

    def mousePressEvent(self,event):
        if event.button()==Qt.MouseButton.LeftButton and self.owner.windowHandle():
            self.owner.windowHandle().startSystemMove()

    def mouseDoubleClickEvent(self,event):
        if not self.compact and event.button()==Qt.MouseButton.LeftButton:
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
