"""Bounded local scalar history, shared by all hosts. No credentials or process data."""
import json,math,os,queue,sqlite3,threading,time,uuid
from pathlib import Path
from functools import wraps
MAX_BYTES=1_000_000_000
SHARD_BYTES=4*1024*1024
RESERVE_BYTES=10*1024*1024
MIN_BYTES=32_000_000
_jobs=queue.Queue(maxsize=256)
_errors={}
_thread=None
_start_lock=threading.Lock()
_io_lock=threading.RLock()


def serialized(fn):
    @wraps(fn)
    def wrapped(*args,**kwargs):
        with _io_lock:return fn(*args,**kwargs)
    return wrapped


def clear(root):
    """Queue a purge behind older writes; later live samples may start a new shard."""
    job={'done':threading.Event(),'error':'','removed':0}
    if not _submit(('clear',Path(root),job)):
        job['error']='历史队列繁忙，请稍后重试';job['done'].set()
    return job


@serialized
def _clear(root,job):
    folder=Path(root)/'history'
    if not folder.exists():return
    if folder.is_symlink() or getattr(folder.lstat(),'st_file_attributes',0)&0x400:
        raise OSError('历史目录是链接，未执行清除')
    failed=[]
    for path in folder.iterdir():
        if path.is_symlink() or not path.is_file():continue
        name=path.name
        if not (name.startswith('part-') and any(name.endswith(s) for s in ('.sqlite','.sqlite-journal','.sqlite-wal','.sqlite-shm'))):continue
        try:
            amount=path.stat().st_size;path.unlink();job['removed']+=amount
        except OSError:failed.append(name)
    if failed:raise OSError(f'有 {len(failed)} 个历史文件暂时无法清除，请稍后重试')



def root_path():
    import backend
    return Path(backend.DATA)


def limit(root):
    try:value=int(json.loads((Path(root)/'history_settings.json').read_text(encoding='utf-8'))['max_bytes'])
    except (OSError,ValueError,KeyError,TypeError):value=MAX_BYTES
    return max(MIN_BYTES,min(MAX_BYTES,value))


def usage(root):
    folder=Path(root)/'history'
    try:return sum(p.stat().st_size for p in folder.iterdir() if p.is_file())
    except FileNotFoundError:return 0


def parts(root):
    folder=Path(root)/'history'
    return sorted(p for p in folder.glob('part-*.sqlite') if not p.is_symlink())


def prune(root,reserve=0):
    budget=limit(root);size=usage(root)
    if size+reserve<=budget:return size
    target=min(int(budget*.9),budget-reserve)
    for path in parts(root):
        # Delete only our own regular shards; never follow a path out of the cache.
        if path.parent.resolve()!=(Path(root)/'history').resolve():continue
        try:
            amount=path.stat().st_size;path.unlink();size-=amount
        except OSError:continue
        if size<=target:break
    size=usage(root)
    if size+reserve>budget:raise OSError('历史缓存无法清理到上限以内，已停止写入新历史；实时监控继续')
    return size


def set_limit(root,value):
    import profiles
    value=int(value)
    if not MIN_BYTES<=value<=MAX_BYTES:raise ValueError('历史缓存上限需为 32–1000 MB')
    profiles.atomic_json(Path(root)/'history_settings.json',{'max_bytes':value})
    _submit(('prune',Path(root),None))


def number(value,percent=False):
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or value<0:return None
    if percent and value>100:return None
    return float(value)


def record(profile,data,stamp,session):
    rows=[]
    for gpu in data.get('gpus',[])[:256]:
        if not isinstance(gpu.get('uuid'),str) or not gpu['uuid']:continue
        used,total=number(gpu.get('used')),number(gpu.get('total'))
        if total==0 or (used is not None and total is not None and used>total):used=total=None
        rows.append((profile['id'],gpu['uuid'][:128],float(stamp),session,str(gpu.get('name','GPU'))[:256],
                     gpu.get('index') if isinstance(gpu.get('index'),int) else None,used,None,None,number(gpu.get('mem_util'),True),float(profile.get('interval',2))))
    if rows:_submit(('write',root_path(),rows))


def _submit(job):
    global _thread
    with _start_lock:
        if _thread is None:
            _thread=threading.Thread(target=_run,name='gpu-history-cache',daemon=True);_thread.start()
    try:_jobs.put_nowait(job);return True
    except queue.Full:
        _errors[str(job[1])]='历史写入队列已满，部分历史点未保存；实时监控继续'
        return False


def _run():
    while True:
        action,root,rows=_jobs.get()
        try:
            if action=='write':append(root,rows)
            elif action=='clear':_clear(root,rows)
            else:prune(root)
            _errors.pop(str(root),None)
        except Exception as exc:
            if action=='clear':rows['error']=str(exc)
            _errors[str(root)]='历史缓存操作失败：'+str(exc)
            if len(_errors)>32:_errors.pop(next(iter(_errors)))
        finally:
            if action=='clear':rows['done'].set()
            _jobs.task_done()


def flush(timeout=3):
    deadline=time.monotonic()+timeout
    while _jobs.unfinished_tasks and time.monotonic()<deadline:time.sleep(.01)
    return not _jobs.unfinished_tasks


def error(root):return _errors.get(str(root),'')


