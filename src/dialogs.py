from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog,QVBoxLayout,QHBoxLayout,QFormLayout,QLineEdit,QComboBox,
    QSpinBox,QCheckBox,QPushButton,QDialogButtonBox,QFileDialog,QMessageBox,QPlainTextEdit)
from backend import BASE, validate, config_path
from visuals import label
import profiles
import vault


class HostDialog(QDialog):
    def __init__(self,parent=None,profile=None,credentials_only=False):
        super().__init__(parent)
        self.original=profiles.clean(profile or {})
        self.setWindowTitle("连接认证" if credentials_only else "编辑主机" if profile else "添加主机")
        self.setMinimumWidth(490)
        box=QVBoxLayout(self)
        box.setContentsMargins(25,24,25,24)
        box.setSpacing(15)
        box.addWidget(label("SECURE CONNECTION","eyebrow"))
        box.addWidget(label(self.windowTitle(),"brand"))
        form=QFormLayout()
        form.setSpacing(12)
        self.name=QLineEdit(self.original.get('name',''))
        self.host=QLineEdit(self.original.get('host',''))
        self.host.setPlaceholderText("域名 / IP / SSH Host 别名")
        self.user=QLineEdit(self.original.get('user',''))
        self.user.setPlaceholderText("留空使用 SSH config")
        self.port=QLineEdit(self.original.get('port',''))
        self.port.setPlaceholderText("留空使用 config / 22")
        self.mode=QComboBox()
        self.mode.addItems(profiles.MODES)
        self.mode.setCurrentText(self.original['mode'])
        self.key=QLineEdit(self.original.get('key',''))
        self.key.setPlaceholderText("~/.ssh/id_ed25519 或相对路径")
        keyrow=QHBoxLayout()
        keyrow.addWidget(self.key)
        browse=QPushButton("…")
        browse.clicked.connect(self.browse)
        keyrow.addWidget(browse)
        self.secret=QLineEdit()
        self.secret.setEchoMode(QLineEdit.EchoMode.Password)
        self.secret.setPlaceholderText("只用于当前会话，不保存到配置")
        self.interval=QSpinBox()
        self.interval.setRange(1,60)
        self.interval.setValue(self.original['interval'])
        self.interval.setSuffix(" 秒")
        for title,widget in (("显示名称",self.name),("主机",self.host),("用户名",self.user),("端口",self.port),("认证方式",self.mode)):
            form.addRow(title,widget)
        form.addRow("私钥文件",keyrow)
        form.addRow("密码 / 私钥口令",self.secret)
        form.addRow("采样间隔",self.interval)
        box.addLayout(form)
        self.auto=QCheckBox("启动程序时自动监控此主机")
        self.auto.setChecked(self.original['autoconnect'])
        self.retry=QCheckBox("连接中断后自动重连")
        self.retry.setChecked(self.original['retry'])
        box.addWidget(self.auto)
        box.addWidget(self.retry)
        self.remember=QCheckBox('记住密码（Windows 凭据管理器，用于自动连接）')
        self.remember.setChecked(True)
        box.addWidget(self.remember)
        hint=label('暂停状态会记住；已保存密码不进入 JSON、SSH config 或迁移包。换电脑后需重新输入。','muted')
        hint.setWordWrap(True)
        box.addWidget(hint)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Save).setText("连接" if credentials_only else "保存并监控")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("取消")
        buttons.accepted.connect(self.check)
        buttons.rejected.connect(self.reject)
        box.addWidget(buttons)
        self.mode.currentIndexChanged.connect(self.mode_changed)
        self.mode_changed()

    def mode_changed(self):
        self.secret.clear()
        self.secret.setEnabled(self.mode.currentIndex()!=0)
        self.remember.setEnabled(self.mode.currentIndex()==2)

    def browse(self):
        path,_=QFileDialog.getOpenFileName(self,"选择私钥",str(Path.home()/'.ssh'))
        if path:
            try:
                path=Path(path).relative_to(BASE).as_posix()
            except ValueError:
                try:
                    path='~/'+Path(path).relative_to(Path.home()).as_posix()
                except ValueError:
                    pass
            self.key.setText(path)

    def profile(self):
        return profiles.clean(dict(self.original,name=self.name.text().strip() or self.host.text().strip(),
            host=self.host.text().strip(),user=self.user.text().strip(),port=self.port.text().strip(),
            key=self.key.text().strip(),mode=self.mode.currentText(),interval=self.interval.value(),
            autoconnect=self.auto.isChecked(),retry=self.retry.isChecked()))

    def credentials(self):
        return (self.secret.text(),"") if self.mode.currentIndex()==2 else ("",self.secret.text())

    def check(self):
        try:
            validate(self.profile())
            if self.mode.currentIndex()==2 and not self.secret.text() and not vault.get_password(self.profile()):
                raise ValueError('请输入服务器密码；此主机尚无已保存密码')
            self.accept()
        except Exception as exc:
            QMessageBox.information(self,"检查连接信息",str(exc))


