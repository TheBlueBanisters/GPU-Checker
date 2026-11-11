import {test,expect,type Page} from '@playwright/test';
test('explosion flash ramps up and fades away without a hard cutoff',async({page})=>{
 await page.addInitScript(()=>{
  const draw=CanvasRenderingContext2D.prototype.fillRect;
  CanvasRenderingContext2D.prototype.fillRect=function(...args:Parameters<typeof draw>){
   if(this.canvas.classList.contains('burst')){
    const state=window as Window&{flashSamples?:{time:number;alpha:number}[]};
    (state.flashSamples??=[]).push({time:performance.now(),alpha:this.globalAlpha});
   }
   return draw.apply(this,args);
  };
 });
 await page.goto('/');const card=page.locator('.gpu-entry').first();await expect(card).toBeVisible();
 await card.click({clickCount:5,delay:40,position:{x:30,y:45}});
 await expect(page.locator('canvas.burst')).toBeVisible();
 await expect(page.locator('canvas.burst')).toHaveCount(0,{timeout:4000});
 const samples=await page.evaluate(()=>(window as Window&{flashSamples?:{time:number;alpha:number}[]}).flashSamples!);
 expect(samples.length).toBeGreaterThan(5);
 const peak=Math.max(...samples.map(s=>s.alpha));
 expect(samples[0].alpha).toBeLessThan(peak);
 expect(samples.at(-1)!.alpha).toBeLessThan(peak*.15);
 expect(samples.at(-1)!.time-samples[0].time).toBeGreaterThan(400);
});
async function expandProcesses(page:Page){await page.evaluate(()=>document.fonts.ready);await expect(page.locator('.gpu-entry').first()).toBeVisible();await expect(page.locator('.process-region')).toHaveAttribute('data-fit-ready','true');const button=page.getByRole('button',{name:'展开用卡进程',exact:true});if(await button.isVisible())await button.click();await expect.poll(()=>page.locator('.process-region').evaluate(e=>Number(getComputedStyle(e).flexGrow))).toBeCloseTo(.62,3)}
test('portrait layout fixes toolbar and hosts while GPU/process lists scroll',async({page})=>{
 const errors:string[]=[];page.on('pageerror',e=>errors.push(e.message));await page.goto('/');
 await expect(page.getByText('浏览器演示模式',{exact:false})).toBeVisible();await expandProcesses(page);
 const toolbar=await page.locator('.topbar').boundingBox(),fleet=await page.locator('.fleet').boundingBox();
 await page.locator('.gpu-list').evaluate(e=>e.scrollTop=1000);
 expect(await page.locator('.topbar').boundingBox()).toEqual(toolbar);expect(await page.locator('.fleet').boundingBox()).toEqual(fleet);
 expect(await page.locator('.gpu-list').evaluate(e=>e.scrollHeight>e.clientHeight)).toBeTruthy();
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();
 await page.locator('.gpu-list').evaluate(e=>e.scrollTop=0);await page.screenshot({path:'../build/mobile-portrait.png'});expect(errors).toEqual([]);
});
test('history, theme, config validation and local cosmetic explosion',async({page})=>{
 await page.goto('/');await page.locator('.host-tile').first().getByText('历史').click();
 await expect(page.getByRole('dialog')).toBeVisible();await expect(page.getByRole('img',{name:'显存占用量曲线'})).toBeVisible();
 await page.getByRole('img',{name:'显存占用量曲线'}).dispatchEvent('pointermove',{clientX:200,clientY:350,pointerId:1});
 await page.screenshot({path:'../build/mobile-history.png'});await page.getByRole('button',{name:'关闭窗口'}).click();
 await page.getByRole('button',{name:'切换日夜模式'}).click();await expect(page.locator('html')).toHaveAttribute('data-theme','day');await page.getByRole('button',{name:'切换日夜模式'}).click();
 await page.getByRole('button',{name:'导入 SSH config'}).click();await page.getByRole('textbox',{name:'SSH config 内容'}).fill('Host broken\n HostName test.invalid');await page.getByRole('button',{name:'识别并导入主机'}).click();await expect(page.getByRole('alert')).toContainText('User');await page.getByRole('button',{name:'关闭窗口'}).click();
 const row=page.locator('.gpu-entry').first();await row.click({clickCount:5,delay:45});await expect(row).toHaveClass(/exploded/);await expect(row).not.toHaveClass(/exploded/,{timeout:4000});
});
test('settings embeds clear action and native credentials are never web inputs',async({page})=>{
 await page.goto('/');await page.getByRole('button',{name:'设置',exact:true}).click();await expect(page.locator('.cache-panel').getByRole('button',{name:'清除历史'})).toBeVisible();await page.getByRole('button',{name:'关闭窗口'}).click();
 await page.getByRole('button',{name:'添加主机'}).click();expect(await page.locator('input[type=password]').count()).toBe(0);await expect(page.getByText('密码和私钥由 Android 原生窗口录入',{exact:false})).toBeVisible();
});

