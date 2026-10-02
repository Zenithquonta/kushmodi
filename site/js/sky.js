// The sky: gradient dome with the Milky Way, about 5000 real stars, constellation lines, the Sun, the Moon with its
// real phase, the seven planets, clouds and rain. All of it sits on a sphere beyond the terrain, so the ground hides it
// through the depth test (the sky objects do not write depth). Positions come from ephemeris.js; this file only draws them.
import * as THREE from '../vendor/three/three.module.js';
import { DEG, eqjUnit } from './ephemeris.js';

const R = 5000;               // sky radius (metres): beyond the terrain (2600 m), so the ground hides the sky by depth test
const MW_W = 1024, MW_H = 512;

// ----- colours ---------------------------------------------------------------------------------------------------
// [sun altitude, zenith rgb, horizon rgb] (0..255); interpolated, so the colour follows the real Sun.
const PALETTE = [
  [-18, [4, 8, 24], [14, 26, 54]],
  [-12, [9, 18, 48], [32, 54, 96]],
  [-6, [26, 46, 104], [118, 104, 128]],
  [-1, [58, 96, 166], [244, 150, 96]],
  [4, [78, 134, 206], [236, 186, 142]],
  [20, [70, 140, 226], [172, 206, 236]],
  [60, [48, 118, 222], [150, 200, 240]],
];
const smooth = (a, b, x) => { const t = Math.min(1, Math.max(0, (x - a) / (b - a))); return t * t * (3 - 2 * t); };
const lerp = (a, b, t) => a + (b - a) * t;

function paletteAt(alt, out) {
  let i = 0;
  while (i < PALETTE.length - 2 && alt > PALETTE[i + 1][0]) i++;
  const [a0, z0, h0] = PALETTE[i], [a1, z1, h1] = PALETTE[i + 1];
  const t = Math.min(1, Math.max(0, (alt - a0) / (a1 - a0)));
  for (let k = 0; k < 3; k++) {
    out.zenith[k] = lerp(z0[k], z1[k], t) / 255;
    out.horizon[k] = lerp(h0[k], h1[k], t) / 255;
  }
}

// Limiting magnitude of the sky: what the naked eye can reach, from the Sun's altitude, cloud, the Moon and the city.
export function limitingMagnitude(sunAlt, moonAlt, moonIllum, env) {
  const table = [[0, -3.5], [-3, -1.5], [-6, 0.5], [-9, 2.5], [-12, 4.0], [-18, 5.6]];
  let m = table[table.length - 1][1];
  if (sunAlt > 0) m = table[0][1];
  else for (let i = 0; i < table.length - 1; i++) {
    if (sunAlt <= table[i][0] && sunAlt >= table[i + 1][0]) {
      m = lerp(table[i][1], table[i + 1][1], (table[i][0] - sunAlt) / (table[i][0] - table[i + 1][0]));
    }
  }
  const dark = smooth(-12, -18, sunAlt);                        // the city and the Moon only matter in the dark
  m -= (1 - env.nightVisibility) * 1.8 * dark;
  m -= env.haze * 0.3 * dark;
  m -= env.cloud * 2.8;
  if (moonAlt > 0) m -= moonIllum * Math.min(1, 0.35 + moonAlt / 40) * 1.7 * dark;
  return m;
}

export function skyLook(sunAlt, env, out = { zenith: [0, 0, 0], horizon: [0, 0, 0] }) {
  paletteAt(sunAlt, out);
  const grey = lerp(0.18, 0.62, smooth(-12, 6, sunAlt));       // overcast sky is grey, brighter by day
  const cloud = Math.min(1, env.cloud * 0.75 + env.rain * 0.3);
  const haze = env.haze * 0.35 + env.fog * 0.6;
  for (let k = 0; k < 3; k++) {
    out.zenith[k] = lerp(out.zenith[k], grey * (0.9 + 0.1 * k / 2), cloud * 0.7);
    out.horizon[k] = lerp(out.horizon[k], grey, cloud * 0.55);
    out.horizon[k] = lerp(out.horizon[k], 0.5 * out.horizon[k] + 0.4 * grey, haze);
  }
  return out;
}

function kelvinToRgb(k) {
  if (!k) return [1, 0.95, 0.9];
  const t = Math.min(40000, Math.max(1500, k)) / 100;
  let r, g, b;
  if (t <= 66) { r = 255; g = 99.47 * Math.log(t) - 161.12; } else { r = 329.7 * Math.pow(t - 60, -0.1332); g = 288.12 * Math.pow(t - 60, -0.0755); }
  if (t >= 66) b = 255; else if (t <= 19) b = 0; else b = 138.52 * Math.log(t - 10) - 305.04;
  const c = [r, g, b].map((v) => Math.min(255, Math.max(0, v)) / 255);
  return c.map((v) => 0.45 + 0.55 * v);                         // keep stars pale: half way to white
}

