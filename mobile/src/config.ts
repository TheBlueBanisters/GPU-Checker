import type {Host} from './types';
export const id=()=>globalThis.crypto?.randomUUID?.()??'host-'+Date.now().toString(36)+'-'+Math.random().toString(36).slice(2);
export function parseConfig(text:string):Host[]{
 if(text.length>524288)throw Error('配置超过 512 KiB');
 if(/^[\s]*[\[{]/.test(text)){
  let parsed:unknown;try{parsed=JSON.parse(text)}catch{throw Error('JSON 配置格式错误')}
  const source=Array.isArray(parsed)?parsed:(parsed as {hosts?:unknown})?.hosts;
  if(!Array.isArray(source)||!source.length||source.length>200)throw Error('配置需要 1–200 个 hosts 条目');
  return source.map((entry:unknown,index)=>{
   if(!entry||typeof entry!=='object')throw Error(`第 ${index+1} 个主机无效`);
   const h=entry as Record<string,unknown>,host=String(h.host??''),user=String(h.user??''),port=Number(h.port??22);
   if(!host||/\s|^[-]/.test(host)||!user.match(/^[A-Za-z0-9_.@+\-]+$/)||!Number.isInteger(port)||port<1||port>65535)throw Error(`第 ${index+1} 个主机缺少有效地址、用户或端口`);
   const mode=h.mode??'password';if(mode!=='password'&&mode!=='key')throw Error(`第 ${index+1} 个主机认证方式无效`);
   return {id:id(),name:String(h.name??host),host,user,port,mode,interval:Math.min(60,Math.max(1,Number(h.interval)||2)),autoconnect:true,retry:h.retry!==false} satisfies Host;
  });
 }
 const blocks:{aliases:string[];fields:Record<string,string>}[]=[];let current:typeof blocks[number]|undefined;
 for(const [index,line] of text.split(/\r?\n/).entries()){
  const clean=line.replace(/\s+#.*$/,'').trim();if(!clean||clean.startsWith('#'))continue;
  const m=clean.match(/^(\w+)(?:\s*=\s*|\s+)(.+)$/);if(!m)throw Error(`第 ${index+1} 行格式错误`);
  const key=m[1].toLowerCase();let value=m[2].trim().replace(/^"(.*)"$/,'$1');
  if(['include','match','proxycommand','proxyjump'].includes(key))throw Error(`移动端暂不支持 ${m[1]}；不会执行配置中的命令`);
  if(key==='host'){current={aliases:value.split(/\s+/),fields:{}};blocks.push(current)}
  else{if(!current)throw Error(`第 ${index+1} 行需放在 Host 条目内`);current.fields[key]??=value}
 }
 const exact=blocks.flatMap(b=>b.aliases.filter(n=>!/[*!?]/.test(n)));if(!exact.length)throw Error('缺少具体 Host 条目');
 return [...new Set(exact)].map(name=>{
  const fields:Record<string,string>={};
  for(const block of blocks)if(block.aliases.includes(name)||block.aliases.includes('*'))for(const [key,value] of Object.entries(block.fields))fields[key]??=value;
  if(!fields.hostname&&!/[.:]/.test(name))throw Error(`Host ${name} 缺少 HostName`);
  if(!fields.user)throw Error(`Host ${name} 缺少 User`);
  const host=fields.hostname??name;const port=Number(fields.port??22);
  if(!host||/\s|^[-]/.test(host)||!Number.isInteger(port)||port<1||port>65535)throw Error(`Host ${name} 地址或端口无效`);
  return {id:id(),name,host,user:fields.user,port,mode:fields.identityfile?'key':'password',interval:2,autoconnect:true,retry:true};
 });
}
