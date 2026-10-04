// 2.5D scenery: detailed 2D artwork placed at real depths in the three.js scene.
// Every object is an alpha-tested textured quad on a ground anchor. Quads face the camera around the vertical axis (some are
// limited to a few tens of degrees so a building keeps a plausible orientation), the depth buffer sorts and occludes
// them, perspective scales them, and walking past them produces real parallax. The painted ridge rings are cylinders of
// ridge silhouettes at three distances. Nothing here draws celestial objects; the sky stays the computed Mumbai sky.
import * as THREE from '../vendor/three/three.module.js';
import { groundHeight, pathMask } from './terrain.js';

const DIR = 'data/scenery/';
const PI = Math.PI;

// Sprite definitions. `mpp` is metres per source pixel, `ax` the horizontal anchor (0..1) of the ground contact point,
// `tone` is the colour multiplier at night/day (the artwork is painted for night; the day value lifts it).
const DEFS = {
  telescope: { file: 'telescope.webp', mpp: 0.0138, ax: 0.665, night: 1.25, day: 2.0, sink: 0.02 },
  workshop: { file: 'workshop.webp', mpp: 0.0158, ax: 0.5, night: 1.0, day: 1.9, sink: 0.04 },
  rover: { file: 'rover.webp', mpp: 0.0125, ax: 0.5, night: 1.05, day: 1.8, sink: 0.08 },
  van: { file: 'van.webp', mpp: 0.0235, ax: 0.5, night: 1.45, day: 2.1, sink: 0.07 },
  tree_a: { file: 'tree_a.webp', mpp: 0.045, ax: 0.5, night: 1.5, day: 2.2, sink: 0.4 },
  tree_b: { file: 'tree_b.webp', mpp: 0.045, ax: 0.5, night: 1.5, day: 2.2, sink: 0.4 },
  lantern: { file: 'lantern.webp', mpp: 0.022, ax: 0.5, night: 1.0, day: 1.4, sink: 0.02 },
  tree_c: { file: 'tree_c.webp', mpp: 0.045, ax: 0.5, night: 1.5, day: 2.2, sink: 0.4 },
  rock_a: { file: 'rock_a.webp', mpp: 0.017, ax: 0.5, night: 0.6, day: 1.5, sink: 0.12 },
  rock_b: { file: 'rock_b.webp', mpp: 0.017, ax: 0.5, night: 0.6, day: 1.5, sink: 0.12 },
  rock_c: { file: 'rock_c.webp', mpp: 0.017, ax: 0.5, night: 0.6, day: 1.5, sink: 0.12 },
};
// Foliage cells of data/foliage-atlas.webp (2 by 2).
const FOLIAGE = { file: 'data/foliage-atlas.webp', night: 0.72, day: 1.55 };
const RIDGES = [
  { file: 'ridge_far.webp', radius: 1100, mpp: 0.66, base: -6, night: 1.1 },
  { file: 'ridge_mid.webp', radius: 640, mpp: 0.36, base: -5, night: 0.8 },
  { file: 'ridge_near.webp', radius: 340, mpp: 0.2, base: -4, night: 0.55 },
];

function loadImage(url) {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = () => reject(new Error(`could not load ${url}`));
    img.src = url;
  });
}

// A coarse alpha mask lets the planet guides test occlusion against the painted silhouettes, not the whole quad.
function alphaMask(img, cols, rows) {
  const canvas = document.createElement('canvas');
  canvas.width = cols; canvas.height = rows;
  const c = canvas.getContext('2d', { willReadFrequently: true });
  c.drawImage(img, 0, 0, cols, rows);
  const px = c.getImageData(0, 0, cols, rows).data;
  const data = new Uint8Array(cols * rows);
  for (let i = 0; i < data.length; i++) data[i] = px[i * 4 + 3] > 110 ? 1 : 0;
  return { cols, rows, data };
}
const maskAt = (m, u, v) => {            // u,v in 0..1, v = 0 at the bottom of the image
  if (u < 0 || u >= 1 || v < 0 || v >= 1) return false;
  return m.data[Math.floor((1 - v) * m.rows) * m.cols + Math.floor(u * m.cols)] === 1;
};