// ----- shaders ---------------------------------------------------------------------------------------------------
const NOISE = `
float hash31(vec3 p){ p = fract(p*0.3183099 + vec3(0.71,0.113,0.419)); p *= 17.0; return fract(p.x*p.y*p.z*(p.x+p.y+p.z)); }
float vnoise(vec3 x){ vec3 i = floor(x), f = fract(x); f = f*f*(3.0-2.0*f);
  return mix(mix(mix(hash31(i), hash31(i+vec3(1,0,0)), f.x), mix(hash31(i+vec3(0,1,0)), hash31(i+vec3(1,1,0)), f.x), f.y),
             mix(mix(hash31(i+vec3(0,0,1)), hash31(i+vec3(1,0,1)), f.x), mix(hash31(i+vec3(0,1,1)), hash31(i+vec3(1,1,1)), f.x), f.y), f.z); }
float fbm(vec3 p){ float a = 0.5, s = 0.0; for (int i = 0; i < 4; i++) { s += a*vnoise(p); p = p*2.03 + 7.1; a *= 0.5; } return s; }
`;

const DOME_VS = `varying vec3 vDir; void main(){ vDir = normalize(position); gl_Position = projectionMatrix*modelViewMatrix*vec4(position,1.0); }`;
const DOME_FS = `
precision highp float;
uniform vec3 uZenith, uHorizon, uSunDir, uSunColor;
uniform float uSunGlow, uCity, uMw, uFlash;
uniform sampler2D uMwTex; uniform mat3 uToEqj;
varying vec3 vDir;
${NOISE}
void main(){
  vec3 d = normalize(vDir);
  float h = max(d.y, 0.0);
  vec3 col = mix(uHorizon, uZenith, pow(h, 0.5));
  float s = max(dot(d, uSunDir), 0.0);
  col += uSunColor * (pow(s, 5.0)*0.30 + pow(s, 36.0)*0.55) * uSunGlow;
  float north = max(dot(normalize(vec3(d.x, 0.0, d.z) + vec3(0.0,0.0,1e-4)), vec3(0.0,0.0,-1.0)), 0.0);
  col += vec3(0.95, 0.52, 0.24) * uCity * pow(north, 2.5) * exp(-h*7.0) * 0.30;
  if (uMw > 0.003) {
    vec3 e = uToEqj * d;
    vec2 uv = vec2(atan(e.y, e.x)/6.2831853 + 0.5, asin(clamp(e.z, -1.0, 1.0))/3.14159265 + 0.5);
    vec3 mw = texture2D(uMwTex, uv).rgb;
    float grain = 0.55 + 0.9*fbm(e*9.0);
    col += mw * grain * uMw * smoothstep(0.0, 0.08, d.y);
  }
  col += uFlash*vec3(0.45, 0.5, 0.65);
  // ordered dither (4x4 Bayer) at 40 levels: banding without hue shifts, and a pixel-art texture
  vec2 q = mod(floor(gl_FragCoord.xy), 4.0);
  float bayer = mod(q.x*4.0 + q.y*7.0 + floor(q.y/2.0)*5.0, 16.0)/16.0;
  col = floor(col*40.0 + bayer)/40.0;
  gl_FragColor = vec4(col, 1.0);
}`;

const STAR_VS = `
attribute float aMag; attribute vec3 aColor;
uniform float uLimit, uPR, uTime, uTwinkle;
varying vec3 vColor; varying float vBig;
void main(){
  float vis = clamp((uLimit - aMag)*1.3 + 0.35, 0.0, 1.0);
  float size = aMag < 0.0 ? 5.0 : aMag < 1.5 ? 4.0 : aMag < 2.6 ? 3.0 : aMag < 3.4 ? 2.0 : 1.0;
  float tw = 1.0 - uTwinkle*0.22*(0.5 + 0.5*sin(uTime*(2.0 + aMag) + position.x*0.37 + position.z*0.21));
  vColor = aColor * vis * tw * clamp(1.5 - aMag*0.12, 0.8, 1.0);
  vBig = size > 2.5 ? 1.0 : 0.0;
  gl_PointSize = vis > 0.0 ? max(1.0, floor(size*uPR + 0.5)) : 0.0;
  gl_Position = projectionMatrix*modelViewMatrix*vec4(position, 1.0);
}`;
const STAR_FS = `
precision mediump float;
varying vec3 vColor; varying float vBig;
void main(){
  if (vBig > 0.5) { vec2 d = abs(gl_PointCoord - 0.5); if (min(d.x, d.y) > 0.14 && d.x + d.y > 0.38) discard; }
  gl_FragColor = vec4(vColor, 1.0);
}`;

