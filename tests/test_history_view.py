from PySide6.QtCore import Qt,QPoint
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from test_multihost import window,snapshot
import history_cache
import time


def wait_for(predicate):
    for _ in range(200):
        QApplication.processEvents()
        if predicate():return
        QTest.qWait(10)
    raise AssertionError('History UI did not finish loading')


def test_gpu_history_button_is_not_an_engine_click_and_host_button_keeps_selection(window):
    window.show();window.connect_all();window.selected.worker.data.emit(snapshot(1))
    assert history_cache.flush()
    card=next(iter(window.cards.values()));heat=card.motion.click_heat
    QTest.mouseClick(card.history_button,Qt.MouseButton.LeftButton)
    assert card.motion.click_heat==heat
    dialog=window.history_windows[-1];wait_for(lambda:dialog.memory.payload is not None)
    assert dialog.active_gpu=='GPU-1' and dialog.memory.payload['rows']
    assert dialog.percent.payload['rows'][0]['values'][1] is None
    assert not dialog.memory.grab().isNull()
    dialog.close();QApplication.processEvents()
    original=window.selected_id;listing=window.host_list;item=listing.item(1)
    listing.scrollToItem(item);QApplication.processEvents()
    tile=listing.itemWidget(item)
    point=tile.history_button.mapTo(listing.viewport(),tile.history_button.rect().center())
    QTest.mouseClick(listing.viewport(),Qt.MouseButton.LeftButton,pos=point)
    assert window.selected_id==original
    host_dialog=window.history_windows[-1];assert host_dialog.host_id!=original and host_dialog.active_gpu is None
    wait_for(lambda:host_dialog.memory.payload is not None)
    assert not host_dialog.memory.payload['rows']
    host_dialog.close()


def test_only_fresh_samples_are_recorded_and_quota_setting_persists(window):
    window.show();window.connect_all();session=window.selected
    data=snapshot(1);data['gpus'][0]['mem_util']=42.
    session.worker.data.emit(data);assert history_cache.flush()
    session.pause();root=history_cache.root_path()
    result=history_cache.query(root,session.id,'GPU-1')
    assert result['rows'] and result['rows'][0]['values'][1]==42.
    before=result['rows']
    window.render_status();window.render_status();assert history_cache.flush()
    assert history_cache.query(root,session.id,'GPU-1')['rows']==before
    window.show_history(session.id)
    dialog=window.history_windows[-1];wait_for(lambda:dialog.memory.payload is not None)
    dialog.quota.setValue(64);dialog.apply_limit();assert history_cache.flush()
    assert history_cache.limit(root)==64_000_000
    dialog.close()


def test_memory_utilization_is_read_independently_from_capacity():
    from remote_probe import parse_xml
    data=parse_xml('<nvidia_smi_log><gpu><uuid>uuid-test</uuid><utilization><gpu_util>91 %</gpu_util><memory_util>17 %</memory_util></utilization><fb_memory_usage><used>4096 MiB</used><total>8192 MiB</total></fb_memory_usage></gpu></nvidia_smi_log>')
    assert data['gpus'][0]['mem_util']==17. and data['gpus'][0]['used']==4096.

def test_history_failure_does_not_interrupt_live_monitor(window):
    root=history_cache.root_path();(root/'history').write_text('not a directory')
    window.connect_all();session=window.selected
    session.worker.data.emit(snapshot(1));assert history_cache.flush()
    assert session.fresh and session.worker.isRunning()
    assert history_cache.error(root)

def test_dialog_blurs_only_body_and_nested_close_restores_it(window):
    from dialogs import HostDialog
    window.show();window.connect_all();window.selected.worker.data.emit(snapshot(1));QApplication.processEvents()
    worker=window.selected.worker
    before=window.content_body.grab().toImage();geometry=(window.title_bar.geometry(),window.table.geometry())
    outer=HostDialog(window,window.selected.profile);outer.show();QTest.qWait(180)
    shade=window.dialog_focus.overlay
    assert shade is not None and shade.parentWidget() is window.content_body
    assert shade.frame!=before and shade.geometry()==window.content_body.rect()
    assert window.title_bar.graphicsEffect() is None
    assert window.content_body.mapTo(window,QPoint()).y()>=window.title_bar.geometry().bottom()
    inner=HostDialog(outer,window.selected.profile);inner.show();QApplication.processEvents()
    assert window.dialog_focus.overlay is shade
    inner.close();QApplication.processEvents();assert window.dialog_focus.overlay is shade
    outer.close();QApplication.processEvents();assert window.dialog_focus.overlay is None
    assert geometry==(window.title_bar.geometry(),window.table.geometry())
    assert window.selected.worker is worker and worker.stops==0


