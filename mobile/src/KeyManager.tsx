import {useState} from 'react';
import {KeyRound,Plus,Trash2,Check} from 'lucide-react';
import {api,native} from './bridge';
import type {KeyInfo} from './types';

export function KeyManager({keys,run}:{keys:KeyInfo[];run:(action:()=>Promise<unknown>)=>Promise<void>}){
 const [busy,setBusy]=useState(false);
 async function add(){setBusy(true);try{await run(async()=>{await api.importKey();return api.getState()})}finally{setBusy(false)}}
 return <section className="key-library"><div className="key-library-heading"><div><span className="eyebrow">ENCRYPTED ON DEVICE</span><h3><KeyRound size={18}/>SSH 私钥库 <span className="pill">{keys.length} 把</span></h3></div><button aria-label="导入私钥到密钥库" disabled={busy} onClick={()=>void add()}><Plus size={17}/>导入</button></div>
 <p className="hint">从手机文件中导入后，各主机可共用同一把私钥。密钥及口令只保存在原生加密存储中。{!native&&' 浏览器仅演示列表，不读取私钥文件。'}</p>
 {!keys.length&&<div className="key-library-empty">尚未导入私钥 · 可先通过 USB 将电脑私钥复制到手机</div>}
 {keys.map(key=><KeyRow key={key.id} entry={key} run={run}/>)}
 </section>
}
function KeyRow({entry,run}:{entry:KeyInfo;run:(action:()=>Promise<unknown>)=>Promise<void>}){
 const [name,setName]=useState(entry.name),[busy,setBusy]=useState(false);
 async function rename(){setBusy(true);try{await run(()=>api.renameKey({keyId:entry.id,name:name.trim()}))}finally{setBusy(false)}}
 return <div className="key-library-row"><div className="key-row-name"><KeyRound size={18}/><input aria-label={'密钥名称 '+entry.name} value={name} maxLength={80} onChange={e=>setName(e.target.value)}/><button aria-label={'保存密钥名称 '+entry.name} disabled={busy||!name.trim()||name.trim()===entry.name} onClick={()=>void rename()}><Check size={17}/></button><button className="danger" aria-label={'删除私钥 '+entry.name} onClick={()=>void run(()=>api.removeKey({keyId:entry.id}))}><Trash2 size={16}/></button></div><div className="key-row-meta"><span>{entry.algorithm}</span><span>{entry.usedBy?.length??0} 台主机使用</span></div><code className="key-fingerprint">{entry.fingerprint}</code></div>
}
