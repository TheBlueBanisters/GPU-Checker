import {defineConfig} from '@playwright/test';
export default defineConfig({testDir:'tests/browser',use:{baseURL:'http://127.0.0.1:5173',channel:'msedge',headless:true,viewport:{width:390,height:844}},reporter:'list',workers:1});
