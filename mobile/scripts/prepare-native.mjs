import {readFile,writeFile,mkdir,copyFile,rm} from 'node:fs/promises';
import {resolve,join} from 'node:path';
import {fileURLToPath} from 'node:url';
const root=resolve(fileURLToPath(new URL('..',import.meta.url)));
const android=join(root,'android'),main=join(android,'app/src/main'),pkg=join(main,'java/top/nullsf/gpuchecker');
await mkdir(pkg,{recursive:true});await mkdir(join(main,'assets'),{recursive:true});
for(const name of ['Vault','KeyLibrary','HistoryStore','MonitorEngine','GpuMonitorPlugin','MainActivity','SshService'])await copyFile(join(root,'native',name+'.kt'),join(pkg,name+'.kt'));
await rm(join(pkg,'MainActivity.java'),{force:true});
await copyFile(join(root,'../src/remote_probe.py'),join(main,'assets/remote_probe.py'));
await writeFile(join(android,'build.gradle'),`buildscript { repositories { google(); mavenCentral() }; dependencies { classpath 'com.android.tools.build:gradle:8.13.0'; classpath 'org.jetbrains.kotlin:kotlin-gradle-plugin:2.1.21' } }
apply from: 'variables.gradle'
allprojects { repositories { google(); mavenCentral() } }
subprojects { sub -> sub.plugins.withId('com.android.library') { sub.android.buildToolsVersion = '36.0.0' } }
tasks.register('clean', Delete) { delete rootProject.layout.buildDirectory }
`);
await writeFile(join(android,'app/build.gradle'),`apply plugin: 'com.android.application'
apply plugin: 'org.jetbrains.kotlin.android'
android {
 namespace 'top.nullsf.gpuchecker'
 compileSdk rootProject.ext.compileSdkVersion
 buildToolsVersion '36.0.0'
 defaultConfig { applicationId 'top.nullsf.gpuchecker'; minSdk 26; targetSdk rootProject.ext.targetSdkVersion; versionCode 15; versionName '1.0.14'; testInstrumentationRunner 'androidx.test.runner.AndroidJUnitRunner' }
 compileOptions { sourceCompatibility JavaVersion.VERSION_21; targetCompatibility JavaVersion.VERSION_21 }
 kotlinOptions { jvmTarget = '21' }
 buildTypes { release { minifyEnabled false; signingConfig signingConfigs.debug } }
 packaging { resources { excludes += ['META-INF/versions/**', 'META-INF/DEPENDENCIES'] } }
}
repositories { flatDir { dirs '../capacitor-cordova-android-plugins/src/main/libs', 'libs' } }
dependencies {
 implementation project(':capacitor-android')
 implementation project(':capacitor-cordova-android-plugins')
 implementation platform('org.jetbrains.kotlin:kotlin-bom:2.1.21')
 androidTestImplementation platform('org.jetbrains.kotlin:kotlin-bom:2.1.21')
 implementation 'com.github.mwiede:jsch:2.28.0'
 implementation 'org.bouncycastle:bcprov-jdk18on:1.83'
 implementation "androidx.appcompat:appcompat:$androidxAppCompatVersion"
 implementation "androidx.coordinatorlayout:coordinatorlayout:$androidxCoordinatorLayoutVersion"
 implementation "androidx.core:core-splashscreen:$coreSplashScreenVersion"
 testImplementation 'junit:junit:4.13.2'
 androidTestImplementation 'androidx.test.ext:junit:1.3.0'
 androidTestImplementation 'androidx.test:runner:1.7.0'
 androidTestImplementation 'androidx.test.espresso:espresso-core:3.7.0'
}
apply from: 'capacitor.build.gradle'
`);
await writeFile(join(main,'AndroidManifest.xml'),`<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns:android="http://schemas.android.com/apk/res/android">
 <uses-permission android:name="android.permission.INTERNET"/>
 <uses-permission android:name="android.permission.ACCESS_NETWORK_STATE"/>
 <uses-permission android:name="android.permission.FOREGROUND_SERVICE"/>
 <uses-permission android:name="android.permission.FOREGROUND_SERVICE_DATA_SYNC"/>
 <uses-permission android:name="android.permission.POST_NOTIFICATIONS"/>
 <uses-permission android:name="android.permission.VIBRATE"/>
 <application android:allowBackup="false" android:fullBackupContent="false" android:usesCleartextTraffic="false" android:icon="@mipmap/ic_launcher" android:roundIcon="@mipmap/ic_launcher_round" android:label="@string/app_name" android:supportsRtl="true" android:theme="@style/AppTheme">
  <activity android:name=".MainActivity" android:exported="true" android:launchMode="singleTask" android:screenOrientation="portrait" android:configChanges="orientation|keyboardHidden|keyboard|screenSize|locale|smallestScreenSize|screenLayout|uiMode|navigation|density" android:theme="@style/AppTheme.NoActionBarLaunch" android:windowSoftInputMode="adjustResize">
   <property android:name="android.window.PROPERTY_COMPAT_ALLOW_RESTRICTED_RESIZABILITY" android:value="true"/>
   <intent-filter><action android:name="android.intent.action.MAIN"/><category android:name="android.intent.category.LAUNCHER"/></intent-filter>
  </activity>
  <service android:name=".SshService" android:exported="false" android:foregroundServiceType="dataSync"/>
 </application>
</manifest>`);
const drawable=join(main,'res/drawable');await mkdir(drawable,{recursive:true});
const chip=`<vector xmlns:android="http://schemas.android.com/apk/res/android" android:width="24dp" android:height="24dp" android:viewportWidth="24" android:viewportHeight="24"><path android:strokeColor="#FFFFFFFF" android:strokeWidth="1.5" android:fillColor="#00000000" android:pathData="M6,5L18,5L18,19L6,19ZM9,9L15,9L15,15L9,15ZM9,2L9,5M15,2L15,5M9,19L9,22M15,19L15,22M3,9L6,9M3,15L6,15M18,9L21,9M18,15L21,15"/></vector>`;
await writeFile(join(drawable,'ic_stat_chip.xml'),chip);
await writeFile(join(drawable,'ic_launcher_foreground.xml'),chip.replace('24dp','108dp').replace('24dp','108dp'));
// Keep the launcher consistent with the in-app GPU chip; API 26+ adaptive icon.
await copyFile(join(root,'public/branding/gpu-checker-b2.png'),join(drawable,'gpu_launcher_art.png'));
// Fractional padding keeps the full metal housing inside the circular launcher mask at every density.
await writeFile(join(drawable,'ic_gpu_launcher.xml'),`<inset xmlns:android="http://schemas.android.com/apk/res/android" android:insetLeft="20.5%" android:insetTop="20.5%" android:insetRight="20.5%" android:insetBottom="20.5%"><bitmap android:src="@drawable/gpu_launcher_art" android:gravity="fill" android:filter="true"/></inset>`);
const adaptive=join(main,'res/mipmap-anydpi-v26');await mkdir(adaptive,{recursive:true});
await writeFile(join(main,'res/values/gpu_colors.xml'),'<resources><color name="gpu_launcher_background">#0C192A</color></resources>');
for(const name of ['ic_launcher.xml','ic_launcher_round.xml'])await writeFile(join(adaptive,name),`<adaptive-icon xmlns:android="http://schemas.android.com/apk/res/android"><background android:drawable="@color/gpu_launcher_background"/><foreground android:drawable="@drawable/ic_gpu_launcher"/></adaptive-icon>`);
await rm(join(android,'app/src/androidTest/java/com/getcapacitor/myapp/ExampleInstrumentedTest.java'),{force:true});
await rm(join(android,'app/src/test/java/com/getcapacitor/myapp/ExampleUnitTest.java'),{force:true});
let wrapper=await readFile(join(android,'gradle/wrapper/gradle-wrapper.properties'),'utf8');wrapper=wrapper.replace('gradle-8.14.3-all.zip','gradle-8.14.3-bin.zip').replace('networkTimeout=10000','networkTimeout=120000');await writeFile(join(android,'gradle/wrapper/gradle-wrapper.properties'),wrapper);
console.log('Kotlin plugins and identical read-only desktop probe prepared.');

