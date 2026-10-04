"""The real night sky for the live observatory (Phase 17): where the stars, the Milky Way and the constellation lines
are, for one moment and one place, projected onto the observatory's dome.

Pure geometry and data, no drawing and no dependency on build_animation (the renderer passes its canvas in as a
``Dome``). The catalogue files in assets/sky/ come from scripts/sky_catalog.py and are read once.

Projection (a rectangular panorama that the Sun, Moon and planets share): the viewer faces ``dome.facing``
(azimuth in degrees, 0 = north), so the left edge is 90 degrees to the left of that and the right edge 90 degrees to
the right. Both axes are linear, so the whole picture is sky:

    x = width * (az - facing + 90) / 180        y = horizon_y - alt/top_alt * (horizon_y - top_y)

Only the front hemisphere, cos(az - facing) >= 0, exists: whatever is behind the viewer is not drawn, however high it
stands (nothing is mirrored). Polygons and lines that cross the boundary are cut exactly there (the left and right
edges of the picture).
"""
from collections import namedtuple
from datetime import datetime, timezone
import functools
import json
import math
from pathlib import Path

import astronomy as ae

SKY_DIR = Path(__file__).resolve().parents[1]/'assets'/'sky'
Dome = namedtuple('Dome', 'width horizon_y top_y top_alt facing')
EPSILON = 1e-9
HORIZON_FLOOR = -1.0        # degrees: things lower than this are below the horizon and never drawn
MW_EDGE_DEGREES = 1.5       # Milky Way and constellation edges longer than this are subdivided before projecting
LINE_EDGE_DEGREES = 4.0
ARC_STEP_DEGREES = 4.0      # step of the arc that closes a Milky Way outline along the edge of the dome


def project(alt, az, dome):
    """Scene position of the point at altitude ``alt`` and azimuth ``az`` (degrees); does not cut at the horizon
    or at the edge of the dome (use ``in_front``)."""
    d = (az-dome.facing+180) % 360-180
    return (dome.width*(d+90)/180, dome.horizon_y-alt/dome.top_alt*(dome.horizon_y-dome.top_y))


def in_front(az, facing):
    """Whether azimuth ``az`` lies in the half of the sky the viewer faces."""
    return math.cos(math.radians(az-facing)) >= -EPSILON


def to_screen(v, dome):
    """Scene position of a viewer-frame unit vector (right, forward, up)."""
    alt = math.degrees(math.asin(max(-1.0, min(1.0, v[2]))))
    side = math.degrees(math.atan2(v[0], v[1])) if v[0] or v[1] else 0.0   # the zenith has no direction
    return dome.width*(side+90)/180, dome.horizon_y-alt/dome.top_alt*(dome.horizon_y-dome.top_y)


# ---------------------------------------------------------------------------------------------------------------
# The catalogue files (read once).
# ---------------------------------------------------------------------------------------------------------------
def _unit(ra_deg, dec_deg):
    r, d = math.radians(ra_deg), math.radians(dec_deg)
    return math.cos(d)*math.cos(r), math.cos(d)*math.sin(r), math.sin(d)


GALACTIC_SOUTH = _unit(12.86, -27.13)   # the south galactic pole (J2000): outside every Milky Way outline


@functools.lru_cache(maxsize=1)
def catalogue():
    """The bright stars as tuples (x, y, z, magnitude, kelvin, hr) of J2000 unit vectors, brightest first, and the
    proper names {hr: name}."""
    data = json.loads((SKY_DIR/'stars.json').read_text())
    stars = [(*_unit(ra, dec), mag, kelvin, hr) for ra, dec, mag, kelvin, hr in data['stars']]
    return stars, {int(hr): name for hr, name in data['names'].items()}


@functools.lru_cache(maxsize=1)
def milky_way():
    """The five outline levels, each a list of rings of J2000 unit-vector tuples."""
    data = json.loads((SKY_DIR/'milkyway.json').read_text())
    return [[[_unit(ra, dec) for ra, dec in ring] for ring in rings] for rings in data['levels']]