test('key library metadata can be reused by two hosts and deleted without losing hosts',async({page})=>{
 await page.goto('/');await page.getByRole('button',{name:'设置',exact:true}).click();
 await page.getByRole('button',{name:'导入私钥到密钥库'}).click();
 const name=page.getByRole('textbox',{name:'密钥名称 演示密钥'});await name.fill('共享实验密钥');
 await page.getByRole('button',{name:'保存密钥名称 演示密钥'}).click();
 await expect(page.getByRole('textbox',{name:'密钥名称 共享实验密钥'})).toHaveValue('共享实验密钥');
 await page.getByRole('button',{name:'关闭窗口'}).click();
 for(const label of ['共享主机甲','共享主机乙']){
  await page.getByRole('button',{name:'添加主机',exact:true}).click();
  await page.getByLabel('显示名称',{exact:true}).fill(label);await page.getByLabel('主机地址',{exact:true}).fill('example.invalid');await page.getByLabel('用户名',{exact:true}).fill('test');
  await page.locator('.form-grid select').first().selectOption('key');
  await page.getByLabel('使用的私钥',{exact:true}).selectOption({label:'共享实验密钥 · ssh-ed25519'});
  await page.getByRole('button',{name:'保存',exact:true}).click();
 }
 await page.getByRole('button',{name:'设置',exact:true}).click();await expect(page.getByText('2 台主机使用')).toBeVisible();
 await page.getByRole('button',{name:'删除私钥 共享实验密钥'}).click();await expect(page.getByText('尚未导入私钥',{exact:false})).toBeVisible();
 await page.getByRole('button',{name:'关闭窗口'}).click();await expect(page.locator('.host-tile').filter({hasText:'共享主机甲'})).toContainText('已暂停');await expect(page.locator('.host-tile').filter({hasText:'共享主机乙'})).toContainText('已暂停');
});

