from pathlib import Path
from PySide6.QtCore import Qt,QRectF,QPointF,QVariantAnimation,QSize
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen, QLinearGradient, QRadialGradient,QFont
from PySide6.QtWidgets import QWidget, QFrame, QLabel, QVBoxLayout, QHBoxLayout, QProgressBar,QPushButton,QSizePolicy

STYLE = """
QWidget {font-family:'Rajdhani Medium','Rajdhani','ZCOOL QingKe HuangYou','Noto Sans SC';font-size:15px;color:#a9cbdc;background:transparent;}
QDialog,QMessageBox {background:#101b2d;}
QLabel {border:0;background:transparent;}
QLabel#muted {color:#7498b1;font-size:14px;}
QLabel#eyebrow {color:#5d9aaf;font-family:'Rajdhani Medium','Rajdhani','ZCOOL QingKe HuangYou';font-size:13px;letter-spacing:1px;}
QLabel#brand {color:#8ad5e3;font-family:'Orbitron','ZCOOL QingKe HuangYou';font-size:16px;font-weight:500;}
QLabel#section {color:#69cddd;font-family:'ZCOOL QingKe HuangYou','Noto Sans SC';font-size:24px;font-weight:400;letter-spacing:1px;}
QLabel#count {color:#75e6e1;background:#102b39;border:1px solid #28515d;border-radius:1px;font-family:'Orbitron';font-size:14px;font-weight:500;}
QLabel#heading {color:#a0dfea;font-family:'Orbitron','ZCOOL QingKe HuangYou','Noto Sans SC';font-size:27px;font-weight:500;}
QFrame#sidebar {background:rgba(9,17,32,235);border-right:1px solid #20334d;}
QFrame#glass,QFrame#card,QFrame#hostTile {background:transparent;border:0;}
QLabel#metric {font-family:'Orbitron';font-size:30px;font-weight:500;color:#6bf8e0;}
QLabel#stat {font-family:'Orbitron','ZCOOL QingKe HuangYou';font-size:21px;font-weight:500;color:#8fc8de;}
QLineEdit,QSpinBox,QComboBox {background:#0b192a;border:1px solid #30536b;border-bottom:2px solid #345d73;border-radius:1px;padding:9px 12px;min-height:20px;selection-background-color:#15798a;}
QLineEdit:focus,QSpinBox:focus,QComboBox:focus {border:1px solid #54e6e1;}
QComboBox QAbstractItemView {background:#14233a;color:#d5edff;selection-background-color:#24566b;}
QPushButton {background:#142c3d;border:1px solid #365d74;border-radius:1px;padding:10px 20px;font-weight:400;}
QPushButton:hover {background:#263c50;border-color:#52677d;color:#f0faff;}
QPushButton:pressed {background:#112137;}
QPushButton#primary {background:#64e5c7;border:1px solid #64e5c7;color:#072a29;}
QPushButton#primary:hover {background:#8df2d9;border-color:#8df2d9;}
QPushButton#danger {color:#ffb0b7;border-color:#694152;}
QPushButton:disabled {color:#50647c;border-color:#25354d;background:#132035;}
QListWidget {border:0;outline:0;background:transparent;}
QListWidget::item {border:0;background:transparent;padding:0;margin:0 0 10px 0;}
QListWidget::item:selected {background:transparent;}
QProgressBar {background:#1b3047;border:0;border-radius:0;height:5px;max-height:5px;}
QProgressBar::chunk {background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #187f9c,stop:1 #65ffe0);border-radius:0;}
QTableWidget {background:rgba(11,22,39,215);border:1px solid #315267;border-radius:1px;gridline-color:#2b4b60;selection-background-color:#194f62;selection-color:#a8efeb;}
QHeaderView::section {background:#15263c;color:#8eacc6;padding:11px 8px;border:0;border-bottom:1px solid #30465f;font-weight:600;}
QTableWidget::item {padding:7px;border-bottom:1px solid #1c2d44;}
QTableWidget::item:selected {background:#17485b;}
QTextEdit {background:rgba(13,26,45,215);border:1px solid #315267;border-radius:1px;padding:12px;font-family:'JetBrains Mono','ZCOOL QingKe HuangYou';font-size:13px;color:#91b8cc;}
QScrollArea {border:0;background:transparent;}
QScrollBar:horizontal {height:7px;background:#102139;border:0;}
QScrollBar:vertical {width:7px;background:#102139;border:0;}
QScrollBar::handle {background:#3c6c80;border-radius:0;min-width:25px;min-height:25px;}
QScrollBar::add-line,QScrollBar::sub-line {width:0;height:0;}
QCheckBox {spacing:8px;}
QCheckBox::indicator {width:16px;height:16px;border:1px solid #52738d;border-radius:0;background:#0c1729;}
QCheckBox::indicator:checked {background:#29b8b0;border:1px solid #8cf9e1;}
QSplitter::handle {background:#183547;height:5px;}
QToolTip {background:#182b43;color:#e0f5ff;border:1px solid #3f718c;padding:7px;}
"""


