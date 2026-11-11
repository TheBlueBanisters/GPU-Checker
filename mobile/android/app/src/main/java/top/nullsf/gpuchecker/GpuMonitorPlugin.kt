package top.nullsf.gpuchecker

import android.app.AlertDialog
import android.content.Intent
import android.os.Build
import android.text.InputType
import android.view.WindowManager
import android.widget.CheckBox
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.TextView
import androidx.activity.result.ActivityResult
import com.getcapacitor.*
import com.getcapacitor.annotation.ActivityCallback
import com.getcapacitor.annotation.CapacitorPlugin
import org.json.JSONObject
import java.util.concurrent.Executors

fun bridgeNumber(data:JSONObject,key:String):Long {
    val number=data.opt(key) as? Number?:error("缺少参数：$key")
    require(number.toDouble().isFinite()&&number.toDouble() in 0.0..9_007_199_254_740_991.0){"数值参数无效"}
    return number.toLong()
}

@CapacitorPlugin(name="GpuMonitor")
class GpuMonitorPlugin:Plugin() {
    private val pool=Executors.newCachedThreadPool()
    private val engine get()=MonitorEngine.get(context)
    override fun load(){engine.activity=activity;engine.changed={notifyListeners("state",JSObject(engine.state().toString()))}}
    override fun handleOnResume(){engine.activity=activity}
    override fun handleOnDestroy(){engine.changed=null;engine.activity=null}
    private fun work(call:PluginCall,block:()->JSONObject){pool.execute {try{call.resolve(JSObject(block().toString()))}catch(e:Exception){call.reject(e.message?.take(200)?:"操作失败，请检查参数和本机存储")}}}
    @PluginMethod fun copyHosts(call:PluginCall){
        val hosts=engine.state().getJSONArray("hosts")
        for(i in 0 until hosts.length())hosts.getJSONObject(i).apply{remove("credentialReady");remove("keyId")}
        val text=JSONObject().put("schema",1).put("hosts",hosts).toString(2)
        activity.runOnUiThread {
            val clipboard=context.getSystemService(android.content.Context.CLIPBOARD_SERVICE) as android.content.ClipboardManager
            clipboard.setPrimaryClip(android.content.ClipData.newPlainText("GPU Checker hosts",text))
            call.resolve(JSObject().put("copied",true))
        }
    }
    @PluginMethod fun getState(call:PluginCall){work(call){engine.boot();engine.state()}}
    @PluginMethod fun saveHost(call:PluginCall){work(call){engine.save(call.getObject("host")?:error("缺少主机配置"))}}
    @PluginMethod fun importHosts(call:PluginCall){work(call){engine.importHosts(call.getArray("hosts")?:error("缺少主机列表"))}}
    @PluginMethod fun removeHost(call:PluginCall){work(call){engine.remove(call.getString("id")?:error("缺少主机 ID"))}}
    @PluginMethod fun pause(call:PluginCall){work(call){engine.pause(call.getString("id")?:error("缺少主机 ID"))}}
    @PluginMethod fun connect(call:PluginCall){
        if(Build.VERSION.SDK_INT>=33&&activity.checkSelfPermission(android.Manifest.permission.POST_NOTIFICATIONS)!=android.content.pm.PackageManager.PERMISSION_GRANTED&&!context.getSharedPreferences("monitor",0).getBoolean("notification_asked",false)){
            context.getSharedPreferences("monitor",0).edit().putBoolean("notification_asked",true).apply()
            activity.runOnUiThread{activity.requestPermissions(arrayOf(android.Manifest.permission.POST_NOTIFICATIONS),442)}
        }
        work(call){engine.connect(call.getString("id")?:error("缺少主机 ID"))}
    }
    @PluginMethod fun historyStats(call:PluginCall){work(call){JSONObject().put("bytes",engine.history.bytes()).put("limit",engine.history.budget())}}
    @PluginMethod fun clearHistory(call:PluginCall){work(call){engine.history.clear();JSONObject().put("cleared",true)}}
    @PluginMethod fun setHistoryLimit(call:PluginCall){work(call){val bytes=bridgeNumber(call.data,"bytes");engine.history.setLimit(bytes);JSONObject().put("limit",engine.history.budget())}}
    @PluginMethod fun history(call:PluginCall){work(call){engine.history.query(call.getString("id")?:error("缺少主机 ID"),call.getString("gpu"),bridgeNumber(call.data,"start"),bridgeNumber(call.data,"end"))}}
    @PluginMethod fun resetTrust(call:PluginCall){
        val id=call.getString("id")?:return call.reject("缺少主机 ID")
        activity.runOnUiThread{AlertDialog.Builder(activity).setTitle("重置主机指纹？").setMessage("只清除手机保存的指纹。下次连接会重新要求核对，不会改变服务器。请先向管理员确认变更。")
            .setPositiveButton("重置"){_,_->engine.resetPin(id);call.resolve(JSObject().put("reset",true))}.setNegativeButton("取消"){_,_->call.reject("已取消")}.setOnCancelListener{call.reject("已取消")}.show()}
    }
    @PluginMethod fun importKey(call:PluginCall){
        startActivityForResult(call,Intent(Intent.ACTION_OPEN_DOCUMENT).addCategory(Intent.CATEGORY_OPENABLE).setType("*/*"),"keyPicked")
    }
    @PluginMethod fun renameKey(call:PluginCall){work(call){engine.keys.rename(call.getString("keyId")?:error("缺少密钥 ID"),call.getString("name")?:error("缺少名称"));engine.announce();engine.state()}}
    @PluginMethod fun removeKey(call:PluginCall){
        val id=call.getString("keyId")?:return call.reject("缺少密钥 ID")
        val hosts=engine.state().getJSONArray("hosts");val affected=(0 until hosts.length()).map{hosts.getJSONObject(it)}.filter{it.optString("keyId")==id}.map{it.optString("name")}
        activity.runOnUiThread{AlertDialog.Builder(activity).setTitle("删除此私钥？").setMessage(if(affected.isEmpty())"只删除手机密钥库中的副本，不改变电脑或服务器。" else "以下主机将暂停并需要重新选择私钥，主机及快照会保留：\n"+affected.joinToString("、"))
            .setPositiveButton("删除"){_,_->work(call){engine.removeKey(id)}}.setNegativeButton("取消"){_,_->call.reject("已取消")}.setOnCancelListener{call.reject("已取消")}.show()}
    }
    @PluginMethod fun configureCredentials(call:PluginCall){
        val id=call.getString("id")?:return call.reject("缺少主机 ID")
        val host=engine.host(id)?:return call.reject("主机不存在")
        if(host.getString("mode")=="key"){
            if(host.optString("keyId").isNotBlank()&&engine.keys.has(host.getString("keyId"))){call.resolve(JSObject().put("saved",true));return}
            importKey(call)
        }else promptSecret(call,id,null)
    }
    @ActivityCallback private fun keyPicked(call:PluginCall?,result:ActivityResult){
        if(call==null)return
        val uri=result.data?.data
        if(result.resultCode!=android.app.Activity.RESULT_OK||uri==null)return call.reject("已取消私钥导入")
        pool.execute {try {
            val bytes=context.contentResolver.openInputStream(uri)?.use {val data=java.io.ByteArrayOutputStream();val chunk=ByteArray(4096);while(data.size()<=65536){val n=it.read(chunk);if(n<0)break;data.write(chunk,0,n)};data.toByteArray()}?:error("无法读取文件")
            try {require(bytes.size<=65536){"私钥文件超过 64 KiB"};val key=String(bytes,Charsets.UTF_8);require(key.contains("PRIVATE KEY-----")){"请选择 PEM 或 OpenSSH 私钥文件"};val filename=try{context.contentResolver.query(uri,arrayOf(android.provider.OpenableColumns.DISPLAY_NAME),null,null,null)?.use{if(it.moveToFirst())it.getString(0)else null}}catch(_:Exception){null}
                promptSecret(call,call.getString("id"),key,(filename?:"SSH 私钥").take(80))}finally{bytes.fill(0)}
        }catch(e:Exception){call.reject(e.message?:"导入失败")}}
    }
    private fun promptSecret(call:PluginCall,id:String?,key:String?,defaultName:String="SSH 私钥"){activity.runOnUiThread{
        val box=LinearLayout(activity).apply {orientation=LinearLayout.VERTICAL;setPadding(48,24,48,8)}
        val tip=TextView(activity).apply {text=if(key==null)"仅在本机原生层使用，不返回网页界面。" else "私钥将保存至本机加密密钥库，可供多台主机选择使用。若已加密，请输入口令。"};box.addView(tip)
        val keyName=if(key!=null)EditText(activity).apply{hint="密钥名称";contentDescription="密钥名称";setText(defaultName);isSingleLine=true;filters=arrayOf(android.text.InputFilter.LengthFilter(80));box.addView(this)}else null
        val secret=EditText(activity).apply {inputType=InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_PASSWORD;isSingleLine=true;transformationMethod=android.text.method.PasswordTransformationMethod.getInstance();isSaveEnabled=false;filters=arrayOf(android.text.InputFilter.LengthFilter(2048));hint=if(key==null)"服务器密码" else "私钥口令（可留空）";contentDescription=if(key==null)"服务器密码" else "私钥口令";setAutofillHints(if(key==null)android.view.View.AUTOFILL_HINT_PASSWORD else "")};box.addView(secret)
        val remember=CheckBox(activity).apply {text="记住认证（Android Keystore 加密）";isChecked=true};if(key==null)box.addView(remember)
        val dialog=AlertDialog.Builder(activity).setTitle(if(key==null)"SSH 服务器密码" else "SSH 私钥认证").setView(box).setPositiveButton("保存",null).setNegativeButton("取消"){_,_->call.reject("已取消认证")}.setOnCancelListener{call.reject("已取消认证")}.create()
        dialog.setOnShowListener {
            dialog.window?.addFlags(WindowManager.LayoutParams.FLAG_SECURE)
            dialog.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener {
                if(key==null&&secret.text.isNullOrEmpty()){secret.error="请输入服务器密码";return@setOnClickListener}
                val password=secret.text.toString();val name=keyName?.text?.toString().orEmpty();val keep=remember.isChecked
                dialog.getButton(AlertDialog.BUTTON_POSITIVE).isEnabled=false
                pool.execute {try {
                    val metadata=if(key!=null)engine.keys.add(name,key,password)else null
                    if(metadata!=null&&id!=null)engine.assignKey(id,metadata.getString("id"))
                    if(key==null)engine.saveSecret(id?:error("主机不存在"),JSONObject().put("password",password),keep)
                    engine.announce()
                    activity.runOnUiThread{secret.text?.clear();dialog.dismiss();val result=JSObject().put("saved",true);if(metadata!=null)result.put("key",metadata);call.resolve(result)}
                }catch(e:Exception){activity.runOnUiThread{dialog.getButton(AlertDialog.BUTTON_POSITIVE).isEnabled=true;secret.error=if(key!=null)e.message?.take(100)?:"私钥保存失败" else "无法保存，请检查设备密钥库或取消记住后重试"}}}

            }
        };dialog.setOnDismissListener{secret.text?.clear()};dialog.show();secret.requestFocus()
    }}
}
