#!/usr/bin/env python3
"""Real satellite passes for the live observatory: the ISS, Hubble and Tiangong over Mumbai.

    python scripts/satellites.py fetch --out /var/lib/observatory/satellites   # on the server, every 12 hours

Two halves, like the weather:

* The fetcher (the only part that goes online) asks CelesTrak for the current two-line elements of three fixed
  catalogue numbers, checks every line (length, mod-10 checksums, line numbers, catalogue number, epoch age) and
  writes tle.json atomically. Names come only from SATELLITES, never from the feed; a missing or invalid satellite
  is skipped and never stops the others. Orbital data by CelesTrak (https://celestrak.org).
* The computation (``compute``) needs no network. It propagates the stored elements with SGP4 through skyfield's
  built-in time scale (no downloads), takes the sun from astronomy-engine, models the Earth's shadow as a cylinder and
  reports, for each satellite, where it is now and its next visible pass over the observatory: a pass is visible
  while the satellite is sunlit, above 10 degrees, and the sun is more than 6 degrees below the observer's horizon.
"""
import argparse
from datetime import datetime, time, timedelta, timezone
import functools
import json
import math
import os
from pathlib import Path
import sys
import tempfile
import urllib.request
from zoneinfo import ZoneInfo

SATELLITES = {25544: 'ISS', 20580: 'HUBBLE', 48274: 'TIANGONG'}
URL = 'https://celestrak.org/NORAD/elements/gp.php?CATNR={n}&FORMAT=TLE'
MAX_BYTES = 2_000
FETCH_MAX_AGE = timedelta(days=7)    # a fresh download must have an epoch no older than this
FUTURE_SLACK = timedelta(days=1)     # ... and no further ahead of the clock than this
STALE_AFTER = timedelta(days=14)     # stored elements older than this (at render time) are ignored
LINE_LENGTH = 69
TLE_CHARACTERS = frozenset('0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ +-.')

EARTH_RADIUS_KM = 6378.137           # the shadow cylinder's radius
AU_KM = 149597870.7
MIN_ALTITUDE_DEG = 10.0
SUN_LIMIT_DEG = -6.0                 # the observer's sun must be at least this far below the horizon
STEP_S = 10                          # pass samples; the coarse track keeps every one of them
SUN_STEP_S = 300
DAY_S = 86400
COMPASS = ('N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW')


class Invalid(ValueError):
    pass


# --- elements: parsing and validation --------------------------------------------------------------------------
def checksum(line):
    """The mod-10 checksum of the first 68 characters: digits count their value, a minus sign counts one."""
    return sum(int(c) if c.isdigit() else 1 if c == '-' else 0 for c in line[:68]) % 10


def epoch_of(line1):
    """The element set's epoch (UTC) from columns 19-32 of line 1 (YYDDD.DDDDDDDD)."""
    try:
        year = int(line1[18:20])
        day = float(line1[20:32])
    except ValueError as error:
        raise Invalid('bad epoch') from error
    if not 1 <= day < 367:
        raise Invalid('epoch day out of range')
    year += 2000 if year < 57 else 1900
    # the 8 decimals of a day are good to a millisecond; whole seconds are plenty and keep the epochs readable
    return (datetime(year, 1, 1, tzinfo=timezone.utc)+timedelta(days=day-1, milliseconds=500)).replace(microsecond=0)


def check_lines(line1, line2, catnr):
    """Validate one pair of element lines for catalogue number ``catnr``; returns the epoch. Raises Invalid."""
    for number, line in ((1, line1), (2, line2)):
        if not isinstance(line, str) or len(line) != LINE_LENGTH or not set(line) <= TLE_CHARACTERS:
            raise Invalid(f'line {number} is not a {LINE_LENGTH}-character element line')
        if line[0] != str(number) or line[1] != ' ':
            raise Invalid(f'line {number} has the wrong line number')
        if not line[68].isdigit() or int(line[68]) != checksum(line):
            raise Invalid(f'line {number} fails its checksum')
    for line in (line1, line2):
        if not line[2:7].isdigit() or int(line[2:7]) != catnr:
            raise Invalid(f'catalogue number is not {catnr}')
    epoch = epoch_of(line1)
    from sgp4.api import Satrec
    try:
        sat = Satrec.twoline2rv(line1, line2)
        error, _, _ = sat.sgp4(sat.jdsatepoch, sat.jdsatepochF)
    except (ValueError, RuntimeError) as failure:   # sgp4 raises ValueError for lines it cannot read
        raise Invalid('sgp4 cannot read the elements') from failure
    if error:
        raise Invalid(f'sgp4 cannot propagate the elements (error {error})')
    return epoch


