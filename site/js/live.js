// /live.json is data, never markup: it is read with fetch, every field is checked against a whitelist or a range, and
// nothing from it is ever written into the page as HTML. A missing, stale or malformed file gives the defaults.

export const SEASONS = {
  vasanta: 'Spring', grishma: 'Summer heat', varsha: 'Monsoon', sharad: 'Autumn', hemanta: 'Early winter', shishira: 'Winter',
};
// the renderer's own weather conditions (scripts/weather.py) -> text for the HUD
export const CONDITIONS = {
  clear: 'Clear', 'partly-cloudy': 'Partly cloudy', overcast: 'Overcast', fog: 'Fog', drizzle: 'Drizzle',
  rain: 'Rain', 'heavy-rain': 'Heavy rain', thunderstorm: 'Thunderstorm',
};
const MAX_AGE_MS = 12 * 3600 * 1000;

const clamp = (v, lo, hi, fallback) => (typeof v === 'number' && Number.isFinite(v) ? Math.min(hi, Math.max(lo, v)) : fallback);

// The renderer's own season calendar and targets (config/observatory.json), used when there is no live.json.
// start = month * 100 + day; the first entry also covers the days before it (the previous year's shishira).
const CALENDAR = [
  ['vasanta', 219, [0.45, 0.15, 0.45, 0.15, 0.65, 0.60]],
  ['grishma', 420, [0.25, 0.05, 0.80, 0.25, 0.45, 0.65]],
  ['varsha', 621, [0.95, 1.0, 0.55, 0.90, 0.20, 0.50]],
  ['sharad', 823, [0.85, 0.50, 0.35, 0.50, 0.50, 0.55]],
  ['hemanta', 1023, [0.60, 0.15, 0.40, 0.15, 0.80, 0.60]],
  ['shishira', 1222, [0.40, 0.05, 0.30, 0.08, 0.95, 0.65]],
];

export function seasonFor(date) {
  const ist = new Date(date.getTime() + 5.5 * 3600 * 1000);
  const v = (ist.getUTCMonth() + 1) * 100 + ist.getUTCDate();
  let found = CALENDAR[CALENDAR.length - 1];
  for (const entry of CALENDAR) if (v >= entry[1]) found = entry;
  return found;
}

export function defaults(date = new Date()) {
  const [season, , t] = seasonFor(date);
  return {
    live: false, season, greenery: t[0], wetness: t[1], haze: t[2], cloud: t[3], nightVisibility: t[4], urbanGlow: t[5],
    condition: null, temperature: null, rain: 0, thunder: false, fog: 0, windKmh: null,
  };
}

// Returns a clean settings object from whatever the file contained.
export function clean(raw, date = new Date(), now = Date.now()) {
  const out = defaults(date);
  if (!raw || typeof raw !== 'object') return out;
  const stamp = typeof raw.timestamp_utc === 'string' ? Date.parse(raw.timestamp_utc) : NaN;
  if (!Number.isFinite(stamp) || now - stamp > MAX_AGE_MS) return out;
  out.live = true;
  const season = raw.season && typeof raw.season === 'object' ? raw.season.id : null;
  if (typeof season === 'string' && Object.hasOwn(SEASONS, season)) out.season = season;
  const env = raw.environment && typeof raw.environment === 'object' ? raw.environment : {};
  out.greenery = clamp(env.greenery, 0, 1, out.greenery);
  out.wetness = clamp(env.ground_wetness, 0, 1, out.wetness);
  out.haze = clamp(env.haze, 0, 1, out.haze);
  out.cloud = clamp(env.cloud_density, 0, 1, out.cloud);
  out.nightVisibility = clamp(env.night_visibility, 0, 1, out.nightVisibility);
  out.urbanGlow = clamp(env.urban_glow, 0, 1, out.urbanGlow);
  const weather = raw.weather && typeof raw.weather === 'object' ? raw.weather : null;
  if (weather && typeof weather.condition === 'string' && Object.hasOwn(CONDITIONS, weather.condition)) {
    out.condition = weather.condition;
    out.cloud = clamp(weather.cloud_cover_pct, 0, 100, out.cloud * 100) / 100;
    out.temperature = clamp(weather.temperature_c, -20, 60, null);
    out.windKmh = clamp(weather.wind_kmh, 0, 300, null);
    const c = weather.condition;
    out.rain = c === 'heavy-rain' || c === 'thunderstorm' ? 1 : c === 'rain' ? 0.6 : c === 'drizzle' ? 0.25 : 0;
    out.thunder = c === 'thunderstorm';
    out.fog = c === 'fog' ? 1 : 0;
    if (out.rain > 0) out.wetness = Math.max(out.wetness, 0.7);
    if (c === 'overcast') out.cloud = Math.max(out.cloud, 0.85);
  }
  return out;
}

export async function loadLive(fetchImpl = fetch, now = Date.now()) {
  try {
    const response = await fetchImpl('/live.json', { cache: 'no-cache' });
    if (!response.ok) return clean(null);
    return clean(await response.json(), new Date(now), now);
  } catch (error) {
    return clean(null, new Date(now), now);
  }
}

// One short sentence for the HUD; only whitelisted words and numbers.
export function weatherText(env) {
  const parts = [];
  if (env.condition) parts.push(CONDITIONS[env.condition]);
  else if (env.cloud > 0.75) parts.push('Overcast');
  else if (env.cloud > 0.35) parts.push('Partly cloudy');
  else parts.push('Mostly clear');
  if (env.temperature !== null) parts.push(`${Math.round(env.temperature)}°C`);
  parts.push(`${Math.round(env.cloud * 100)}% cloud`);
  parts.push(SEASONS[env.season]);
  return parts.join(' · ');
}
