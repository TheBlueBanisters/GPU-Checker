from PySide6.QtCore import Qt,QPoint
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from test_multihost import window,snapshot
from visuals import ModernButton
from window_chrome import WindowControl
from process_table import ALIGNMENTS


def test_table_column_geometry_and_alignment_when_resized(window):
    w=window
    w.show()
    w.connect_all()
    w.selected.worker.data.emit(snapshot(1))
    for width in (1180,1600):
        w.resize(width,960)
        QApplication.processEvents()
        header=w.table.horizontalHeader()
        assert not header.stretchLastSection()
        for col in range(8):
            assert w.table.horizontalHeaderItem(col).textAlignment()==w.table.item(0,col).textAlignment()
            assert w.table.visualItemRect(w.table.item(0,col)).left()==header.sectionViewportPosition(col)
        assert header.sectionSize(6)>header.sectionSize(7)


def test_action_buttons_reserve_space_for_icon_and_text(window):
    w=window
    w.show()
    QApplication.processEvents()
    b=w.connect_button
    for text in ('暂停监控','恢复监控'):
        b.setText(text)
        QApplication.processEvents()
        text_width=b.fontMetrics().horizontalAdvance(text)
        assert b.width()-text_width-26>=40
    QTest.mouseClick(b,Qt.MouseButton.LeftButton)
    assert not b.keyboard_focus


def test_custom_title_bar_maximize_restore_and_resize_handles(window):
    w=window
    assert w.windowFlags() & Qt.WindowType.FramelessWindowHint
    w.show()
    QApplication.processEvents()
    assert w.title_bar.height()==48
    assert len(w.resize_handles)==8
    maximize=next(c for c in w.title_bar.findChildren(WindowControl) if c.kind=='max')
    maximize.click()
    QApplication.processEvents()
    assert w.isMaximized() and all(h.isHidden() for h in w.resize_handles)
    maximize.click()
    QApplication.processEvents()
    assert not w.isMaximized() and all(not h.isHidden() for h in w.resize_handles)
    QTest.mouseDClick(w.title_bar,Qt.MouseButton.LeftButton,pos=QPoint(250,24))
    QApplication.processEvents()
    assert w.isMaximized()
    w.showNormal()