const PLANET_VS = `
attribute float aMag; attribute vec3 aColor; attribute float aUp;
uniform float uLimit, uPR;
varying vec3 vColor;
void main(){
  float vis = clamp((uLimit - aMag)*1.2 + 0.1, 0.0, 1.0) * aUp;
  vColor = aColor * vis;
  gl_PointSize = vis > 0.0 ? floor(clamp(6.0 - aMag*0.9, 3.0, 9.0)*uPR + 0.5) : 0.0;
  gl_Position = projectionMatrix*modelViewMatrix*vec4(position, 1.0);
}`;
const PLANET_FS = `
precision mediump float; varying vec3 vColor;
void main(){ vec2 d = gl_PointCoord - 0.5; if (dot(d, d) > 0.22) discard; gl_FragColor = vec4(vColor, 1.0); }`;

const TRAIL_VS = `
attribute vec3 aColor; attribute float aFade; varying vec4 vC;
void main(){ vC = vec4(aColor, aFade); gl_Position = projectionMatrix*modelViewMatrix*vec4(position, 1.0); }`;
const TRAIL_FS = `precision mediump float; varying vec4 vC; void main(){ if (vC.a < 0.01) discard; gl_FragColor = vC; }`;

const GLOW_FS = `
precision mediump float; uniform vec3 uColor; uniform float uStrength; varying vec2 vUv;
void main(){ float r = length(vUv - 0.5)*2.0; float a = pow(max(1.0 - r, 0.0), 2.2)*uStrength; gl_FragColor = vec4(uColor*a, 1.0); }`;
const UV_VS = `varying vec2 vUv; void main(){ vUv = uv; gl_Position = projectionMatrix*modelViewMatrix*vec4(position,1.0); }`;

const DISC_FS = `
precision mediump float; uniform vec3 uColor; varying vec2 vUv;
void main(){ float r = length(vUv - 0.5)*2.0; if (r > 1.0) discard; gl_FragColor = vec4(uColor, 1.0); }`;

const MOON_VS = `varying vec3 vN; void main(){ vN = normalize(position); gl_Position = projectionMatrix*modelViewMatrix*vec4(position,1.0); }`;
const MOON_FS = `
precision highp float;
uniform vec3 uSun, uRight, uUp, uToMoon; uniform float uBright;
varying vec3 vN;
float blob(vec2 p, vec3 m){ return smoothstep(m.z, m.z*0.35, distance(p, m.xy)); }
void main(){
  vec3 n = normalize(vN);
  vec2 p = vec2(dot(n, uRight), dot(n, uUp));
  float maria = 0.0;
  maria = max(maria, blob(p, vec3(-0.22, 0.42, 0.30)));  maria = max(maria, blob(p, vec3(0.22, 0.46, 0.16)));
  maria = max(maria, blob(p, vec3(0.30, 0.10, 0.22)));   maria = max(maria, blob(p, vec3(0.66, 0.20, 0.10)));
  maria = max(maria, blob(p, vec3(0.52, -0.16, 0.16)));  maria = max(maria, blob(p, vec3(-0.22, -0.40, 0.18)));
  maria = max(maria, blob(p, vec3(-0.62, 0.08, 0.30)));
  float crater = smoothstep(0.07, 0.0, distance(p, vec2(-0.12, -0.66)));
  float lit = smoothstep(-0.03, 0.07, dot(n, uSun));
  vec3 surface = mix(vec3(0.95, 0.92, 0.84), vec3(0.50, 0.52, 0.58), maria*0.85) + crater*0.12;
  vec3 col = mix(vec3(0.045, 0.055, 0.085), surface*uBright, lit);
  col = floor(col*16.0 + 0.5)/16.0;
  gl_FragColor = vec4(col, 1.0);
}`;

