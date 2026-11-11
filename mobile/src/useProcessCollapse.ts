import {useEffect,useState,type RefObject} from 'react';

/** Compare content against the expanded split, not the enlarged collapsed viewport. */
export function useProcessCollapse(root:RefObject<HTMLDivElement|null>,hostId:string){
 const [overflow,setOverflow]=useState(false),[measuredHost,setMeasuredHost]=useState<string|null>(null);
 const [choices,setChoices]=useState<Record<string,boolean>>({});
 useEffect(()=>{
  const workspace=root.current?.querySelector<HTMLElement>('.workspace'),gpu=root.current?.querySelector<HTMLElement>('.gpu-region'),process=root.current?.querySelector<HTMLElement>('.process-region'),list=root.current?.querySelector<HTMLElement>('.gpu-list');
  if(!workspace||!gpu||!process||!list)return;
  let frame=0,disposed=false;const watched=new Set<Element>();
  const noGap=document.documentElement.classList.contains('no-flex-gap');
  const number=(value:string)=>parseFloat(value)||0;
  function measure(){frame=0;if(disposed)return;setMeasuredHost(hostId);
   const cards=list!.querySelectorAll('.gpu-entry');if(!cards.length){setOverflow(false);return}
   const w=getComputedStyle(workspace!),g=getComputedStyle(gpu!),p=getComputedStyle(process!),header=gpu!.querySelector<HTMLElement>('.section-top')!,h=getComputedStyle(header);
   const available=workspace!.clientHeight-number(w.paddingTop)-number(w.paddingBottom)-(noGap?0:number(w.rowGap))-number(p.marginTop);
   const minGpu=number(g.minHeight),minProcess=number(w.getPropertyValue('--process-expanded-min'))||112;
   const share=number(w.getPropertyValue('--gpu-expanded-share'))||1.38,other=number(w.getPropertyValue('--process-expanded-share'))||.62;
   const expandedHeight=Math.max(minGpu,Math.min(available-minProcess,available*share/(share+other)));
   const viewport=expandedHeight-header.offsetHeight-number(h.marginTop)-number(h.marginBottom)-(noGap?0:number(g.rowGap));
   let content=0;for(const child of list!.children){const el=child as HTMLElement;content=Math.max(content,el.offsetTop+el.offsetHeight+number(getComputedStyle(el).marginBottom))}
   content+=number(getComputedStyle(list!).paddingBottom);
   setOverflow(content>viewport+2);
  }
  function schedule(){if(!disposed&&!frame)frame=requestAnimationFrame(measure)}
  const resize=new ResizeObserver(schedule);for(const el of [workspace,gpu,process])resize.observe(el);
  function watch(){const next=new Set(list!.children);for(const el of watched)if(!next.has(el)){resize.unobserve(el);watched.delete(el)}for(const el of next)if(!watched.has(el)){resize.observe(el);watched.add(el)}schedule()}
  const mutations=new MutationObserver(watch);mutations.observe(list,{childList:true,subtree:true});watch();void document.fonts.ready.then(schedule);
  return()=>{disposed=true;cancelAnimationFrame(frame);resize.disconnect();mutations.disconnect()};
 },[root,hostId]);
 const collapsed=hostId in choices?choices[hostId]:overflow;
 function toggle(){if(hostId)setChoices(current=>({...current,[hostId]:!collapsed}))}
 return {collapsed,toggle,ready:measuredHost===hostId,automatic:!(hostId in choices)};
}