test('compact rows, theme-aware counters, crank linkage and tap-centred effects',async({page})=>{
 await page.addInitScript(()=>{
  document.addEventListener('click',e=>{if((e.target as Element).closest('.gpu-entry'))(window as Window&{blastTap?:number[]}).blastTap=[e.clientX,e.clientY]});
  const original=CanvasRenderingContext2D.prototype.createRadialGradient;
  CanvasRenderingContext2D.prototype.createRadialGradient=function(...args:Parameters<typeof original>){
   if(this.canvas.classList.contains('burst')){const r=this.canvas.getBoundingClientRect();(window as Window&{blastFocus?:number[]}).blastFocus=[r.left+args[0],r.top+args[1]]}
   return original.apply(this,args);
  };
 });
 await page.goto('/');await expandProcesses(page);const row=page.locator('.gpu-entry').first();await expect(row).toBeVisible();
 expect((await page.locator('.topbar').boundingBox())!.height).toBeLessThanOrEqual(45);
 expect((await page.locator('.host-tile').first().boundingBox())!.height).toBeLessThanOrEqual(88);
 expect((await row.boundingBox())!.height).toBeLessThanOrEqual(100);
 expect((await page.locator('.process-row').first().boundingBox())!.height).toBeLessThanOrEqual(36);
 expect(await page.locator('.app-foot').count()).toBe(0);
 const badges=await page.locator('.host-tile').first().evaluate(e=>{const a=e.querySelector('.capacity')!.getBoundingClientRect(),b=e.querySelector('.gpu-count')!.getBoundingClientRect();return {dy:Math.abs(a.y-b.y),overlap:a.right>b.left}});expect(badges.dy).toBeLessThan(1);expect(badges.overlap).toBe(false);
 const align=await row.locator('.load').evaluate(e=>{const a=e.querySelector('b')!.getBoundingClientRect(),b=e.querySelector(':scope>span')!.getBoundingClientRect();return Math.abs(a.y+a.height/2-b.y-b.height/2)});expect(align).toBeLessThan(.5);
 await expect(page.locator('.process-row').first()).toContainText('3815527');await expect(page.locator('.process-row').first()).not.toContainText('python');
 await page.locator('.process-row').first().click();await expect(page.getByRole('dialog')).toContainText('/home/research/experiments/vision');await page.getByRole('button',{name:'关闭窗口'}).click();
 const counter=page.locator('.section-top h2>span').first(),night=await counter.evaluate(e=>[getComputedStyle(e).color,getComputedStyle(e).backgroundColor]);
 await page.getByRole('button',{name:'切换日夜模式'}).click();await page.waitForTimeout(450);expect(await counter.evaluate(e=>[getComputedStyle(e).color,getComputedStyle(e).backgroundColor])).not.toEqual(night);
 await page.getByRole('button',{name:'切换日夜模式'}).click();
 const geometry=await row.locator('.engine').evaluate(async svg=>{
  const lengths:number[]=[],pins:number[]=[];
  for(let t=0;t<8;t++){
   for(const g of svg.querySelectorAll('[data-cylinder]')){
    const rod=g.querySelector('[data-rod]') as SVGLineElement,pin=g.querySelector('[data-crank-pin]') as SVGCircleElement;
    lengths.push(Math.hypot(rod.x2.baseVal.value-rod.x1.baseVal.value,rod.y2.baseVal.value-rod.y1.baseVal.value));
    pins.push(Math.hypot(rod.x2.baseVal.value-pin.cx.baseVal.value,rod.y2.baseVal.value-pin.cy.baseVal.value));
   }
   await new Promise(r=>setTimeout(r,55));
  }return {lengths,pins};
 });
 expect(geometry.lengths.every(n=>Math.abs(n-34)<.003)).toBe(true);expect(geometry.pins.every(n=>n<.002)).toBe(true);
 const rect=(await row.boundingBox())!,point={x:31,y:rect.height-29};
 const before=await page.locator('.process-region').boundingBox();await row.click({position:point});await row.click({position:point});expect(await row.locator('.ripple').count()).toBe(2);
 await row.click({position:point,clickCount:3,delay:40});await expect(row).toHaveClass(/exploded/);
 await expect.poll(()=>page.evaluate(()=>(window as Window&{blastFocus?:number[]}).blastFocus)).toBeTruthy();
 const layer=await page.locator('canvas.burst').evaluate(canvas=>{
  const e=canvas as HTMLCanvasElement,r=e.getBoundingClientRect(),style=getComputedStyle(e);
  const original=e.style.pointerEvents;e.style.pointerEvents='auto';
  const top=Object.fromEntries(['.topbar','.host-tile','.process-toggle'].map(selector=>{const target=document.querySelector(selector)!,b=target.getBoundingClientRect();return [selector,document.elementFromPoint(b.x+b.width/2,b.y+b.height/2)===e]}));
  e.style.pointerEvents=original;
  return {root:e.parentElement===document.body,rect:[r.x,r.y,r.width,r.height],viewport:[0,0,innerWidth,innerHeight],pointer:style.pointerEvents,top};
 });
 expect(layer.root).toBe(true);expect(layer.rect).toEqual(layer.viewport);expect(layer.pointer).toBe('none');expect(Object.values(layer.top).every(Boolean)).toBe(true);
 const {focus,tap}=await page.evaluate(()=>({focus:(window as Window&{blastFocus?:number[]}).blastFocus!,tap:(window as Window&{blastTap?:number[]}).blastTap!}));expect(Math.abs(focus[0]-tap[0])).toBeLessThan(1);expect(Math.abs(focus[1]-tap[1])).toBeLessThan(1);
 expect(await page.locator('.process-region').boundingBox()).toEqual(before);await expect(row).not.toHaveClass(/exploded/,{timeout:4000});
 await row.click({position:point});const nightWave=await row.locator('.ripple').last().evaluate(e=>({color:getComputedStyle(e).color,border:parseFloat(getComputedStyle(e).borderTopWidth)}));expect(nightWave.border).toBeGreaterThanOrEqual(1);
 await page.screenshot({path:'../build/mobile-compact-night.png'});
 await page.getByRole('button',{name:'切换日夜模式'}).click();await page.waitForTimeout(450);await page.screenshot({path:'../build/mobile-compact-day.png'});
 await row.click({position:point});const dayWave=await row.locator('.ripple').last().evaluate(e=>({color:getComputedStyle(e).color,border:parseFloat(getComputedStyle(e).borderTopWidth)}));expect(dayWave.color).not.toBe(nightWave.color);expect(dayWave.border).toBeGreaterThanOrEqual(nightWave.border);
 await page.getByRole('button',{name:'添加主机',exact:true}).click();await page.locator('.form-grid select').first().selectOption('key');
 const button=(await page.getByRole('button',{name:'导入新私钥'}).boundingBox())!,hint=(await page.locator('.key-selector .hint').boundingBox())!;
 expect(hint.y-button.y-button.height).toBeGreaterThanOrEqual(14);
});

