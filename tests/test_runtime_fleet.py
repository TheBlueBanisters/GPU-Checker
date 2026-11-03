import json
import profiles
from test_multihost import window


def test_startup_uses_complete_saved_enrollment_after_stale_read(window,monkeypatch):
    # Reproduce an old one-host in-memory read followed by catalog recovery.
    complete=profiles.load()
    monkeypatch.setattr(profiles,'load',lambda:complete[:1])
    fresh=type(window)(autostart=False,session_factory=window.session_factory)
    try:
        assert len(fresh.items)==len(fresh.sessions)==fresh.host_list.count()==2
        state=json.loads((profiles.DATA/'runtime_state.json').read_text(encoding='utf-8'))
        assert state['loaded_count']==state['session_count']==state['visible_row_count']==2
        assert state['load_error']==''
    finally:
        fresh.close()


def test_catalog_only_revision_reloads_visible_rows(window):
    catalog=profiles.catalog()
    catalog['hosts'].append(profiles.clean({'host':'later.test','autoconnect':False}))
    profiles.atomic_json(profiles.DATA/'host_catalog.json',catalog)
    window.tick()
    assert window.host_list.count()==3
    assert any(p['host']=='later.test' for p in window.items)


def test_missing_ui_rows_are_rebuilt_without_disk_change(window):
    window.host_list.clear()
    assert window.host_list.count()==0
    window.tick()
    assert window.host_list.count()==len(window.items)==len(window.sessions)==2
