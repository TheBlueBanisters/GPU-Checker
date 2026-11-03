import subprocess,sys,os
from pathlib import Path


def test_closing_with_active_sessions_exits_event_loop(tmp_path):
    source=Path(__file__).resolve().parents[1]/'src'
    code='''
from pathlib import Path
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication
import app,backend,profiles
from sessions import HostSession
from test_multihost import FakeMonitor
class Delayed(FakeMonitor):
 def stop(self):
  if self.running:
   QTimer.singleShot(20,self.finish)
 def finish(self):
  if self.running:
   self.running=False
   self.finished.emit()
application=QApplication([])
for module in (app,backend,profiles): module.DATA=Path(DATA)
profiles.save([profiles.clean({'host':'shutdown.invalid'})])
w=app.Window(autostart=False,session_factory=lambda p,parent:HostSession(p,parent,factory=Delayed))
w.show();w.connect_all()
QTimer.singleShot(50,w.close)
application.exec()
print('shutdown-ok')
'''.replace('Path(DATA)',repr(str(tmp_path)))
    # Preserve an actual Path, including on Windows.
    code=code.replace('module.DATA='+repr(str(tmp_path)),'module.DATA=Path('+repr(str(tmp_path))+')')
    env=dict(os.environ,PYTHONPATH=str(source)+os.pathsep+str(Path(__file__).parent),QT_QPA_PLATFORM='offscreen')
    result=subprocess.run([sys.executable,'-c',code],capture_output=True,text=True,env=env,timeout=10)
    assert result.returncode==0,result.stderr
    assert 'shutdown-ok' in result.stdout