for(const [width,height] of [[320,480],[320,568],[360,640],[390,844],[430,932],[600,960],[768,1024],[1024,1366]]){
 test(`responsive containment at ${width}x${height}`,async({page})=>{
  await page.setViewportSize({width,height});await page.goto('/');await expect(page.locator('.gpu-entry').first()).toBeVisible();await expandProcesses(page);
  expect(await page.locator('.process-search').count()).toBe(0);
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth&&document.documentElement.scrollHeight<=innerHeight)).toBe(true);
  const report=await page.locator('.process-row').first().evaluate(e=>{
   const r=e.getBoundingClientRect();return {row:r.width,inside:[...e.children].every(c=>{const b=c.getBoundingClientRect();return b.left>=r.left-1&&b.right<=r.right+1})};
  });expect(report.inside).toBe(true);
  const identity=await page.locator('.gpu-identity').first().evaluate(e=>{const a=getComputedStyle(e.querySelector('.eyebrow')!),b=getComputedStyle(e.querySelector('h3')!);return {same:a.fontSize===b.fontSize,different:a.fontWeight!==b.fontWeight&&a.color!==b.color}});expect(identity.same).toBe(true);expect(identity.different).toBe(true);
  await expect.poll(async()=>{const row=(await page.locator('.gpu-entry').first().boundingBox())!,button=(await page.getByRole('button',{name:'暂停',exact:true}).boundingBox())!;return Math.abs(row.x+row.width-button.x-button.width)}).toBeLessThan(1.5);
  const top=await page.locator('.topbar').boundingBox(),fleet=await page.locator('.fleet').boundingBox();
  await page.locator('.gpu-list').evaluate(e=>e.scrollTop=10000);await page.locator('.process-list').evaluate(e=>e.scrollTop=10000);
  expect(await page.locator('.topbar').boundingBox()).toEqual(top);expect(await page.locator('.fleet').boundingBox()).toEqual(fleet);
  await page.locator('.gpu-list').evaluate(e=>e.scrollTop=0);await page.screenshot({path:`../build/mobile-responsive-${width}x${height}.png`});
 });
}

test('scroll fades follow hidden edges and history time remains legible',async({page})=>{
 await page.goto('/');await expandProcesses(page);const fleet=page.locator('.host-deck'),gpus=page.locator('.gpu-list'),processes=page.locator('.process-list');
 await expect(fleet).toHaveAttribute('data-fade-start','false');await expect(fleet).toHaveAttribute('data-fade-end','true');
 await fleet.evaluate(e=>e.scrollLeft=e.scrollWidth);await expect(fleet).toHaveAttribute('data-fade-start','true');await expect(fleet).toHaveAttribute('data-fade-end','false');
 await expect(gpus).toHaveAttribute('data-fade-start','false');await expect(gpus).toHaveAttribute('data-fade-end','true');
 await gpus.evaluate(e=>e.scrollTop=(e.scrollHeight-e.clientHeight)/2);await expect(gpus).toHaveAttribute('data-fade-start','true');await expect(gpus).toHaveAttribute('data-fade-end','true');
 await gpus.evaluate(e=>e.scrollTop=e.scrollHeight);await expect(gpus).toHaveAttribute('data-fade-end','false');
 await processes.locator('.process-row').first().evaluate(row=>{for(let i=0;i<15;i++)row.parentElement!.appendChild(row.cloneNode(true))});
 await expect(processes).toHaveAttribute('data-fade-end','true');await processes.evaluate(e=>e.scrollTop=15);await expect(processes).toHaveAttribute('data-fade-start','true');
 const mask=await gpus.evaluate(e=>getComputedStyle(e).maskImage||getComputedStyle(e).webkitMaskImage);expect(mask).toContain('linear-gradient');
 await fleet.evaluate(e=>e.scrollLeft=0);await page.locator('.host-tile').first().getByText('历史').click();
 const chart=page.getByRole('img',{name:'显存占用量曲线'});await expect(chart).toBeVisible();await expect.poll(()=>chart.locator('path').getAttribute('d')).not.toBe('');
 const b=(await chart.boundingBox())!;await chart.dispatchEvent('pointermove',{clientX:b.x+b.width*.55,clientY:b.y+b.height*.5,pointerId:1});
 const label=page.locator('.chart-cursor-time').first();await expect(label).toBeVisible();expect(await label.evaluate(e=>parseFloat(getComputedStyle(e).fontSize))).toBeGreaterThanOrEqual(15);
 expect(await page.locator('.chart-time-axis time').first().evaluate(e=>parseFloat(getComputedStyle(e).fontSize))).toBeGreaterThanOrEqual(13);
 const boundary=await label.evaluate(e=>{const a=e.getBoundingClientRect(),b=e.closest('.chart-stage')!.getBoundingClientRect();return a.left>=b.left&&a.right<=b.right});expect(boundary).toBe(true);
 await page.screenshot({path:'../build/mobile-history-readable-time.png'});
});

