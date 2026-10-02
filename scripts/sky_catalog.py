#!/usr/bin/env python3
"""Build the compact sky data of the live observatory (Phase 17) into assets/sky/.

    python scripts/sky_catalog.py [--cache DIR]

Three public catalogues are converted into small JSON files that the renderer (scripts/night_sky.py) reads:

    stars.json           the Yale Bright Star Catalogue (BSC5) down to magnitude 5.8
    milkyway.json        the Milky Way outline in five brightness steps (d3-celestial mw.json)
    constellations.json  the constellation stick figures (d3-celestial constellations.lines.json)
    SOURCES.md           where the data comes from, with the credit and the BSD licence text

The conversion is deterministic: the same downloads always give the same bytes. Downloads are kept in the cache
directory (default ~/.cache/observatory-sky) so a rebuild needs no network; the renderer and the tests never use it.
"""
import argparse
import json
import math
import os
from pathlib import Path
import re
import ssl
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'assets'/'sky'
HOST = 'https://raw.githubusercontent.com'    # the same data as the GitHub projects' raw files
SOURCES = {
    'bsc5-short.json': HOST+'/brettonw/YaleBrightStarCatalog/master/bsc5-short.json',
    'mw.json': HOST+'/ofrohn/d3-celestial/master/data/mw.json',
    'constellations.lines.json': HOST+'/ofrohn/d3-celestial/master/data/constellations.lines.json',
    'LICENSE': HOST+'/ofrohn/d3-celestial/master/LICENSE',
}
MAG_LIMIT = 5.8           # stars brighter than this (smaller V) are kept
NAME_LIMIT = 3.5          # proper names are kept for the stars brighter than this
MW_STEP_DEG = .45         # a Milky Way outline point is kept when it is this far from the last one kept
MW_MIN_POINTS = 4         # rings that shrink below this are dropped
SAFE_NAME = re.compile(r'^[A-Za-z][A-Za-z \-]*$')


def ra_degrees(text):
    """'18h 36m 56.3s' -> degrees."""
    h, m, s = (float(p) for p in re.findall(r'[\d.]+', text))
    return (h+m/60+s/3600)*15


def dec_degrees(text):
    """'+38° 47′ 01″' -> degrees."""
    d, m, s = (float(p) for p in re.findall(r'[\d.]+', text))
    return math.copysign(d+m/60+s/3600, -1 if text.strip().startswith('-') else 1)


def convert_stars(bsc, limit=MAG_LIMIT, name_limit=NAME_LIMIT):
    """BSC5 'short' records -> {'columns': [...], 'stars': [[ra, dec, v, kelvin, hr]...], 'names': {hr: name}}.

    Positions are J2000 degrees (3 decimals, about 4 arc seconds). Stars are sorted by magnitude (then HR number);
    a missing temperature becomes 0 (drawn white). Names are the catalogue's proper names, plain letters only."""
    rows, names = [], {}
    for record in bsc:
        try:
            v = float(record['V'])
        except (KeyError, ValueError):
            continue
        if v > limit:
            continue
        hr = int(record['HR'])
        rows.append([round(ra_degrees(record['RA']), 3), round(dec_degrees(record['Dec']), 3), round(v, 2),
                     int(record['K']) if record.get('K') else 0, hr])
        name = (record.get('N') or '').strip()
        if name and v <= name_limit and SAFE_NAME.match(name):
            names[str(hr)] = name
    rows.sort(key=lambda r: (r[2], r[4]))
    return {'epoch': 'J2000', 'limit': limit, 'columns': ['ra_deg', 'dec_deg', 'v_mag', 'kelvin', 'hr'],
            'stars': rows, 'names': dict(sorted(names.items(), key=lambda item: int(item[0])))}


def _unit(ra, dec):
    r, d = math.radians(ra), math.radians(dec)
    return math.cos(d)*math.cos(r), math.cos(d)*math.sin(r), math.sin(d)


def _apart(a, b):
    """Angle in degrees between two (ra, dec) points in degrees."""
    dot = sum(x*y for x, y in zip(_unit(*a), _unit(*b)))
    return math.degrees(math.acos(max(-1, min(1, dot))))


