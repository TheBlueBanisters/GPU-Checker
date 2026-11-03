from pathlib import Path
from PySide6.QtCore import Qt,QRectF,QPointF,QVariantAnimation,QSize
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen, QLinearGradient, QRadialGradient,QFont
from PySide6.QtWidgets import QWidget, QFrame, QLabel, QVBoxLayout, QHBoxLayout, QProgressBar,QPushButton,QSizePolicy

STYLE = """
QWidget {font-family:'Inter','Noto Sans SC';font-size:13px;color:#d8e5f1;background:transparent;}
QDialog,QMessageBox {background:#101b2d;}
QLabel {border:0;background:transparent;}
QLabel#muted {color:#7f96b1;font-size:12px;}
QLabel#eyebrow {color:#7aa5b6;font-family:'Inter','Noto Sans SC';font-size:11px;letter-spacing:1px;}
QLabel#brand {color:#e7f8ff;font-size:20px;font-weight:700;}
QLabel#heading {color:#effbff;font-size:30px;font-weight:700;}
QLabel#badge {color:#68f6cf;background:rgba(29,201,158,22);border:1px solid #1b6b62;border-radius:9px;padding:7px 12px;}
QFrame#sidebar {background:rgba(9,17,32,235);border-right:1px solid #20334d;}
QFrame#glass {background:rgba(18,32,54,195);border:1px solid #263d59;border-radius:13px;}
QFrame#card {background:rgba(17,33,55,205);border:1px solid #29445e;border-top:2px solid #36ced9;border-radius:12px;}
QFrame#hostTile {background:rgba(17,30,50,160);border:1px solid #24364f;border-radius:10px;}
QFrame#hostTile[selected="true"] {background:rgba(26,68,82,165);border:1px solid #4be7df;border-left:3px solid #66ffe5;}
QLabel#metric {font-family:'JetBrains Mono';font-size:32px;font-weight:500;color:#6bf8e0;}
QLabel#stat {font-family:'Inter','Noto Sans SC';font-size:23px;font-weight:600;color:#e6f8ff;}
QLineEdit,QSpinBox,QComboBox {background:#0c1729;border:1px solid #2c435f;border-radius:7px;padding:8px;min-height:20px;selection-background-color:#15798a;}
QLineEdit:focus,QSpinBox:focus,QComboBox:focus {border:1px solid #54e6e1;}
QComboBox QAbstractItemView {background:#14233a;color:#d5edff;selection-background-color:#24566b;}
QPushButton {background:#1b2a3c;border:1px solid #304256;border-radius:9px;padding:9px 16px;font-weight:500;}
QPushButton:hover {background:#263c50;border-color:#52677d;color:#f0faff;}
QPushButton:pressed {background:#112137;}
QPushButton#primary {background:#64e5c7;border:1px solid #64e5c7;color:#072a29;}
QPushButton#primary:hover {background:#8df2d9;border-color:#8df2d9;}
QPushButton#danger {color:#ffb0b7;border-color:#694152;}
QPushButton:disabled {color:#50647c;border-color:#25354d;background:#132035;}
QListWidget {border:0;outline:0;background:transparent;}
QListWidget::item {border:0;background:transparent;padding:0;margin:0 0 9px 0;}
QListWidget::item:selected {background:transparent;}
QProgressBar {background:#1b3047;border:0;border-radius:3px;height:5px;max-height:5px;}
QProgressBar::chunk {background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #187f9c,stop:1 #65ffe0);border-radius:3px;}
QTableWidget {background:rgba(11,22,39,215);border:1px solid #263c56;border-radius:10px;gridline-color:#22344e;selection-background-color:#194f62;selection-color:#e6ffff;}
QHeaderView::section {background:#15263c;color:#8eacc6;padding:11px 8px;border:0;border-bottom:1px solid #30465f;font-weight:600;}
QTableWidget::item {padding:7px;border-bottom:1px solid #1c2d44;}
QTableWidget::item:selected {background:#17485b;}
QTextEdit {background:rgba(13,26,45,215);border:1px solid #263f58;border-radius:10px;padding:10px;font-family:'JetBrains Mono','Noto Sans SC';font-size:12px;color:#b4cbdc;}
QScrollArea {border:0;background:transparent;}
QScrollBar:horizontal {height:7px;background:#102139;border:0;}
QScrollBar:vertical {width:7px;background:#102139;border:0;}
QScrollBar::handle {background:#35576c;border-radius:3px;min-width:25px;min-height:25px;}
QScrollBar::add-line,QScrollBar::sub-line {width:0;height:0;}
QCheckBox {spacing:8px;}
QCheckBox::indicator {width:16px;height:16px;border:1px solid #52738d;border-radius:4px;background:#0c1729;}
QCheckBox::indicator:checked {background:#29b8b0;border:1px solid #8cf9e1;}
QSplitter::handle {background:transparent;height:7px;}
QToolTip {background:#182b43;color:#e0f5ff;border:1px solid #3f718c;padding:7px;}
"""


