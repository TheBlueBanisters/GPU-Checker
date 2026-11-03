"""Explicit real-server test; --two-hosts includes the user-authorized server-183."""
import json
from pathlib import Path
import sys
import tempfile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer
import app as ui
import backend
import profiles
from dialogs import ConfigDialog,HostDialog

application=QApplication([])
ui.configure_app(application)
temp=tempfile.TemporaryDirectory()
for module in (ui,backend,profiles):
    module.DATA=Path(temp.name)
two_hosts='--two-hosts' in sys.argv
items=[profiles.clean({'name':'null-sf.top','host':'null-sf.top'}),
       profiles.clean({'name':'server-183','host':'server-183'}) if two_hosts else
       profiles.clean({'name':'null-sf · 内置密钥','host':'null-sf.top','mode':profiles.MODES[1]})]
profiles.save(items)
w=ui.Window(autostart=False)
w.show()
sessions=list(w.sessions.values())
state={'ok':False,'killed':False,'switches':0}
out=Path(__file__).resolve().parents[1]/'delivery'

def tick():
    if state['ok']:
        return
    a,b=sessions
    if a.snapshot and b.snapshot:
        w.host_list.setCurrentRow(1-w.host_list.currentRow())
        state['switches']+=1
        assert w.selected.snapshot is not None
        assert len(w.cards)==(2 if two_hosts and w.host_list.currentRow()==1 else 5)
        assert w.table.rowCount()>0
    if min(a.sample_count,b.sample_count)>=3 and not state['killed']:
        state['old']=a.worker
        state['before_b']=b.sample_count
        state['killed']=True
        a.worker.proc.terminate()  # Only the local SSH client, never a GPU process.
    elif state['killed'] and a.worker is not state['old'] and a.fresh and b.sample_count>state['before_b']:
        assert a.sample_count>=4 and b.sample_count>=4
        w.host_list.setCurrentRow(0)
        w.table.selectRow(0)
        application.processEvents()
        w.grab().save(str(out/'preview.png'))
        editor=ConfigDialog(w)
        editor.editor.setPlainText('Host lab-gpu\n    HostName gpu.example.com\n    User yourname\n\nHost render-gpu\n    HostName render.example.com\n    # 缺少 User，保存时应指出此条目\n')
        assert not editor.check()
        editor.show()
        application.processEvents()
        editor.grab().save(str(out/'config-editor.png'))
        editor.close()
        dialog=HostDialog(w,a.profile)
        dialog.show()
        application.processEvents()
        dialog.grab().save(str(out/'host-editor.png'))
        dialog.close()
        state.update(ok=True,samples=[a.sample_count,b.sample_count],gpus=[len(s.snapshot['gpus']) for s in sessions],background_continued=True,reconnected=True)
        w.stop_all()
        QTimer.singleShot(1000,w.close)

def timeout():
    if not state['ok']:
        print([(s.state,s.message) for s in sessions])
    w.stop_all()
    QTimer.singleShot(1000,w.close)

timer=QTimer()
timer.timeout.connect(tick)
timer.start(400)
QTimer.singleShot(200,w.connect_all)
QTimer.singleShot(35000,timeout)
application.exec()
print(json.dumps({k:v for k,v in state.items() if k!='old'},ensure_ascii=True))
temp.cleanup()
sys.exit(0 if state['ok'] else 1)