const CLOUD_FS = `
precision highp float;
uniform vec3 uColor, uShade; uniform float uCover, uTime;
varying vec3 vDir;
${NOISE}
void main(){
  vec3 d = normalize(vDir);
  if (d.y < 0.0 || uCover < 0.02) discard;
  vec2 p = d.xz/(d.y + 0.28)*1.4 + vec2(uTime*0.004, uTime*0.0015);
  float n = fbm(vec3(p*1.7, 3.0));
  float th = mix(0.78, 0.32, uCover);
  float a = smoothstep(th, th + 0.18, n);
  a = floor(a*4.0 + 0.5)/4.0 * smoothstep(0.0, 0.12, d.y) * min(1.0, 0.35 + uCover);
  if (a < 0.02) discard;
  float shade = fbm(vec3(p*3.1, 9.0));
  vec3 col = mix(uShade, uColor, smoothstep(0.25, 0.7, shade));
  gl_FragColor = vec4(col, a);
}`;

const RAIN_VS = `
attribute float aSeed; uniform float uTime, uRain, uPR;
varying float vA;
void main(){
  vec3 p = position;
  float speed = 14.0 + 8.0*fract(aSeed*7.0);
  p.y = mod(position.y - uTime*speed, 12.0) - 3.0;
  p.x += (p.y)*0.12;
  vA = aSeed < uRain ? 0.55 : 0.0;
  gl_Position = projectionMatrix*modelViewMatrix*vec4(p, 1.0);
}`;
const RAIN_FS = `precision mediump float; varying float vA; void main(){ if (vA < 0.01) discard; gl_FragColor = vec4(0.62, 0.72, 0.85, vA); }`;

// ----- the sky object --------------------------------------------------------------------------------------------
const PLANET_COLORS = {
  Mercury: [0.78, 0.75, 0.69], Venus: [1, 0.96, 0.85], Mars: [1, 0.55, 0.36], Jupiter: [1, 0.88, 0.69],
  Saturn: [0.94, 0.85, 0.56], Uranus: [0.63, 0.94, 0.91], Neptune: [0.48, 0.63, 1],
};

export const TRAIL_BODIES = ['Moon', 'Mercury', 'Venus', 'Mars', 'Jupiter', 'Saturn', 'Uranus', 'Neptune'];
const TRAIL_SEGMENTS = 36;     // 3 hours in 5-minute steps

export class Sky {
  constructor(scene, data, planetNames, pixelRatio = 1) {
    this.pixelRatio = pixelRatio;
    this.group = new THREE.Group();          // follows the camera
    this.group.name = 'sky';
    this.group.frustumCulled = false;
    this.equatorial = new THREE.Group();     // J2000 equatorial frame -> world; holds the stars and the lines
    this.equatorial.matrixAutoUpdate = false;
    this.group.add(this.equatorial);
    scene.add(this.group);
    this.mwCanvas = this.drawMilkyWay(data.milkyway);
    this.buildDome();
    this.buildStars(data.stars);
    this.buildLines(data.constellations);
    this.buildBodies(planetNames);
    this.buildTrails();
    this.buildClouds();
    this.buildRain();
    this.look = { zenith: [0, 0, 0], horizon: [0, 0, 0] };
    this.flash = 0;
    this.linesWanted = true;
    this.matrix4 = new THREE.Matrix4();
    this.tmp = new THREE.Vector3();
    this.limit = 5.6;
  }

  drawMilkyWay(mw) {
    const canvas = document.createElement('canvas');
    canvas.width = MW_W; canvas.height = MW_H;
    const ctx = canvas.getContext('2d');
    ctx.fillStyle = '#000';
    ctx.fillRect(0, 0, MW_W, MW_H);
    // outermost outline first; each deeper level adds light, and the colour warms toward the galactic centre
    const colors = ['rgba(34,52,104,0.20)', 'rgba(60,70,128,0.20)', 'rgba(110,100,150,0.20)', 'rgba(170,140,150,0.22)', 'rgba(220,180,140,0.26)'];
    ctx.globalCompositeOperation = 'lighter';
    mw.levels.forEach((rings, level) => {
      ctx.fillStyle = colors[Math.min(level, colors.length - 1)];
      // d3-celestial outlines are planar polygons with longitude (= right ascension, -180..180) as x, already cut at
      // the antimeridian, so they are drawn as they are; the shader reads u = RA / 360 + 0.5.
      ctx.beginPath();
      for (const ring of rings) {
        for (let i = 0; i < ring.length; i += 2) {
          const x = ((ring[i] + 180) / 360) * MW_W, y = ((90 - ring[i + 1]) / 180) * MW_H;
          if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
        }
        ctx.closePath();
      }
      ctx.fill('evenodd');
    });
    return canvas;
  }

