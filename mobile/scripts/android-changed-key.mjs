import {_android as android,expect} from '@playwright/test';
import {readFile,writeFile} from 'node:fs/promises';
const pkg='top.nullsf.gpuchecker',device=(await android.devices()).find(d=>d.serial()==='emulator-5580');
const page=await(await device.webView({pkg})).page();
try{
 const original=await page.evaluate(()=>window.Capacitor.Plugins.GpuMonitor.getState());
 const h=original.hosts.find(h=>h.name==='EMULATOR · KEY');
 await page.evaluate(id=>window.Capacitor.Plugins.GpuMonitor.connect({id}),h.id);
 let st;
 for(let i=0;i<90;i++){st=await page.evaluate(()=>window.Capacitor.Plugins.GpuMonitor.getState());if(st.runtimes[h.id]?.message.includes('指纹'))break;await new Promise(r=>setTimeout(r,250))}
 expect(st.runtimes[h.id].message).toContain('指纹');expect(st.runtimes[h.id].fresh).toBe(false);expect(st.runtimes[h.id].snapshot.gpus.length).toBe(2);
 const events=JSON.parse(await readFile('../build/mobile-ssh-changed-events.json','utf8'));
 expect(events.passwordAttempts).toBe(0);expect(events.keyAttempts).toBe(0);
 await page.evaluate(id=>window.Capacitor.Plugins.GpuMonitor.pause({id}),h.id);
 await page.evaluate(()=>window.Capacitor.Plugins.GpuMonitor.copyHosts());
 await writeFile('../build/mobile-android-changed-key-report.json',JSON.stringify({passed:'Changed host key rejected before sending either credential; frozen snapshot retained; native metadata clipboard export succeeds',events},null,2));
 console.log('Changed fingerprint rejection before authentication passed.');
}finally{await device.close()}
