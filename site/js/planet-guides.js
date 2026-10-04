// Labels use exactly the same astronomical world vectors as the rendered planets.
import * as THREE from '../vendor/three/three.module.js';

export class PlanetGuides {
  constructor(root, button) {
    this.root = root; this.button = button; this.enabled = true;
    this.labels = new Map(); this.point = new THREE.Vector3();
    this.direction = new THREE.Vector3(); this.forward = new THREE.Vector3();
    this.ray = new THREE.Raycaster(); this.ray.far = 2600;
    this.checked = 0; this.occluded = new Map();
    button.addEventListener('click', () => {
      this.enabled = !this.enabled;
      button.setAttribute('aria-pressed', String(this.enabled));
      root.hidden = !this.enabled;
    });
  }

  // True when terrain or painted scenery covers the sky direction as seen from `origin` (a unit vector toward the body).
  blocked(origin, direction, world) {
    this.ray.set(origin, direction);
    return this.ray.intersectObject(world.terrain, false).length > 0 || (world.scenery ? world.scenery.blocked(origin, direction) : false);
  }

  update(state, camera, world) {
    if (!this.enabled || !state) return;
    const width = innerWidth, height = innerHeight;
    camera.getWorldDirection(this.forward);
    const now = performance.now(), checkOcclusion = now - this.checked > 250;
    if (checkOcclusion) this.checked = now;
    const occupied = [];
    for (const body of state.planets) {
      let entry = this.labels.get(body.name);
      if (!entry) {
        const node = document.createElement('div'); node.className = 'planet-guide'; node.hidden = true;
        const ring = document.createElement('span'); ring.className = 'planet-ring'; ring.setAttribute('aria-hidden','true');
        const tag = document.createElement('span'); tag.className = 'planet-tag';
        tag.textContent = body.name;
        node.append(ring,tag); this.root.appendChild(node);
        entry = {node,tag}; this.labels.set(body.name, entry);
      }
      const {node,tag} = entry;
      this.direction.fromArray(body.world);
      if (body.altitude <= 0 || this.direction.dot(this.forward) <= 0) { node.hidden = true; continue; }
      // Match sky.js's planet radius and camera-relative sky origin.
      this.point.copy(this.direction).multiplyScalar(5000).add(camera.position).project(camera);
      if (this.point.z > 1 || Math.abs(this.point.x) > .96 || Math.abs(this.point.y) > .94) { node.hidden = true; continue; }
      if (checkOcclusion) {
        this.occluded.set(body.name, this.blocked(camera.position, this.direction, world));
      }
      if (this.occluded.get(body.name)) { node.hidden = true; continue; }
      const x = (this.point.x + 1) * width / 2, y = (1 - this.point.y) * height / 2;
      node.hidden = false; node.style.left = `${x}px`; node.style.top = `${y}px`;
      node.classList.toggle('label-left', x > width - 160);
      // Keep nearby labels apart while leaving their rings centered on the true coordinates.
      let offset = -10;
      while (occupied.some(p => Math.abs(p.x-x)<140 && Math.abs(p.y-(y+offset))<25)) offset += 27;
      tag.style.top = `${offset}px`; occupied.push({x,y:y+offset});
      tag.textContent = body.magnitude > 6.5 ? `${body.name} · telescope` : body.name;
      node.setAttribute('aria-label', `${body.name}, altitude ${body.altitude.toFixed(0)} degrees`);
    }
  }
}