@functools.lru_cache(maxsize=1)
def constellation_lines():
    """The constellation stick figures: polylines of J2000 unit-vector tuples."""
    data = json.loads((SKY_DIR/'constellations.json').read_text())
    return [[_unit(ra, dec) for ra, dec in line] for line in data['lines']]


def star_name(hr):
    """The star's proper name, else its Harvard Revised number ('HR 5460')."""
    return catalogue()[1].get(hr) or f'HR {hr}'


# ---------------------------------------------------------------------------------------------------------------
# The sky for one moment and place.
# ---------------------------------------------------------------------------------------------------------------
class Sky:
    """Converts J2000 unit vectors into the viewer's frame at one UTC moment for one observer.

    Precession and nutation come from astronomy-engine (J2000 mean equator to the true equator of date); the local
    sidereal time turns that into hour angle. Refraction is ignored, like the Sun's and Moon's altitudes."""

    def __init__(self, utc, latitude, longitude, facing):
        if utc.tzinfo is None:
            raise ValueError('Sky needs an aware datetime')
        utc = utc.astimezone(timezone.utc)
        t = ae.Time.Make(utc.year, utc.month, utc.day, utc.hour, utc.minute, utc.second+utc.microsecond/1e6)
        self.rot = ae.Rotation_EQJ_EQD(t).rot
        lst = math.radians((ae.SiderealTime(t)*15+longitude) % 360)
        self.cos_l, self.sin_l = math.cos(lst), math.sin(lst)
        phi = math.radians(latitude)
        self.cos_p, self.sin_p = math.cos(phi), math.sin(phi)
        face = math.radians(facing)
        self.cos_f, self.sin_f = math.cos(face), math.sin(face)

    def enu(self, v):
        """(east, north, up) of a J2000 unit vector."""
        r = self.rot
        x = r[0][0]*v[0]+r[1][0]*v[1]+r[2][0]*v[2]    # AstroEngine rotations act on the column index
        y = r[0][1]*v[0]+r[1][1]*v[1]+r[2][1]*v[2]
        z = r[0][2]*v[0]+r[1][2]*v[1]+r[2][2]*v[2]
        hx = x*self.cos_l+y*self.sin_l                # cos(dec) cos(hour angle)
        hy = y*self.cos_l-x*self.sin_l                # cos(dec) sin(ra - sidereal time) = east
        return hy, z*self.cos_p-hx*self.sin_p, z*self.sin_p+hx*self.cos_p

    def viewer(self, v):
        """(right, forward, up) of a J2000 unit vector for a viewer facing ``facing``."""
        e, n, u = self.enu(v)
        return e*self.cos_f-n*self.sin_f, n*self.cos_f+e*self.sin_f, u

    def horizontal(self, ra_deg, dec_deg):
        """(altitude, azimuth) in degrees of a J2000 position."""
        e, n, u = self.enu(_unit(ra_deg, dec_deg))
        return math.degrees(math.asin(max(-1.0, min(1.0, u)))), math.degrees(math.atan2(e, n)) % 360


@functools.lru_cache(maxsize=16)
def sky_for(utc_text, latitude, longitude, facing):
    """A ``Sky`` for an ISO UTC time (cached: one render asks for it several times)."""
    return Sky(datetime.fromisoformat(utc_text.replace('Z', '+00:00')), latitude, longitude, facing)


# ---------------------------------------------------------------------------------------------------------------
# Cutting at the edge of the dome.
# ---------------------------------------------------------------------------------------------------------------
def _norm(v):
    length = math.sqrt(v[0]*v[0]+v[1]*v[1]+v[2]*v[2])
    return v[0]/length, v[1]/length, v[2]/length


def _angle(a, b):
    return math.degrees(math.acos(max(-1.0, min(1.0, a[0]*b[0]+a[1]*b[1]+a[2]*b[2]))))


def _between(a, b, f):
    return _norm((a[0]+(b[0]-a[0])*f, a[1]+(b[1]-a[1])*f, a[2]+(b[2]-a[2])*f))


def _cross_edge(p, q):
    """The unit vector where the great-circle edge p -> q (p in front, q behind or the reverse) meets the edge of the
    dome (forward component 0)."""
    f = p[1]/(p[1]-q[1])
    x, _, z = _between(p, q, f)
    length = math.hypot(x, z) or 1.0
    return x/length, 0.0, z/length