  buildDome() {
    const texture = new THREE.CanvasTexture(this.mwCanvas);
    texture.wrapS = THREE.RepeatWrapping;
    texture.colorSpace = THREE.NoColorSpace;
    texture.minFilter = THREE.LinearFilter;
    texture.magFilter = THREE.LinearFilter;
    texture.generateMipmaps = false;
    this.domeUniforms = {
      uZenith: { value: new THREE.Vector3() }, uHorizon: { value: new THREE.Vector3() }, uSunDir: { value: new THREE.Vector3(0, -1, 0) },
      uSunColor: { value: new THREE.Vector3(1, 0.7, 0.4) }, uSunGlow: { value: 0 }, uCity: { value: 0.5 }, uMw: { value: 1 },
      uFlash: { value: 0 }, uMwTex: { value: texture }, uToEqj: { value: new THREE.Matrix3() },
    };
    const material = new THREE.ShaderMaterial({
      uniforms: this.domeUniforms, vertexShader: DOME_VS, fragmentShader: DOME_FS, side: THREE.BackSide,
      depthTest: true, depthWrite: false, fog: false,
    });
    this.dome = new THREE.Mesh(new THREE.SphereGeometry(R * 1.05, 48, 24), material);
    this.dome.renderOrder = -20;
    this.dome.frustumCulled = false;
    this.group.add(this.dome);
  }

  buildStars(stars) {
    const n = stars.stars.length;
    const position = new Float32Array(n * 3), mag = new Float32Array(n), color = new Float32Array(n * 3);
    const u = [0, 0, 0];
    this.starEqj = new Float32Array(n * 3);
    stars.stars.forEach(([ra, dec, m, k], i) => {
      eqjUnit(ra, dec, u);
      position.set([u[0] * R, u[1] * R, u[2] * R], i * 3);
      this.starEqj.set(u, i * 3);
      mag[i] = m;
      color.set(kelvinToRgb(k), i * 3);
    });
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute('position', new THREE.BufferAttribute(position, 3));
    geometry.setAttribute('aMag', new THREE.BufferAttribute(mag, 1));
    geometry.setAttribute('aColor', new THREE.BufferAttribute(color, 3));
    this.starUniforms = { uLimit: { value: 5.6 }, uPR: { value: this.pixelRatio }, uTime: { value: 0 }, uTwinkle: { value: 1 } };
    const material = new THREE.ShaderMaterial({
      uniforms: this.starUniforms, vertexShader: STAR_VS, fragmentShader: STAR_FS, transparent: true,
      blending: THREE.AdditiveBlending, depthTest: true, depthWrite: false, fog: false,
    });
    this.stars = new THREE.Points(geometry, material);
    this.stars.renderOrder = -19;
    this.stars.frustumCulled = false;
    this.equatorial.add(this.stars);
  }

  buildLines(data) {
    const verts = [];
    const u = [0, 0, 0];
    for (const c of data.constellations) {
      for (const line of c.lines) {
        for (let i = 0; i + 3 < line.length; i += 2) {
          for (const j of [i, i + 2]) {
            eqjUnit(line[j], line[j + 1], u);
            verts.push(u[0] * R, u[1] * R, u[2] * R);
          }
        }
      }
    }
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute('position', new THREE.Float32BufferAttribute(verts, 3));
    this.lineMaterial = new THREE.LineBasicMaterial({ color: 0x4fb6d8, transparent: true, opacity: 0.2, depthTest: true, depthWrite: false, fog: false });
    this.lines = new THREE.LineSegments(geometry, this.lineMaterial);
    this.lines.renderOrder = -18;
    this.lines.frustumCulled = false;
    this.equatorial.add(this.lines);
  }

