// The hill and the plain around it, the ridges, and the ground detail that makes the places readable: clearings as
// ground-hugging discs and dirt paths as ribbons. -Z is north. groundHeight() is the single source of truth for the
// avatar, the props and the plants.
import * as THREE from '../vendor/three/three.module.js';
import { CROWN_RADIUS, FAR, HILL_TOP, LOCATIONS, PATHS, WALK_RADIUS, MAIN_PATH, WEST_PATH, EAST_PATH, ROBOTICS_LOOP, siteMask } from './layout.js';

export { CROWN_RADIUS, FAR, HILL_TOP, WALK_RADIUS };

const smooth = (a, b, x) => {
  const t = Math.min(1, Math.max(0, (x - a) / (b - a)));
  return t * t * (3 - 2 * t);
};

// gentle swells between the places (about +-1.3 m); the places themselves are levelled by siteMask
function rolling(x, z) {
  return (Math.sin(x * 0.11 + 1.3) * Math.cos(z * 0.09) + 0.7 * Math.sin((x - z) * 0.17 + 0.5) + 0.5 * Math.cos(x * 0.05 - z * 0.07 + 2)) * 0.55;
}

export function groundHeight(x, z) {
  const r = Math.hypot(x, z);
  let h = HILL_TOP * (1 - smooth(CROWN_RADIUS, 130, r));
  h += rolling(x, z) * (1 - siteMask(x, z)) * (1 - smooth(70, 140, r));
  // slow swells on the slopes and the plain (kept small so the crown stays calm)
  const swell = Math.sin(x * 0.045 + 1.3) * Math.cos(z * 0.038) + 0.6 * Math.sin((x - z) * 0.09);
  h += swell * 1.1 * smooth(CROWN_RADIUS + 10, 130, r);
  // ridges to the east, south and west; the north is open plain
  if (r > 260) {
    const north = smooth(0.05, 0.55, -z / r);
    const ang = Math.atan2(x, z);
    const ridge = 0.5 + 0.5 * Math.sin(ang * 5.0 + 0.7) * Math.cos(ang * 2.0 + 2.1) + 0.25 * Math.sin(ang * 13.0);
    const band = smooth(260, 620, r) * (1 - smooth(1100, 2200, r) * 0.6);
    h += Math.max(0, ridge) * 120 * band * (1 - north);
  }
  return h;
}

export function buildTerrain(greenery = 0.7) {
  const radii = [];
  for (let r = 0; r <= 78; r += 3) radii.push(r);
  for (let r = 85; r <= 130; r += 7) radii.push(r);
  for (let r = 155; r <= 800; r += 25) radii.push(r);
  for (let r = 900; r <= FAR; r += 100) radii.push(r);
  const SEG = 128;
  const positions = [], colors = [], index = [];
  const lush = new THREE.Color('#3f7a45'), dry = new THREE.Color('#8a8a4a');
  const rock = new THREE.Color('#566178'), far = new THREE.Color('#2f4f3a'), tint = new THREE.Color();
  const grass = lush.clone().lerp(dry, 1 - greenery);
  const col = new THREE.Color();

  for (let ri = 0; ri < radii.length; ri++) {
    const r = radii[ri];
    for (let s = 0; s < SEG; s++) {
      const a = (s / SEG) * Math.PI * 2;
      const x = Math.sin(a) * r, z = Math.cos(a) * r;
      const y = groundHeight(x, z);
      positions.push(x, y, z);
      const crown = 1 - smooth(CROWN_RADIUS, 90, r);
      col.copy(grass).multiplyScalar(0.8 + 0.25 * Math.sin(x * 0.7) * Math.cos(z * 0.9) + 0.1 * crown);
      col.lerp(far, smooth(90, 500, r) * 0.75);
      col.lerp(rock, smooth(8, 90, y - 3) * smooth(300, 700, r) * 0.7);
      for (const l of LOCATIONS) {                                   // a faint clearing tint under each place
        const k = (1 - smooth(l.r * 0.7, l.r * 1.3, Math.hypot(x - l.x, z - l.z))) * 0.55;
        if (k > 0) col.lerp(tint.set(l.ground), k);
      }
      colors.push(col.r, col.g, col.b);
    }
  }
  for (let ri = 0; ri < radii.length - 1; ri++) {
    for (let s = 0; s < SEG; s++) {
      const a = ri * SEG + s, b = ri * SEG + ((s + 1) % SEG);
      const c2 = (ri + 1) * SEG + s, d = (ri + 1) * SEG + ((s + 1) % SEG);
      index.push(a, c2, b, b, c2, d);
    }
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));
  g.setAttribute('color', new THREE.Float32BufferAttribute(colors, 3));
  g.setIndex(index);
  g.computeVertexNormals();
  const mesh = new THREE.Mesh(g, new THREE.MeshLambertMaterial({ vertexColors: true, flatShading: true }));
  mesh.name = 'terrain';
  mesh.receiveShadow = true;
  return mesh;
}

