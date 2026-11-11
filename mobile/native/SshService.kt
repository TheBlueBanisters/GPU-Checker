package top.nullsf.gpuchecker

import android.app.*
import android.content.Intent
import android.content.pm.ServiceInfo
import android.os.Build
import android.os.IBinder

class SshService:Service(){
    override fun onBind(intent:Intent?):IBinder?=null
    override fun onStartCommand(intent:Intent?,flags:Int,startId:Int):Int {
        val manager=getSystemService(NotificationManager::class.java)
        manager.createNotificationChannel(NotificationChannel("gpu_monitor","GPU SSH 监控",NotificationManager.IMPORTANCE_LOW))
        val open=PendingIntent.getActivity(this,0,Intent(this,MainActivity::class.java),PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)
        val notification=Notification.Builder(this,"gpu_monitor").setSmallIcon(R.drawable.ic_stat_chip).setContentTitle("GPU Checker 正在监控")
            .setContentText("手机通过 SSH 直接采集，点击返回监控界面").setContentIntent(open).setOngoing(true).build()
        if(Build.VERSION.SDK_INT>=29)startForeground(2201,notification,ServiceInfo.FOREGROUND_SERVICE_TYPE_DATA_SYNC)else startForeground(2201,notification)
        return START_NOT_STICKY
    }
    override fun onTimeout(startId:Int,fgsType:Int){MonitorEngine.get(this).timeout();stopSelf()}
}
