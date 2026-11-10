"""GPU perimeter comet and conservative, restart-safe zero-memory timing."""
import math,time
from functools import lru_cache
from PySide6.QtCore import QPointF,QRectF,Qt
from PySide6.QtGui import QPainterPath,QPen,QColor,QRadialGradient,QConicalGradient,QPainter,QImage
from PySide6.QtWidgets import QWidget
from shiboken6 import isValid

# Production gating: only a verified two-hour zero-GPU-utilization streak.
PREVIEW_ALL=False
REQUIRED_SECONDS=2*60*60
GAP_SECONDS=60


class ZeroGpuTracker:
    def __init__(self,interval=2):self.states={};self.gap=max(GAP_SECONDS,float(interval)+3)
    def observe(self,gpus,now):
        ids={g.get('uuid') for g in gpus};self.states={k:v for k,v in self.states.items() if k in ids}
        for gpu in gpus:
            key=gpu.get('uuid')
            if not isinstance(key,str) or not key or key=='N/A':continue
            value=gpu.get('util');old=self.states.get(key)
            valid=isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value) and 0<=value<=100
            if valid and value>0:self.states.pop(key,None)
            elif valid and value==0:
                start=old[0] if old and 0<=now-old[1]<=self.gap else now
                self.states[key]=(start,now)
            elif old and not 0<=now-old[1]<=self.gap:self.states.pop(key,None)
            state=self.states.get(key)
            gpu['gpu_zero_since']=state[0] if state else None
            gpu['gpu_zero_last']=state[1] if state else None
    def restore(self,gpus,now):
        self.states={}
        for gpu in gpus:
            start,last=gpu.get('gpu_zero_since'),gpu.get('gpu_zero_last')
            if (all(isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v) for v in (start,last))
                    and 0<=start<=last<=now and now-last<=self.gap):
                value=gpu.get('util')
                if value is None or value==0:self.states[gpu['uuid']]=(start,last)
    def eligible(self,key,now):
        state=self.states.get(key)
        return bool(state and 0<=now-state[1]<=self.gap and now-state[0]>=REQUIRED_SECONDS)


def active(widget):
    preview=widget.property('_haloPreview')
    return bool((PREVIEW_ALL if preview is None else preview) or widget.property('idleHaloEligible'))


PAD=9


@lru_cache(maxsize=64)
def orbit(width,height):
    # Match the chassis outline; only the soft bloom extends past its border.
    l=t=.7;r=width-.7;b=height-.7;cut=10
    path=QPainterPath(QPointF(l,t));path.lineTo(r-cut,t);path.lineTo(r,t+cut)
    path.lineTo(r,b);path.lineTo(l+cut,b);path.lineTo(l,b-cut);path.closeSubpath()
    return path,path.length()


def paint(p,widget,seed,now=None):
    if not active(widget):return
    # Apply opacity once to the complete glow, so overlapping bloom/core strokes
    # cannot accumulate into an opaque white point.
    dpr=p.device().devicePixelRatioF()
    layer=QImage(round((widget.width()+PAD*2)*dpr),round((widget.height()+PAD*2)*dpr),QImage.Format.Format_ARGB32_Premultiplied)
    layer.setDevicePixelRatio(dpr);layer.fill(0)
    brush=QPainter(layer);brush.translate(PAD,PAD)
    _paint_glow(brush,widget,seed,now);brush.end()
    p.save();p.setOpacity(p.opacity()*.68);p.drawImage(QPointF(-PAD,-PAD),layer);p.restore()


def _paint_glow(p,widget,seed,now=None):
    path,length=orbit(widget.width(),widget.height())
    if length<=0:return
    now=time.monotonic() if now is None else now
    head=((now/8.5)+(seed%37)/37)%1*length
    pos=path.pointAtPercent(path.percentAtLength(head))
    tone=QColor('#70cfff')
    center=QPointF(widget.width()/2,widget.height()/2)
    angle=math.degrees(math.atan2(center.y()-pos.y(),pos.x()-center.x()))
    p.save();p.setRenderHint(QPainter.RenderHint.Antialiasing)
    # One continuous stroke: interpolation is handled by Qt's gradient rasterizer,
    # with no individual line caps or discrete alpha bands along the afterimage.
    for width,alpha in ((10,35),(5,75),(2.6,225)):
        gradient=QConicalGradient(center,angle)
        for stop,strength in ((0,1),(.055,.93),(.16,.64),(.30,.29),(.44,.07),(.52,0),(.9999,0),(1,0)):
            ink=QColor(tone);ink.setAlpha(round(alpha*strength));gradient.setColorAt(stop,ink)
        pen=QPen(gradient,width);pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        p.setPen(pen);p.setBrush(Qt.BrushStyle.NoBrush);p.drawPath(path)
    glow=QRadialGradient(pos,16)
    for stop,alpha in ((0,220),(.20,120),(.5,35),(1,0)):
        ink=QColor(tone);ink.setAlpha(alpha);glow.setColorAt(stop,ink)
    p.fillRect(QRectF(pos.x()-16,pos.y()-16,32,32),glow)
    p.setPen(Qt.PenStyle.NoPen);p.setBrush(tone.lighter(125));p.drawEllipse(pos,3.5,3.5)
    p.setBrush(tone.lighter(160));p.drawEllipse(pos,1.2,1.2)
    p.restore()


class HaloOverlay(QWidget):
    """A mouse-transparent sibling, so the glow can escape the card's clip."""
    def __init__(self,card):
        super().__init__(card.parentWidget());self.card=card
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        card.destroyed.connect(self.deleteLater)
    def paintEvent(self,event):
        card=self.card
        if not isValid(card) or getattr(card.motion,'burst',None):return
        painter=QPainter(self);painter.translate(PAD,PAD)
        paint(painter,card,card.motion.seed)


def sync(widget):
    overlay=getattr(widget,'halo_overlay',None)
    visible=active(widget) and widget.isVisible() and not widget.window().isMinimized()
    visible=visible and not getattr(widget.motion,'burst',None)
    if not visible:
        if overlay is not None and isValid(overlay):overlay.hide()
        return
    if widget.parentWidget() is None:return
    if overlay is None or not isValid(overlay):
        overlay=widget.halo_overlay=HaloOverlay(widget)
    if overlay.parentWidget() is not widget.parentWidget():overlay.setParent(widget.parentWidget())
    geometry=widget.geometry().adjusted(-PAD,-PAD,PAD,PAD)
    if overlay.geometry()!=geometry:overlay.setGeometry(geometry)
    overlay.show();overlay.raise_();overlay.update()
