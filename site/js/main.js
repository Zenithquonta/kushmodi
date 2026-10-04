// Living Observatory: boots the 3D world, or leaves the plain text page when 3D is not possible.
import * as THREE from '../vendor/three/three.module.js';
import { DEG, altAz, applyMatrix, bodyTrails, makeObserver, skyState, twilightName, PLANETS } from './ephemeris.js';
import { Sky, TRAIL_BODIES } from './sky.js';
import { buildWorld, POS } from './world.js';
import { Player } from './controls.js';
import { PlanetGuides } from './planet-guides.js';
import { Hud } from './hud.js';
import { brightStars, nightlyTargetPicker, skyLines } from './target.js';
import { loadLive, weatherText } from './live.js';

const html = document.documentElement;
const params = new URLSearchParams(location.search);
const smooth = (a, b, x) => { const t = Math.min(1, Math.max(0, (x - a) / (b - a))); return t * t * (3 - 2 * t); };
const lerp = (a, b, t) => a + (b - a) * t;

// ----- the plain page --------------------------------------------------------------------------------------------
function ensureHero() {
  const hero = document.getElementById('hero');
  if (!hero || hero.querySelector('img')) return;
  const picture = document.createElement('picture');
  const source = document.createElement('source');
  source.media = '(prefers-reduced-motion: reduce)';
  source.srcset = '/live.png';
  const img = document.createElement('img');
  img.src = '/live.svg';
  img.alt = "Kush Modi's observatory live from Mumbai: the real sky, season and weather over the telescope and maker workshop, redrawn through the day";
  picture.append(source, img);
  hero.appendChild(picture);
}

function fallback(reason) {
  html.classList.remove('gl');
  html.classList.add('fallback');
  const note = document.getElementById('fallback-note');
  if (note) { note.textContent = reason; note.hidden = false; }
  ensureHero();
}

function webglOk() {
  try {                                                  // probe on a scratch canvas so the real one keeps its attributes
    const probe = document.createElement('canvas');
    return !!(window.WebGL2RenderingContext && probe.getContext('webgl2')) || !!probe.getContext('webgl');
  } catch (error) {
    return false;
  }
}

// ----- the simulated clock (the ?time= and ?speed= test hooks) -----------------------------------------------------
function makeClock() {
  const raw = params.get('time');
  const given = raw ? Date.parse(raw.replace(' ', '+')) : NaN;      // a "+" in a URL arrives as a space
  const speed = Math.min(5000, Math.max(0, Number(params.get('speed')) || 1));
  const start = Number.isFinite(given) ? given : Date.now();
  const t0 = performance.now();
  return { now: () => new Date(start + (performance.now() - t0) * speed), hooked: Number.isFinite(given) };
}

async function getJson(path) {
  const response = await fetch(path);
  if (!response.ok) throw new Error(`${path}: ${response.status}`);
  return response.json();
}

