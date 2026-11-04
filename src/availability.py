"""Conservative, read-only workload-admission hints; never reserves or probes CUDA."""
from dataclasses import dataclass,asdict
import math

COLORS={'idle':'#63dec1','available':'#65bde9','light':'#e8ca67','busy':'#ed8948','blocked':'#78909f',
        'unknown':'#78909f','observing':'#859faf'}
LABELS={'idle':'空闲','available':'可用','light':'轻量占用','busy':'占用','blocked':'不可用','unknown':'不可用','observing':'观察中'}


@dataclass(frozen=True)
class Rules:
    free_mib: float=4096
    free_fraction: float=.20
    max_util: float=10
    stable_seconds: float=10
    min_samples: int=3
    light_max_util: float=10
    light_used_mib: float=4096
    light_used_fraction: float=.10

    def __post_init__(self):
        if not (512<=self.free_mib<=524288 and 0<=self.free_fraction<=.95 and 0<=self.max_util<=90
                and 3<=self.stable_seconds<=120 and 3<=self.min_samples<=30
                and 0<=self.light_max_util<=90 and 512<=self.light_used_mib<=65536
                and .01<=self.light_used_fraction<=.50):
            raise ValueError('可用性规则超出有效范围')

    def as_dict(self):
        return asdict(self)


def result(status,reason):
    return {'status':status,'label':LABELS[status],'color':COLORS[status],'reason':reason,
            'idle':status=='idle','available':status in ('idle','available','light')}


def finite(value):
    return not isinstance(value,bool) and isinstance(value,(float,int)) and math.isfinite(value)


def candidate(g,processes,rules):
    if g.get('uuid') in (None,'','N/A','Unknown'):
        return result('unknown','无法确认 GPU 的唯一标识')
    mode=str(g.get('compute_mode','')).lower().replace(' ','_')
    if mode=='prohibited':
        return result('blocked','驱动禁止计算（Compute Mode: Prohibited）')
    recovery=str(g.get('recovery_action','N/A')).strip().lower()
    if recovery not in ('n/a','none','not supported',''):
        return result('blocked','驱动要求恢复操作：'+str(g['recovery_action']))
    if str(g.get('remap_failure','')).lower() in ('yes','true','1'):
        return result('blocked','驱动报告显存行重映射失败')
    if finite(g.get('ecc_uncorrectable')) and g['ecc_uncorrectable']>0:
        return result('blocked','存在易失性不可纠错 ECC 错误，需管理员确认')
    if finite(g.get('temp')) and finite(g.get('slowdown_temp')) and g['temp']>=g['slowdown_temp']:
        return result('blocked','温度已达到驱动报告的减速阈值')
    if str(g.get('mig_mode','')).lower()=='enabled':
        return result('unknown','MIG 已启用；不能把物理卡读数当作实例可用性')
    if not finite(g.get('temp')) or not 0<=g['temp']<=150:
        return result('unknown','温度传感器数据缺失或异常')
    if g.get('device_access') is False:
        return result('blocked','当前 SSH 账号没有 NVIDIA 设备节点的基础读写权限')
    if g.get('device_access') is not True:
        return result('unknown','未确认当前命名空间内的 NVIDIA 设备节点权限')
    if g.get('process_query_ok') is not True:
        return result('unknown','进程查询缺失或受限，无法确认是否有人占卡')
    kinds=[str(p.get('kind','')).strip().upper() for p in processes]
    if any(kind not in ('G','C','C+G') for kind in kinds) or any('mps' in str(p.get('name','')).lower() for p in processes):
        return result('busy','存在 MPS／未识别的 GPU 进程，不能确认可共卡')
    compute=[p for p,kind in zip(processes,kinds) if kind!='G']
    if mode not in ('default','exclusive_process','exclusive_thread'):
        return result('unknown','无法确认 Compute Mode 是否允许计算')
    if mode!='default' and processes:
        return result('busy','独占模式下仍有 GPU 上下文')
    util,used,total,free=g.get('util'),g.get('used'),g.get('total'),g.get('free')
    if not all(finite(v) for v in (util,used,total,free)) or not (0<=util<=100 and total>0 and 0<=used<=total and 0<=free<=total and free+used<=total*1.01):
        return result('unknown','利用率或显存数据缺失／异常')
    if util>rules.max_util:
        return result('busy',f'GPU 利用率 {util:g}% 超过 {rules.max_util:g}% 门槛')
    required=max(rules.free_mib,total*rules.free_fraction)
    if free<required:
        return result('busy',f'剩余显存不足：需要至少 {required/1024:.1f} GiB')
    if compute:
        known=all(str(p.get('pid','')).isdigit() and p.get('name') and
                  finite(p.get('memory')) and p['memory']>=0 for p in compute)
        limit=min(rules.light_used_mib,total*rules.light_used_fraction)
        if known and mode=='default' and util<=rules.light_max_util and used<=limit:
            return result('light',f'已有计算进程；负载低且占用不超过 {limit/1024:.1f} GiB，设备允许共享。仅为当前资源提示，不预留资源')
        return result('busy','已有计算进程，负载／显存超出轻量门槛或进程数据不完整')
    idle_memory=min(1024,max(256,total*.02))
    if not processes and used>idle_memory:
        return result('unknown','显存占用较大却没有可见进程，不能确认归属')
    if processes and used>min(1024,max(512,total*.05)):
        return result('busy','图形进程显存占用较大，保守视为占用')
    if not processes and util<=5 and used<=idle_memory:
        return result('idle','无 GPU 进程、利用率不超过 5%、显存仅少量后台开销')
    return result('available','仅少量图形后台或低负载，且剩余显存满足规则')