@serialized
def append(root,rows):
    folder=Path(root)/'history';folder.mkdir(parents=True,exist_ok=True)
    prune(root,RESERVE_BYTES)
    files=parts(root)
    path=files[-1] if files and files[-1].stat().st_size<SHARD_BYTES-131072 else folder/f'part-{time.time_ns():020d}-{uuid.uuid4().hex[:6]}.sqlite'
    try:write_part(path,rows)
    except sqlite3.DatabaseError:
        path=folder/f'part-{time.time_ns():020d}-{uuid.uuid4().hex[:6]}.sqlite'
        write_part(path,rows)
    prune(root)


def write_part(path,rows):
    connection=sqlite3.connect(path,timeout=.5)
    try:
        connection.execute('PRAGMA journal_mode=DELETE');connection.execute('PRAGMA synchronous=NORMAL')
        connection.execute('PRAGMA page_size=4096');connection.execute('PRAGMA max_page_count=1024')
        connection.execute('CREATE TABLE IF NOT EXISTS samples (host TEXT, gpu TEXT, ts REAL, session TEXT, name TEXT, idx INTEGER, used REAL, total REAL, util REAL, mem_util REAL, interval REAL, PRIMARY KEY(host,gpu,ts,session))')
        connection.execute('CREATE INDEX IF NOT EXISTS by_host_time ON samples(host,ts,session)')
        connection.execute('CREATE TABLE IF NOT EXISTS devices (host TEXT,gpu TEXT,name TEXT,idx INTEGER,seen REAL,PRIMARY KEY(host,gpu))')
        connection.executemany('INSERT OR REPLACE INTO samples VALUES (?,?,?,?,?,?,?,?,?,?,?)',rows)
        connection.executemany('INSERT OR REPLACE INTO devices VALUES (?,?,?,?,?)',[(r[0],r[1],r[4],r[5],r[2]) for r in rows])
        connection.commit()
    finally:connection.close()


def read_connection(path,cancel):
    c=sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True,timeout=.2)
    c.execute('PRAGMA query_only=ON');c.execute('PRAGMA cache_size=-512')
    c.set_progress_handler(lambda:int(cancel.is_set()),1000)
    return c


@serialized
def query(root,host,gpu=None,since=None,until=None,points=1200,cancel=None):
    cancel=cancel or threading.Event();until=until or time.time();files=parts(root)
    devices={};earliest=until;damaged=0
    for path in files:
        if cancel.is_set():return None
        c=None
        try:
            with read_connection(path,cancel) as c:
                for uid,name,index,seen in c.execute('SELECT gpu,name,idx,seen FROM devices WHERE host=?',(host,)):
                    if uid not in devices or devices[uid]['seen']<seen:devices[uid]={'uuid':uid,'name':name,'index':index,'seen':seen}
                row=c.execute('SELECT MIN(ts) FROM samples WHERE host=?',(host,)).fetchone()
                if row[0] is not None:earliest=min(earliest,row[0])
        except (sqlite3.Error,OSError):damaged+=1
        finally:
            if c:c.close()
    start=since if since is not None else earliest
    span=max(1.,until-start);bucket=span/max(2,min(2000,points));bins={};last={};segments={}
    for path in files:
        if cancel.is_set():return None
        c=None
        try:
            c=read_connection(path,cancel)
            where='host=? AND ts>=? AND ts<=?';args=[host,start,until]
            if gpu:where+=' AND gpu=?';args.append(gpu)
            # Aggregation is per successful host sample; partial/unknown totals remain gaps.
            sql='SELECT ts,session,SUM(used),COUNT(used),COUNT(*),AVG(mem_util),COUNT(mem_util),MAX(interval) FROM samples WHERE '+where+' GROUP BY ts,session ORDER BY ts'
            for ts,session,used,nu,n,mem,nmem,interval in c.execute(sql,args):
                if cancel.is_set():return None
                if session in last and ts-last[session]>max(10,interval*3):segments[session]=segments.get(session,0)+1
                last[session]=ts
                segment=(session,segments.get(session,0))
                key=int((ts-start)/bucket)
                if len(last)>256:
                    oldest=next(iter(last));last.pop(oldest);segments.pop(oldest,None)
                values=(used/1024 if used is not None and nu==n else None,mem if nmem==n else None)
                item=bins.setdefault(key,{'t':ts,'segment':segment,'stats':[[0.,0,None,None] for _ in range(2)]})
                if item['segment']!=segment:item['segment']=('mixed',key)
                for stat,value in zip(item['stats'],values):
                    if value is not None:
                        stat[0]+=value;stat[1]+=1;stat[2]=value if stat[2] is None else min(stat[2],value);stat[3]=value if stat[3] is None else max(stat[3],value)
        except (sqlite3.Error,OSError):damaged+=1
        finally:
            if c:c.close()
    rows=[]
    for item in sorted(bins.values(),key=lambda item:item['t']):
        rows.append({'t':item['t'],'segment':item['segment'],'values':[s[0]/s[1] if s[1] else None for s in item['stats']],
                     'min':[s[2] for s in item['stats']],'max':[s[3] for s in item['stats']]})
    return {'rows':rows,'devices':sorted(devices.values(),key=lambda g:(g['index'] is None,g['index'] or 0,g['uuid'])),
            'start':start,'end':until,'oldest':earliest,'damaged':damaged,'usage':usage(root),'limit':limit(root),'error':error(root)}