function makeTexture(img, crisp = false) {
  const t = new THREE.Texture(img);
  if (crisp) t.magFilter = THREE.NearestFilter;            // keep the pixel-art look when a sprite is magnified
  t.colorSpace = THREE.SRGBColorSpace;
  t.anisotropy = 4;
  t.generateMipmaps = true;
  t.minFilter = THREE.LinearMipmapLinearFilter;
  t.needsUpdate = true;
  return t;
}

function spriteMaterial(texture) {
  return new THREE.MeshBasicMaterial({ map: texture, alphaTest: 0.4, side: THREE.DoubleSide, alphaToCoverage: true });
}

function glowTexture() {
  const c = document.createElement('canvas');
  c.width = c.height = 64;
  const g = c.getContext('2d');
  const grad = g.createRadialGradient(32, 32, 0, 32, 32, 32);
  grad.addColorStop(0, 'rgba(255,255,255,1)');
  grad.addColorStop(0.25, 'rgba(255,255,255,0.45)');
  grad.addColorStop(1, 'rgba(255,255,255,0)');
  g.fillStyle = grad; g.fillRect(0, 0, 64, 64);
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  return t;
}

// Deterministic placement.
function rng(seed) {
  let s = seed >>> 0;
  return () => { s = (Math.imul(s, 1664525) + 1013904223) >>> 0; return s / 4294967296; };
}

