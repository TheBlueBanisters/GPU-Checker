"""Independent host sessions. Selecting a view never touches a transport."""
from collections import deque
import time
from PySide6.QtCore import QObject, QTimer, Signal
from backend import Monitor
import profiles
import vault
import snapshots
from availability import Tracker,result


class HostSession(QObject):
    changed = Signal(str)
    sampled = Signal(str)
    trust = Signal(str, str, str)
    stopped = Signal(str)

    def __init__(self, profile, parent=None, factory=Monitor):
        super().__init__(parent)
        self.profile = profiles.clean(profile)
        self.id = self.profile["id"]
        self.factory = factory
        self.worker = None
        self.desired = False
        self.password = self.passphrase = ""
        self.snapshot = None
        self.history = {}
        self.received = 0
        self.sample_count = 0
        self.sampled_at=0.
        self.retained_snapshot=False
        self.cache_error=''
        self.availability_tracker=Tracker()
        self.gpu_states={}
        self.gpu_hint=None
        self.state = '未连接' if self.profile['autoconnect'] else '已暂停'
        self.message = '点击连接开始监控' if self.profile['autoconnect'] else '已记住暂停状态，不会自动连接'
        self.retry_count = 0
        self.retry_timer = QTimer(self)
        self.retry_timer.setSingleShot(True)
        self.retry_timer.timeout.connect(self._launch)
        cached=snapshots.load(self.profile)
        if cached:
            self.snapshot=cached['data']
            self.sampled_at=cached['sampled_at']
            self.history={key:deque(values,maxlen=60) for key,values in cached['history'].items()}
            self.gpu_hint=self.snapshot.get('gpu_status','available')
            self.retained_snapshot=True
            self.message='已恢复最后一次成功采样；等待连接，当前显示历史快照'


    @property
    def running(self):
        return bool(self.worker and self.worker.isRunning())

    @property
    def fresh(self):
        return (self.state in ('在线','在线 · 无 GPU','在线 · GPU 不可用') and self.received > 0 and
                time.monotonic() - self.received < max(10, self.profile["interval"]*2+5))

    @property
    def historical(self):
        return self.snapshot is not None and (not self.fresh or self.retained_snapshot)

    @property
    def snapshot_time(self):
        return time.strftime('%Y-%m-%d %H:%M:%S',time.localtime(self.sampled_at)) if self.sampled_at else '时间未知'

    def start(self, password="", passphrase=""):
        if self.desired:
            return
        if self.profile['mode']==profiles.MODES[2] and not password:
            try:
                password=vault.get_password(self.profile)
            except Exception as exc:
                self.state,self.message='待认证','无法读取已保存密码：'+str(exc)
                self.changed.emit(self.id)
                return
        if self.profile["mode"] == profiles.MODES[2] and not password:
            self.state, self.message = "待认证", "需要输入本次会话的服务器密码"
            self.changed.emit(self.id)
            return
        self.password, self.passphrase = password, passphrase
        self.desired = True
        self.retry_count = 0
        self.retry_timer.stop()
        if not self.running:
            self._launch()
        # If an old worker is still shutting down, finished() launches the new session.

    def _launch(self):
        if not self.desired or self.running:
            return
        self.state, self.message = "连接中", "正在建立加密连接…"
        self.availability_tracker.reset()
        self.gpu_states={}
        worker = self.factory(self.profile, self.password, self.passphrase)
        self.worker = worker
        worker.data.connect(lambda data, w=worker: self._sample(w, data))
        worker.status.connect(lambda message, w=worker: self._status(w, message))
        worker.failed.connect(lambda message, w=worker: self._failed(w, message))
        worker.trust.connect(lambda host, fp, w=worker: self._trust(w, host, fp))
        worker.finished.connect(lambda w=worker: self._finished(w))
        self.changed.emit(self.id)
        worker.start()

    def _status(self, worker, message):
        if worker is self.worker and self.desired:
            self.message = message
            self.changed.emit(self.id)

    def _trust(self, worker, host, fingerprint):
        if worker is self.worker and self.desired:
            self.state, self.message = "待确认", "请核对服务器主机指纹"
            self.changed.emit(self.id)
            self.trust.emit(self.id, host, fingerprint)
        else:
            worker.accept_key(False)

    def _sample(self, worker, data):
        if worker is not self.worker or not self.desired:
            return
        if data.get("error"):
            self.availability_tracker.reset()
            self.gpu_states={}
            self.state, self.message = "采样异常", str(data["error"])
            self.changed.emit(self.id)
            return
        capability=data.get('gpu_status','available')
        if capability=='unavailable' and self.snapshot is not None:
            self.retained_snapshot=True
            self.received=time.monotonic()
            self.sample_count+=1
            self.gpu_hint=capability
            self.gpu_states={}
            self.availability_tracker.reset()
            self.state='在线 · GPU 不可用'
            self.message=data.get('notice','GPU 查询不可用；保留最后一次成功采样')
            self.changed.emit(self.id)
            self.sampled.emit(self.id)
            return
        self.snapshot = data
        self.retained_snapshot=False
        self.sampled_at=time.time()
        self.received = time.monotonic()
        self.sample_count += 1
        self.retry_count = 0
        capability=data.get('gpu_status','available')
        self.gpu_hint=capability
        self.gpu_states=self.availability_tracker.observe(data,self.received,self.profile['interval'])
        self.state = '在线 · 无 GPU' if capability=='no_gpu' else '在线 · GPU 不可用' if capability=='unavailable' else '在线'
        self.message=data.get('notice') or '只读实时采样正常'
        for gpu in data["gpus"]:
            values = self.history.setdefault(gpu["uuid"], deque(maxlen=60))
            values.append(gpu.get("util"))
        if capability in ('available','no_gpu'):
            try:
                snapshots.save(self.profile,self.snapshot,self.history,self.sampled_at)
                self.cache_error=''
            except Exception:
                self.cache_error='本次快照未保存到磁盘，仍显示实时数据'
        self.changed.emit(self.id)
        self.sampled.emit(self.id)

    def _failed(self, worker, message):
        if worker is not self.worker or not self.desired:
            return
        self.state, self.message = "连接异常", message
        fatal = any(token in message.lower() for token in (
            "认证失败", "permission denied", "host key", "does not match", "未信任", "格式不正确",
            "需要填写", "未找到 openssh", "跳板机", "端口应为"))
        if fatal:
            self.desired = False
            self.password = self.passphrase = ""
        self.changed.emit(self.id)

    def _finished(self, worker):
        if worker is not self.worker:
            return
        self.worker = None
        worker.deleteLater()
        if self.desired and self.profile.get("retry", True):
            self.retry_count += 1
            delay = min(60, 3 * 2 ** min(self.retry_count-1, 5))
            self.state = "重连中"
            self.message += f" · {delay} 秒后重连"
            self.retry_timer.start(delay*1000)
        else:
            self.desired = False
            self.password = self.passphrase = ""
        self.changed.emit(self.id)
        self.stopped.emit(self.id)

    def stop(self):
        self.desired = False
        self.retry_timer.stop()
        self.availability_tracker.reset()
        self.password = self.passphrase = ""
        self.state, self.message = "已停止", "监控已停止；保留最后一次采样"
        if self.worker:
            self.worker.stop()
        self.changed.emit(self.id)

    def pause(self):
        self.profile['autoconnect']=False
        self.stop()
        self.state,self.message='已暂停','已记住暂停状态；下次启动不会自动连接'
        self.changed.emit(self.id)

    def refresh_age(self):
        if self.state in ('在线','在线 · 无 GPU','在线 · GPU 不可用') and not self.fresh:
            self.state, self.message = "数据过期", "等待新采样；显示的是历史数据"
            self.availability_tracker.reset()
            self.changed.emit(self.id)

    def gpu_availability(self,uuid):
        if not self.fresh or self.retained_snapshot:
            state=result('unknown','监控暂停、连接异常或数据过期，不沿用历史可用判断')
            state['visual']='paused' if self.state in ('已暂停','已停止') else 'disconnected'
            state['label']='已暂停' if state['visual']=='paused' else '连接中断'
            return state
        return self.gpu_states.get(uuid,result('unknown','尚无完整采样'))

    def availability_counts(self):
        if not self.fresh or self.retained_snapshot or not self.snapshot or self.gpu_hint=='unavailable':
            return None
        states=[self.gpu_availability(g['uuid']) for g in self.snapshot['gpus']]
        return {'idle':sum(s['idle'] for s in states),'available':sum(s['available'] for s in states),
                'total':len(states),'unknown':sum(s['status'] in ('unknown','observing') for s in states)}