class ConfigDialog(QDialog):
    def __init__(self,parent=None):
        super().__init__(parent)
        self.setWindowTitle('粘贴 / 编辑 SSH config')
        self.resize(730,660)
        box=QVBoxLayout(self)
        box.setContentsMargins(24,23,24,23)
        box.setSpacing(12)
        box.addWidget(label('SSH CONFIG EDITOR','eyebrow'))
        box.addWidget(label('粘贴配置，识别你的主机','brand'))
        hint=label('每个条目需包含 Host 与 User；别名还需 HostName。Port 可省略（22），IdentityFile 可省略。只校验文本，不尝试连接。','muted')
        hint.setWordWrap(True)
        box.addWidget(hint)
        row=QHBoxLayout()
        for text,fn in (('读取 config 文件',self.read_file),('载入当前配置',self.read_current)):
            b=QPushButton(text)
            b.clicked.connect(fn)
            row.addWidget(b)
        row.addStretch()
        box.addLayout(row)
        self.editor=QPlainTextEdit()
        self.editor.setStyleSheet("QPlainTextEdit {background:#0b1728;color:#bce5ee;border:1px solid #345570;border-radius:9px;padding:12px;font-family:Consolas;font-size:13px;}")
        self.editor.setPlaceholderText('Host lab-gpu\n    HostName gpu.example.com\n    User yourname\n    Port 22\n    IdentityFile ~/.ssh/id_ed25519\n\n# 可以一次粘贴多个 Host 条目')
        box.addWidget(self.editor,1)
        self.report=label('尚未检查。保存前会自动校验，失败不会覆盖原配置。','muted')
        self.report.setWordWrap(True)
        self.report.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        box.addWidget(self.report)
        row=QHBoxLayout()
        check=QPushButton('检查内容')
        check.clicked.connect(self.check)
        row.addWidget(check)
        row.addStretch()
        cancel=QPushButton('取消')
        cancel.clicked.connect(self.reject)
        row.addWidget(cancel)
        save=QPushButton('保存并导入主机')
        save.setObjectName('primary')
        save.clicked.connect(self.save)
        row.addWidget(save)
        box.addLayout(row)

    def read_file(self):
        path,_=QFileDialog.getOpenFileName(self,'读取 SSH config',str(Path.home()/'.ssh'))
        if path:
            self.read_path(Path(path))

    def read_current(self):
        self.read_path(config_path())

    def read_path(self,path):
        try:
            self.editor.setPlainText(path.read_text(encoding='utf-8-sig'))
            self.report.setText('已载入，尚未修改已保存配置。')
        except Exception as exc:
            self.report.setText('读取失败：'+str(exc))

    def check(self):
        try:
            names,info=profiles.validate_config(self.editor.toPlainText())
            self.report.setStyleSheet('color:#79f4cb')
            self.report.setText(f'校验通过，识别 {len(names)} 台主机：\n'+'\n'.join(f"{name} → {info[name].get('user')}@{info[name].get('hostname',name)}:{info[name].get('port',22)}" for name in names))
            return True
        except Exception as exc:
            self.report.setStyleSheet('color:#ffadba')
            self.report.setText(str(exc))
            return False

    def save(self):
        if self.check():
            self.accept()
