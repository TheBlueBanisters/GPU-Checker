import type {CapacitorConfig} from '@capacitor/cli';
const config:CapacitorConfig={appId:'top.nullsf.gpuchecker',appName:'GPU Checker',webDir:'dist',loggingBehavior:'none',android:{allowMixedContent:false,minWebViewVersion:80},server:{androidScheme:'https'},plugins:{SystemBars:{insetsHandling:'native',style:'DARK'}}};
export default config;