async function boot() {
  const canvas = document.getElementById('view');
  if (!canvas) return;
  if (!webglOk()) { fallback('The 3D observatory needs WebGL, which is not available here. This is the text version.'); return; }

  let site, stars, milkyway, constellations, env;
  try {
    [site, stars, milkyway, constellations, env] = await Promise.all([
      getJson('data/site.json'), getJson('data/stars.json'), getJson('data/milkyway.json'), getJson('data/constellations.json'), loadLive(),
    ]);
  } catch (error) {
    fallback('The sky data could not be loaded, so this is the text version.');
    return;
  }

  let renderer;
  try {
    renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: false, powerPreference: 'high-performance' });
  } catch (error) {
    fallback('The 3D observatory could not start on this device. This is the text version.');
    return;
  }
  canvas.addEventListener('webglcontextlost', (e) => { e.preventDefault(); fallback('The 3D view was lost. Reload the page to try again; this is the text version.'); });
  html.classList.add('gl');

  const motion = window.matchMedia('(prefers-reduced-motion: reduce)');
  let reduced = motion.matches;
  motion.addEventListener?.('change', () => { reduced = motion.matches; player.reduced = reduced; });
  const coarse = window.matchMedia('(pointer: coarse)').matches || navigator.maxTouchPoints > 0 && !window.matchMedia('(hover: hover)').matches;
  if (coarse) html.classList.add('touch');

  // scene, camera, lights
  const scene = new THREE.Scene();
  scene.fog = new THREE.Fog(0x000000, 14, 170);
  const camera = new THREE.PerspectiveCamera(62, 16 / 9, 0.1, 8000);
  const hemi = new THREE.HemisphereLight(0x3a4f8a, 0x141a2a, 1);
  const sunLight = new THREE.DirectionalLight(0xfff0d0, 0);
  const moonLight = new THREE.DirectionalLight(0x9fb8ff, 0);
  scene.add(hemi, sunLight, sunLight.target, moonLight, moonLight.target);

  const observer = makeObserver(site);
  const clock = makeClock();
  let world;
  try {
    world = await buildWorld(scene, site, env);
  } catch (error) {
    console.error(error);
    fallback('The scenery could not be loaded, so this is the text version.');
    return;
  }
  const sky = new Sky(scene, { stars, milkyway, constellations }, PLANETS, 1);
  const guides = new PlanetGuides(document.getElementById('planet-guides'), document.getElementById('btn-guides'));
  world.sky = sky;
  world.look = sky.look;
  const bright = brightStars(stars);
  const targetForNight = nightlyTargetPicker(bright, observer);

  const hud = new Hud();
  hud.el.root.hidden = false;
  hud.setHint(coarse ? 'Joystick to move. Drag to look. Tap the telescope.' : 'Click to look around. WASD to move. E at the telescope.');

  const heading = params.has('heading') ? Number(params.get('heading')) : 0;
  const pitch = params.has('pitch') ? Number(params.get('pitch')) : 9;
  const player = new Player(canvas, world.colliders, {
    x: POS.start[0], z: POS.start[1], yaw: -(Number.isFinite(heading) ? heading : 0) * DEG, pitch: (Number.isFinite(pitch) ? pitch : 9) * DEG,
    joystick: document.getElementById('joy'), knob: document.getElementById('knob'),
    onPick: (x, y, centre) => pickAt(x, y, centre),
    onKey: (code) => key(code),
  });
  player.reduced = reduced;

  // Full-resolution rendering, capped on dense displays to keep mobile GPU cost bounded.
  let pixelRatio = 1, renderW = 0, renderH = 0;
  function resize() {
    const w = Math.max(1, window.innerWidth), h = Math.max(1, window.innerHeight);
    const scale = Math.min(1, 1920 / w);
    pixelRatio = Math.min(window.devicePixelRatio || 1, 1.5);
    renderW = Math.max(160, Math.round(w * scale));
    renderH = Math.max(90, Math.round(h * scale));
    renderer.setPixelRatio(pixelRatio);
    renderer.setSize(renderW, renderH, false);
    camera.aspect = w / h;
    camera.fov = w / h < 1 ? 74 : 62;
    camera.updateProjectionMatrix();
    sky.resize(pixelRatio);
  }
  window.addEventListener('resize', resize);
  resize();

  // ----- state -------------------------------------------------------------------------------------------------
  let state = null, lastSimMs = -1e12, lastTrailMs = -1e12, target = null;
  const raycaster = new THREE.Raycaster();
  const ndc = new THREE.Vector2();
  let lastLive = performance.now();

  function refreshSky(date) {
    state = skyState(date, observer);
    target = targetForNight(date, state);
    const ms = date.getTime();
    if (ms - lastTrailMs >= 30000 || ms < lastTrailMs) {            // the 3-hour trails are recomputed every 30 s of sky time
      lastTrailMs = ms;
      sky.setTrails(bodyTrails(date, observer, TRAIL_BODIES));
    }
    sky.setState(state, env, reduced);
    applyLook();
    hud.setSky(skyLines(state, twilightName(state.sun.altitude)), weatherText(env));
    world.telescope.aim(target.world, 0, !world.telescope.ready);
    if (hud.readoutOpen) hud.showTelescope(target);
  }

  function applyLook() {
    const alt = state.sun.altitude;
    const day = smooth(-6, 12, alt);
    const look = sky.look;
    const fog = scene.fog;
    fog.color.setRGB(look.horizon[0], look.horizon[1], look.horizon[2], THREE.SRGBColorSpace);
    const mist = Math.min(1, env.haze * 0.5 + env.fog * 0.9 + env.rain * 0.35);
    fog.near = lerp(14, 8, mist);                       // layered depth: the far clearing and tree line melt into the horizon colour
    fog.far = lerp(170, 90, mist * 0.9);
    hemi.color.setRGB(lerp(0.2, 0.62, day) + look.zenith[0] * 0.3, lerp(0.3, 0.72, day) + look.zenith[1] * 0.3, lerp(0.55, 0.9, day), THREE.SRGBColorSpace);
    hemi.groundColor.setRGB(lerp(0.08, 0.3, day), lerp(0.1, 0.28, day), lerp(0.17, 0.2, day), THREE.SRGBColorSpace);
    hemi.intensity = lerp(1.3, 2.7, day) * (1 - env.cloud * 0.12);
    const sunI = 3.6 * smooth(-2, 14, alt) * (1 - env.cloud * 0.65);
    sunLight.intensity = sunI;
    const low = 1 - smooth(5, 40, alt);
    sunLight.color.setRGB(1, lerp(0.96, 0.62, low), lerp(0.88, 0.38, low), THREE.SRGBColorSpace);
    sunLight.position.fromArray(state.sun.world).multiplyScalar(100);
    const moonI = 1.5 * state.moon.illuminated * smooth(-2, 12, state.moon.altitude) * (1 - smooth(-8, 4, alt)) * (1 - env.cloud * 0.6);
    moonLight.intensity = moonI;
    moonLight.position.fromArray(state.moon.world).multiplyScalar(100);
    world.terrain.material.color.setScalar(1 - 0.28 * env.wetness);
    scene.background = null;
    renderer.setClearColor(fog.color, 1);
  }

  function pickAt(clientX, clientY, centre) {
    const rect = canvas.getBoundingClientRect();
    ndc.set(centre ? 0 : ((clientX - rect.left) / rect.width) * 2 - 1, centre ? 0 : -((clientY - rect.top) / rect.height) * 2 + 1);
    raycaster.setFromCamera(ndc, camera);
    raycaster.far = 60;
    if (raycaster.intersectObjects(world.pickables, false).length) {
      if (Math.hypot(player.pos.x - POS.telescope[0], player.pos.z - POS.telescope[1]) < 6) toggleReadout(true);
      else hud.setHint('Walk closer to the telescope to look through the eyepiece.');
    }
  }

  function toggleReadout(force) {
    if (!state) return;
    if (hud.readoutOpen && !force) closeEyepiece();
    else {
      hud.showTelescope(target); player.enabled = false; guides.root.hidden = true;
      player.keys.clear(); player.tapped.clear(); player.joy.x = player.joy.y = 0;
      setEyepieceModal(true);
      if (document.pointerLockElement) document.exitPointerLock();
      document.getElementById('btn-close-eyepiece').focus();
    }
  }

  function closeEyepiece() {
    hud.hideTelescope(); setEyepieceModal(false); player.enabled = true; guides.root.hidden = !guides.enabled; canvas.focus();
  }
  function setEyepieceModal(open) {
    for (const element of document.body.children) if (element !== hud.el.root) element.inert = open;
    for (const element of hud.el.root.children) if (element !== hud.el.readout) element.inert = open;
  }
  document.getElementById('btn-close-eyepiece').addEventListener('click', closeEyepiece);
  document.getElementById('btn-telescope').addEventListener('click', () => toggleReadout(true));
  window.addEventListener('keydown', e => {
    if (!hud.readoutOpen) return;
    if (e.code === 'Escape' || e.code === 'KeyE') { e.preventDefault(); closeEyepiece(); }
    if (e.code === 'Tab') { e.preventDefault(); document.getElementById('btn-close-eyepiece').focus(); }
    e.stopImmediatePropagation();
  }, true);
  function key(code) {
    if (code === 'KeyE') {
      const d = Math.hypot(player.pos.x - POS.telescope[0], player.pos.z - POS.telescope[1]);
      if (hud.readoutOpen) closeEyepiece();
      else if (d < 6) toggleReadout(true);
      else hud.setHint('Walk up to the telescope, then press E.');
    } else if (code === 'KeyC') toggleLines();
    else if (code === 'KeyH') toggleHelp();
    else if (code === 'Escape') { closeText(); }
  }

  // ----- buttons and the text version ---------------------------------------------------------------------------
  const textPanel = document.getElementById('text-version');
  const btnText = document.getElementById('btn-text'), btnLines = document.getElementById('btn-lines'), btnHelp = document.getElementById('btn-help');
  function openText() {
    ensureHero();
    textPanel.classList.add('open');
    player.enabled = false;
    if (document.pointerLockElement) document.exitPointerLock();
    textPanel.focus();
  }
  function closeText() {
    if (!textPanel.classList.contains('open')) return;
    textPanel.classList.remove('open');
    player.enabled = true;
    canvas.focus();
  }
  function toggleLines() {
    const on = btnLines.getAttribute('aria-pressed') !== 'true';
    btnLines.setAttribute('aria-pressed', String(on));
    sky.setConstellations(on);
    if (state) sky.setState(state, env, reduced);
  }
  function toggleHelp() {
    const help = document.getElementById('hud-help');
    help.hidden = !help.hidden;
    btnHelp.setAttribute('aria-expanded', String(!help.hidden));
  }
  btnText.addEventListener('click', openText);
  document.getElementById('btn-close-text').addEventListener('click', closeText);
  btnLines.addEventListener('click', toggleLines);
  btnHelp.addEventListener('click', toggleHelp);

  // ----- the loop ---------------------------------------------------------------------------------------------
  let last = performance.now(), hudAt = 0, frames = 0, fpsAt = performance.now(), fps = 0;
  const cameraDir = new THREE.Vector3();
  function frame(ts) {
    requestAnimationFrame(frame);
    const dt = Math.min(0.1, (ts - last) / 1000);
    last = ts;
    const seconds = ts / 1000;
    const date = clock.now();
    if (!state || date.getTime() - lastSimMs >= 2000 || date.getTime() < lastSimMs) { lastSimMs = date.getTime(); refreshSky(date); }
    if (ts - lastLive > 5 * 60 * 1000) {
      lastLive = ts;
      loadLive().then((fresh) => { env = fresh; if (state) refreshSky(clock.now()); }).catch(() => {});
    }
    player.update(dt);
    player.apply(camera);
    sky.frame(camera, seconds, dt, env, reduced);

    world.update(state, env, seconds, dt, reduced, camera);
    world.telescope.aim(target.world, dt, false);
    if (ts - hudAt > 200) {
      hudAt = ts; hud.setClock(date);
      const nearby = Math.hypot(player.pos.x - POS.telescope[0], player.pos.z - POS.telescope[1]) < 6;
      document.getElementById('btn-telescope').hidden = !nearby;
      if (nearby) hud.setHint(`Tonight: ${target.name}. Press E or tap Look through telescope.`);
    }
    hud.setHeading(player.heading);
    renderer.render(scene, camera);
    guides.update(state, camera, world);
    frames++;
    if (ts - fpsAt > 1000) { fps = (frames * 1000) / (ts - fpsAt); frames = 0; fpsAt = ts; }
  }

  // Read-only view of the state for the test scripts (screenshots, positions).
  window.__obs = {
    get ready() { return !!state; },
    get fps() { return fps; },
    get pixelRatio() { return pixelRatio; },
    get renderSize() { return [renderW, renderH]; },
    get calls() { return renderer.info.render.calls; },
    get triangles() { return renderer.info.render.triangles; },
    get limitingMagnitude() { return sky.limit; },
    get env() { return { ...env }; },
    get target() { return target ? { name: target.name, altitude: target.altitude, azimuth: target.azimuth } : null; },
    get heading() { return player.heading; },
    get position() { return { ...player.pos, y: player.eyeY }; },
    body(name) {
      if (!state) return null;
      const b = name === 'Sun' ? state.sun : name === 'Moon' ? state.moon : state.planets.find((p) => p.name === name);
      return b ? { altitude: b.altitude, azimuth: b.azimuth, screen: project(b.world) } : null;
    },
    star(name) {
      const i = stars.names.find(([, n]) => n === name);
      if (!i || !state) return null;
      const [ra, dec] = stars.stars[i[0]];
      const c = Math.cos(dec * DEG);
      const w = applyMatrix(state.matrix, c * Math.cos(ra * DEG), c * Math.sin(ra * DEG), Math.sin(dec * DEG));
      const { alt, az } = altAz(w);
      return { altitude: alt, azimuth: az, screen: project(w) };
    },
    // Test hooks: is the sky direction (altitude, azimuth in degrees) covered by terrain or painted scenery from here?
    blockedSky(altitude, azimuth) {
      const a = altitude * DEG, z = azimuth * DEG;                         // azimuth: 0 north, 90 east; world +X east, -Z north
      const dir = new THREE.Vector3(Math.cos(a) * Math.sin(z), Math.sin(a), -Math.cos(a) * Math.cos(z));
      return guides.blocked(camera.position, dir, world);
    },
    frontHit(ox, oy, oz, dx, dy, dz) {
      const d = new THREE.Vector3(dx, dy, dz).normalize();
      return world.scenery.frontHit({ x: ox, y: oy, z: oz }, d);
    },
    get sprites() { return world.scenery.items.map((i) => ({ name: i.set.name, x: i.x, y: i.y, z: i.z, w: i.w, h: i.h })); },
    get guides() { return [...document.querySelectorAll('.planet-guide')].map((n) => ({ name: n.querySelector('.planet-tag').textContent.replace(' · telescope', ''), hidden: n.hidden, x: parseFloat(n.style.left), y: parseFloat(n.style.top) })); },
    planets() { return state ? state.planets.map((p) => ({ name: p.name, altitude: p.altitude, azimuth: p.azimuth, screen: project(p.world) })) : []; },
    setView(headingDeg, pitchDeg) { player.yaw = -headingDeg * DEG; player.pitch = pitchDeg * DEG; },
    setPosition(x, z) { player.pos.x = x; player.pos.z = z; },
  };
  function project(w) {
    camera.getWorldDirection(cameraDir);
    const v = new THREE.Vector3(w[0], w[1], w[2]);
    if (v.dot(cameraDir) <= 0) return null;
    v.multiplyScalar(1000).add(camera.position).project(camera);
    return { x: Math.round(((v.x + 1) / 2) * window.innerWidth), y: Math.round(((1 - v.y) / 2) * window.innerHeight) };
  }

  requestAnimationFrame(frame);
}

boot().catch((error) => {
  console.error(error);
  fallback('Something went wrong starting the 3D observatory, so this is the text version.');
});