def notch_path(rect,cut=9):
    x,y,w,h=rect.x(),rect.y(),rect.width(),rect.height()
    p=QPainterPath()
    p.moveTo(x,y);p.lineTo(x+w-cut,y);p.lineTo(x+w,y+cut)
    p.lineTo(x+w,y+h);p.lineTo(x+cut,y+h);p.lineTo(x,y+h-cut);p.closeSubpath()
    return p


class MechPanel(QFrame):
    def paintEvent(self,event):
        p=QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        role=self.objectName()
        selected=bool(self.property('selected'))
        rect=QRectF(0.7,0.7,self.width()-1.4,self.height()-1.4)
        gradient=QLinearGradient(0,0,self.width(),self.height())
        gradient.setColorAt(0,QColor(22,61,76,230) if selected else QColor(17,37,56,222))
        gradient.setColorAt(1,QColor(12,28,46,225))
        p.setBrush(gradient)
        p.setPen(QPen(QColor('#58c8ce' if selected else '#2c5368'),1))
        p.drawPath(notch_path(rect,10))
        accent=QColor('#64e5d8' if selected else '#3e98ac' if role=='card' else '#315e76')
        p.setPen(QPen(accent,2))
        p.drawLine(QPointF(1,1),QPointF(min(47,self.width()/3),1))
        p.drawLine(QPointF(self.width()-1,self.height()-1),QPointF(self.width()-24,self.height()-1))
        if selected:
            p.drawLine(QPointF(1,13),QPointF(1,self.height()-16))


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
        if not self.property('fixedAction'):
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
        p.drawPath(notch_path(QRectF(1,1,self.width()-2,self.height()-2),7))
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
            p.drawPath(notch_path(QRectF(4,4,self.width()-8,self.height()-8),5))


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


class GPUCard(MechPanel):
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


class HostTile(MechPanel):
    def __init__(self,session):
        super().__init__()
        self.setObjectName("hostTile")
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        box=QVBoxLayout(self)
        box.setContentsMargins(15,13,15,13)
        box.setSpacing(7)
        row=QHBoxLayout()
        self.name=label(session.profile['name'])
        self.name.setStyleSheet("font-family:'Rajdhani Medium','Rajdhani','ZCOOL QingKe HuangYou';font-weight:500;font-size:17px;color:#95cfe0")
        self.dot=StatusIndicator('')
        self.dot.setFixedSize(10,16)
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
        self.dot.setTone('#5bdac4' if session.fresh else '#c8a572' if session.desired else '#5c798c')
        if session.snapshot:
            gs=session.snapshot['gpus']
            utils=[g['util'] for g in gs if g['util'] is not None]
            avg=sum(utils)/len(utils) if utils else None
            self.summary.setText(f"{session.state}  ·  {len(gs)} GPU  ·  {fmt(avg,'%')}" if gs else session.state+(' · SSH 保活' if session.fresh else ''))
            self.bar.setValue(int(avg or 0))
            self.bar.setVisible(bool(gs))
        else:
            self.summary.setText('已暂停 · 随时可恢复' if not session.profile['autoconnect'] and not session.desired else session.state+' · 等待遥测')
            self.bar.setValue(0)
            self.bar.setVisible(session.desired)
        self.setToolTip(session.message)


class StatusIndicator(QWidget):
    def __init__(self,text='尚未连接'):
        super().__init__()
        self.value=text
        self.tone=QColor('#78a2b4')
        self.setFixedHeight(26)
        self.setText(text)

    def setText(self,text):
        self.value=text.removeprefix('● ')
        self.setFixedWidth(self.fontMetrics().horizontalAdvance(self.value)+25)
        self.update()

    def text(self):
        return self.value

    def setTone(self,color):
        self.tone=QColor(color)
        self.update()

    def paintEvent(self,event):
        p=QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(self.tone)
        path=QPainterPath()
        path.moveTo(1,self.height()/2);path.lineTo(5,self.height()/2-4);path.lineTo(9,self.height()/2);path.lineTo(5,self.height()/2+4);path.closeSubpath()
        p.drawPath(path)
        p.setPen(self.tone)
        p.setFont(self.font())
        p.drawText(QRectF(17,0,self.width()-17,self.height()),Qt.AlignmentFlag.AlignVCenter,self.value)
