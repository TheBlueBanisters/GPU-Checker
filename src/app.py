from themes import set_style
import themes
from host_list import HostList
import json
from pathlib import Path
import sys
import tempfile
import time
import uuid
from PySide6.QtCore import Qt, QTimer, QSize,QEvent,QObject
from PySide6.QtGui import QColor, QIcon, QPalette,QFontDatabase,QFont
from PySide6.QtWidgets import (QApplication,QMainWindow,QWidget,QFrame,QLabel,QHBoxLayout,QVBoxLayout,
    QPushButton,QLineEdit,QListWidget,QListWidgetItem,QScrollArea,QTableWidget,QTableWidgetItem,
    QHeaderView,QTextEdit,QSplitter,QFileDialog,QMessageBox,QDialog,QSizePolicy,QToolTip)
from backend import DATA, config_path
from sessions import HostSession
from dialogs import HostDialog,ConfigDialog
from visuals import STYLE,Backdrop,GPUCard,HostTile,ModernButton,StatusIndicator,MechPanel,label,fmt
import profiles
import vault
from process_table import ProcessHeader,ProcessCells,ProcessTable,ALIGNMENTS
from availability import Rules,Tracker,COLORS,LABELS
from dialogs import AvailabilityDialog
from window_chrome import TitleBar,install_handles,layout_handles

ASSETS=Path(getattr(sys,'_MEIPASS',Path(__file__).parent.parent))/'assets'


class NoHoverPopups(QObject):
    def eventFilter(self,watched,event):
        if event.type()==QEvent.Type.ToolTip:
            QToolTip.hideText()
            return True
        return False


