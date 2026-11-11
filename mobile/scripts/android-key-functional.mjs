import {_android as android,expect} from '@playwright/test';
import {readFile,writeFile} from 'node:fs/promises';import {resolve} from 'node:path';import {execFileSync} from 'node:child_process';
const port=process.env.GPU_TEST_KEY_PORT??'41723';
const root=resolve('..'),pkg='top.nullsf.gpuchecker',serial='emulator-5580';
execFileSync('adb',['-s',serial,'push',resolve(root,'build/mobile-ssh-client.pem'),'/sdcard/Download/gpu-fixture-key.pem']);
let device=(await android.devices()).find(d=>d.serial()===serial);device.setDefaultTimeout(20000);
let page=await(await device.webView({pkg})).page();const state=()=>page.evaluate(()=>window.Capacitor.Plugins.GpuMonitor.getState());
const events=async()=>JSON.parse(await readFile(resolve(root,'build/mobile-ssh-key-events.json'),'utf8'));
async function tap(selector){for(let i=0;i<4;i++){try{return await device.tap(selector)}catch(e){if(!String(e).includes('StaleObject')||i===3)throw e;await new Promise(r=>setTimeout(r,350))}}}
async function poll(fn,label){for(let i=0;i<100;i++){if(await fn())return;await new Promise(r=>setTimeout(r,250))}throw Error(label)}
try{
 await page.evaluate(async()=>{const api=window.Capacitor.Plugins.GpuMonitor;const s=await api.getState();for(const h of s.hosts)if(h.name==='EMULATOR · KEY')await api.removeHost({id:h.id})});
 if(await page.getByRole('dialog').count())await page.getByRole('button',{name:'关闭窗口'}).click();
 await page.getByRole('button',{name:'添加主机',exact:true}).click();await page.getByLabel('显示名称',{exact:true}).fill('EMULATOR · KEY');await page.getByLabel('主机地址',{exact:true}).fill('10.0.2.2');await page.getByLabel('用户名',{exact:true}).fill('mobile-test');await page.getByLabel('端口',{exact:true}).fill(port);await page.locator('.form-grid select').selectOption('key');
 await page.getByRole('button',{name:'安全配置认证'}).click();
 await tap({desc:'Show roots'});await new Promise(r=>setTimeout(r,700));
 await tap({text:'Downloads',res:'android:id/title'});await new Promise(r=>setTimeout(r,700));
 await tap({text:'gpu-fixture-key.pem'});await device.wait({clazz:'android.widget.EditText',pkg});
 await device.fill({desc:'私钥口令'},'fixture-key-passphrase');await device.tap({res:'android:id/button1'});
 await device.wait({text:'核对 SSH 主机指纹'});expect((await events()).keyAttempts).toBe(0);await device.tap({res:'android:id/button1'});
 page=await(await device.webView({pkg})).page();
 await poll(async()=>{const s=await state();const h=s.hosts.find(h=>h.name==='EMULATOR · KEY');return h&&s.runtimes[h.id]?.fresh},'Private-key authentication did not produce a sample');
 const s=await state(),keyHost=s.hosts.find(h=>h.name==='EMULATOR · KEY'),passwordHost=s.hosts.find(h=>h.name==='EMULATOR · SSH');expect(s.runtimes[passwordHost.id].fresh).toBe(true);expect((await events()).keyAccepted).toBeGreaterThan(0);
 const serialized=JSON.stringify(s);expect(serialized).not.toContain('PRIVATE KEY-----');expect(serialized).not.toContain('fixture-key-passphrase');
 const keysBefore=(await events()).keyAccepted;
 execFileSync('adb',['-s',serial,'shell','am','force-stop',pkg]);execFileSync('adb',['-s',serial,'shell','am','start','-n',pkg+'/.MainActivity']);await new Promise(r=>setTimeout(r,1300));page=await(await device.webView({pkg})).page();
 await poll(async()=>{const st=await state();return st.runtimes[keyHost.id]?.fresh&&st.runtimes[passwordHost.id]?.fresh},'Independent saved credentials did not restore both hosts');
 expect((await events()).keyAccepted).toBeGreaterThan(keysBefore);
 await page.locator('.host-tile').filter({hasText:'EMULATOR · KEY'}).click();await page.getByRole('button',{name:'暂停',exact:true}).click();
 const paused=await state();expect(paused.runtimes[passwordHost.id].fresh).toBe(true);expect(paused.hosts.find(h=>h.id===keyHost.id).autoconnect).toBe(false);
 await writeFile(resolve(root,'build/mobile-android-key-report.json'),JSON.stringify({passed:['Native SAF encrypted RSA key import, passphrase authentication, host trust before key authentication','Both independent SSH sessions live together','Both Keystore credentials restore after process restart','Pausing one host leaves the other SSH session live','No key or passphrase returned in frontend state'],events:await events(),keyHostId:keyHost.id,passwordHostId:passwordHost.id},null,2));
 console.log('Encrypted private-key import, authentication, restart restore, multi-host isolation, and credential boundary passed.');
}finally{execFileSync('adb',['-s',serial,'shell','rm','-f','/sdcard/Download/gpu-fixture-key.pem']);await device.close()}
