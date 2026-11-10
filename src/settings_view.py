"""Small cache settings window; purge runs on the existing history writer."""
from PySide6.QtCore import Qt,QTimer
from PySide6.QtWidgets import QVBoxLayout,QHBoxLayout,QProgressBar
from dialogs import MechDialog,dialog_layout
from visuals import MechPanel,ModernButton,label
import history_cache


def space(value):
    return f'{value / 1_000_000:.2f} MB' if value<1_000_000_000 else f'{value / 1_000_000_000:.2f} GB'


class SettingsDialog(MechDialog):
    def __init__(self,parent):
        super().__init__(parent)
        self.setWindowTitle('设置');self.resize(500,330)
        self.setMinimumSize(420,280)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.root=history_cache.root_path();self.job=None
        box=dialog_layout(self);box.setContentsMargins(20,17,20,17);box.setSpacing(12)
        box.addWidget(label('历史监控缓存','section'))
        panel=self.cache_panel=MechPanel();panel.setObjectName('glass');panel.setProperty('squarePanel',True)
        rowbox=QVBoxLayout(panel);rowbox.setContentsMargins(14,12,14,12);rowbox.setSpacing(9)
        row=QHBoxLayout();row.addWidget(label('已占用空间','muted'));row.addStretch()
        self.size_label=label('—','stat');row.addWidget(self.size_label);rowbox.addLayout(row)
        self.meter=QProgressBar();self.meter.setRange(0,1000);self.meter.setTextVisible(False);self.meter.setFixedHeight(5)
        rowbox.addWidget(self.meter)
        actions=QHBoxLayout();self.status=label('','muted');self.status.setWordWrap(True)
        actions.addWidget(self.status,1)
        self.clear_button=ModernButton('清除历史');self.clear_button.setFixedSize(114,36)
        self.clear_button.clicked.connect(self.clear_history);actions.addWidget(self.clear_button)
        rowbox.addLayout(actions);box.addWidget(panel)
        hint=label('清除所有主机的历史曲线数据。主机配置、已记住的密码和最后快照会保留；实时监控会继续记录新数据。','muted')
        hint.setWordWrap(True);box.addWidget(hint)
        self.timer=QTimer(self);self.timer.setInterval(250);self.timer.timeout.connect(self.refresh);self.timer.start()
        self.refresh()

    def clear_history(self):
        if self.job:return
        self.job=history_cache.clear(self.root)
        self.clear_button.setEnabled(False);self.status.setText('正在清除…')

    def refresh(self):
        if self.job and self.job['done'].is_set():
            job=self.job;self.job=None
            self.status.setText(job['error'] or '历史已清除')
            if not job['error']:
                from shiboken6 import isValid
                for window in getattr(self.parentWidget(),'history_windows',[]):
                    if isValid(window) and window.isVisible():window.refresh()
        try:
            size=history_cache.usage(self.root);budget=history_cache.limit(self.root)
            self.size_label.setText(space(size))
            self.meter.setValue(min(1000,round(size/budget*1000)))
            self.clear_button.setEnabled(self.job is None and size>0)
        except OSError:self.status.setText('暂时无法读取历史空间')

    def closeEvent(self,event):
        self.timer.stop();super().closeEvent(event)