def parse(text, catnr, now):
    """The validated element set from a CelesTrak response (name line, line 1, line 2), as used on download."""
    try:
        lines = text.decode('ascii') if isinstance(text, bytes) else text
    except UnicodeDecodeError as error:
        raise Invalid('not ASCII') from error
    lines = lines.split('\n')
    if lines and lines[-1] == '':
        lines.pop()
    lines = [line.rstrip('\r') for line in lines]
    if len(lines) != 3:
        raise Invalid(f'expected a name and two element lines, got {len(lines)} lines')
    epoch = check_lines(lines[1], lines[2], catnr)
    if now-epoch > FETCH_MAX_AGE or epoch-now > FUTURE_SLACK:
        raise Invalid(f'epoch {epoch.isoformat()} is not within a week of {now.isoformat()}')
    return entry_for(catnr, lines[1], lines[2], epoch)


def entry_for(catnr, line1, line2, epoch):
    return dict(name=SATELLITES[catnr], line1=line1, line2=line2, epoch=epoch.isoformat())


def check(catnr, entry, when=None, future=FUTURE_SLACK):
    """Re-validate a stored entry (files on disk are not trusted). With ``when``, a set whose epoch is more than
    STALE_AFTER old, or more than ``future`` ahead, is refused too. The name always comes from SATELLITES."""
    if catnr not in SATELLITES or not isinstance(entry, dict):
        raise Invalid('not a known satellite')
    epoch = check_lines(entry.get('line1'), entry.get('line2'), catnr)
    if when is not None and (when-epoch > STALE_AFTER or epoch-when > future):
        raise Invalid('elements are too old or too new for this moment')
    return entry_for(catnr, entry['line1'], entry['line2'], epoch)


def load_entries(path):
    """Every valid entry in a tle.json (regardless of age), keyed by catalogue number; {} when unusable."""
    try:
        data = json.loads(Path(path).read_text())
        stored = data['satellites']
    except (OSError, ValueError, KeyError, TypeError):
        return {}
    out = {}
    for key, entry in (stored.items() if isinstance(stored, dict) else ()):
        try:
            catnr = int(key)
            out[catnr] = check(catnr, entry)
        except (ValueError, TypeError, KeyError):
            continue
    return out


def load(path, when, future=FUTURE_SLACK):
    """The stored entries that are valid and neither stale nor more than ``future`` ahead of ``when``, keyed by
    catalogue number (names from SATELLITES); None when there are none. The daily archive renders frames up to two
    days in the past and passes a wider ``future`` (SGP4 propagates backwards as well as forwards)."""
    out = {}
    for catnr, entry in load_entries(path).items():
        try:
            out[catnr] = check(catnr, entry, when, future)
        except Invalid:
            continue
    return out or None


def _write_atomic(path, data):
    with tempfile.NamedTemporaryFile('w', dir=path.parent, prefix=f'.{path.name}-', delete=False) as handle:
        json.dump(data, handle, indent=1)
        handle.write('\n')
    os.chmod(handle.name, 0o644)
    os.replace(handle.name, path)


def store(entries, out, now=None):
    """Write tle.json: the new entries over whatever valid, not yet stale entries the file already holds, so one
    failed download keeps that satellite's previous elements. Returns what was written."""
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    now = now or datetime.now(timezone.utc)
    kept = {catnr: entry for catnr, entry in load_entries(out/'tle.json').items()
            if now-datetime.fromisoformat(entry['epoch']) <= STALE_AFTER}
    for catnr, entry in entries.items():
        kept[catnr] = check(catnr, entry)
    data = dict(fetched=now.replace(microsecond=0).isoformat(),
                satellites={str(catnr): kept[catnr] for catnr in sorted(kept)})
    _write_atomic(out/'tle.json', data)
    return kept


def fetch_one(catnr, now, opener=urllib.request.urlopen):
    request = urllib.request.Request(URL.format(n=catnr), headers={'User-Agent': 'kushmodi-observatory'})
    with opener(request, timeout=20) as response:
        body = response.read(MAX_BYTES+1)
    if len(body) > MAX_BYTES:
        raise Invalid('response too large')
    return parse(body, catnr, now)