test('processes auto-collapse without oscillation and explicit expansion survives refresh',async({page})=>{
 await page.goto('/');const section=page.locator('.process-region');await expect(section).toHaveClass(/is-collapsed/);
 await expect(page.getByRole('button',{name:'展开用卡进程',exact:true})).toHaveAttribute('aria-expanded','false');await expect(page.locator('.process-row').first()).not.toBeVisible();
 const sheen=await page.locator('.process-toggle').evaluate(e=>({name:getComputedStyle(e,'::before').animationName,repeat:getComputedStyle(e,'::before').animationIterationCount}));expect(sheen.name).toBe('spherical-sheen');expect(sheen.repeat).toBe('infinite');
 await page.waitForTimeout(2400);await expect(section).toHaveClass(/is-collapsed/);
 await expandProcesses(page);await expect(page.locator('.process-row').first()).toBeVisible();const height=(await section.boundingBox())!.height;
 await page.waitForTimeout(2400);await expect(section).not.toHaveClass(/is-collapsed/);expect((await section.boundingBox())!.height).toBeCloseTo(height,0);
 await page.locator('.host-tile').filter({hasText:'LISA'}).click();await expect(section).not.toHaveClass(/is-collapsed/);
 await page.locator('.host-tile').filter({hasText:'ATLAS'}).click();await expect(section).not.toHaveClass(/is-collapsed/);
 await page.getByRole('button',{name:'折叠用卡进程',exact:true}).click();await expect(section).toHaveClass(/is-collapsed/);await page.screenshot({path:'../build/mobile-process-auto-collapsed.png'});
});

test('GPU status diamond centres on its text and host status centres below its diamond',async({page})=>{
 await page.goto('/');
 const check=async()=>{
  const result=await page.locator('.gpu-status').first().evaluate(e=>{const a=e.querySelector('.diamond')!.getBoundingClientRect(),b=e.querySelector('strong')!.getBoundingClientRect();return Math.abs(a.y+a.height/2-b.y-b.height/2)});expect(result).toBeLessThan(.6);
  const right=await page.locator('.host-tile').first().evaluate(e=>{const a=e.querySelector('.diamond')!.getBoundingClientRect(),b=e.querySelector('.host-state')!.getBoundingClientRect();return Math.abs((a.left+a.width/2)-(b.left+b.width/2))});expect(right).toBeLessThan(.6);
 };
 await check();await page.getByRole('button',{name:'切换日夜模式'}).click();await check();await page.getByRole('button',{name:'暂停',exact:true}).click();await check();
});


