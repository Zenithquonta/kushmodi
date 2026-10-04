// Real-browser check of the Living Observatory website (Chromium through Playwright, software GL).
//   node scripts/site_browser_check.mjs http://127.0.0.1:8099 OUT_DIR       (python scripts/site_preview.py --port 8099)
// Serve the site with the production Content-Security-Policy in force (scripts/site_preview.py does). Fails on any console error,
// page error, failed request or HTTP error status, and on every failed assertion. Software GL renders about one frame per
// second, so movement is always measured in rendered frames (never in wall-clock milliseconds).
import { createRequire } from 'node:module';
import fs from 'node:fs';
const require = createRequire(import.meta.url);
const { chromium } = require(process.env.PLAYWRIGHT_PATH || 'playwright');

const base = process.argv[2] || 'http://127.0.0.1:8099';
const out = process.argv[3] || '.';
fs.mkdirSync(out, { recursive: true });
const NIGHT = '2026-10-04T23:30:00%2B05:30', SATURN = '2026-10-05T00:30:00%2B05:30', DAY = '2026-10-04T12:00:00%2B05:30';
const SATURN_NIGHT = '2026-10-05T23:30:00%2B05:30', SET = '2026-10-05T03:30:00%2B05:30';
const problems = [];
const report = {};
function check(value, description) { if (!value) problems.push(`assertion: ${description}`); }

const launch = { args: ['--use-angle=swiftshader', '--use-gl=angle', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist', '--no-sandbox'] };
if (process.env.CHROMIUM_PATH) launch.executablePath = process.env.CHROMIUM_PATH;
const browser = await chromium.launch(launch);

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
    await page.waitForFunction(() => window.__obs && window.__obs.ready, null, { timeout: 90000 });
    await page.waitForTimeout(1500);
  }
  return { context, page };
}

const frames = (page, n) => page.evaluate((count) => new Promise((resolve) => { let i = 0; const f = () => (++i >= count ? resolve() : requestAnimationFrame(f)); requestAnimationFrame(f); }), n);
const position = (page) => page.evaluate(() => ({ x: window.__obs.position.x, z: window.__obs.position.z }));
const dist = (a, b) => Math.hypot(a.x - b.x, a.z - b.z);
async function hold(page, key, n) { await page.keyboard.down(key); await frames(page, n); await page.keyboard.up(key); }
const eyepiece = (page) => page.evaluate(() => {
  const pixels = document.getElementById('eyepiece-canvas').getContext('2d').getImageData(0, 0, 192, 192).data;
  let lit = 0, ring = 0;
  for (let i = 0; i < pixels.length; i += 4) {
    if (pixels[i] + pixels[i + 1] + pixels[i + 2] > 100) {
      lit++;
      const p = i / 4, x = p % 192, y = Math.floor(p / 192);
      if (Math.abs(x - 96) > 40 && Math.abs(y - 96) < 26) ring++;
    }
  }
  return {
    lit, ring, title: document.getElementById('eyepiece-title').textContent, status: document.getElementById('eyepiece-status').textContent,
    caption: document.getElementById('eyepiece-caption').textContent, label: document.getElementById('eyepiece-canvas').getAttribute('aria-label'),
    inert: document.getElementById('view').inert,
  };
});
const desktop = { viewport: { width: 1280, height: 720 }, deviceScaleFactor: 1 };

// guide invariants for the current view: a visible ring sits on the planet's projected position; hidden rings belong to bodies that
// are below the horizon, off the screen or covered
async function guideInvariants(page, label) {
  await frames(page, 3);
  const data = await page.evaluate(() => ({ planets: window.__obs.planets(), guides: window.__obs.guides, w: innerWidth, h: innerHeight }));
  let visible = 0;
  for (const g of data.guides) {
    const p = data.planets.find((q) => q.name === g.name);
    if (!p) { problems.push(`assertion: ${label}: guide ${g.name} has no planet`); continue; }
    if (!g.hidden) {
      visible++;
      check(p.altitude > 0, `${label}: ${g.name} ring only above the horizon`);
      check(p.screen && Math.hypot(g.x - p.screen.x, g.y - p.screen.y) <= 3, `${label}: ${g.name} ring within 3 px of the projected planet`);
    }
  }
  for (const p of data.planets) {
    const g = data.guides.find((q) => q.name === p.name);
    if (p.altitude <= 0) check(!g || g.hidden, `${label}: ${p.name} below the horizon has no ring`);
    const off = !p.screen || p.screen.x < 0 || p.screen.y < 0 || p.screen.x > data.w || p.screen.y > data.h;
    if (off) check(!g || g.hidden, `${label}: ${p.name} off screen has no ring`);
  }
  return { visible, guides: data.guides, planets: data.planets.map((p) => ({ name: p.name, altitude: Math.round(p.altitude), screen: p.screen })) };
}

