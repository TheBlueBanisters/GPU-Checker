// Runs only against the isolated development emulator after android-functional.mjs.
import {_android as android,expect} from '@playwright/test';
import {execFileSync} from 'node:child_process';
import {writeFile} from 'node:fs/promises';
const serial='emulator-5580',pkg='top.nullsf.gpuchecker';
const adb=(...args)=>execFileSync('adb',['-s',serial,...args],{encoding:'utf8'}).trim();
const auto=adb('shell','settings','get','system','accelerometer_rotation'),rotation=adb('shell','settings','get','system','user_rotation');
const sizeBefore=adb('shell','wm','size'),densityBefore=adb('shell','wm','density');
const device=(await android.devices()).find(d=>d.serial()===serial);const reports=[];
async function pageAfterRestart(){adb('shell','am','force-stop',pkg);adb('shell','am','start','-n',pkg+'/.MainActivity');await new Promise(r=>setTimeout(r,1200));const page=await(await device.webView({pkg})).page();await expect(page.locator('.gpu-entry').first()).toBeVisible({timeout:20000});await page.evaluate(()=>document.fonts.ready);await expect(page.locator('.process-region')).toHaveAttribute('data-fit-ready','true');const expand=page.getByRole('button',{name:'展开用卡进程',exact:true});if(await expand.isVisible())await expand.click();await expect(page.locator('.process-row').first()).toBeVisible({timeout:20000});return page}
try{
 for(const [label,size,density] of [['default',null,null],['small-320dpi','720x1280','320'],['large-480dpi','1440x2560','480']]){
  if(size){adb('shell','wm','size',size);adb('shell','wm','density',density)}
  const page=await pageAfterRestart();
  const layout=await page.evaluate(()=>{
   const rect=(s)=>{const r=document.querySelector(s).getBoundingClientRect();return {x:r.x,y:r.y,width:r.width,height:r.height}};
   return {viewport:[innerWidth,innerHeight],dpr:devicePixelRatio,toolbar:rect('.topbar'),host:rect('.host-tile'),gpu:rect('.gpu-entry'),process:rect('.process-row'),overflow:document.documentElement.scrollWidth>innerWidth,identity:(()=>{const a=getComputedStyle(document.querySelector('.gpu-identity .eyebrow')),b=getComputedStyle(document.querySelector('.gpu-identity h3'));return a.fontSize===b.fontSize&&a.fontWeight!==b.fontWeight})(),edge:(()=>{const a=document.querySelector('.gpu-entry').getBoundingClientRect(),b=document.querySelector('.host-controls>button:last-child').getBoundingClientRect();return Math.abs(a.right-b.right)})(),mask:getComputedStyle(document.querySelector('.gpu-list')).webkitMaskImage,footer:!!document.querySelector('.app-foot'),align:(()=>{const a=document.querySelector('.load b').getBoundingClientRect(),b=document.querySelector('.load>span').getBoundingClientRect();return Math.abs(a.y+a.height/2-b.y-b.height/2)})(),badges:(()=>{const a=document.querySelector('.host-tile .capacity').getBoundingClientRect(),b=document.querySelector('.host-tile .gpu-count').getBoundingClientRect();return {dy:Math.abs(a.y-b.y),overlap:a.right>b.left}})(),search:!!document.querySelector('.process-search'),engine:[...document.querySelectorAll('.engine [data-rod]')].map(r=>Math.hypot(+r.getAttribute('x2')-+r.getAttribute('x1'),+r.getAttribute('y2')-+r.getAttribute('y1')))};
  });
  expect(layout.viewport[1]).toBeGreaterThan(layout.viewport[0]);expect(layout.overflow).toBe(false);expect(layout.search).toBe(false);
  expect(layout.identity).toBe(true);expect(layout.edge).toBeLessThan(1.5);expect(layout.mask).toContain("linear-gradient");expect(layout.footer).toBe(false);expect(layout.align).toBeLessThan(.5);expect(layout.badges.dy).toBeLessThan(1);expect(layout.badges.overlap).toBe(false);expect(layout.gpu.height).toBeLessThanOrEqual(100);expect(layout.host.height).toBeLessThanOrEqual(88);expect(layout.process.height).toBeLessThanOrEqual(36);expect(layout.engine.every(n=>Math.abs(n-34)<.003)).toBe(true);
  await page.screenshot({path:`../build/mobile-native-compact-${label}.png`});reports.push({label,...layout});
 }
 adb('shell','settings','put','system','accelerometer_rotation','0');adb('shell','settings','put','system','user_rotation','1');await new Promise(r=>setTimeout(r,900));
 const page=await(await device.webView({pkg})).page();const orientation=await page.evaluate(async()=>({viewport:[innerWidth,innerHeight],native:(await window.Capacitor.Plugins.GpuMonitor.getState()).portrait}));
 expect(orientation.native).toBe(true);expect(orientation.viewport[1]).toBeGreaterThan(orientation.viewport[0]);
 await writeFile('../build/mobile-portrait-layout-report.json',JSON.stringify({passed:'Native portrait lock, three DPI/size configurations, compact rows, no search box, constant rod length',reports,rotationAttempt:orientation},null,2));
 console.log('Native compact layout at three DPI/size configurations and portrait rotation lock passed.');
}catch(error){console.error(error);process.exitCode=1}finally{
 const oldSize=sizeBefore.match(/Override size:\s*(\S+)/)?.[1]??'reset',oldDensity=densityBefore.match(/Override density:\s*(\S+)/)?.[1]??'reset';
 adb('shell','wm','size',oldSize);adb('shell','wm','density',oldDensity);
 for(const [key,value] of [['accelerometer_rotation',auto],['user_rotation',rotation]])if(value==='null')adb('shell','settings','delete','system',key);else adb('shell','settings','put','system',key,value);
 await Promise.race([device.close().catch(()=>{}),new Promise(resolve=>setTimeout(resolve,5000))]);process.exit(process.exitCode??0);
}
