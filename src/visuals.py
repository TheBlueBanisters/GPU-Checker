from themes import set_style, color as themed, is_day
import math
import time
from card_motion import CardMotion
from pathlib import Path
from PySide6.QtCore import Qt,QRectF,QPointF,QPoint,QVariantAnimation,QSize,QEvent,QEasingCurve,Signal
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen, QLinearGradient, QRadialGradient,QFont
from PySide6.QtWidgets import QWidget, QFrame, QLabel, QVBoxLayout, QHBoxLayout, QProgressBar,QPushButton,QSizePolicy,QGraphicsDropShadowEffect
from availability import result as availability_result

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
QLineEdit,QSpinBox,QDoubleSpinBox,QComboBox {background:#0b192a;border:1px solid #30536b;border-bottom:2px solid #345d73;border-radius:1px;padding:9px 12px;min-height:20px;selection-background-color:#15798a;}
QLineEdit:focus,QSpinBox:focus,QDoubleSpinBox:focus,QComboBox:focus {border:1px solid #54e6e1;}
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
    def __init__(self,parent=None):
        super().__init__(parent)
        self.feedback_enabled=False
        self.hover_amount=0.
        self.click_progress=1.
        self.ripples=[]
        self.feedback_point=QPointF(30,30)
        self.click_origin=QPointF(30,30)
        self.hover_animation=QVariantAnimation(self)
        self.hover_animation.setDuration(240)
        self.hover_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.hover_animation.valueChanged.connect(self._hover_frame)
        self.click_animation=QVariantAnimation(self)
        self.click_animation.setDuration(2400)
        self.click_animation.setStartValue(0.)
        self.click_animation.setEndValue(1.)
        self.click_animation.setEasingCurve(QEasingCurve.Type.Linear)
        self.click_animation.valueChanged.connect(self._click_frame)
        self.click_animation.finished.connect(self.clear_ripples)

    def enable_feedback(self):
        self.feedback_enabled=True
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        # Passive labels/charts must forward feedback without losing their tooltips.
        for child in self.findChildren(QWidget):
            child.setMouseTracking(True)
            child.installEventFilter(self)

    def _hover_frame(self,value):
        self.hover_amount=float(value)
        self.update()

    def _click_frame(self,value):
        now=time.monotonic()
        self.ripples=[wave for wave in self.ripples if now-wave[1]<2.4]
        self.click_progress=float(value)
        self.update()

    def _hover_to(self,end):
        if abs(self.hover_amount-end)<.001 and self.hover_animation.state()!=QVariantAnimation.State.Running:
            return
        if self.hover_animation.endValue()==end and self.hover_animation.state()==QVariantAnimation.State.Running:
            return
        self.hover_animation.stop()
        self.hover_animation.setStartValue(self.hover_amount)
        self.hover_animation.setEndValue(end)
        self.hover_animation.start()

    def pulse_at(self,point):
        if not self.feedback_enabled:
            return
        self.feedback_point=QPointF(point)
        self.click_origin=QPointF(point)
        self.ripples.append((QPointF(point),time.monotonic()))
        self.click_animation.stop()
        self.click_progress=0.
        self.click_animation.start()
        self.update()

    def ripple_color(self):
        return themed(self.property('feedbackColor') or self.property('availabilityColor') or '#75e6e1')

    def clear_ripples(self):
        self.click_animation.stop()
        self.ripples.clear()
        self.click_progress=1.
        self.update()

    def eventFilter(self,watched,event):
        if isinstance(watched,QPushButton):return super().eventFilter(watched,event)
        if getattr(self,'feedback_enabled',False):
            if event.type()==QEvent.Type.MouseMove:
                self.feedback_point=QPointF(watched.mapTo(self,event.position().toPoint()))
                self._hover_to(1.)
                self.update()
            elif event.type() in (QEvent.Type.MouseButtonPress,QEvent.Type.MouseButtonDblClick) and event.button()==Qt.MouseButton.LeftButton:
                self.pulse_at(QPointF(watched.mapTo(self,QPoint()))+event.position())
                return True
        return super().eventFilter(watched,event)

    def enterEvent(self,event):
        if getattr(self,'feedback_enabled',False):
            self._hover_to(1.)
        super().enterEvent(event)

    def leaveEvent(self,event):
        if getattr(self,'feedback_enabled',False):
            self._hover_to(0.)
        super().leaveEvent(event)

    def mouseMoveEvent(self,event):
        if getattr(self,'feedback_enabled',False):
            self.feedback_point=event.position()
            self.update()
        super().mouseMoveEvent(event)

    def mousePressEvent(self,event):
        if self.feedback_enabled and event.button()==Qt.MouseButton.LeftButton:
            self.pulse_at(event.position())
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseDoubleClickEvent(self,event):
        self.mousePressEvent(event)

    def hideEvent(self,event):
        self.hover_animation.stop()
        self.clear_ripples()
        self.hover_amount=0.
        super().hideEvent(event)

    def panel_path(self,rect):
        if self.property('squarePanel'):
            path=QPainterPath();path.addRect(rect);return path
        return notch_path(rect,10)

    def paint_background(self,p,rect):
        pass

    def paintEvent(self,event):
        p=QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        role=self.objectName()
        selected=bool(self.property('selected'))
        rect=QRectF(0.7,0.7,self.width()-1.4,self.height()-1.4)
        gradient=QLinearGradient(0,0,self.width(),self.height())
        tones=[(18,38,59),(26,35,59),(18,44,48),(34,36,52)]
        tone=(29,37,43) if self.property('noGpu') else tones[int(self.property('hostTone') or 0)%len(tones)] if role=='hostTile' else (17,37,56)
        if is_day():
            tones=[(222,237,246),(232,230,246),(221,240,234),(235,232,240)]
            tone=(232,237,241) if self.property('noGpu') else tones[int(self.property('hostTone') or 0)%4] if role=='hostTile' else (239,247,251)
        state_color=self.property('availabilityColor')
        if role=='card' and state_color:
            tint=themed(state_color).getRgb()
            tone=tuple(round(tone[i]*.85+tint[i]*.15) for i in range(3))
        gradient.setColorAt(0,(QColor if is_day() else themed)(*(tuple(min(255,n+7) for n in tone) if selected else tone),230 if selected else 222))
        gradient.setColorAt(1,themed(12,28,46,225))
        p.setBrush(gradient)
        edge=themed(state_color) if state_color else themed('#58c8ce' if selected else '#2c5368')
        if state_color:
            edge.setAlpha(165)
        p.setPen(QPen(edge,1))
        p.drawPath(self.panel_path(rect))
        self.paint_background(p,rect)
        accent=themed(state_color or ('#64e5d8' if selected else '#3e98ac' if role=='card' else '#315e76'))
        p.setPen(QPen(accent,2))
        p.drawLine(QPointF(1,1),QPointF(min(47,self.width()/3),1))
        p.drawLine(QPointF(self.width()-1,self.height()-1),QPointF(self.width()-24,self.height()-1))
        if selected:
            p.drawLine(QPointF(1,13),QPointF(1,self.height()-16))
        if self.feedback_enabled and (self.hover_amount>0 or self.ripples):
            outline=self.panel_path(rect)
            p.setClipPath(outline)
            if self.hover_amount>0:
                glow=QRadialGradient(self.feedback_point,max(self.width(),self.height())*.85)
                hover_color=QColor(themed(state_color)) if role=='card' and state_color else themed('#63dec1')
                ink=QColor(hover_color);ink.setAlpha(int(43*self.hover_amount));glow.setColorAt(0,ink)
                ink.setAlpha(0);glow.setColorAt(1,ink)
                p.fillPath(outline,glow)
                p.setBrush(Qt.BrushStyle.NoBrush)
                ink=QColor(hover_color);ink.setAlpha(int(175*self.hover_amount))
                p.setPen(QPen(ink,1.6))
                p.drawPath(outline)
                p.setPen(QPen(themed(102,255,227,int(90*self.hover_amount)),4))
                p.drawLine(QPointF(1,1),QPointF(min(72,self.width()/2),1))
            for origin,born in tuple(self.ripples):
                t=min(1,max(0,(time.monotonic()-born)/2.4))
                if t>=1: continue
                # Smooth ease-in/out expansion and soft annuli, no sweeping scan bar.
                travel=t*t*(3-2*t)
                reach=max(math.hypot(x-origin.x(),y-origin.y())
                          for x,y in ((0,0),(self.width(),0),(0,self.height()),(self.width(),self.height())))
                radius=max(2,reach*travel)
                fade=math.sin(math.pi*t)**1.5
                glow=QRadialGradient(origin,radius)
                for stop,alpha in ((0,0),(.55,0),(.72,7),(.84,22),(.94,9),(1,0)):
                    ink=self.ripple_color();ink.setAlpha(round(alpha*fade))
                    glow.setColorAt(stop,ink)
                p.fillPath(outline,glow)
                if t>.16:
                    echo=QRadialGradient(origin,max(2,radius*.64))
                    for stop,alpha in ((0,0),(.7,0),(.86,10),(1,0)):
                        ink=self.ripple_color();ink.setAlpha(round(alpha*fade))
                        echo.setColorAt(stop,ink)
                    p.fillPath(outline,echo)
        if role=='card' and state_color:
            # Draw last: hover feedback must never replace the workload color.
            p.setClipping(False)
            border=self.panel_path(QRectF(1.4,1.4,self.width()-2.8,self.height()-2.8))
            ink=QColor(themed(state_color));ink.setAlpha(48 if not is_day() else 32)
            p.setBrush(Qt.BrushStyle.NoBrush);p.setPen(QPen(ink,6));p.drawPath(border)
            ink=QColor(themed(state_color));ink.setAlpha(255)
            p.setPen(QPen(ink,2.1));p.drawPath(border)




class ModernButton(QPushButton):
    """Quiet Fluent-inspired controls, drawn consistently on every Windows theme."""
    def __init__(self,text,primary=False,ghost=False):
        super().__init__(text)
        self.primary,self.ghost=primary,ghost
        self.phase=0.
        self.resume_emphasis=False
        self.monitor_action=None
        self.action_glow=None
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

    def set_resume_emphasis(self,enabled):
        if self.resume_emphasis==enabled: return
        self.resume_emphasis=enabled
        self.sync_glow()
        self.update()

    def sync_glow(self):
        self.glow_frame()

    def set_monitor_action(self,action):
        if action==self.monitor_action: return
        self.monitor_action=action
        if action and self.action_glow is None:
            self.action_glow=QGraphicsDropShadowEffect(self)
            self.action_glow.setOffset(0,0)
            self.setGraphicsEffect(self.action_glow)
        if self.action_glow: self.action_glow.setEnabled(action is not None)
        self.sync_glow();self.glow_frame()

    def glow_frame(self):
        if self.action_glow and self.monitor_action:
            color=QColor(themed('#ee7d8f',day='#b53551') if self.monitor_action=='pause' else themed('#65e69d',day='#219455'))
            color.setAlpha(190)
            self.action_glow.setColor(color)
            self.action_glow.setBlurRadius(38)
        self.update()

    def showEvent(self,event):
        super().showEvent(event)
        self.sync_glow()

    def hideEvent(self,event):
        super().hideEvent(event)

    def changeEvent(self,event):
        super().changeEvent(event)
        if event.type() in (QEvent.Type.PaletteChange,QEvent.Type.StyleChange) and hasattr(self,'action_glow'):
            self.glow_frame()

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
        a=themed('#62ddc1' if self.primary else '#17263a')
        b=themed('#99f4df' if self.primary else '#2c425a')
        if self.monitor_action:
            a=themed('#e37b8b',day='#ae3450') if self.monitor_action=='pause' else themed('#67dd9c',day='#197b4b')
            b=themed('#f0a2ad',day='#c64961') if self.monitor_action=='pause' else themed('#9bf1be',day='#24965d')
        color=QColor(*[int(a.getRgb()[i]+(b.getRgb()[i]-a.getRgb()[i])*self.phase) for i in range(3)])
        if self.ghost:
            color.setAlpha(int(10+80*self.phase))
        if self.isDown():
            color=color.darker(115)
        p.setBrush(color)
        p.setPen(QPen(themed('#41576c' if not self.primary else '#7eefd4'),1) if not self.ghost else Qt.PenStyle.NoPen)
        p.drawPath(notch_path(QRectF(1,1,self.width()-2,self.height()-2),7))
        if self.resume_emphasis or self.monitor_action:
            p.setBrush(Qt.BrushStyle.NoBrush)
            for inset,thickness,alpha in ((2,5,26),(2,3,46),(2,1.3,180)):
                ink=QColor(themed('#ffd1da',day='#f1a6b5') if self.monitor_action=='pause' else themed('#baf6cf',day='#72d99b'));ink.setAlpha(alpha)
                p.setPen(QPen(ink,thickness))
                p.drawPath(notch_path(QRectF(inset,inset,self.width()-2*inset,self.height()-2*inset),6))
        fg=themed('#092f2b' if self.primary else '#ceddea') if self.isEnabled() else themed('#56677c')
        if self.monitor_action and self.isEnabled():
            fg=QColor('#fff5f7' if is_day() else '#35141e') if self.monitor_action=='pause' else QColor('#f0fff5' if is_day() else '#123723')
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
        elif '刷新' in text or '复位' in text:
            p.drawArc(QRectF(2.5,2.5,11,11),40*16,285*16);line(13,2,13,6);line(9,6,13,6)
        elif '缓存' in text:
            p.drawRoundedRect(QRectF(2,2,12,12),2,2);line(5,5,11,5);line(5,8,11,8);line(5,11,8,11)
        elif '保存' in text:
            p.drawRect(QRectF(2,2,12,12));p.drawRect(QRectF(5,2,6,4));p.drawRect(QRectF(5,9,6,5))
        elif '添加' in text:
            line(8,2,8,14);line(2,8,14,8)
        elif '移除' in text or '清除' in text:
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
            p.setPen(QPen(themed('#b1f6e5'),1))
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
        self.paint_backdrop(p)

    def paint_backdrop(self,p):
        p.fillRect(self.rect(), themed("#080f1e"))
        for x, y, radius, color in ((self.width()*.75, 0, 600, themed(0,190,202,24)),
                                    (self.width()*.9, self.height(), 650, themed(110,57,220,23))):
            g = QRadialGradient(x,y,radius)
            g.setColorAt(0,color)
            g.setColorAt(1,themed(0,0,0,0))
            p.fillRect(self.rect(),g)
        p.setPen(themed(75,143,183,10))
        for x in range(0,self.width(),40):
            p.drawLine(x,0,x,self.height())
        for y in range(0,self.height(),40):
            p.drawLine(0,y,self.width(),y)


class Sparkline(QWidget):
    def __init__(self):
        super().__init__()
        self.values = []
        self.color=QColor('#61f9de')
        self.setFixedHeight(36)

    def paintEvent(self,event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w,h = self.width(),self.height()
        p.setPen(QPen(themed("#253d54"),1))
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
        glow=themed(self.color);glow.setAlpha(30)
        p.setPen(QPen(glow,7))
        p.drawPath(path)
        p.setPen(QPen(themed(self.color),1.7))
        p.drawPath(path)
        if last:
            p.setBrush(themed(self.color).lighter(130))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(last[0]-2,last[1]-2,4,4)


class HistoryLink(QPushButton):
    """A quiet footer action with a chart glyph, aligned to the same baseline."""
    def __init__(self):
        super().__init__('历史');self.setFixedSize(64,28)
        self.setCursor(Qt.CursorShape.PointingHandCursor);self.setAccessibleName('查看监控历史')
        set_style(self,'font-size:12px;padding:0px;border:0;background:transparent;color:#7498b1')
    def paintEvent(self,event):
        p=QPainter(self);p.setRenderHint(QPainter.RenderHint.Antialiasing)
        color=themed('#75e6e1' if self.underMouse() or self.hasFocus() else '#7498b1')
        if self.underMouse() or self.isDown():
            fill=themed('#205568');fill.setAlpha(110);p.fillPath(notch_path(QRectF(0,0,self.width(),self.height()),5),fill)
        if self.isDown():p.translate(0,1)
        middle=self.height()/2;p.setPen(QPen(color,1.1))
        path=QPainterPath(QPointF(5,middle+4));path.lineTo(9,middle);path.lineTo(12,middle+2);path.lineTo(17,middle-5);p.drawPath(path)
        p.setFont(self.font());p.drawText(QRectF(23,0,self.width()-33,self.height()),Qt.AlignmentFlag.AlignVCenter,'历史')
        p.drawLine(QPointF(self.width()-9,middle-3),QPointF(self.width()-6,middle));p.drawLine(QPointF(self.width()-6,middle),QPointF(self.width()-9,middle+3))


def history_button():return HistoryLink()


def history_footer():
    footer=QFrame();footer.setObjectName('historyFooter');footer.setFixedHeight(32)
    set_style(footer,'QFrame#historyFooter {border:0;border-top:1px solid #2b4b60;background:transparent;}')
    row=QHBoxLayout(footer);row.setContentsMargins(0,4,0,0);row.setSpacing(5)
    return footer,row


class GPUCard(MechPanel):
    historyRequested=Signal(str)
    def panel_path(self,rect):
        path=notch_path(rect,10)
        if not hasattr(self,'motion') or self.motion.state!='paused': return path
        # Actual cutouts in the painted chassis, with unchanged widget geometry.
        cuts=QPainterPath()
        anchors=((rect.left()+rect.width()*.72,rect.top(),0),
                 (rect.right(),rect.top()+rect.height()*.38,1),
                 (rect.left()+rect.width()*.57,rect.bottom(),2),
                 (rect.left(),rect.top()+rect.height()*.62,3))
        for x,y,side in anchors:
            polygon=[]
            variation=math.sin((self.motion.seed+side*13)*.71)
            half=4.2+variation;depth=8+variation*1.6
            for u,v in ((-half,-2),(half,-2),(half*.65,2),(half*.1,depth*.7),(-half*.3,depth*.4),(-half*.75,depth)):
                dx,dy=((u,v),(-v,u),(u,-v),(v,u))[side]
                polygon.append(QPointF(x+dx,y+dy))
            cut=QPainterPath(polygon[0])
            for point in polygon[1:]:cut.lineTo(point)
            cut.closeSubpath();cuts.addPath(cut)
        return path.subtracted(cuts)

    def paint_background(self,p,rect):
        self.motion.paint(p,rect)

    def showEvent(self,event):
        super().showEvent(event)
        self.motion.sync()

    def hideEvent(self,event):
        self.motion.timer.stop()
        overlay=getattr(self,'halo_overlay',None)
        if overlay is not None:overlay.hide()
        super().hideEvent(event)

    def eventFilter(self,watched,event):
        if hasattr(self,'motion') and event.type() in (QEvent.Type.WindowStateChange,QEvent.Type.Show):
            self.motion.sync()
        return super().eventFilter(watched,event)

    def __init__(self,gpu,history=(),availability=None):
        super().__init__()
        self.setObjectName("card")
        self.motion=CardMotion(self)
        box=QVBoxLayout(self)
        box.setContentsMargins(17,12,17,12)
        box.setSpacing(5)
        self.title=label("","eyebrow")
        self.state_label=StatusIndicator('不可用',diamond_size=12)
        set_style(self.state_label,'font-size:16px;font-weight:600')
        title_row=QHBoxLayout()
        title_row.setContentsMargins(0,0,0,0)
        title_row.addWidget(self.title,1)
        title_row.setAlignment(self.title,Qt.AlignmentFlag.AlignTop)
        status=QVBoxLayout()
        status.setSpacing(0)
        status.addWidget(self.state_label,0,Qt.AlignmentFlag.AlignRight)
        self.pause_note=label('（暂停监控）')
        self.pause_note.setFixedSize(104,18)
        set_style(self.pause_note,'font-size:12px;color:#859faf')
        self.pause_note.setAlignment(Qt.AlignmentFlag.AlignRight)
        status.addWidget(self.pause_note)
        title_row.addLayout(status)
        box.addLayout(title_row)
        self.name=label("")
        self.name.setWordWrap(True)
        self.name.setMinimumHeight(30)
        self.name.setMaximumHeight(54)
        set_style(self.name,"font-size:21px;font-weight:600;color:#bdd5e9")
        self.metric_label=label("","metric")
        self.spark=Sparkline()
        self.memory=label("","muted")
        self.bar=QProgressBar()
        self.bar.setTextVisible(False)
        self.thermal=label("","muted")
        for widget in (self.name,self.metric_label,self.spark,self.memory,self.bar):
            box.addWidget(widget)
        footer,bottom=history_footer()
        self.thermal.setMinimumWidth(0);self.thermal.setSizePolicy(QSizePolicy.Policy.Ignored,QSizePolicy.Policy.Preferred)
        bottom.addWidget(self.thermal,1)
        self.history_button=history_button()
        self.history_button.clicked.connect(lambda:self.historyRequested.emit(self.gpu_uuid))
        bottom.addWidget(self.history_button);box.addWidget(footer)
        self.update_data(gpu,history,availability)
        self.enable_feedback()

    def pulse_at(self,point):
        if self.motion.burst is not None:return
        super().pulse_at(point)
        self.motion.boost(point)

    def update_data(self,g,history,availability=None):
        self.gpu_uuid=g['uuid']
        self.motion.seed=sum((i+1)*ord(c) for i,c in enumerate(g['uuid']))%997
        self.title.setText(f"GPU {g['index'] if g['index'] is not None else '—'}")
        self.title.setToolTip(g["uuid"])
        name=g["name"].replace("NVIDIA ","")
        self.name.setText(name)
        self.name.setToolTip(g["name"])
        self.metric_label.setText(fmt(g["util"],"%"))
        self.spark.values=list(history)
        self.spark.update()
        self.memory.setText(f"{fmt(g['used']/1024 if g['used'] is not None else None,digits=1)} / {fmt(g['total']/1024 if g['total'] is not None else None,' GiB',1)}")
        self.memory.setToolTip(f"显存：{fmt(g['used'])} / {fmt(g['total'])} MiB")
        self.bar.setValue(int(100*(g['used'] or 0)/g['total']) if g['total'] else 0)
        self.thermal.setText(f"{fmt(g['temp'],' °C')}   ·   {fmt(g['power'],' W',1)}")
        self.thermal.setToolTip(f"风扇：{g['fan']}")
        self.set_availability(availability or availability_result('unknown','等待完整的可用性判断'))

    def set_availability(self,state):
        self.setProperty('idleHaloEligible',bool(state.get('idle_glow')))
        visual=state.get('visual',state['status'])
        self.motion.set_state(visual)
        color='#78909f' if visual in ('blocked','disconnected','paused') else state['color']
        self.setProperty('availabilityColor',color)
        self.setProperty('feedbackColor',state['color'] if state.get('historical') else color)
        self.state_label.setTone(state['color'] if state.get('historical') else color)
        self.state_label.setText(state['label'])
        self.pause_note.setText('（暂停监控）' if visual=='paused' else '')
        self.state_label.setToolTip(state['reason'])
        set_style(self.metric_label,f'color:{color}')
        set_style(self.bar,f'QProgressBar::chunk {{background:{color};border-radius:0;}}')
        self.spark.color=QColor(color)
        self.spark.update()
        self.setToolTip(state['label']+'：'+state['reason'])
        self.update()


class CapsuleLabel(QLabel):
    """Content-sized capsule with consistent round ends in both themes."""
    def __init__(self,text,tone='#78a9bd'):
        super().__init__(text)
        self.tone=tone
        self.setContentsMargins(10,2,10,2)
        self.setFixedHeight(27)
        self.setSizePolicy(QSizePolicy.Policy.Maximum,QSizePolicy.Policy.Fixed)
        set_style(self,'font-size:13px;color:'+tone)

    def paintEvent(self,event):
        p=QPainter(self);p.setRenderHint(QPainter.RenderHint.Antialiasing)
        ink=QColor(themed(self.tone));fill=QColor(ink);fill.setAlpha(22)
        outline=QColor(ink);outline.setAlpha(82)
        p.setBrush(fill);p.setPen(QPen(outline,1))
        p.drawRoundedRect(QRectF(.5,.5,self.width()-1,self.height()-1),self.height()/2,self.height()/2)
        p.end();super().paintEvent(event)


class HostTile(MechPanel):
    historyRequested=Signal(str)
    def __init__(self,session,tone_index=0):
        super().__init__()
        self.setObjectName("hostTile")
        self.feedback_enabled=True
        self.setProperty('hostTone',tone_index)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        box=QVBoxLayout(self)
        box.setContentsMargins(13,11,13,11)
        box.setSpacing(5)
        row=QHBoxLayout()
        self.name=label(session.profile['name'])
        set_style(self.name,"font-family:'Rajdhani Medium','Rajdhani','ZCOOL QingKe HuangYou';font-weight:500;font-size:17px;color:#95cfe0")
        self.dot=StatusIndicator('')
        self.dot.setFixedSize(10,16)
        row.addWidget(self.name,1)
        row.addWidget(self.dot)
        box.addLayout(row)
        self.endpoint=label(session.profile['host'],"muted")
        box.addWidget(self.endpoint)
        self.summary=label("","muted")
        info=QHBoxLayout();info.setSpacing(6)
        self.gpu_count=CapsuleLabel('显卡 — 张')
        info.addWidget(self.summary,1);info.addWidget(self.gpu_count)
        box.addLayout(info)
        self.capacity=CapsuleLabel('空闲 — · 可用 —')
        box.addWidget(self.capacity,0,Qt.AlignmentFlag.AlignLeft)
        self.bar=QProgressBar()
        self.bar.setTextVisible(False)
        box.addWidget(self.bar)
        footer,bottom=history_footer()
        caption=label('显存趋势','eyebrow');set_style(caption,'font-size:11px;color:#5d9aaf')
        bottom.addWidget(caption,1)
        self.history_button=history_button();self.history_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.history_button.clicked.connect(lambda:self.historyRequested.emit(session.id))
        bottom.addWidget(self.history_button);box.addWidget(footer)
        for text in (self.name,self.endpoint,self.summary):
            text.setMinimumWidth(0)
            text.setSizePolicy(QSizePolicy.Policy.Ignored,QSizePolicy.Policy.Preferred)
        self.update_data(session)

    def update_data(self,session,selected=False):
        no_gpu=session.gpu_hint=='no_gpu'
        self.capacity.tone='#7a8c97' if no_gpu else '#63dec1' if session.fresh else '#78a9bd'
        set_style(self.capacity,'font-size:13px;color:'+self.capacity.tone)
        self.gpu_count.setText('无 GPU' if no_gpu else f"显卡 {len(session.snapshot['gpus'])} 张" if session.snapshot else '显卡 — 张')
        self.setProperty('noGpu',no_gpu)
        self.setProperty("selected",selected)
        self.style().unpolish(self)
        self.style().polish(self)
        name=session.profile['name']
        self.name.setText(name[:21]+('…' if len(name)>21 else ''))
        self.name.setToolTip(name)
        endpoint=session.profile['host']
        self.endpoint.setText(endpoint[:29]+('…' if len(endpoint)>29 else ''))
        self.dot.setTone('#8b9ca6' if no_gpu else '#5bdac4' if session.fresh else '#c8a572' if session.desired else '#5c798c')
        if session.snapshot:
            gs=session.snapshot['gpus']
            utils=[g['util'] for g in gs if g['util'] is not None]
            avg=sum(utils)/len(utils) if utils else None
            self.summary.setText(f"{session.state} · {fmt(avg,'%')}" if gs else session.state)
            self.bar.setValue(int(avg or 0))
            self.bar.setVisible(bool(gs))
        else:
            self.summary.setText('已暂停 · 随时可恢复' if not session.profile['autoconnect'] and not session.desired else session.state+' · 等待遥测')
            self.bar.setValue(0)
            self.bar.setVisible(session.desired)
        if session.historical:
            self.summary.setText('历史快照 · '+session.snapshot_time[5:])
        self.setToolTip(session.message)
        counts=session.availability_counts()
        if no_gpu:
            self.capacity.setText('无 GPU · 仅 SSH 连接' if session.fresh else '无 GPU（上次检测）')
            set_style(self.capacity,'font-size:14px;color:#7a8c97')
        elif counts is not None:
            self.capacity.setText(f"空闲 {counts['idle']} · 可用 {counts['available']} / {counts['total']}"+(' · 待确认' if counts['unknown'] else ''))
        else:
            self.capacity.setText('空闲 — · 可用 —')
        self.capacity.setToolTip('可用数量包含空闲卡和连续确认后的轻量占用卡；根据当前资源门槛及设备状态判断。暂停和过期数据不计为可用。')
        self.update()


class StatusIndicator(QWidget):
    def __init__(self,text='尚未连接',diamond_size=8):
        super().__init__()
        self.diamond_size=diamond_size
        self.value=text
        self.tone=QColor('#78a2b4')
        self.setFixedHeight(26)
        self.setText(text)

    def setText(self,text):
        self.value=text.removeprefix('● ')
        self.ensurePolished()
        self.setFixedWidth(self.fontMetrics().horizontalAdvance(self.value)+self.diamond_size+17)
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
        p.setBrush(themed(self.tone))
        path=QPainterPath()
        radius=self.diamond_size/2
        centre=1+radius
        path.moveTo(1,self.height()/2);path.lineTo(centre,self.height()/2-radius);path.lineTo(1+self.diamond_size,self.height()/2);path.lineTo(centre,self.height()/2+radius);path.closeSubpath()
        p.drawPath(path)
        p.setPen(themed(self.tone))
        p.setFont(self.font())
        left=self.diamond_size+9
        p.drawText(QRectF(left,0,self.width()-left,self.height()),Qt.AlignmentFlag.AlignVCenter,self.value)
