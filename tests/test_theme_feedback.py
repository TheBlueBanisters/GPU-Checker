import json
from PySide6.QtCore import QPoint,Qt,QEvent
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from test_multihost import window,snapshot
import app as ui
import themes
from visuals import STYLE
from dialogs import HostDialog
from shiboken6 import isValid


def test_theme_crossfade_can_reverse_without_moving_layout_and_cleans_on_resize(window):
    w=window;application=QApplication.instance();themes.apply(application,'night',STYLE)
    w.show();w.resize(1280,900);w.connect_all();w.selected.worker.data.emit(snapshot(1))
    QApplication.processEvents();QTest.qWait(1000)
    worker=w.selected.worker
    widgets=(w.table,w.details,w.card_scroll,w.status_text,*[value.parentWidget() for value in w.stats])
    def geometry():return [(widget.mapTo(w,QPoint()).toTuple(),widget.size().toTuple()) for widget in widgets]
    baseline=geometry()
    w.toggle_theme();QApplication.processEvents();QTest.qWait(150)
    first=w.theme_transition.overlay
    assert first and 0<first.progress<1 and themes.is_day()
    assert first.testAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
    assert geometry()==baseline and w.selected.worker is worker and worker.stops==0
    w.toggle_theme();QApplication.processEvents();QTest.qWait(100)
    assert not themes.is_day() and w.theme_transition.overlay is not first
    assert not isValid(first) or not first.isVisible()
    assert geometry()==baseline
    QTest.qWait(650);assert w.theme_transition.overlay is None
    w.toggle_theme();w.resize(1360,900);QApplication.processEvents()
    assert w.theme_transition.overlay is None
    w.toggle_theme();w.close();assert w.theme_transition.overlay is None


def test_host_hover_dwell_preserves_selection_and_workers(window):
    w=window
    w.show();w.connect_all();QApplication.processEvents()
    workers=[s.worker for s in w.sessions.values()]
    listing=w.host_list
    QTest.mouseRelease(listing.viewport(),Qt.MouseButton.LeftButton,pos=QPoint(1,1))
    listing.setCurrentRow(0)
    w.side_scroll.ensureWidgetVisible(listing)
    listing.scrollToItem(listing.item(1))
    QApplication.processEvents()
    point=listing.visualItemRect(listing.item(1)).center()
    QTest.mouseMove(listing.viewport(),point)
    QTest.qWait(1650)
    tile=listing.itemWidget(listing.item(1))
    assert tile.hover_amount>.9 and tile.click_progress<1
    assert listing.currentRow()==0
    QTest.mouseClick(listing.viewport(),Qt.MouseButton.LeftButton,pos=point)
    assert listing.currentRow()==1
    assert [s.worker for s in w.sessions.values()]==workers
    assert all(worker.stops==0 for worker in workers)
    QApplication.sendEvent(listing.viewport(),QEvent(QEvent.Type.Leave))
    QTest.qWait(300)
    assert not listing.wave_timer.isActive() and tile.hover_amount==0


def test_theme_updates_existing_and_new_widgets_and_persists(window):
    w=window
    application=QApplication.instance()
    themes.apply(application,'night',STYLE)
    w.show();w.connect_all();w.selected.worker.data.emit(snapshot(1))
    QApplication.processEvents()
    workers=[s.worker for s in w.sessions.values()]
    old_dialog=HostDialog(w,w.selected.profile)
    try:
        w.title_bar.theme_button.click()
        QApplication.processEvents()
        assert themes.is_day()
        assert json.loads((ui.DATA/'ui_preferences.json').read_text())['theme']=='day'
        assert '#e0edf3' in w.title_bar.styleSheet()
        assert '切换夜间' in w.title_bar.theme_button.toolTip()
        new_dialog=HostDialog(w,w.selected.profile)
        assert old_dialog.styleSheet()==new_dialog.styleSheet()
        new_dialog.close()
        ui.configure_app(application)
        assert themes.is_day()
        assert [s.worker for s in w.sessions.values()]==workers
        gpu=next(iter(w.cards.values()))
        assert f"{round(21*w.property('uiDensity'))}px" in gpu.name.styleSheet() and gpu.name.text()=='test'
        w.toggle_theme()
        assert not themes.is_day() and '#0d1d30' in w.title_bar.styleSheet()
    finally:
        old_dialog.close()
        themes.apply(application,'night',STYLE)


def test_grid_visible_on_hover_in_both_themes(window):
    w=window;w.show();w.connect_all()
    w.selected.worker.data.emit(snapshot(1));QApplication.processEvents()
    QTest.qWait(700)  # Assert steady-state grid contrast after the entry fade.
    table=w.table
    for mode in ('night','day'):
        themes.apply(QApplication.instance(),mode,STYLE)
        QTest.mouseMove(table.viewport(),table.visualItemRect(table.item(0,0)).center())
        QApplication.processEvents()
        image=table.viewport().grab().toImage()
        rect=table.visualItemRect(table.item(0,0))
        border=image.pixelColor(rect.right(),rect.top()+5)
        fill=image.pixelColor(rect.right()-5,rect.top()+5)
        assert sum(abs(border.getRgb()[i]-fill.getRgb()[i]) for i in range(3))>60
    themes.apply(QApplication.instance(),'night',STYLE)


def test_repeated_theme_switch_after_dialog_destruction(window):
    from PySide6.QtCore import QCoreApplication
    window.show()
    for i in range(12):
        dialog=HostDialog(window,window.selected.profile)
        dialog.show();QApplication.processEvents()
        dialog.close();dialog.deleteLater()
        QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete)
        themes.apply(QApplication.instance(),'day' if i%2==0 else 'night',STYLE)
        QApplication.processEvents()
        assert window.isVisible()
    themes.apply(QApplication.instance(),'night',STYLE)
