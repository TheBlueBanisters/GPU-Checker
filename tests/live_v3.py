"""Explicit three-host check, including the user's authorized CPU-only server."""
import sys,json,tempfile,shutil
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer,QPoint,QRect,Qt
from PySide6.QtTest import QTest
import app as ui
import profiles,backend
from dialogs import HostDialog,ConfigDialog

application=QApplication([])
ui.configure_app(application)
import themes
from visuals import STYLE
themes.apply(application,"night",STYLE)
items=profiles.load()
for item in items:
    item['autoconnect']=True  # Test copy only; preserve the user's saved pause choices.
original=backend.DATA
temp=tempfile.TemporaryDirectory()
for module in (ui,profiles,backend):
    module.DATA=Path(temp.name)
if (original/'known_hosts').exists():
    shutil.copy2(original/'known_hosts',backend.DATA/'known_hosts')
profiles.save(items)
w=ui.Window()
w.show()
state={'ok':False}
out=Path(__file__).resolve().parents[1]/'delivery'

def check():
    if state['ok'] or state.get('busy'):
        return
    sessions=list(w.sessions.values())
    if len(sessions)==3 and all(s.fresh and s.sample_count>=7 for s in sessions):
        state['busy']=True
        cpu=next(s for s in sessions if s.profile['host']=='lisa-cpu')
        assert cpu.state=='在线 · 无 GPU' and cpu.snapshot['gpus']==[]
        i=next(i for i,p in enumerate(w.items) if p['id']==cpu.id)
        w.host_list.setCurrentRow(i)
        application.processEvents()
        assert 'SSH' in w.empty.text()
        w.grab().save(str(out/'preview-nogpu.png'))
        w.toggle_selected()
        assert not cpu.desired
        assert next(p for p in profiles.load() if p['id']==cpu.id)['autoconnect'] is False
        w.host_list.setCurrentRow(0)
        application.processEvents()
        if w.table.rowCount():
            QTest.mouseMove(w.table.viewport(),w.table.visualItemRect(w.table.item(0,2)).center())
            QTest.qWait(30)
        w.grab().save(str(out/'preview.png'))
        if '--feedback-demo' in sys.argv:
            frames=out.parent/'build/feedback-frames'
            frames.mkdir(parents=True,exist_ok=True)
            top=w.stats[0].parentWidget().mapTo(w,QPoint(0,0))
            bottom=w.card_scroll.mapTo(w,QPoint(w.card_scroll.width(),w.card_scroll.height()))
            region=QRect(top,bottom)
            index=[0]
            def capture(count):
                for _ in range(count):
                    QTest.qWait(40)
                    shot=w.grab(region).scaledToWidth(1100,Qt.TransformationMode.SmoothTransformation)
                    shot.save(str(frames/f'frame-{index[0]:03d}.png'))
                    index[0]+=1
            capture(8)
            QTest.mouseMove(w.stats[0],QPoint(20,10));capture(6)
            QTest.mouseClick(w.stats[0],Qt.MouseButton.LeftButton,pos=QPoint(20,10));capture(16)
            gpu=next(iter(w.cards.values()))
            QTest.mouseMove(gpu.metric_label,QPoint(30,15));capture(6)
            QTest.mouseClick(gpu.metric_label,Qt.MouseButton.LeftButton,pos=QPoint(30,15));capture(16)
            QTest.mouseMove(w.heading,QPoint(10,10));capture(8)
        w.toggle_theme();application.processEvents();w.grab().save(str(out/'preview-day.png'))
        d=HostDialog(w,cpu.profile)
        d.show();application.processEvents();d.grab().save(str(out/'host-editor-day.png'));d.close()
        c=ConfigDialog(w)
        c.editor.setPlainText('Host lab-gpu\n HostName gpu.example.com\n User yourname\n\nHost cpu-server\n HostName cpu.example.com\n')
        assert not c.check()
        c.show();application.processEvents();c.grab().save(str(out/'config-editor.png'));c.close()
        w.toggle_theme()
        state.update(ok=True,samples=[s.sample_count for s in sessions],gpu_counts=[len(s.snapshot['gpus']) for s in sessions],saved_password_autologin=True,pause_persisted=True,
                     availability=[{'host':s.profile['name'],'counts':s.availability_counts(),'states':[value['status'] for value in s.gpu_states.values()]} for s in sessions])
        w.close()

def timeout():
    print([(s.profile['name'],s.state) for s in w.sessions.values()])
    w.close()

timer=QTimer();timer.timeout.connect(check);timer.start(300)
QTimer.singleShot(35000,timeout)
application.exec()
print(json.dumps(state))
temp.cleanup()
sys.exit(0 if state['ok'] else 1)
