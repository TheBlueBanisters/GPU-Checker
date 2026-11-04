import math,struct,wave
from pathlib import Path
from test_multihost import window,snapshot
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QPointF


def test_explosion_audio_fires_once_at_impact_and_never_on_normal_click(window,monkeypatch):
    import click_burst
    calls=[];monkeypatch.setattr(click_burst,'play_soft_burst',lambda widget:calls.append(widget))
    window.show();window.connect_all();window.selected.worker.data.emit(snapshot(1));QApplication.processEvents()
    card=next(iter(window.cards.values()))
    card.pulse_at(QPointF(20,20));assert not calls
    for _ in range(7):card.pulse_at(QPointF(20,20))
    burst=card.motion.burst;assert burst is not None
    burst.animation.pause();burst.advance(.04);assert not calls
    burst.advance(.06);assert calls==[burst]
    for progress in (.1,.2,.3,.5,.8,1.):burst.advance(progress)
    assert len(calls)==1
    burst.finish();burst.advance(.1);assert len(calls)==1


def test_original_sound_is_short_low_amplitude_pcm():
    with wave.open(str(Path(__file__).resolve().parents[1]/'assets/audio/soft-burst.wav'),'rb') as f:
        assert f.getnchannels()==1 and f.getsampwidth()==2
        assert .15<f.getnframes()/f.getframerate()<.3
        samples=struct.unpack('<'+'h'*f.getnframes(),f.readframes(f.getnframes()))
    peak=max(abs(v) for v in samples)/32768
    rms=math.sqrt(sum(v*v for v in samples)/len(samples))/32768
    assert .05<peak<.15 and .005<rms<.04

def test_audio_backend_uses_async_file_playback_and_handles_failure(monkeypatch):
    import sys,types,sound_feedback
    monkeypatch.setattr(sound_feedback,'QGuiApplication',types.SimpleNamespace(platformName=lambda:'windows'))
    widget=types.SimpleNamespace(isVisible=lambda:True,window=lambda:types.SimpleNamespace(isMinimized=lambda:False))
    calls=[]
    backend=types.SimpleNamespace(SND_FILENAME=1,SND_ASYNC=2,SND_NODEFAULT=4,PlaySound=lambda path,flags:calls.append((path,flags)))
    monkeypatch.setitem(sys.modules,'winsound',backend)
    assert sound_feedback.play_soft_burst(widget)
    assert calls[0][1]==7 and Path(calls[0][0]).is_file()
    def fail(*args):raise RuntimeError('no sound device')
    backend.PlaySound=fail
    assert not sound_feedback.play_soft_burst(widget)
