import {colors,labels,type GPU,type Process,type Verdict,type Sample,type Status} from './types';
const finite=(v:unknown):v is number=>typeof v==='number'&&Number.isFinite(v);
const result=(status:Status,reason:string):Verdict=>({status,label:labels[status],color:colors[status],reason,available:['idle','available','light'].includes(status)});
export function candidate(g:GPU,ps:Process[]):Verdict{
 const mode=(g.compute_mode??'').toLowerCase().replace(/ /g,'_');
 if(!g.uuid||g.uuid==='N/A')return result('blocked','无法确认 GPU 身份');
 if(mode==='prohibited')return result('blocked','驱动禁止计算');
 if(!['','n/a','none','not supported'].includes((g.recovery_action??'N/A').toLowerCase()))return result('blocked','驱动要求恢复操作');
 if(['yes','true','1'].includes((g.remap_failure??'').toLowerCase())||(g.ecc_uncorrectable??0)>0)return result('blocked','驱动报告不可纠错错误');
 if(finite(g.slowdown_temp)&&finite(g.temp)&&g.temp>=g.slowdown_temp)return result('blocked','温度达到减速阈值');
 if(g.mig_mode?.toLowerCase()==='enabled')return result('blocked','MIG 实例可用性未确认');
 if(!finite(g.temp)||g.temp<0||g.temp>150||g.device_access!==true||g.process_query_ok!==true)return result('blocked','传感器、进程查询或设备权限未确认');
 if(ps.some(p=>!['G','C','C+G'].includes(p.kind)||p.name.toLowerCase().includes('mps')))return result('busy','存在 MPS 或未识别的 GPU 进程');
 if(!['default','exclusive_process','exclusive_thread'].includes(mode))return result('blocked','计算模式未确认');
 if(mode!=='default'&&ps.length)return result('busy','独占模式下已有 GPU 上下文');
 const {util,used,total,free}=g;
 if(!finite(util)||!finite(used)||!finite(total)||!finite(free)||util<0||util>100||total<=0||used<0||free<0||used>total||free>total||used+free>total*1.01)return result('blocked','负载或显存数据缺失／异常');
 if(util>10||free<Math.max(4096,total*.2))return result('busy','负载较高或剩余显存不足');
 const compute=ps.filter(p=>p.kind!=='G');
 if(compute.length){
  if(mode==='default'&&util<=10&&used<=Math.min(4096,total*.1)&&compute.every(p=>/^\d+$/.test(p.pid)&&p.name&&finite(p.memory)&&p.memory>=0))return result('light','允许共享；仅是当前资源提示，不预留资源');
  return result('busy','已有计算进程，超出轻量占用门槛');
 }
 const idleMemory=Math.min(1024,Math.max(256,total*.02));
 if(!ps.length&&used>idleMemory)return result('blocked','显存占用与可见进程不一致');
 if(ps.length&&used>Math.min(1024,Math.max(512,total*.05)))return result('busy','图形进程显存占用较大');
 return !ps.length&&util<=5&&used<=idleMemory?result('idle','无进程且负载与显存开销低'):result('available','低负载且剩余显存满足门槛');
}
export class AvailabilityTracker{
 private runs=new Map<string,{since:number;last:number;count:number;status:Status;categorySince:number;categoryCount:number}>();
 private last=new Map<string,Verdict>();
 observe(sample:Sample,interval:number){
  const now=sample.receivedAt/1000;const out:Record<string,Verdict>={};
  for(const g of sample.gpus){
   let state=candidate(g,sample.processes.filter(p=>p.uuid===g.uuid));let run=this.runs.get(g.uuid);let prior=this.last.get(g.uuid);
   if(run&&(now<run.last||now-run.last>Math.max(10,interval*2+5))){run=undefined;prior=undefined;this.runs.delete(g.uuid)}
   if(state.available){
    if(!run)run={since:now,last:now,count:0,status:state.status,categorySince:now,categoryCount:0};
    if(run.status!==state.status){run.status=state.status;run.categorySince=now;run.categoryCount=0}
    if(now!==run.last||run.count===0){run.count++;run.categoryCount++}run.last=now;this.runs.set(g.uuid,run);
    if(now-run.since<10||run.count<3)state=result(prior&&['busy','blocked'].includes(prior.status)?prior.status:'observing','等待 10 秒与至少 3 次连续采样确认');
    else if(state.status==='idle'&&(now-run.categorySince<10||run.categoryCount<3))state=result('available','资源满足门槛，等待空闲状态稳定');
   }else this.runs.delete(g.uuid);
   out[g.uuid]=state;this.last.set(g.uuid,state);
  }
  for(const key of this.runs.keys())if(!sample.gpus.some(g=>g.uuid===key))this.runs.delete(key);
  return out;
 }
}
