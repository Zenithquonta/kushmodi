// Focused checks for telescope click selection and a target that has set.
import fs from 'node:fs';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url);
const {chromium}=require(process.env.PLAYWRIGHT_PATH||'playwright');
const base=process.argv[2]||'http://127.0.0.1:8099',out=process.argv[3]||'.';
fs.mkdirSync(out,{recursive:true});
const browser=await chromium.launch({args:['--use-angle=swiftshader','--use-gl=angle','--enable-unsafe-swiftshader','--ignore-gpu-blocklist','--no-sandbox']});
const page=await browser.newPage({viewport:{width:1280,height:720}});
const errors=[];
page.on('pageerror',e=>errors.push(e.message));
async function near(iso){
  await page.goto(`${base}/?time=${encodeURIComponent(iso)}`);
  await page.waitForFunction(()=>window.__obs?.ready,null,{timeout:60000});
  await page.evaluate(()=>{window.__obs.setPosition(-3,4);window.__obs.setView(5.7,-3.4);});
  await page.waitForTimeout(600);
}
function check(value,message){if(!value)throw new Error(message);}
if (!process.argv.includes('--planet-only')) {
await near('2026-10-04T23:30:00+05:30');
await page.locator('#view').click({position:{x:640,y:360}});
check(await page.locator('#readout').isVisible(),'clicking nearby telescope must open eyepiece');
check(await page.evaluate(()=>!document.pointerLockElement),'eyepiece must not acquire pointer lock');
await page.keyboard.press('Escape');
check(await page.locator('#readout').isHidden(),'Escape must close clicked telescope');
await near('2026-10-05T03:30:00+05:30');
await page.locator('#btn-telescope').click();
const status=await page.locator('#eyepiece-status').textContent();
check(status.includes('Below the horizon'),'set target must explain horizon status');
const lit=await page.evaluate(()=>{
  const p=document.getElementById('eyepiece-canvas').getContext('2d').getImageData(0,0,192,192).data;
  let n=0;for(let i=0;i<p.length;i+=4)if(p[i]+p[i+1]+p[i+2]>100)n++;return n;
});
check(lit===0,'set target must not show a false visible illustration');
await page.screenshot({path:`${out}/site-below-horizon.png`});
}
await near('2026-10-05T23:30:00+05:30');
await page.locator('#btn-telescope').click();
check((await page.locator('#eyepiece-title').textContent())==='Saturn','Oct5 nightly selection must choose Saturn');
await page.screenshot({path:`${out}/site-saturn-eyepiece.png`});
await browser.close();
check(!errors.length,errors.join('\n'));
console.log('PASS: telescope interaction checks and real Oct5 Saturn eyepiece selection');