def test_focus_shade_tracks_resize_and_history_settings_are_collapsed(window):
    window.show();window.connect_all();window.selected.worker.data.emit(snapshot(1));window.show_history(window.selected_id)
    dialog=window.history_windows[-1];wait_for(lambda:dialog.memory.payload is not None)
    assert dialog.details_panel.isHidden()
    dialog.details_toggle.click();QApplication.processEvents();assert not dialog.details_panel.isHidden()
    dialog.details_toggle.click();QApplication.processEvents();assert dialog.details_panel.isHidden()
    window.resize(1180,850);QTest.qWait(100)
    shade=window.dialog_focus.overlay;assert shade.geometry()==window.content_body.rect()
    assert not shade.frame.isNull()
    import themes
    before=shade.frame.copy();window.toggle_theme();QTest.qWait(720)
    assert window.dialog_focus.overlay.frame!=before
    dialog.close();QApplication.processEvents();assert window.dialog_focus.overlay is None

def test_history_has_two_curves_clear_window_border_and_linked_time_zoom(window):
    from PySide6.QtGui import QWheelEvent
    from PySide6.QtCore import QPointF
    from themes import color
    window.show();window.connect_all();window.selected.worker.data.emit(snapshot(1));window.show_history(window.selected_id)
    dialog=window.history_windows[-1];wait_for(lambda:dialog.memory.payload is not None and dialog.worker is None)
    from visuals import MechPanel
    assert dialog.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
    assert all(panel.property('squarePanel') for panel in dialog.findChildren(MechPanel))
    assert dialog.memory.indices==(0,) and dialog.percent.indices==(1,)
    assert len(dialog.percent.payload['rows'][0]['values'])==2
    edge=dialog.grab().toImage().pixelColor(dialog.width()//2,1)
    expected=color('#65bde9')
    assert max(abs(a-b) for a,b in zip(edge.getRgb()[:3],expected.getRgb()[:3]))<45
    chart=dialog.memory;before=chart.payload['end']-chart.payload['start']
    point=QPointF(chart.width()/2,chart.height()/2)
    wheel=QWheelEvent(point,point,QPoint(),QPoint(0,120),Qt.MouseButton.NoButton,Qt.KeyboardModifier.NoModifier,Qt.ScrollPhase.NoScrollPhase,False)
    QApplication.sendEvent(chart,wheel)
    wait_for(lambda:dialog.worker is None)
    after=chart.payload['end']-chart.payload['start']
    assert after<before and dialog.view_range is not None
    assert (chart.payload['start'],chart.payload['end'])==(dialog.percent.payload['start'],dialog.percent.payload['end'])
    old=dialog.view_range[0]
    QTest.mousePress(chart,Qt.MouseButton.LeftButton,pos=point.toPoint())
    QTest.mouseMove(chart,point.toPoint()+QPoint(35,0))
    QTest.mouseRelease(chart,Qt.MouseButton.LeftButton,pos=point.toPoint()+QPoint(35,0))
    wait_for(lambda:dialog.worker is None)
    assert dialog.view_range[0]<old
    QTest.mouseDClick(chart,Qt.MouseButton.LeftButton,pos=point.toPoint());wait_for(lambda:dialog.worker is None)
    assert dialog.view_range is None and chart.payload['end']-chart.payload['start']>=before-1
    dialog.close()

def test_history_scrollbar_has_gaps_to_body_and_outer_frame(window):
    window.show();window.connect_all();window.selected.worker.data.emit(snapshot(1))
    window.show_history(window.selected_id);dialog=window.history_windows[-1]
    dialog.resize(760,440);dialog.details_toggle.setChecked(True)
    wait_for(lambda:dialog.history_scroll.verticalScrollBar().isVisible())
    scroll=dialog.history_scroll;bar=scroll.verticalScrollBar();body=scroll.widget()
    body_right=body.mapTo(dialog,QPoint(body.width(),0)).x()
    bar_left=bar.mapTo(dialog,QPoint()).x()
    bar_right=bar.mapTo(dialog,QPoint(bar.width(),0)).x()
    assert bar_left-body_right>=10
    assert dialog.width()-bar_right>=16
    assert bar.width()<=12
    dialog.close()
