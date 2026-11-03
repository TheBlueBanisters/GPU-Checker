"""Isolated visual state demo; all GPU values are explicitly synthetic."""
import os,sys
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from PySide6.QtWidgets import QApplication,QVBoxLayout,QHBoxLayout
from PySide6.QtCore import Qt,QPoint
from PySide6.QtTest import QTest
import app as ui
from visuals import Backdrop,GPUCard,label,STYLE
from availability import result
import themes
application=QApplication([]);ui.configure_app(application);themes.apply(application,'night',STYLE)
w=Backdrop();w.resize(1240,340)
layout=QVBoxLayout(w);layout.setContentsMargins(20,14,20,20)
layout.addWidget(label('机械运转动效演示 · 以下为模拟状态，不代表实时遥测','section'))
row=QHBoxLayout();layout.addLayout(row)
cards=[]
for i,status in enumerate(('busy','available','idle','blocked','unknown')):
 g={'index':i,'uuid':str(i),'name':'GeForce RTX 4090','state':'P0','util':96 if i==0 else 0,'used':13000. if i==0 else 0.,'total':24576.,'temp':75.,'power':250.,'fan':'40 %'}
 state=result(status,'模拟动效状态')
 if i==4: state.update(visual='disconnected',label='连接中断')
 card=GPUCard(g,[g['util']]*60,state);row.addWidget(card);cards.append(card)
w.show();QApplication.processEvents()
out=Path(__file__).resolve().parents[1]/'build/motion-frames';out.mkdir(parents=True,exist_ok=True)
QTest.mouseMove(w,QPoint(5,5))
for i in range(90):
 QTest.qWait(50)
 if i==10: cards[0].pulse_at(QPoint(35,120))
 if i==18: cards[0].pulse_at(QPoint(145,170))
 if i==26: cards[0].pulse_at(QPoint(90,60))
 w.grab().save(str(out/f'frame-{i:03d}.png'))
w.close()
print('Saved 90 synthetic animation frames')
