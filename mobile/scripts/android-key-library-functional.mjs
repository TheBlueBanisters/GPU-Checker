// Isolated emulator test only. Start ssh_fixture.py on 41724 and 41725 first.
import {_android as android,expect} from '@playwright/test';
import {execFileSync} from 'node:child_process';
import {readFile,writeFile} from 'node:fs/promises';
import {resolve} from 'node:path';
const serial='emulator-5580',pkg='top.nullsf.gpuchecker';
const adb=(...args)=>execFileSync('adb',['-s',serial,...args],{encoding:'utf8'});
adb('push',resolve('../build/mobile-ssh-client.pem'),'/sdcard/Download/gpu-library-fixture.pem');
const device=(await android.devices()).find(d=>d.serial()===serial);device.setDefaultTimeout(20000);
let page=await(await device.webView({pkg})).page();
const state=()=>page.evaluate(()=>window.Capacitor.Plugins.GpuMonitor.getState());
async function tap(selector){for(let i=0;i<4;i++){try{return await device.tap(selector)}catch(e){if(!String(e).includes('StaleObject')||i===3)throw e;await new Promise(r=>setTimeout(r,500))}}}
async function poll(fn,label){for(let i=0;i<100;i++){if(await fn())return;await new Promise(r=>setTimeout(r,250))}throw Error(label)}
const ids=[];
try{
 if(await page.getByRole('dialog').count())await page.getByRole('button',{name:'关闭窗口'}).click();
 await page.getByRole('button',{name:'设置',exact:true}).click();
 if(!(await state()).keys.some(k=>k.name==='Shared emulator key')){await page.getByRole('button',{name:'导入私钥到密钥库'}).click();
 await tap({desc:'Show roots'});await new Promise(r=>setTimeout(r,600));await tap({text:'Downloads',res:'android:id/title'});
 await tap({text:'gpu-library-fixture.pem'});await device.wait({desc:'私钥口令'});
 await device.fill({desc:'密钥名称'},'Shared emulator key');await device.fill({desc:'私钥口令'},'fixture-key-passphrase');await tap({res:'android:id/button1'});
 }
 await poll(async()=>Boolean((await state()).keys.find(k=>k.name==='Shared emulator key')),'Native key import failed');
 const imported=(await state()).keys.find(k=>k.name==='Shared emulator key');
 await expect(page.getByRole('textbox',{name:'密钥名称 Shared emulator key'})).toBeVisible();
 await page.getByRole('button',{name:'关闭窗口'}).click();
 for(const [port,name] of [[41724,'Library host A'],[41725,'Library host B']]){
  await page.getByRole('button',{name:'添加主机',exact:true}).click();
  await page.getByLabel('显示名称',{exact:true}).fill(name);await page.getByLabel('主机地址',{exact:true}).fill('10.0.2.2');await page.getByLabel('用户名',{exact:true}).fill('mobile-test');await page.getByLabel('端口',{exact:true}).fill(String(port));
  await page.locator('.form-grid select').first().selectOption('key');await page.getByLabel('使用的私钥',{exact:true}).selectOption(imported.id);await page.getByRole('button',{name:'保存',exact:true}).click();
  await device.wait({text:'核对 SSH 主机指纹'});await tap({res:'android:id/button1'});
  await poll(async()=>{const s=await state(),h=s.hosts.find(h=>h.name===name);return h&&s.runtimes[h.id]?.fresh},'Shared key did not authenticate '+name);
  ids.push((await state()).hosts.find(h=>h.name===name).id);
 }
 let s=await state();expect(s.keys.find(k=>k.id===imported.id).usedBy.length).toBe(2);expect(s.hosts.filter(h=>ids.includes(h.id)).every(h=>h.keyId===imported.id&&h.credentialReady)).toBe(true);
 expect(JSON.stringify(s)).not.toContain('PRIVATE KEY-----');expect(JSON.stringify(s)).not.toContain('fixture-key-passphrase');
 const prefs=adb('shell','run-as',pkg,'cat','shared_prefs/encrypted_credentials.xml');expect(prefs).not.toContain('fixture-key-passphrase');expect(prefs).not.toContain('PRIVATE KEY-----');
 adb('shell','am','force-stop',pkg);adb('shell','am','start','-n',pkg+'/.MainActivity');await new Promise(r=>setTimeout(r,1200));page=await(await device.webView({pkg})).page();
 await poll(async()=>{const st=await state();return ids.every(id=>st.runtimes[id]?.fresh)},'Saved shared key/bindings did not survive restart');
 await page.getByRole('button',{name:'设置',exact:true}).click();await expect(page.getByText('2 台主机使用')).toBeVisible();
 await page.screenshot({path:'../build/mobile-key-library.png'});
 await page.getByRole('button',{name:'删除私钥 Shared emulator key'}).click();await device.wait({text:'删除此私钥？'});await tap({res:'android:id/button1'});
 await poll(async()=>!(await state()).keys.some(k=>k.id===imported.id),'Key removal did not persist');
 s=await state();expect(s.hosts.filter(h=>ids.includes(h.id)).length).toBe(2);
 for(const id of ids){expect(s.hosts.find(h=>h.id===id).autoconnect).toBe(false);expect(s.hosts.find(h=>h.id===id).keyId).toBeUndefined();expect(s.runtimes[id].fresh).toBe(false);expect(s.runtimes[id].snapshot.gpus.length).toBe(2)}
 await writeFile('../build/mobile-key-library-report.json',JSON.stringify({passed:['Native SAF import into encrypted shared library','Same imported key authenticates two independent SSH endpoints','Two bindings and key survive process restart and reconnect without input','Only public key metadata crosses the bridge; encrypted storage has no plaintext key/passphrase','Deleting a shared key requires native confirmation, pauses both hosts and preserves both snapshots'],events:JSON.parse(await readFile('../build/mobile-library-ssh-events.json','utf8')),events2:JSON.parse(await readFile('../build/mobile-library-ssh-events2.json','utf8'))},null,2));
 for(const id of ids)await page.evaluate(id=>window.Capacitor.Plugins.GpuMonitor.removeHost({id}),id);
 console.log('Shared native key library import, reuse, restart, deletion isolation and credential boundary passed.');
}finally{adb('shell','rm','-f','/sdcard/Download/gpu-library-fixture.pem');await device.close()}