// 1. night, facing north (the default): sky, scenery and the telescope interaction
{
  const { context, page } = await open('night', desktop, `?time=${NIGHT}`);
  report.night = await page.evaluate(() => ({
    polaris: window.__obs.star('Polaris'), saturn: window.__obs.body('Saturn'), moon: window.__obs.body('Moon'),
    target: window.__obs.target, heading: window.__obs.heading, pixelRatio: window.__obs.pixelRatio, renderSize: window.__obs.renderSize,
    calls: window.__obs.calls, triangles: window.__obs.triangles, limit: window.__obs.limitingMagnitude, fps: window.__obs.fps,
    hudTime: document.getElementById('hud-time').textContent, sky: [...document.querySelectorAll('#hud-sky li')].map((l) => l.textContent),
    weather: document.getElementById('hud-weather').textContent, sprites: window.__obs.sprites.length,
  }));
  check(report.night.sprites > 100, 'the 2.5D scene has its sprites');
  await page.screenshot({ path: `${out}/site-night.png` });
  await page.keyboard.press('KeyE');
  await frames(page, 2);
  check(await page.locator('#readout').isHidden(), 'telescope requires proximity');
  // approach: stand in front of the telescope (clear of its collider), face it, press E
  await page.evaluate(() => { window.__obs.setPosition(-3, 4); window.__obs.setView(5.7, 6); });
  await frames(page, 3);
  check(await page.locator('#btn-telescope').isVisible(), 'the telescope button appears near the telescope');
  await page.screenshot({ path: `${out}/site-telescope-approach.png` });
  await page.keyboard.press('KeyE');
  await frames(page, 2);
  report.readout = await page.evaluate(() => (document.getElementById('readout').hidden ? null : document.getElementById('readout-body').textContent));
  check(!!report.readout, 'E opens nearby telescope');
  report.eyepiece = await eyepiece(page);
  check(report.eyepiece.lit > 100, 'visible nightly object has a pixel-art eyepiece');
  check(report.eyepiece.title === 'Altair' && /pixel-art illustration/i.test(report.eyepiece.caption), 'eyepiece is a labelled illustration of the nightly target');
  check(report.eyepiece.inert, 'modal makes background inert');
  check(await page.evaluate(() => document.activeElement.id === 'btn-close-eyepiece'), 'focus moves into the modal on open');
  await page.keyboard.press('Tab');
  check(await page.evaluate(() => document.activeElement.id === 'btn-close-eyepiece'), 'modal traps keyboard focus (Tab)');
  await page.keyboard.press('Shift+Tab');
  check(await page.evaluate(() => document.activeElement.id === 'btn-close-eyepiece'), 'modal traps keyboard focus (Shift+Tab)');
  const paused = await position(page);
  await hold(page, 'KeyW', 4);
  check(dist(await position(page), paused) < 0.01, 'walking pauses in eyepiece');
  await page.screenshot({ path: `${out}/site-telescope.png` });
  await page.keyboard.press('KeyE');
  await frames(page, 2);
  check(await page.locator('#readout').isHidden(), 'E closes eyepiece');
  check(await page.evaluate(() => document.activeElement.id === 'view' && !document.getElementById('view').inert), 'closing returns focus to the world and removes inert');
  // movement after closing, in two directions: the key must reach the world again
  const afterE = await position(page);
  await hold(page, 'KeyS', 3);
  const s1 = await position(page);
  check(dist(s1, afterE) > 0.2, 'walking (S) resumes after E closes the eyepiece');
  await page.evaluate(() => { window.__obs.setPosition(-3, 4); window.__obs.setView(-58, 8); });
  await frames(page, 3);
  await page.locator('#btn-telescope').click();
  check(await page.locator('#readout').isVisible(), 'the button reopens the eyepiece');
  await page.keyboard.press('Escape');
  await frames(page, 2);
  check(await page.locator('#readout').isHidden(), 'Escape returns to world');
  // from a spot clear of every collider, walk away from and back toward the telescope
  await page.evaluate(() => { window.__obs.setPosition(-1, 8); window.__obs.setView(0, 6); });
  await frames(page, 2);
  const clear0 = await position(page);
  await hold(page, 'KeyW', 5);
  const clear1 = await position(page);
  check(clear0.z - clear1.z > 0.3, 'walking forward (W) resumes after Escape');
  await hold(page, 'KeyA', 4);
  check(dist(await position(page), clear1) > 0.2, 'strafing (A) resumes after Escape');
  await page.evaluate(() => { window.__obs.setPosition(-3, 4); window.__obs.setView(-58, 8); });
  await frames(page, 2);
  await page.locator('#btn-telescope').click();
  await page.locator('#btn-close-eyepiece').click();
  await frames(page, 2);
  check(await page.locator('#readout').isHidden(), 'close button returns to world');
  const afterClose = await position(page);
  await hold(page, 'KeyS', 4);
  check(dist(await position(page), afterClose) > 0.2, 'walking resumes after the close button');
  await context.close();
}