class Window(QMainWindow):
    def toggle_theme(self):
        mode='night' if themes.is_day() else 'day'
        themes.apply(QApplication.instance(),mode,STYLE)
        DATA.mkdir(parents=True,exist_ok=True)
        path=DATA/'ui_preferences.json'
        temporary=path.with_suffix('.tmp')
        temporary.write_text(json.dumps({'theme':mode}),encoding='utf-8')
        temporary.replace(path)

    def __init__(self,autostart=True,session_factory=HostSession):
        super().__init__()
        self.setWindowTitle('GPU Checker · 多主机算力监控')
        self.setWindowIcon(QIcon(str(ASSETS/'app.ico')))
        self.setWindowFlags(Qt.WindowType.Window|Qt.WindowType.FramelessWindowHint|Qt.WindowType.WindowMinMaxButtonsHint|Qt.WindowType.WindowCloseButtonHint|Qt.WindowType.WindowSystemMenuHint)
        self.resize_handles=[]
        self.resize(1480,1000)
        self.setMinimumSize(1080,760)
        self.session_factory=session_factory
        try:
            self.availability_rules=Rules(**json.loads((DATA/'availability_rules.json').read_text(encoding='utf-8')))
        except Exception:
            self.availability_rules=Rules()
        try:
            self.inventory_hints=json.loads((DATA/'inventory_hints.json').read_text(encoding='utf-8'))
            self.inventory_hints={str(k):v for k,v in self.inventory_hints.items() if v in ('available','no_gpu','unavailable')}
        except Exception:
            self.inventory_hints={}
        self.sessions={}
        self.retired=[]
        self.tiles={}
        self.cards={}
        self.selected_id=None
        self.current=[]
        self.visible_processes=[]
        self.closing=False
        self.trust_queue=[]
        self.trust_busy=False
        self.load_error=''
        self.items=[]
        try:
            self.items=profiles.load()
            seen=set()
            for p in self.items:
                if p['id'] in seen:
                    p['id']=uuid.uuid4().hex
                seen.add(p['id'])
            self.items=profiles.save(self.items)
        except Exception as exc:
            self.load_error=f'读取或保存配置失败：{exc}'
        self.profile_stamp=self.profiles_stamp()
        self.automatic_start=autostart
        central=Backdrop()
        shell=QWidget()
        shell.setObjectName('shell')
        set_style(shell,'QWidget#shell {background:#0b1424;border:1px solid #263a50;}')
        self.setCentralWidget(shell)
        outer=QVBoxLayout(shell)
        outer.setContentsMargins(1,1,1,1)
        outer.setSpacing(0)
        self.title_bar=TitleBar(self)
        outer.addWidget(self.title_bar)
        outer.addWidget(central,1)
        root=QHBoxLayout(central)
        root.setContentsMargins(0,0,0,0)
        root.setSpacing(0)
        side=QFrame()
        side.setObjectName('sidebar')
        side.setFixedWidth(282)
        sb=QVBoxLayout(side)
        sb.setContentsMargins(18,25,18,19)
        sb.setSpacing(13)
        brand=QHBoxLayout()
        icon=QLabel()
        icon.setPixmap(QIcon(str(ASSETS/'app.ico')).pixmap(QSize(36,36)))
        brand.addWidget(label('HOST DIRECTORY','brand'))
        brand.addStretch()
        sb.addLayout(brand)
        sb.addWidget(label('MULTI-HOST / SECURE SHELL','eyebrow'))
        sb.addSpacing(18)
        row=QHBoxLayout()
        row.addWidget(label('主机舰队','section'))
        self.host_count=label('00','eyebrow')
        row.addStretch()
        row.addWidget(self.host_count)
        sb.addLayout(row)
        self.host_search=QLineEdit()
        self.host_search.setPlaceholderText('搜索主机…')
        self.host_search.textChanged.connect(self.filter_hosts)
        sb.addWidget(self.host_search)
        self.host_list=HostList()
        self.host_list.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.host_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.host_list.currentRowChanged.connect(self.select_row)
        sb.addWidget(self.host_list,1)
        self.fleet_hint=label('滚动查看全部主机 · 暂停仍保留','eyebrow')
        sb.addWidget(self.fleet_hint)
        sb.addWidget(self.button('+ 添加主机',self.add_host,True))
        sb.addWidget(self.button('导入 SSH config',self.import_ssh))
        sb.addWidget(self.button('粘贴 / 编辑 config',self.edit_config))
        row=QHBoxLayout()
        row.addWidget(self.button('全部连接',self.connect_all))
        row.addWidget(self.button('全部暂停',self.pause_all))
        sb.addLayout(row)
        row=QHBoxLayout()
        row.addWidget(self.button('迁移配置',self.export_bundle))
        row.addWidget(self.button('使用说明',self.help))
        sb.addLayout(row)
        sb.addWidget(label('READ ONLY  ·  无远端常驻服务','eyebrow'))
        root.addWidget(side)
        content=QVBoxLayout()
        content.setContentsMargins(27,22,27,19)
        content.setSpacing(11)
        self.fleet=self.title_bar.fleet_label
        self.clock=self.title_bar.clock_label
        hero=MechPanel()
        hero.setObjectName('glass')
        hb=QVBoxLayout(hero)
        hb.setContentsMargins(22,15,22,15)
        header=QHBoxLayout()
        titles=QVBoxLayout()
        self.heading=label('选择一台主机','heading')
        self.subtitle=label('所有已连接主机在后台独立采集，点击列表切换查看。','muted')
        self.subtitle.setWordWrap(True)
        titles.addWidget(self.heading)
        titles.addWidget(self.subtitle)
        header.addLayout(titles,1)
        self.badge=StatusIndicator()
        header.addWidget(self.badge)
        hb.addLayout(header)
        actions=QHBoxLayout()
        self.telemetry=label('SECURE SHELL  /  LIVE TELEMETRY','eyebrow')
        self.telemetry.setMinimumWidth(0)
        self.telemetry.setSizePolicy(QSizePolicy.Policy.Ignored,QSizePolicy.Policy.Preferred)
        actions.addWidget(self.telemetry)
        actions.addStretch()
        self.connect_button=self.button('连接主机',self.toggle_selected,True)
        self.edit_button=self.button('编辑',self.edit_host)
        self.remove_button=self.button('移除',self.remove_host)
        for button in (self.connect_button,self.edit_button,self.remove_button):
            button.ghost=False
            button.setProperty('fixedAction',True)
            button.setFixedSize(140,42)
            actions.addWidget(button)
        actions.setSpacing(12)
        hb.addLayout(actions)
        content.addWidget(hero)
        metrics=QHBoxLayout()
        self.stats=[]
        for title in ('显卡数量','平均 GPU 利用率','显存占用 / 总量','用卡进程'):
            frame=MechPanel()
            frame.setObjectName('glass')
            box=QVBoxLayout(frame)
            box.setContentsMargins(17,12,17,12)
            box.addWidget(label(title,'muted'))
            value=label('—','stat')
            box.addWidget(value)
            self.stats.append(value)
            frame.enable_feedback()
            metrics.addWidget(frame,1)
        content.addLayout(metrics)
        row=QHBoxLayout()
        row.addWidget(label('GPU 遥测','section'))
        row.addStretch()
        self.availability_legend=QWidget()
        legend=QHBoxLayout(self.availability_legend)
        legend.setContentsMargins(0,0,0,0)
        legend.setSpacing(12)
        for state in ('idle','available','busy','blocked','unknown'):
            entry=label('◆ '+LABELS[state])
            set_style(entry,f'font-size:13px;color:{COLORS[state]}')
            legend.addWidget(entry)
        self.availability_legend.setToolTip('绿：空闲；蓝：可用；琥珀：占用；灰：不可用／断连／未知，按文字区分。可用包含空闲。')
        row.addWidget(self.availability_legend)
        row.addWidget(self.button('判定规则',self.edit_availability_rules))
        content.addLayout(row)
        self.card_scroll=QScrollArea()
        self.card_scroll.setWidgetResizable(True)
        self.card_scroll.setFixedHeight(242)
        self.card_widget=QWidget()
        self.card_layout=QHBoxLayout(self.card_widget)
        self.card_layout.setContentsMargins(0,0,0,5)
        self.card_layout.setSpacing(12)
        self.empty=label('等待加密遥测链路建立…','muted')
        self.card_layout.addWidget(self.empty)
        self.card_layout.addStretch()
        self.card_scroll.setWidget(self.card_widget)
        content.addWidget(self.card_scroll)
        row=QHBoxLayout()
        self.process_title=label('用卡进程','section')
        row.addWidget(self.process_title)
        self.process_count=label('00','count')
        self.process_count.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.process_count.setFixedSize(52,30)
        row.addSpacing(8)
        row.addWidget(self.process_count)
        row.addStretch()
        self.search=QLineEdit()
        self.search.setPlaceholderText('筛选用户、PID、进程或目录…')
        self.search.setMaximumWidth(310)
        self.search.textChanged.connect(self.render_processes)
        row.addWidget(self.search)
        content.addLayout(row)
        self.table=ProcessTable(0,8)
        self.table.setHorizontalHeaderLabels(['GPU','PID','用户','类型','显存 MiB','进程','当前工作目录','父 PID'])
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.verticalHeader().hide()
        self.table.verticalHeader().setDefaultSectionSize(44)
        self.table.setWordWrap(False)
        self.table.setShowGrid(False)
        self.table.setHorizontalHeader(ProcessHeader(self.table))
        self.table.setItemDelegate(ProcessCells(self.table))
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        for i,width in enumerate((70,120,130,80,140,165,260,130)):
            self.table.setColumnWidth(i,width)
            self.table.horizontalHeaderItem(i).setTextAlignment(ALIGNMENTS[i])
        self.table.horizontalHeader().setSectionResizeMode(6,QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setStretchLastSection(False)
        self.table.setHorizontalScrollMode(QTableWidget.ScrollMode.ScrollPerPixel)
        self.table.itemSelectionChanged.connect(self.show_details)
        self.details=QTextEdit()
        self.details.setReadOnly(True)
        self.details.setMinimumHeight(93)
        self.details.setPlainText('选择进程，查看完整工作目录与身份信息。只读查询遵循服务器权限。')
        splitter=QSplitter(Qt.Orientation.Vertical)
        splitter.addWidget(self.table)
        splitter.addWidget(self.details)
        splitter.setSizes([230,105])
        content.addWidget(splitter,1)
        self.status_text=label(self.load_error or '就绪 · 主机切换仅改变当前视图，不影响其他监控会话。','muted')
        self.status_text.setWordWrap(True)
        self.status_text.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        content.addWidget(self.status_text)
        root.addLayout(content,1)
        for profile in self.items:
            self.register(profile)
        self.rebuild_list()
        self.timer=QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(1000)
        self.resize_handles=install_handles(self)
        layout_handles(self)
        self.tick()
        if self.load_error:
            QTimer.singleShot(100,lambda: self.notify('配置读取提示',self.load_error))
        if autostart:
            QTimer.singleShot(350,self.autostart)

    def button(self,text,fn,primary=False):
        button=ModernButton(text,primary,ghost=text in ('导入 SSH config','粘贴 / 编辑 config','迁移配置','使用说明','编辑','移除'))
        if primary:
            button.setObjectName('primary')
        button.clicked.connect(fn)
        return button

    def notify(self,title,message):
        QMessageBox.information(self,title,message)

    def register(self,p):
        session=self.session_factory(p,self)
        session.availability_tracker=Tracker(self.availability_rules)
        session.gpu_hint=self.inventory_hints.get(session.id)
        self.sessions[session.id]=session
        session.changed.connect(self.host_changed)
        session.sampled.connect(self.host_sampled)
        session.trust.connect(self.queue_trust)
        session.stopped.connect(self.session_stopped)
        return session

    @property
    def selected(self):
        return self.sessions.get(self.selected_id)

    def rebuild_list(self,selected=None):
        selected=selected or self.selected_id
        self.host_list.blockSignals(True)
        self.host_list.clear()
        self.tiles={}
        select=0
        for index,p in enumerate(self.items):
            item=QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole,p['id'])
            item.setSizeHint(QSize(230,134))
            self.host_list.addItem(item)
            tile=HostTile(self.sessions[p['id']],index)
            self.host_list.setItemWidget(item,tile)
            self.tiles[p['id']]=tile
            if p['id']==selected:
                select=index
        self.host_list.setCurrentRow(select if self.items else -1)
        self.host_list.blockSignals(False)
        self.select_row(self.host_list.currentRow())
        self.filter_hosts()
        self.host_count.setText(f'{len(self.items):02d}')
        self.write_runtime_state()

    def filter_hosts(self):
        needle=self.host_search.text().strip().lower()
        for i,p in enumerate(self.items):
            self.host_list.item(i).setHidden(needle not in (p['name']+' '+p['host']).lower())

    def select_row(self,row):
        item=self.host_list.item(row)
        sid=item.data(Qt.ItemDataRole.UserRole) if item else None
        changed=sid!=self.selected_id
        self.selected_id=sid
        if changed:
            self.search.blockSignals(True)
            self.search.clear()
            self.search.blockSignals(False)
            self.clear_cards()
            self.table.setRowCount(0)
            self.details.setPlainText('选择此主机的进程，查看完整路径和身份。')
        for key,tile in self.tiles.items():
            tile.update_data(self.sessions[key],key==sid)
        self.render_selected()

    def clear_cards(self):
        for card in self.cards.values():
            self.card_layout.removeWidget(card)
            card.hide()
            card.deleteLater()
        self.cards={}

    def host_changed(self,sid):
        if sid in self.tiles and sid in self.sessions:
            self.tiles[sid].update_data(self.sessions[sid],sid==self.selected_id)
        self.update_fleet()
        if sid==self.selected_id:
            self.render_status()
            self.update_availability_badges()

    def host_sampled(self,sid):
        session=self.sessions.get(sid)
        if session and session.gpu_hint in ('available','no_gpu','unavailable') and self.inventory_hints.get(sid)!=session.gpu_hint:
            self.inventory_hints[sid]=session.gpu_hint
            try:
                DATA.mkdir(parents=True,exist_ok=True)
                target=DATA/'inventory_hints.json'
                temporary=target.with_suffix('.tmp')
                temporary.write_text(json.dumps(self.inventory_hints),encoding='utf-8')
                temporary.replace(target)
            except OSError:
                pass  # Inventory tint is optional; never disturb monitoring on a cache failure.
        if sid==self.selected_id:
            self.render_selected()

    def update_availability_badges(self):
        if self.selected:
            for uuid,card in self.cards.items():
                card.set_availability(self.selected.gpu_availability(uuid))

    def edit_availability_rules(self):
        dialog=AvailabilityDialog(self,self.availability_rules)
        if dialog.exec()!=QDialog.DialogCode.Accepted:
            return
        rules=dialog.rules()
        try:
            DATA.mkdir(parents=True,exist_ok=True)
            target=DATA/'availability_rules.json'
            temporary=target.with_suffix('.tmp')
            temporary.write_text(json.dumps(rules.as_dict(),indent=2),encoding='utf-8')
            temporary.replace(target)
        except OSError as exc:
            self.notify('无法保存规则',str(exc))
            return
        self.availability_rules=rules
        for session in self.sessions.values():
            session.availability_tracker=Tracker(rules)
            session.gpu_states={}
            self.host_changed(session.id)

    def render_status(self):
        session=self.selected
        for widget in (self.connect_button,self.edit_button,self.remove_button):
            widget.setEnabled(session is not None)
        if not session:
            self.badge.setText('● 无主机')
            self.heading.setText('添加你的第一台主机')
            return
        p=session.profile
        self.heading.setText(p['name'])
        self.heading.setToolTip(p['name'])
        self.connect_button.setText('暂停监控' if session.desired else '恢复监控')
        self.badge.setText('● '+session.state)
        color='#68f6cf' if session.fresh else '#ffcb84' if session.desired or session.state in ('连接异常','待认证') else '#91a4be'
        self.badge.setTone(color)
        self.status_text.setText(session.message+(' · 最近采样 '+str(int(time.monotonic()-session.received))+' 秒前' if session.received else ''))
        self.telemetry.setText(f'SECURE SHELL  /  {p["interval"]}s INTERVAL  /  后台独立监控')

    def render_selected(self):
        self.render_status()
        session=self.selected
        data=session.snapshot if session else None
        if session:
            p=session.profile
            endpoint=(p['user']+'@' if p['user'] else '')+p['host']+(':'+p['port'] if p['port'] else '')
            self.subtitle.setText(endpoint+(f'  /  Driver {data["driver"]}  /  CUDA {data["cuda"]}' if data else '  /  等待首次采样'))
        else:
            self.subtitle.setText('左侧添加或导入主机，所有连接可同时监控。')
        if not data:
            self.clear_cards()
            self.empty.show()
            self.current=[]
            for value in self.stats:
                value.setText('—')
        else:
            gs=data['gpus']
            self.empty.setVisible(not gs)
            self.empty.setText('SSH 连接正常\n\n'+data.get('notice','当前主机没有可显示的 GPU') if not gs else '')
            ids={g['uuid'] for g in gs}
            for key in list(self.cards):
                if key not in ids:
                    card=self.cards.pop(key)
                    self.card_layout.removeWidget(card)
                    card.hide()
                    card.deleteLater()
            for g in gs:
                history=session.history.get(g['uuid'],())
                if g['uuid'] not in self.cards:
                    card=GPUCard(g,history,session.gpu_availability(g['uuid']))
                    self.cards[g['uuid']]=card
                    self.card_layout.insertWidget(self.card_layout.count()-1,card)
                else:
                    self.cards[g['uuid']].update_data(g,history,session.gpu_availability(g['uuid']))
            utils=[g['util'] for g in gs if g['util'] is not None]
            used=sum(g['used'] or 0 for g in gs)/1024
            total=sum(g['total'] or 0 for g in gs)/1024
            self.current=data['processes']
            values=[str(len(gs)),fmt(sum(utils)/len(utils) if utils else None,'%'),f'{used:.1f} / {total:.1f} GiB' if gs else '—',str(len({p['pid'] for p in self.current}))]
            for value,text in zip(self.stats,values):
                value.setText(text)
        self.size_cards()
        self.render_processes()

    def render_processes(self):
        old=self.table.currentRow()
        selected=self.table.item(old,1).data(Qt.ItemDataRole.UserRole) if old>=0 and self.table.item(old,1) else None
        needle=self.search.text().strip().lower()
        rows=[p for p in self.current if needle in ' '.join(str(v) for v in p.values()).lower()]
        self.visible_processes=rows
        self.table.blockSignals(True)
        self.table.setRowCount(len(rows))
        selected_row=-1
        for row,p in enumerate(rows):
            identity=(p['uuid'],p['pid'],p.get('start'))
            if identity==selected:
                selected_row=row
            values=[p['gpu'],p['pid'],p.get('user','—'),p['kind'],fmt(p['memory']),p['name'].rsplit('/',1)[-1],p.get('cwd','—'),p.get('ppid','—')]
            for col,value in enumerate(values):
                item=QTableWidgetItem(str(value))
                item.setTextAlignment(ALIGNMENTS[col])
                item.setToolTip(str(value))
                if col==1:
                    item.setData(Qt.ItemDataRole.UserRole,identity)
                    item.setForeground(QColor('#7eece6'))
                self.table.setItem(row,col,item)
        self.table.clearSelection()
        if selected_row>=0:
            self.table.selectRow(selected_row)
        self.table.blockSignals(False)
        if selected_row>=0:
            self.show_details()
        elif selected:
            self.details.setPlainText('原选中进程已退出、发生变化或被筛选隐藏。')
        self.process_count.setText(f'{len(rows):02d}')
        self.layout_process_columns()

    def layout_process_columns(self):
        header=self.table.horizontalHeader()
        remaining=self.table.viewport().width()-sum(header.sectionSize(i) for i in range(8) if i!=6)
        mode=QHeaderView.ResizeMode.Stretch if remaining>=260 else QHeaderView.ResizeMode.Interactive
        if header.sectionResizeMode(6)!=mode:
            header.setSectionResizeMode(6,mode)
        if mode==QHeaderView.ResizeMode.Interactive:
            header.resizeSection(6,260)

    def show_details(self):
        row=self.table.currentRow()
        if not 0<=row<len(self.visible_processes):
            return
        p=self.visible_processes[row]
        self.details.setPlainText(f"GPU {p['gpu']}  |  PID {p['pid']}  |  用户 {p.get('user','—')}  |  UID {p.get('uid','—')}  |  父 PID {p.get('ppid','—')}\n工作目录：{p.get('cwd','—')}\n可执行文件：{p.get('exe','—')}\n驱动报告：{p['name']}\nGPU 实例：{p.get('instance','N/A')}  |  进程身份标记：{p.get('start','不可用')}")

    def autostart(self):
        for session in self.sessions.values():
            if session.profile['autoconnect']:
                session.start()

    def connect_all(self):
        pending=[]
        for session in self.sessions.values():
            session.profile['autoconnect']=True
            session.start()
            if session.state=='待认证':
                pending.append(session.profile['name'])
        if pending:
            self.notify('需要密码','以下主机需要逐台点击“连接主机”输入密码：\n'+'\n'.join(pending))
        self.persist_session_preferences()

    def persist_session_preferences(self):
        self.save_items([s.profile for s in self.sessions.values()])

    def pause_all(self):
        for session in self.sessions.values():
            session.pause()
        self.persist_session_preferences()

    def stop_all(self):
        for session in self.sessions.values():
            session.stop()

    def toggle_selected(self):
        s=self.selected
        if not s:
            return
        if s.desired:
            s.pause()
            self.persist_session_preferences()
        elif (s.profile['mode']==profiles.MODES[2] and not vault.get_password(s.profile)) or s.state=='连接异常':
            self.edit_host(credentials_only=True)
        else:
            s.profile['autoconnect']=True
            self.persist_session_preferences()
            s.start()

    def write_runtime_state(self):
        try:
            profiles.atomic_json(DATA/'runtime_state.json',{
                'version':'v13','pid':__import__('os').getpid(),
                'exe':sys.executable,'app_data':str(DATA),'profile_data':str(profiles.DATA),
                'loaded_count':len(self.items),'session_count':len(self.sessions),
                'visible_row_count':self.host_list.count(),'load_error':self.load_error,
                'names':[p['name'] for p in self.items],
                'stamp':self.profile_stamp,
            })
        except OSError:
            pass

    def profiles_stamp(self):
        stamps=[]
        for name in ('profiles.json','host_catalog.json'):
            try:
                stat=(profiles.DATA/name).stat()
                stamps.append((stat.st_mtime_ns,stat.st_size))
            except OSError:
                stamps.append(None)
        return tuple(stamps)

    def reload_profiles(self):
        if self.closing:
            return
        stamp=self.profiles_stamp()
        if stamp==self.profile_stamp and {p['id'] for p in self.items}==set(self.sessions) and self.host_list.count()==len(self.items):
            return
        try:
            incoming=profiles.load()
            if len({p['id'] for p in incoming})!=len(incoming):
                return
        except (OSError,ValueError,TypeError):
            return  # An incomplete external write never removes the visible fleet.
        new_ids={p['id'] for p in incoming}
        for sid in list(self.sessions):
            if sid not in new_ids:
                old=self.sessions.pop(sid)
                old.stop()
                if old.running: self.retired.append(old)
                else: old.deleteLater()
        for p in incoming:
            old=self.sessions.get(p['id'])
            if old and old.profile==p:
                continue
            connection_changed=old and any(old.profile.get(k)!=p.get(k) for k in ('host','user','port','key','mode','interval'))
            if connection_changed:
                old.stop()
                if old.running: self.retired.append(old)
                else: old.deleteLater()
                old=None
            if old:
                desired_changed=old.profile['autoconnect']!=p['autoconnect']
                old.profile=p
                if desired_changed:
                    old.start() if p['autoconnect'] else old.pause()
            else:
                old=self.register(p)
                if p['autoconnect'] and self.automatic_start: old.start()
        self.items=incoming
        self.profile_stamp=self.profiles_stamp()
        self.rebuild_list()

    def save_items(self,items,removed_ids=()):
        try:
            # A stale window must preserve hosts added by another running version.
            known=set(self.sessions)
            supplied={p['id'] for p in items}
            added=[p for p in profiles.load() if p['id'] not in known and p['id'] not in supplied and p['id'] not in removed_ids]
            items=items+added
            items=profiles.save(items,removed_ids=removed_ids)
            for p in added:
                session=self.register(p)
                if p['autoconnect'] and self.automatic_start: session.start()
            self.profile_stamp=self.profiles_stamp()
            self.items=items
            return True
        except Exception as exc:
            self.notify('配置未保存',str(exc))
            return False

    def add_host(self):
        dialog=HostDialog(self)
        if dialog.exec()==QDialog.DialogCode.Accepted:
            self.apply_profile(dialog.profile(),*dialog.credentials(),remember=dialog.remember.isChecked())
        dialog.secret.clear()

    def edit_host(self,credentials_only=False):
        if not self.selected:
            return
        dialog=HostDialog(self,self.selected.profile,credentials_only)
        if dialog.exec()==QDialog.DialogCode.Accepted:
            p=dialog.profile()
            if credentials_only:
                p['autoconnect']=True
            self.apply_profile(p,*dialog.credentials(),remember=dialog.remember.isChecked())
        dialog.secret.clear()

    def apply_profile(self,p,password='',passphrase='',remember=True):
        p=profiles.clean(p)
        try:
            if p['mode']==profiles.MODES[2]:
                if remember and password:
                    vault.save_password(p,password)
                elif not remember:
                    password=password or vault.get_password(p)
                    vault.forget_password(p)
        except Exception as exc:
            self.notify('无法保存密码',str(exc))
            return
        old=self.sessions.get(p['id'])
        updated=[p if x['id']==p['id'] else x for x in self.items]
        if not old:
            updated.append(p)
        if not self.save_items(updated):
            return
        if old:
            old.stop()
            if old.running:
                self.retired.append(old)
            else:
                old.deleteLater()
        session=self.register(p)
        self.rebuild_list(p['id'])
        session.start(password,passphrase)

    def remove_host(self):
        s=self.selected
        if not s:
            return
        if not self.save_items([p for p in self.items if p['id']!=s.id],removed_ids={s.id}):
            return
        s.stop()
        if s.running:
            self.retired.append(s)
        else:
            s.deleteLater()
        del self.sessions[s.id]
        self.rebuild_list()

    def import_ssh(self):
        path,_=QFileDialog.getOpenFileName(self,'导入 SSH config 或迁移 JSON',str(Path.home()/'.ssh'),'配置文件 (*);;JSON (*.json)')
        if not path:
            return
        self.import_path(path)

    def import_path(self,path):
        try:
            warnings=[]
            if path.lower().endswith('.json'):
                bundle=json.loads(Path(path).read_text(encoding='utf-8-sig'))
                imported=[profiles.clean(p) for p in bundle['profiles']]
                ssh=bundle.get('ssh_config','')
                if ssh:
                    with tempfile.TemporaryDirectory() as temp:
                        f=Path(temp)/'config'
                        f.write_text(ssh,encoding='utf-8')
                        _,warnings=profiles.import_config(f)
            else:
                names,warnings=profiles.import_config(path)
                imported=[profiles.clean({'name':name,'host':name}) for name in names]
            existing={p['name'] for p in self.items}
            ids=set(self.sessions)
            added=[]
            for p in imported:
                if p['name'] in existing:
                    continue
                if p['id'] in ids:
                    p['id']=uuid.uuid4().hex
                existing.add(p['name'])
                ids.add(p['id'])
                added.append(p)
            if not self.save_items(self.items+added):
                return
            for p in added:
                self.register(p)
            self.rebuild_list(added[0]['id'] if added else None)
            self.notify('配置已保存',f'新增 {len(added)} 台主机。点击“全部连接”可并行监控。\n已有主机将在下次连接时使用更新的 SSH config；当前连接不中断。\n'+'\n'.join(warnings))
        except Exception as exc:
            self.notify('导入失败',str(exc))

    def edit_config(self):
        dialog=ConfigDialog(self)
        if dialog.exec()!=QDialog.DialogCode.Accepted:
            return
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'config'
            path.write_text(dialog.editor.toPlainText(),encoding='utf-8')
            self.import_path(str(path))

    def export_bundle(self):
        path,_=QFileDialog.getSaveFileName(self,'导出迁移配置','GPUChecker-connections.json','JSON (*.json)')
        if not path:
            return
        try:
            source=config_path()
            ssh=source.read_text(encoding='utf-8-sig') if source.exists() else ''
            Path(path).write_text(json.dumps({'version':2,'profiles':[profiles.clean(p) for p in self.items],'ssh_config':ssh},ensure_ascii=False,indent=2),encoding='utf-8')
            self.notify('已导出','包含主机配置与 SSH config，不包含程序输入的密码、私钥口令、私钥内容或信任记录。\nSSH config 自定义指令原样保留，请勿在其中内嵌秘密。')
        except Exception as exc:
            self.notify('导出失败',str(exc))

    def queue_trust(self,sid,host,fingerprint):
        self.trust_queue.append((sid,self.sessions.get(sid),host,fingerprint))
        if not self.trust_busy:
            QTimer.singleShot(0,self.drain_trust)

    def drain_trust(self):
        if self.trust_busy:
            return
        self.trust_busy=True
        try:
            while self.trust_queue:
                sid,session,host,fp=self.trust_queue.pop(0)
                if not session or not session.desired or not session.worker:
                    continue
                worker=session.worker
                answer=QMessageBox.question(self,'核对主机指纹',f"主机：{session.profile['name']} ({host})\n\n{fp}\n\n请与管理员提供的指纹核对。信任并保存？",QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No,QMessageBox.StandardButton.No)
                worker.accept_key(answer==QMessageBox.StandardButton.Yes and session.desired and self.sessions.get(sid) is session)
        finally:
            self.trust_busy=False

    def session_stopped(self,sid):
        self.retired=[s for s in self.retired if s.running]
        if self.closing and not any(s.running for s in list(self.sessions.values())+self.retired):
            self.close()
            QApplication.instance().quit()

    def update_fleet(self):
        active=sum(s.fresh for s in self.sessions.values())
        self.fleet.setText(f'{active} 台在线 / {len(self.sessions)} 台主机')

    def tick(self):
        self.reload_profiles()
        self.clock.setText(time.strftime('%H:%M:%S')+'  LOCAL')
        for s in self.sessions.values():
            s.refresh_age()
        self.update_fleet()
        self.render_status()

    def size_cards(self):
        if self.cards:
            width=max(180,min(270,(self.card_scroll.viewport().width()-12*(len(self.cards)-1))//len(self.cards)))
            for card in self.cards.values():
                card.setFixedWidth(width)

    def resizeEvent(self,event):
        super().resizeEvent(event)
        if hasattr(self,'card_scroll'):
            self.size_cards()
        if hasattr(self,'table'):
            QTimer.singleShot(0,self.layout_process_columns)
        if getattr(self,'resize_handles',None):
            layout_handles(self)

    def changeEvent(self,event):
        super().changeEvent(event)
        if event.type()==QEvent.Type.WindowStateChange and getattr(self,'resize_handles',None):
            layout_handles(self)
            for control in self.title_bar.findChildren(QWidget):
                control.update()

    def help(self):
        self.notify('GPU Checker v13 使用说明','左侧主机在后台持续采集，点击只切换右侧视图。暂停某台或全部暂停会保存状态，下次启动仍暂停；恢复后重新启用自动连接。正常关闭窗口不会改变暂停设置。\n\n编辑主机可勾选记住服务器密码，存入当前 Windows 用户的凭据管理器。程序启动时可自动取用；暂停不会删除已保存密码。取消勾选并保存可删除凭据。换电脑需重新输入。私钥口令仍仅保留在会话内存。\n\n无 GPU 主机显示在线并继续保活；驱动不可用与无设备分别显示。不提权，不控制用卡进程，不读取环境或完整命令行。\n\nOpenSSH 模式支持系统 config、Agent 和跳板机；内置密码模式仅直连。新主机需核对指纹，已有密钥变化拒绝连接。\n\n远端要求 Linux 与 Python 3.6+；GPU 遥测另需 NVIDIA 驱动和 nvidia-smi。\n\n配置位置：'+str(DATA)+'\n主机条目：'+str(len(self.items))+'；列表：'+str(self.host_list.count())+'\n主机读取位置：'+str(profiles.DATA)+'\nexe 旁放 portable.flag 可启用 data/ 便携模式。密码不进入 JSON、config 或迁移包，私钥请独立保管。')

    def closeEvent(self,event):
        self.closing=True
        all_sessions=list(self.sessions.values())+self.retired
        running=any(s.running for s in all_sessions)
        for s in all_sessions:
            s.stop()
        if running:
            self.hide()
            event.ignore()
        else:
            event.accept()


def configure_app(app):
    if not hasattr(app,'hover_popup_filter'):
        app.hover_popup_filter=NoHoverPopups(app)
        app.installEventFilter(app.hover_popup_filter)
    QToolTip.hideText()
    app.setStyle('Fusion')
    if not app.property('bundledFontsLoaded'):
        for path in (ASSETS/'fonts').glob('*.ttf'):
            QFontDatabase.addApplicationFont(str(path))
        app.setProperty('bundledFontsLoaded',True)
    font=QFont()
    font.setFamilies(['Rajdhani Medium','Rajdhani','ZCOOL QingKe HuangYou','Noto Sans SC'])
    font.setPointSize(10)
    app.setFont(font)
    try:
        mode=json.loads((DATA/'ui_preferences.json').read_text(encoding='utf-8')).get('theme','night')
    except Exception:
        mode='night'
    themes.apply(app,mode,STYLE)



def main():
    app=QApplication(sys.argv)
    configure_app(app)
    from instance_guard import InstanceGuard
    app.instance_guard=InstanceGuard(DATA,app)
    try:
        if not app.instance_guard.claim(): return 0
    except RuntimeError as exc:
        QMessageBox.warning(None,'GPU Checker',str(exc))
        return 1
    window=Window()
    app.instance_guard.window=window
    window.show()
    return app.exec()


if __name__=='__main__':
    sys.exit(main())
