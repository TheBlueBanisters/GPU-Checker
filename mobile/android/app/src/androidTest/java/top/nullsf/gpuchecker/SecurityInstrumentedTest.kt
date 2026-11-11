package top.nullsf.gpuchecker

import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith
import org.json.JSONObject
import org.json.JSONArray
import java.util.UUID

@RunWith(AndroidJUnit4::class)
class SecurityInstrumentedTest {
    @Test fun launcherHousingFitsCircularMaskAtEveryDensity(){
        val context=InstrumentationRegistry.getInstrumentation().targetContext
        assertEquals(android.graphics.Color.parseColor("#0C192A"),context.getColor(R.color.gpu_launcher_background))
        for(density in listOf(160,320,480))for(size in listOf(108,216,432)){
            val config=android.content.res.Configuration(context.resources.configuration)
            config.densityDpi=density
            val themed=context.createConfigurationContext(config)
            val drawable=themed.getDrawable(R.drawable.ic_gpu_launcher)!!.mutate()
            val image=android.graphics.Bitmap.createBitmap(size,size,android.graphics.Bitmap.Config.ARGB_8888)
            drawable.setBounds(0,0,size,size);drawable.draw(android.graphics.Canvas(image))
            var opaque=0;var radius=0.0
            for(y in 0 until size)for(x in 0 until size){
                if(android.graphics.Color.alpha(image.getPixel(x,y))>8){
                    opaque++
                    radius=maxOf(radius,Math.hypot(x+.5-size/2.0,y+.5-size/2.0))
                }
            }
            assertTrue("Launcher must render at density $density / size $size",opaque>size*size/10)
            assertTrue("Housing outside 72dp launcher circle: density $density / size $size, radius $radius",radius<=size*36.0/108+.5)
            image.recycle()
        }
        val preview=android.graphics.Bitmap.createBitmap(256,256,android.graphics.Bitmap.Config.ARGB_8888)
        val canvas=android.graphics.Canvas(preview);canvas.drawColor(android.graphics.Color.rgb(65,78,88))
        val icon=context.getDrawable(R.mipmap.ic_launcher)!!
        icon.setBounds(16,16,240,240);icon.draw(canvas)
        java.io.File(context.cacheDir,"launcher-icon-preview.png").outputStream().use{preview.compress(android.graphics.Bitmap.CompressFormat.PNG,100,it)}
        preview.recycle()
    }
    @Test fun sharedKeyLibraryValidatesDeduplicatesAndProtectsHostBindings(){
        val context=InstrumentationRegistry.getInstrumentation().targetContext
        val engine=MonitorEngine.get(context);val keys=engine.keys
        val pair=com.jcraft.jsch.KeyPair.genKeyPair(com.jcraft.jsch.JSch(),com.jcraft.jsch.KeyPair.RSA,2048)
        val output=java.io.ByteArrayOutputStream();pair.writePrivateKey(output,"library-fixture-passphrase".toByteArray());pair.dispose()
        val pem=output.toString("UTF-8");val prefix="libtest-"+UUID.randomUUID().toString();var keyId:String?=null
        fun host(id:String)=JSONObject().put("id",id).put("name",id).put("host","test.invalid").put("port",22).put("user","test").put("mode","key").put("autoconnect",false)
        try {
            val count=keys.list().length()
            try{keys.add("Invalid",pem,"wrong-passphrase");fail("Wrong passphrase must be rejected")}catch(_:IllegalArgumentException){}
            assertEquals(count,keys.list().length())
            val entry=keys.add("Shared RSA",pem,"library-fixture-passphrase");keyId=entry.getString("id")
            assertEquals(keyId,keys.add("Same key",pem,"library-fixture-passphrase").getString("id"))
            assertFalse(entry.toString().contains("PRIVATE KEY"));assertFalse(entry.toString().contains("library-fixture-passphrase"))
            keys.rename(keyId,"Renamed shared key");assertTrue(KeyLibrary(context,engine.vault).list().toString().contains("Renamed shared key"))
            engine.save(host(prefix+"a").put("keyId",keyId),false);engine.save(host(prefix+"b").put("keyId",keyId),false)
            fun exported()=engine.state().getJSONArray("hosts")
            assertEquals(2,(0 until exported().length()).map{exported().getJSONObject(it)}.count{it.optString("keyId")==keyId&&it.optBoolean("credentialReady")})
            assertFalse(engine.state().toString().contains("library-fixture-passphrase"));assertFalse(engine.state().toString().contains("BEGIN RSA PRIVATE KEY"))
            engine.remove(prefix+"a");assertTrue(keys.has(keyId));assertEquals(pem,keys.secret(keyId)!!.getString("key"))
            engine.removeKey(keyId);assertFalse(keys.has(keyId));assertNotNull(engine.host(prefix+"b"));assertFalse(engine.host(prefix+"b")!!.optBoolean("autoconnect"));assertFalse(engine.host(prefix+"b")!!.has("keyId"))
        }finally{engine.remove(prefix+"a");engine.remove(prefix+"b");keyId?.let{keys.remove(it)}}
    }
    @Test fun legacyHostPrivateKeyMigratesWithoutLosingItsProfile(){
        val context=InstrumentationRegistry.getInstrumentation().targetContext;val engine=MonitorEngine.get(context)
        val id="migration-"+UUID.randomUUID().toString();var keyId:String?=null
        val pair=com.jcraft.jsch.KeyPair.genKeyPair(com.jcraft.jsch.JSch(),com.jcraft.jsch.KeyPair.RSA,2048);val output=java.io.ByteArrayOutputStream();pair.writePrivateKey(output);pair.dispose()
        try{
            val h=JSONObject().put("id",id).put("name","Legacy key host").put("host","legacy.invalid").put("port",22).put("user","test").put("mode","key").put("autoconnect",false)
            engine.save(h,false);engine.saveSecret(id,JSONObject().put("key",output.toString("UTF-8")).put("passphrase",""),true)
            engine.migrateLegacyKeys();keyId=engine.host(id)!!.getString("keyId")
            assertTrue(engine.keys.has(keyId));assertFalse(engine.vault.has(id));assertFalse(engine.host(id)!!.optBoolean("autoconnect"))
            assertEquals(output.toString("UTF-8"),engine.keys.secret(keyId)!!.getString("key"))
        }finally{engine.remove(id);keyId?.let{engine.keys.remove(it)}}
    }
    @Test fun ed25519SigningWorksWithoutDesktopJavaProviders(){
        val pair=com.jcraft.jsch.KeyPair.genKeyPair(com.jcraft.jsch.JSch(),com.jcraft.jsch.KeyPair.ED25519)
        try {
            val message="android-native-ssh".toByteArray()
            val signature=pair.getSignature(message)
            val verifier=pair.verifier
            verifier.update(message)
            assertTrue(verifier.verify(signature))
        }finally{pair.dispose()}
    }
    @Test fun bridgeTimestampsAcceptLongIntegerAndFractionalValues(){
        val data=JSONObject().put("long",1800000000000L).put("fraction",1800000000000.75).put("int",32000000)
        assertEquals(1800000000000L,bridgeNumber(data,"long"));assertEquals(1800000000000L,bridgeNumber(data,"fraction"));assertEquals(32000000L,bridgeNumber(data,"int"))
    }
    @Test fun scalarHistoryPrunesOldestAndKeepsWithinBudget(){
        val context=InstrumentationRegistry.getInstrumentation().targetContext
        val name="instrumented-"+UUID.randomUUID().toString();val dbName="$name.db"
        val store=HistoryStore(context,dbName,name)
        try {
            store.setLimit(32_000_000L)
            val gpus=JSONArray();for(i in 0 until 128)gpus.put(JSONObject().put("uuid","GPU-$i").put("index",i*2).put("name","NVIDIA "+"X".repeat(1024)).put("used",512).put("mem_util",20))
            for(i in 0 until 350){store.record("host",JSONObject().put("receivedAt",1_800_000_000_000L+i*2000).put("gpus",gpus),"run");assertTrue(store.bytes()<=32_000_000L)}
            assertEquals(0,store.query("host",null,1_799_999_999_999L,1_800_000_000_001L).getJSONArray("rows").length())
            assertTrue(store.query("host",null,1_800_000_650_000L,1_800_000_700_000L).getJSONArray("rows").length()>0)
            store.clear();assertEquals(0,store.query("host",null,1_799_999_999_999L,1_800_000_700_000L).getJSONArray("rows").length())
        }finally{store.close();context.deleteDatabase(dbName);context.deleteSharedPreferences(name)}
    }
    @Test fun credentialCiphertextRoundTripAndEndpointBinding(){
        val context=InstrumentationRegistry.getInstrumentation().targetContext
        val vault=Vault(context);val id="test-"+UUID.randomUUID().toString()
        try {
            vault.put(id,JSONObject().put("password","instrumentation-only-secret").put("endpoint","first"))
            assertEquals("instrumentation-only-secret",Vault(context).get(id)!!.getString("password"))
            val ciphertext=context.getSharedPreferences("encrypted_credentials",0).getString(id,"")!!
            assertFalse(ciphertext.contains("instrumentation-only-secret"));assertFalse(ciphertext.contains("endpoint"))
            val engine=MonitorEngine.get(context)
            val host=JSONObject().put("id",id).put("name","Instrumented").put("host","test.invalid").put("port",22).put("user","test").put("mode","password").put("autoconnect",false)
            engine.save(host,false);engine.saveSecret(id,JSONObject().put("password","instrumentation-only-secret"),true)
            assertFalse(engine.state().toString().contains("instrumentation-only-secret"))
            assertTrue(engine.state().getJSONArray("hosts").toString().contains("credentialReady"))
            engine.save(host.put("host","other.invalid"),false);assertFalse(vault.has(id))
            engine.remove(id)
        }finally{vault.remove(id)}
    }
}
