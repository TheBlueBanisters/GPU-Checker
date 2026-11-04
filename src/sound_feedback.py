"""Quiet, non-blocking Windows feedback; does not use a multimedia runtime."""
import sys
from pathlib import Path
from PySide6.QtGui import QGuiApplication


def play_soft_burst(widget):
    if (not widget.isVisible() or widget.window().isMinimized()
            or QGuiApplication.platformName() in ('offscreen','minimal')):
        return False
    sound=Path(getattr(sys,'_MEIPASS',Path(__file__).resolve().parents[1]))/'assets/audio/soft-burst.wav'
    if not sound.is_file():return False
    try:
        import winsound
        winsound.PlaySound(str(sound),winsound.SND_FILENAME|winsound.SND_ASYNC|winsound.SND_NODEFAULT)
    except (ImportError,OSError,RuntimeError):
        return False
    return True
