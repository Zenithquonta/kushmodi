// The hill, the plain around it and the ridges. -Z is north; the north side stays a flat plain toward the city.
import * as THREE from '../vendor/three/three.module.js';

export const HILL_TOP = 9;          // metres: height of the flat crown
export const CROWN_RADIUS = 22;
export const WALK_RADIUS = 46;      // soft boundary
export const FAR = 2600;

const smooth = (a, b, x) => {
  const t = Math.min(1, Math.max(0, (x - a) / (b - a)));
  return t * t * (3 - 2 * t);
};

export function groundHeight(x, z) {
  const r = Math.hypot(x, z);
  let h = HILL_TOP * (1 - smooth(CROWN_RADIUS, 96, r));
  // gentle swells on the slopes and plain (kept small so the crown stays flat)
  const swell = Math.sin(x * 0.045 + 1.3) * Math.cos(z * 0.038) + 0.6 * Math.sin((x - z) * 0.09);
  h += swell * 1.1 * smooth(CROWN_RADIUS + 6, 120, r);
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

// 1 on the walking path that leads from the start point to the telescope and the shed, 0 elsewhere
export function pathMask(x, z) {
  const d1 = distToSegment(x, z, 0, 18, -7, -1);
  const d2 = distToSegment(x, z, -1, 4, 13, -4);
  const d3 = distToSegment(x, z, 3, 12, 9, 11);
  return Math.max(1 - smooth(0.9, 1.9, Math.min(d1, d2, d3)), 0);
}

function distToSegment(px, pz, ax, az, bx, bz) {
  const dx = bx - ax, dz = bz - az;
  const t = Math.max(0, Math.min(1, ((px - ax) * dx + (pz - az) * dz) / (dx * dx + dz * dz)));
  return Math.hypot(px - (ax + t * dx), pz - (az + t * dz));
}

export function buildTerrain(greenery = 0.7) {
  const radii = [];
  for (let r = 0; r <= 100; r += 4) radii.push(r);
  for (let r = 125; r <= 800; r += 25) radii.push(r);
  for (let r = 900; r <= FAR; r += 100) radii.push(r);
  const SEG = 192;
  const positions = [];
  const colors = [];
  const index = [];
  const wet = new THREE.Color();
  const lush = new THREE.Color('#29423d'), dry = new THREE.Color('#62634b');
  const rock = new THREE.Color('#566178'), dirt = new THREE.Color('#71604d'), far = new THREE.Color('#2f4f3a');
  const grass = lush.clone().lerp(dry, 1 - greenery);
  const col = new THREE.Color();

  for (let ri = 0; ri < radii.length; ri++) {
    const r = radii[ri];
    for (let s = 0; s < SEG; s++) {
      const a = (s / SEG) * Math.PI * 2;
      const x = Math.sin(a) * r, z = Math.cos(a) * r;
      const y = groundHeight(x, z);
      positions.push(x, y, z);
      // colour: flat crown is grass, slopes darker, plain farther away blends to a dark green, ridges to rock
      const crown = 1 - smooth(CROWN_RADIUS, 80, r);
      col.copy(grass).multiplyScalar(0.8 + 0.07 * Math.sin(x * 0.18) * Math.cos(z * 0.21) + 0.1 * crown);
      col.lerp(far, smooth(90, 500, r) * 0.75);
      col.lerp(rock, smooth(8, 90, y - 3) * smooth(300, 700, r) * 0.7);
      col.lerp(dirt, pathMask(x, z) * 0.9);
      wet.copy(col);
      colors.push(wet.r, wet.g, wet.b);
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
  const mesh = new THREE.Mesh(g, new THREE.MeshLambertMaterial({ vertexColors: true, flatShading: false }));
  // Fine surface variation is procedural, so no texture downloads are needed.
  mesh.material.onBeforeCompile = (shader) => {
    shader.vertexShader = 'varying vec3 vGround;\n' + shader.vertexShader;
    shader.vertexShader = shader.vertexShader.replace('#include <begin_vertex>', '#include <begin_vertex>\nvGround = position;');
    shader.fragmentShader = 'varying vec3 vGround;\n' + shader.fragmentShader;
    shader.fragmentShader = shader.fragmentShader.replace('#include <color_fragment>', `#include <color_fragment>
      float grain = fract(sin(dot(floor(vGround.xz * 38.0), vec2(12.9898, 78.233))) * 43758.5453);
      float patches = sin(vGround.x * 1.7 + sin(vGround.z * 0.8)) * sin(vGround.z * 1.3);
      diffuseColor.rgb *= 0.88 + grain * 0.18 + patches * 0.06;`);
  };
  mesh.name = 'terrain';
  return mesh;
}
