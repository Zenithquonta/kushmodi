// Movement and looking: WASD / arrow keys, mouse look (pointer lock, or drag), and touch (joystick plus drag to look).
// Collision against the colliders from world.js; the walkable area is the hilltop inside the fence.
import { groundHeight, WALK_RADIUS } from './terrain.js';

const PLAYER_RADIUS = 0.4;
const EYE = 1.7;
const WALK = 3.0, RUN = 5.6;

export function resolve(pos, colliders) {
  for (let pass = 0; pass < 2; pass++) {
    for (const c of colliders) {
      if (c.type === 'circle') {
        const dx = pos.x - c.x, dz = pos.z - c.z, min = c.r + PLAYER_RADIUS, d = Math.hypot(dx, dz);
        if (d < min) {
          const k = d > 1e-6 ? min / d : 0;
          if (k) { pos.x = c.x + dx * k; pos.z = c.z + dz * k; } else pos.x += min;
        }
      } else {
        const cos = Math.cos(c.yaw), sin = Math.sin(c.yaw);
        const px = pos.x - c.x, pz = pos.z - c.z;
        const lx = px * cos - pz * sin - c.lx, lz = px * sin + pz * cos - c.lz;
        const ox = c.hw + PLAYER_RADIUS - Math.abs(lx), oz = c.hd + PLAYER_RADIUS - Math.abs(lz);
        if (ox > 0 && oz > 0) {
          let nx = lx, nz = lz;
          if (ox < oz) nx = Math.sign(lx || 1) * (c.hw + PLAYER_RADIUS); else nz = Math.sign(lz || 1) * (c.hd + PLAYER_RADIUS);
          const wx = (nx + c.lx) * cos + (nz + c.lz) * sin, wz = -(nx + c.lx) * sin + (nz + c.lz) * cos;
          pos.x = c.x + wx; pos.z = c.z + wz;
        }
      }
    }
    const d = Math.hypot(pos.x, pos.z), limit = WALK_RADIUS - 1.2;
    if (d > limit) { pos.x *= limit / d; pos.z *= limit / d; }
  }
}

export class Player {
  constructor(canvas, colliders, options) {
    this.canvas = canvas;
    this.colliders = colliders;
    this.pos = { x: options.x, z: options.z };
    this.yaw = options.yaw || 0;            // 0 faces north (-Z); positive turns left
    this.pitch = options.pitch || 0;
    this.eyeY = groundHeight(this.pos.x, this.pos.z) + EYE;
    this.keys = new Set();
    this.tapped = new Set();               // keys pressed since the last frame, so a tap shorter than one frame still moves
    this.joy = { x: 0, y: 0 };
    this.enabled = true;
    this.locked = false;
    this.bob = 0;
    this.moving = false;
    this.reduced = false;
    this.onPick = options.onPick || (() => {});
    this.onKey = options.onKey || (() => {});
    this.touchLook = null;
    this.mouseDrag = null;
    this.bind(options.joystick, options.knob);
  }

