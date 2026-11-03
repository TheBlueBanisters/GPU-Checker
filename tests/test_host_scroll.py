from PySide6.QtCore import QPoint,QPointF,Qt,QAbstractAnimation
from PySide6.QtGui import QWheelEvent
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from test_multihost import window
import profiles


def fleet(window):
    items=window.items+[profiles.clean({'host':f'extra{i}.test','autoconnect':False}) for i in range(6)]
    profiles.save(items);window.tick();window.show();QApplication.processEvents()
    return window.host_list


def wheel(listing,angle=0,pixels=0):
    point=QPointF(30,40)
    event=QWheelEvent(point,QPointF(listing.viewport().mapToGlobal(point.toPoint())),
                      QPoint(0,pixels),QPoint(0,angle),Qt.MouseButton.NoButton,
                      Qt.KeyboardModifier.NoModifier,Qt.ScrollPhase.ScrollUpdate,False)
    QApplication.sendEvent(listing.viewport(),event)


def test_host_scroll_has_intermediate_frames_and_accumulates_wheel_input(window):
    listing=fleet(window);bar=listing.verticalScrollBar()
    listing.setCurrentRow(0);bar.setValue(0)
    wheel(listing,angle=-120)
    first_target=listing.scroll_target
    assert first_target>0 and bar.value()<first_target
    QTest.qWait(70)
    assert 0<bar.value()<first_target
    wheel(listing,angle=-120)
    second_target=listing.scroll_target
    assert second_target>first_target
    QTest.qWait(270)
    assert bar.value()==round(second_target)
    assert listing.currentRow()==0 and listing.count()==8
    assert all(not s.running for s in window.sessions.values())
    wheel(listing,angle=120);QTest.qWait(270)
    assert bar.value()<second_target


def test_scrollbar_has_clear_gutter_and_manual_scroll_interrupts_animation(window):
    listing=fleet(window);bar=listing.verticalScrollBar()
    right=listing.viewport().mapTo(listing,QPoint(listing.viewport().width(),0)).x()
    assert bar.mapTo(listing,QPoint(0,0)).x()-right>=12
    wheel(listing,angle=-120)
    QTest.qWait(50)
    bar.setValue(bar.maximum())
    QTest.qWait(270)
    assert bar.value()==bar.maximum()
    assert listing.scroll_animation.state()==QAbstractAnimation.State.Stopped


def test_pixel_wheel_input_is_direct_and_hidden_scroll_stops(window):
    listing=fleet(window);bar=listing.verticalScrollBar();bar.setValue(0)
    wheel(listing,pixels=-17)
    assert bar.value()==17 and listing.scroll_animation.state()==QAbstractAnimation.State.Stopped
    wheel(listing,angle=-120);listing.hide()
    assert listing.scroll_animation.state()==QAbstractAnimation.State.Stopped