def densify(points, limit, closed):
    """The points with every edge longer than ``limit`` degrees split into equal pieces."""
    out = []
    count = len(points)
    for i in range(count if closed else count-1):
        a, b = points[i], points[(i+1) % count]
        out.append(a)
        pieces = int(_angle(a, b)//limit)
        out.extend(_between(a, b, k/(pieces+1)) for k in range(1, pieces+1))
    if not closed:
        out.append(points[-1])
    return out


def _cross3(a, b):
    return a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0]


def _dot(a, b):
    return a[0]*b[0]+a[1]*b[1]+a[2]*b[2]


def contains(ring, point, outside):
    """Whether ``point`` lies inside the closed ring (unit vectors). A ring on a sphere has two sides; its inside is
    the side that does not hold ``outside``, so the geodesic from the point to ``outside`` crosses it an even number
    of times exactly when the point is outside."""
    normal = _cross3(point, outside)
    if _dot(normal, normal) < 1e-12:      # the point is the very opposite of ``outside``: nudge it
        point = _norm((point[0]+1e-3, point[1], point[2]+1e-3))
        normal = _cross3(point, outside)
    count, previous = 0, _dot(normal, ring[-1])
    last = ring[-1]
    for vertex in ring:
        side = _dot(normal, vertex)
        if previous*side < 0:
            f = previous/(previous-side)
            x = tuple(last[k]+(vertex[k]-last[k])*f for k in range(3))
            if _dot(_cross3(point, x), normal) >= 0 and _dot(_cross3(x, outside), normal) >= 0:
                count += 1
        previous, last = side, vertex
    return count % 2 == 1


