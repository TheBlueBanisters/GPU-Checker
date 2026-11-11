package top.nullsf.gpuchecker

import android.content.Context
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import android.util.Base64
import org.json.JSONObject
import java.security.KeyStore
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec

/** Secrets never cross the Capacitor bridge. No software key is stored alongside ciphertext. */
class Vault(context:Context) {
    private val prefs=context.getSharedPreferences("encrypted_credentials",Context.MODE_PRIVATE)
    private val alias="gpu-checker-credentials-v1"
    private fun key():SecretKey {
        val store=KeyStore.getInstance("AndroidKeyStore").apply { load(null) }
        (store.getKey(alias,null) as? SecretKey)?.let { return it }
        return KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES,"AndroidKeyStore").apply {
            init(KeyGenParameterSpec.Builder(alias,KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT)
                .setBlockModes(KeyProperties.BLOCK_MODE_GCM).setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
                .setRandomizedEncryptionRequired(true).setKeySize(256).build())
        }.generateKey()
    }
    @Synchronized fun put(id:String,value:JSONObject) {
        val bytes=value.toString().toByteArray(Charsets.UTF_8)
        try {
            val cipher=Cipher.getInstance("AES/GCM/NoPadding");cipher.init(Cipher.ENCRYPT_MODE,key())
            val encrypted=cipher.iv+cipher.doFinal(bytes)
            check(prefs.edit().putString(id,Base64.encodeToString(encrypted,Base64.NO_WRAP)).commit())
        } finally { bytes.fill(0) }
    }
    @Synchronized fun get(id:String):JSONObject? {
        val encoded=prefs.getString(id,null)?:return null
        val bytes=Base64.decode(encoded,Base64.NO_WRAP)
        val cipher=Cipher.getInstance("AES/GCM/NoPadding")
        cipher.init(Cipher.DECRYPT_MODE,key(),GCMParameterSpec(128,bytes.copyOfRange(0,12)))
        val plain=cipher.doFinal(bytes.copyOfRange(12,bytes.size))
        return try { JSONObject(String(plain,Charsets.UTF_8)) } finally { plain.fill(0);bytes.fill(0) }
    }
    fun has(id:String):Boolean=prefs.contains(id)
    fun remove(id:String) { prefs.edit().remove(id).apply() }
}
