// Tiny geometry "bag": collects boxes, cylinders and cones with one vertex colour each and builds a single
// flat-shaded mesh, so the whole observatory stays within a small draw-call budget.
import * as THREE from '../vendor/three/three.module.js';

const m4 = new THREE.Matrix4();
const q = new THREE.Quaternion();
const e = new THREE.Euler();
const p = new THREE.Vector3();
const s1 = new THREE.Vector3(1, 1, 1);
const c = new THREE.Color();

export class Bag {
  constructor() {
    this.pos = [];
    this.nor = [];
    this.col = [];
  }

  add(geometry, x, y, z, rx, ry, rz, color, sx = 1, sy = 1, sz = 1) {
    e.set(rx, ry, rz, 'YXZ');
    q.setFromEuler(e);
    p.set(x, y, z);
    m4.compose(p, q, s1.set(sx, sy, sz));
    const g = geometry.index ? geometry.toNonIndexed() : geometry.clone();
    g.applyMatrix4(m4);
    c.set(color);
    const pa = g.attributes.position.array, na = g.attributes.normal.array;
    for (let i = 0; i < pa.length; i += 3) {
      this.pos.push(pa[i], pa[i + 1], pa[i + 2]);
      this.nor.push(na[i], na[i + 1], na[i + 2]);
      this.col.push(c.r, c.g, c.b);
    }
    g.dispose();
    s1.set(1, 1, 1);
    return this;
  }

  // box(width, height, depth, colour, x, y, z, rotX, rotY, rotZ); the box is centred on (x, y, z)
  box(w, h, d, color, x = 0, y = 0, z = 0, rx = 0, ry = 0, rz = 0) {
    return this.add(Bag.cache('box', 1, 1, 1), x, y, z, rx, ry, rz, color, w, h, d);
  }

  cyl(rTop, rBottom, h, color, x = 0, y = 0, z = 0, rx = 0, ry = 0, rz = 0, segments = 8) {
    return this.add(Bag.cache('cyl', rTop, rBottom, h, segments), x, y, z, rx, ry, rz, color);
  }

  cone(r, h, color, x = 0, y = 0, z = 0, segments = 6) {
    return this.add(Bag.cache('cyl', 0, r, h, segments), x, y, z, 0, 0, 0, color);
  }

  ball(r, color, x = 0, y = 0, z = 0, detail = 1) {
    return this.add(Bag.cache('ico', r, detail), x, y, z, 0, 0, 0, color);
  }

  static cache(kind, a, b, c2, d) {
    const key = [kind, a, b, c2, d].join('|');
    let g = Bag.geoms.get(key);
    if (!g) {
      if (kind === 'box') g = new THREE.BoxGeometry(a, b, c2);
      else if (kind === 'cyl') g = new THREE.CylinderGeometry(a, b, c2, d, 1);
      else g = new THREE.IcosahedronGeometry(a, b);
      Bag.geoms.set(key, g);
    }
    return g;
  }

  // kind: 'lit' (Lambert, reacts to the lights) or 'glow' (unlit, not fogged: lamps, screens, windows)
  mesh(kind = 'lit') {
    const g = new THREE.BufferGeometry();
    g.setAttribute('position', new THREE.Float32BufferAttribute(this.pos, 3));
    g.setAttribute('normal', new THREE.Float32BufferAttribute(this.nor, 3));
    g.setAttribute('color', new THREE.Float32BufferAttribute(this.col, 3));
    g.computeBoundingSphere();
    const mesh = new THREE.Mesh(g, kind === 'glow' ? Bag.glowMaterial() : Bag.litMaterial());
    return mesh;
  }

  static litMaterial() {
    if (!Bag._lit) Bag._lit = new THREE.MeshLambertMaterial({ vertexColors: true, flatShading: true });
    return Bag._lit;
  }

  static glowMaterial() {
    if (!Bag._glow) Bag._glow = new THREE.MeshBasicMaterial({ vertexColors: true, fog: false });
    return Bag._glow;
  }
}
Bag.geoms = new Map();
