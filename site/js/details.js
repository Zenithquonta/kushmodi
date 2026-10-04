// Small, merged environmental details inspired by the profile's observatory artwork.
import * as THREE from '../vendor/three/three.module.js';
import { Bag } from './geom.js';
import { groundHeight } from './terrain.js';

export function buildDetails(root, world, pos) {
  const stone = new Bag(), plants = new Bag(), metal = new Bag(), glow = new Bag();
  let seed = 42;
  const random = () => { seed = (Math.imul(seed, 1664525) + 1013904223) >>> 0; return seed / 4294967296; };
  // A stone observing terrace grounds the instrument in the landscape.
  const [tx, tz] = pos.telescope;
  stone.cyl(3.1, 3.2, 0.08, '#53616a', tx, groundHeight(tx, tz) + 0.02, tz, 0, 0, 0, 64);
  for (let i = 0; i < 48; i++) {
    const a = i / 48 * Math.PI * 2;
    stone.box(0.31, 0.055, 0.12, '#85928c', tx + Math.sin(a) * 2.96, groundHeight(tx, tz) + 0.08, tz + Math.cos(a) * 2.96, 0, a, 0);
  }
  // Restrained amber path markers echo the warm lanterns in the original image.
  const lightTexture = poolTexture();
  for (const [x, z] of [[-3.8, 6], [3.5, 7], [-7, -1], [5.6, 2.8], [11, -4]]) {
    const y = groundHeight(x, z);
    metal.cyl(0.07, 0.1, 0.62, '#263b40', x, y + 0.31, z, 0, 0, 0, 16);
    metal.cyl(0.16, 0.16, 0.06, '#465758', x, y + 0.72, z, 0, 0, 0, 24);
    glow.cyl(0.095, 0.095, 0.16, '#ffd092', x, y + 0.61, z, 0, 0, 0, 24);
    const pool = new THREE.Mesh(new THREE.PlaneGeometry(4, 4), new THREE.MeshBasicMaterial({ map: lightTexture, color: '#ffb65e', transparent: true, opacity: 0.2, depthWrite: false, blending: THREE.AdditiveBlending }));
    pool.rotation.x = -Math.PI / 2; pool.position.set(x, y + 0.055, z); root.add(pool);
  }
  root.add(stone.mesh(), plants.mesh(), metal.mesh(), glow.mesh('glow'));
  // Cladding, deck seams, roof battens and a pegboard give the maker shed a crafted scale.
  const timber = new Bag();
  for (let i = 0; i < 27; i++) timber.box(0.018, 2.9, 0.018, '#a17d50', -3.95 + i * 0.3, 1.62, -2.405);
  for (let i = 0; i < 19; i++) timber.box(8.4, 0.012, 0.014, '#4b3529', 0, 0.166, -2.6 + i * 0.29);
  for (let i = 0; i < 24; i++) timber.box(0.04, 0.06, 6, '#485257', -4.4 + i * 0.38, 3.45, 0.15, -0.1, 0, 0);
  for (let i = 0; i < 7; i++) {
    timber.cyl(0.018, 0.018, 0.26 + i % 3 * 0.08, '#a9b3ad', -3.6 + i * 0.15, 2.1, -2.3);
    timber.box(0.06, 0.1, 0.05, i % 2 ? '#be743c' : '#3d8090', -3.6 + i * 0.15, 1.94, -2.3);
  }
  world.shed.add(timber.mesh());
}

function poolTexture() {
  const canvas = document.createElement('canvas'); canvas.width = canvas.height = 64;
  const ctx = canvas.getContext('2d'), gradient = ctx.createRadialGradient(32, 32, 0, 32, 32, 32);
  gradient.addColorStop(0, '#ffffff'); gradient.addColorStop(0.2, '#ffffff90'); gradient.addColorStop(1, '#ffffff00');
  ctx.fillStyle = gradient; ctx.fillRect(0, 0, 64, 64);
  return new THREE.CanvasTexture(canvas);
}