// ----- ground-hugging detail: clearings (discs) and dirt paths (ribbons) -------------------------------------------
const LIFT = 0.07;

function disc(cx, cz, radius, color, rings = 4, seg = 40) {
  const pos = [], col = [], idx = [];
  const c = new THREE.Color(color);
  for (let ri = 0; ri <= rings; ri++) {
    const rr = (ri / rings) * radius;
    for (let s = 0; s < (ri === 0 ? 1 : seg); s++) {
      const a = (s / seg) * Math.PI * 2;
      const x = cx + Math.cos(a) * rr, z = cz + Math.sin(a) * rr;
      pos.push(x, groundHeight(x, z) + LIFT, z);
      const v = 0.92 + 0.08 * Math.sin(x * 1.7 + z * 1.3);
      col.push(c.r * v, c.g * v, c.b * v);
    }
  }
  for (let ri = 1; ri <= rings; ri++) {
    const prev = ri === 1 ? 0 : 1 + (ri - 2) * seg, cur = 1 + (ri - 1) * seg;
    for (let s = 0; s < seg; s++) {
      const n = (s + 1) % seg;
      if (ri === 1) idx.push(0, cur + n, cur + s);
      else idx.push(prev + s, cur + n, cur + s, prev + s, prev + n, cur + n);
    }
  }
  return { pos, col, idx };
}

function ribbon(points, width, color, lift = LIFT) {
  const pos = [], col = [], idx = [];
  const c = new THREE.Color(color);
  for (let i = 0; i < points.length; i++) {
    const a = points[Math.max(0, i - 1)], b = points[Math.min(points.length - 1, i + 1)];
    let dx = b[0] - a[0], dz = b[1] - a[1];
    const len = Math.hypot(dx, dz) || 1;
    dx /= len; dz /= len;
    const wob = 0.82 + 0.3 * Math.sin(i * 0.9) * Math.cos(i * 0.37);       // slightly uneven edges
    for (const side of [-1, 1]) {
      const x = points[i][0] - dz * side * width * 0.5 * wob, z = points[i][1] + dx * side * width * 0.5 * wob;
      pos.push(x, groundHeight(x, z) + lift, z);
      const v = 0.9 + 0.1 * Math.sin(i * 1.7 + side);
      col.push(c.r * v, c.g * v, c.b * v);
    }
    if (i) { const k = i * 2; idx.push(k - 2, k - 1, k, k - 1, k + 1, k); }
  }
  return { pos, col, idx };
}

function merge(parts) {
  const pos = [], col = [], idx = [];
  for (const p of parts) {
    const base = pos.length / 3;
    for (const v of p.pos) pos.push(v);
    for (const v of p.col) col.push(v);
    for (const i of p.idx) idx.push(base + i);
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
  g.setAttribute('color', new THREE.Float32BufferAttribute(col, 3));
  g.setIndex(idx);
  g.computeVertexNormals();
  return g;
}

function patchMaterial(factor) {
  return new THREE.MeshLambertMaterial({ vertexColors: true, flatShading: true, side: THREE.DoubleSide, polygonOffset: true, polygonOffsetFactor: factor, polygonOffsetUnits: factor });
}

export function buildGroundDetail() {
  const group = new THREE.Group();
  group.name = 'ground-detail';
  const discs = LOCATIONS.map((l) => disc(l.x, l.z, l.r * 0.82, l.ground));
  const clear = new THREE.Mesh(merge(discs), patchMaterial(-2));
  clear.receiveShadow = true;
  group.add(clear);
  const dirt = '#8d6d47';
  const strips = [ribbon(MAIN_PATH, 2.4, dirt), ribbon(WEST_PATH, 2.4, dirt), ribbon(EAST_PATH, 2.4, dirt), ribbon(ROBOTICS_LOOP, 2.2, '#7a5e3c', LIFT + 0.02)];
  for (const spur of PATHS.slice(4)) strips.push(ribbon(spur, 2.0, dirt));
  const paths = new THREE.Mesh(merge(strips), patchMaterial(-4));
  paths.receiveShadow = true;
  group.add(paths);
  return group;
}

// A dashed ribbon along a polyline (rover tracks, footpath wear): `dash` and `gap` in samples.
export function trackMarks(points, width, color, dash = 3, gap = 2) {
  const parts = [];
  for (let i = 0; i + dash < points.length; i += dash + gap) parts.push(ribbon(points.slice(i, i + dash + 1), width, color, LIFT + 0.04));
  const mesh = new THREE.Mesh(merge(parts), patchMaterial(-6));
  mesh.receiveShadow = true;
  return mesh;
}