def fetch(now=None, opener=urllib.request.urlopen, pause=0, log=None):
    """The validated entries for every satellite that could be fetched. A failing satellite is reported through
    ``log`` and skipped."""
    import time as clock
    now = now or datetime.now(timezone.utc)
    found = {}
    for number, catnr in enumerate(SATELLITES):
        if number and pause:
            clock.sleep(pause)   # CelesTrak asks for a low request rate
        try:
            found[catnr] = fetch_one(catnr, now, opener)
        except (Invalid, OSError, ValueError) as error:
            if log:
                log(f'{SATELLITES[catnr]} ({catnr}) skipped: {error}')
    return found


# --- geometry ----------------------------------------------------------------------------------------------------
def in_sunlight(position_km, sun_km):
    """True where a satellite at ``position_km`` (GCRS, shape (3,) or (3, N)) is in sunlight: not inside the
    Earth's cylindrical shadow, the cylinder behind the Earth along the sun's direction with the Earth's radius."""
    import numpy as np
    position, sun = np.asarray(position_km, float), np.asarray(sun_km, float)
    hat = sun/np.linalg.norm(sun, axis=0)
    along = np.sum(position*hat, axis=0)
    off_axis = np.linalg.norm(position-along*hat, axis=0)
    return ~((along < 0) & (off_axis < EARTH_RADIUS_KM))


