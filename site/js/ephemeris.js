// Real positions of the Sun, Moon and planets, and the sky rotation, for the observatory.
// Pure computation (no DOM, no three.js) so it can be checked in Node as well as used by the page.
//
// World axes: +X east, +Y up, +Z south (north is -Z). Astronomy Engine's horizontal frame is x = north, y = west,
// z = zenith, so world = (east, up, south) = (-y, z, -x).
import * as A from '../vendor/astronomy-engine/astronomy.js';

export const PLANETS = ['Mercury', 'Venus', 'Mars', 'Jupiter', 'Saturn', 'Uranus', 'Neptune'];
export const DEG = Math.PI / 180;

export function makeObserver(site) {
  return new A.Observer(site.latitude, site.longitude, site.elevation_m);
}

export function horToWorld(v, out = [0, 0, 0]) {
  out[0] = -v.y;
  out[1] = v.z;
  out[2] = -v.x;
  return out;
}

// Column-major 3x3 (9 numbers) that maps a J2000 equatorial vector to a world vector.
export function skyMatrix(date, observer, out = new Array(9)) {
  const rotation = A.Rotation_EQJ_HOR(date, observer);
  const basis = [new A.Vector(1, 0, 0, null), new A.Vector(0, 1, 0, null), new A.Vector(0, 0, 1, null)];
  const w = [0, 0, 0];
  for (let i = 0; i < 3; i++) {
    horToWorld(A.RotateVector(rotation, basis[i]), w);
    out[i * 3] = w[0];
    out[i * 3 + 1] = w[1];
    out[i * 3 + 2] = w[2];
  }
  return out;
}

export function applyMatrix(m, x, y, z, out = [0, 0, 0]) {
  out[0] = m[0] * x + m[3] * y + m[6] * z;
  out[1] = m[1] * x + m[4] * y + m[7] * z;
  out[2] = m[2] * x + m[5] * y + m[8] * z;
  return out;
}

// RA/Dec in degrees (J2000) to a unit J2000 vector.
export function eqjUnit(raDeg, decDeg, out = [0, 0, 0]) {
  const ra = raDeg * DEG, dec = decDeg * DEG, c = Math.cos(dec);
  out[0] = c * Math.cos(ra);
  out[1] = c * Math.sin(ra);
  out[2] = Math.sin(dec);
  return out;
}

// Altitude and azimuth (degrees, azimuth from north through east) of a world direction.
export function altAz(w) {
  const len = Math.hypot(w[0], w[1], w[2]) || 1;
  const alt = Math.asin(Math.max(-1, Math.min(1, w[1] / len))) / DEG;
  const az = ((Math.atan2(w[0], -w[2]) / DEG) % 360 + 360) % 360;
  return { alt, az };
}

function bodyState(name, date, observer, m) {
  const eq = A.Equator(name, date, observer, false, true);
  const len = Math.hypot(eq.vec.x, eq.vec.y, eq.vec.z);
  const world = applyMatrix(m, eq.vec.x / len, eq.vec.y / len, eq.vec.z / len);
  const { alt, az } = altAz(world);
  const illum = A.Illumination(name, date);
  return {
    name,
    world,                         // unit vector in world axes
    eqj: [eq.vec.x / len, eq.vec.y / len, eq.vec.z / len],
    raHours: eq.ra, decDeg: eq.dec, // J2000
    altitude: alt, azimuth: az,
    magnitude: illum.mag,
    illuminated: illum.phase_fraction,
    distanceAu: eq.dist,
  };
}

// Everything the scene needs about the sky at one instant.
export function skyState(date, observer) {
  const m = skyMatrix(date, observer);
  const sun = bodyState('Sun', date, observer, m);
  const moon = bodyState('Moon', date, observer, m);
  moon.phaseAngle = A.MoonPhase(date);               // 0 new, 90 first quarter, 180 full, 270 last quarter
  moon.waxing = moon.phaseAngle < 180;
  const planets = PLANETS.map((name) => bodyState(name, date, observer, m));
  return { time: date, matrix: m, sun, moon, planets, siderealHours: A.SiderealTime(date) };
}

// Sky colour phase from the Sun's altitude: 1 full day, 0 astronomical night.
export function daylight(sunAltitude) {
  const t = Math.max(0, Math.min(1, (sunAltitude + 18) / 18));
  return t * t * (3 - 2 * t);
}

export function twilightName(sunAltitude) {
  if (sunAltitude > 0) return 'day';
  if (sunAltitude > -6) return 'civil twilight';
  if (sunAltitude > -12) return 'nautical twilight';
  if (sunAltitude > -18) return 'astronomical twilight';
  return 'night';
}

export function fmtRa(hours) {
  const h = ((hours % 24) + 24) % 24;
  const hh = Math.floor(h);
  const mm = Math.floor((h - hh) * 60);
  const ss = Math.round(((h - hh) * 60 - mm) * 60);
  return `${String(hh).padStart(2, '0')}h ${String(mm).padStart(2, '0')}m ${String(ss).padStart(2, '0')}s`;
}

export function fmtDec(deg) {
  const sign = deg < 0 ? '-' : '+';
  const a = Math.abs(deg);
  const dd = Math.floor(a);
  const mm = Math.floor((a - dd) * 60);
  return `${sign}${String(dd).padStart(2, '0')}° ${String(mm).padStart(2, '0')}′`;
}
