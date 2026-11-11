import {Capacitor,registerPlugin,type PluginListenerHandle} from '@capacitor/core';
import type {AppState,Host,HistoryData,Sample,GPU,KeyInfo} from './types';
export const native=Capacitor.isNativePlatform();
export interface MonitorPlugin{
 getState():Promise<AppState>;
 importKey():Promise<{saved:boolean;key:KeyInfo}>;
 renameKey(options:{keyId:string;name:string}):Promise<AppState>;
 removeKey(options:{keyId:string}):Promise<AppState>;
 copyHosts():Promise<{copied:boolean}>;
 saveHost(options:{host:Host}):Promise<AppState>;
 importHosts(options:{hosts:Host[]}):Promise<AppState>;
 removeHost(options:{id:string}):Promise<AppState>;
 connect(options:{id:string}):Promise<AppState>;
 pause(options:{id:string}):Promise<AppState>;
 configureCredentials(options:{id:string}):Promise<{saved:boolean}>;
 resetTrust(options:{id:string}):Promise<{reset:boolean}>;
 history(options:{id:string;gpu?:string;start:number;end:number}):Promise<HistoryData>;
 historyStats():Promise<{bytes:number;limit:number}>;
 clearHistory():Promise<{cleared:boolean}>;
 setHistoryLimit(options:{bytes:number}):Promise<{limit:number}>;
 addListener(event:'state',listener:(state:AppState)=>void):Promise<PluginListenerHandle>;
}
const Android=registerPlugin<MonitorPlugin>('GpuMonitor');
const saved=()=>{try{return JSON.parse(localStorage.getItem('gpu-preview-hosts')??'null') as Host[]|null}catch{return null}};
let demoHosts:Host[]=saved()??[
 {id:'demo-atlas',name:'ATLAS · 4090',host:'atlas.example',user:'research',port:22,mode:'password',interval:2,autoconnect:true,retry:true},
 {id:'demo-nova',name:'NOVA · A100',host:'nova.example',user:'research',port:22,mode:'key',interval:2,autoconnect:false,retry:true},
 {id:'demo-cpu',name:'LISA · CPU',host:'cpu.example',user:'research',port:22,mode:'password',interval:2,autoconnect:true,retry:true}];
export function demoSample(cpu=false):Sample{
 const time=Date.now();const gpus:GPU[]=cpu?[]:[0,2,3,4].map((index,i)=>({uuid:'DEMO-'+index,index,name:i===2?'NVIDIA A100-SXM4-80GB':'GeForce RTX 4090',util:i===0?92+Math.round(Math.sin(time/1800)*3):i===1?0:i===2?3:28,mem_util:i===0?67:i===1?0:i===2?2:21,used:i===0?14720:i===1?16:i===2?512:8192,total:i===2?81920:24576,free:(i===2?81920:24576)-(i===0?14720:i===1?16:i===2?512:8192),temp:i===0?78:36+i*3,power:i===0?326:24+i*12,compute_mode:'Default',mig_mode:'Disabled',process_query_ok:true,device_access:true,gpu_zero_since:i===1?time/1000-7300:undefined,gpu_zero_last:i===1?time/1000:undefined}));
 return {gpus,processes:cpu?[]:[{uuid:'DEMO-0',gpu:0,pid:'3815527',name:'python',kind:'C',memory:14720,user:'research',cwd:'/home/research/experiments/vision',ppid:'3813646',exe:'/opt/conda/bin/python'},{uuid:'DEMO-3',gpu:3,pid:'3815742',name:'python',kind:'C',memory:512,user:'research',cwd:'/home/research/notebooks',ppid:'3815657'},{uuid:'DEMO-4',gpu:4,pid:'3791983',name:'python',kind:'C',memory:8192,user:'team',cwd:'/home/team/runs/segmentation',ppid:'3698476'}],timestamp:time/1000,receivedAt:time,driver:'580.178.04',cuda:'13.0',gpu_status:cpu?'no_gpu':'available'};
}
let demoKeys:KeyInfo[]=[];
function demoState():AppState{return {keys:demoKeys.map(k=>({...k,usedBy:demoHosts.filter(h=>h.keyId===k.id).map(h=>h.name)})),hosts:demoHosts,runtimes:Object.fromEntries(demoHosts.map(h=>[h.id,{status:h.autoconnect?'在线':'已暂停',message:'浏览器演示 · 不执行 SSH',fresh:h.autoconnect,snapshot:demoSample(h.id==='demo-cpu')}]))}}
const listeners=new Set<(state:AppState)=>void>();
function publish(){localStorage.setItem('gpu-preview-hosts',JSON.stringify(demoHosts));const state=demoState();listeners.forEach(l=>l(state));return state}
const Web:MonitorPlugin={
 async importKey(){const key={id:'demo-key-'+Date.now(),name:'演示密钥',algorithm:'ssh-ed25519',fingerprint:'浏览器演示 · 不含私钥',createdAt:Date.now()};demoKeys.push(key);publish();return {saved:true,key}},
 async renameKey({keyId,name}){demoKeys=demoKeys.map(k=>k.id===keyId?{...k,name}:k);return publish()},
 async removeKey({keyId}){demoKeys=demoKeys.filter(k=>k.id!==keyId);demoHosts=demoHosts.map(h=>h.keyId===keyId?{...h,keyId:undefined,autoconnect:false}:h);return publish()},
 async copyHosts(){await navigator.clipboard.writeText(JSON.stringify({schema:1,hosts:demoHosts.map(({credentialReady:_,keyId:__,...h})=>h)},null,2));return {copied:true}},
 async getState(){return demoState()},async saveHost({host}){demoHosts=[...demoHosts.filter(h=>h.id!==host.id),host];return publish()},
 async importHosts({hosts}){for(const h of hosts){const exists=demoHosts.find(x=>x.host===h.host&&x.user===h.user&&x.port===h.port);if(!exists)demoHosts.push(h)}return publish()},
 async removeHost({id}){demoHosts=demoHosts.filter(h=>h.id!==id);return publish()},
 async connect({id}){demoHosts=demoHosts.map(h=>h.id===id?{...h,autoconnect:true}:h);return publish()},
 async pause({id}){demoHosts=demoHosts.map(h=>h.id===id?{...h,autoconnect:false}:h);return publish()},
 async configureCredentials(){throw Error('SSH 凭据只能在 Android 原生安全窗口中配置；浏览器仅供界面预览。')},
 async resetTrust(){throw Error('请在 Android 中管理主机指纹')},
 async history({start,end}){return {devices:demoSample().gpus.map(g=>({uuid:g.uuid,name:g.name,index:g.index})),rows:Array.from({length:160},(_,i)=>({t:start+(end-start)*i/159,used:8+5*Math.sin(i/16)**2,mem:Math.max(0,38+32*Math.sin(i/18))})).filter((_,i)=>i<68||i>72)}},
 async historyStats(){return {bytes:12480000,limit:256000000}},async clearHistory(){return {cleared:true}},async setHistoryLimit({bytes}){return {limit:bytes}},
 async addListener(_event,listener){listeners.add(listener);const timer=setInterval(()=>listener(demoState()),2000);return {remove:async()=>{clearInterval(timer);listeners.delete(listener)}}}
};
export const api=native?Android:Web;