def compass(azimuth):
    return COMPASS[int(((azimuth % 360)+22.5)//45) % 8]


@functools.lru_cache(maxsize=1)
def _timescale():
    from skyfield.api import load as skyfield_load
    return skyfield_load.timescale()   # the built-in leap-second and delta-T data: nothing is downloaded


def _utc(when):
    return when.astimezone(timezone.utc)


def _ae_time(when):
    import astronomy as ae
    when = _utc(when)
    return ae.Time.Make(when.year, when.month, when.day, when.hour, when.minute, when.second+when.microsecond/1e6)


@functools.lru_cache(maxsize=8)
def _sun(start, seconds, loc_key):
    """The sun at ``seconds`` after ``start`` every SUN_STEP_S: (GCRS vector in km, shape (3, n); geometric altitude
    in degrees, shape (n,)) from astronomy-engine for the observer."""
    import astronomy as ae
    import numpy as np
    lat, lon, elevation = loc_key[:3]
    observer = ae.Observer(lat, lon, elevation)
    first = _ae_time(start)
    vectors, altitudes = [], []
    for k in range(int(seconds//SUN_STEP_S)+2):
        t = first.AddDays(k*SUN_STEP_S/DAY_S)
        v = ae.GeoVector(ae.Body.Sun, t, True)
        vectors.append((v.x*AU_KM, v.y*AU_KM, v.z*AU_KM))
        eq = ae.Equator(ae.Body.Sun, t, observer, True, True)
        altitudes.append(ae.Horizon(t, observer, eq.ra, eq.dec, ae.Refraction.Airless).altitude)
    return np.array(vectors).T, np.array(altitudes)


def _interp(offsets, nodes):
    """Linear interpolation of node values (every SUN_STEP_S) at ``offsets`` seconds; rows are interpolated apart."""
    import numpy as np
    grid = np.arange(nodes.shape[-1])*SUN_STEP_S
    if nodes.ndim == 1:
        return np.interp(offsets, grid, nodes)
    return np.array([np.interp(offsets, grid, row) for row in nodes])


def _satellite(entry):
    from skyfield.api import EarthSatellite
    return EarthSatellite(entry['line1'], entry['line2'], entry['name'], _timescale())


def _observer(loc_key):
    from skyfield.api import wgs84
    return wgs84.latlon(loc_key[0], loc_key[1], elevation_m=loc_key[2])


def _times(start, offsets):
    ts = _timescale()
    return ts.tt_jd(ts.from_datetime(_utc(start)).tt+offsets/DAY_S)


def look(entry, start, offsets, loc_key):
    """(altitude deg, azimuth deg, position km in GCRS, height above the ground km) of a satellite at ``offsets``
    seconds after ``start``, seen from the observer. NaN where SGP4 cannot propagate."""
    import numpy as np
    satellite, observer = _satellite(entry), _observer(loc_key)
    t = _times(start, np.asarray(offsets, float))
    with np.errstate(all='ignore'):
        topocentric = (satellite-observer).at(t)
        alt, az, _ = topocentric.altaz()
        geocentric = satellite.at(t)
        height = geocentric.subpoint().elevation.km
    return alt.degrees, az.degrees, geocentric.position.km, height


def _visible_runs(flags):
    runs, begin = [], None
    for i, flag in enumerate(flags):
        if flag and begin is None:
            begin = i
        elif not flag and begin is not None:
            runs.append((begin, i-1))
            begin = None
    if begin is not None:
        runs.append((begin, len(flags)-1))
    return runs


def _cache_root():
    root = os.environ.get('OBSERVATORY_CACHE') or os.environ.get('CACHE_DIRECTORY')
    return Path(root) if root else None


@functools.lru_cache(maxsize=1)
def _code_hash():
    """Changes with this file and the libraries it computes with, so a new version never reads old results."""
    import hashlib
    import astronomy
    import skyfield
    import sgp4
    digest = hashlib.sha256(Path(__file__).read_bytes())
    for part in (skyfield.__version__, sgp4.__version__, getattr(astronomy, '__version__', '')):
        digest.update(part.encode()+b'\0')
    return digest.hexdigest()


CACHE_PREFIX = 'satellites-'
CACHE_KEEP = timedelta(days=4)


def _cache_path(root, catnr, line1, line2, day, loc_key):
    import hashlib
    key = '\0'.join((_code_hash(), str(catnr), line1, line2, day.isoformat(), repr(loc_key)))
    return root/f'{CACHE_PREFIX}{hashlib.sha256(key.encode()).hexdigest()[:32]}.json'


def _pass_json(p):
    start, top, end, max_alt, start_az, end_az, track = p
    return [start.isoformat(), top.isoformat(), end.isoformat(), max_alt, start_az, end_az, [list(point) for point in track]]


def _pass_from_json(item):
    """A cached pass, re-validated: the cache directory is not trusted any more than the network is."""
    start, top, end = (datetime.fromisoformat(stamp) for stamp in item[:3])
    max_alt, start_az, end_az = (float(v) for v in item[3:6])
    track = tuple((int(a), float(b), float(c)) for a, b, c in item[6])
    numbers = [max_alt, start_az, end_az]+[v for point in track for v in point]
    if not (start.tzinfo and start <= top <= end and track and all(math.isfinite(v) for v in numbers)):
        raise ValueError('bad cached pass')
    if not (MIN_ALTITUDE_DEG <= max_alt <= 90 and all(0 <= az <= 360 for az in (start_az, end_az))
            and all(MIN_ALTITUDE_DEG <= alt <= 90 and 0 <= az <= 360 and 0 <= s for s, alt, az in track)):
        raise ValueError('cached pass out of range')
    return (start, top, end, max_alt, start_az, end_az, track)


def _prune(root, now):
    for path in root.glob(f'{CACHE_PREFIX}*.json'):
        try:
            if now-path.stat().st_mtime > CACHE_KEEP.total_seconds():
                path.unlink()
        except OSError:
            pass


@functools.lru_cache(maxsize=32)
def _window(catnr, line1, line2, day, loc_key):
    """Every visible pass between local noon of ``day`` and local noon the next day (see _search), cached in
    memory and, when the service has a cache directory, on disk: each render is a fresh process, and the elements
    and the night's sun do not change within an observing night."""
    root = _cache_root()
    if root is None:
        return _search(catnr, line1, line2, day, loc_key)
    path = _cache_path(root, catnr, line1, line2, day, loc_key)
    try:
        return tuple(_pass_from_json(item) for item in json.loads(path.read_text()))
    except (OSError, ValueError, TypeError, IndexError):
        pass
    passes = _search(catnr, line1, line2, day, loc_key)
    try:
        import time as clock
        root.mkdir(parents=True, exist_ok=True)
        temp = path.with_name(f'.{path.name}.{os.getpid()}.tmp')
        temp.write_text(json.dumps([_pass_json(p) for p in passes]))
        os.replace(temp, path)
        _prune(root, clock.time())
    except OSError:
        pass
    return passes


def _search(catnr, line1, line2, day, loc_key):
    """The visible passes of one window, as tuples (start, max, end, max altitude, start azimuth, end azimuth,
    track) with track = ((seconds after start, altitude, azimuth), ...) every STEP_S for the sunlit part."""
    import numpy as np
    tz = ZoneInfo(loc_key[3])
    start = datetime.combine(day, time(12), tz)
    offsets = np.arange(0, DAY_S, STEP_S, dtype=float)
    sun_km, sun_alt = _sun(start, DAY_S, loc_key)
    dark = _interp(offsets, sun_alt) < SUN_LIMIT_DEG
    entry = dict(name=SATELLITES[catnr], line1=line1, line2=line2)
    index = np.nonzero(dark)[0]
    if not len(index):
        return ()
    alt, az, position, _ = look(entry, start, offsets[index], loc_key)
    lit = in_sunlight(position, _interp(offsets[index], sun_km))
    flags = np.zeros(len(offsets), bool)
    flags[index] = (alt > MIN_ALTITUDE_DEG) & lit   # NaN compares false
    full_alt, full_az = np.zeros(len(offsets)), np.zeros(len(offsets))
    full_alt[index], full_az[index] = alt, az
    passes = []
    for first, last in _visible_runs(flags):
        rows = range(first, last+1)
        top = max(rows, key=lambda i: full_alt[i])
        stamp = lambda i: (start+timedelta(seconds=float(offsets[i]))).replace(microsecond=0)
        passes.append((stamp(first), stamp(top), stamp(last), round(float(full_alt[top]), 1),
                       round(float(full_az[first]), 1), round(float(full_az[last]), 1),
                       tuple((int(offsets[i]-offsets[first]), round(float(full_alt[i]), 1), round(float(full_az[i]), 1))
                             for i in rows)))
    return tuple(passes)


def _pass_dict(p, tz):
    start, top, end, max_alt, start_az, end_az, track = p
    iso = lambda stamp: stamp.astimezone(tz).isoformat()
    return {'start': iso(start), 'max': iso(top), 'end': iso(end), 'max_altitude_deg': max_alt,
            'start_azimuth_deg': start_az, 'end_azimuth_deg': end_az,
            'start_direction': compass(start_az), 'end_direction': compass(end_az),
            'track': [list(point) for point in track]}


def compute(tles, when, config):
    """The satellites block of the scene state, or None when no satellite could be computed.

    {NAME: {name, norad, epoch, altitude_deg, azimuth_deg, sunlit, visible, height_km, next_pass}} where next_pass is
    None or the first visible pass still to end within the next 24 hours, with its coarse track. No network."""
    import numpy as np
    loc = config['location']
    loc_key = (loc['latitude'], loc['longitude'], loc['elevation_m'], loc['timezone'])
    tz = ZoneInfo(loc['timezone'])
    when = _utc(when)
    local = when.astimezone(tz)
    first_day = (local-timedelta(hours=12)).date()
    sun_km, sun_alt = _sun(when, 0, loc_key)
    sun_now = float(sun_alt[0])
    out = {}
    for catnr, name in SATELLITES.items():
        entry = (tles or {}).get(catnr)
        if not entry:
            continue
        try:
            alt, az, position, height = look(entry, when, [0.0], loc_key)
            alt, az, height = float(alt[0]), float(az[0]), float(height[0])
            if not all(math.isfinite(v) for v in (alt, az, height)):
                continue
            sunlit = bool(in_sunlight(position[:, 0], sun_km[:, 0]))
            window = []
            for day in (first_day, first_day+timedelta(days=1)):
                window += _window(catnr, entry['line1'], entry['line2'], day, loc_key)
            upcoming = [p for p in window if p[2] > when and p[0] < when+timedelta(days=1)]
            out[name] = {'name': name, 'norad': catnr, 'epoch': entry['epoch'], 'altitude_deg': round(alt, 2),
                         'azimuth_deg': round(az, 2), 'sunlit': sunlit,
                         'visible': bool(sunlit and alt > MIN_ALTITUDE_DEG and sun_now < SUN_LIMIT_DEG),
                         'height_km': round(height), 'next_pass': _pass_dict(upcoming[0], tz) if upcoming else None}
        except Exception as error:   # one satellite's trouble never costs the picture the others
            print(f'satellites: {name} skipped: {error}', file=sys.stderr)
    return out or None


def main():
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('command', choices=['fetch'])
    parser.add_argument('--out', default='satellites')
    args = parser.parse_args()
    now = datetime.now(timezone.utc)
    found = fetch(now, pause=1, log=lambda message: print(message, file=sys.stderr))
    if not found:
        sys.exit('no satellite could be fetched; keeping the previous elements')
    kept = store(found, args.out, now)
    for catnr, entry in sorted(kept.items()):
        print(f"{entry['name']} ({catnr}) epoch {entry['epoch']}{'' if catnr in found else ' (kept from an earlier fetch)'}")


if __name__ == '__main__':
    main()
