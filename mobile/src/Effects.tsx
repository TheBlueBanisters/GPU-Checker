import {useEffect,useRef} from 'react';
import {createPortal} from 'react-dom';
/** One continuous SVG perimeter, rather than morphing four unrelated clipping polygons. */
export function OrbitGlow(){
 const ref=useRef<SVGSVGElement>(null);
 useEffect(()=>{
  const svg=ref.current!;
  const update=()=>{
   const w=svg.clientWidth,h=svg.clientHeight,r=Math.min(12,w/2,h/2);
   if(w<2||h<2)return;
   const d=`M1 1H${w-r-1}Q${w-1} 1 ${w-1} ${r+1}V${h-1}H${r+1}Q1 ${h-1} 1 ${h-r-1}Z`;
   for(const path of svg.querySelectorAll('path'))path.setAttribute('d',d);
  };
  const observer=new ResizeObserver(update);observer.observe(svg);update();
  return()=>observer.disconnect();
 },[]);
 return <svg ref={ref} className="orbit-glow" aria-hidden="true">
  <path pathLength="1000" className="orbit-tail far"/>
  <path pathLength="1000" className="orbit-tail near"/>
  <path pathLength="1000" className="orbit-head" data-orbit-head/>
 </svg>;
}
/** A slider-crank: each rigid rod connects the piston pin to the rotating crank pin. */
export function Engine({speed,active=true}:{speed:number;active?:boolean}){
 const ref=useRef<SVGSVGElement>(null),rate=useRef(speed),angle=useRef(0);rate.current=speed;
 useEffect(()=>{
  const svg=ref.current!;let frame=0,last=performance.now(),visible=true;
  const reduced=matchMedia('(prefers-reduced-motion: reduce)').matches;
  const observer=new IntersectionObserver(entries=>{visible=entries[0].isIntersecting});observer.observe(svg);
  const cylinders=Array.from(svg.querySelectorAll<SVGGElement>('[data-cylinder]'));
  function draw(now:number){
   const dt=Math.min(.1,Math.max(0,(now-last)/1000));last=now;
   if(visible&&!document.hidden){
    if(active&&!reduced)angle.current=(angle.current+dt*2*Math.PI/Math.max(.12,rate.current))%(4*Math.PI);
    cylinders.forEach((group,i)=>{
     const cx=23+i*42,theta=angle.current+[0,3*Math.PI,Math.PI,2*Math.PI][i],r=8,l=34,cy=60;
     const dx=r*Math.sin(theta),pinX=cx+dx,pinY=cy-r*Math.cos(theta);
     const pistonY=pinY-Math.sqrt(l*l-dx*dx);
     group.querySelector('[data-piston]')!.setAttribute('transform',`translate(0 ${pistonY.toFixed(3)})`);
     const rod=group.querySelector('[data-rod]')!;rod.setAttribute('y1',pistonY.toFixed(3));rod.setAttribute('x2',pinX.toFixed(3));rod.setAttribute('y2',pinY.toFixed(3));
     const spoke=group.querySelector('[data-spoke]')!;spoke.setAttribute('x2',pinX.toFixed(3));spoke.setAttribute('y2',pinY.toFixed(3));
     const pin=group.querySelector('[data-crank-pin]')!;pin.setAttribute('cx',pinX.toFixed(3));pin.setAttribute('cy',pinY.toFixed(3));
     const cycle=((theta%(4*Math.PI))+4*Math.PI)%(4*Math.PI),distance=Math.min(cycle,4*Math.PI-cycle);
     // Fire near compression TDC once per 720 degrees, not at the bottom of the stroke.
     group.querySelector('[data-flame]')!.setAttribute('opacity',String(Math.max(0,1-distance/.24)*.75));
    });
   }
   if(active&&!reduced)frame=requestAnimationFrame(draw);
  }
  frame=requestAnimationFrame(draw);return()=>{cancelAnimationFrame(frame);observer.disconnect()};
 },[active]);
 return <svg ref={ref} className="engine" viewBox="0 0 180 74" aria-hidden="true">{[0,1,2,3].map(i=>{const cx=23+i*42;return <g key={i} data-cylinder={i}>
  <rect x={cx-13} y="5" width="26" height="35" rx="2"/>
  <path d={`M${cx-15} 7h4m22 0h4M${cx-13} 39h26`} opacity=".65"/>
  <circle cx={cx} cy="60" r="10" opacity=".65"/>
  <line data-spoke x1={cx} y1="60" x2={cx} y2="52" strokeWidth="1.3"/>
  <line data-rod x1={cx} y1="18" x2={cx} y2="52" strokeWidth="1.6"/>
  <g data-piston transform="translate(0 18)"><rect x={cx-12} y="-4" width="24" height="7" rx="1"/><path d={`M${cx-11} -1h22`} opacity=".6"/><circle cx={cx} cy="0" r="1.3"/></g>
  <circle data-crank-pin cx={cx} cy="52" r="1.6" fill="var(--status)"/><circle cx={cx} cy="60" r="1.5"/>
  <ellipse data-flame cx={cx} cy="10" rx="8" ry="3" fill="var(--status)" stroke="none" opacity="0"/>
 </g>})}</svg>
}
export function Burst({color,origin,onDone}:{color:string;origin:{x:number;y:number};onDone:()=>void}){
 const ref=useRef<HTMLCanvasElement>(null);
 useEffect(()=>{const canvas=ref.current!;const ctx=canvas.getContext('2d')!;const r=canvas.getBoundingClientRect(),cx=origin.x-r.left,cy=origin.y-r.top,dpr=Math.min(2,devicePixelRatio);canvas.width=r.width*dpr;canvas.height=r.height*dpr;ctx.scale(dpr,dpr);
 const parts=Array.from({length:150},()=>{const a=Math.random()*Math.PI*2,v=35+Math.random()*250;return {vx:Math.cos(a)*v,vy:Math.sin(a)*v-30,s:.4+Math.random()*1.6,life:.55+Math.random()*.75}});
 const start=performance.now();let frame=0;function draw(now:number){const t=(now-start)/1000;ctx.clearRect(0,0,r.width,r.height);
 const smooth=(a:number,b:number,value:number)=>{const x=Math.max(0,Math.min(1,(value-a)/(b-a)));return x*x*(3-2*x)};
 const ignition=smooth(0,.065,t),flash=ignition*(1-smooth(.09,.65,t));
 if(flash>0){ctx.globalAlpha=flash;const grad=ctx.createRadialGradient(cx,cy,0,cx,cy,100+t*200);grad.addColorStop(0,'#ffffffaa');grad.addColorStop(.16,color+'bb');grad.addColorStop(1,color+'00');ctx.fillStyle=grad;ctx.fillRect(0,0,r.width,r.height)}
 ctx.fillStyle=color;for(const p of parts){const age=t/p.life;if(age>=1)continue;ctx.globalAlpha=ignition*(1-age)**1.3*(1-smooth(.95,1.3,t));ctx.beginPath();ctx.arc(cx+p.vx*t,cy+p.vy*t+80*t*t,p.s*(1-age*.5),0,Math.PI*2);ctx.fill()}ctx.globalAlpha=1;
 if(t<1.3)frame=requestAnimationFrame(draw);else onDone()};frame=requestAnimationFrame(draw);return()=>cancelAnimationFrame(frame)},[color,onDone,origin]);
 return createPortal(<canvas ref={ref} className="burst" data-effect-layer="global" data-origin-x={origin.x} data-origin-y={origin.y} aria-hidden="true"/>,document.body);
}