// 2. Saturn: guides, alignment, occlusion, the guide toggle
{
  const { context, page } = await open('saturn', desktop, `?time=${SATURN}&heading=180&pitch=55`);
  report.saturn = await page.evaluate(() => ({ saturn: window.__obs.body('Saturn'), target: window.__obs.target }));
  report.guideState = await guideInvariants(page, 'saturn view');
  const saturnGuide = report.guideState.guides.find((g) => g.name === 'Saturn' && !g.hidden);
  check(!!saturnGuide, 'Saturn ring is shown when Saturn is on screen');
  await page.screenshot({ path: `${out}/site-saturn.png` });
  await page.locator('#btn-guides').click();
  check(await page.locator('#planet-guides').isHidden(), 'guide toggle hides rings');
  await page.locator('#btn-guides').click();
  check(await page.locator('#planet-guides').isVisible(), 'guide toggle shows rings again');
  await page.evaluate(() => window.__obs.setView(0, 9));
  report.guideNorth = await guideInvariants(page, 'north view');
  await context.close();
}

// 2b. occlusion and depth order, from the live scene (hooks use the same code as the guides)
{
  const { context, page } = await open('depth', desktop, `?time=${NIGHT}`);
  const r = await page.evaluate(() => {
    const o = window.__obs, pos = o.position, sp = o.sprites;
    const result = { up: o.blockedSky(80, 0), below: o.blockedSky(-5, 180) };
    // direction to the workshop's middle from where the visitor stands
    const shed = sp.find((s) => s.name === 'workshop');
    const dx = shed.x - pos.x, dz = shed.z - pos.z, dy = shed.y + shed.h * 0.4 - pos.y;
    const az = (Math.atan2(dx, -dz) * 180) / Math.PI, alt = (Math.atan2(dy, Math.hypot(dx, dz)) * 180) / Math.PI;
    result.shed = { alt, az, blocked: o.blockedSky(alt, az) };
    // a clear sky direction well above the workshop roof
    result.aboveShed = o.blockedSky(alt + 35, az);
    // depth order: telescope versus the rock outcrop behind it, from both ends of the line joining them
    const tel = sp.find((s) => s.name === 'telescope'), rock = sp.find((s) => s.name === 'rock_a' && Math.hypot(s.x + 5.5, s.z + 5) < 0.1);
    const ux = (tel.x - rock.x), uz = (tel.z - rock.z), len = Math.hypot(ux, uz);
    const nx = ux / len, nz = uz / len, y = tel.y + 1.3;
    const fromTelescopeSide = o.frontHit(tel.x + nx * 6, y, tel.z + nz * 6, -nx, 0, -nz);
    const fromRockSide = o.frontHit(rock.x - nx * 6, y, rock.z - nz * 6, nx, 0, nz);
    result.order = { fromTelescopeSide: fromTelescopeSide && fromTelescopeSide.name, fromRockSide: fromRockSide && fromRockSide.name };
    return result;
  });
  report.depth = r;
  check(r.up === false, 'open sky overhead is not occluded');
  check(r.below === true, 'directions below the horizon are covered by the ground');
  check(r.shed.blocked === true, 'painted workshop occludes a guide behind it (alpha mask)');
  check(r.aboveShed === false, 'sky well above the workshop roof is clear');
  check(r.order.fromTelescopeSide === 'telescope' && r.order.fromRockSide === 'rock_a', 'depth order flips with the viewpoint (telescope in front from its side, rock in front from the rock side)');
  // the real picture: walking changes which sprite is in front on screen too (frame sampled at both viewpoints)
  await page.evaluate(() => { window.__obs.setPosition(-2.5, 7); window.__obs.setView(0, 4); });
  await frames(page, 3);
  await page.screenshot({ path: `${out}/site-depth-a.png` });
  await page.evaluate(() => { window.__obs.setPosition(-9, 4); window.__obs.setView(-15, 4); });
  await frames(page, 3);
  await page.screenshot({ path: `${out}/site-depth-b.png` });
  await context.close();
}

