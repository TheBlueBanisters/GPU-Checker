"""Low-opacity, local-only engine and fracture artwork for GPU panels."""
import math
import time
import random
from functools import lru_cache
from PySide6.QtCore import QPointF,QRectF,QTimer,QEvent,Qt
from PySide6.QtGui import QColor,QPen,QPainterPath,QRadialGradient,QLinearGradient
from themes import color as themed,is_day


@lru_cache(maxsize=192)
def spark_particles(seed):
    rng=random.Random(seed)
    count=13+rng.randrange(3)
    return tuple((math.tau*(i+rng.uniform(.1,.9))/count,rng.uniform(44,84),
                  rng.uniform(.54,.90),rng.uniform(.55,.9),rng.randrange(3)) for i in range(count))


@lru_cache(maxsize=192)
def molten_drops(seed):
    rng=random.Random(seed+7019)
    return tuple((rng.uniform(.08,.24),rng.uniform(-8,8),rng.uniform(5,12),
                  rng.uniform(1.9,2.5),rng.uniform(.9,1.3),rng.uniform(-3,3)) for _ in range(2))


def spark_origin(rect,seed):
    """A repeatable random source, leaving room for the falling molten tail."""
    rng=random.Random(seed+9181)
    return QPointF(rect.left()+rect.width()*rng.uniform(.18,.82),
                   rect.top()+rect.height()*rng.uniform(.12,.46))


def paint_molten_trails(p,centre,age,seed):
    for birth,vx,vy,life,width,offset in molten_drops(seed):
        t=age-birth
        if not 0<t<life:continue
        fade=min(1,t/.06)*min(1,(life-t)/.65)
        def point(at):
            return centre+QPointF(offset+vx*(1-math.exp(-2*at))/2+math.sin(at*3+offset)*1.2,
                                  vy*at+22*at*at)
        positions=[point(max(0,t-delta)) for delta in (.40,.32,.24,.16,.08,0)]
        cooling=min(1,t/life)
        hot=QColor('#bd831a' if is_day() else '#ffe4a0')
        cool=QColor('#8a4e19' if is_day() else '#c66b24')
        color=QColor(*[round(hot.getRgb()[i]*(1-cooling)+cool.getRgb()[i]*cooling) for i in range(3)])
        trail=QPainterPath(positions[0])
        for position in positions[1:]:trail.lineTo(position)
        halo=QColor(color);halo.setAlpha(round(23*fade));p.setPen(QPen(halo,4));p.drawPath(trail)
        for i,(a,b) in enumerate(zip(positions,positions[1:])):
            ink=QColor(color);ink.setAlpha(round((30+35*i)*fade))
            pen=QPen(ink,width*(.18+.17*i));pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            p.setPen(pen);p.drawLine(a,b)
        ink=QColor(color);ink.setAlpha(round(225*fade));p.setBrush(ink);p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(positions[-1],width*.75,width*1.3)


