"""Low-opacity, local-only engine and fracture artwork for GPU panels."""
import math
import time
from PySide6.QtCore import QPointF,QRectF,QTimer,QEvent,Qt
from PySide6.QtGui import QColor,QPen,QPainterPath,QRadialGradient,QLinearGradient
from themes import color as themed,is_day


def cylinder_state(phase,index):
    # phase is a full 720-degree four-stroke cycle, firing order 1-3-4-2.
    angle=(phase*4*math.pi+(0,math.pi,3*math.pi,2*math.pi)[index])%(4*math.pi)
    crank_x=8*math.sin(angle)
    crank_y=94-8*math.cos(angle)  # angle 0 = top dead centre
    piston_y=crank_y-math.sqrt(49**2-crank_x**2)
    relative=angle-4*math.pi if angle>3*math.pi else angle
    def smooth(x):
        x=max(0,min(1,x))
        return x*x*(3-2*x)
    # Ignition begins just before compression TDC; fades on the power downstroke.
    burn=smooth((relative+.22)/.32)*(1-smooth((relative-.10)/.95))
    return crank_x,crank_y,piston_y,burn


def combustion_stages(phase,index):
    angle=(phase*4*math.pi+(0,math.pi,3*math.pi,2*math.pi)[index])%(4*math.pi)
    relative=angle-4*math.pi if angle>3*math.pi else angle
    spark=math.exp(-((relative+.12)/.09)**2) if -.4<relative<.12 else 0
    burn=cylinder_state(phase,index)[3]
    afterglow=(math.sin(math.pi*(relative-.25)/2)**2*.28 if .25<relative<2.25 else 0)
    front=max(0,min(1,(relative+.22)/1.27))
    return spark,max(burn,afterglow),front


