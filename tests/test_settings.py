from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication
from test_multihost import window,snapshot
from test_history_view import wait_for
from test_history_cache import row
import history_cache as cache


def test_clear_history_orders_writes_and_protects_other_files(tmp_path):
    sentinel=tmp_path/'profiles.json';sentinel.write_text('profile')
    snap=tmp_path/'snapshots';snap.mkdir();(snap/'last.json').write_text('snapshot')
    cache._submit(('write',tmp_path,[row()]))
    job=cache.clear(tmp_path)
    assert job['done'].wait(3) and not job['error'] and job['removed']>0
    assert cache.usage(tmp_path)==0
    assert sentinel.read_text()=='profile' and (snap/'last.json').read_text()=='snapshot'
    # Live monitoring can immediately continue after the purge.
    cache._submit(('write',tmp_path,[row(stamp=200)]));assert cache.flush()
    assert cache.query(tmp_path,'host-a',since=190,until=210)['rows']
    other=tmp_path/'history'/'keep.txt';other.write_text('untouched')
    job=cache.clear(tmp_path);assert job['done'].wait(3) and not job['error']
    assert other.read_text()=='untouched'


def test_settings_entry_blur_size_clear_and_monitor_continuity(window):
    window.show();window.connect_all();window.selected.worker.data.emit(snapshot(1));assert cache.flush()
    worker=window.selected.worker;profiles_before=(cache.root_path()/'profiles.json').read_bytes()
    toolbar=window.title_bar
    assert toolbar.settings_button.geometry().right()<toolbar.theme_button.geometry().left()
    toolbar.settings_button.click();QApplication.processEvents()
    dialog=window.settings_window
    assert dialog.isVisible() and dialog.width()<=520 and dialog.height()<450
    assert window.dialog_focus.overlay is not None and dialog.clear_button.isEnabled()
    assert dialog.size_label.text()!='—'
    assert dialog.clear_button.parentWidget() is dialog.cache_panel
    assert dialog.size_label.parentWidget() is dialog.cache_panel
    window.show_settings();assert window.settings_window is dialog
    dialog.clear_button.click();wait_for(lambda:dialog.job is not None and dialog.job['done'].is_set())
    dialog.refresh();assert dialog.status.text()=='历史已清除'
    assert cache.usage(cache.root_path())==0 and not dialog.clear_button.isEnabled()
    assert (cache.root_path()/'profiles.json').read_bytes()==profiles_before
    assert window.selected.worker is worker and worker.stops==0
    window.selected.worker.data.emit(snapshot(1));assert cache.flush()
    dialog.refresh();assert dialog.clear_button.isEnabled()
    dialog.close();QApplication.processEvents();assert window.dialog_focus.overlay is None
