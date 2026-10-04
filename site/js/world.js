// The observatory world, built as a 2.5D scene: the terrain mesh carries a painted ground texture and the clearing, buildings,
// van, rocks, trees and plants are detailed 2D artwork placed at real depths (scenery.js). The distant Mumbai skyline is kept as
// far-away silhouettes with lit windows. Axes: +X east, +Y up, +Z south (north is -Z). Colliders are plain data for controls.js.
import * as THREE from '../vendor/three/three.module.js';
import { Bag } from './geom.js';
import { buildTerrain, groundHeight } from './terrain.js';
import { buildScenery } from './scenery.js';

export const POS = {
  start: [0, 10], telescope: [-2.5, -1], shed: [9, -1], rover: [4.8, 3.2], van: [-11, -5], pad: [17, 8], boulder: [-4.5, -4.5],
};

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

export async function buildWorld(scene, site, env) {
  const world = { colliders: [], pickables: [] };
  const root = new THREE.Group();
  root.name = 'world';
  scene.add(root);

  world.terrain = buildTerrain(env.greenery);
  root.add(world.terrain);
  buildTelescopeProxy(world, root, site);
  buildSkyline(world, root);
  await buildScenery(root, world, POS);

  world.update = (state, env2, seconds, delta, reduced, camera) => update(world, seconds, reduced, camera);
  return world;
}

// The telescope itself is a painted sprite. This invisible volume is what the pointer picks, and the telescope object
// keeps the aim API of the earlier 3D instrument so the nightly target logic is unchanged.
function buildTelescopeProxy(world, root) {
  const [tx, tz] = POS.telescope;
  const proxy = new THREE.Mesh(new THREE.SphereGeometry(2.1, 10, 8), new THREE.MeshBasicMaterial({ visible: false }));
  proxy.position.set(tx, groundHeight(tx, tz) + 2.3, tz);
  proxy.name = 'telescope';
  root.add(proxy);
  world.telescope = { proxy, ready: false, aim() { this.ready = true; } };
  world.pickables = [proxy];
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
      h *= row ? 0.28 : 0.32;
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
function update(world, seconds, reduced, camera) {
  const dark = world.sky ? world.sky.dark : 1;
  const c = world.city;
  const night = Math.max(0, Math.min(1, dark * 1.15));
  c.winMesh.material.color.setScalar(0.05 + 0.95 * night);
  c.lights.material.color.setScalar(night);
  c.lights.visible = night > 0.02;
  c.beaconMesh.visible = reduced ? true : Math.floor(seconds / 1.1) % 2 === 0;
  c.beaconMesh.material.color.setScalar(0.2 + 0.8 * night);
  const h = world.look.horizon;
  tmpColor.setRGB(h[0], h[1], h[2], THREE.SRGBColorSpace).multiplyScalar(0.35 + 0.15 * (1 - night));
  c.bodyMesh.material.color.copy(tmpColor);
  if (world.scenery) world.scenery.update(camera, world.look, dark, seconds, reduced);
}
