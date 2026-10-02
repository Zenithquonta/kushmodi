#!/usr/bin/env python3
"""Real Mumbai weather for the live observatory (Open-Meteo, no key; stdlib only).

    python scripts/weather.py fetch --out /var/lib/observatory/weather   # on the server, every 15 minutes

The fetcher is the only part of the observatory that goes online. It keeps exactly the fields below, checks every
value against a fixed range, maps the WMO weather code to the observatory's own small set of conditions, and writes
current.json plus a 48-hour history.json atomically. The renderer never sees the provider's text, only these
validated numbers and condition names, and it falls back to the seasonal model when the data is missing or stale.
Weather data by Open-Meteo.com (CC BY 4.0).
"""
import argparse
from datetime import datetime, timedelta
import json
import os
from pathlib import Path
import tempfile
import urllib.request
from zoneinfo import ZoneInfo

URL = ('https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}'
       '&current=temperature_2m,relative_humidity_2m,precipitation,rain,weather_code,cloud_cover,'
       'wind_speed_10m,wind_gusts_10m,is_day&timezone={tz}')
MAX_BYTES = 64_000
FRESH_MINUTES = 90
HISTORY_HOURS = 48

# field -> (key in the provider's "current" block, low, high)
FIELDS = dict(temperature_c=('temperature_2m', -20, 60), humidity_pct=('relative_humidity_2m', 0, 100),
              precipitation_mm=('precipitation', 0, 300), rain_mm=('rain', 0, 300), cloud_cover_pct=('cloud_cover', 0, 100),
              wind_kmh=('wind_speed_10m', 0, 300), gust_kmh=('wind_gusts_10m', 0, 400))

# WMO weather interpretation codes -> the observatory's conditions
CONDITIONS = {0: 'clear', 1: 'clear', 2: 'partly-cloudy', 3: 'overcast', 45: 'fog', 48: 'fog',
              51: 'drizzle', 53: 'drizzle', 55: 'drizzle', 56: 'drizzle', 57: 'drizzle',
              61: 'rain', 63: 'rain', 65: 'heavy-rain', 66: 'rain', 67: 'heavy-rain',
              71: 'rain', 73: 'rain', 75: 'heavy-rain', 77: 'rain', 80: 'rain', 81: 'heavy-rain', 82: 'heavy-rain',
              85: 'rain', 86: 'heavy-rain', 95: 'thunderstorm', 96: 'thunderstorm', 99: 'thunderstorm'}
CONDITION_NAMES = frozenset(CONDITIONS.values())


class Invalid(ValueError):
    pass