// 2c. a planet on screen whose ring is checked at several views (invariants), incl. Neptune at the telescope-only limit
{
  const { context, page } = await open('east', desktop, `?time=${NIGHT}&heading=140&pitch=50`);
  report.east = await page.evaluate(() => ({ uranus: window.__obs.body('Uranus'), saturn: window.__obs.body('Saturn') }));
  report.guideEast = await guideInvariants(page, 'south-east view');
  check(report.guideEast.visible > 0, 'a planet ring appears for a planet in view');
  await page.screenshot({ path: `${out}/site-night-trail.png` });
  await context.close();
}

// 3. Saturn is the nightly target on 5 October: the eyepiece shows the ringed planet
{
  const { context, page } = await open('saturn-eyepiece', desktop, `?time=${SATURN_NIGHT}`);
  await page.evaluate(() => { window.__obs.setPosition(-3, 4); window.__obs.setView(-58, 8); });
  await frames(page, 3);
  await page.locator('#btn-telescope').click();
  report.saturnEyepiece = await eyepiece(page);
  check(report.saturnEyepiece.title === 'Saturn', 'nightly target on 5 October is Saturn');
  check(report.saturnEyepiece.lit > 400, 'Saturn eyepiece draws a lit disc');
  check(report.saturnEyepiece.ring > 40, 'Saturn eyepiece draws rings beyond the disc');
  check(/pixel-art illustration/i.test(report.saturnEyepiece.caption) && /pixel-art illustration/i.test(report.saturnEyepiece.label), 'Saturn eyepiece is labelled as an illustration');
  await page.screenshot({ path: `${out}/site-saturn-eyepiece.png` });
  await context.close();
}

// 3b. the target has set: honest blank eyepiece
{
  const { context, page } = await open('set', desktop, `?time=${SET}`);
  await page.evaluate(() => { window.__obs.setPosition(-3, 4); window.__obs.setView(-58, 8); });
  await frames(page, 3);
  await page.locator('#btn-telescope').click();
  report.belowHorizon = await eyepiece(page);
  check(/Below the horizon/.test(report.belowHorizon.status), 'set target explains the horizon status');
  check(report.belowHorizon.lit === 0, 'set target shows no illustration');
  await page.screenshot({ path: `${out}/site-below-horizon.png` });
  await context.close();
}

// 4. day
{
  const { context, page } = await open('day', desktop, `?time=${DAY}&heading=20`);
  report.day = await page.evaluate(() => ({ sun: window.__obs.body('Sun'), calls: window.__obs.calls, sky: [...document.querySelectorAll('#hud-sky li')].map((l) => l.textContent) }));
  await page.screenshot({ path: `${out}/site-day.png` });
  report.guideDay = await guideInvariants(page, 'day view');
  await page.evaluate(() => window.__obs.setPosition(-3, 4));
  await frames(page, 3);
  await page.locator('#btn-telescope').click();
  const e = await eyepiece(page);
  check(e.status.includes('Daylight'), 'daylight telescope status is explicit');
  check(e.lit === 0, 'no illustration in daylight');
  await context.close();
}