export async function buildScenery(root, world, POS) {
  const names = Object.keys(DEFS);
  const [images, atlasImg, ridgeImgs, groundImg] = await Promise.all([
    Promise.all(names.map((n) => loadImage(DIR + DEFS[n].file))),
    loadImage(FOLIAGE.file),
    Promise.all(RIDGES.map((r) => loadImage(DIR + r.file))),
    loadImage(DIR + 'ground.webp'),
  ]);

  // ---- ground texture for the existing terrain mesh -------------------------------------------------------------
  const groundTex = new THREE.Texture(groundImg);
  groundTex.colorSpace = THREE.SRGBColorSpace;
  groundTex.wrapS = groundTex.wrapT = THREE.RepeatWrapping;
  groundTex.anisotropy = 8;
  groundTex.needsUpdate = true;
  world.terrain.material.map = groundTex;
  world.terrain.material.emissiveMap = groundTex;          // keeps the meadow readable by starlight; strength is set per frame
  world.terrain.material.needsUpdate = true;

  // ---- sprite sets (one InstancedMesh per image) ----------------------------------------------------------------
  const sets = [];
  const byName = {};
  function makeSet(name, texture, w, h, ax, uv, tone, mask, capacity) {
    const geo = new THREE.PlaneGeometry(1, 1);
    geo.translate(0.5 - ax, 0.5, 0);
    if (uv) {
      const a = geo.attributes.uv;
      for (let i = 0; i < a.count; i++) a.setXY(i, uv[0] + a.getX(i) * uv[2], uv[1] + a.getY(i) * uv[3]);
    }
    const material = spriteMaterial(texture);
    const mesh = new THREE.InstancedMesh(geo, material, capacity);
    mesh.frustumCulled = false;
    mesh.name = `sprite-${name}`;
    mesh.count = 0;
    const set = { name, mesh, material, w, h, ax, tone, mask, items: [] };
    sets.push(set);
    root.add(mesh);
    return set;
  }
  names.forEach((n, i) => {
    const d = DEFS[n], img = images[i];
    byName[n] = makeSet(n, makeTexture(img, !n.startsWith('rock')), img.width * d.mpp, img.height * d.mpp, d.ax, null, { night: d.night, day: d.day },
      alphaMask(img, Math.min(img.width, 96), Math.round(Math.min(img.width, 96) * img.height / img.width)), 8 + (n.startsWith('tree') ? 140 : n.startsWith('rock') ? 40 : 0));
  });
  const atlasTex = makeTexture(atlasImg);
  const atlasMask = alphaMask(atlasImg, 256, 256);
  const foliage = [];
  for (let v = 0; v < 4; v++) {
    const col = v % 2, row = Math.floor(v / 2);
    const uv = [col * 0.5 + 0.008, (1 - row) * 0.5 + 0.008, 0.484, 0.484];
    // each cell gets its own sub-mask so occlusion matches what is drawn
    const sub = { cols: 128, rows: 128, data: new Uint8Array(128 * 128) };
    for (let y = 0; y < 128; y++) for (let x = 0; x < 128; x++) {
      const sx = Math.floor((uv[0] + (x / 128) * uv[2]) * 256), sy = Math.floor((1 - (uv[1] + ((127 - y) / 128) * uv[3])) * 256);
      sub.data[y * 128 + x] = atlasMask.data[Math.min(255, sy) * 256 + Math.min(255, sx)];
    }
    foliage.push(makeSet(`foliage${v}`, atlasTex, 1, 1, 0.5, uv, { night: FOLIAGE.night, day: FOLIAGE.day }, sub, 1100));
  }

  // add(set, x, z, scale, options): all sprites stand on the terrain height at (x, z)
  function add(set, x, z, scale = 1, o = {}) {
    if (set.items.length >= set.mesh.instanceMatrix.count) return null;
    const item = {
      set, x, z, y: groundHeight(x, z) - set.h * scale * (o.sink ?? DEFS[set.name]?.sink ?? 0.03), s: scale, flip: o.flip ? -1 : 1,
      base: o.yaw ?? 0, limit: o.limit ?? PI, rot: o.yaw ?? 0, w: set.w * scale, h: set.h * scale,
    };
    set.items.push(item);
    return item;
  }
  const S = (n) => byName[n];
  const rand = rng(2026);
  const rr = (a, b) => a + (b - a) * rand();

  // The compact clearing, composed like the reference.
  const [tx, tz] = POS.telescope;
  add(S('telescope'), tx, tz, 1);
  const toStart = (x, z) => Math.atan2(POS.start[0] - x, POS.start[1] - z);
  const shed = add(S('workshop'), POS.shed[0], POS.shed[1], 1, { yaw: toStart(POS.shed[0], POS.shed[1]), limit: 0.95 });
  add(S('rock_a'), tx - 1.7, tz - 1.0, 1.1);                    // authored boulder behind the telescope
  add(S('rover'), POS.rover[0], POS.rover[1], 1);
  add(S('van'), POS.van[0] - 1.5, POS.van[1] + 0.5, 1, { yaw: toStart(POS.van[0], POS.van[1]), limit: 1.1 });

  // trees: canopies cut from the reference, stacked in overlapping groups so their cut edges hide inside each other; the
  // dark lower mass fades into the ground. A few large groups frame the clearing, the rest ring the boundary (north stays open).
  const crowns = ['tree_a', 'tree_b', 'tree_c'];
  function grove(x, z, size, n = 4) {
    for (let i = 0; i < n; i++) {
      const dx = (rand() - 0.5) * 3.2 * size, dz = (rand() - 0.5) * 2.2 * size;
      add(S(crowns[Math.floor(rand() * 3)]), x + dx, z + dz, size * rr(0.85, 1.35), { flip: rand() < 0.5, sink: 0.32 + rand() * 0.2 });
    }
  }
  const treeSpots = [[-17, -13], [-23, -6], [-21, -17], [14, -13], [21, -9], [17, -19], [-20, 6], [22, 4], [-27, -1], [26, -3], [-14, 17], [16, 16]];
  treeSpots.forEach(([x, z]) => grove(x, z, 1.3, 5));
  for (let i = 0; i < 22; i++) {
    const a = rand() * PI * 2, d = 34 + rand() * 14, x = Math.sin(a) * d, z = Math.cos(a) * d;
    if (z < -0.3 * d && Math.abs(x) < 0.55 * d) continue;
    grove(x, z, rr(1.4, 1.9), 4);
    for (let k = 0; k < 3; k++) add(foliage[(i + k) % 4], x + (rand() - 0.5) * 7, z + (rand() - 0.5) * 5, rr(3.2, 6), { flip: rand() < 0.5, sink: 0.05 });
  }
  world.colliders.push({ type: 'circle', x: tx, z: tz, r: 1.3 });
  world.colliders.push({ type: 'circle', x: tx - 1.9, z: tz - 0.9, r: 1.5 });                       // the rock under the telescope
  world.colliders.push({ type: 'box', x: POS.shed[0], z: POS.shed[1], yaw: shed.base, lx: 0, lz: -0.9, hw: 3.4, hd: 0.9 });
  world.colliders.push({ type: 'circle', x: POS.rover[0], z: POS.rover[1], r: 0.95 });
  world.colliders.push({ type: 'circle', x: POS.van[0] - 3.3, z: POS.van[1] - 0.2, r: 1.9 });
  world.colliders.push({ type: 'circle', x: POS.van[0] - 0.4, z: POS.van[1] - 0.3, r: 1.9 });
  for (const [x, z] of treeSpots) world.colliders.push({ type: 'circle', x, z, r: 0.6 });

  // rocks (outcrops frame the terrace; small ones bed into the foliage)
  const outcrops = [[-5.5, -5, 1.4], [-8, -3, 1.0], [-7, 3, 0.8], [3, -6, 1.3], [-14, -8, 1.8], [16, -8, 1.8], [-11, 12, 1.3], [10, 13, 1.1]];
  outcrops.forEach(([x, z, s], i) => {
    add(S(['rock_a', 'rock_b', 'rock_c'][i % 3]), x, z, s, { flip: i % 2 === 1 });
    world.colliders.push({ type: 'circle', x, z, r: s * 1.3 });
  });

  for (let i = 0; i < 6; i++) add(foliage[i % 4], POS.van[0] - 5.2 + (rand() - 0.5) * 2, POS.van[1] + (rand() - 0.5) * 3, 2 + rand() * 1.2, { flip: rand() < 0.5, sink: 0.04 });   // hides the van's cut edge
  // path lanterns (amber, as in the reference)
  const lanternSpots = [[-3.8, 6], [3.5, 7], [-7, -1], [5.6, 2.8], [11, -4], [-15.5, -2.5]];
  for (const [x, z] of lanternSpots) add(S('lantern'), x, z, 1);

  // foliage: dense around the rock beds and the clearing edge, never on the paths
  const spots = Object.values(POS);
  const clear = (x, z, margin = 0) => {
    if (spots.some(([a, b]) => Math.hypot(x - a, z - b) < 3.3 + margin)) return true;
    if (x > 4 && x < 14 && z > -6 && z < 5) return true;
    if (z > -2 && z < 12 && Math.abs(x + (10 - z) * 0.23) < 1.5 + margin) return true;
    if (z > 1 && z < 12 && Math.abs(x - (10 - z) * 0.6) < 1.8 + margin) return true;
    return false;
  };
  let placed = 0;
  const tryFoliage = (x, z, h) => {
    if (clear(x, z, 0.2)) return;
    const set = foliage[placed++ % 4];
    add(set, x, z, h, { flip: rand() < 0.5, sink: 0.02 });
  };
  for (const [cx, cz] of [[-5.5, 7.5], [4.8, 8], [-8, 2], [3.8, -5], [14, 3], [-3.5, -7], [8, 8.5], [-9.5, 9]]) {
    for (let i = 0; i < 12; i++) tryFoliage(cx + (rand() - 0.5) * 4.4, cz + (rand() - 0.5) * 4.4, 0.5 + rand() * 0.85);
  }
  for (let i = 0; i < 640; i++) {
    const x = (rand() - 0.5) * 82, z = (rand() - 0.5) * 72, close = Math.hypot(x, z) < 22;
    tryFoliage(x, z, close ? 0.7 + rand() * 1.3 : 1.6 + rand() * 2.6);
  }
  for (let i = 0; i < 520; i++) {                       // low grass tufts everywhere except the worn paths, so the ground reads as meadow
    const x = (rand() - 0.5) * 60, z = (rand() - 0.5) * 56;
    if (pathMask(x, z) > 0.35 || Math.hypot(x - tx, z - tz) < 2.2) continue;
    add(foliage[i % 2 ? 1 : 3], x, z, 0.28 + rand() * 0.34, { flip: rand() < 0.5, sink: 0.03 });
  }
  for (const [x, z, s] of outcrops) for (let i = 0; i < 4; i++) {
    const a = rand() * PI * 2, d = s * (1.7 + rand() * 1.2);
    tryFoliage(x + Math.cos(a) * d, z + Math.sin(a) * d, 0.6 + rand() * 0.9);
  }

  // ---- contact shadows (flat soft blobs on the ground) -----------------------------------------------------------
  const blobTex = glowTexture();
  const shadowMat = new THREE.MeshBasicMaterial({ map: blobTex, color: 0x000000, transparent: true, opacity: 0.6, depthWrite: false, polygonOffset: true, polygonOffsetFactor: -2, polygonOffsetUnits: -2 });
  const shadowItems = [];
  for (const set of sets) {
    if (set.name.startsWith('foliage') || set.name.startsWith('tree')) continue;
    for (const it of set.items) shadowItems.push(it);
  }
  const shadows = new THREE.InstancedMesh(new THREE.PlaneGeometry(1, 1).rotateX(-PI / 2), shadowMat, shadowItems.length);
  shadows.frustumCulled = false;
  const m4 = new THREE.Matrix4(), v3 = new THREE.Vector3(), q0 = new THREE.Quaternion(), sc = new THREE.Vector3();
  shadowItems.forEach((it, i) => {
    const wide = it.set.name === 'workshop' ? 0.9 : it.set.name === 'van' ? 0.8 : it.set.name === 'telescope' ? 0.85 : 1.3;
    m4.compose(v3.set(it.x, groundHeight(it.x, it.z) + 0.04, it.z), q0, sc.set(it.w * wide, 1, it.w * wide * 0.4));
    shadows.setMatrixAt(i, m4);
  });
  root.add(shadows);

  // ---- warm light spill and halos (additive, night only) ---------------------------------------------------------
  const glowMat = (hex) => new THREE.MeshBasicMaterial({ map: blobTex, color: hex, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, fog: false, opacity: 0.5 });
  const halos = [];
  function halo(item, px, py, size, hex, opacity, flicker = 0) {
    // px, py: pixel position in the source image (origin top-left) of a baked light
    const set = item.set, img = images[names.indexOf(set.name)];
    const m = new THREE.Mesh(new THREE.PlaneGeometry(1, 1), glowMat(hex));
    m.renderOrder = 5;
    halos.push({ item, m, lx: (px / img.width - set.ax) * item.w, ly: (1 - py / img.height) * item.h, size, opacity, flicker });
    root.add(m);
  }
  const sh = shed, vanItem = byName.van.items[0];
  halo(sh, 160, 178, 5.5, 0xffb15e, 0.55, 0.06);                    // 3D printer lamp (pixel positions in the workshop image)
  halo(sh, 335, 122, 4.2, 0x35cfe6, 0.28);                          // cyan strip light
  halo(sh, 470, 345, 2.6, 0xffa84a, 0.5, 0.12);                     // bench lantern
  halo(sh, 405, 200, 4.5, 0x3fc7e8, 0.16);                          // blueprint screen
  halo(vanItem, 31, 112, 3.0, 0xffb25a, 0.5, 0.04);
  halo(vanItem, 105, 107, 3.0, 0xffb25a, 0.4, 0.04);
  halo(vanItem, 225, 120, 2.6, 0xffbb66, 0.4, 0.04);
  for (const it of byName.lantern.items) halo(it, 10, 9, 2.4, 0xffb65e, 0.6, 0.1);
  halo(byName.rover.items[0], 75, 55, 1.8, 0x7fe3ff, 0.2);

  // warm pools of lamp light on the ground (flat additive decals) ------------------------------------------------------
  const pools = [];
  for (const [x, z, size, hex, op] of [[POS.shed[0] - 2.2, POS.shed[1] + 3.6, 9, 0xff9a40, 0.5], [POS.rover[0], POS.rover[1], 4.5, 0xff9a40, 0.3],
    [POS.van[0] - 2.5, POS.van[1] + 2.4, 6, 0xffaa55, 0.32], [-3.8, 6, 3.4, 0xffb65e, 0.35], [3.5, 7, 3.4, 0xffb65e, 0.35], [-7, -1, 3.2, 0xffb65e, 0.3], [11, -4, 3.2, 0xffb65e, 0.3],
    [tx, tz + 1.2, 6, 0x4aa6c4, 0.12]]) {
    const m = new THREE.Mesh(new THREE.PlaneGeometry(1, 1).rotateX(-PI / 2), glowMat(hex));
    m.position.set(x, groundHeight(x, z) + 0.06, z);
    m.scale.set(size, 1, size * 0.8);
    m.renderOrder = 4;
    root.add(m);
    pools.push({ m, op });
  }

  // fireflies drifting over the meadow at night (decorative, low and warm so they cannot be mistaken for stars)
  const FLY = 44, flyBase = new Float32Array(FLY * 3), flyPos = new Float32Array(FLY * 3);
  for (let i = 0; i < FLY; i++) {
    const a = rand() * PI * 2, d = 3 + rand() * 20, x = Math.sin(a) * d, z = Math.cos(a) * d;
    flyBase.set([x, groundHeight(x, z) + 0.5 + rand() * 1.9, z], i * 3);
  }
  const flyGeo = new THREE.BufferGeometry();
  flyGeo.setAttribute('position', new THREE.BufferAttribute(flyPos, 3));
  const flyMat = new THREE.PointsMaterial({ map: blobTex, color: 0xcfff7a, size: 7, sizeAttenuation: false, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, opacity: 0.8, fog: false });
  const flies = new THREE.Points(flyGeo, flyMat);
  flies.frustumCulled = false;
  flies.renderOrder = 6;
  root.add(flies);

  // ---- distant painted ridges: three rings at three distances (real parallax when the visitor walks) --------------
  const rings = RIDGES.map((def, i) => {
    const img = ridgeImgs[i];
    const N = 256, H = img.height * def.mpp;
    const pos = [], uv = [], idx = [];
    for (let k = 0; k <= N; k++) {
      const a = (k / N) * PI * 2, x = Math.sin(a) * def.radius, z = -Math.cos(a) * def.radius;
      pos.push(x, def.base, z, x, def.base + H, z);
      uv.push(k / N, 0, k / N, 1);
      if (k < N) { const j = k * 2; idx.push(j, j + 1, j + 2, j + 1, j + 3, j + 2); }
    }
    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
    geo.setAttribute('uv', new THREE.Float32BufferAttribute(uv, 2));
    geo.setIndex(idx);
    const tex = makeTexture(img);
    tex.wrapS = THREE.RepeatWrapping;
    const mat = new THREE.MeshBasicMaterial({ map: tex, alphaTest: 0.4, side: THREE.DoubleSide, fog: false, alphaToCoverage: true });
    const mesh = new THREE.Mesh(geo, mat);
    mesh.frustumCulled = false;
    mesh.name = `ridge-${i}`;
    mesh.renderOrder = -1;
    root.add(mesh);
    return { def, mesh, mat, H, mask: alphaMask(img, 1024, 80) };
  });

  // ---- a far plain joins the hill to the ridges (dark, fogged, no detail needed) ----------------------------------
  {
    const N = 96, pos = [], idx = [];
    for (let k = 0; k <= N; k++) {
      const a = (k / N) * PI * 2, s = Math.sin(a), c = Math.cos(a);
      pos.push(s * 96, 0.2, c * 96, s * 1500, -1.2, c * 1500);
      if (k < N) { const j = k * 2; idx.push(j, j + 2, j + 1, j + 1, j + 2, j + 3); }
    }
    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
    geo.setIndex(idx);
    const plain = new THREE.Mesh(geo, new THREE.MeshBasicMaterial({ color: 0x1b2a2c, side: THREE.DoubleSide }));
    plain.name = 'far-plain';
    plain.frustumCulled = false;
    root.add(plain);
    world.plain = plain;
  }

  // ---- per-frame --------------------------------------------------------------------------------------------------
  const tint = new THREE.Color();
  const wrap = (a) => ((a + PI) % (2 * PI) + 2 * PI) % (2 * PI) - PI;
  function writeMatrix(set, i, it) {
    const c = Math.cos(it.rot), s = Math.sin(it.rot), sx = it.w * it.flip, sy = it.h;
    const e = set.mesh.instanceMatrix.array, o = i * 16;
    e[o] = c * sx; e[o + 1] = 0; e[o + 2] = -s * sx; e[o + 3] = 0;
    e[o + 4] = 0; e[o + 5] = sy; e[o + 6] = 0; e[o + 7] = 0;
    e[o + 8] = s; e[o + 9] = 0; e[o + 10] = c; e[o + 11] = 0;
    e[o + 12] = it.x; e[o + 13] = it.y; e[o + 14] = it.z; e[o + 15] = 1;
  }

  const scenery = {
    sets, rings, halos, items: sets.flatMap((s) => s.items), byName,
    update(camera, look, dark, seconds, reduced) {
      const cx = camera.position.x, cz = camera.position.z;
      const day = 1 - Math.min(1, Math.max(0, dark));           // 0 at night, 1 in full daylight
      for (const set of sets) {
        set.mesh.count = set.items.length;
        for (let i = 0; i < set.items.length; i++) {
          const it = set.items[i];
          const want = Math.atan2(cx - it.x, cz - it.z);
          it.rot = it.limit >= PI ? want : it.base + Math.max(-it.limit, Math.min(it.limit, wrap(want - it.base)));
          writeMatrix(set, i, it);
        }
        set.mesh.instanceMatrix.needsUpdate = true;
        const k = set.tone.night + (set.tone.day - set.tone.night) * day;
        set.material.color.setRGB(k, k, k * 1.02);
      }
      shadowMat.opacity = 0.62 - 0.32 * day;
      flies.visible = day < 0.6;
      flyMat.opacity = 0.85 * (1 - day / 0.6);
      for (let i = 0; i < FLY; i++) {
        const t = reduced ? 0 : seconds * 0.35 + i * 7.1;
        flyPos[i * 3] = flyBase[i * 3] + Math.sin(t * 1.3 + i) * 0.9;
        flyPos[i * 3 + 1] = flyBase[i * 3 + 1] + Math.sin(t * 2.1 + i * 3) * 0.3;
        flyPos[i * 3 + 2] = flyBase[i * 3 + 2] + Math.cos(t * 1.1 + i * 2) * 0.9;
      }
      flyGeo.attributes.position.needsUpdate = true;
      for (const p of pools) { p.m.material.opacity = p.op * (1 - day) * (reduced ? 1 : 1 + 0.04 * Math.sin(seconds * 6.1 + p.m.position.x)); p.m.visible = p.m.material.opacity > 0.01; }
      world.terrain.material.emissive.setRGB(0.02, 0.034, 0.036).multiplyScalar(1 - day);
      const h = look.horizon;
      for (const r of rings) {
        // ridges take the haze colour of the horizon: pale and cool far away, darker nearby
        const k = r.def.night + (0.9 - r.def.night) * day * 0.55;
        tint.setRGB(h[0], h[1], h[2], THREE.SRGBColorSpace).multiplyScalar(k * 1.35);
        r.mat.color.copy(tint);
      }
      world.plain.material.color.setRGB(h[0] * 0.24 + 0.012, h[1] * 0.27 + 0.02, h[2] * 0.24 + 0.02);
      for (const g of halos) {
        const it = g.item, c = Math.cos(it.rot), s = Math.sin(it.rot);
        const lx = g.lx * it.flip;
        g.m.position.set(it.x + lx * c + 0.12 * s, it.y + g.ly, it.z - lx * s + 0.12 * c);
        g.m.rotation.y = it.rot;
        g.m.scale.setScalar(g.size);
        const fl = reduced || !g.flicker ? 1 : 1 + g.flicker * Math.sin(seconds * 7.3 + g.lx) * Math.sin(seconds * 2.9 + g.ly);
        g.m.material.opacity = g.opacity * (1 - day) * fl;
        g.m.visible = g.m.material.opacity > 0.01;
      }
    },
    // The nearest painted sprite along a finite ray (for tests and depth-order checks): { name, t } or null.
    frontHit(origin, dir) {
      let best = null;
      for (const set of sets) {
        for (const it of set.items) {
          const c = Math.cos(it.rot), s = Math.sin(it.rot);
          const px = origin.x - it.x, pz = origin.z - it.z;
          const oxl = px * c - pz * s, ozl = px * s + pz * c;
          const dxl = dir.x * c - dir.z * s, dzl = dir.x * s + dir.z * c;
          if (Math.abs(dzl) < 1e-6) continue;
          const t = -ozl / dzl;
          if (t <= 0 || (best && t >= best.t)) continue;
          const xl = oxl + dxl * t, yl = origin.y - it.y + dir.y * t;
          if (yl < 0 || yl > it.h) continue;
          if (maskAt(it.set.mask, (xl * it.flip) / it.w + it.set.ax, yl / it.h)) best = { name: it.set.name, t };
        }
      }
      return best;
    },
    // True when a ray from the camera toward a direction at infinity (a planet) meets painted artwork first.
    blocked(origin, dir) {
      for (const r of rings) {
        // cylinder |xz - 0| = R along the ray; origin lies inside it
        const ox = origin.x, oz = origin.z, dx = dir.x, dz = dir.z;
        const a = dx * dx + dz * dz;
        if (a < 1e-9) continue;
        const b = 2 * (ox * dx + oz * dz), c = ox * ox + oz * oz - r.def.radius * r.def.radius;
        const disc = b * b - 4 * a * c;
        if (disc < 0) continue;
        const t = (-b + Math.sqrt(disc)) / (2 * a);
        if (t <= 0) continue;
        const x = ox + dx * t, z = oz + dz * t, y = origin.y + dir.y * t;
        let u = Math.atan2(x, -z) / (2 * PI);
        if (u < 0) u += 1;
        if (maskAt(r.mask, u, (y - r.def.base) / r.H)) return true;
      }
      for (const set of sets) {
        for (const it of set.items) {
          const c = Math.cos(it.rot), s = Math.sin(it.rot);
          const px = origin.x - it.x, pz = origin.z - it.z;
          const oxl = px * c - pz * s, ozl = px * s + pz * c;            // origin in the sprite frame
          const dxl = dir.x * c - dir.z * s, dzl = dir.x * s + dir.z * c;
          if (Math.abs(dzl) < 1e-6) continue;
          const t = -ozl / dzl;
          if (t <= 0) continue;
          const xl = oxl + dxl * t, yl = origin.y - it.y + dir.y * t;
          if (yl < 0 || yl > it.h) continue;
          const u = (xl * it.flip) / it.w + it.set.ax;
          if (maskAt(it.set.mask, u, yl / it.h)) return true;
        }
      }
      return false;
    },
  };
  world.scenery = scenery;
  return scenery;
}
