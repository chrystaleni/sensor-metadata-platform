import {defineConfig} from '@playwright/test';
export default defineConfig({
 testDir:'.',testMatch:'*.spec.js',fullyParallel:false,workers:1,retries:0,
 timeout:60000,outputDir:process.env.E2E_RESULTS_DIR||'/tmp/sensor-playwright-artifacts',
 reporter:[['list'],['junit',{outputFile:process.env.E2E_JUNIT||'/tmp/sensor-playwright-results.xml'}]],
 use:{baseURL:process.env.E2E_BASE_URL||'http://127.0.0.1:5173',headless:true,screenshot:'only-on-failure',trace:'retain-on-failure'},
});
