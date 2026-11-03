import json
from pathlib import Path
import profiles
import storage
import os
import subprocess
import sys


def test_default_is_identical_under_different_appdata_overlays(tmp_path,monkeypatch):
    monkeypatch.delenv('GPUCHECKER_DATA_DIR',raising=False)
    monkeypatch.setattr(storage,'default_dir',lambda:tmp_path/'canonical')
    monkeypatch.setenv('LOCALAPPDATA',str(tmp_path/'real-AppData'))
    first=storage.data_dir(tmp_path/'app')
    monkeypatch.setenv('LOCALAPPDATA',str(tmp_path/'package-LocalCache'))
    assert storage.data_dir(tmp_path/'app')==first==tmp_path/'canonical'


def test_first_start_merges_one_host_real_view_and_eight_host_package_view(tmp_path,monkeypatch):
    monkeypatch.delenv('GPUCHECKER_DATA_DIR',raising=False)
    canonical=tmp_path/'canonical'
    real=tmp_path/'real-AppData';virtual=tmp_path/'package-LocalCache'
    entries=[profiles.clean({'host':f'host{i}.test','autoconnect':i==0}) for i in range(8)]
    legacy=profiles.clean(dict(entries[0],id='old-id-same-endpoint'))
    profiles.atomic_json(real/'profiles.json',[legacy])
    profiles.atomic_json(virtual/'host_catalog.json',{'hosts':entries,'removed':[]})
    profiles.atomic_json(virtual/'profiles.json',entries[:1])
    (virtual/'snapshots').mkdir()
    (virtual/'snapshots/example.json').write_text('{"sample":"retained"}')
    (virtual/'ssh_config').write_text('Host host0.test\n User user\n')
    monkeypatch.setattr(storage,'default_dir',lambda:canonical)
    monkeypatch.setattr(storage,'legacy_roots',lambda:[real,virtual])
    monkeypatch.setattr(profiles,'DATA',canonical)
    loaded=profiles.load()
    assert len(loaded)==8 and {p['id'] for p in loaded}=={p['id'] for p in entries}
    assert [p['autoconnect'] for p in loaded]==[p['autoconnect'] for p in entries]
    assert (canonical/'snapshots/example.json').read_text()=='{"sample":"retained"}'
    assert (canonical/'ssh_config').exists()
    assert len(list((canonical/'backups').rglob('profiles.json')))==2
    assert len(json.loads((real/'profiles.json').read_text()))==1
    assert len(json.loads((virtual/'host_catalog.json').read_text())['hosts'])==8
    for _ in range(3): assert len(profiles.load())==8
    profiles.save(loaded[:1],removed_ids={p['id'] for p in loaded[1:]})
    assert len(profiles.load())==1  # explicit deletion is never resurrected by migration


def test_existing_canonical_and_explicit_portable_data_are_not_reimported(tmp_path,monkeypatch):
    canonical=tmp_path/'canonical';portable=tmp_path/'app'
    portable.mkdir();(portable/'portable.flag').touch()
    monkeypatch.delenv('GPUCHECKER_DATA_DIR',raising=False)
    monkeypatch.setattr(storage,'default_dir',lambda:canonical)
    assert storage.data_dir(portable)==portable/'data'
    monkeypatch.setenv('GPUCHECKER_DATA_DIR',str(tmp_path/'isolated'))
    assert storage.data_dir(portable)==tmp_path/'isolated'
    monkeypatch.delenv('GPUCHECKER_DATA_DIR')
    profiles.atomic_json(canonical/'profiles.json',[])
    monkeypatch.setattr(storage,'legacy_roots',lambda:(_ for _ in ()).throw(AssertionError('Must not scan old data')))
    storage.migrate_once(canonical)
    storage.migrate_once(portable/'data')


def test_physical_path_is_reported_from_actual_file_handle(tmp_path):
    file=tmp_path/'probe.json';file.write_text('{}')
    assert storage.physical_path(file).resolve()==file.resolve()


def test_real_restarts_use_same_store_across_appdata_contexts(tmp_path):
    home=tmp_path/'home';home.mkdir()
    first=tmp_path/'package-view';second=tmp_path/'desktop-view'
    entries=[profiles.clean({'host':f'node{i}.test','autoconnect':False}) for i in range(8)]
    profiles.atomic_json(first/'GPUChecker/profiles.json',entries)
    profiles.atomic_json(second/'GPUChecker/profiles.json',entries[:1])
    source=Path(__file__).resolve().parents[1]/'src/app.py'
    expected={p['id'] for p in entries}
    for location in (first,second,first,second):
        env=dict(os.environ,USERPROFILE=str(home),LOCALAPPDATA=str(location),QT_QPA_PLATFORM='offscreen')
        env.pop('GPUCHECKER_DATA_DIR',None)
        run=subprocess.run([sys.executable,str(source),'--storage-self-test'],env=env,capture_output=True,text=True,timeout=15)
        assert run.returncode==0,run.stderr
        root=home/'.gpu-checker'
        state=json.loads((root/'runtime_state.json').read_text(encoding='utf-8'))
        assert state['visible_row_count']==state['loaded_count']==8
        assert {p['id'] for p in json.loads((root/'profiles.json').read_text(encoding='utf-8'))}==expected
        assert Path(state['physical_profile_file']).resolve()==(root/'profiles.json').resolve()