  buildBodies(planetNames) {
    this.planetNames = planetNames;
    const n = planetNames.length;
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute('position', new THREE.BufferAttribute(new Float32Array(n * 3), 3));
    geometry.setAttribute('aMag', new THREE.BufferAttribute(new Float32Array(n), 1));
    geometry.setAttribute('aUp', new THREE.BufferAttribute(new Float32Array(n), 1));
    const color = new Float32Array(n * 3);
    planetNames.forEach((name, i) => color.set(PLANET_COLORS[name] || [1, 1, 1], i * 3));
    geometry.setAttribute('aColor', new THREE.BufferAttribute(color, 3));
    this.planetUniforms = { uLimit: this.starUniforms.uLimit, uPR: this.starUniforms.uPR };
    this.planets = new THREE.Points(geometry, new THREE.ShaderMaterial({
      uniforms: this.planetUniforms, vertexShader: PLANET_VS, fragmentShader: PLANET_FS, depthTest: true, depthWrite: false, fog: false,
    }));
    this.planets.renderOrder = -17;
    this.planets.frustumCulled = false;
    this.group.add(this.planets);

    // Sun: a disc (about 4 degrees across, exaggerated for a 240-pixel-tall picture) and a soft glow
    const sunSize = R * Math.tan(2.2 * DEG) * 2;
    this.sunUniforms = { uColor: { value: new THREE.Vector3(1, 0.95, 0.75) } };
    this.sun = new THREE.Mesh(new THREE.PlaneGeometry(sunSize, sunSize), new THREE.ShaderMaterial({
      uniforms: this.sunUniforms, vertexShader: UV_VS, fragmentShader: DISC_FS, depthTest: true, depthWrite: false, fog: false,
    }));
    this.sun.renderOrder = -15;
    this.sunGlowUniforms = { uColor: { value: new THREE.Vector3(1, 0.8, 0.45) }, uStrength: { value: 0.6 } };
    this.sunGlow = new THREE.Mesh(new THREE.PlaneGeometry(sunSize * 7, sunSize * 7), new THREE.ShaderMaterial({
      uniforms: this.sunGlowUniforms, vertexShader: UV_VS, fragmentShader: GLOW_FS, blending: THREE.AdditiveBlending,
      depthTest: true, depthWrite: false, fog: false, transparent: true,
    }));
    this.sunGlow.renderOrder = -16;
    this.group.add(this.sunGlow, this.sun);

    // Moon: a lit sphere, so the phase and the tilt of the bright limb come from the real Sun direction
    const moonRadius = R * Math.tan(1.9 * DEG);
    this.moonUniforms = {
      uSun: { value: new THREE.Vector3(0, 1, 0) }, uRight: { value: new THREE.Vector3(1, 0, 0) }, uUp: { value: new THREE.Vector3(0, 1, 0) },
      uToMoon: { value: new THREE.Vector3(0, 0, -1) }, uBright: { value: 1 },
    };
    this.moon = new THREE.Mesh(new THREE.SphereGeometry(moonRadius, 24, 16), new THREE.ShaderMaterial({
      uniforms: this.moonUniforms, vertexShader: MOON_VS, fragmentShader: MOON_FS, depthTest: true, depthWrite: false, fog: false,
    }));
    this.moon.renderOrder = -14;
    this.moon.frustumCulled = false;
    this.group.add(this.moon);
  }

  // A comet-like line behind the Moon and each planet: the path of the last three hours, brightest at the body and
  // fading to nothing at the oldest sample.
  buildTrails() {
    const bodies = TRAIL_BODIES.length, verts = bodies * TRAIL_SEGMENTS * 2;
    const position = new Float32Array(verts * 3), color = new Float32Array(verts * 3), fade = new Float32Array(verts);
    TRAIL_BODIES.forEach((name, b) => {
      const c = name === 'Moon' ? [0.9, 0.92, 1] : PLANET_COLORS[name];
      for (let v = 0; v < TRAIL_SEGMENTS * 2; v++) color.set(c, (b * TRAIL_SEGMENTS * 2 + v) * 3);
    });
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute('position', new THREE.BufferAttribute(position, 3));
    geometry.setAttribute('aColor', new THREE.BufferAttribute(color, 3));
    geometry.setAttribute('aFade', new THREE.BufferAttribute(fade, 1));
    this.trails = new THREE.LineSegments(geometry, new THREE.ShaderMaterial({
      vertexShader: TRAIL_VS, fragmentShader: TRAIL_FS, transparent: true, blending: THREE.AdditiveBlending,
      depthTest: true, depthWrite: false, fog: false,
    }));
    this.trails.renderOrder = -17.5;
    this.trails.frustumCulled = false;
    this.trailSamples = null;
    this.group.add(this.trails);
  }

  // samples: bodyTrails() output for TRAIL_BODIES (newest first)
  setTrails(samples) {
    this.trailSamples = samples;
    this.writeTrails(null);
  }

