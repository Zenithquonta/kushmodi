// The observatory itself: hill, equatorial telescope, maker shed, rover and robot, van, drone pad, trees, fence and the
// distant Mumbai skyline. Axes: +X east, +Y up, +Z south (north is -Z). Geometry is merged per material (geom.js), so
// the whole world is a few dozen draw calls. Colliders are returned as plain data for controls.js.
import * as THREE from '../vendor/three/three.module.js';
import { Bag } from './geom.js';
import { HILL_TOP, WALK_RADIUS, buildTerrain, groundHeight } from './terrain.js';
import { DEG } from './ephemeris.js';

const G = HILL_TOP;
const PI = Math.PI;

export const POS = {
  start: [0, 16], telescope: [-7, -4], shed: [17, -9], rover: [-15, 7], van: [-24, -15], pad: [9, 11], boulder: [-6.5, -10.5],
};
const SHED_YAW = -PI / 4;                 // the open front faces south-west, toward the start point

function rng(seed) {                      // small deterministic generator, so the world is the same every visit
  let s = seed >>> 0;
  return () => {
    s = (s + 0x6d2b79f5) >>> 0;
    let t = s;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

// A rod (cylinder) between two points.
function rod(bag, a, b, r, color, segments = 6) {
  const dx = b[0] - a[0], dy = b[1] - a[1], dz = b[2] - a[2];
  const len = Math.hypot(dx, dy, dz);
  bag.cyl(r, r, len, color, (a[0] + b[0]) / 2, (a[1] + b[1]) / 2, (a[2] + b[2]) / 2, Math.acos(dy / len), Math.atan2(dx, dz), 0, segments);
}

function group(name, x, y, z, ry = 0) {
  const g = new THREE.Group();
  g.name = name;
  g.position.set(x, y, z);
  g.rotation.y = ry;
  return g;
}

export function buildWorld(scene, site, env) {
  const world = { colliders: [], lights: {}, animated: [], rain: null };
  const root = new THREE.Group();
  root.name = 'world';
  scene.add(root);

  world.terrain = buildTerrain(env.greenery);
  root.add(world.terrain);

  buildTelescope(world, root, site);
  buildShed(world, root);
  buildRover(world, root);
  buildVan(world, root);
  buildPad(world, root);
  buildScatter(world, root);
  buildSkyline(world, root);

  world.update = (state, env2, seconds, delta, reduced) => update(world, state, env2, seconds, delta, reduced);
  return world;
}

// ----- the telescope ---------------------------------------------------------------------------------------------
function buildTelescope(world, root, site) {
  const [tx, tz] = POS.telescope;
  const t = group('telescope', tx, G, tz);
  t.scale.setScalar(1.5);                  // a little larger than life so it reads from the start point
  root.add(t);
  const head = [0, 1.3, 0];
  const legs = new Bag();
  for (let i = 0; i < 3; i++) {
    const a = PI / 2 + (i * 2 * PI) / 3;
    rod(legs, [Math.cos(a) * 0.12, head[1], Math.sin(a) * 0.12], [Math.cos(a) * 0.85, 0, Math.sin(a) * 0.85], 0.028, 5);
  }
  rod(legs, [0, 0.55, 0], [0.45, 0.55, 0.3], 0.012, 4);                        // spreader bars
  legs.cyl(0.07, 0.07, 0.34, '#2a3140', 0, 1.15, 0);                           // pier
  legs.box(0.28, 0.1, 0.28, '#3a4252', 0, 1.3, 0);                             // head
  legs.cyl(0.18, 0.18, 0.03, '#566074', 0, 0.55, 0, 0, 0, 0, 6);              // accessory tray
  t.add(legs.mesh());

  const polar = new THREE.Group();
  polar.position.set(0, 1.4, 0);
  polar.rotation.x = site.latitude * DEG - PI / 2;                             // the polar axis points at the celestial pole
  t.add(polar);
  const ra = new THREE.Group();
  polar.add(ra);
  const raBag = new Bag();
  raBag.cyl(0.085, 0.085, 0.5, '#2e3646', 0, 0.2, 0);
  raBag.cyl(0.11, 0.11, 0.1, '#4a5468', 0, -0.02, 0);
  raBag.cyl(0.05, 0.05, 0.3, '#1d222d', 0, -0.25, 0);                          // polar finder
  raBag.box(0.5, 0.2, 0.2, '#2e3646', 0, 0.42, 0, 0, 0, 0);                    // declination housing
  ra.add(raBag.mesh());
  const dec = new THREE.Group();
  dec.position.set(0, 0.42, 0);
  ra.add(dec);
  const decBag = new Bag();
  decBag.cyl(0.05, 0.05, 0.4, '#8a96a8', 0, 0, 0, 0, 0, PI / 2);                // declination axis along X
  decBag.cyl(0.012, 0.012, 0.62, '#aeb8c6', 0, -0.4, -0.02);                    // counterweight shaft
  decBag.cyl(0.085, 0.085, 0.12, '#1a1d26', 0, -0.62, -0.02);                   // counterweight
  decBag.cyl(0.085, 0.085, 0.12, '#1a1d26', 0, -0.5, -0.02);
  decBag.cyl(0.115, 0.115, 0.92, '#222a3a', 0, 0.1, 0.17);                      // optical tube
  decBag.cyl(0.125, 0.125, 0.07, '#c8d0dc', 0, 0.56, 0.17);                     // front ring
  decBag.cyl(0.12, 0.12, 0.06, '#10131a', 0, -0.36, 0.17);                      // rear cell
  decBag.cyl(0.13, 0.13, 0.03, '#8a96a8', 0, 0.0, 0.17);                        // saddle rings
  decBag.cyl(0.13, 0.13, 0.03, '#8a96a8', 0, 0.28, 0.17);
  decBag.cyl(0.03, 0.03, 0.16, '#aeb8c6', 0.19, 0.38, 0.17, 0, 0, PI / 2);      // focuser
  decBag.cyl(0.02, 0.02, 0.09, '#d0d6e0', 0.3, 0.38, 0.17, 0, 0, PI / 2);       // eyepiece
  decBag.cyl(0.03, 0.03, 0.34, '#10131a', 0, 0.38, 0.35);                       // finder scope
  decBag.box(0.05, 0.04, 0.04, '#aeb8c6', 0, 0.38, 0.29);
  dec.add(decBag.mesh());
  const proxy = new THREE.Mesh(new THREE.SphereGeometry(1.7, 8, 6), new THREE.MeshBasicMaterial({ visible: false }));
  proxy.position.set(0, 1.4, 0);
  proxy.name = 'telescope';
  t.add(proxy);

  const tel = {
    group: t, proxy, ra, dec, polarTilt: site.latitude * DEG - PI / 2, hour: 0, decl: PI / 2, ready: false,
    position: new THREE.Vector3(tx, G + 2.1, tz),
    // Point the tube at a world direction; smoothly, unless `snap`.
    aim(w, delta, snap) {
      const c = Math.cos(this.polarTilt), s = Math.sin(this.polarTilt);
      const lx = w[0], ly = w[1] * c + w[2] * s, lz = -w[1] * s + w[2] * c;
      const decl = Math.asin(Math.max(-1, Math.min(1, ly)));
      const hour = Math.atan2(-lx, lz);
      if (snap || !this.ready) { this.hour = hour; this.decl = decl; this.ready = true; } else {
        let dh = hour - this.hour;
        dh = ((dh + PI) % (2 * PI) + 2 * PI) % (2 * PI) - PI;
        const k = 1 - Math.exp(-delta * 2.2);
        this.hour += dh * k;
        this.decl += (decl - this.decl) * k;
      }
      this.ra.rotation.y = -this.hour;
      this.dec.rotation.x = PI / 2 - this.decl;
    },
  };
  world.telescope = tel;
  world.pickables = [proxy];
  world.colliders.push({ type: 'circle', x: tx, z: tz, r: 1.3 });
}

// ----- the maker shed --------------------------------------------------------------------------------------------
function buildShed(world, root) {
  const [sx, sz] = POS.shed;
  const shed = group('shed', sx, G, sz, SHED_YAW);
  root.add(shed);
  const wood = '#6b4a2f', dark = '#3a2a1c', plank = '#82603d';
  const b = new Bag(), glow = new Bag();
  b.box(8.6, 0.16, 5.6, plank, 0, 0.08, 0);                                            // deck
  b.box(8.2, 3.0, 0.16, dark, 0, 1.6, -2.5);                                            // back wall
  b.box(0.16, 3.0, 5.2, dark, -4.1, 1.6, 0);                                            // side walls
  b.box(0.16, 3.0, 5.2, dark, 4.1, 1.6, 0);
  for (const x of [-4.1, -1.4, 1.4, 4.1]) b.box(0.22, 3.2, 0.22, wood, x, 1.7, 2.5);   // front posts
  b.box(8.8, 0.2, 0.2, wood, 0, 3.15, 2.5);                                             // front beam
  b.box(9.2, 0.14, 6.2, '#262d3a', 0, 3.34, 0.15, -0.1, 0, 0);                          // roof, sloping down to the front
  b.box(9.3, 0.1, 0.25, '#3a4252', 0, 3.2, 3.2, -0.1, 0, 0);                            // roof lip
  b.box(7.4, 0.1, 1.1, wood, 0, 0.98, -1.85);                                           // workbench
  for (const x of [-3.5, -1.2, 1.2, 3.5]) b.box(0.12, 0.9, 0.12, dark, x, 0.5, -1.4);
  b.box(7.4, 0.08, 0.9, wood, 0, 0.35, -1.9);                                           // lower shelf
  for (let i = 0; i < 3; i++) b.box(2.4, 0.06, 0.34, wood, 3.0, 1.7 + i * 0.5, -2.3);   // wall shelves
  const books = ['#c0392b', '#2e86c1', '#d4ac0d', '#27ae60', '#8e44ad', '#e67e22'];
  for (let i = 0; i < 12; i++) b.box(0.12, 0.34, 0.24, books[i % 6], 2.0 + (i % 6) * 0.18 + (i > 5 ? 0 : 0.1), 1.9 + (i > 5 ? 0.5 : 0), -2.28);
  // 3D printer (left of the bench): frame, gantry, bed with a small rocket
  const px = -2.0;
  for (const dx of [-0.35, 0.35]) for (const dz of [-0.3, 0.3]) b.box(0.05, 0.9, 0.05, '#14171e', px + dx, 1.5, -1.85 + dz);
  b.box(0.8, 0.05, 0.7, '#14171e', px, 1.97, -1.85);
  b.box(0.8, 0.05, 0.7, '#14171e', px, 1.07, -1.85);
  b.box(0.72, 0.04, 0.05, '#c0392b', px, 1.62, -1.85);                                  // x gantry
  b.box(0.1, 0.1, 0.1, '#aeb8c6', px + 0.1, 1.52, -1.85);                               // print head
  b.cyl(0.06, 0.07, 0.3, '#f4f6fa', px - 0.12, 1.28, -1.7, 0, 0, 0, 8);                 // rocket body
  b.cone(0.06, 0.12, '#e74c3c', px - 0.12, 1.49, -1.7, 8);
  for (const a of [0, PI / 2, PI, 1.5 * PI]) b.box(0.015, 0.1, 0.07, '#e74c3c', px - 0.12 + Math.cos(a) * 0.08, 1.15, -1.7 + Math.sin(a) * 0.08);
  glow.box(0.5, 0.02, 0.45, '#3ad0ff', px - 0.12, 1.1, -1.75);                         // lit bed
  // LEGO starship on the bench, bricks, a small crate
  b.box(0.7, 0.07, 0.22, '#e9edf3', 0.9, 1.1, -1.9);
  b.box(0.3, 0.05, 0.6, '#e9edf3', 1.0, 1.08, -1.9);
  b.box(0.2, 0.06, 0.14, '#c0392b', 1.35, 1.12, -1.9);
  b.box(0.12, 0.08, 0.1, '#3a8fd6', 0.55, 1.14, -1.9);
  const brick = ['#e74c3c', '#f1c40f', '#2e86c1', '#2ecc71'];
  for (let i = 0; i < 8; i++) b.box(0.1, 0.06, 0.06, brick[i % 4], 2.0 + (i % 4) * 0.14, 1.07, -1.6 + Math.floor(i / 4) * 0.12);
  b.box(0.6, 0.45, 0.6, '#4a3a28', 3.2, 0.3, 1.8);                                      // crate (lantern stand)
  // wall screen: frame here, picture is a canvas texture below
  b.box(2.5, 1.5, 0.06, '#10131a', 0.1, 2.2, -2.38);
  // neon strips
  glow.box(7.8, 0.06, 0.06, '#38e0ff', 0, 3.02, 2.35);
  glow.box(0.06, 0.06, 3.4, '#ff4fd8', -3.9, 3.05, 0.6);
  glow.box(0.06, 0.06, 2.6, '#38e0ff', 3.9, 3.05, 0.9);
  glow.box(0.3, 0.3, 0.3, '#fff0b8', -1.0, 2.6, 0.5);                                   // lamp bulb
  b.box(0.4, 0.06, 0.4, '#202020', -1.0, 2.82, 0.5);
  glow.box(0.16, 0.24, 0.16, '#ffc44d', 3.2, 0.66, 1.8);                                // lantern
  b.box(0.22, 0.05, 0.22, '#222', 3.2, 0.55, 1.8);
  b.box(0.22, 0.05, 0.22, '#222', 3.2, 0.79, 1.8);
  shed.add(b.mesh());
  const g = glow.mesh('glow');
  shed.add(g);

  const canvas = document.createElement('canvas');
  canvas.width = 200; canvas.height = 120;
  const texture = new THREE.CanvasTexture(canvas);
  texture.magFilter = THREE.NearestFilter;
  texture.minFilter = THREE.NearestFilter;
  texture.generateMipmaps = false;
  texture.colorSpace = THREE.SRGBColorSpace;
  const screen = new THREE.Mesh(new THREE.PlaneGeometry(2.38, 1.38), new THREE.MeshBasicMaterial({ map: texture, fog: false }));
  screen.position.set(0.1, 2.2, -2.34);
  shed.add(screen);
  world.screen = { canvas, texture, last: -1 };

  const lamp = new THREE.PointLight(0xffb468, 18, 16, 1.6);
  lamp.position.set(-1.0, 2.5, 0.5);
  const lantern = new THREE.PointLight(0xffa640, 7, 9, 1.8);
  lantern.position.set(3.2, 0.95, 1.8);
  const screenLight = new THREE.PointLight(0x58d8ff, 5, 7, 1.8);
  screenLight.position.set(0.1, 2.0, -1.6);
  shed.add(lamp, lantern, screenLight);
  world.lights = { lamp, lantern, screenLight };

  // colliders in the shed's frame (rotated boxes)
  const col = (x, z, hw, hd) => world.colliders.push({ type: 'box', x: sx, z: sz, yaw: SHED_YAW, lx: x, lz: z, hw, hd });
  col(0, -2.5, 4.2, 0.25);
  col(-4.1, 0, 0.25, 2.6);
  col(4.1, 0, 0.25, 2.6);
  col(0, -1.85, 3.8, 0.6);
  col(3.2, 1.8, 0.4, 0.4);
  world.shed = shed;
}

function drawScreen(world, state, seconds) {
  const s = world.screen;
  const ctx = s.canvas.getContext('2d');
  const W = s.canvas.width, H = s.canvas.height;
  ctx.fillStyle = '#04182c';
  ctx.fillRect(0, 0, W, H);
  ctx.strokeStyle = 'rgba(58,208,255,0.22)';
  ctx.lineWidth = 1;
  for (let x = 0; x <= W; x += 20) { ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, H); ctx.stroke(); }
  for (let y = 0; y <= H; y += 20) { ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(W, y); ctx.stroke(); }
  ctx.strokeStyle = '#8fe9ff';
  ctx.lineWidth = 2;
  ctx.beginPath();                                                // a wireframe starship, top view
  const ship = [[24, 60], [90, 52], [150, 30], [172, 52], [150, 60], [172, 68], [150, 90], [90, 68], [24, 60]];
  ship.forEach(([x, y], i) => (i ? ctx.lineTo(x, y) : ctx.moveTo(x, y)));
  ctx.moveTo(90, 52); ctx.lineTo(70, 20); ctx.lineTo(112, 44); ctx.moveTo(90, 68); ctx.lineTo(70, 100); ctx.lineTo(112, 76);
  ctx.stroke();
  ctx.fillStyle = '#ffc44d';
  ctx.font = '11px monospace';
  if (state) {
    const f = (n) => `${n >= 0 ? '+' : ''}${n.toFixed(0)}`;
    ctx.fillText(`SUN  ${f(state.sun.altitude)}  MOON ${f(state.moon.altitude)}`, 8, 112);
  } else ctx.fillText('SKY TRACKER', 8, 112);
  ctx.fillStyle = '#a8f8ff';
  ctx.fillText('KM-1  WIREFRAME', 8, 12);
  s.texture.needsUpdate = true;
}

// ----- rover, robot, van, pad ------------------------------------------------------------------------------------
function buildRover(world, root) {
  const [rx, rz] = POS.rover;
  const rover = group('rover', rx, G, rz, 0.7);
  root.add(rover);
  const b = new Bag(), glow = new Bag();
  b.box(1.3, 0.2, 0.8, '#d8dde6', 0, 0.5, 0);
  b.box(1.4, 0.06, 0.06, '#8a96a8', 0, 0.38, 0.36);
  b.box(1.4, 0.06, 0.06, '#8a96a8', 0, 0.38, -0.36);
  b.box(0.9, 0.06, 0.55, '#2a3140', -0.1, 0.62, 0);
  b.box(0.3, 0.14, 0.22, '#e67e22', -0.35, 0.72, 0.1);
  b.cyl(0.025, 0.025, 0.7, '#aeb8c6', 0.45, 0.95, 0, 0, 0, 0, 5);
  b.box(0.2, 0.12, 0.16, '#10131a', 0.45, 1.34, 0);
  b.cyl(0.07, 0.07, 0.06, '#222', 0.2, 0.72, 0, 0, 0, 0, 6);
  glow.box(0.04, 0.06, 0.08, '#58d8ff', 0.56, 1.34, 0);
  for (const x of [-0.5, 0, 0.5]) for (const z of [-0.52, 0.52]) {
    b.cyl(0.19, 0.19, 0.14, '#14161c', x, 0.2, z, PI / 2, 0, 0, 8);
    b.cyl(0.09, 0.09, 0.15, '#8a96a8', x, 0.2, z, PI / 2, 0, 0, 6);
    b.box(0.05, 0.3, 0.05, '#8a96a8', x, 0.35, z * 0.88);
  }
  rover.add(b.mesh(), glow.mesh('glow'));
  world.colliders.push({ type: 'circle', x: rx, z: rz, r: 0.95 });

  // the small robot beside it: turns its head and sweeps a few steps
  const robot = group('robot', rx + 1.6, G, rz - 0.9, -0.6);
  root.add(robot);
  const rb = new Bag(), rg = new Bag();
  rb.box(0.3, 0.06, 0.34, '#2a3140', 0, 0.1, 0);
  for (const z of [-0.18, 0.18]) rb.cyl(0.07, 0.07, 0.05, '#14161c', 0, 0.07, z, PI / 2, 0, 0, 6);
  rb.box(0.26, 0.3, 0.22, '#e9edf3', 0, 0.3, 0);
  rb.box(0.06, 0.2, 0.06, '#aeb8c6', -0.16, 0.32, 0);
  rb.box(0.06, 0.2, 0.06, '#aeb8c6', 0.16, 0.32, 0);
  robot.add(rb.mesh(), rg.mesh('glow'));
  const head = new THREE.Group();
  head.position.set(0, 0.55, 0);
  const hb = new Bag(), hg = new Bag();
  hb.box(0.24, 0.16, 0.2, '#e9edf3', 0, 0, 0);
  hb.cyl(0.01, 0.01, 0.14, '#aeb8c6', 0.08, 0.14, 0, 0, 0, 0, 4);
  hg.box(0.05, 0.04, 0.02, '#58d8ff', -0.055, 0.01, 0.105);
  hg.box(0.05, 0.04, 0.02, '#58d8ff', 0.055, 0.01, 0.105);
  head.add(hb.mesh(), hg.mesh('glow'));
  robot.add(head);
  world.robot = { group: robot, head, home: robot.position.clone() };
  world.colliders.push({ type: 'circle', x: rx + 1.6, z: rz - 0.9, r: 0.4 });
}

function buildVan(world, root) {
  const [vx, vz] = POS.van;
  const van = group('van', vx, G, vz, 0.35);
  root.add(van);
  const b = new Bag(), glow = new Bag();
  b.box(4.8, 0.95, 2.0, '#3d4a3f', 0, 0.95, 0);
  b.box(3.0, 0.85, 1.9, '#4a5a4c', -0.5, 1.85, 0);
  b.box(1.3, 0.5, 1.95, '#3d4a3f', 1.75, 1.2, 0);
  for (const z of [-0.6, 0.6]) b.box(3.2, 0.06, 0.06, '#10131a', -0.4, 2.35, z);       // roof rack
  for (const x of [-1.8, -0.4, 1.0]) b.box(0.06, 0.06, 1.3, '#10131a', x, 2.35, 0);
  b.box(1.2, 0.35, 0.8, '#2a3140', -1.3, 2.55, 0);                                    // roof box
  for (const x of [-1.5, 1.6]) for (const z of [-1.0, 1.0]) {
    b.cyl(0.4, 0.4, 0.3, '#12141a', x, 0.4, z, PI / 2, 0, 0, 10);
    b.cyl(0.18, 0.18, 0.32, '#8a96a8', x, 0.4, z, PI / 2, 0, 0, 6);
  }
  for (const x of [-1.5, 0.3]) glow.box(1.0, 0.5, 0.05, '#ffb24d', x, 1.9, 0.97);        // lit side windows
  glow.box(0.05, 0.4, 1.3, '#ffcf80', 1.2, 1.9, 0);
  glow.box(0.06, 0.2, 0.34, '#fff4c8', 2.42, 1.1, 0.65);                                // headlights
  glow.box(0.06, 0.2, 0.34, '#fff4c8', 2.42, 1.1, -0.65);
  van.add(b.mesh(), glow.mesh('glow'));
  world.colliders.push({ type: 'box', x: vx, z: vz, yaw: 0.35, lx: 0, lz: 0, hw: 2.5, hd: 1.1 });
}

function buildPad(world, root) {
  const [px, pz] = POS.pad;
  const pad = group('pad', px, G, pz);
  root.add(pad);
  const b = new Bag(), glow = new Bag();
  b.cyl(1.5, 1.5, 0.06, '#3a4250', 0, 0.03, 0, 0, 0, 0, 12);
  glow.cyl(1.3, 1.3, 0.02, '#ffc44d', 0, 0.065, 0, 0, 0, 0, 12);
  b.cyl(1.2, 1.2, 0.03, '#2a3140', 0, 0.075, 0, 0, 0, 0, 12);
  b.box(0.1, 0.01, 0.8, '#ffc44d', -0.3, 0.095, 0);
  b.box(0.1, 0.01, 0.8, '#ffc44d', 0.3, 0.095, 0);
  b.box(0.7, 0.01, 0.1, '#ffc44d', 0, 0.095, 0);
  pad.add(b.mesh(), glow.mesh('glow'));

  const drone = group('drone', px, G + 0.75, pz);
  root.add(drone);
  const d = new Bag(), dg = new Bag();
  d.box(0.26, 0.07, 0.26, '#1d222d', 0, 0, 0);
  d.box(0.1, 0.05, 0.12, '#58606e', 0, 0.06, 0);
  rod(d, [-0.2, 0, -0.2], [0.2, 0, 0.2], 0.012, '#aeb8c6');
  rod(d, [0.2, 0, -0.2], [-0.2, 0, 0.2], 0.012, '#aeb8c6');
  dg.box(0.04, 0.03, 0.03, '#ff4d4d', -0.08, 0.0, 0.14);
  dg.box(0.04, 0.03, 0.03, '#4dff7a', 0.08, 0.0, 0.14);
  drone.add(d.mesh(), dg.mesh('glow'));
  const rotors = [];
  for (const [x, z] of [[-0.2, -0.2], [0.2, -0.2], [-0.2, 0.2], [0.2, 0.2]]) {
    const r = new Bag();
    r.cyl(0.11, 0.11, 0.01, '#8a96a8', 0, 0.05, 0, 0, 0, 0, 3);
    r.cyl(0.1, 0.1, 0.012, '#aeb8c6', 0, 0.05, 0, 0, PI / 3, 0, 3);
    const mesh = r.mesh();
    mesh.position.set(x, 0, z);
    drone.add(mesh);
    rotors.push(mesh);
  }
  world.drone = { group: drone, rotors, base: G + 0.75 };
}

// ----- trees, rocks, fence ---------------------------------------------------------------------------------------
function buildScatter(world, root) {
  const r = rng(20261002);
  const b = new Bag();
  // pine trees on the slopes; the north stays open so the skyline is visible
  for (let i = 0; i < 90; i++) {
    const a = r() * PI * 2, d = 36 + r() * 70;
    const x = Math.sin(a) * d, z = Math.cos(a) * d;
    if (z < -0.35 * d && Math.abs(x) < 0.7 * d) continue;
    const y = groundHeight(x, z);
    const s = 0.9 + r() * 0.9;
    const tone = ['#14301f', '#1a3a26', '#10281a'][i % 3];
    b.cyl(0.18 * s, 0.24 * s, 1.4 * s, '#3a2a1c', x, y + 0.7 * s, z, 0, 0, 0, 5);
    b.cone(1.5 * s, 3.0 * s, tone, x, y + 2.3 * s, z, 6);
    b.cone(1.1 * s, 2.4 * s, tone, x, y + 3.9 * s, z, 6);
    b.cone(0.7 * s, 1.8 * s, tone, x, y + 5.2 * s, z, 6);
  }
  // rocks: the big boulder behind the telescope, and a few small ones
  const [bx, bz] = POS.boulder;
  b.ball(1.0, '#3a4252', bx, G + 0.2, bz, 1);
  world.colliders.push({ type: 'circle', x: bx, z: bz, r: 1.4 });
  for (let i = 0; i < 16; i++) {
    const a = r() * PI * 2, d = 12 + r() * 24;
    const x = Math.sin(a) * d, z = Math.cos(a) * d;
    if (Math.hypot(x - POS.telescope[0], z - POS.telescope[1]) < 3 || Math.hypot(x - POS.start[0], z - POS.start[1]) < 4) continue;
    b.ball(0.2 + r() * 0.35, '#4a5262', x, groundHeight(x, z) + 0.05, z, 0);
  }
  // a small lantern on the ground by the van
  b.box(0.2, 0.05, 0.2, '#222', -17, G + 0.03, -9.5);
  b.box(0.2, 0.05, 0.2, '#222', -17, G + 0.34, -9.5);
  const m = b.mesh();
  root.add(m);
  const g = new Bag();
  g.box(0.14, 0.26, 0.14, '#ffc44d', -17, G + 0.18, -9.5);
  root.add(g.mesh('glow'));

  // fence: posts and a rail on the walking boundary
  const f = new Bag();
  const N = 64, rad = WALK_RADIUS - 0.6;
  for (let i = 0; i < N; i++) {
    const a0 = (i / N) * PI * 2, a1 = ((i + 1) / N) * PI * 2;
    const x0 = Math.sin(a0) * rad, z0 = Math.cos(a0) * rad, x1 = Math.sin(a1) * rad, z1 = Math.cos(a1) * rad;
    const y0 = groundHeight(x0, z0), y1 = groundHeight(x1, z1);
    f.box(0.14, 1.2, 0.14, '#5a4630', x0, y0 + 0.6, z0);
    rod(f, [x0, y0 + 0.95, z0], [x1, y1 + 0.95, z1], 0.03, '#7a6244', 4);
  }
  root.add(f.mesh());
}

// ----- Mumbai on the northern horizon ---------------------------------------------------------------------------
function buildSkyline(world, root) {
  const r = rng(1908);
  const body = new Bag(), win = new Bag();
  const beacons = new Bag();
  const warm = ['#ffd38a', '#ffe9b8', '#ffc070', '#9fe8ff'];
  const towers = [];
  for (let row = 0; row < 2; row++) {
    const z0 = row ? -980 : -780;
    for (let x = -460; x < 460;) {
      const w = 12 + r() * 26, depth = 12 + r() * 14;
      const centre = 1 - Math.min(1, Math.abs(x) / 460);
      let h = 24 + r() * 50 + (r() < 0.16 + centre * 0.15 ? 55 + r() * 85 : 0);
      if (row) h *= 0.8;
      const z = z0 + (r() - 0.5) * 50;
      const shade = row ? '#121a2c' : '#0b1220';
      body.box(w, h, depth, shade, x + w / 2, h / 2 - 2, z);
      if (h > 95) beacons.box(2.4, 2.4, 2.4, '#ff3030', x + w / 2, h + 0.5, z);
      const cols = Math.max(1, Math.floor(w / 6)), rows = Math.max(1, Math.floor(h / 9));
      for (let c = 0; c < cols; c++) for (let q = 0; q < rows; q++) {
        if (r() > 0.42) continue;
        win.box(3.6, 4.2, 1, warm[Math.floor(r() * warm.length)], x + 3 + c * 6 + (w - cols * 6) / 2, 4 + q * 9, z + depth / 2 + 0.3);
      }
      towers.push({ x, h });
      x += w + 2 + r() * 8;
    }
  }
  const bodyMesh = body.mesh('glow');                      // silhouettes: unlit and unfogged; recoloured each frame
  bodyMesh.material = new THREE.MeshBasicMaterial({ vertexColors: false, color: 0x0b1220, fog: false });
  const winMesh = win.mesh('glow');
  winMesh.material = new THREE.MeshBasicMaterial({ vertexColors: true, fog: false });
  const beaconMesh = beacons.mesh('glow');
  root.add(bodyMesh, winMesh, beaconMesh);
  // scattered city lights across the plain
  const n = 1400, pos = new Float32Array(n * 3), col = new Float32Array(n * 3);
  const c = new THREE.Color();
  for (let i = 0; i < n; i++) {
    pos.set([(r() - 0.5) * 1100, 1.5 + r() * 3, -430 - r() * 520], i * 3);
    c.set(warm[Math.floor(r() * 4)]);
    c.multiplyScalar(0.4 + r() * 0.4);
    col.set([c.r, c.g, c.b], i * 3);
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.BufferAttribute(pos, 3));
  g.setAttribute('color', new THREE.BufferAttribute(col, 3));
  const lights = new THREE.Points(g, new THREE.PointsMaterial({ vertexColors: true, size: 1.5, sizeAttenuation: false, fog: false }));
  lights.frustumCulled = false;
  root.add(lights);
  world.city = { bodyMesh, winMesh, beaconMesh, lights };
}

// ----- per-frame ------------------------------------------------------------------------------------------------
const tmpColor = new THREE.Color();
function update(world, state, env, seconds, delta, reduced) {
  const dark = world.sky ? world.sky.dark : 1;
  const c = world.city;
  const night = Math.max(0, Math.min(1, dark * 1.15));
  c.winMesh.material.color.setScalar(0.05 + 0.95 * night);
  c.lights.material.color.setScalar(night);
  c.lights.visible = night > 0.02;
  c.beaconMesh.visible = reduced ? true : Math.floor(seconds / 1.1) % 2 === 0;
  c.beaconMesh.material.color.setScalar(0.2 + 0.8 * night);
  // silhouette tone: the haze colour at the horizon, darkened toward the ground colour
  const h = world.look.horizon;
  tmpColor.setRGB(h[0], h[1], h[2], THREE.SRGBColorSpace).multiplyScalar(0.35 + 0.15 * (1 - night));
  c.bodyMesh.material.color.copy(tmpColor);

  const L = world.lights;
  const flick = reduced ? 1 : 1 + 0.05 * Math.sin(seconds * 7.1) * Math.sin(seconds * 2.3 + 1.0);
  L.lamp.intensity = 18 * flick;
  L.lantern.intensity = 7 * (reduced ? 1 : 1 + 0.12 * Math.sin(seconds * 9.0) * Math.sin(seconds * 3.7));

  if (world.robot && !reduced) {
    const r = world.robot;
    r.head.rotation.y = Math.sin(seconds * 0.7) * 0.7;
    r.group.position.x = r.home.x + Math.sin(seconds * 0.25) * 0.5;
    r.group.rotation.y = -0.6 + Math.sin(seconds * 0.25 + 1.5) * 0.15;
  }
  if (world.drone) {
    const d = world.drone;
    for (const rotor of d.rotors) rotor.rotation.y = reduced ? 0 : seconds * 60;
    d.group.position.y = d.base + (reduced ? 0 : Math.sin(seconds * 1.3) * 0.08 + 0.1);
    d.group.rotation.y = reduced ? 0 : Math.sin(seconds * 0.2) * 0.4;
  }
  if (state && world.screen && seconds - world.screen.last > 2) {
    world.screen.last = seconds;
    drawScreen(world, state, seconds);
  }
}
