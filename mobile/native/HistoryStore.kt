package top.nullsf.gpuchecker

import android.content.ContentValues
import android.content.Context
import android.database.sqlite.SQLiteDatabase
import android.database.sqlite.SQLiteOpenHelper
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import kotlin.math.max

/** Local scalar-only store; bounded disk usage, never stores credentials or process paths. */
class HistoryStore(private val context:Context,private val databaseName:String="gpu_history.db",settingsName:String="monitor"):SQLiteOpenHelper(context,databaseName,null,1) {
    private val prefs=context.getSharedPreferences(settingsName,Context.MODE_PRIVATE)
    override fun onConfigure(db:SQLiteDatabase) { db.rawQuery("PRAGMA journal_mode=DELETE",null).use {it.moveToFirst()};db.execSQL("PRAGMA auto_vacuum=INCREMENTAL") }
    override fun onCreate(db:SQLiteDatabase) {
        db.execSQL("CREATE TABLE samples(host TEXT NOT NULL,gpu TEXT NOT NULL,ts INTEGER NOT NULL,used REAL,mem REAL,name TEXT,idx INTEGER,session TEXT,PRIMARY KEY(host,gpu,ts))")
        db.execSQL("CREATE INDEX by_host_time ON samples(host,ts)")
    }
    override fun onUpgrade(db:SQLiteDatabase,oldVersion:Int,newVersion:Int) {}
    fun budget():Long=prefs.getLong("history_limit",256_000_000L).coerceIn(32_000_000L,1_000_000_000L)
    fun bytes():Long { val f=context.getDatabasePath(databaseName);return listOf(f,File(f.path+"-journal"),File(f.path+"-wal"),File(f.path+"-shm")).sumOf { if(it.isFile)it.length() else 0L } }
    @Synchronized fun setLimit(value:Long) { require(value in 32_000_000L..1_000_000_000L);prefs.edit().putLong("history_limit",value).commit();trim(true) }
    @Synchronized fun clear() { writableDatabase.execSQL("DELETE FROM samples");writableDatabase.execSQL("VACUUM") }
    private fun scalar(objectValue:JSONObject,key:String):Double? {
        if(objectValue.isNull(key))return null
        val value=objectValue.optDouble(key,Double.NaN)
        return value.takeIf { it.isFinite()&&it>=0 }
    }
    @Synchronized fun record(host:String,sample:JSONObject,session:String) {
        val db=writableDatabase;db.rawQuery("PRAGMA max_page_count=${max(1024L,(budget()-8_000_000L)/4096)}",null).use {it.moveToFirst()}
        trim(false)
        val gs=sample.optJSONArray("gpus")?:return
        db.beginTransaction()
        try {
            for(i in 0 until gs.length()) {
                val g=gs.getJSONObject(i);val uuid=g.optString("uuid");if(uuid.isEmpty())continue
                val v=ContentValues().apply {
                    put("host",host);put("gpu",uuid);put("ts",sample.getLong("receivedAt"));put("name",g.optString("name"));put("session",session)
                    if(!g.isNull("index"))put("idx",g.optInt("index"))
                    scalar(g,"used")?.let { put("used",it/1024) }
                    scalar(g,"mem_util")?.takeIf { it<=100 }?.let { put("mem",it) }
                }
                db.insertWithOnConflict("samples",null,v,SQLiteDatabase.CONFLICT_REPLACE)
            };db.setTransactionSuccessful()
        } finally { db.endTransaction() }
        trim(false)
    }
    private fun trim(force:Boolean) {
        val db=writableDatabase;val capacity=budget()-8_000_000L;val target=(capacity*.8).toLong()
        if(bytes()<capacity-1_000_000&&!force)return
        var loops=0
        while(bytes()>target&&loops++<500) {
            val changed=db.compileStatement("DELETE FROM samples WHERE rowid IN (SELECT rowid FROM samples ORDER BY ts LIMIT 5000)").executeUpdateDelete()
            db.rawQuery("PRAGMA incremental_vacuum(2048)",null).use {while(it.moveToNext()){} }
            if(changed==0){db.execSQL("VACUUM");break}
        }
    }
    @Synchronized fun query(host:String,gpu:String?,start:Long,end:Long):JSONObject {
        require(end>start);val db=readableDatabase;val args=mutableListOf(host,start.toString(),end.toString())
        val where="host=? AND ts>=? AND ts<=?"+(if(gpu!=null)" AND gpu=?" else "");if(gpu!=null)args.add(gpu)
        val rows=JSONArray();val devices=JSONArray();val bucket=max(1L,(end-start)/1200)
        // Aggregate by successful host sample first; partial metric reports remain null.
        val inner="SELECT ts,session,CASE WHEN COUNT(used)=COUNT(*) THEN SUM(used) END AS used,CASE WHEN COUNT(mem)=COUNT(*) THEN AVG(mem) END AS mem FROM samples WHERE $where GROUP BY ts,session"
        val sql="SELECT AVG(ts),AVG(used),AVG(mem),session FROM ($inner) GROUP BY CAST((ts-$start)/$bucket AS INTEGER),session ORDER BY AVG(ts) LIMIT 2400"
        db.rawQuery(sql,args.toTypedArray()).use { cursor->
            var previousSession:String?=null;var last=0L
            while(cursor.moveToNext()) {
                val stamp=cursor.getDouble(0).toLong();val session=cursor.getString(3)
                if(previousSession!=null&&(session!=previousSession||stamp-last>max(60_000,bucket*3)))rows.put(JSONObject().put("t",stamp-1).put("used",JSONObject.NULL).put("mem",JSONObject.NULL))
                rows.put(JSONObject().put("t",stamp).put("used",if(cursor.isNull(1))JSONObject.NULL else cursor.getDouble(1)).put("mem",if(cursor.isNull(2))JSONObject.NULL else cursor.getDouble(2)))
                previousSession=session;last=stamp
            }
        }
        db.rawQuery("SELECT gpu,MAX(name),MAX(idx) FROM samples WHERE host=? GROUP BY gpu ORDER BY MAX(idx)",arrayOf(host)).use { cursor->while(cursor.moveToNext())devices.put(JSONObject().put("uuid",cursor.getString(0)).put("name",cursor.getString(1)).put("index",if(cursor.isNull(2))JSONObject.NULL else cursor.getInt(2))) }
        return JSONObject().put("rows",rows).put("devices",devices)
    }
}