class ModernButton(QPushButton):
    """Quiet Fluent-inspired controls, drawn consistently on every Windows theme."""
    def __init__(self,text,primary=False,ghost=False):
        super().__init__(text)
        self.primary,self.ghost=primary,ghost
        self.phase=0.
        self.keyboard_focus=False
        self.animation=QVariantAnimation(self)
        self.animation.setDuration(140)
        self.animation.valueChanged.connect(self.animate)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(42)
        self.setMinimumWidth(self.sizeHint().width())
        self.setSizePolicy(QSizePolicy.Policy.Minimum,QSizePolicy.Policy.Fixed)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def sizeHint(self):
        font=self.font()
        font.setWeight(QFont.Weight.Medium)
        from PySide6.QtGui import QFontMetrics
        return QSize(QFontMetrics(font).horizontalAdvance(self.text().lstrip('+ '))+16+10+44,42)

    def minimumSizeHint(self):
        return self.sizeHint()

    def setText(self,text):
        super().setText(text)
        self.setMinimumWidth(self.sizeHint().width())
        self.updateGeometry()

    def focusInEvent(self,event):
        self.keyboard_focus=event.reason() in (Qt.FocusReason.TabFocusReason,Qt.FocusReason.BacktabFocusReason,Qt.FocusReason.ShortcutFocusReason)
        super().focusInEvent(event)

    def animate(self,value):
        self.phase=float(value)
        self.update()

    def enterEvent(self,event):
        self.fade(1.)
        super().enterEvent(event)

    def leaveEvent(self,event):
        self.fade(0.)
        super().leaveEvent(event)

    def fade(self,end):
        self.animation.stop()
        self.animation.setStartValue(self.phase)
        self.animation.setEndValue(end)
        self.animation.start()

    def paintEvent(self,event):
        p=QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        a=QColor('#62ddc1' if self.primary else '#17263a')
        b=QColor('#99f4df' if self.primary else '#2c425a')
        color=QColor(*[int(a.getRgb()[i]+(b.getRgb()[i]-a.getRgb()[i])*self.phase) for i in range(3)])
        if self.ghost:
            color.setAlpha(int(10+80*self.phase))
        if self.isDown():
            color=color.darker(115)
        p.setBrush(color)
        p.setPen(QPen(QColor('#41576c' if not self.primary else '#7eefd4'),1) if not self.ghost else Qt.PenStyle.NoPen)
        p.drawRoundedRect(QRectF(1,1,self.width()-2,self.height()-2),9,9)
        fg=QColor('#092f2b' if self.primary else '#ceddea') if self.isEnabled() else QColor('#56677c')
        p.setPen(fg)
        text=self.text().lstrip('+ ')
        font=self.font()
        font.setWeight(QFont.Weight.Medium)
        p.setFont(font)
        width=p.fontMetrics().horizontalAdvance(text)
        start=(self.width()-width-25)/2
        cy=self.height()/2
        p.save()
        p.translate(start,cy-8)
        pen=QPen(fg,1.6)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        def line(x1,y1,x2,y2):
            p.drawLine(QPointF(x1,y1),QPointF(x2,y2))
        if '暂停' in text or '停止' in text:
            line(5,3,5,13);line(11,3,11,13)
        elif '连接' in text or '恢复' in text:
            path=QPainterPath();path.moveTo(4,2);path.lineTo(13,8);path.lineTo(4,14);path.closeSubpath();p.drawPath(path)
        elif '添加' in text:
            line(8,2,8,14);line(2,8,14,8)
        elif '移除' in text:
            line(3,4,13,4);line(6,1,10,1);p.drawRoundedRect(QRectF(4,4,8,10),1,1);line(7,7,7,11);line(10,7,10,11)
        elif '导入' in text or '迁移' in text:
            line(8,1,8,10);line(4,7,8,11);line(8,11,12,7);line(2,11,2,14);line(2,14,14,14);line(14,14,14,11)
        elif 'config' in text:
            line(5,4,1,8);line(1,8,5,12);line(11,4,15,8);line(15,8,11,12);line(9,2,7,14)
        elif '编辑' in text:
            line(3,13,5,8);line(5,8,12,1);line(12,1,15,4);line(15,4,8,11);line(8,11,3,13)
        else:
            p.drawEllipse(QRectF(1,1,14,14));line(8,7,8,12);p.drawPoint(QPointF(8,4))
        p.restore()
        p.setPen(fg)
        p.drawText(QRectF(start+25,0,width+3,self.height()),Qt.AlignmentFlag.AlignVCenter,text)
        if self.hasFocus() and self.keyboard_focus:
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(QPen(QColor('#b1f6e5'),1))
            p.drawRoundedRect(QRectF(4,4,self.width()-8,self.height()-8),6,6)