  // Rewrites the line vertices; `state` (optional) moves the head of each trail to the body's current position.
  writeTrails(state) {
    if (!this.trailSamples) return;
    const pos = this.trails.geometry.attributes.position, fade = this.trails.geometry.attributes.aFade;
    const D = R * 0.955;
    TRAIL_BODIES.forEach((name, b) => {
      const s = this.trailSamples[b];
      if (state) {
        const body = name === 'Moon' ? state.moon : state.planets.find((p) => p.name === name);
        s[0] = body.world[0]; s[1] = body.world[1]; s[2] = body.world[2];
      }
      const mag = name === 'Moon' ? -9 : state ? state.planets.find((p) => p.name === name).magnitude : 0;
      const vis = Math.min(1, Math.max(0, (this.limit - mag) * 1.2 + 0.1)) * 0.85;
      for (let k = 0; k < TRAIL_SEGMENTS; k++) {
        const base = (b * TRAIL_SEGMENTS + k) * 2;
        for (let e = 0; e < 2; e++) {
          const i = k + e;
          pos.setXYZ(base + e, s[i * 3] * D, s[i * 3 + 1] * D, s[i * 3 + 2] * D);
          fade.setX(base + e, vis * Math.pow(1 - i / TRAIL_SEGMENTS, 1.4));
        }
      }
    });
    pos.needsUpdate = fade.needsUpdate = true;
  }

  buildClouds() {
    this.cloudUniforms = {
      uColor: { value: new THREE.Vector3(1, 1, 1) }, uShade: { value: new THREE.Vector3(0.6, 0.6, 0.65) }, uCover: { value: 0 }, uTime: { value: 0 },
    };
    this.clouds = new THREE.Mesh(new THREE.SphereGeometry(R * 1.02, 32, 16), new THREE.ShaderMaterial({
      uniforms: this.cloudUniforms, vertexShader: DOME_VS, fragmentShader: CLOUD_FS, side: THREE.BackSide, transparent: true,
      depthTest: true, depthWrite: false, fog: false,
    }));
    this.clouds.renderOrder = -13;
    this.clouds.frustumCulled = false;
    this.group.add(this.clouds);
  }

  buildRain() {
    const drops = 900;
    const position = new Float32Array(drops * 6), seed = new Float32Array(drops * 2);
    for (let i = 0; i < drops; i++) {
      const x = (((i * 73856093) % 1000) / 1000 - 0.5) * 24, z = (((i * 19349663) % 1000) / 1000 - 0.5) * 24;
      const y = ((i * 83492791) % 1000) / 1000 * 12;
      position.set([x, y, z, x + 0.03, y - 0.35, z], i * 6);
      seed[i * 2] = seed[i * 2 + 1] = (i + 0.5) / drops;
    }
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute('position', new THREE.BufferAttribute(position, 3));
    geometry.setAttribute('aSeed', new THREE.BufferAttribute(seed, 1));
    this.rainUniforms = { uTime: { value: 0 }, uRain: { value: 0 }, uPR: { value: 1 } };
    this.rain = new THREE.LineSegments(geometry, new THREE.ShaderMaterial({
      uniforms: this.rainUniforms, vertexShader: RAIN_VS, fragmentShader: RAIN_FS, transparent: true, depthWrite: false, fog: false,
    }));
    this.rain.frustumCulled = false;
    this.rain.visible = false;
    this.rain.renderOrder = 50;
    this.group.add(this.rain);
  }

