#!/usr/bin/env python3
"""Build the compact data files of the Living Observatory website (site/data/*.json).

    python scripts/build_site_data.py [--cache DIR] [--out DIR]

Inputs (downloaded once into the cache directory, never at run time of the site):
  * Yale Bright Star Catalog 5 (bsc5-short.json, brettonw/YaleBrightStarCatalog)
  * d3-celestial mw.json and constellations.lines.json (BSD 3-clause, ofrohn/d3-celestial)
  * config/observatory.json (the observatory's location)

Outputs, all deterministic (sorted, fixed precision, no timestamps), so running it twice gives identical bytes:
  * site.json            location of the observatory
  * stars.json           {"cols": [...], "stars": [[ra_deg, dec_deg, mag, kelvin]...], "names": [[index, name]...]}
  * milkyway.json        {"levels": [[ring, ...], ...]} with rings as flat [lon, lat, lon, lat...] lists; lon is in
                         -180..180 and equals the right ascension in degrees (J2000), as in d3-celestial
  * constellations.json  {"constellations": [{"id": "Ori", "lines": [[ra, dec, ra, dec...]...]}...]}, ra in 0..360
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sys
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
SOURCES = {
    'bsc5-short.json': 'https://raw.githubusercontent.com/brettonw/YaleBrightStarCatalog/master/bsc5-short.json',
    'mw.json': 'https://raw.githubusercontent.com/ofrohn/d3-celestial/master/data/mw.json',
    'constellations.lines.json': 'https://raw.githubusercontent.com/ofrohn/d3-celestial/master/data/constellations.lines.json',
}
MAX_MAG = 6.0
MW_TOLERANCE_DEG = 0.4        # Douglas-Peucker tolerance for the Milky Way contours
DEFAULT_KELVIN = 0            # 0 means "unknown"; the browser substitutes a sun-like colour

_RA = re.compile(r'^\s*(\d+)h\s*(\d+)m\s*([\d.]+)s\s*$')
_DEC = re.compile(r'^\s*([+-])\s*(\d+)°\s*(\d+)′\s*([\d.]+)″\s*$')


def parse_ra(text):
    """'00h 05m 09.9s' -> degrees."""
    match = _RA.match(text)
    if not match:
        raise ValueError(f'bad right ascension: {text!r}')
    hours, minutes, seconds = int(match[1]), int(match[2]), float(match[3])
    return (hours + minutes/60 + seconds/3600)*15


def parse_dec(text):
    """'-00° 30′ 11″' -> degrees; the sign comes from the text (int('-00') would lose it)."""
    match = _DEC.match(text)
    if not match:
        raise ValueError(f'bad declination: {text!r}')
    value = int(match[2]) + int(match[3])/60 + float(match[4])/3600
    return -value if match[1] == '-' else value


def build_stars(catalog, max_mag=MAX_MAG):
    """The stars brighter than max_mag, brightest first, and the names of the named ones."""
    rows = []
    for entry in catalog:
        try:
            mag = float(entry['V'])
            ra, dec = parse_ra(entry['RA']), parse_dec(entry['Dec'])
        except (KeyError, ValueError):
            continue                      # no magnitude or position: not usable
        if mag > max_mag:
            continue
        try:
            kelvin = int(round(float(entry.get('K', DEFAULT_KELVIN))/50.0))*50
        except ValueError:
            kelvin = DEFAULT_KELVIN
        name = entry.get('N') or ''
        rows.append((round(mag, 2), round(ra, 3), round(dec, 3), kelvin, name, int(entry.get('HR') or 0)))
    rows.sort(key=lambda row: (row[0], row[1], row[2], row[5]))
    stars = [[ra, dec, mag, kelvin] for mag, ra, dec, kelvin, _, _ in rows]
    names = [[index, row[4]] for index, row in enumerate(rows) if row[4]]
    return {'cols': ['ra_deg', 'dec_deg', 'mag', 'kelvin'], 'stars': stars, 'names': names}


def simplify(points, tolerance):
    """Douglas-Peucker on a polyline of (x, y) in degrees (planar; the contours are small features)."""
    if tolerance <= 0 or len(points) < 3:
        return list(points)
    keep = [False]*len(points)
    keep[0] = keep[-1] = True
    stack = [(0, len(points)-1)]
    while stack:
        first, last = stack.pop()
        (x1, y1), (x2, y2) = points[first], points[last]
        dx, dy = x2-x1, y2-y1
        length = math.hypot(dx, dy)
        worst, index = -1.0, -1
        for i in range(first+1, last):
            x, y = points[i]
            if length == 0:
                distance = math.hypot(x-x1, y-y1)
            else:
                distance = abs(dy*(x-x1) - dx*(y-y1))/length
            if distance > worst:
                worst, index = distance, i
        if worst > tolerance and index > 0:
            keep[index] = True
            stack.extend(((first, index), (index, last)))
    return [point for point, flag in zip(points, keep) if flag]


def _flat(points, digits):
    out = []
    for x, y in points:
        out.extend((round(x, digits), round(y, digits)))
    return out


def build_milkyway(collection, tolerance=MW_TOLERANCE_DEG):
    """Simplified Milky Way contour levels (outermost first) as flat rings."""
    levels = []
    for feature in sorted(collection['features'], key=lambda f: str(f['id'])):
        rings = []
        for polygon in feature['geometry']['coordinates']:
            for ring in polygon:
                points = simplify([(float(x), float(y)) for x, y in ring], tolerance)
                if len(points) >= 3:
                    rings.append(_flat(points, 1))
        levels.append(rings)
    return {'levels': levels}


def build_constellations(collection):
    """Constellation figure lines, right ascension wrapped to 0..360."""
    out = []
    for feature in sorted(collection['features'], key=lambda f: str(f['id'])):
        lines = []
        for line in feature['geometry']['coordinates']:
            points = [((float(x) + 360) % 360, float(y)) for x, y in line]
            if len(points) >= 2:
                lines.append(_flat(points, 2))
        out.append({'id': str(feature['id']), 'lines': lines})
    return {'constellations': out}


def build_site(config):
    place = config['location']
    return {'name': place['name'], 'latitude': place['latitude'], 'longitude': place['longitude'],
            'elevation_m': place['elevation_m'], 'timezone': place['timezone']}


def dumps(data):
    return json.dumps(data, separators=(',', ':'), sort_keys=True, ensure_ascii=True) + '\n'


def fetch(name, cache):
    path = Path(cache)/name
    if not path.exists():
        Path(cache).mkdir(parents=True, exist_ok=True)
        print(f'downloading {SOURCES[name]}', file=sys.stderr)
        with urllib.request.urlopen(SOURCES[name], timeout=60) as response:   # fixed https URLs, only run by hand
            path.write_bytes(response.read())
    return path


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--cache', default=os.environ.get('SITE_DATA_CACHE', str(Path.home()/'.cache'/'kushmodi-site')))
    parser.add_argument('--out', default=str(ROOT/'site'/'data'))
    args = parser.parse_args(argv)
    sources = {name: json.loads(fetch(name, args.cache).read_text(encoding='utf-8')) for name in SOURCES}
    config = json.loads((ROOT/'config'/'observatory.json').read_text(encoding='utf-8'))
    outputs = {
        'site.json': build_site(config),
        'stars.json': build_stars(sources['bsc5-short.json']),
        'milkyway.json': build_milkyway(sources['mw.json']),
        'constellations.json': build_constellations(sources['constellations.lines.json']),
    }
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    for name, data in outputs.items():
        text = dumps(data)
        (out/name).write_text(text, encoding='utf-8')
        print(f'{name}: {len(text.encode())} bytes, sha256 {hashlib.sha256(text.encode()).hexdigest()[:16]}')


if __name__ == '__main__':
    main()
