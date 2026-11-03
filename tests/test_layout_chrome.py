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


def test_host_actions_equal_and_process_count_separate(window):
    w=window
    w.show()
    QApplication.processEvents()
    buttons=(w.connect_button,w.edit_button,w.remove_button)
    assert len({(b.width(),b.height()) for b in buttons})==1
    w.connect_all()
    w.selected.worker.data.emit(snapshot(1))
    assert w.process_title.text()=='用卡进程' and w.process_count.text()=='01'
    assert w.badge.height()==26


def test_process_hover_highlights_row_without_changing_selection(window):
    from PySide6.QtCore import QEvent
    w=window
    w.show();w.connect_all()
    data=snapshot(1)
    data['processes'].append(dict(data['processes'][0],pid='999'))
    w.selected.worker.data.emit(data)
    w.table.selectRow(1)
    QApplication.processEvents()
    rect=w.table.visualItemRect(w.table.item(0,2))
    QTest.mouseMove(w.table.viewport(),rect.center())
    assert w.table.hovered_row==0
    assert w.table.selectionModel().selectedRows()[0].row()==1
    QApplication.sendEvent(w.table.viewport(),QEvent(QEvent.Type.Leave))
    assert w.table.hovered_row==-1


def test_host_tints_and_no_gpu_gray_hint(window):
    a,b=list(window.sessions.values())
    assert window.tiles[a.id].property('hostTone')!=window.tiles[b.id].property('hostTone')
    b.gpu_hint='no_gpu'
    window.host_changed(b.id)
    assert window.tiles[b.id].property('noGpu') is True
    assert '无 GPU' in window.tiles[b.id].capacity.text()


def test_availability_is_invalidated_on_pause_staleness_and_resume(window,monkeypatch):
    import sessions
    from test_availability import gpu
    clock=[100.]
    monkeypatch.setattr(sessions.time,'monotonic',lambda:clock[0])
    w=window;w.connect_all();s=w.selected
    data=snapshot(1)
    data['gpus'][0].update(gpu(uuid=data['gpus'][0]['uuid']))
    data['processes']=[]
    for now in (100.,105.,110.):
        clock[0]=now;s.worker.data.emit(data)
    assert s.availability_counts()['idle']==1 and s.availability_counts()['available']==1
    uuid=data['gpus'][0]['uuid']
    s.pause()
    assert s.availability_counts() is None and not s.gpu_availability(uuid)['available']
    s.start();clock[0]=120.;s.worker.data.emit(data)
    assert s.gpu_availability(uuid)['status']=='observing'
    clock[0]=1000.;s.refresh_age()
    assert s.availability_counts() is None and s.gpu_availability(uuid)['status']=='unknown'


def test_panel_feedback_on_child_labels_is_cosmetic_and_finishes(window):
    from PySide6.QtCore import QAbstractAnimation
    w=window
    w.show()
    w.connect_all()
    s=w.selected
    s.worker.data.emit(snapshot(1))
    QApplication.processEvents()
    gpu=next(iter(w.cards.values()))
    before_worker=s.worker
    before_samples=s.sample_count
    QTest.mouseMove(gpu.metric_label,QPoint(15,10))
    QTest.qWait(200)
    assert gpu.hover_amount>.9
    QTest.mouseClick(gpu.metric_label,Qt.MouseButton.LeftButton,pos=QPoint(15,10))
    QTest.qWait(80)
    assert 0<gpu.click_progress<1
    assert s.worker is before_worker and s.sample_count==before_samples and s.desired
    QTest.qWait(650)
    assert gpu.click_animation.state()==QAbstractAnimation.State.Stopped
    assert gpu.click_progress==1.
    summary=w.stats[0].parentWidget()
    QTest.mouseClick(w.stats[0],Qt.MouseButton.LeftButton,pos=QPoint(5,5))
    QTest.qWait(40)
    assert summary.click_progress<1 and s.worker is before_worker
    summary.hide()
    assert summary.click_animation.state()==QAbstractAnimation.State.Stopped


def test_password_pause_resumes_without_edit_dialog(window,monkeypatch):
    import profiles,vault
    s=window.selected
    s.profile['mode']=profiles.MODES[2]
    s.pause()
    monkeypatch.setattr(vault,'get_password',lambda p:'test-only-secret')
    monkeypatch.setattr(window,'edit_host',lambda **k: (_ for _ in ()).throw(AssertionError('Unexpected edit dialog')))
    window.toggle_selected()
    assert s.running and s.desired and window.host_list.count()==2


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