def _arc(a, b, ring, outside):
    """Points along the edge of the dome from a to b (both on it), excluding the ends: the way round that runs
    through the inside of ``ring`` (the polygon is closed along the edge of the dome where it leaves the front)."""
    start, end = math.atan2(a[2], a[0]), math.atan2(b[2], b[0])
    ccw = (end-start) % (2*math.pi)
    sweep = ccw
    for candidate in (ccw, ccw-2*math.pi):
        mid = start+candidate/2
        if contains(ring, (math.cos(mid), 0.0, math.sin(mid)), outside):
            sweep = candidate
            break
    else:
        sweep = ccw if ccw <= math.pi else ccw-2*math.pi
    steps = int(abs(math.degrees(sweep))//ARC_STEP_DEGREES)
    return [(math.cos(start+sweep*k/(steps+1)), 0.0, math.sin(start+sweep*k/(steps+1))) for k in range(1, steps+1)]


def clip_ring(ring, outside):
    """The part of a closed ring (viewer-frame unit vectors) in front of the viewer, as a closed ring: where the ring
    leaves the front it is closed along the edge of the dome (through the ring's inside, the side without
    ``outside``), so a filled polygon keeps its shape. A ring wholly behind the viewer gives nothing, or the whole
    dome when its inside covers the front."""
    inside = [p[1] >= 0 for p in ring]
    if not any(inside):
        if contains(ring, (0.0, 1.0, 0.0), outside):
            return [(math.cos(math.radians(a)), 0.0, math.sin(math.radians(a))) for a in range(0, 360, int(ARC_STEP_DEGREES))]
        return []
    if all(inside):
        return list(ring)
    start = inside.index(True)
    original = ring
    ring = ring[start:]+ring[:start]
    inside = inside[start:]+inside[:start]
    out, leaving, count = [], None, len(ring)
    for i in range(count):
        p, q = ring[i], ring[(i+1) % count]
        if inside[i]:
            out.append(p)
            if not inside[(i+1) % count]:
                leaving = _cross_edge(p, q)
                out.append(leaving)
        elif inside[(i+1) % count]:
            entering = _cross_edge(q, p)
            if leaving is not None:
                out.extend(_arc(leaving, entering, original, outside))
            out.append(entering)
            leaving = None
    return out


def clip_line(points):
    """The runs of an open polyline (viewer-frame unit vectors) that lie in front of the viewer, cut at the edge."""
    runs, run = [], []
    for i, p in enumerate(points):
        front = p[1] >= 0
        if front:
            if not run and i and points[i-1][1] < 0:
                run.append(_cross_edge(p, points[i-1]))
            run.append(p)
        elif run:
            run.append(_cross_edge(points[i-1], p))
            runs.append(run)
            run = []
    if run:
        runs.append(run)
    return [r for r in runs if len(r) >= 2]


# ---------------------------------------------------------------------------------------------------------------
# What is on the dome.
# ---------------------------------------------------------------------------------------------------------------
def _fmt(v):
    text = f'{v:.1f}'
    return text[:-2] if text.endswith('.0') else text


def _path(points, dome, close):
    pts = [to_screen(p, dome) for p in points]
    if len(pts) < 2:
        return ''
    return 'M'+'L'.join(f'{_fmt(x)} {_fmt(y)}' for x, y in pts)+('Z' if close else '')


def visible_stars(sky, dome):
    """Stars in front of the viewer and above the horizon, brightest first, as dicts with scene position ``x``/``y``,
    ``mag``, ``kelvin``, ``hr``, ``alt`` (degrees) and its J2000 ``ra_hours`` and ``dec_deg``."""
    out = []
    for x, y, z, mag, kelvin, hr in catalogue()[0]:
        v = sky.viewer((x, y, z))
        if v[1] < 0 or v[2] < math.sin(math.radians(HORIZON_FLOOR)):
            continue
        sx, sy = to_screen(v, dome)
        out.append(dict(x=sx, y=sy, mag=mag, kelvin=kelvin, hr=hr, alt=math.degrees(math.asin(v[2])),
                        ra_hours=math.degrees(math.atan2(y, x)) % 360/15, dec_deg=math.degrees(math.asin(z))))
    return out


def milky_way_paths(sky, dome):
    """One SVG path (even-odd fill) per brightness level, outermost first, for the part of the Milky Way in front."""
    paths = []
    outside = sky.viewer(GALACTIC_SOUTH)
    for rings in milky_way():
        d = []
        for ring in rings:
            points = [sky.viewer(p) for p in densify(ring, MW_EDGE_DEGREES, True)]
            clipped = clip_ring(points, outside)
            if len(clipped) >= 3:
                d.append(_path(clipped, dome, True))
        paths.append(''.join(d))
    return paths


def constellation_path(sky, dome):
    """The constellation lines in front of the viewer and not wholly below the horizon, as one SVG path."""
    floor = math.sin(math.radians(HORIZON_FLOOR))
    d = []
    for line in constellation_lines():
        points = [sky.viewer(p) for p in densify(line, LINE_EDGE_DEGREES, False)]
        for run in clip_line(points):
            if any(p[2] > floor for p in run):
                d.append(_path(run, dome, False))
    return ''.join(d)


@functools.lru_cache(maxsize=8)
def layout(utc_text, latitude, longitude, dome):
    """Everything the renderer draws of the real sky: ``stars`` (see ``visible_stars``), ``milky_way`` (path per
    level) and ``lines`` (one path). Cached on the moment, so a render that asks twice (or a test) pays once."""
    sky = sky_for(utc_text, latitude, longitude, dome.facing)
    return dict(stars=visible_stars(sky, dome), milky_way=milky_way_paths(sky, dome), lines=constellation_path(sky, dome))


# ---------------------------------------------------------------------------------------------------------------
# Readout text.
# ---------------------------------------------------------------------------------------------------------------
def constellation_of(ra_hours, dec_deg):
    """(name, three-letter symbol) of the IAU constellation holding a J2000 position."""
    found = ae.Constellation(ra_hours, dec_deg)
    return found.name, found.symbol


def ra_text(hours):
    """'13h29m' (J2000 right ascension, rounded to the minute)."""
    total = round(hours % 24*60) % 1440
    return f'{total//60:02d}h{total % 60:02d}m'


def dec_text(degrees):
    """'+47°11'' (declination, rounded to the arc minute)."""
    total = round(abs(degrees)*60)
    return f"{'-' if degrees < 0 else '+'}{total//60:02d}°{total % 60:02d}'"