def thin(ring, step=MW_STEP_DEG):
    """Keep a point of a closed ring when it is at least ``step`` degrees from the last kept one."""
    kept = [ring[0]]
    for point in ring[1:]:
        if _apart(kept[-1], point) >= step:
            kept.append(point)
    return kept


def convert_milkyway(geojson, step=MW_STEP_DEG):
    """d3-celestial mw.json (MultiPolygon features ol1..ol5, outermost to brightest) -> {'levels': [[ring...]...]}.

    Each ring is a list of [ra, dec] in degrees (RA 0..360, 2 decimals) without the closing duplicate; rings that
    thin out to a sliver are dropped. The coordinates are equatorial J2000, as in the source."""
    features = sorted(geojson['features'], key=lambda f: f['id'])
    levels = []
    for feature in features:
        rings = []
        for polygon in feature['geometry']['coordinates']:
            for ring in polygon:
                points = [(lon % 360, lat) for lon, lat in ring]
                if points[0] == points[-1]:
                    points = points[:-1]
                points = thin(points, step)
                if len(points) >= MW_MIN_POINTS:
                    rings.append([[round(lon, 2), round(lat, 2)] for lon, lat in points])
        levels.append(rings)
    return {'epoch': 'J2000', 'levels': levels}


def convert_constellations(geojson):
    """d3-celestial constellations.lines.json -> {'lines': [[[ra, dec]...]...]} (RA 0..360, 3 decimals)."""
    lines = []
    for feature in sorted(geojson['features'], key=lambda f: f['id']):
        for line in feature['geometry']['coordinates']:
            lines.append([[round(lon % 360, 3), round(lat, 3)] for lon, lat in line])
    return {'epoch': 'J2000', 'lines': lines}


def dump(data):
    return json.dumps(data, separators=(',', ':'), sort_keys=True, ensure_ascii=True)+'\n'


def sources_text(license_text):
    return f"""# Sky data sources

The live observatory (`scripts/night_sky.py`) draws the real night sky for the render time and Mumbai from these
files. They are produced by `scripts/sky_catalog.py` from the public data below; nothing here is hand-edited.

| File | Content | Source |
| --- | --- | --- |
| `stars.json` | The {MAG_LIMIT}-magnitude-or-brighter stars of the Yale Bright Star Catalogue, 5th revised edition (BSC5): J2000 position, visual magnitude, colour temperature in kelvin, Harvard Revised number and proper names | Hoffleit and Warren Jr. (1991), VizieR V/50, as a JSON file by Bretton Wade: https://github.com/brettonw/YaleBrightStarCatalog (`bsc5-short.json`) |
| `milkyway.json` | The Milky Way outline in five brightness steps, thinned to {MW_STEP_DEG} degree spacing | Olaf Frohn, d3-celestial, `data/mw.json`: https://github.com/ofrohn/d3-celestial |
| `constellations.json` | The constellation stick figures | Olaf Frohn, d3-celestial, `data/constellations.lines.json` |

The star positions are J2000; the renderer applies precession and nutation for the render time.

## d3-celestial licence (BSD 3-Clause)

```text
{license_text.strip()}
```
"""


def fetch(name, cache):
    """The downloaded source file ``name``: from the cache directory, else from the network (and then cached)."""
    path = cache/name
    if not path.exists():
        context = ssl.create_default_context(cafile=os.environ.get('SSL_CERT_FILE') or None)
        with urllib.request.urlopen(SOURCES[name], context=context, timeout=120) as response:
            data = response.read()
        cache.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    return path.read_text(encoding='utf-8')


def build(cache, out=OUT):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    files = {
        'stars.json': dump(convert_stars(json.loads(fetch('bsc5-short.json', cache)))),
        'milkyway.json': dump(convert_milkyway(json.loads(fetch('mw.json', cache)))),
        'constellations.json': dump(convert_constellations(json.loads(fetch('constellations.lines.json', cache)))),
        'SOURCES.md': sources_text(fetch('LICENSE', cache)),
    }
    for name, text in files.items():
        (out/name).write_text(text, encoding='utf-8')
        print(f'{name}: {len(text.encode()):,} bytes')


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--cache', default=os.environ.get('SKY_CATALOG_CACHE') or Path.home()/'.cache'/'observatory-sky',
                        help='directory for the downloaded sources')
    args = parser.parse_args()
    build(Path(args.cache))


if __name__ == '__main__':
    main()
