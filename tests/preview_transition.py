"""Offline transition preview. All hosts, processes and GPU values are synthetic."""
import os,sys,math,tempfile
from pathlib import Path
from collections import deque
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QRect,Qt
from PySide6.QtTest import QTest
import app as ui
import profiles,backend,themes
from visuals import STYLE
from sessions import HostSession
from test_multihost import FakeMonitor
from test_availability import gpu


def data(level):
    gpus=[];processes=[]
    for index in range(5):
        gpus.append(gpu(index=index,uuid=f'DEMO-{index}',name='GeForce RTX 4090',
                        state='P0',util=level-index*2,used=12288.+index*160,
                        total=24576.,free=12288.-index*160,power=280.,fan='45 %'))
        processes.append(dict(gpu=index,uuid=f'DEMO-{index}',pid=str(1000+index),user='demo',kind='C',
                              memory=12288.,name='python',cwd='/demo/project',exe='/demo/python',start='1',ppid='1'))
    return dict(gpus=gpus,processes=processes,driver='DEMO',cuda='DEMO',gpu_status='available')


application=QApplication([]);ui.configure_app(application);themes.apply(application,'night',STYLE)
with tempfile.TemporaryDirectory(prefix='gpu-transition-demo-') as directory:
    for module in (ui,profiles,backend):module.DATA=Path(directory)
    profiles.save([profiles.clean({'host':'demo.invalid','name':'模拟数据 · 遥测过渡演示','autoconnect':False})])
    w=ui.Window(autostart=False,session_factory=lambda p,parent:HostSession(p,parent,factory=FakeMonitor))
    w.show();w.resize(1720,1000);application.processEvents()
    out=ROOT/'build/transition-frames';out.mkdir(parents=True,exist_ok=True)
    index=0
    frames=[]
    region=QRect(294,54,w.width()-310,w.height()-66)
    def capture(count):
        global index
        for _ in range(count):
            QTest.qWait(40)
            frames.append(w.grab(region).scaledToWidth(1000,Qt.TransformationMode.SmoothTransformation).toImage())
            index+=1
    capture(10)
    s=w.selected;s.start()
    for i in range(5):s.history[f'DEMO-{i}']=deque([85-i*2+math.sin(j*.8)*2 for j in range(60)],maxlen=60)
    s.worker.data.emit(data(88));capture(38)
    s.pause();capture(38)
    s.start();s.worker.data.emit(data(48));capture(38)
    assert w.telemetry_transition.started_count==3
    w.close();application.processEvents()
    for index,frame in enumerate(frames):frame.save(str(out/f'frame-{index:03d}.png'))
print('Synthetic transition frames:',len(frames))