class CardMotion:
    def __init__(self,widget):
        self.widget=widget
        self.state='unknown'
        self.phase=0.
        self.stamp=time.monotonic()
        self.transition=self.stamp-3
        self.timer=QTimer(widget)
        self.timer.setInterval(50)
        self.timer.timeout.connect(self.frame)
        self.owner=None

    def set_state(self,state):
        if self.state!=state:
            self.state=state
            self.transition=time.monotonic()
        self.sync()

    def sync(self):
        w=self.widget
        if self.owner is None and w.isVisible():
            self.owner=w.window()
            self.owner.installEventFilter(w)
        moving=self.state in ('busy','available','idle') or (
            self.state in ('blocked','disconnected') and time.monotonic()-self.transition<1.6)
        interval=20 if self.state=='busy' else 50
        if self.timer.interval()!=interval: self.timer.setInterval(interval)
        if w.isVisible() and not w.window().isMinimized() and moving:
            if not self.timer.isActive():
                self.stamp=time.monotonic()
                self.timer.start()
        else:
            self.timer.stop()

    def frame(self):
        now=time.monotonic()
        speed={'busy':.7,'available':.16,'idle':.055}.get(self.state,0)
        self.phase=(self.phase+min(now-self.stamp,.15)*speed)%1
        self.stamp=now
        self.sync()
        self.widget.update()

    def paint(self,p,rect):
        if self.state in ('blocked','disconnected'):
            self.fracture(p,rect)
        elif self.state in ('busy','available','idle'):
            self.engine(p,rect)

    def engine(self,p,rect):
        busy=self.state=='busy'
        tint=themed('#d9a86c' if busy else '#65bde9' if self.state=='available' else '#63dec1')
        p.save()
        p.setClipPath(self.widget.panel_path(rect))
        # A quiet four-cylinder bank: real slider-crank geometry, staggered firing.
        p.translate(rect.width()*.48,rect.height()*.23)
        scale=min(rect.width()*.48/136,rect.height()*.58/132)
        p.scale(scale,scale)
        tint.setAlpha(60 if busy else 27)
        p.setPen(QPen(tint,1.1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(QRectF(0,4,136,74),5,5)
        p.drawLine(QPointF(0,90),QPointF(136,90))
        for i in range(4):
            x=17+i*34
            crank_x,crank_y,piston_y,burn=cylinder_state(self.phase,i)
            crank=QPointF(x+crank_x,crank_y)
            p.drawRoundedRect(QRectF(x-10,10,20,62),2,2)
            p.drawLine(QPointF(x-7,7),QPointF(x-7,0))
            p.drawLine(QPointF(x+7,7),QPointF(x+7,0))
            # Spark -> expanding flame front -> warm residual gas, all clipped
            # above the moving piston crown. No one-frame explosion or flat flash.
            spark,heat,front=combustion_stages(self.phase,i) if busy else (0,0,0)
            p.save()
            chamber=QRectF(x-8.4,11,16.8,max(1,piston_y-15))
            p.setClipRect(chamber,Qt.ClipOperation.IntersectClip)
            hot=QColor('#a95a1d' if is_day() else '#ffc278')
            orange=QColor('#b46b20' if is_day() else '#eb8b42')
            core=QColor('#8d4915' if is_day() else '#fff0c0')
            if heat>.001:
                gas=QLinearGradient(x,12,x,piston_y-4)
                cap=QColor(orange);cap.setAlpha(round(heat*40))
                gas.setColorAt(0,cap)
                cap.setAlpha(round(heat*13));gas.setColorAt(1,cap)
                p.fillRect(chamber,gas)
                centre=QPointF(x,17+chamber.height()*.48*front)
                flame=QRadialGradient(centre,3+21*front)
                for stop,color,alpha in ((0,core,95),(.27,hot,85),(.62,orange,43),(1,orange,0)):
                    ink=QColor(color);ink.setAlpha(round(alpha*heat));flame.setColorAt(stop,ink)
                p.fillRect(chamber,flame)
                # Curved flame filaments travel down with expansion, then fade.
                filament=QColor(hot);filament.setAlpha(round(heat*65*(1-front*.65)))
                p.setPen(QPen(filament,.7));p.setBrush(Qt.BrushStyle.NoBrush)
                for lane in (-1,0,1):
                    y=min(piston_y-5,17+front*chamber.height()*.82)
                    curve=QPainterPath(QPointF(x+lane*1.8,16))
                    curve.cubicTo(x+lane*5,19+front*7,x+lane*6.4,y-6,x+lane*3.8,y)
                    p.drawPath(curve)
            if spark>.005:
                flash=QRadialGradient(QPointF(x,15),4.5)
                ink=QColor(core);ink.setAlpha(round(150*spark));flash.setColorAt(0,ink)
                ink.setAlpha(0);flash.setColorAt(1,ink);p.fillRect(chamber,flash)
                ink=QColor(core);ink.setAlpha(round(200*spark));p.setPen(QPen(ink,.8))
                bolt=QPainterPath(QPointF(x-1.8,12));bolt.lineTo(x+.9,14);bolt.lineTo(x-.8,15.4);bolt.lineTo(x+1.6,17.2);p.drawPath(bolt)
            p.restore()
            # Small spark-plug silhouette stays visible between firing events.
            p.setPen(QPen(tint,.9));p.drawLine(QPointF(x,5),QPointF(x,13))
            p.drawLine(QPointF(x-2,8),QPointF(x+2,8))
            piston=QColor(tint);piston.setAlpha(40 if busy else 15)
            p.setBrush(piston)
            p.drawRoundedRect(QRectF(x-9,piston_y-4,18,8),1,1)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawLine(QPointF(x-8,piston_y-1),QPointF(x+8,piston_y-1))
            if heat>.01:
                rim=QColor(hot);rim.setAlpha(round(heat*72));p.setPen(QPen(rim,1.1))
                p.drawLine(QPointF(x-8,piston_y-4),QPointF(x+8,piston_y-4))
                p.setPen(QPen(tint,1.1))
            p.drawLine(QPointF(x,piston_y+4),crank)
            p.drawEllipse(QPointF(x,94),10,10)
            p.drawEllipse(crank,2,2)
        p.drawLine(QPointF(5,114),QPointF(131,114))
        p.restore()

    def fracture(self,p,rect):
        p.save()
        p.setClipPath(self.widget.panel_path(rect))
        progress=min(1,max(0,(time.monotonic()-self.transition)/1.6))
        eased=progress*progress*(3-2*progress)
        # Fixed geometry, no random flicker; opens once and remains fractured.
        points=[(.66,0),(.59,.19),(.69,.34),(.55,.52),(.62,.71),(.53,1)]
        p.setOpacity(.45+.55*eased)
        gap=1.5+3*eased
        # Subtle displaced facets make a broken panel, while keeping telemetry legible.
        for polygon,dx,dy in (([(.69,.34),(.88,.27),(1,.31),(1,.7),(.62,.71),(.55,.52)],4,-2),
                              ([(.62,.71),(.81,.78),(.86,1),(.53,1)],-3,4)):
            facet=QPainterPath()
            for i,(x,y) in enumerate(polygon):
                pt=QPointF(rect.width()*x+dx*eased,rect.height()*y+dy*eased)
                facet.moveTo(pt) if i==0 else facet.lineTo(pt)
            facet.closeSubpath()
            fill=themed('#8398a7');fill.setAlpha(10)
            p.fillPath(facet,fill)

        for offset in (-gap,gap):
            path=QPainterPath()
            for i,(x,y) in enumerate(points):
                pt=QPointF(rect.width()*x+offset,rect.height()*y)
                path.moveTo(pt) if i==0 else path.lineTo(pt)
            ink=themed('#718492',day='#8398a7');ink.setAlpha(70)
            p.setPen(QPen(ink,1));p.drawPath(path)
        ink=themed('#8398a7');ink.setAlpha(45)
        p.setPen(QPen(ink,1))
        for a,b,c in (((.69,.34),(.88,.27),(1,.31)),((.55,.52),(.35,.57),(.28,.71)),((.62,.71),(.81,.78),(.86,1))):
            path=QPainterPath();path.moveTo(rect.width()*a[0],rect.height()*a[1]);path.lineTo(rect.width()*b[0],rect.height()*b[1]);path.lineTo(rect.width()*c[0],rect.height()*c[1]);p.drawPath(path)
        p.restore()
