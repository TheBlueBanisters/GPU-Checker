import {useEffect,useRef,useState} from 'react';
import {Minus,Plus,RotateCcw} from 'lucide-react';
import {api} from './bridge';import type {HistoryRow,Host} from './types';
export function History({host,gpu}:{host:Host;gpu?:string}){
 const [period,setPeriod]=useState(21600000),[view,setView]=useState<[number,number]>(()=>[Date.now()-21600000,Date.now()]),[rows,setRows]=useState<HistoryRow[]>([]),[error,setError]=useState('');const bounds=useRef<[number,number]>(view);
 const request=useRef({id:host.id,gpu,view});request.current={id:host.id,gpu,view};
 const queryBusy=useRef(false),queryVersion=useRef(0);
 useEffect(()=>{let alive=true;const version=++queryVersion.current;
  async function load(){if(queryBusy.current)return;queryBusy.current=true;const q=request.current;
   try{const data=await api.history({id:q.id,gpu:q.gpu,start:q.view[0],end:q.view[1]});if(alive&&version===queryVersion.current){setRows(data.rows);setError('')}}catch(e){if(alive)setError(String(e))}finally{queryBusy.current=false}}
  const settle=setTimeout(()=>void load(),180),timer=setInterval(()=>void load(),1000);
  return()=>{alive=false;clearTimeout(settle);clearInterval(timer)}
 },[host.id,gpu,view]);
 function reset(ms=period){const end=Date.now();bounds.current=[end-ms,end];setView([...bounds.current])}
 function change(a:number,b:number){const max=bounds.current[1]-bounds.current[0],span=Math.max(30000,Math.min(max,b-a));a=Math.max(bounds.current[0],Math.min(bounds.current[1]-span,a));setView([a,a+span])}
 return <div className="history-content"><div className="history-tools"><div><span className="eyebrow">{gpu?'SINGLE GPU':'HOST AGGREGATE'}</span><h3>{host.name}</h3></div><select aria-label="时间范围" value={period} onChange={e=>{const ms=Number(e.target.value);setPeriod(ms);reset(ms)}}>{[[3600000,'1 小时'],[21600000,'6 小时'],[86400000,'24 小时'],[604800000,'7 天'],[2592000000,'30 天']].map(([v,label])=><option key={v} value={v}>{label}</option>)}</select></div>
 <div className="chart-actions"><span>单指平移 · 双指缩放 · 轻触读数</span><button aria-label="缩小时间" onClick={()=>change(view[0]-(view[1]-view[0])*.25,view[1]+(view[1]-view[0])*.25)}><Minus size={16}/></button><button aria-label="放大时间" onClick={()=>change(view[0]+(view[1]-view[0])*.2,view[1]-(view[1]-view[0])*.2)}><Plus size={16}/></button><button aria-label="复位时间" onClick={()=>reset()}><RotateCcw size={16}/></button></div>
 {error&&<p className="error">{error}</p>}{(['used','mem'] as const).map(metric=><Chart key={metric} rows={rows} metric={metric} view={view} change={change} reset={()=>reset()}/>)}
 <p className="hint">显存利用率指驱动报告的显存读写时间比例；主机占用量相加，利用率取各卡平均。缺测留空，曲线不代表资源预留。</p></div>
}
function Chart({rows,metric,view,change,reset}:{rows:HistoryRow[];metric:'used'|'mem';view:[number,number];change:(a:number,b:number)=>void;reset:()=>void}){
 const [cursor,setCursor]=useState<number|null>(null);const points=useRef(new Map<number,number>());const gesture=useRef<{view:[number,number];x:number;distance:number}|null>(null);const svg=useRef<SVGSVGElement>(null);
 const max=metric==='mem'?100:Math.max(1,...rows.map(r=>(r.used??0)*1.15));const color=metric==='used'?'#63dec1':'#65bde9';const width=640,left=52,right=628,top=12,bottom=150;const span=view[1]-view[0];
 let path='',last=0;const intervals=rows.slice(1).map((r,i)=>r.t-rows[i].t).filter(n=>n>0).sort((a,b)=>a-b);const gap=Math.max(60000,(intervals[Math.floor(intervals.length/2)]??2000)*2.5);
 for(const r of rows){const value=r[metric];if(value===null){last=0;continue}const x=left+(r.t-view[0])/span*(right-left),y=bottom-value/max*(bottom-top);path+=`${!last||r.t-last>gap?'M':'L'}${x.toFixed(2)},${y.toFixed(2)} `;last=r.t}
 function xOf(e:React.PointerEvent){const r=svg.current!.getBoundingClientRect();return Math.max(0,Math.min(1,(e.clientX-r.left-r.width*left/width)/(r.width*(right-left)/width)))}
 function begin(e:React.PointerEvent){e.currentTarget.setPointerCapture(e.pointerId);points.current.set(e.pointerId,xOf(e));const xs=[...points.current.values()];gesture.current={view:[...view],x:xs.reduce((a,b)=>a+b)/xs.length,distance:xs.length>1?Math.abs(xs[0]-xs[1]):0};setCursor(xOf(e))}
 function move(e:React.PointerEvent){const x=xOf(e);setCursor(x);if(!points.current.has(e.pointerId)||!gesture.current)return;points.current.set(e.pointerId,x);const xs=[...points.current.values()],g=gesture.current,center=xs.reduce((a,b)=>a+b)/xs.length,oldSpan=g.view[1]-g.view[0];
 const newSpan=xs.length>1&&g.distance>0?oldSpan*g.distance/Math.max(.03,Math.abs(xs[0]-xs[1])):oldSpan;const anchor=g.view[0]+g.x*oldSpan;change(anchor-center*newSpan,anchor+(1-center)*newSpan)}
 const stamp=cursor===null?null:view[0]+cursor*span;const nearest=stamp===null||!rows.length?undefined:rows.reduce((a,b)=>Math.abs(a.t-stamp)<Math.abs(b.t-stamp)?a:b);
 return <section className="plot-panel"><div className="plot-heading"><h4>{metric==='used'?'显存占用量':'显存利用率'}</h4><b style={{color}}>{nearest&&stamp!==null&&Math.abs(nearest.t-stamp)<=gap?nearest[metric]?.toFixed(1)??'—':'—'} <small>{metric==='used'?'GiB':'%'}</small></b></div><div className="chart-stage"><svg ref={svg} viewBox="0 0 640 170" className="history-chart" role="img" aria-label={metric==='used'?'显存占用量曲线':'显存利用率曲线'} onPointerDown={begin} onPointerMove={move} onPointerUp={e=>{points.current.delete(e.pointerId);gesture.current=null}} onPointerCancel={()=>{points.current.clear();gesture.current=null}} onPointerLeave={()=>{if(!points.current.size)setCursor(null)}} onDoubleClick={reset}>
 <defs><clipPath id={'clip-'+metric}><rect x={left} y={top} width={right-left} height={bottom-top}/></clipPath></defs>{[0,1,2,3,4].map(i=><g key={i}><line x1={left} x2={right} y1={bottom-i*(bottom-top)/4} y2={bottom-i*(bottom-top)/4} stroke="var(--line)"/><text x="43" y={bottom-i*(bottom-top)/4+4} textAnchor="end">{(max*i/4).toFixed(metric==='mem'?0:1)}</text></g>)}<path d={path} fill="none" stroke={color} strokeWidth="2.5" clipPath={`url(#clip-${metric})`}/>{!rows.length&&<text x="334" y="85" textAnchor="middle">暂无历史记录 · 连接后自动采样</text>}
 {stamp!==null&&<line className="chart-cursor-line" x1={left+cursor!*(right-left)} x2={left+cursor!*(right-left)} y1={top} y2={bottom} stroke="#7bb4d3" strokeDasharray="4 4"/>}</svg>
 <div className="chart-time-axis" style={{paddingLeft:`${left/width*100}%`,paddingRight:`${(width-right)/width*100}%`}}>{[0,.5,1].map(v=><time key={v}>{new Date(view[0]+span*v).toLocaleTimeString('zh-CN',{hour:'2-digit',minute:'2-digit'})}</time>)}</div>
 {stamp!==null&&<time className="chart-cursor-time" style={{left:`clamp(90px,${(left+cursor!*(right-left))/width*100}%,calc(100% - 90px))`}}>{new Date(stamp).toLocaleString('zh-CN',{month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',second:'2-digit',hour12:false})}</time>}
 </div></section>
}
