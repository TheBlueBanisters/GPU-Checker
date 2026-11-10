import json,time,threading
from pathlib import Path
import pytest
import history_cache as cache


def row(host='host-a',gpu='uuid-a',stamp=100.,session='run-a',used=1024.,total=8192.,mem=12.,util=30.,index=3):
    return (host,gpu,stamp,session,'GPU test',index,used,total,util,mem,2.)


def test_host_and_gpu_views_preserve_uuid_and_distinguish_utilization(tmp_path):
    cache.append(tmp_path,[row(),row(gpu='uuid-b',used=3072.,total=24576.,mem=22.,index=7),row(host='other',used=999.)])
    card=cache.query(tmp_path,'host-a','uuid-a',since=90,until=110)
    assert card['rows'][0]['values']==[1.,12.]
    host=cache.query(tmp_path,'host-a',since=90,until=110)
    assert host['rows'][0]['values']==[4.,17.]
    assert [g['index'] for g in host['devices']]==[3,7]
    assert cache.query(tmp_path,'absent',since=90,until=110)['rows']==[]
    # Reopening the on-disk store needs no in-memory session or live connection.
    assert cache.query(tmp_path,'host-a','uuid-b',since=90,until=110)['rows'][0]['values'][0]==3.


def test_missing_values_are_not_zero_and_reconnects_break_series(tmp_path):
    cache.append(tmp_path,[row(stamp=100),row(stamp=102,session='run-b',used=None,mem=None),row(stamp=160,session='run-b')])
    points=cache.query(tmp_path,'host-a','uuid-a',since=90,until=170)['rows']
    assert points[1]['values'][0] is None and points[1]['values'][1] is None
    assert len({tuple(p['segment']) for p in points})==3
    assert all(p['values'][0] is None or p['values'][0]==1. for p in points)


def test_downsampling_bounds_memory_and_keeps_short_peaks(tmp_path):
    cache.append(tmp_path,[row(stamp=100+i,session=f'run-{i}',used=8192. if i==10 else 1024.) for i in range(1000)])
    result=cache.query(tmp_path,'host-a',since=100,until=1100,points=40)
    assert len(result['rows'])<=41
    assert max(p['max'][0] for p in result['rows'])==8.
    assert min(p['min'][0] for p in result['rows'])==1.
    assert cache.query(tmp_path,'host-a',cancel=threading.Event()) is not None
    cancel=threading.Event();cancel.set();assert cache.query(tmp_path,'host-a',cancel=cancel) is None


def test_quota_deletes_oldest_shards_and_protects_other_data(tmp_path):
    (tmp_path/'history_settings.json').write_text(json.dumps({'max_bytes':32_000_000}))
    sentinel=tmp_path/'profiles.json';sentinel.write_text('unchanged')
    cache.append(tmp_path,[row()]);folder=tmp_path/'history'
    old=[]
    for i in range(8):
        path=folder/f'part-{i:020d}.sqlite'
        with path.open('wb') as f:f.truncate(4*1024*1024)
        old.append(path)
    cache.append(tmp_path,[row(stamp=200)])
    assert not old[0].exists() and not old[1].exists()
    assert old[-1].exists() and sentinel.read_text()=='unchanged'
    assert cache.usage(tmp_path)<=32_000_000
    assert cache.query(tmp_path,'host-a',since=190,until=210)['rows'][0]['values'][0]==1.
    with pytest.raises(ValueError):cache.set_limit(tmp_path,1_000_000_001)
    assert cache.limit(tmp_path)<=cache.MAX_BYTES==1_000_000_000


def test_corrupt_tail_does_not_stop_future_history(tmp_path):
    folder=tmp_path/'history';folder.mkdir();(folder/'part-00000000000000000001.sqlite').write_text('corrupt')
    cache.append(tmp_path,[row()])
    result=cache.query(tmp_path,'host-a',since=90,until=110)
    assert result['rows'] and result['damaged']>0


def test_recording_is_async_scalar_only_and_invalid_numbers_are_gaps(tmp_path,monkeypatch):
    import backend
    monkeypatch.setattr(backend,'DATA',tmp_path)
    profile={'id':'host-a','interval':2}
    data={'password':'never-store-secret','processes':[{'cwd':'/private'}],
          'gpus':[{'uuid':'uuid-a','index':3,'name':'test','used':float('nan'),'total':8192.,'util':False,'mem_util':None}]}
    cache.record(profile,data,100,'run-a');assert cache.flush()
    result=cache.query(tmp_path,'host-a',since=90,until=110)
    assert result['rows'][0]['values']==[None,None]
    for path in cache.parts(tmp_path):
        raw=path.read_bytes();assert b'never-store-secret' not in raw and b'/private' not in raw

def test_history_survives_a_fresh_process(tmp_path):
    import subprocess,sys
    cache.append(tmp_path,[row()])
    code="import sys;sys.path.insert(0,sys.argv[1]);import history_cache as h;r=h.query(sys.argv[2],'host-a','uuid-a',since=90,until=110);assert r['rows'][0]['values']==[1.,12.];print('restored')"
    result=subprocess.run([sys.executable,'-c',code,str(Path(__file__).resolve().parents[1]/'src'),str(tmp_path)],capture_output=True,text=True,timeout=15)
    assert result.returncode==0 and 'restored' in result.stdout
