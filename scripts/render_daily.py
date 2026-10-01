#!/usr/bin/env python3
"""Render the daily archive: one day frame (local solar noon) and one night frame (21:00 local) per date, as WebP.

    python scripts/render_daily.py                       # today in Mumbai
    python scripts/render_daily.py --date 2026-12-14
    python scripts/render_daily.py --range 2026-12-01 2026-12-07 --out /tmp/archive

Frames for a date are rendered in a temporary directory, validated (decodes, size, not blank) and moved into place
together; archive/index.json is rewritten atomically. A lock file serializes writers. A date whose two frames
already exist and decode is skipped unless --force is given.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, time, timedelta, timezone
import fcntl
import json
import os
from pathlib import Path
import tempfile
from zoneinfo import ZoneInfo

import astronomy as ae

import build_animation as scene
import scene_state

ROOT = Path(__file__).resolve().parents[1]
MIN_WEBP_BYTES = 8_000
MIN_STDEV = 6           # a frame flatter than this is a failed render, not a scene
KINDS = ('day', 'night')


def today_local(config, now=None):
    """Today's date where the observatory is, whatever the machine's clock zone (a VPS is usually on UTC)."""
    now = now or datetime.now(timezone.utc)
    return now.astimezone(ZoneInfo(config['location']['timezone'])).date()


def frame_times(d, config):
    """(day, night) aware datetimes for date ``d``: solar noon (rounded to the minute) and the night time."""
    loc = config['location']
    tz = ZoneInfo(loc['timezone'])
    archive = config['archive']
    midnight = datetime.combine(d, time(0), tz)
    if archive['day_time'] == 'solar_noon':
        observer = ae.Observer(loc['latitude'], loc['longitude'], loc['elevation_m'])
        start = midnight.astimezone(timezone.utc)
        event = ae.SearchHourAngle(ae.Body.Sun, observer, 0, ae.Time.Make(start.year, start.month, start.day,
                                                                            start.hour, start.minute, 0), 1)
        noon = event.time.Utc().replace(tzinfo=timezone.utc).astimezone(tz)
        day = (noon+timedelta(seconds=30)).replace(second=0, microsecond=0)
    else:
        day = datetime.combine(d, time.fromisoformat(archive['day_time']), tz)
    night = datetime.combine(d, time.fromisoformat(archive['night_time']), tz)
    return day, night


def in_window(d, config):
    window = config['year_window']
    return date.fromisoformat(window['start']) <= d < date.fromisoformat(window['end'])


def frame_path(out, d, kind):
    return Path(out)/f'{d.year:04d}'/f'{d.isoformat()}-{kind}.webp'


def validate_frame(path, width):
    from PIL import Image, ImageStat
    if path.stat().st_size < MIN_WEBP_BYTES:
        raise ValueError(f'{path.name} is too small ({path.stat().st_size} bytes)')
    with Image.open(path) as image:
        image.load()
        expected = (width, round(width*scene.H/scene.W))
        if abs(image.width-expected[0]) > 1 or abs(image.height-expected[1]) > 1:
            raise ValueError(f'{path.name} is {image.size}, expected about {expected}')
        if max(ImageStat.Stat(image.convert('RGB')).stddev) < MIN_STDEV:
            raise ValueError(f'{path.name} is blank')


def is_complete(out, d, width):
    for kind in KINDS:
        try:
            validate_frame(frame_path(out, d, kind), width)
        except (OSError, ValueError):
            return False
    return True


def visible_planets(state):
    sun = state['astronomy']['sun']['altitude_deg']
    return sorted(name for name, body in state['astronomy'].get('planets', {}).items()
                  if body['altitude_deg'] > 0 and scene.in_view(body['altitude_deg'], body['azimuth_deg'])
                  and scene.planet_visibility(body['magnitude'], sun) > .02)


def _render_one(state, png, webp, width, quality):
    from PIL import Image
    svg = png.with_suffix('.svg')
    svg.write_text(scene.scene(0, False, state=state))
    scene.rasterize(svg, png, width)
    svg.unlink()
    with Image.open(png) as image:
        image.convert('RGB').save(webp, 'WEBP', quality=quality, method=6)
    png.unlink()


def render_date(d, out, config, width, quality, pool=None):
    """Render, validate and install both frames for ``d``; returns its index entry."""
    out = Path(out)
    year_dir = out/f'{d.year:04d}'
    year_dir.mkdir(parents=True, exist_ok=True)
    states = {kind: scene_state.scene_state(when, config) for kind, when in zip(KINDS, frame_times(d, config))}
    with tempfile.TemporaryDirectory(prefix='.frames-', dir=out) as directory:
        temp = Path(directory)
        jobs = [(states[kind], temp/f'{kind}.png', temp/f'{kind}.webp', width, quality) for kind in KINDS]
        if pool:
            list(pool.map(lambda job: _render_one(*job), jobs))
        else:
            for job in jobs:
                _render_one(*job)
        for kind in KINDS:
            validate_frame(temp/f'{kind}.webp', width)
        for kind in KINDS:   # only reached when both frames are valid
            os.replace(temp/f'{kind}.webp', frame_path(out, d, kind))
    night = states['night']
    return dict(date=d.isoformat(), season=night['season']['id'],
                day_time=states['day']['timestamp_local'], night_time=night['timestamp_local'],
                moon_illuminated=night['astronomy']['moon']['illuminated_fraction'],
                meteor_shower=night['sky_events']['meteor_shower'], planets_at_night=visible_planets(night),
                files={kind: dict(path=frame_path(out, d, kind).relative_to(out).as_posix(),
                                  bytes=frame_path(out, d, kind).stat().st_size) for kind in KINDS},
                renderer_version=night['renderer_version'])


def read_index(out):
    path = Path(out)/'index.json'
    return json.loads(path.read_text()) if path.exists() else dict(version=1, frames={})


def write_index(out, index):
    out = Path(out)
    index['frames'] = dict(sorted(index['frames'].items()))
    with tempfile.NamedTemporaryFile('w', dir=out, prefix='.index-', suffix='.json', delete=False) as handle:
        json.dump(index, handle, indent=1)
        handle.write('\n')
    os.replace(handle.name, out/'index.json')


def run(dates, out, config, width=None, quality=None, force=False, log=print):
    """Render every date in ``dates`` (inside the year window) under one lock; returns the dates rendered."""
    archive = config['archive']
    width, quality = width or archive['width'], quality or archive['webp_quality']
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    bad = [d for d in dates if not in_window(d, config)]
    if bad:
        raise ValueError(f'outside the year window: {", ".join(d.isoformat() for d in bad)}')
    rendered = []
    with open(out/'.lock', 'w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        index = read_index(out)
        with ThreadPoolExecutor(max_workers=2) as pool:
            for d in dates:
                if not force and is_complete(out, d, width) and d.isoformat() in index['frames']:
                    log(f'{d} already archived')
                    continue
                index['frames'][d.isoformat()] = render_date(d, out, config, width, quality, pool)
                write_index(out, index)   # after every date, so an interrupted range keeps what it finished
                rendered.append(d)
                entry = index['frames'][d.isoformat()]
                log(f'{d} {entry["season"]}: day {entry["files"]["day"]["bytes"]} B, night {entry["files"]["night"]["bytes"]} B')
    return rendered


def main():
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--date', type=date.fromisoformat, help='one local date (default: today in Mumbai)')
    group.add_argument('--range', nargs=2, type=date.fromisoformat, metavar=('START', 'END'), help='inclusive')
    parser.add_argument('--out', default=str(ROOT/'archive'))
    parser.add_argument('--width', type=int)
    parser.add_argument('--force', action='store_true', help='re-render dates that are already archived')
    args = parser.parse_args()
    config = scene_state.load_config()
    if args.range:
        start, end = args.range
        if end < start:
            parser.error('END is before START')
        dates = [start+timedelta(days=i) for i in range((end-start).days+1)]
    else:
        dates = [args.date or today_local(config)]
    run(dates, args.out, config, args.width, force=args.force)


if __name__ == '__main__':
    main()
