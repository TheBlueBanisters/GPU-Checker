package top.nullsf.gpuchecker

import android.app.Activity
import android.app.AlertDialog
import android.content.Context
import android.content.Intent
import android.os.Handler
import android.os.Looper
import android.util.AtomicFile
import android.util.Base64
import androidx.core.content.ContextCompat
import com.jcraft.jsch.*
import org.json.JSONArray
import org.json.JSONObject
import java.io.BufferedInputStream
import java.io.ByteArrayOutputStream
import java.security.MessageDigest
import java.util.UUID
import java.util.concurrent.ConcurrentHashMap
import java.util.concurrent.CountDownLatch
import java.util.concurrent.Executors
import java.util.concurrent.Semaphore
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicBoolean

class MonitorEngine private constructor(val context:Context) {
    companion object { @Volatile private var instance:MonitorEngine?=null;fun get(context:Context):MonitorEngine=instance?:synchronized(this){instance?:MonitorEngine(context.applicationContext).also {instance=it}} }
    val vault=Vault(context);val history=HistoryStore(context);val keys=KeyLibrary(context,vault)
    private val prefs=context.getSharedPreferences("monitor",Context.MODE_PRIVATE)
    private val pool=Executors.newCachedThreadPool()
    private val handler=Handler(Looper.getMainLooper())
    private val workers=ConcurrentHashMap<String,Worker>()
    private val runtimes=ConcurrentHashMap<String,JSONObject>()
    private val memorySecrets=ConcurrentHashMap<String,JSONObject>()
    private val trustLock=Semaphore(1,true)
    @Volatile var activity:Activity?=null
    @Volatile var changed:(()->Unit)?=null
    private var booted=false
    private var profiles=try{JSONArray(prefs.getString("hosts","[]"))}catch(e:Exception){JSONArray()}
    init {
        migrateLegacyKeys()
        for(i in 0 until profiles.length()) {
            val h=profiles.getJSONObject(i);val snapshot=try {JSONObject(snapshotFile(h.getString("id")).openRead().bufferedReader().use {it.readText()})}catch(e:Exception){null}
            runtimes[h.getString("id")]=JSONObject().put("status",if(h.optBoolean("autoconnect"))"等待连接" else "已暂停").put("message","保留最后快照").put("fresh",false).apply {if(snapshot!=null)put("snapshot",snapshot)}
        }
        val timer=Executors.newSingleThreadScheduledExecutor()
        timer.scheduleAtFixedRate({
            for((id,worker) in workers) {
                val elapsed=System.currentTimeMillis()-worker.lastSample
                if(elapsed>maxOf(35_000,worker.interval*2000+15000))worker.disconnect()
                if(elapsed>maxOf(10_000,worker.interval*2000+5000)&&runtimes[id]?.optBoolean("fresh")==true)update(id,worker,"数据过期","等待新采样；显示历史快照",false)
            }
        },2,2,TimeUnit.SECONDS)
    }
    private fun snapshotFile(id:String):AtomicFile {require(id.matches(Regex("[A-Za-z0-9_-]{1,80}")));val folder=java.io.File(context.filesDir,"snapshots");folder.mkdirs();return AtomicFile(java.io.File(folder,"$id.json"))}
    @Synchronized fun host(id:String):JSONObject?=(0 until profiles.length()).map {profiles.getJSONObject(it)}.find {it.optString("id")==id}?.let {JSONObject(it.toString())}
    fun endpoint(h:JSONObject)=MessageDigest.getInstance("SHA-256").digest((listOf(h.optString("host"),h.optInt("port",22).toString(),h.optString("user"),h.optString("mode","password"))+if(h.optString("keyId").isNotBlank())listOf(h.getString("keyId"))else emptyList()).joinToString("\u0000").toByteArray()).joinToString(""){"%02x".format(it)}
    private fun pinKey(h:JSONObject)="pin-"+MessageDigest.getInstance("SHA-256").digest("${h.optString("host")}:${h.optInt("port",22)}".toByteArray()).joinToString(""){"%02x".format(it)}
    private fun ready(h:JSONObject):Boolean {if(h.optString("mode")=="key"&&h.optString("keyId").isNotBlank())return keys.has(h.getString("keyId"));val id=h.getString("id");return memorySecrets[id]?.optString("endpoint")==endpoint(h)||(vault.has(id)&&prefs.getString("credential-$id",null)==endpoint(h))}
    @Synchronized fun state():JSONObject {
        val hosts=JSONArray();for(i in 0 until profiles.length()) {val h=JSONObject(profiles.getJSONObject(i).toString());h.put("credentialReady",ready(h));hosts.put(h)}
        val rs=JSONObject();for((id,r) in runtimes)rs.put(id,JSONObject(r.toString()))
        val library=keys.list();for(i in 0 until library.length()){val key=library.getJSONObject(i);key.put("usedBy",JSONArray((0 until profiles.length()).map{profiles.getJSONObject(it)}.filter{it.optString("keyId")==key.getString("id")}.map{it.optString("name")}))}
        return JSONObject().put("hosts",hosts).put("runtimes",rs).put("keys",library).put("portrait",(activity?.resources?:context.resources).configuration.orientation!=android.content.res.Configuration.ORIENTATION_LANDSCAPE)
    }
    @Synchronized private fun persist(){check(prefs.edit().putString("hosts",profiles.toString()).commit())}
    fun announce(){handler.post {changed?.invoke()}}
    @Synchronized fun boot(){if(booted)return;booted=true;for(i in 0 until profiles.length()){val h=profiles.getJSONObject(i);if(h.optBoolean("autoconnect"))connect(h.getString("id"))}}
    @Synchronized fun save(input:JSONObject,autostart:Boolean=true):JSONObject {
        val id=input.optString("id");require(id.matches(Regex("[A-Za-z0-9_-]{1,80}"))){"主机 ID 无效"}
        val h=JSONObject();for(key in listOf("id","name","host","user","port","mode","interval","autoconnect","retry","keyId"))if(input.has(key))h.put(key,input.get(key))
        require(h.optString("host").isNotBlank()&&!h.optString("host").contains(Regex("\\s"))&&!h.optString("host").startsWith("-")){"主机地址无效"}
        require(h.optString("user").matches(Regex("[A-Za-z0-9_.@+\\-]+"))){"用户名无效"}
        require(h.optInt("port") in 1..65535){"端口无效"};require(h.optString("mode") in listOf("password","key")){"认证方式无效"}
        h.put("interval",h.optInt("interval",2).coerceIn(1,60));h.put("name",h.optString("name").ifBlank {h.getString("host")});h.put("retry",h.optBoolean("retry",true))
        if(h.getString("mode")=="password")h.remove("keyId")
        if(h.optString("keyId").isNotBlank())require(keys.has(h.getString("keyId"))){"所选私钥不存在，请重新选择"}
        val old=host(id);if(old!=null&&endpoint(old)!=endpoint(h)){vault.remove(id);memorySecrets.remove(id);prefs.edit().remove("credential-$id").apply()}
        workers.remove(id)?.stop();val next=JSONArray();for(i in 0 until profiles.length())if(profiles.getJSONObject(i).getString("id")!=id)next.put(profiles.getJSONObject(i));next.put(h);profiles=next;persist()
        if(autostart&&h.optBoolean("autoconnect"))connect(id) else update(id,null,"已暂停","随时可以恢复监控",false)
        announce();return state()
    }
    @Synchronized fun importHosts(imported:JSONArray):JSONObject {
        // Validate the complete batch before saving anything.
        for(i in 0 until imported.length()){val h=imported.getJSONObject(i);require(h.optString("host").isNotBlank()&&h.optString("user").matches(Regex("[A-Za-z0-9_.@+\\-]+"))&&h.optInt("port") in 1..65535&&h.optString("id").matches(Regex("[A-Za-z0-9_-]{1,80}"))){"导入配置无效"}}
        for(i in 0 until imported.length()){val h=imported.getJSONObject(i);val exists=(0 until profiles.length()).any {val p=profiles.getJSONObject(it);p.optString("host")==h.optString("host")&&p.optString("user")==h.optString("user")&&p.optInt("port")==h.optInt("port")};if(!exists)save(h.put("autoconnect",true))}
        return state()
    }
    @Synchronized fun migrateLegacyKeys(){
        for(i in 0 until profiles.length()){
            val h=profiles.getJSONObject(i);val id=h.optString("id")
            if(h.optString("mode")!="key"||h.optString("keyId").isNotBlank())continue
            try{val secret=vault.get(id)?:continue
                if(secret.optString("endpoint")!=endpoint(h)||!secret.has("key"))continue
                val entry=keys.add(h.optString("name",h.optString("host"))+" 私钥",secret.getString("key"),secret.optString("passphrase"))
                h.put("keyId",entry.getString("id"));persist();vault.remove(id);prefs.edit().remove("credential-$id").commit()
            }catch(_:Exception){/* Retain the legacy credential if it cannot be migrated. */}
        }
    }
    @Synchronized fun assignKey(id:String,keyId:String){val h=host(id)?:error("主机不存在");require(h.optString("mode")=="key");save(h.put("keyId",keyId))}
    @Synchronized fun removeKey(keyId:String):JSONObject {
        require(keys.has(keyId)){"私钥不存在"}
        val affected=(0 until profiles.length()).map{profiles.getJSONObject(it)}.filter{it.optString("keyId")==keyId}.map{it.getString("id")}
        for(id in affected){pause(id);for(i in 0 until profiles.length())if(profiles.getJSONObject(i).getString("id")==id)profiles.getJSONObject(i).remove("keyId");update(id,null,"待认证","原私钥已从密钥库删除，请重新选择；主机和快照仍保留",false)}
        persist();keys.remove(keyId);announce();return state()
    }
    @Synchronized fun remove(id:String):JSONObject {pause(id);vault.remove(id);memorySecrets.remove(id);prefs.edit().remove("credential-$id").apply();profiles=JSONArray((0 until profiles.length()).map{profiles.getJSONObject(it)}.filter{it.getString("id")!=id});persist();runtimes.remove(id);snapshotFile(id).delete();announce();return state()}
    @Synchronized fun saveSecret(id:String,secret:JSONObject,remember:Boolean){val h=host(id)?:error("主机不存在");secret.put("endpoint",endpoint(h));if(remember){vault.put(id,secret);prefs.edit().putString("credential-$id",endpoint(h)).commit();memorySecrets.remove(id)}else{vault.remove(id);prefs.edit().remove("credential-$id").commit();memorySecrets[id]=secret};announce()}
    @Synchronized fun pause(id:String):JSONObject {workers.remove(id)?.stop();for(i in 0 until profiles.length())if(profiles.getJSONObject(i).getString("id")==id)profiles.getJSONObject(i).put("autoconnect",false);persist();update(id,null,"已暂停","显示暂停前最后快照",false);if(workers.isEmpty())context.stopService(Intent(context,SshService::class.java));announce();return state()}
    @Synchronized fun timeout(){for(id in workers.keys.toList()){pause(id);update(id,null,"已暂停","Android 已限制后台运行，请返回应用恢复监控",false)}}
    @Synchronized fun connect(id:String):JSONObject {
        val h=host(id)?:error("主机不存在");if(workers[id]?.active?.get()==true)return state()
        for(i in 0 until profiles.length())if(profiles.getJSONObject(i).getString("id")==id)profiles.getJSONObject(i).put("autoconnect",true);persist()
        if(!ready(h)){update(id,null,"待认证","请点击安全配置认证，凭据只在原生端保存",false);return state()}
        try{ContextCompat.startForegroundService(context,Intent(context,SshService::class.java))}catch(e:Exception){update(id,null,"待恢复","系统限制后台启动，请回到应用恢复连接",false);return state()}
        val worker=Worker(id,h);workers[id]=worker;pool.execute {worker.run()};update(id,worker,"连接中","正在建立加密连接",false);return state()
    }
    @Synchronized fun resetPin(id:String){val h=host(id)?:return;prefs.edit().remove(pinKey(h)).commit()}
    @Synchronized private fun update(id:String,worker:Worker?,status:String,message:String,fresh:Boolean,sample:JSONObject?=null){if(worker!=null&&workers[id]!==worker)return;val r=JSONObject(runtimes[id]?.toString()?:"{}");r.put("status",status).put("message",message).put("fresh",fresh);if(sample!=null)r.put("snapshot",sample);runtimes[id]=r;announce()}
    private fun verify(h:JSONObject,key:ByteArray,active:AtomicBoolean):Int {
        val fingerprint="SHA256:"+Base64.encodeToString(MessageDigest.getInstance("SHA-256").digest(key),Base64.NO_WRAP or Base64.NO_PADDING)
        val pin=pinKey(h);prefs.getString(pin,null)?.let {return if(it==fingerprint)HostKeyRepository.OK else HostKeyRepository.CHANGED}
        if(!trustLock.tryAcquire(60,TimeUnit.SECONDS))return HostKeyRepository.NOT_INCLUDED
        try {
            prefs.getString(pin,null)?.let {return if(it==fingerprint)HostKeyRepository.OK else HostKeyRepository.CHANGED}
            val latch=CountDownLatch(1);val accepted=AtomicBoolean(false);val a=activity?:return HostKeyRepository.NOT_INCLUDED
            handler.post {if(a.isFinishing||!active.get()){latch.countDown();return@post};AlertDialog.Builder(a).setTitle("核对 SSH 主机指纹").setMessage("${h.optString("host")}:${h.optInt("port")}\n\n$fingerprint\n\n请与管理员提供的指纹核对。此确认在发送密码或私钥认证之前进行。")
                .setPositiveButton("信任并连接"){_,_->accepted.set(true);latch.countDown()}.setNegativeButton("取消"){_,_->latch.countDown()}.setOnCancelListener {latch.countDown()}.show()}
            var elapsed=0;while(active.get()&&elapsed++<60&&!latch.await(1,TimeUnit.SECONDS)){}
            if(accepted.get()&&active.get()){prefs.edit().putString(pin,fingerprint).commit();return HostKeyRepository.OK}
            return HostKeyRepository.NOT_INCLUDED
        } finally {trustLock.release()}
    }
    private inner class Worker(val id:String,val profile:JSONObject) {
        val active=AtomicBoolean(true);val interval=profile.optInt("interval",2);@Volatile var lastSample=System.currentTimeMillis()
        @Volatile private var session:Session?=null;@Volatile private var channel:ChannelExec?=null
        fun disconnect(){try{channel?.disconnect()}catch(_:Exception){};try{session?.disconnect()}catch(_:Exception){}}
        fun stop(){active.set(false);disconnect()}
        fun run(){var attempt=0;while(active.get()){
            try {
                update(id,this,"连接中","正在建立加密连接",false);lastSample=System.currentTimeMillis()
                val libraryKey=profile.optString("mode")=="key"&&profile.optString("keyId").isNotBlank()
                val secret=if(libraryKey)keys.secret(profile.getString("keyId"))?:error("所选私钥不存在，需要重新配置认证")else memorySecrets[id]?:vault.get(id)?:error("需要重新配置认证")
                if(!libraryKey)check(secret.optString("endpoint")==endpoint(profile)){"主机端点改变，需要重新配置认证"}
                val jsch=JSch();jsch.setHostKeyRepository(object:HostKeyRepository{
                    override fun check(host:String,key:ByteArray):Int=verify(profile,key,active)
                    override fun add(hostkey:HostKey,ui:UserInfo?){};override fun remove(host:String,type:String?){};override fun remove(host:String,type:String?,key:ByteArray?){}
                    override fun getKnownHostsRepositoryID()="GPUChecker pinned fingerprints"
                    override fun getHostKey():Array<HostKey> = emptyArray();override fun getHostKey(host:String?,type:String?):Array<HostKey> = emptyArray()
                })
                if(profile.getString("mode")=="key"){
                    val bytes=secret.getString("key").toByteArray(Charsets.UTF_8);val pass=secret.optString("passphrase").toByteArray(Charsets.UTF_8)
                    try{jsch.addIdentity("gpu-checker",bytes,null,pass)}finally{bytes.fill(0);pass.fill(0)}
                }
                val s=jsch.getSession(profile.getString("user"),profile.getString("host").removeSurrounding("[","]"),profile.optInt("port",22));session=s
                s.setConfig("StrictHostKeyChecking","yes");s.setConfig("PreferredAuthentications",if(profile.getString("mode")=="password")"password,keyboard-interactive" else "publickey")
                if(profile.getString("mode")=="password")s.setPassword(secret.getString("password"))
                s.serverAliveInterval=10_000;s.serverAliveCountMax=3;s.setTimeout(maxOf(35_000,interval*2000+15000));s.connect(15_000)
                if(!active.get())break
                val c=s.openChannel("exec") as ChannelExec;channel=c;c.setPty(false)
                val probe=context.assets.open("remote_probe.py").use{Base64.encodeToString(it.readBytes(),Base64.NO_WRAP)}
                c.setCommand("if command -v python3 >/dev/null 2>&1; then exec python3 -u -c \"import base64;exec(compile(base64.b64decode('$probe'),'<gpu-checker>','exec'))\" $interval; else printf 'GPUCHECK:{\\\"error\\\":\\\"Remote Python 3 required\\\"}\\n'; fi")
                val input=BufferedInputStream(c.inputStream);c.setErrStream(object:java.io.OutputStream(){override fun write(b:Int){} });c.connect(12_000)
                val runId=UUID.randomUUID().toString();attempt=0
                while(active.get()){
                    val bytes=ByteArrayOutputStream();var byte=input.read();if(byte<0)error("SSH 采样流已结束")
                    while(byte>=0&&byte!=10){if(bytes.size()>1_048_576)error("采样超出安全大小限制");bytes.write(byte);byte=input.read()}
                    val line=bytes.toString("UTF-8");if(!line.startsWith("GPUCHECK:"))continue
                    val sample=JSONObject(line.substring(9));if(sample.has("error"))error("远端采样失败："+sample.optString("error").take(300))
                    if(!active.get()||workers[id]!==this)break
                    val now=System.currentTimeMillis();sample.put("receivedAt",now);markZero(sample,now)
                    try{history.record(id,sample,runId)}catch(_:Exception){sample.put("history_notice","历史记录暂时写入失败，实时监控继续")}
                    val file=snapshotFile(id);val stream=file.startWrite();try{stream.write(sample.toString().toByteArray());file.finishWrite(stream)}catch(e:Exception){file.failWrite(stream)}
                    lastSample=now;val status=if(sample.optString("gpu_status")=="no_gpu")"在线 · 无 GPU" else if(sample.optString("gpu_status")=="unavailable")"在线 · GPU 不可用" else "在线"
                    update(id,this,status,sample.optString("notice","只读采样正常"),true,sample)
                }
            }catch(e:Exception){
                if(!active.get())break
                val raw=e.message.orEmpty().lowercase();val auth=raw.contains("auth fail")||raw.contains("auth cancel");val trust=raw.contains("hostkey")||raw.contains("host key")||raw.contains("reject")
                val fatal=auth||trust||raw.contains("认证")||raw.contains("invalid privatekey")||raw.contains("python 3")
                val message=when{auth->"认证失败，请重新配置密码或私钥";trust->"主机指纹未信任或已改变；未发送认证，核对后再连接";else->"SSH 连接或采样中断，请检查地址、网络和远端 Python 3"}
                update(id,this,if(fatal)"待认证" else "连接中断",message,false)
                if(fatal||!profile.optBoolean("retry",true)){active.set(false);break}
                val delay=minOf(60,3*(1 shl minOf(4,attempt++)));update(id,this,"重连中","网络中断，${delay} 秒后自动重连",false)
                repeat(delay*2){if(active.get())Thread.sleep(500)}
            }finally{disconnect()}
        };workers.remove(id,this);if(workers.isEmpty())context.stopService(Intent(context,SshService::class.java))}
        private fun markZero(sample:JSONObject,now:Long){
            val previous=runtimes[id]?.optJSONObject("snapshot")?.optJSONArray("gpus");val old=mutableMapOf<String,JSONObject>();if(previous!=null)for(i in 0 until previous.length())old[previous.getJSONObject(i).optString("uuid")]=previous.getJSONObject(i)
            val gs=sample.optJSONArray("gpus")?:return
            for(i in 0 until gs.length()) {val g=gs.getJSONObject(i);val prior=old[g.optString("uuid")];val last=prior?.optDouble("gpu_zero_last",Double.NaN)?:Double.NaN;val start=prior?.optDouble("gpu_zero_since",Double.NaN)?:Double.NaN;val continuous=last.isFinite()&&start.isFinite()&&now/1000.0-last in 0.0..60.0
                val util=if(g.isNull("util"))Double.NaN else g.optDouble("util",Double.NaN)
                if(util==0.0){g.put("gpu_zero_since",if(continuous)start else now/1000.0);g.put("gpu_zero_last",now/1000.0)}else if(util.isNaN()&&continuous){g.put("gpu_zero_since",start);g.put("gpu_zero_last",last)}
            }
        }
    }
}