// 5. phone with touch: joystick movement, telescope button, no overflow
{
  const { context, page } = await open('mobile', { viewport: { width: 390, height: 844 }, deviceScaleFactor: 3, isMobile: true, hasTouch: true }, `?time=${NIGHT}`);
  report.mobile = await page.evaluate(() => ({ pixelRatio: window.__obs.pixelRatio, renderSize: window.__obs.renderSize, touch: document.documentElement.classList.contains('touch'), scrollW: document.documentElement.scrollWidth }));
  check(report.mobile.touch, 'touch layout is active');
  check(await page.locator('#joy').isVisible(), 'joystick is visible on the phone');
  await page.screenshot({ path: `${out}/site-mobile.png` });
  // drive the joystick with real pointer events: push the knob upward (forward)
  const joy = await page.locator('#joy').boundingBox();
  const cx = joy.x + joy.width / 2, cy = joy.y + joy.height / 2;
  await page.evaluate(() => window.__obs.setPosition(0, 12));
  await frames(page, 2);
  const p0 = await position(page);
  await page.evaluate(([x, y]) => {
    const j = document.getElementById('joy');
    const ev = (type, dy) => j.dispatchEvent(new PointerEvent(type, { pointerId: 7, pointerType: 'touch', clientX: x, clientY: y + dy, bubbles: true, isPrimary: true }));
    ev('pointerdown', 0); ev('pointermove', -40);
  }, [cx, cy]);
  await frames(page, 8);
  const p1 = await position(page);
  check(p0.z - p1.z > 0.3, 'the touch joystick moves the player forward');
  await page.evaluate(([x, y]) => {
    const j = document.getElementById('joy');
    j.dispatchEvent(new PointerEvent('pointerup', { pointerId: 7, pointerType: 'touch', clientX: x, clientY: y, bubbles: true, isPrimary: true }));
  }, [cx, cy]);
  await frames(page, 3);
  const p2 = await position(page);
  await frames(page, 4);
  check(dist(await position(page), p2) < 0.01, 'releasing the joystick stops the player');
  await page.evaluate(() => { window.__obs.setPosition(-3, 4); window.__obs.setView(-58, 8); });
  await frames(page, 3);
  await page.locator('#btn-telescope').tap();
  check(await page.locator('#readout').isVisible(), 'mobile telescope button opens eyepiece');
  check(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), 'mobile modal has no horizontal overflow');
  await page.screenshot({ path: `${out}/site-mobile-eyepiece.png` });
  await page.locator('#btn-close-eyepiece').tap();
  await frames(page, 2);
  check(await page.locator('#readout').isHidden(), 'mobile close button works');
  const m0 = await position(page);
  await page.evaluate(([x, y]) => {
    const j = document.getElementById('joy');
    const ev = (type, dy) => j.dispatchEvent(new PointerEvent(type, { pointerId: 8, pointerType: 'touch', clientX: x, clientY: y + dy, bubbles: true, isPrimary: true }));
    ev('pointerdown', 0); ev('pointermove', 40);
  }, [cx, cy]);
  await frames(page, 8);
  check(dist(await position(page), m0) > 0.3, 'the joystick works again after closing the eyepiece');
  await context.close();
}

// 6. golden hour, mid-morning haze: another sky colour
{
  const { context, page } = await open('dusk', desktop, `?time=2026-10-04T18:15:00%2B05:30&heading=270&pitch=6`);
  await page.screenshot({ path: `${out}/site-dusk.png` });
  await context.close();
}

// 7. no WebGL: the text page stays readable and shows the live picture
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

// 8. no JavaScript at all
{
  const { context, page } = await open('nojs', { ...desktop, javaScriptEnabled: false }, '', { waitReady: false });
  report.nojs = await page.evaluate(() => ({ visible: getComputedStyle(document.getElementById('text-version')).position, canvas: getComputedStyle(document.getElementById('view')).display, heroNoscript: !!document.querySelector('#hero img[src="/live.svg"]') }));
  await context.close();
}
await browser.close();
report.assertionFailures = problems.filter((p) => p.startsWith('assertion:')).length;
console.log(JSON.stringify(report, null, 1));
if (problems.length) { console.log('PROBLEMS:\n' + [...new Set(problems)].join('\n')); process.exit(1); }
console.log('no console errors, page errors, failed requests, HTTP errors or failed assertions');
