import json
import math
from PySide6.QtWidgets import QApplication
from test_multihost import window
import profiles
from instance_guard import InstanceGuard
from card_motion import combustion_stages


def test_legacy_snapshot_omission_cannot_erase_registered_hosts(window):
    extra=[profiles.clean({'host':f'gpu{i}.test','name':f'GPU {i}','autoconnect':False}) for i in range(6)]
    enrolled=profiles.save(window.items+extra)
    assert len(enrolled)==8
    # A legacy executable writes an old one-host snapshot directly.
    (profiles.DATA/'profiles.json').write_text(json.dumps(enrolled[:1]),encoding='utf-8')
    restored=profiles.load()
    assert {p['id'] for p in restored}=={p['id'] for p in enrolled}
    window.tick()
    assert window.host_list.count()==8
    fresh=type(window)(autostart=False,session_factory=window.session_factory)
    try:
        assert fresh.host_list.count()==8
        assert all(not fresh.sessions[p['id']].running for p in extra)
    finally:
        fresh.close()


def test_explicit_removal_survives_legacy_snapshot_write(window):
    old=list(window.items)
    sid=old[0]['id']
    window.remove_host()
    assert all(p['id']!=sid for p in profiles.load())
    (profiles.DATA/'profiles.json').write_text(json.dumps(old),encoding='utf-8')
    assert all(p['id']!=sid for p in profiles.load())


def test_catalog_survives_missing_snapshot(window):
    expected={p['id'] for p in profiles.load()}
    (profiles.DATA/'profiles.json').unlink()
    assert {p['id'] for p in profiles.load()}==expected


def test_instance_guard_shared_across_executable_names(window,tmp_path):
    first=InstanceGuard(tmp_path)
    second=InstanceGuard(tmp_path)
    another=InstanceGuard(tmp_path/'portable')
    try:
        first.window=window
        window.host_search.setText('nothing-matches')
        assert first.claim()
        assert not second.claim()
        QApplication.processEvents()
        assert window.host_search.text()==''
        assert another.claim()
    finally:
        first.server.close();second.server.close();another.server.close()
        first.lock.unlock();second.lock.unlock();another.lock.unlock()


def test_spark_flame_and_residual_heat_are_separate_stages():
    # Relative crank angles: plug spark, flame growth, late expansion afterglow.
    spark=combustion_stages((-.12/(4*math.pi))%1,0)
    flame=combustion_stages(.1/(4*math.pi),0)
    residual=combustion_stages(1.5/(4*math.pi),0)
    bottom=combustion_stages(.25,0)
    assert spark[0]>.95 and flame[0]<.01
    assert flame[1]>.95 and 0<residual[1]<flame[1]
    assert spark[2]<flame[2]<residual[2]
    assert bottom[0]==bottom[1]==0