def label(text, kind=None):
    w = QLabel(text)
    w.setTextFormat(Qt.TextFormat.PlainText)
    if kind:
        w.setObjectName(kind)
    return w


def fmt(value, suffix="", digits=0):
    return "N/A" if value is None else f"{value:,.{digits}f}{suffix}"


class Backdrop(QWidget):
    def paintEvent(self, event):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor("#080f1e"))
        for x, y, radius, color in ((self.width()*.75, 0, 600, QColor(0,190,202,24)),
                                    (self.width()*.9, self.height(), 650, QColor(110,57,220,23))):
            g = QRadialGradient(x,y,radius)
            g.setColorAt(0,color)
            g.setColorAt(1,QColor(0,0,0,0))
            p.fillRect(self.rect(),g)
        p.setPen(QColor(75,143,183,10))
        for x in range(0,self.width(),40):
            p.drawLine(x,0,x,self.height())
        for y in range(0,self.height(),40):
            p.drawLine(0,y,self.width(),y)


class Sparkline(QWidget):
    def __init__(self):
        super().__init__()
        self.values = []
        self.setFixedHeight(36)

    def paintEvent(self,event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w,h = self.width(),self.height()
        p.setPen(QPen(QColor("#253d54"),1))
        for y in (h-3,h//2):
            p.drawLine(0,y,w,y)
        path = QPainterPath()
        last = None
        for i,v in enumerate(self.values):
            if v is None:
                last = None
                continue
            x = (60-len(self.values)+i)*w/59
            y = h-3-min(100,max(0,v))/100*(h-8)
            if last is None:
                path.moveTo(x,y)
            else:
                path.lineTo(x,y)
            last = (x,y)
        p.setPen(QPen(QColor(73,255,224,30),7))
        p.drawPath(path)
        p.setPen(QPen(QColor("#61f9de"),1.7))
        p.drawPath(path)
        if last:
            p.setBrush(QColor("#b9fff1"))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(last[0]-2,last[1]-2,4,4)


class GPUCard(QFrame):
    def __init__(self,gpu,history=()):
        super().__init__()
        self.setObjectName("card")
        box=QVBoxLayout(self)
        box.setContentsMargins(17,12,17,12)
        box.setSpacing(5)
        self.title=label("","eyebrow")
        self.name=label("")
        self.name.setStyleSheet("font-size:12px;font-weight:600;color:#bdd5e9")
        self.metric_label=label("","metric")
        self.spark=Sparkline()
        self.memory=label("","muted")
        self.bar=QProgressBar()
        self.bar.setTextVisible(False)
        self.thermal=label("","muted")
        for widget in (self.title,self.name,self.metric_label,self.spark,self.memory,self.bar,self.thermal):
            box.addWidget(widget)
        self.update_data(gpu,history)

    def update_data(self,g,history):
        self.title.setText(f"GPU {g['index']:02d}  /  {g['state']}")
        self.title.setToolTip(g["uuid"])
        name=g["name"].replace("NVIDIA ","")
        self.name.setText(name[:27]+("…" if len(name)>27 else ""))
        self.name.setToolTip(g["name"])
        self.metric_label.setText(fmt(g["util"],"%"))
        self.spark.values=list(history)
        self.spark.update()
        self.memory.setText(f"{fmt(g['used']/1024 if g['used'] is not None else None,digits=1)} / {fmt(g['total']/1024 if g['total'] is not None else None,' GiB',1)}")
        self.memory.setToolTip(f"显存：{fmt(g['used'])} / {fmt(g['total'])} MiB")
        self.bar.setValue(int(100*(g['used'] or 0)/g['total']) if g['total'] else 0)
        self.thermal.setText(f"{fmt(g['temp'],' °C')}   ·   {fmt(g['power'],' W',1)}")
        self.thermal.setToolTip(f"风扇：{g['fan']}")


class HostTile(QFrame):
    def __init__(self,session):
        super().__init__()
        self.setObjectName("hostTile")
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        box=QVBoxLayout(self)
        box.setContentsMargins(15,13,15,13)
        box.setSpacing(7)
        row=QHBoxLayout()
        self.name=label(session.profile['name'])
        self.name.setStyleSheet("font-weight:700;font-size:14px;color:#dff5ff")
        self.dot=label("●")
        row.addWidget(self.name,1)
        row.addWidget(self.dot)
        box.addLayout(row)
        self.endpoint=label(session.profile['host'],"muted")
        box.addWidget(self.endpoint)
        self.summary=label("","muted")
        box.addWidget(self.summary)
        self.bar=QProgressBar()
        self.bar.setTextVisible(False)
        box.addWidget(self.bar)
        self.update_data(session)

    def update_data(self,session,selected=False):
        self.setProperty("selected",selected)
        self.style().unpolish(self)
        self.style().polish(self)
        name=session.profile['name']
        self.name.setText(name[:21]+('…' if len(name)>21 else ''))
        self.name.setToolTip(name)
        endpoint=session.profile['host']
        self.endpoint.setText(endpoint[:29]+('…' if len(endpoint)>29 else ''))
        self.dot.setStyleSheet("color:"+("#64ffce" if session.fresh else "#ffbf68" if session.desired else "#637792"))
        if session.snapshot:
            gs=session.snapshot['gpus']
            utils=[g['util'] for g in gs if g['util'] is not None]
            avg=sum(utils)/len(utils) if utils else None
            self.summary.setText(f"{session.state}  ·  {len(gs)} GPU  ·  {fmt(avg,'%')}" if gs else session.state+(' · SSH 保活' if session.fresh else ''))
            self.bar.setValue(int(avg or 0))
            self.bar.setVisible(bool(gs))
        else:
            self.summary.setText(session.state+"  ·  等待遥测")
            self.bar.setValue(0)
        self.setToolTip(session.message)
