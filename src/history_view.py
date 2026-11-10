"""Native Qt time-series plots and a nonblocking, read-only history viewer."""
import math,time,threading
from PySide6.QtCore import Qt,QRectF,QPointF,QThread,Signal,QTimer
from PySide6.QtGui import QPainter,QPainterPath,QPen,QColor,QFont
from PySide6.QtWidgets import QWidget,QHBoxLayout,QComboBox,QSpinBox,QPushButton,QLabel,QVBoxLayout,QProgressBar,QSizePolicy
from dialogs import MechDialog,dialog_layout
from themes import color as themed,set_style
from visuals import MechPanel,ModernButton,label
import history_cache

COLORS=('#63dec1','#65bde9')
NAMES=('显存占用量 GiB','显存利用率 %')


class HistoryChart(QWidget):
    readout=Signal(str)
    rangeChanged=Signal(object)
    resetRequested=Signal()
    def __init__(self,indices,parent=None):
        super().__init__(parent);self.indices=indices;self.payload=None;self.hover=None;self.drag_origin=None;self.drag_range=None
        self.setMinimumHeight(155);self.setMinimumWidth(360);self.setMouseTracking(True)

    def mouseMoveEvent(self,event):
        if self.drag_origin is not None and self.payload:
            span=self.drag_range[1]-self.drag_range[0]
            delta=-(event.position().x()-self.drag_origin)/max(1,self.width()-65)*span
            self.change_range(self.drag_range[0]+delta,span);event.accept();return
        self.hover=event.position();self.update()
        if self.payload and self.payload['rows']:
            span=max(1,self.payload['end']-self.payload['start'])
            stamp=self.payload['start']+max(0,min(1,(self.hover.x()-48)/max(1,self.width()-65)))*span
            row=min(self.payload['rows'],key=lambda r:abs(r['t']-stamp))
            names=('显存占用量','显存利用率')
            parts=[names[i]+' '+(f"{row['values'][i]:.1f}"+(' GiB' if i==0 else '%') if row['values'][i] is not None else '—') for i in self.indices]
            self.readout.emit(time.strftime('%m-%d %H:%M:%S',time.localtime(row['t']))+'   ·   '+'   /   '.join(parts))
    def leaveEvent(self,event):self.hover=None;self.readout.emit('');self.update()
    def set_data(self,data):self.payload=data;self.update()

    def change_range(self,start,span):
        bounds=self.payload.get('bounds',(self.payload['start'],self.payload['end']))
        available=max(.001,bounds[1]-bounds[0]);span=max(min(10,available),min(available,span))
        start=max(bounds[0],min(bounds[1]-span,start))
        self.rangeChanged.emit((start,start+span))
    def wheelEvent(self,event):
        if not self.payload:return super().wheelEvent(event)
        steps=event.angleDelta().y()/120
        if not steps:event.ignore();return
        start,end=self.payload['start'],self.payload['end'];span=max(1,end-start)
        ratio=max(0,min(1,(event.position().x()-48)/max(1,self.width()-65)))
        new_span=span*(.8**steps)
        self.change_range(start+span*ratio-new_span*ratio,new_span);event.accept()
    def mousePressEvent(self,event):
        if event.button()==Qt.MouseButton.LeftButton and self.payload:
            self.drag_origin=event.position().x();self.drag_range=(self.payload['start'],self.payload['end'])
            self.setCursor(Qt.CursorShape.ClosedHandCursor);event.accept();return
        super().mousePressEvent(event)
    def mouseReleaseEvent(self,event):
        self.drag_origin=None;self.drag_range=None;self.unsetCursor();event.accept()
    def mouseDoubleClickEvent(self,event):
        self.drag_origin=None;self.drag_range=None;self.unsetCursor();self.resetRequested.emit();event.accept()
    def set_range(self,span):
        if self.payload:self.payload=dict(self.payload,start=span[0],end=span[1]);self.update()

    def paintEvent(self,event):
        p=QPainter(self);p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(),themed('#0b192a'))
        plot=QRectF(48,16,max(1,self.width()-65),max(1,self.height()-48))
        font=QFont(self.font());font.setPixelSize(11);p.setFont(font)
        data=self.payload;rows=data['rows'] if data else []
        top=100. if 0 not in self.indices else max(1.,max((r['max'][0] or 0 for r in rows),default=1)*1.12)
        for tick in range(5):
            y=plot.bottom()-plot.height()*tick/4
            p.setPen(QPen(themed('#2b4b60'),.7));p.drawLine(QPointF(plot.left(),y),QPointF(plot.right(),y))
            p.setPen(themed('#7498b1'));p.drawText(QRectF(1,y-9,42,18),Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignVCenter,f'{top*tick/4:.0f}' if top>=10 else f'{top*tick/4:.1f}')
        if not rows:
            p.setPen(themed('#7498b1'));p.drawText(plot,Qt.AlignmentFlag.AlignCenter,'尚无历史数据，启用监控后开始记录');return
        span=max(1,data['end']-data['start'])
        def point(row,value):return QPointF(plot.left()+(row['t']-data['start'])/span*plot.width(),plot.bottom()-value/top*plot.height())
        p.save();p.setClipRect(plot)
        for i in self.indices:
            color=themed(COLORS[i]);p.setPen(QPen(color,1.5));path=QPainterPath();previous=None
            for row in rows:
                value=row['values'][i]
                if value is None:previous=None;continue
                pos=point(row,value)
                if previous is None or previous['segment']!=row['segment']:path.moveTo(pos)
                else:path.lineTo(pos)
                # Per-bin extrema remain visible even when the line is averaged.
                if row['min'][i]!=row['max'][i]:
                    ink=QColor(color);ink.setAlpha(55);p.setPen(QPen(ink,2))
                    p.drawLine(point(row,row['min'][i]),point(row,row['max'][i]));p.setPen(QPen(color,1.5))
                p.drawEllipse(pos,1.2,1.2);previous=row
            p.drawPath(path)
        if self.hover and plot.contains(self.hover):
            stamp=data['start']+(self.hover.x()-plot.left())/plot.width()*span
            nearest=min(rows,key=lambda r:abs(r['t']-stamp));px=point(nearest,0).x()
            p.setPen(QPen(themed('#7498b1'),1,Qt.PenStyle.DashLine));p.drawLine(QPointF(px,plot.top()),QPointF(px,plot.bottom()))
        p.restore();p.setPen(themed('#7498b1'))
        for tick in range(3):
            stamp=data['start']+span*tick/2;text=time.strftime('%m-%d %H:%M',time.localtime(stamp))
            left=max(0,min(self.width()-92,plot.left()+plot.width()*tick/2-46))
            p.drawText(QRectF(left,plot.bottom()+7,92,18),Qt.AlignmentFlag.AlignCenter,text)