test('process panel slides through intermediate heights in both directions and reverses cleanly',async({page})=>{
 await page.goto('/');await expandProcesses(page);
 const sample=()=>page.locator('.process-region').evaluate(async section=>{
  const heights:number[]=[];const start=performance.now();(section.querySelector('.process-toggle') as HTMLButtonElement).click();
  while(performance.now()-start<520){heights.push(section.getBoundingClientRect().height);await new Promise(requestAnimationFrame)}
  return heights;
 });
 const closing=await sample();expect(closing[0]-closing.at(-1)!).toBeGreaterThan(25);
 expect(closing.some(h=>h<closing[0]-8&&h>closing.at(-1)!+8)).toBe(true);
 for(let i=1;i<closing.length;i++)expect(closing[i]-closing[i-1]).toBeLessThan(1);
 await expect(page.locator('.process-body')).toHaveAttribute('inert','');
 await expect(page.locator('.process-row').first()).not.toBeVisible();
 const opening=await sample();expect(opening.at(-1)!-opening[0]).toBeGreaterThan(25);
 expect(opening.some(h=>h>opening[0]+8&&h<opening.at(-1)!-8)).toBe(true);
 await expect(page.locator('.process-row').first()).toBeVisible();
 await page.locator('.process-toggle').evaluate(async e=>{(e as HTMLButtonElement).click();await new Promise(r=>setTimeout(r,90));(e as HTMLButtonElement).click()});
 await expect.poll(()=>page.locator('.process-region').evaluate(e=>Number(getComputedStyle(e).flexGrow))).toBeCloseTo(.62,3);
 await expect(page.locator('.process-toggle')).toHaveAttribute('aria-expanded','true');
 await page.emulateMedia({reducedMotion:'reduce'});
 await page.getByRole('button',{name:'折叠用卡进程',exact:true}).click();
 expect(await page.locator('.process-region').evaluate(e=>Math.max(...getComputedStyle(e).transitionDuration.split(',').map(Number.parseFloat)))).toBeLessThan(.001);
});


test('perimeter glow travels continuously and stays absent through explosion and delayed recovery',async({page})=>{
 await page.goto('/');const card=page.locator('.gpu-entry.zero-glow').first();await expect(card).toBeVisible();
 const label=await card.getAttribute('aria-label');const stable=page.locator('.gpu-entry').filter({has:page.locator('.gpu-identity h3')}).and(page.getByRole('article',{name:label!,exact:true}));
 const travel=await card.locator('[data-orbit-head]').evaluate(async el=>{
  const samples:{offset:number;time:number}[]=[];
  for(let i=0;i<8;i++){samples.push({offset:parseFloat(getComputedStyle(el).strokeDashoffset),time:performance.now()});await new Promise(r=>setTimeout(r,45))}
  return samples;
 });
 for(let i=1;i<travel.length;i++){
  const delta=(travel[i-1].offset-travel[i].offset+1000)%1000;
  expect(Math.abs(delta-(travel[i].time-travel[i-1].time)/8)).toBeLessThan(4);
 }
 await card.click({clickCount:5,delay:40,position:{x:35,y:40}});
 await expect(stable).toHaveClass(/exploded/);await expect(stable.locator('.orbit-glow')).toHaveCount(0);
 await expect(page.locator('canvas.burst')).toHaveCount(0,{timeout:2500});
 await page.waitForTimeout(900);await expect(stable).toHaveClass(/exploded/);await expect(stable.locator('.orbit-glow')).toHaveCount(0);
 await expect(stable).toHaveClass(/reborn/,{timeout:2500});await expect(stable.locator('.orbit-glow')).toHaveCount(0);
 await expect(stable.locator('.orbit-glow')).toHaveCount(1,{timeout:2000});
 await expect(stable).not.toHaveClass(/exploded|reborn/);
});


test('day and night colors pass through intermediate shades without moving layout',async({page})=>{
 await page.goto('/');await page.evaluate(()=>document.fonts.ready);await page.waitForTimeout(500);
 const card=page.locator('.gpu-entry').first(),rect=await card.boundingBox();
 const capture=()=>card.evaluate(e=>getComputedStyle(e).backgroundColor);
 const night=await capture();await page.getByRole('button',{name:'切换日夜模式'}).click();await page.waitForTimeout(90);const between=await capture();await page.waitForTimeout(450);const day=await capture();
 expect(between).not.toBe(night);expect(between).not.toBe(day);expect(await card.boundingBox()).toEqual(rect);
 await page.getByRole('button',{name:'切换日夜模式'}).click();await page.waitForTimeout(90);const returning=await capture();expect(returning).not.toBe(day);expect(returning).not.toBe(night);await page.waitForTimeout(450);expect(await capture()).toBe(night);
});
