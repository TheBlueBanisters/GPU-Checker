import json
from PySide6.QtCore import QPoint,Qt,QEvent
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from test_multihost import window,snapshot
import app as ui
import themes
from visuals import STYLE
from dialogs import HostDialog


def test_host_hover_dwell_preserves_selection_and_workers(window):
    w=window
    w.show();w.connect_all();QApplication.processEvents()
    workers=[s.worker for s in w.sessions.values()]
    listing=w.host_list
    QTest.mouseRelease(listing.viewport(),Qt.MouseButton.LeftButton,pos=QPoint(1,1))
    listing.setCurrentRow(0)
    point=listing.visualItemRect(listing.item(1)).center()
    QTest.mouseMove(listing.viewport(),point)
    QTest.qWait(1100)
    tile=listing.itemWidget(listing.item(1))
    assert tile.hover_amount>.9 and tile.click_progress<1
    assert listing.currentRow()==0
    QTest.mouseClick(listing.viewport(),Qt.MouseButton.LeftButton,pos=point)
    assert listing.currentRow()==1
    assert [s.worker for s in w.sessions.values()]==workers
    assert all(worker.stops==0 for worker in workers)
    QApplication.sendEvent(listing.viewport(),QEvent(QEvent.Type.Leave))
    QTest.qWait(200)
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
        assert '17px' in gpu.name.styleSheet() and gpu.name.text()=='test'
        w.toggle_theme()
        assert not themes.is_day() and '#0d1d30' in w.title_bar.styleSheet()
    finally:
        old_dialog.close()
        themes.apply(application,'night',STYLE)


def test_grid_visible_on_hover_in_both_themes(window):
    w=window;w.show();w.connect_all()
    w.selected.worker.data.emit(snapshot(1));QApplication.processEvents()
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