  // Called when the sky state changes (every 2 simulated seconds) or the weather changes.
  setState(state, env, reduced) {
    const m = state.matrix;
    this.matrix4.set(m[0], m[3], m[6], 0, m[1], m[4], m[7], 0, m[2], m[5], m[8], 0, 0, 0, 0, 1);
    this.equatorial.matrix.copy(this.matrix4);
    this.equatorial.matrixWorldNeedsUpdate = true;
    this.domeUniforms.uToEqj.value.set(m[0], m[1], m[2], m[3], m[4], m[5], m[6], m[7], m[8]);

    const sunAlt = state.sun.altitude, moonAlt = state.moon.altitude;
    const moonIllum = state.moon.illuminated;
    this.limit = limitingMagnitude(sunAlt, moonAlt, moonIllum, env);
    this.starUniforms.uLimit.value = this.limit;
    this.starUniforms.uTwinkle.value = reduced ? 0 : 1;
    const dark = smooth(-6, -16, sunAlt);
    this.dark = dark;
    skyLook(sunAlt, env, this.look);
    const u = this.domeUniforms;
    u.uZenith.value.fromArray(this.look.zenith);
    u.uHorizon.value.fromArray(this.look.horizon);
    u.uSunDir.value.fromArray(state.sun.world);
    const low = 1 - smooth(8, 35, sunAlt);                    // warmer sun glow near the horizon
    u.uSunColor.value.set(1, lerp(0.95, 0.55, low), lerp(0.8, 0.28, low));
    u.uSunGlow.value = sunAlt > -8 ? smooth(-8, 0, sunAlt) * (1 - env.cloud * 0.6) : 0;
    u.uCity.value = env.urbanGlow * dark * (1 - env.cloud * 0.2) + env.urbanGlow * 0.1 * (1 - dark) * 0;
    u.uMw.value = dark * (0.55 + 0.4 * env.nightVisibility) * (1 - Math.min(0.9, env.cloud * 0.9)) * (1 - moonIllum * Math.min(1, Math.max(0, moonAlt) / 30) * 0.55) * (1 - env.haze * 0.3);

    this.lineMaterial.opacity = this.linesWanted ? 0.22 * smooth(-6, -14, sunAlt) * (1 - env.cloud * 0.5) : 0;
    this.lines.visible = this.lineMaterial.opacity > 0.005;

    const place = (mesh, w, distance = R * 0.97) => mesh.position.set(w[0] * distance, w[1] * distance, w[2] * distance);
    place(this.sun, state.sun.world);
    this.sun.lookAt(0, 0, 0);
    place(this.sunGlow, state.sun.world, R * 0.98);
    this.sunGlow.lookAt(0, 0, 0);
    this.sun.visible = this.sunGlow.visible = sunAlt > -4;
    this.sunUniforms.uColor.value.set(1, lerp(0.97, 0.7, low), lerp(0.82, 0.4, low));
    this.sunGlowUniforms.uStrength.value = 0.85 * (1 - env.cloud * 0.55);
    this.sunGlowUniforms.uColor.value.copy(u.uSunColor.value);

    place(this.moon, state.moon.world);
    this.moon.visible = moonAlt > -3;
    const toMoon = this.tmp.fromArray(state.moon.world);
    const right = new THREE.Vector3().crossVectors(toMoon, new THREE.Vector3(0, 1, 0));
    if (right.lengthSq() < 1e-6) right.set(1, 0, 0);
    right.normalize();
    const up = new THREE.Vector3().crossVectors(right, toMoon).normalize();
    this.moonUniforms.uRight.value.copy(right);
    this.moonUniforms.uUp.value.copy(up);
    this.moonUniforms.uToMoon.value.copy(toMoon);
    this.moonUniforms.uSun.value.fromArray(state.sun.world);
    this.moonUniforms.uBright.value = 1 - env.cloud * 0.25;

    const pos = this.planets.geometry.attributes.position, mag = this.planets.geometry.attributes.aMag, up2 = this.planets.geometry.attributes.aUp;
    state.planets.forEach((p, i) => {
      pos.setXYZ(i, p.world[0] * R * 0.96, p.world[1] * R * 0.96, p.world[2] * R * 0.96);
      mag.setX(i, p.magnitude);
      up2.setX(i, p.altitude > -0.5 ? 1 : 0);
    });
    pos.needsUpdate = mag.needsUpdate = up2.needsUpdate = true;
    this.writeTrails(state);

    // clouds: lit by the sun by day, by the city glow and the Moon at night
    const day = smooth(-8, 8, sunAlt);
    const c = this.cloudUniforms;
    c.uCover.value = Math.min(1, env.cloud * 1.05);
    const warm = (1 - smooth(4, 25, sunAlt)) * smooth(-9, 0, sunAlt);
    c.uColor.value.set(lerp(0.12, lerp(0.94, 1.0, warm), day) + env.urbanGlow * 0.08 * dark, lerp(0.14, lerp(0.95, 0.72, warm), day), lerp(0.2, lerp(0.97, 0.55, warm), day));
    c.uShade.value.set(lerp(0.05, 0.52, day), lerp(0.06, 0.55, day), lerp(0.1, 0.62, day));
    this.rain.visible = env.rain > 0;
    this.rainUniforms.uRain.value = env.rain;
  }

  // Per frame: keep the sky centred on the camera and advance the cheap animations.
  frame(camera, seconds, delta, env, reduced) {
    this.group.position.copy(camera.position);
    this.starUniforms.uTime.value = seconds;
    this.cloudUniforms.uTime.value = reduced ? 0 : seconds;
    this.rainUniforms.uTime.value = reduced ? 0 : seconds;
    if (env.thunder && !reduced) {
      this.flash = Math.max(0, this.flash - delta * 5);
      if (Math.random() < delta / 9) this.flash = 1;
    } else this.flash = 0;
    this.domeUniforms.uFlash.value = this.flash * 0.5;
  }

  setConstellations(on) {
    this.linesWanted = on;
  }

  resize(pixelRatio) {
    this.starUniforms.uPR.value = pixelRatio;
  }
}