def _number(value, low, high, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not low <= value <= high:
        raise Invalid(f'{name} out of range: {value!r}')
    return round(float(value), 2)


def parse(payload, timezone='Asia/Kolkata'):
    """The validated observation from an Open-Meteo response; raises Invalid on anything unexpected."""
    if not isinstance(payload, dict) or not isinstance(payload.get('current'), dict):
        raise Invalid('no current block')
    current = payload['current']
    try:
        when = datetime.fromisoformat(current['time'])
    except (KeyError, TypeError, ValueError) as error:
        raise Invalid('bad time') from error
    if when.tzinfo is None:
        when = when.replace(tzinfo=ZoneInfo(timezone))
    code = current.get('weather_code')
    if isinstance(code, bool) or not isinstance(code, int) or code not in CONDITIONS:
        raise Invalid(f'unknown weather code: {code!r}')
    if current.get('is_day') not in (0, 1):
        raise Invalid('bad is_day')
    observation = {name: _number(current.get(key), low, high, name) for name, (key, low, high) in FIELDS.items()}
    observation.update(time=when.isoformat(), weather_code=code, condition=CONDITIONS[code], is_day=current['is_day'])
    return observation


def check(observation):
    """Re-validate a stored observation (files on disk are not trusted either)."""
    if not isinstance(observation, dict):
        raise Invalid('not an observation')
    clean = {name: _number(observation.get(name), low, high, name) for name, (_, low, high) in FIELDS.items()}
    if observation.get('condition') not in CONDITION_NAMES or observation.get('weather_code') not in CONDITIONS:
        raise Invalid('bad condition')
    if CONDITIONS[observation['weather_code']] != observation['condition']:
        raise Invalid('condition does not match its code')
    when = datetime.fromisoformat(observation['time'])
    if when.tzinfo is None:
        raise Invalid('naive time')
    clean.update(time=when.isoformat(), weather_code=observation['weather_code'], condition=observation['condition'],
                 is_day=1 if observation.get('is_day') == 1 else 0)
    return clean


def fresh(observation, when, minutes=FRESH_MINUTES):
    return abs(datetime.fromisoformat(observation['time'])-when) <= timedelta(minutes=minutes)


def load_current(path, when):
    """The stored observation if it is valid and within FRESH_MINUTES of ``when``; otherwise None."""
    try:
        observation = check(json.loads(Path(path).read_text()))
    except (OSError, ValueError, KeyError, TypeError):
        return None
    return observation if fresh(observation, when) else None


def nearest(history_path, when):
    """The valid observation closest to ``when`` in the history file, if one is within FRESH_MINUTES."""
    try:
        entries = json.loads(Path(history_path).read_text())
    except (OSError, ValueError):
        return None
    best = None
    for entry in entries if isinstance(entries, list) else []:
        try:
            observation = check(entry)
        except (ValueError, KeyError, TypeError):
            continue
        gap = abs(datetime.fromisoformat(observation['time'])-when)
        if gap <= timedelta(minutes=FRESH_MINUTES) and (best is None or gap < best[0]):
            best = (gap, observation)
    return None if best is None else best[1]


def _write_atomic(path, data):
    with tempfile.NamedTemporaryFile('w', dir=path.parent, prefix=f'.{path.name}-', delete=False) as handle:
        json.dump(data, handle, indent=1)
        handle.write('\n')
    os.chmod(handle.name, 0o644)
    os.replace(handle.name, path)


def store(observation, out):
    """Write current.json and add the observation to history.json (one entry per time, last HISTORY_HOURS)."""
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    _write_atomic(out/'current.json', observation)
    try:
        history = [check(entry) for entry in json.loads((out/'history.json').read_text())]
    except (OSError, ValueError, KeyError, TypeError):
        history = []
    by_time = {entry['time']: entry for entry in history}
    by_time[observation['time']] = observation
    newest = datetime.fromisoformat(observation['time'])
    keep = [entry for entry in by_time.values()
            if newest-datetime.fromisoformat(entry['time']) <= timedelta(hours=HISTORY_HOURS)]
    _write_atomic(out/'history.json', sorted(keep, key=lambda entry: entry['time']))


def fetch(config, opener=urllib.request.urlopen):
    loc = config['location']
    url = URL.format(lat=loc['latitude'], lon=loc['longitude'], tz=loc['timezone'].replace('/', '%2F'))
    request = urllib.request.Request(url, headers={'User-Agent': 'kushmodi-observatory'})
    with opener(request, timeout=20) as response:
        body = response.read(MAX_BYTES+1)
    if len(body) > MAX_BYTES:
        raise Invalid('response too large')
    return parse(json.loads(body), loc['timezone'])


def main():
    import scene_state
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('command', choices=['fetch'])
    parser.add_argument('--out', default='weather')
    args = parser.parse_args()
    observation = fetch(scene_state.load_config())
    store(observation, args.out)
    print(f"{observation['time']} {observation['condition']} code {observation['weather_code']} "
          f"cloud {observation['cloud_cover_pct']}% rain {observation['precipitation_mm']} mm "
          f"wind {observation['wind_kmh']} km/h gusts {observation['gust_kmh']} km/h")


if __name__ == '__main__':
    main()