def paint_spark_burst(p,centre,age,seed):
    """One tiny golden firework: drag, gravity, tapered trails and a fading core."""
    if not 0<=age<2.85:return
    p.save()
    core=math.exp(-age/.045)
    if core>.01:
        glow=QRadialGradient(centre,8)
        for stop,alpha in ((0,160),(.25,75),(1,0)):
            ink=QColor('#b37a19' if is_day() else '#ffe4a0');ink.setAlpha(round(alpha*core));glow.setColorAt(stop,ink)
        p.fillRect(QRectF(centre.x()-8,centre.y()-8,16,16),glow)
    for angle,speed,life,width,tint in spark_particles(seed):
        if age>=life:continue
        fade=(1-age/life)**1.2*min(1,age/.025)
        vx,vy=math.cos(angle)*speed,math.sin(angle)*speed
        def point(t):
            drag=(1-math.exp(-1.8*t))/1.8
            return centre+QPointF(vx*drag,vy*drag+24*t*t)
        positions=[point(max(0,age-offset)) for offset in (.16,.10,.04,0)]
        color=QColor(('#a36c12','#b88218','#8b590b')[tint] if is_day() else ('#ffc44f','#ffd978','#ffe5a7')[tint])
        trail=QPainterPath(positions[0])
        for position in positions[1:]:trail.lineTo(position)
        halo=QColor(color);halo.setAlpha(round(15*fade));p.setPen(QPen(halo,3));p.drawPath(trail)
        for i,(a,b) in enumerate(zip(positions,positions[1:])):
            ink=QColor(color);ink.setAlpha(round((55+65*i)*fade))
            pen=QPen(ink,width*(.45+.25*i));pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            p.setPen(pen);p.drawLine(a,b)
        ink=QColor(color);ink.setAlpha(round(230*fade));p.setPen(Qt.PenStyle.NoPen);p.setBrush(ink)
        p.drawEllipse(positions[-1],.65,.65)
    paint_molten_trails(p,centre,age,seed)
    p.restore()


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
        self.seed=0
        self.stamp=time.monotonic()
        self.transition=self.stamp-3
        self.timer=QTimer(widget)
        self.timer.setInterval(50)
        self.timer.timeout.connect(self.frame)
        self.owner=None
        self.afterglow=None
        self.spark_quiet_until=0.
        self.click_heat=0.
        self.heat_stamp=self.stamp
        self.burst=None

    def cool(self,now):
        self.click_heat=max(0,self.click_heat-max(0,now-self.heat_stamp)*1.8)
        self.heat_stamp=now

    def boost(self):
        if self.state not in ('busy','light','available','idle','unknown') or self.burst is not None:return
        now=time.monotonic()
        self.cool(now)
        self.click_heat+=1
        if self.click_heat>=6:
            from click_burst import ClickBurst
            self.burst=ClickBurst(self.widget)
            self.click_heat=0.
            self.burst.show();self.burst.raise_();self.burst.begin()
        self.sync()

    def continue_sparks(self,age,seed):
        now=time.monotonic()
        self.afterglow=(now-age,seed)
        self.spark_quiet_until=now+max(0,2.85-age)+1.
        self.sync()

    def set_state(self,state):
        if self.state!=state:
            self.state=state
            self.transition=time.monotonic()
            if state in ('paused','blocked','disconnected'):
                self.click_heat=0.
                if self.burst:self.burst.finish()
        self.sync()

    def sync(self):
        w=self.widget
        if self.afterglow and time.monotonic()-self.afterglow[0]>=2.85:self.afterglow=None
        if self.owner is None and w.isVisible():
            self.owner=w.window()
            self.owner.installEventFilter(w)
        moving=self.state in ('busy','light','available','idle','paused') or (
            self.state in ('blocked','disconnected') and time.monotonic()-self.transition<1.6)
        moving=moving or self.afterglow is not None or self.click_heat>0
        interval=20 if self.state=='busy' or self.click_heat>0 else 50
        if self.timer.interval()!=interval: self.timer.setInterval(interval)
        if w.isVisible() and not w.window().isMinimized() and moving:
            if not self.timer.isActive():
                self.stamp=time.monotonic()
                self.timer.start()
        else:
            self.timer.stop()

    def frame(self):
        now=time.monotonic()
        speed={'busy':.7,'light':.24,'available':.16,'idle':.055}.get(self.state,0)
        dt=min(now-self.stamp,.15)
        self.cool(now)
        self.phase=(self.phase+dt*max(speed,.12 if self.click_heat else 0)*(1+self.click_heat*.65))%1
        self.stamp=now
        self.sync()
        self.widget.update()

    def paint(self,p,rect):
        if self.state in ('blocked','disconnected'):
            self.fracture(p,rect)
        elif self.state=='paused':
            self.fracture(p,rect)
            self.electric_sparks(p,rect)
        elif self.state in ('busy','light','available','idle'):
            self.engine(p,rect)
        if self.afterglow:
            p.save();p.setClipPath(self.widget.panel_path(rect))
            paint_spark_burst(p,spark_origin(rect,self.afterglow[1]),
                              time.monotonic()-self.afterglow[0],self.afterglow[1])
            p.restore()

    def engine(self,p,rect):
        busy=self.state=='busy'
        tint=themed('#ed8948' if busy else '#e8ca67' if self.state=='light' else '#65bde9' if self.state=='available' else '#63dec1')
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

    def electric_sparks(self,p,rect):
        start=max(self.transition+(self.seed%19)*.11,self.spark_quiet_until)
        elapsed=time.monotonic()-start
        if elapsed<0 or self.afterglow:return
        period=3.8+(self.seed%5)*.31
        cycle=int(elapsed/period);age=elapsed%period
        if age>=2.85:return
        seed=self.seed+cycle*997
        p.save();p.setClipPath(self.widget.panel_path(rect))
        paint_spark_burst(p,spark_origin(rect,seed),age,seed)
        p.restore()

    def glass_fracture(self,p,rect):
        key=(*rect.getRect(),self.seed)
        if getattr(self,'_glass_key',None)!=key:
            rng=random.Random(self.seed*41+17)
            points=[]
            for i in range(21):
                t=i/20 if i in (0,20) else i/20+rng.uniform(-.011,.011)
                drift=(math.sin(t*9)*.025+rng.uniform(-.012,.012))*math.sin(math.pi*t)
                points.append(QPointF(rect.left()+rect.width()*(.72-.15*t+drift),rect.top()+rect.height()*t))
            paths=[(points,2.)]
            for start,end in ((7,QPointF(rect.right(),rect.top()+rect.height()*.38)),
                              (12,QPointF(rect.left(),rect.top()+rect.height()*.62)),
                              (4,points[4]+QPointF(-rect.width()*.17,-rect.height()*.10)),
                              (16,points[16]+QPointF(rect.width()*.17,rect.height()*.09))):
                origin=points[start];branch=[]
                for i in range(11):
                    t=i/10
                    noise=math.sin(math.pi*t)*rng.uniform(-3,3)
                    branch.append(origin+(end-origin)*t+QPointF(noise,noise*.7))
                paths.append((branch,1.))
            self._glass_key=key;self._glass_paths=paths
        p.save();p.setClipPath(self.widget.panel_path(rect))
        for points,width in self._glass_paths:
            for i,(a,b) in enumerate(zip(points,points[1:])):
                taper=(1-i/max(1,len(points)-1))**.7
                shade=QColor('#587482' if is_day() else '#03070f');shade.setAlpha(round(90+85*taper))
                pen=QPen(shade,max(.22,width*(.18+.82*taper)))
                pen.setCapStyle(Qt.PenCapStyle.RoundCap);p.setPen(pen);p.drawLine(a,b)
                glint=QColor('#adc1cd' if is_day() else '#91a6b1');glint.setAlpha(round(30+55*taper))
                p.setPen(QPen(glint,.45));p.drawLine(a+QPointF(.7,-.2),b+QPointF(.7,-.2))
        p.restore()

    def fracture(self,p,rect):
        if self.state=='paused':
            self.glass_fracture(p,rect)
            return
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