class Tracker:
    def __init__(self,rules=None):
        self.rules=rules or Rules()
        self.runs={}
        self.verdicts={}

    def reset(self):
        self.runs.clear()
        self.verdicts.clear()

    def observe(self,snapshot,now,interval):
        states={}
        ids={g['uuid'] for g in snapshot['gpus']}
        self.runs={key:value for key,value in self.runs.items() if key in ids}
        self.verdicts={key:value for key,value in self.verdicts.items() if key in ids}
        for g in snapshot['gpus']:
            key=g['uuid']
            previous=self.verdicts.get(key)
            if previous and (now<previous['time'] or now-previous['time']>max(10,interval*2+5)):
                self.runs.pop(key,None)
                previous=None
            ps=[p for p in snapshot['processes'] if p.get('uuid')==key]
            state=candidate(g,ps,self.rules)
            if state['available']:
                old=self.runs.get(key)
                if not old:
                    run={'status':state['status'],'since':now,'count':0,'last':now,
                         'category_since':now,'category_count':0}
                else:
                    run=old
                if run['status']!=state['status']:
                    run.update(status=state['status'],category_since=now,category_count=0)
                run['count']+=1
                run['category_count']+=1
                run['last']=now
                self.runs[key]=run
                elapsed=now-run['since']
                if elapsed<self.rules.stable_seconds or run['count']<self.rules.min_samples:
                    reason=f"连续确认中：{elapsed:.0f}/{self.rules.stable_seconds:g} 秒，{run['count']}/{self.rules.min_samples} 次采样"
                    held=previous['state']['status'] if previous and previous['state']['status'] in ('busy','blocked') else 'observing'
                    state=result(held,reason+('；恢复确认结束前保留原判定' if held!='observing' else ''))
                elif state['status']=='idle' and (now-run['category_since']<self.rules.stable_seconds or run['category_count']<self.rules.min_samples):
                    state=result('available','资源连续满足门槛；等待无进程／低后台占用状态持续稳定后再标为空闲')
            else:
                self.runs.pop(key,None)
            self.verdicts[key]={'time':now,'state':dict(state)}
            states[key]=state
        return states
