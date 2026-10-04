// Real-browser check of the Living Observatory website (Chromium through Playwright, software GL).
//   NODE_PATH=/opt/node-tools/node_modules node scripts/site_browser_check.mjs http://127.0.0.1:8099 OUT_DIR
// Serve the site through Caddy with the repository's template so the Content-Security-Policy is really in force
// (see docs/WEBSITE.md). Fails on any console error, page error, failed request or HTTP error status.
import { createRequire } from 'node:module';
import fs from 'node:fs';
const require = createRequire(import.meta.url);
const { chromium } = require(process.env.PLAYWRIGHT_PATH || 'playwright');

const base = process.argv[2] || 'http://127.0.0.1:8099';
const out = process.argv[3] || '.';
fs.mkdirSync(out, { recursive: true });
const NIGHT = '2026-10-04T23:30:00%2B05:30', SATURN = '2026-10-05T00:30:00%2B05:30', DAY = '2026-10-04T12:00:00%2B05:30';
const problems = [];
const report = {};
function check(value, description) { if (!value) problems.push(`assertion: ${description}`); }

const browser = await chromium.launch({
  args: ['--use-angle=swiftshader', '--use-gl=angle', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist', '--no-sandbox'],
});

async function open(name, options, query, { init, waitReady = true } = {}) {
  const context = await browser.newContext(options);
  if (init) await context.addInitScript(init);
  const page = await context.newPage();
  page.on('console', (m) => { if (m.type() === 'error' || m.type() === 'warning') problems.push(`${name}: console ${m.type()}: ${m.text()}`); });
  page.on('pageerror', (e) => problems.push(`${name}: pageerror: ${e.message}`));
  page.on('requestfailed', (r) => problems.push(`${name}: request failed: ${r.url()} ${r.failure()?.errorText}`));
  page.on('response', (r) => { if (r.status() >= 400) problems.push(`${name}: HTTP ${r.status()} ${r.url()}`); });
  await page.goto(`${base}/${query}`, { waitUntil: 'load' });
  if (waitReady) {
    await page.waitForFunction(() => window.__obs && window.__obs.ready, null, { timeout: 60000 });
    await page.waitForTimeout(2500);
  }
  return { context, page };
}

const desktop = { viewport: { width: 1280, height: 720 }, deviceScaleFactor: 1 };

// 1. night, facing north (the default): Polaris near 19 degrees, the telescope, the skyline
{
  const { context, page } = await open('night', desktop, `?time=${NIGHT}`);
  report.night = await page.evaluate(() => ({
    polaris: window.__obs.star('Polaris'), saturn: window.__obs.body('Saturn'), moon: window.__obs.body('Moon'),
    target: window.__obs.target, heading: window.__obs.heading, pixelRatio: window.__obs.pixelRatio, renderSize: window.__obs.renderSize,
    calls: window.__obs.calls, triangles: window.__obs.triangles, limit: window.__obs.limitingMagnitude, fps: window.__obs.fps,
    hudTime: document.getElementById('hud-time').textContent, sky: [...document.querySelectorAll('#hud-sky li')].map((l) => l.textContent),
    weather: document.getElementById('hud-weather').textContent,
  }));
  await page.screenshot({ path: `${out}/site-night.png` });
  await page.keyboard.press('KeyE');
  check(await page.locator('#readout').isHidden(), 'telescope requires proximity');
  // click the telescope: the readout appears with RA/Dec/alt/az
  await page.evaluate(() => window.__obs.setPosition(-3, 4));
  await page.evaluate(() => window.__obs.setView(-58, 8));
  await page.waitForTimeout(500);
  await page.keyboard.press('KeyE');
  await page.waitForTimeout(400);
  report.readout = await page.evaluate(() => document.getElementById('readout').hidden ? null : document.getElementById('readout-body').textContent);
  check(!!report.readout, 'E opens nearby telescope');
  report.eyepiece = await page.evaluate(() => {
    const pixels=document.getElementById('eyepiece-canvas').getContext('2d').getImageData(0,0,192,192).data;
    let lit=0;for(let i=0;i<pixels.length;i+=4)if(pixels[i]+pixels[i+1]+pixels[i+2]>100)lit++;
    return {lit,status:document.getElementById('eyepiece-status').textContent,inert:document.getElementById('view').inert};
  });
  check(report.eyepiece.lit > 100, 'visible nightly object has a pixel-art eyepiece');
  check(report.eyepiece.inert, 'modal makes background inert');
  await page.keyboard.press('Tab');
  check(await page.evaluate(()=>document.activeElement.id==='btn-close-eyepiece'), 'modal traps keyboard focus');
  const paused=await page.evaluate(()=>window.__obs.position);
  await page.keyboard.down('KeyW'); await page.waitForTimeout(250); await page.keyboard.up('KeyW');
  check(await page.evaluate(p=>Math.hypot(window.__obs.position.x-p.x,window.__obs.position.z-p.z)<.01,paused), 'walking pauses in eyepiece');
  await page.screenshot({ path: `${out}/site-telescope.png` });
  await page.keyboard.press('KeyE');
  check(await page.locator('#readout').isHidden(), 'E closes eyepiece');
  await page.locator('#btn-telescope').click();
  await page.keyboard.press('Escape');
  check(await page.locator('#readout').isHidden(), 'Escape returns to world');
  await page.keyboard.down('KeyW'); await page.waitForTimeout(250); await page.keyboard.up('KeyW');
  check(await page.evaluate(p=>Math.hypot(window.__obs.position.x-p.x,window.__obs.position.z-p.z)>.05,paused), 'walking resumes after modal');
  await page.locator('#btn-telescope').click();
  await page.locator('#btn-close-eyepiece').click();
  check(await page.locator('#readout').isHidden(), 'close button returns to world');
  await context.close();
}
// 2. Saturn near 00:30 IST on 5 October: due south, high up
{
  const { context, page } = await open('saturn', desktop, `?time=${SATURN}&heading=180&pitch=55`);
  report.saturn = await page.evaluate(() => ({ saturn: window.__obs.body('Saturn'), target: window.__obs.target }));
  report.guides = await page.evaluate(()=>[...document.querySelectorAll('.planet-guide')].filter(n=>!n.hidden).map(n=>({name:n.querySelector('.planet-tag').textContent,x:parseFloat(n.style.left),y:parseFloat(n.style.top)})));
  const saturnGuide=report.guides.find(g=>g.name==='Saturn');
  check(saturnGuide && Math.hypot(saturnGuide.x-report.saturn.saturn.screen.x,saturnGuide.y-report.saturn.saturn.screen.y)<2,'planet ring follows real body projection');
  await page.screenshot({ path: `${out}/site-saturn.png` });
  await page.locator('#btn-guides').click();
  check(await page.locator('#planet-guides').isHidden(),'guide toggle hides rings');
  await page.locator('#btn-guides').click();
  await page.evaluate(()=>window.__obs.setView(0,9));await page.waitForTimeout(500);
  check(await page.evaluate(()=>[...document.querySelectorAll('.planet-guide')].every(n=>n.hidden)),'offscreen planets have no rings');
  await context.close();
}
// 2b. night looking south-east: Saturn and its three-hour trail
{
  const { context, page } = await open('east', desktop, `?time=${NIGHT}&heading=140&pitch=50`);
  report.east = await page.evaluate(() => ({ uranus: window.__obs.body('Uranus'), saturn: window.__obs.body('Saturn') }));
  await page.screenshot({ path: `${out}/site-night-trail.png` });
  await context.close();
}
// 3. day
{
  const { context, page } = await open('day', desktop, `?time=${DAY}&heading=20`);
  report.day = await page.evaluate(() => ({ sun: window.__obs.body('Sun'), calls: window.__obs.calls, sky: [...document.querySelectorAll('#hud-sky li')].map((l) => l.textContent) }));
  await page.screenshot({ path: `${out}/site-day.png` });
  await page.evaluate(()=>window.__obs.setPosition(-3,4));await page.waitForTimeout(300);
  await page.locator('#btn-telescope').click();
  check((await page.locator('#eyepiece-status').textContent()).includes('Daylight'),'daylight telescope status is explicit');
  await context.close();
}
// 4. phone, with touch
{
  const { context, page } = await open('mobile', { viewport: { width: 390, height: 844 }, deviceScaleFactor: 3, isMobile: true, hasTouch: true }, `?time=${NIGHT}`);
  report.mobile = await page.evaluate(() => ({ pixelRatio: window.__obs.pixelRatio, renderSize: window.__obs.renderSize, touch: document.documentElement.classList.contains('touch'), scrollW: document.documentElement.scrollWidth }));
  await page.screenshot({ path: `${out}/site-mobile.png` });
  await page.evaluate(()=>window.__obs.setPosition(-3,4));await page.waitForTimeout(350);
  await page.locator('#btn-telescope').click();
  check(await page.locator('#readout').isVisible(),'mobile telescope button opens eyepiece');
  check(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'mobile modal has no horizontal overflow');
  await page.screenshot({path:`${out}/site-mobile-eyepiece.png`});
  await page.locator('#btn-close-eyepiece').click();
  check(await page.locator('#readout').isHidden(),'mobile close button works');
  await context.close();
}
// 5. golden hour, mid-morning haze: another sky colour
{
  const { context, page } = await open('dusk', desktop, `?time=2026-10-04T18:15:00%2B05:30&heading=270&pitch=6`);
  await page.screenshot({ path: `${out}/site-dusk.png` });
  await context.close();
}
// 6. no WebGL: the text page stays readable and shows the live picture
{
  const { context, page } = await open('nowebgl', desktop, '', {
    waitReady: false,
    init: () => { HTMLCanvasElement.prototype.getContext = () => null; },
  });
  await page.waitForSelector('html.fallback', { timeout: 20000 });
  await page.waitForTimeout(1500);
  report.fallback = await page.evaluate(() => ({
    h1: document.querySelector('h1').textContent, hero: !!document.querySelector('#hero img'), note: document.getElementById('fallback-note').textContent,
    heroLoaded: document.querySelector('#hero img')?.naturalWidth > 0, links: [...document.querySelectorAll('footer a')].map((a) => a.href),
    sections: [...document.querySelectorAll('h2')].map((h) => h.textContent),
  }));
  await page.screenshot({ path: `${out}/site-fallback.png`, fullPage: false });
  await context.close();
}
// 7. no JavaScript at all
{
  const { context, page } = await open('nojs', { ...desktop, javaScriptEnabled: false }, '', { waitReady: false });
  report.nojs = await page.evaluate(() => ({ visible: getComputedStyle(document.getElementById('text-version')).position, canvas: getComputedStyle(document.getElementById('view')).display, heroNoscript: !!document.querySelector('#hero img[src="/live.svg"]') }));
  await context.close();
}
await browser.close();
console.log(JSON.stringify(report, null, 1));
if (problems.length) { console.log('PROBLEMS:\n' + [...new Set(problems)].join('\n')); process.exit(1); }
console.log('no console errors, page errors, failed requests or HTTP errors');
