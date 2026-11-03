"""One atomic, credential-free last-good snapshot per saved host, local only."""
import hashlib
import json
import math
import profiles
import vault

GPU_FIELDS=set('index uuid name util used total free temp power fan state compute_mode mig_mode recovery_action slowdown_temp remap_failure minor_number process_query_ok ecc_uncorrectable device_access'.split())
PROCESS_FIELDS=set('gpu uuid pid user uid kind memory name cwd exe start ppid instance'.split())
MAX_BYTES=8*1024*1024


def path_for(profile):
    key=hashlib.sha256(profile['id'].encode()).hexdigest()
    return profiles.DATA/'snapshots'/(key+'.json')


def endpoint(profile):
    return hashlib.sha256(vault.target(profile).encode()).hexdigest()


def fields(record,allowed):
    return {k:v for k,v in record.items() if k in allowed and
            (v is None or isinstance(v,(int,float,bool,str)))}


def clean_data(data):
    if not isinstance(data,dict) or not isinstance(data.get('gpus'),list) or not isinstance(data.get('processes'),list):
        raise ValueError('Invalid snapshot')
    if len(data['gpus'])>256 or len(data['processes'])>20000:
        raise ValueError('Oversized snapshot')
    gpus=[fields(g,GPU_FIELDS) for g in data['gpus']]
    processes=[fields(p,PROCESS_FIELDS) for p in data['processes']]
    required={'index','uuid','name','util','used','total','temp','power','fan','state'}
    if any(not required.issubset(g) or not isinstance(g['uuid'],str) for g in gpus):
        raise ValueError('Incomplete GPU snapshot')
    for g in gpus:
        if not isinstance(g['index'],int) or isinstance(g['index'],bool) or g['index']<0: raise ValueError('Invalid GPU index')
        if any(not isinstance(g[k],str) for k in ('uuid','name','fan','state')): raise ValueError('Invalid GPU text')
        for key in ('util','used','total','temp','power'):
            value=g[key]
            if value is not None and (isinstance(value,bool) or not isinstance(value,(float,int)) or not math.isfinite(value)):
                raise ValueError('Invalid GPU metric')
    if any(not {'gpu','uuid','pid','kind','memory','name'}.issubset(p) for p in processes):
        raise ValueError('Incomplete process snapshot')
    for p in processes:
        if not isinstance(p['gpu'],int) or isinstance(p['gpu'],bool): raise ValueError('Invalid process GPU')
        if any(not isinstance(p[k],str) for k in ('uuid','pid','kind','name')): raise ValueError('Invalid process text')
        value=p['memory']
        if value is not None and (isinstance(value,bool) or not isinstance(value,(float,int)) or not math.isfinite(value)):
            raise ValueError('Invalid process memory')
    result={'gpus':gpus,'processes':processes,'driver':str(data.get('driver','N/A')),
            'cuda':str(data.get('cuda','N/A')),'gpu_status':data.get('gpu_status','available')}
    if result['gpu_status'] not in ('available','no_gpu'):
        raise ValueError('Unavailable telemetry must not replace a good snapshot')
    if 'notice' in data: result['notice']=str(data['notice'])
    return result


def save(profile,data,history,sampled_at):
    data=clean_data(data)
    record={'version':1,'endpoint':endpoint(profile),'sampled_at':sampled_at,'data':data,
            'history':{g['uuid']:list(history.get(g['uuid'],()))[-60:] for g in data['gpus']}}
    if len(json.dumps(record,ensure_ascii=False,allow_nan=False).encode())>MAX_BYTES:
        raise ValueError('Snapshot exceeds local cache size limit')
    profiles.atomic_json(path_for(profile),record)


def load(profile):
    try:
        path=path_for(profile)
        if path.stat().st_size>MAX_BYTES: return None
        record=json.loads(path.read_text(encoding='utf-8'))
        if record['version']!=1 or record['endpoint']!=endpoint(profile): return None
        stamp=record['sampled_at']
        if isinstance(stamp,bool) or not isinstance(stamp,(float,int)) or not math.isfinite(stamp) or stamp<=0: return None
        data=clean_data(record['data'])
        history={}
        for g in data['gpus']:
            values=record.get('history',{}).get(g['uuid'],[])
            if not isinstance(values,list): return None
            if any(v is not None and (isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v)) for v in values): return None
            history[g['uuid']]=values[-60:]
        return {'data':data,'history':history,'sampled_at':stamp}
    except Exception:
        return None


def remove(profile):
    try:
        path_for(profile).unlink(missing_ok=True)
    except OSError:
        pass
