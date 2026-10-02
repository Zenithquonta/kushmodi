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
  // click the telescope: the readout appears with RA/Dec/alt/az
  await page.evaluate(() => window.__obs.setPosition(-3, 4));
  await page.evaluate(() => window.__obs.setView(-58, 8));
  await page.waitForTimeout(500);
  await page.keyboard.press('KeyE');
  await page.waitForTimeout(400);
  report.readout = await page.evaluate(() => document.getElementById('readout').hidden ? null : document.getElementById('readout-body').textContent);
  await page.screenshot({ path: `${out}/site-telescope.png` });
  await context.close();
}
// 2. Saturn near 00:30 IST on 5 October: due south, high up
{
  const { context, page } = await open('saturn', desktop, `?time=${SATURN}&heading=180&pitch=55`);
  report.saturn = await page.evaluate(() => ({ saturn: window.__obs.body('Saturn'), target: window.__obs.target }));
  await page.screenshot({ path: `${out}/site-saturn.png` });
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
  await context.close();
}
// 4. phone, with touch
{
  const { context, page } = await open('mobile', { viewport: { width: 390, height: 844 }, deviceScaleFactor: 3, isMobile: true, hasTouch: true }, `?time=${NIGHT}`);
  report.mobile = await page.evaluate(() => ({ pixelRatio: window.__obs.pixelRatio, renderSize: window.__obs.renderSize, touch: document.documentElement.classList.contains('touch'), scrollW: document.documentElement.scrollWidth }));
  await page.screenshot({ path: `${out}/site-mobile.png` });
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