const tests=join(android,'app/src/androidTest/java/top/nullsf/gpuchecker');await mkdir(tests,{recursive:true});await copyFile(join(root,'native-test/SecurityInstrumentedTest.kt'),join(tests,'SecurityInstrumentedTest.kt'));
await writeFile(join(main,'res/values/styles.xml'),`<resources>
<style name="AppTheme" parent="Theme.AppCompat.NoActionBar"><item name="colorPrimary">#0e1d2e</item><item name="colorPrimaryDark">#080f1e</item><item name="colorAccent">#63dec1</item><item name="android:windowBackground">#080f1e</item><item name="android:statusBarColor">#080f1e</item><item name="android:navigationBarColor">#080f1e</item><item name="android:windowLightStatusBar">false</item><item name="android:windowLightNavigationBar">false</item></style>
<style name="AppTheme.NoActionBar" parent="AppTheme"><item name="windowActionBar">false</item><item name="windowNoTitle">true</item></style>
<style name="AppTheme.NoActionBarLaunch" parent="Theme.SplashScreen"><item name="windowSplashScreenBackground">#080f1e</item><item name="windowSplashScreenAnimatedIcon">@mipmap/ic_launcher</item><item name="postSplashScreenTheme">@style/AppTheme.NoActionBar</item></style>
</resources>`);