  bind(joystick, knob) {
    const canvas = this.canvas;
    window.addEventListener('keydown', (e) => {
      if (!this.enabled || e.ctrlKey || e.metaKey || e.altKey) return;
      if (e.target instanceof HTMLElement && /^(INPUT|TEXTAREA|SELECT)$/.test(e.target.tagName)) return;
      this.keys.add(e.code);
      this.tapped.add(e.code);
      if (/^(Arrow|Space)/.test(e.code)) e.preventDefault();
      if (!e.repeat) this.onKey(e.code);
    });
    window.addEventListener('keyup', (e) => this.keys.delete(e.code));
    window.addEventListener('blur', () => { this.keys.clear(); this.joy.x = this.joy.y = 0; });
    document.addEventListener('pointerlockchange', () => { this.locked = document.pointerLockElement === canvas; });
    document.addEventListener('mousemove', (e) => {
      if (this.locked && this.enabled) this.look(e.movementX * 0.0022, e.movementY * 0.0022);
    });

    canvas.addEventListener('pointerdown', (e) => {
      if (!this.enabled) return;
      if (e.pointerType === 'mouse' && e.button !== 0) return;
      try { canvas.setPointerCapture?.(e.pointerId); } catch (err) { /* the pointer may already be gone */ }
      const drag = { id: e.pointerId, x: e.clientX, y: e.clientY, moved: 0, type: e.pointerType };
      if (e.pointerType === 'mouse') this.mouseDrag = drag; else this.touchLook = drag;
    });
    canvas.addEventListener('pointermove', (e) => {
      const drag = e.pointerType === 'mouse' ? this.mouseDrag : this.touchLook;
      if (!drag || drag.id !== e.pointerId || !this.enabled) return;
      const dx = e.clientX - drag.x, dy = e.clientY - drag.y;
      drag.x = e.clientX; drag.y = e.clientY;
      drag.moved += Math.abs(dx) + Math.abs(dy);
      if (!this.locked) this.look(dx * (drag.type === 'mouse' ? 0.0035 : 0.006), dy * (drag.type === 'mouse' ? 0.0035 : 0.006));
    });
    const up = (e) => {
      const mouse = e.pointerType === 'mouse';
      const drag = mouse ? this.mouseDrag : this.touchLook;
      if (!drag || drag.id !== e.pointerId) return;
      if (mouse) this.mouseDrag = null; else this.touchLook = null;
      if (e.type === 'pointerup' && drag.moved < 8) {
        this.onPick(e.clientX, e.clientY, this.locked);
        if (mouse && this.enabled && !this.locked) { try { const p = canvas.requestPointerLock?.(); if (p && p.catch) p.catch(() => {}); } catch (err) { /* ignored */ } }
      }
    };
    canvas.addEventListener('pointerup', up);
    canvas.addEventListener('pointercancel', up);

    if (joystick) {
      let id = null;
      const centre = () => { const r = joystick.getBoundingClientRect(); return [r.left + r.width / 2, r.top + r.height / 2, r.width / 2]; };
      const set = (e) => {
        const [cx, cy, rad] = centre();
        let dx = (e.clientX - cx) / rad, dy = (e.clientY - cy) / rad;
        const len = Math.hypot(dx, dy);
        if (len > 1) { dx /= len; dy /= len; }
        this.joy.x = dx; this.joy.y = dy;
        if (knob) { knob.style.setProperty('--kx', `${dx * 34}px`); knob.style.setProperty('--ky', `${dy * 34}px`); }
      };
      joystick.addEventListener('pointerdown', (e) => { id = e.pointerId; try { joystick.setPointerCapture?.(id); } catch (err) { /* synthetic or finished pointer */ } set(e); e.preventDefault(); });
      joystick.addEventListener('pointermove', (e) => { if (e.pointerId === id) set(e); });
      const end = (e) => {
        if (e.pointerId !== id) return;
        id = null; this.joy.x = this.joy.y = 0;
        if (knob) { knob.style.setProperty('--kx', '0px'); knob.style.setProperty('--ky', '0px'); }
      };
      joystick.addEventListener('pointerup', end);
      joystick.addEventListener('pointercancel', end);
    }
  }

  look(dx, dy) {
    this.yaw -= dx;
    this.pitch = Math.max(-1.25, Math.min(1.25, this.pitch - dy));
  }

  get heading() {
    return (((-this.yaw * 180) / Math.PI) % 360 + 360) % 360;      // compass bearing: 0 north, 90 east
  }

  update(dt) {
    const k = new Set([...this.keys, ...this.tapped]);
    this.tapped.clear();
    let fwd = 0, side = 0, turn = 0;
    if (this.enabled) {
      if (k.has('KeyW') || k.has('ArrowUp')) fwd += 1;
      if (k.has('KeyS') || k.has('ArrowDown')) fwd -= 1;
      if (k.has('KeyD')) side += 1;
      if (k.has('KeyA')) side -= 1;
      if (k.has('ArrowLeft')) turn += 1;
      if (k.has('ArrowRight')) turn -= 1;
      if (k.has('KeyQ')) turn += 1;
      fwd -= this.joy.y;
      side += this.joy.x;
    }
    this.yaw += turn * 1.7 * dt;
    const len = Math.hypot(fwd, side);
    this.moving = len > 0.05;
    if (this.moving) {
      const run = k.has('ShiftLeft') || k.has('ShiftRight') || Math.hypot(this.joy.x, this.joy.y) > 0.92;
      const speed = (run ? RUN : WALK) * Math.min(1, len);
      const sy = Math.sin(this.yaw), cy = Math.cos(this.yaw);
      const mx = (-sy * fwd + cy * side) / len, mz = (-cy * fwd - sy * side) / len;
      this.pos.x += mx * speed * dt;
      this.pos.z += mz * speed * dt;
      resolve(this.pos, this.colliders);
      this.bob += dt * (run ? 11 : 8);
    }
    const target = groundHeight(this.pos.x, this.pos.z) + EYE + (this.moving && !this.reduced ? Math.sin(this.bob) * 0.04 : 0);
    this.eyeY += (target - this.eyeY) * Math.min(1, dt * 12);
  }

  apply(camera) {
    camera.position.set(this.pos.x, this.eyeY, this.pos.z);
    camera.rotation.set(this.pitch, this.yaw, 0, 'YXZ');
  }
}
