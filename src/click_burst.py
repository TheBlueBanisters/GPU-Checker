"""Cosmetic over-rev burst. Only a child raster moves; telemetry stays alive."""
import math
import random
from PySide6.QtCore import Qt,QRectF,QPointF,QVariantAnimation,QEasingCurve,QEvent,QPoint
from PySide6.QtGui import QPainter,QColor,QPen,QRadialGradient,QPixmap
from PySide6.QtWidgets import QWidget
from themes import color as themed,is_day
from card_motion import paint_spark_burst,spark_origin
from sound_feedback import play_soft_burst


class ClickBurst(QWidget):
    def __init__(self,card,origin=None):
        # Capture before attaching the overlay, including labels at native DPI.
        # Reassembly reuses this raster: transient click waves must never be baked in.
        card.clear_ripples()
        frame=card.grab()
        super().__init__(card)
        self.frame=frame
        self.seed=card.motion.seed+round(card.motion.phase*10000)
        self.progress=0.
        self.done=False
        self.sound_fired=False
        self.setGeometry(card.rect())
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        card.installEventFilter(self)
        self.animation=QVariantAnimation(self)
        self.animation.setDuration(3400)
        self.animation.setStartValue(0.);self.animation.setEndValue(1.)
        self.animation.setEasingCurve(QEasingCurve.Type.Linear)
        self.animation.valueChanged.connect(self.advance)
        self.animation.finished.connect(self.finish)
        rng=random.Random(self.seed)
        point=QPointF(origin) if origin is not None else QPointF(self.width()/2,self.height()/2)
        self.origin=QPointF(max(0.,min(self.width()-1.,point.x())),
                            max(0.,min(self.height()-1.,point.y())))
        # Sample the panel into sub-pixel grains, not polygonal image fragments.
        image=frame.toImage();ratio=frame.devicePixelRatio()
        spacing=max(5.,math.sqrt(self.width()*self.height()/1400))
        self.dust=[]
        y=spacing/2
        while y<self.height():
            x=spacing/2
            while x<self.width():
                centre=QPointF(x+rng.uniform(-spacing*.45,spacing*.45),
                              y+rng.uniform(-spacing*.45,spacing*.45))
                color=image.pixelColor(min(image.width()-1,max(0,round(centre.x()*ratio))),
                                       min(image.height()-1,max(0,round(centre.y()*ratio))))
                angle=math.atan2(centre.y()-self.origin.y(),centre.x()-self.origin.x())+rng.uniform(-.45,.45)
                speed=rng.uniform(75,240)
                self.dust.append((centre,math.cos(angle)*speed,math.sin(angle)*speed-55,
                                  rng.uniform(.28,.85),rng.uniform(1.05,1.8),rng.uniform(0,math.tau),color))
                x+=spacing
            y+=spacing
        self.embers=tuple((rng.uniform(0,math.tau),rng.uniform(120,430),
                           rng.uniform(.8,2.1),rng.uniform(.6,1.6),rng.uniform(0,.12)) for _ in range(68))
        self.clouds=tuple((rng.uniform(0,math.tau),rng.uniform(12,60),rng.uniform(12,27)) for _ in range(11))

    def begin(self):self.animation.start()

    def advance(self,value):
        self.progress=float(value)
        if not self.done and not self.sound_fired and self.progress*3.4>=.18:
            self.sound_fired=True
            play_soft_burst(self)
        self.update()

    def finish(self):
        if self.done:return
        self.done=True;self.animation.stop()
        card=self.parentWidget()
        card.clear_ripples()
        if card.motion.burst is self:card.motion.burst=None
        card.removeEventFilter(self)
        self.hide();self.frame=QPixmap();self.deleteLater();card.update()

    def eventFilter(self,watched,event):
        if event.type() in (QEvent.Type.Hide,QEvent.Type.Resize,QEvent.Type.Close):self.finish()
        return False

    def draw_dust(self,p,t):
        drag=(1-math.exp(-2.2*t))/2.2
        for index,(start,vx,vy,radius,life,phase,color) in enumerate(self.dust):
            if t>=life:continue
            fade=(1-t/life)**1.15
            point=start+QPointF(vx*drag+math.sin(t*4+phase)*9*t,
                               vy*drag+105*t*t+math.sin(t*3+phase)*4*t)
            # Cool panel-colored dust mixed with a few hot grains, all tiny/soft.
            ink=QColor(color)
            if index%11==0:ink=QColor('#ffcb76' if t<.45 else '#ca854b')
            elif max(ink.red(),ink.green(),ink.blue())<85:
                ink=QColor('#7594a4' if is_day() else '#7b99ab')
            ink.setAlpha(round(210*fade))
            p.setPen(Qt.PenStyle.NoPen);p.setBrush(ink)
            p.drawEllipse(point,radius,radius)
            if index%11==0:
                ink.setAlpha(round(22*fade));p.setBrush(ink)
                p.drawEllipse(point,radius*2.6,radius*2.6)

    def draw_blast(self,p,t):
        if t<0:return
        # Layered low-alpha fire lobes, outward shock rings, then cooling smoke.
        for angle,speed,size in self.clouds:
            life=max(0,min(1,t/1.8));heat=math.exp(-t*3.2)
            centre=self.origin+QPointF(math.cos(angle)*speed*t,math.sin(angle)*speed*t-18*t*t)
            radius=size*(.4+min(t,1)*2.2)
            glow=QRadialGradient(centre,max(1,radius))
            for stop,color,alpha in ((0,'#fff2ba',135*heat),(.26,'#ffb23e',135*heat),
                                     (.58,'#e86424',90*heat),(1,'#cc481a',0)):
                ink=QColor(color);ink.setAlpha(round(alpha));glow.setColorAt(stop,ink)
            p.fillRect(QRectF(centre.x()-radius,centre.y()-radius,2*radius,2*radius),glow)
            if .15<t<1.9:
                smoke=QRadialGradient(centre,radius*1.3)
                ink=QColor('#766952' if is_day() else '#574c40');ink.setAlpha(round(29*math.sin(math.pi*life)))
                smoke.setColorAt(0,ink);ink.setAlpha(0);smoke.setColorAt(1,ink)
                p.fillRect(QRectF(centre.x()-radius*1.3,centre.y()-radius*1.3,2.6*radius,2.6*radius),smoke)
        for delay in (0,.13):
            age=t-delay
            if 0<age<.7:
                radius=10+self.width()*1.5*(1-math.exp(-age*4))
                ink=QColor('#ffd382');ink.setAlpha(round(190*(1-age/.7)**2))
                p.setBrush(Qt.BrushStyle.NoBrush);p.setPen(QPen(ink,max(.7,4*(1-age/.7))))
                p.drawEllipse(self.origin,radius,radius*.8)
        for index,(angle,speed,life,width,birth) in enumerate(self.embers):
            age=t-birth
            if not 0<age<life:continue
            fade=(1-age/life)**1.3
            def at(v):
                drag=(1-math.exp(-2.7*v))/2.7
                return self.origin+QPointF(math.cos(angle)*speed*drag,
                                          math.sin(angle)*speed*drag+115*v*v)
            head=at(age);tail=at(max(0,age-.055-.06*fade))
            color=QColor('#fff1b7' if index%4==0 else '#ffbe50' if age<.7 else '#e77c2e')
            ink=QColor(color);ink.setAlpha(round(35*fade));p.setPen(QPen(ink,width+3));p.drawLine(tail,head)
            ink.setAlpha(round(240*fade));pen=QPen(ink,width);pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            p.setPen(pen);p.drawLine(tail,head)
        # A short white-hot core, not a full-window flash.
        core=math.exp(-((t-.04)/.075)**2)
        glow=QRadialGradient(self.origin,max(1,self.width()*.55))
        for stop,alpha in ((0,245),(.15,190),(.45,75),(1,0)):
            ink=QColor('#fff0be');ink.setAlpha(round(alpha*core));glow.setColorAt(stop,ink)
        p.fillRect(self.rect(),glow)
        paint_spark_burst(p,self.origin,t,self.seed)

    def paintEvent(self,event):
        p=QPainter(self);p.setRenderHint(QPainter.RenderHint.Antialiasing)
        card=self.parentWidget();rect=QRectF(self.rect())
        # Cover the entire old frame, including its antialiased outside edge.
        # Repaint the real dashboard backdrop so there is no rectangular placeholder.
        p.fillRect(rect,themed('#080f1e'))
        backdrop=card.parentWidget()
        while backdrop is not None and not hasattr(backdrop,'paint_backdrop'):
            backdrop=backdrop.parentWidget()
        if backdrop is not None:
            offset=card.mapTo(backdrop,QPoint())
            p.save();p.translate(-offset.x(),-offset.y());backdrop.paint_backdrop(p);p.restore()
        outline=card.panel_path(rect.adjusted(.5,.5,-.5,-.5))
        p.setClipPath(outline)
        t=self.progress*3.4
        if t<.18:
            # Local charge-up tremor; no actual widgets move.
            strength=t/.18
            p.save();p.translate(math.sin(t*155)*3*strength,math.sin(t*213)*2*strength)
            p.drawPixmap(QPointF(),self.frame);p.restore()
            glow=QRadialGradient(self.origin,self.width()*.65)
            ink=QColor('#ffcd68');ink.setAlpha(round(100*strength));glow.setColorAt(0,ink)
            ink.setAlpha(0);glow.setColorAt(1,ink);p.fillRect(rect,glow)
        elif t<2.15:
            age=t-.18
            self.draw_dust(p,age)
            self.draw_blast(p,age)
        else:
            # Signal reacquisition: fade + intermittent horizontal tearing.
            # Every strip is raster-only and clipped inside the original footprint.
            amount=min(1,(t-2.15)/1.25)
            opacity=amount*amount*(3-2*amount)
            envelope=math.sin(math.pi*amount)*(1-amount)
            pulse=max(math.exp(-((amount-c)/.06)**2) for c in (.12,.32,.57,.76))
            strength=envelope*(.25+.75*pulse)
            rng=random.Random(self.seed+int(amount*28))
            y=0
            while y<self.height():
                height=rng.randrange(5,16)
                torn=rng.random()<.36
                offset=(rng.uniform(-30,30)*strength if torn else math.sin(t*91+y)*2.8*strength)
                band=QRectF(0,y,self.width(),height)
                p.save();p.setClipRect(band,Qt.ClipOperation.IntersectClip)
                p.setOpacity(opacity)
                p.drawPixmap(QPointF(offset,0),self.frame)
                if torn and strength>.035:
                    # Thin horizontal afterimages stretch the bright panel detail.
                    for trail in (7,15,25):
                        p.setOpacity(opacity*strength*.25)
                        p.drawPixmap(QPointF(offset+math.copysign(trail*strength,offset or 1),0),self.frame)
                    tint=themed(card.property('feedbackColor') or '#63dec1')
                    tint.setAlpha(round(65*strength))
                    p.setOpacity(1);p.setPen(QPen(tint,.65))
                    x=self.width()*rng.uniform(.1,.6)
                    p.drawLine(QPointF(x,y+height-1),QPointF(min(self.width(),x+self.width()*.3),y+height-1))
                p.restore();y+=height
        p.end()
