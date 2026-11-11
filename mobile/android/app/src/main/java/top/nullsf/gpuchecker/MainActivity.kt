package top.nullsf.gpuchecker

import android.os.Bundle
import androidx.activity.OnBackPressedCallback
import com.getcapacitor.BridgeActivity

class MainActivity:BridgeActivity(){
    override fun onConfigurationChanged(newConfig:android.content.res.Configuration){super.onConfigurationChanged(newConfig);MonitorEngine.get(this).announce()}
    override fun onCreate(savedInstanceState:Bundle?){
        registerPlugin(GpuMonitorPlugin::class.java);super.onCreate(savedInstanceState);requestedOrientation=android.content.pm.ActivityInfo.SCREEN_ORIENTATION_PORTRAIT
        onBackPressedDispatcher.addCallback(this,object:OnBackPressedCallback(true){override fun handleOnBackPressed(){bridge.webView.evaluateJavascript("window.gpuHandleBack ? window.gpuHandleBack() : false"){handled->if(handled!="true")moveTaskToBack(true)}}})
    }
}
