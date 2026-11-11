import {useEffect,type RefObject} from 'react';

/** Fade only edges that actually hide more content; never cover a fully visible end. */
export function useScrollFades(root:RefObject<HTMLDivElement|null>){
 useEffect(()=>{
  const cleanups:Array<()=>void>=[];
  for(const el of root.current?.querySelectorAll<HTMLElement>('.host-deck,.gpu-list,.process-list')??[]){
   const horizontal=el.classList.contains('host-deck');el.dataset.scrollAxis=horizontal?'x':'y';
   let frame=0,disposed=false;
   function update(){frame=0;if(disposed)return;
    const offset=horizontal?el.scrollLeft:el.scrollTop,extent=horizontal?el.scrollWidth-el.clientWidth:el.scrollHeight-el.clientHeight;
    el.dataset.fadeStart=String(extent>1&&offset>1);el.dataset.fadeEnd=String(extent>1&&offset<extent-1);
    if(el.classList.contains('gpu-list')){
     const first=el.querySelector<HTMLElement>('.gpu-entry');
     if(first)el.parentElement?.style.setProperty('--gpu-right-inset',`${Math.max(0,el.offsetWidth-first.offsetLeft-first.offsetWidth)}px`);
    }
   }
   function schedule(){if(!disposed&&!frame)frame=requestAnimationFrame(update)}
   const resize=new ResizeObserver(schedule);resize.observe(el);if(el.parentElement)resize.observe(el.parentElement);
   const observed=new Set<Element>();function watchChildren(){const current=new Set(el.children);for(const child of observed)if(!current.has(child)){resize.unobserve(child);observed.delete(child)}for(const child of current)if(!observed.has(child)){resize.observe(child);observed.add(child)}schedule()}
   const mutations=new MutationObserver(watchChildren);mutations.observe(el,{childList:true,subtree:true});
   el.addEventListener('scroll',schedule,{passive:true});watchChildren();void document.fonts.ready.then(schedule);
   cleanups.push(()=>{disposed=true;cancelAnimationFrame(frame);resize.disconnect();mutations.disconnect();el.removeEventListener('scroll',schedule)});
  }
  return()=>cleanups.forEach(clean=>clean());
 },[root]);
}
