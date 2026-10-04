// What the telescope points at, and the text the HUD shows about the sky. Pure functions (no DOM, no three.js).
import { altAz, applyMatrix, eqjUnit, skyState } from './ephemeris.js';

const COMPASS = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW'];
export const cardinal = (az) => COMPASS[Math.round((((az % 360) + 360) % 360) / 45) % 8];

export function moonPhaseName(phaseAngle) {
  // 0 new, 90 first quarter, 180 full, 270 last quarter (Astronomy Engine's MoonPhase)
  const a = ((phaseAngle % 360) + 360) % 360;
  if (a < 11.25 || a >= 348.75) return 'New Moon';
  if (a < 78.75) return 'Waxing crescent';
  if (a < 101.25) return 'First quarter';
  if (a < 168.75) return 'Waxing gibbous';
  if (a < 191.25) return 'Full Moon';
  if (a < 258.75) return 'Waning gibbous';
  if (a < 281.25) return 'Last quarter';
  return 'Waning crescent';
}

// The bright stars (magnitude < 2.5) with names, for the telescope and the HUD.
export function brightStars(stars, maxMag = 2.5) {
  const names = new Map(stars.names.map(([i, n]) => [i, n]));
  const out = [];
  stars.stars.forEach(([ra, dec, mag], i) => {
    if (mag < maxMag) out.push({ name: names.get(i) || `Star ${i}`, ra, dec, mag, eqj: eqjUnit(ra, dec) });
  });
  const polaris = stars.stars.findIndex((_, i) => names.get(i) === 'Polaris');
  return { list: out, polaris: polaris >= 0 ? { name: 'Polaris', ra: stars.stars[polaris][0], dec: stars.stars[polaris][1], mag: stars.stars[polaris][2], eqj: eqjUnit(stars.stars[polaris][0], stars.stars[polaris][1]) } : null };
}

function starTarget(star, m) {
  const world = applyMatrix(m, star.eqj[0], star.eqj[1], star.eqj[2]);
  const { alt, az } = altAz(world);
  return { kind: 'star', name: star.name, raHours: star.ra / 15, decDeg: star.dec, altitude: alt, azimuth: az, magnitude: star.mag, world };
}

function bodyTarget(b, label) {
  return { kind: 'body', name: label || b.name, raHours: b.raHours, decDeg: b.decDeg, altitude: b.altitude, azimuth: b.azimuth, magnitude: b.magnitude, world: b.world, illuminated: b.illuminated, phaseAngle: b.phaseAngle };
}

// An observing night runs noon-to-noon in Mumbai, so midnight does not change the target.
export function observingNight(date) {
  return new Date(date.getTime() + 5.5 * 3600000 - 12 * 3600000).toISOString().slice(0, 10);
}

export function nightlyTargetPicker(bright, observer) {
  let key = '', chosen = null;
  return (date, current) => {
    const night = observingNight(date);
    if (night !== key) {
      key = night;
      const reference = skyState(new Date(`${night}T21:00:00+05:30`), observer);
      const late = skyState(new Date(`${night}T23:59:00+05:30`), observer);
      // Pick objects usable throughout the main evening session. An object that
      // eventually sets stays selected: its honest horizon status explains the wait.
      const candidates = reference.planets.filter(p => p.altitude > 15 && late.planets.find(b => b.name === p.name).altitude > 15).map(p => ({name:p.name, kind:'body'}));
      if (reference.moon.altitude > 15 && late.moon.altitude > 15 && reference.moon.illuminated > .1) candidates.push({name:'Moon',kind:'body'});
      const stars = bright.list.filter(s => !s.name.startsWith('Star ') && starTarget(s, reference.matrix).altitude > 20 && starTarget(s, late.matrix).altitude > 20).sort((a,b) => a.mag-b.mag).slice(0,5);
      candidates.push(...stars.map(s => ({name:s.name,kind:'star',star:s})));
      if (!candidates.length) {
        const fallback = bright.polaris || bright.list[0];
        candidates.push({name:fallback.name,kind:'star',star:fallback});
      }
      let hash = 2166136261;
      for (const c of night) hash = Math.imul(hash ^ c.charCodeAt(0), 16777619) >>> 0;
      chosen = candidates[hash % candidates.length];
    }
    const target = chosen.kind === 'star' ? starTarget(chosen.star, current.matrix) : bodyTarget(chosen.name === 'Moon' ? current.moon : current.planets.find(p => p.name === chosen.name), chosen.name);
    return {...target, night:key, daylight:current.sun.altitude > -4};
  };
}

// The highest of the Moon and the planets brighter than magnitude 3 above 5 degrees; otherwise the highest star
// brighter than magnitude 2 above 15 degrees; otherwise Polaris. The Sun is never a target.
export function pickTarget(state, bright) {
  const candidates = [];
  if (state.moon.altitude > 5) candidates.push(bodyTarget(state.moon, 'Moon'));
  for (const p of state.planets) if (p.altitude > 5 && p.magnitude < 3) candidates.push(bodyTarget(p));
  if (candidates.length) return candidates.reduce((a, b) => (b.altitude > a.altitude ? b : a));
  let best = null;
  for (const s of bright.list) {
    if (s.mag >= 2) continue;
    const t = starTarget(s, state.matrix);
    if (t.altitude > 15 && (!best || t.altitude > best.altitude)) best = t;
  }
  return best || starTarget(bright.polaris || bright.list[0], state.matrix);
}

// Lines for the "what is up" list: the Sun, the Moon, then planets above the horizon (highest first).
export function skyLines(state, twilight) {
  const lines = [];
  const where = (b) => `${Math.round(b.altitude)}° ${cardinal(b.azimuth)}`;
  lines.push(state.sun.altitude > 0 ? `Sun up, ${where(state.sun)}` : `Sun down, ${twilight}`);
  const pct = Math.round(state.moon.illuminated * 100);
  const phase = moonPhaseName(state.moon.phaseAngle);
  lines.push(state.moon.altitude > 0 ? `Moon ${phase}, ${pct}% lit, ${where(state.moon)}` : `Moon ${phase}, ${pct}% lit, below the horizon`);
  const up = state.planets.filter((p) => p.altitude > 0).sort((a, b) => b.altitude - a.altitude);
  for (const p of up.slice(0, 4)) lines.push(`${p.name} ${where(p)}, mag ${p.magnitude.toFixed(1)}${p.magnitude > 6.5 ? ' (telescope)' : ''}`);
  if (!up.length) lines.push('No planets above the horizon');
  return lines;
}
