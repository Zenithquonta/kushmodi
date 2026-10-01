#!/usr/bin/env python3
"""Scene state for the living observatory: local time, season, astronomy, lighting and the daily seed.

Pure function of (aware datetime, config). The seed only names the local date for art variation;
astronomy never reads it. Sun and moon come from astronomy-engine for the configured observer.
"""
import argparse
from datetime import date, datetime, time, timedelta, timezone
import hashlib
import json
import math
from pathlib import Path
from zoneinfo import ZoneInfo

import astronomy as ae

CONFIG_PATH = Path(__file__).resolve().parents[1] / 'config' / 'observatory.json'
PARAMS = ('greenery', 'ground_wetness', 'haze', 'cloud_density', 'night_visibility', 'urban_glow')
TWILIGHT = ((-0.833, 'day'), (-6, 'civil'), (-12, 'nautical'), (-18, 'astronomical'))  # sun altitude floors


def load_config(path=CONFIG_PATH):
    return json.loads(Path(path).read_text())


def smoothstep(x):
    x = min(1.0, max(0.0, x))
    return x * x * (3 - 2 * x)


def _timeline(year, cfg):
    """Season starts for the previous, current and next year, in date order, so wrapping needs no special case."""
    out = [(date(y, *map(int, s['start'].split('-'))), s)
           for y in (year - 1, year, year + 1) for s in cfg['seasons']]
    return sorted(out, key=lambda item: item[0])


def _locate(d, cfg):
    line = _timeline(d.year, cfg)
    return line, max(i for i, (start, _) in enumerate(line) if start <= d)


def season_for(d, cfg=None):
    cfg = cfg or load_config()
    line, i = _locate(d, cfg)
    length = (line[i + 1][0] - line[i][0]).days
    index = (d - line[i][0]).days
    season = line[i][1]
    return {'id': season['id'], 'name': season['name'], 'day_index_in_season': index,
            'fraction': round(index / length, 4)}


def environment_for(d, cfg=None):
    """Blend season targets between season centres with smoothstep: continuous at every boundary."""
    cfg = cfg or load_config()
    line, i = _locate(d, cfg)
    centre = lambda k: line[k][0].toordinal() + (line[k + 1][0] - line[k][0]).days / 2
    x = d.toordinal()
    a, b = (i, i + 1) if x >= centre(i) else (i - 1, i)
    w = smoothstep((x - centre(a)) / (centre(b) - centre(a)))
    ta, tb = line[a][1]['target'], line[b][1]['target']
    return {p: round(min(1.0, max(0.0, ta[p] + (tb[p] - ta[p]) * w)), 4) for p in PARAMS}


def daylight(sun_altitude_deg):
    """0 at or below -12 deg, 1 at or above +10 deg, smooth and monotonic between."""
    return smoothstep((sun_altitude_deg + 12) / 22)


def twilight_label(sun_altitude_deg):
    for floor, label in TWILIGHT:
        if sun_altitude_deg >= floor:
            return label
    return 'night'


def seed_for(local_date):
    digest = hashlib.sha256(f'kushmodi-{local_date.isoformat()}'.encode()).hexdigest()
    return digest, int(digest[:16], 16)


def _ae_time(dt_utc):
    return ae.Time.Make(dt_utc.year, dt_utc.month, dt_utc.day, dt_utc.hour, dt_utc.minute,
                        dt_utc.second + dt_utc.microsecond / 1e6)


def _horizon(body, t, observer):
    eq = ae.Equator(body, t, observer, True, True)
    h = ae.Horizon(t, observer, eq.ra, eq.dec, ae.Refraction.Airless)  # geometric altitude matches the -0.833 thresholds
    return round(h.altitude, 3), round(h.azimuth, 3)


def _local(t, tz):
    return None if t is None else t.Utc().replace(tzinfo=timezone.utc).astimezone(tz).replace(microsecond=0).isoformat()


def scene_state(when, config=None):
    if when.tzinfo is None or when.utcoffset() is None:
        raise ValueError('scene_state needs a timezone-aware datetime')
    cfg = config or load_config()
    loc = cfg['location']
    tz = ZoneInfo(loc['timezone'])
    local = when.astimezone(tz)
    utc = when.astimezone(timezone.utc)
    t = _ae_time(utc)
    observer = ae.Observer(loc['latitude'], loc['longitude'], loc['elevation_m'])

    sun_alt, sun_az = _horizon(ae.Body.Sun, t, observer)
    moon_alt, moon_az = _horizon(ae.Body.Moon, t, observer)
    illum = ae.Illumination(ae.Body.Moon, t)
    midnight = _ae_time(datetime.combine(local.date(), time(0), tz).astimezone(timezone.utc))
    sun = ae.Body.Sun
    seed, seed_int = seed_for(local.date())

    return {
        'date': local.date().isoformat(),
        'time': local.strftime('%H:%M:%S'),
        'timezone': loc['timezone'],
        'timestamp_local': local.replace(microsecond=0).isoformat(),
        'timestamp_utc': utc.replace(microsecond=0).isoformat().replace('+00:00', 'Z'),
        'season': season_for(local.date(), cfg),
        'environment': environment_for(local.date(), cfg),
        'astronomy': {
            'sun': {'altitude_deg': sun_alt, 'azimuth_deg': sun_az},
            'moon': {'altitude_deg': moon_alt, 'azimuth_deg': moon_az,
                     'phase_angle_deg': round(illum.phase_angle, 3),  # 0 = full, 180 = new
                     'illuminated_fraction': round(illum.phase_fraction, 4),
                     'waxing': ae.MoonPhase(t) < 180},
            'local_sidereal_time_hours': round((ae.SiderealTime(t) + loc['longitude'] / 15) % 24, 4),
            'twilight': twilight_label(sun_alt),
            'sun_times': {  # local ISO timestamps for the local calendar date
                'civil_dawn': _local(ae.SearchAltitude(sun, observer, ae.Direction.Rise, midnight, 1, -6), tz),
                'sunrise': _local(ae.SearchRiseSet(sun, observer, ae.Direction.Rise, midnight, 1), tz),
                'sunset': _local(ae.SearchRiseSet(sun, observer, ae.Direction.Set, midnight, 1), tz),
                'civil_dusk': _local(ae.SearchAltitude(sun, observer, ae.Direction.Set, midnight, 1, -6), tz),
            },
        },
        'lighting': {'daylight': round(daylight(sun_alt), 4)},
        'seed': seed,
        'seed_int': seed_int,
        'renderer_version': cfg['renderer_version'],
    }


def main():
    parser = argparse.ArgumentParser(description='Print the observatory scene state as JSON.')
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--at', help='aware ISO timestamp, e.g. 2026-12-14T21:37:00+05:30')
    group.add_argument('--date', help='local date YYYY-MM-DD, evaluated at 21:00 local time')
    args = parser.parse_args()
    cfg = load_config()
    tz = ZoneInfo(cfg['location']['timezone'])
    if args.at:
        when = datetime.fromisoformat(args.at)
    elif args.date:
        when = datetime.combine(date.fromisoformat(args.date), time(21), tz)
    else:
        when = datetime.now(tz)
    print(json.dumps(scene_state(when, cfg), indent=2))


if __name__ == '__main__':
    main()