class QueryWorker(QThread):
    ready=Signal(object);failed=Signal(str)
    def __init__(self,root,host,gpu,since,parent,until=None):
        super().__init__(parent);self.args=(root,host,gpu,since,until);self.cancel=threading.Event()
    def run(self):
        try:
            value=history_cache.query(*self.args,cancel=self.cancel)
            if value is not None and not self.cancel.is_set():self.ready.emit(value)
        except Exception as exc:self.failed.emit(str(exc))


class HistoryDialog(MechDialog):
    def __init__(self,parent,profile,gpu=None):
        super().__init__(parent);self.host_id=profile['id'];self.initial_gpu=gpu;self.active_gpu=gpu
        self.root=history_cache.root_path();self.worker=None;self.pending=False;self.stopping=False;self.view_range=None;self.range_bounds=None
        self.setWindowTitle(profile['name']+' · 历史监控');self.resize(990,730)
        self.setProperty('uiDensity',float(parent.property('uiDensity') or 1.))
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        box=dialog_layout(self,scroll_gutter=True);box.setContentsMargins(22,17,22,17);box.setSpacing(12)
        heading=QHBoxLayout();titles=QVBoxLayout();titles.setSpacing(3)
        self.scope_title=label('历史监控','section');titles.addWidget(self.scope_title)
        self.explanation=label(profile['name'],'muted');self.explanation.setWordWrap(True);titles.addWidget(self.explanation)
        heading.addLayout(titles,1)
        status=label('●  自动刷新 / 5 秒','eyebrow');set_style(status,'font-size:11px;color:#63dec1');heading.addWidget(status,0,Qt.AlignmentFlag.AlignTop)
        box.addLayout(heading)
        filters=QHBoxLayout();filters.setSpacing(12)
        self.devices=QComboBox();self.devices.addItem('整台主机（汇总）',None);self.devices.setMinimumWidth(120)
        self.period=QComboBox()
        for name,seconds in (('最近 1 小时',3600),('最近 6 小时',21600),('最近 24 小时',86400),('最近 7 天',604800),('最近 30 天',2592000),('全部缓存',None)):self.period.addItem(name,seconds)
        self.period.setCurrentIndex(1);self.period.setFixedWidth(146)
        for title,widget,stretch in (('查看设备',self.devices,1),('时间范围',self.period,0)):
            group=QVBoxLayout();group.setSpacing(5);group.addWidget(label(title,'eyebrow'));group.addWidget(widget);filters.addLayout(group,stretch)
        refresh=ModernButton('刷新',ghost=True);refresh.setProperty('fixedAction',True);refresh.setFixedSize(80,36)
        filters.addWidget(refresh,0,Qt.AlignmentFlag.AlignBottom)
        reset=ModernButton('复位',ghost=True);reset.setProperty('fixedAction',True);reset.setFixedSize(78,36);reset.clicked.connect(self.reset_range)
        filters.addWidget(reset,0,Qt.AlignmentFlag.AlignBottom);box.addLayout(filters)
        self.memory=HistoryChart((0,));self.percent=HistoryChart((1,))
        for chart in (self.memory,self.percent):
            chart.rangeChanged.connect(self.zoom_range);chart.resetRequested.connect(self.reset_range)
        self.last_memory=label('—','stat');self.last_memory.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.last_stamp=label('—','stat');self.last_stamp.setAlignment(Qt.AlignmentFlag.AlignRight)
        for chart,title,metric in ((self.memory,'显存占用量',self.last_memory),(self.percent,'显存利用率',self.last_stamp)):
            panel=MechPanel();panel.setObjectName('glass');panel.setProperty('squarePanel',True);layout=QVBoxLayout(panel);layout.setContentsMargins(14,10,14,9);layout.setSpacing(4)
            row=QHBoxLayout();name=label(title);set_style(name,'font-size:16px;color:#bdd5e9');row.addWidget(name,1);row.addWidget(metric)
            layout.addLayout(row)
            layout.addWidget(chart)
            readout=label('滚轮缩放 · 拖动平移 · 双击复位','eyebrow');readout.setMinimumHeight(16)
            chart.readout.connect(lambda text,view=readout:view.setText(text or '滚轮缩放 · 拖动平移 · 双击复位'))
            layout.addWidget(readout);box.addWidget(panel)
        footer=QHBoxLayout();footer.setSpacing(12)
        footer.addWidget(label('本地缓存','eyebrow'))
        self.cache_meter=QProgressBar();self.cache_meter.setRange(0,1000);self.cache_meter.setTextVisible(False);self.cache_meter.setFixedSize(100,4)
        footer.addWidget(self.cache_meter)
        self.status=label('读取中…','muted');footer.addWidget(self.status,1)
        self.details_toggle=ModernButton('缓存与说明',ghost=True);self.details_toggle.setProperty('fixedAction',True);self.details_toggle.setFixedSize(110,32);self.details_toggle.setCheckable(True)
        footer.addWidget(self.details_toggle);box.addLayout(footer)
        self.details_panel=MechPanel();self.details_panel.setObjectName('glass');self.details_panel.setProperty('squarePanel',True)
        details=QVBoxLayout(self.details_panel);details.setContentsMargins(16,13,16,13);details.setSpacing(10)
        quota=QHBoxLayout();quota.addWidget(label('全局缓存上限'))
        self.quota=QSpinBox();self.quota.setRange(32,1000);self.quota.setSuffix(' MB');self.quota.setValue(history_cache.limit(self.root)//1_000_000)
        self.quota.setFixedWidth(126);quota.addWidget(self.quota)
        apply=ModernButton('保存上限',primary=True);apply.setProperty('fixedAction',True);apply.setFixedSize(110,34)
        quota.addWidget(apply);quota.addStretch();details.addLayout(quota)
        note=label('所有主机共用缓存，最多 1 GB；接近上限时清理最老数据，不删除主机配置与快照。\n\n显存利用率为驱动报告的显存读写时间比例，缺失时留空。主机占用量相加，利用率取各卡平均。\n长范围曲线使用分桶均值，细竖线保留最小 / 最大值；暂停、断线和重启均保留空档。','muted')
        note.setWordWrap(True);details.addWidget(note);box.addWidget(self.details_panel)
        self.details_panel.hide();self.details_toggle.toggled.connect(self.details_panel.setVisible)
        self.message=label('','muted');self.message.setWordWrap(True);self.message.hide();box.addWidget(self.message)
        self.devices.currentIndexChanged.connect(self.device_changed);self.period.currentIndexChanged.connect(self.reset_range)
        refresh.clicked.connect(self.refresh);apply.clicked.connect(self.apply_limit)
        self.timer=QTimer(self);self.timer.setInterval(5000);self.timer.timeout.connect(self.refresh);self.timer.start()
        QTimer.singleShot(0,self,self.refresh)

    def device_changed(self):self.active_gpu=self.devices.currentData();self.refresh()
    def zoom_range(self,span):
        self.view_range=span
        for chart in (self.memory,self.percent):chart.set_range(span)
        self.refresh()
    def reset_range(self,*args):self.view_range=None;self.range_bounds=None;self.refresh()
    def apply_limit(self):
        try:history_cache.set_limit(self.root,self.quota.value()*1_000_000);self.status.setText('上限已保存，正在清理最老历史…');self.refresh()
        except Exception as exc:self.status.setText('无法设置历史缓存：'+str(exc))
    def refresh(self,*args):
        if self.stopping:return
        if self.worker is not None:self.pending=True;return
        seconds=self.period.currentData();since=time.time()-seconds if seconds else None
        until=None
        if self.view_range:since,until=self.view_range
        self.worker=QueryWorker(self.root,self.host_id,self.active_gpu,since,self,until=until)
        request=(self.active_gpu,self.period.currentData(),self.view_range)
        self.worker.ready.connect(lambda data,r=request:self.loaded(data,r));self.worker.failed.connect(lambda message:self.status.setText('历史读取失败：'+message))
        worker=self.worker;worker.finished.connect(lambda w=worker:self.finished_query(w));worker.start()
    def finished_query(self,worker):
        worker.deleteLater()
        if self.worker is worker:self.worker=None
        if self.pending and not self.stopping:self.pending=False;self.refresh()
    def loaded(self,data,request=None):
        if self.stopping or (request is not None and request!=(self.active_gpu,self.period.currentData(),self.view_range)):return
        self.devices.blockSignals(True);self.devices.clear();self.devices.addItem('整台主机（汇总）',None)
        for device in data['devices']:self.devices.addItem(f"GPU {device['index'] if device['index'] is not None else '—'} · {device['name']}",device['uuid'])
        index=self.devices.findData(self.active_gpu)
        if index<0 and self.active_gpu:self.devices.addItem('所选 GPU · 暂无历史',self.active_gpu);index=self.devices.count()-1
        self.devices.setCurrentIndex(max(0,index));self.devices.blockSignals(False)
        if self.view_range is None:self.range_bounds=(data['start'],data['end'])
        data['bounds']=self.range_bounds or (data['start'],data['end'])
        self.memory.set_data(data);self.percent.set_data(data)
        self.scope_title.setText('主机历史' if self.active_gpu is None else 'GPU 历史')
        description='主机汇总 · 显存占用量求和 / 显存利用率取平均' if self.active_gpu is None else self.devices.currentText()
        self.explanation.setText(description)
        latest=data['rows'][-1] if data['rows'] else None
        value=latest['values'][0] if latest else None
        self.last_memory.setText(f'{value:.1f} GiB' if value is not None else '—')
        util=latest['values'][1] if latest else None
        self.last_stamp.setText(f'{util:.1f}%' if util is not None else '—')
        self.cache_meter.setValue(round(min(1,data['usage']/max(1,data['limit']))*1000))
        self.status.setText(f"{data['usage']/1_000_000:.1f} / {data['limit']/1_000_000:.0f} MB")
        message=data['error'] or ('部分数据片段暂不可读，已跳过。' if data['damaged'] else '')
        self.message.setText(message);self.message.setVisible(bool(message))

    def closeEvent(self,event):
        self.stopping=True;self.timer.stop()
        if self.worker and self.worker.isRunning():
            self.worker.cancel.set()
            if not self.worker.wait(2000):event.ignore();QTimer.singleShot(100,self,self.close);return
        super().closeEvent(event)
