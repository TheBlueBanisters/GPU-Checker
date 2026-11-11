package top.nullsf.gpuchecker

import android.content.Context
import android.util.Base64
import com.jcraft.jsch.JSch
import org.json.JSONArray
import org.json.JSONObject
import java.security.MessageDigest
import java.util.UUID

/** Only public metadata leaves this class. Key material and passphrases stay in Vault. */
class KeyLibrary(context:Context,private val vault:Vault) {
    private val prefs=context.getSharedPreferences("ssh_key_library",Context.MODE_PRIVATE)
    private fun entries():JSONArray=JSONArray(prefs.getString("entries","[]"))
    private fun valid(id:String)=id.matches(Regex("key-[a-f0-9-]{36}"))
    @Synchronized fun list():JSONArray=entries()
    @Synchronized fun has(id:String):Boolean {
        if(!valid(id)||!vault.has("library-$id"))return false
        val items=entries();return (0 until items.length()).any{items.getJSONObject(it).optString("id")==id}
    }
    @Synchronized fun secret(id:String):JSONObject?=if(has(id))vault.get("library-$id")else null
    @Synchronized fun add(name:String,key:String,passphrase:String):JSONObject {
        require(name.trim().isNotEmpty()&&name.length<=80&&!name.contains('\u0000')){"密钥名称需为 1–80 字符"}
        require(key.toByteArray(Charsets.UTF_8).size<=65536){"私钥文件超过 64 KiB"}
        val jsch=JSch();val bytes=key.toByteArray(Charsets.UTF_8);val pass=passphrase.toByteArray(Charsets.UTF_8)
        val algorithm:String;val fingerprint:String
        try {
            jsch.addIdentity("import",bytes,null,pass)
            val identity=jsch.identityRepository.identities.firstOrNull()?:error("无效私钥")
            require(!identity.isEncrypted){"无法解密"}
            val blob=identity.publicKeyBlob?:error("缺少公钥")
            algorithm=identity.algName
            fingerprint="SHA256:"+Base64.encodeToString(MessageDigest.getInstance("SHA-256").digest(blob),Base64.NO_WRAP or Base64.NO_PADDING)
        }catch(_:Exception){throw IllegalArgumentException("私钥口令不正确或私钥格式不支持，请重新选择并检查口令")}
        finally{bytes.fill(0);pass.fill(0);jsch.removeAllIdentity()}
        val entries=entries()
        for(i in 0 until entries.length())if(entries.getJSONObject(i).optString("fingerprint")==fingerprint){
            val existing=entries.getJSONObject(i)
            // Re-import also repairs a damaged encrypted copy without duplicating bindings.
            vault.put("library-${existing.getString("id")}",JSONObject().put("key",key).put("passphrase",passphrase))
            return JSONObject(existing.toString())
        }
        require(entries.length()<100){"私钥库最多保存 100 把密钥"}
        val id="key-"+UUID.randomUUID().toString()
        val metadata=JSONObject().put("id",id).put("name",name.trim()).put("algorithm",algorithm).put("fingerprint",fingerprint).put("createdAt",System.currentTimeMillis())
        vault.put("library-$id",JSONObject().put("key",key).put("passphrase",passphrase))
        entries.put(metadata);check(prefs.edit().putString("entries",entries.toString()).commit())
        return JSONObject(metadata.toString())
    }
    @Synchronized fun rename(id:String,name:String){
        require(has(id)){"私钥不存在"};require(name.trim().isNotEmpty()&&name.length<=80&&!name.contains('\u0000')){"密钥名称需为 1–80 字符"}
        val entries=entries();for(i in 0 until entries.length())if(entries.getJSONObject(i).getString("id")==id)entries.getJSONObject(i).put("name",name.trim())
        check(prefs.edit().putString("entries",entries.toString()).commit())
    }
    @Synchronized fun remove(id:String){
        require(valid(id)){"密钥 ID 无效"};val old=entries();val next=JSONArray()
        for(i in 0 until old.length())if(old.getJSONObject(i).getString("id")!=id)next.put(old.getJSONObject(i))
        check(prefs.edit().putString("entries",next.toString()).commit());vault.remove("library-$id")
    }
}
