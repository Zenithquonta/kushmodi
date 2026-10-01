#!/usr/bin/env python3
"""Build the observatory SVG and render a portable GIF with FFmpeg/librsvg (Pillow finds the painted stars).

The background and transparent sprites are authored with image generation.
This script composes those layers and defines their animation timelines.
"""
import argparse
import base64
from concurrent.futures import ThreadPoolExecutor
import functools
import math
from pathlib import Path
import random
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / 'assets'
W, H, PERIOD = 1672, 941, 24
GIF_WIDTH = 840  # GitHub shows the hero at about 830px, so 1000px frames only add bytes
RECTS = {
    'galaxy': ((0, 45, 510, 545), (300, 328)),
    'planet': ((512, 190, 522, 315), (784, 346)),
    'explorer': ((1035, 245, 500, 220), (1278, 346)),
    'fighter': ((64, 680, 448, 280), (288, 821)),
    'airplane': ((520, 700, 515, 205), (784, 815)),
    'moon': ((1170, 655, 300, 290), (1298, 805)),
}


def png_uri(name):
    return 'data:image/png;base64,' + base64.b64encode((ASSETS / name).read_bytes()).decode()


BACKGROUND = png_uri('observatory-background.png')
ATLAS = png_uri('space-sprites.png')


def sprite(name, width):
    (x, y, sw, sh), (ox, oy) = RECTS[name]
    scale = width / sw
    return (f'<svg x="{-(ox-x)*scale:.3f}" y="{-(oy-y)*scale:.3f}" '
            f'width="{width}" height="{sh*scale:.3f}" viewBox="{x} {y} {sw} {sh}" '
            f'overflow="hidden"><use href="#atlas" xlink:href="#atlas"/></svg>')


def _num(value, digits=3):
    """Fixed-point text without trailing zeros (and never '-0')."""
    text = f'{value:.{digits}f}'
    if '.' in text:
        text = text.rstrip('0').rstrip('.')
    return '0' if text in ('-0', '') else text


class Track:
    """One keyframed SMIL animation, evaluated identically for the SVG and the sampled raster.

    ``values`` are scalars or equal-length tuples; ``key_times`` (None = evenly spaced) run 0..1 and
    interpolation is always linear, repeating forever like ``repeatCount="indefinite"``.  A negative
    ``begin`` means the animation is already that many seconds into its cycle at t=0.  Everything is
    rounded to the precision that ``smil()`` prints, so ``at(t)`` returns exactly what a browser will
    interpolate from the markup.
    """

    def __init__(self, values, key_times=None, dur=PERIOD, begin=0, digits=3):
        rnd = lambda v: round(v, digits)+0.0
        self.values = tuple(tuple(rnd(c) for c in v) if isinstance(v, (tuple, list)) else rnd(v) for v in values)
        count = len(self.values)
        self.explicit_times = key_times is not None
        self.key_times = tuple(round(k, 6)+0.0 for k in key_times) if key_times is not None \
            else tuple(i/(count-1) for i in range(count))
        assert count >= 2 and len(self.key_times) == count
        assert self.key_times[0] == 0 and self.key_times[-1] == 1 and list(self.key_times) == sorted(self.key_times)
        assert PERIOD % dur == 0, 'every period must divide the master cycle'
        self.dur, self.digits, self.begin = dur, digits, round(begin, 4)+0.0

    @classmethod
    def sine(cls, centre, amplitude, dur, phase=0, samples=24, lift=None, digits=3):
        """Sample ``centre + amplitude*sin(2*pi*(t/dur + phase))`` (phase in cycles) into keyframes."""
        values = [centre+amplitude*math.sin(2*math.pi*i/samples) for i in range(samples)]
        values.append(values[0])  # exactly closed loop
        if lift:
            values = [lift(v) for v in values]
        return cls(values, None, dur, -phase*dur, digits)

    def at(self, t):
        u = ((t-self.begin) % self.dur)/self.dur
        times = self.key_times
        for i in range(1, len(times)):
            if u <= times[i]:
                f = 1.0 if times[i] == times[i-1] else (u-times[i-1])/(times[i]-times[i-1])
                a, b = self.values[i-1], self.values[i]
                if isinstance(a, tuple):
                    return tuple(x+(y-x)*f for x, y in zip(a, b))
                return a+(b-a)*f
        return self.values[-1]

    def text(self, value):
        return ' '.join(_num(c, self.digits) for c in value) if isinstance(value, tuple) else _num(value, self.digits)

    def smil(self, attribute, transform=None):
        """The ``<animate>`` / ``<animateTransform type=...>`` element for this track."""
        tag, kind = ('animate', '') if transform is None else ('animateTransform', f' type="{transform}"')
        times = f' keyTimes="{";".join(_num(k, 6) for k in self.key_times)}"' if self.explicit_times else ''
        begin = f' begin="{_num(self.begin, 4)}s"' if self.begin else ''
        return (f'<{tag} attributeName="{attribute}"{kind} values="{";".join(self.text(v) for v in self.values)}"'
                f'{times} dur="{self.dur}s"{begin} repeatCount="indefinite"/>')

    def value_text(self, t):
        return self.text(self.at(t))

    @classmethod
    def timeline(cls, points, base, dur=PERIOD, digits=3):
        """Keyframes given as ``(seconds, value)``; the track rests at ``base`` at both ends of the cycle.

        Hidden-state resets (a line collapsing back to its start) belong where the object is invisible.
        """
        pts = list(points)
        if pts[0][0] > 0:
            pts.insert(0, (0, base))
        if pts[-1][0] < dur:
            pts.append((dur, base))
        assert pts[0][1] == pts[-1][1], 'a looping track must end where it starts'
        return cls([v for _, v in pts], [s/dur for s, _ in pts], dur, 0, digits)


# (start phase in radians, sprite width, period in seconds); theta = 2*pi*t/period + phase.
MOONS = [(0, 39, 12), (math.pi, 28, 24)]
ORBIT = (1480, 162, 150, 66)  # projected ellipse: centre x, centre y, radii x and y


def moon_layer(phase, period, behind):
    """Opacity of one moon copy: a step track whose cycle starts at theta=pi/2 (mid near half).

    The far half (sin(theta)<0) is cycle fraction .25..75; the coincident key times make
    the switches instant steps at theta=pi and theta=0 (mod 2*pi).
    """
    begin = ((math.pi/2-phase)/(2*math.pi)*period) % period-period
    values = [0, 0, 1, 1, 0, 0] if behind else [1, 1, 0, 0, 1, 1]
    return Track(values, [0, .25, .25, .75, .75, 1], period, begin)


def moon(t, animated, phase, size, period, behind):
    theta = 2*math.pi*t/period+phase
    cx, cy, rx, ry = ORBIT
    mx, my = cx+rx*math.cos(theta), cy+ry*math.sin(theta)
    layer = moon_layer(phase, period, behind)
    fade = layer.smil('opacity') if animated else ''
    if animated:
        # Circular parameter is projected to an ellipse by scaling its parent.
        degrees = math.degrees(phase)
        body = (f'<g transform="translate({cx} {cy}) scale(1 {ry/rx:.2f})"><g transform="rotate({degrees:.3f})">'
                f'<animateTransform attributeName="transform" type="rotate" from="{degrees:.3f}" to="{degrees+360:.3f}" dur="{period}s" repeatCount="indefinite"/>'
                f'<g transform="translate({rx} 0)"><g transform="rotate({-degrees:.3f})">'
                f'<animateTransform attributeName="transform" type="rotate" from="{-degrees:.3f}" to="{-degrees-360:.3f}" dur="{period}s" repeatCount="indefinite"/>'
                f'<g transform="scale(1 {rx/ry:.5f})">{sprite("moon",size)}</g></g></g></g></g>')
    else:
        body = f'<g transform="translate({mx:.3f} {my:.3f})">{sprite("moon",size)}</g>'
    return (f'<g data-moon="{"behind" if behind else "front"}" opacity="{layer.value_text(t)}">{fade}{body}</g>')


SPIN_FADE = 8  # seconds each galaxy spends cross-dissolving into its successor at the end of its cycle
SPIN_SAMPLES = 16


def _spin_opacity(outgoing, offset):
    """Opacity track of one galaxy copy: eased so the overlapping core stays >=94% bright with normal blending.

    The outgoing copy (drawn first) fades as 1-w^2 and the incoming copy on top as 1-(1-w)^2, where w runs
    0..1 over the last SPIN_FADE seconds.  Normal blending only, because librsvg ignores plus-lighter and the
    GIF frames must match the browser.
    """
    hold = (PERIOD-SPIN_FADE)/PERIOD
    ws = [i/SPIN_SAMPLES for i in range(SPIN_SAMPLES+1)]
    curve = [1-w*w for w in ws] if outgoing else [1-(1-w)**2 for w in ws]
    return Track([curve[0]]+curve, [0]+[hold+(1-hold)*w for w in ws], PERIOD, -offset)


def slow_spin(name, width, x, y, sweep, t, animated, offset=0):
    """Turn a galaxy by only `sweep` degrees per loop.

    Copy A turns 0..sweep and dissolves away in the last SPIN_FADE seconds while copy B, drawn on top, turns
    -sweep..0 and dissolves in.  At the wrap B (fully visible at 0 deg) hands over to A (fully visible at
    0 deg), so the loop closes without a jump.  The two-armed galaxy looks almost the same half a turn apart,
    which keeps the dissolve subtle.  `offset` shifts this galaxy's cycle so two galaxies never dissolve together.
    """
    u = ((t+offset) % PERIOD)/PERIOD
    copies = []
    for start, outgoing in ((0, True), (-sweep, False)):
        fade = _spin_opacity(outgoing, offset)
        begin = f' begin="{-offset}s"' if offset else ''
        spin = (f'<animateTransform attributeName="transform" type="rotate" from="{start}" to="{start+sweep}" '
                f'dur="{PERIOD}s"{begin} repeatCount="indefinite"/>' if animated else '')
        copies.append(f'<g opacity="{fade.value_text(t)}">{fade.smil("opacity") if animated else ""}'
                      f'<g transform="rotate({_num(start+sweep*u, 4)})">{spin}{sprite(name,width)}</g></g>')
    return f'<g data-spin="{name}-{width}" transform="translate({x} {y})">{"".join(copies)}</g>'


def celestial(t, animated):
    # Half a turn per loop (the old full turn read as busy).  The small galaxy turns the other way, and its
    # cycle is offset by 12 s so the two dissolves happen at different moments.
    parts = [slow_spin('galaxy', 390, 810, 184, 180, t, animated),
             slow_spin('galaxy', 137, 1128, 228, -180, t, animated, offset=12)]
    orbit = '<ellipse cx="1480" cy="162" rx="150" ry="66" fill="none" stroke="#71d6ef" stroke-width="1.4" stroke-dasharray="3 10" opacity=".4"/>'
    parts.append(orbit)
    # Gentle +-3px bob, sampled from a sine so SMIL and the raster follow the same keyframes.
    bob = Track.sine(163, 3, 24, lift=lambda y: (1480, y))
    planet = (f'<g transform="translate({bob.value_text(t)})">{bob.smil("transform", "translate") if animated else ""}'
              f'{sprite("planet",305)}</g>')
    # Each moon is drawn twice: a copy before the planet that is visible on the far (upper, sin(theta)<0)
    # half of its orbit and a copy after it for the near half.  Complementary opacity tracks switch
    # them at theta=0 and theta=pi, where the moon is clear of the planet body.
    behind, front = [], []
    for phase, size, period in MOONS:
        behind.append(moon(t, animated, phase, size, period, True))
        front.append(moon(t, animated, phase, size, period, False))
    parts.extend(behind)
    parts.append(planet)
    parts.extend(front)
    return ''.join(parts)


# ---------------------------------------------------------------------------
# Space traffic: one route description drives both the sampled frames and SMIL.
# ---------------------------------------------------------------------------
# Quiet text block baked into the plate; no traffic may overlap it while visible.
TEXT_RECT = (30, 218, 565, 375)
VISIBLE_OPACITY = .02

# Topmost foreground (trees, van, telescope finder, workshop roof) per column,
# measured from assets/observatory-background.png and kept ~8px conservative
# (it lies above the true silhouette).  Traffic boxes must stay above it.
SKYLINE = [(0, 572), (132, 572), (138, 580), (236, 580), (244, 606), (290, 606), (298, 616), (340, 616),
           (346, 640), (700, 648), (780, 690), (792, 540), (844, 540), (850, 600), (858, 690), (1092, 690),
           (1100, 676), (1112, 636), (1162, 636), (1168, 602), (1222, 588), (1234, 550), (1292, 550),
           (1302, 568), (1450, 533), (1456, 520), (1478, 496), (1494, 458), (1512, 450), (1524, 474),
           (1540, 494), (1562, 472), (1584, 486), (1592, 498), (1606, 440), (1620, 442), (1624, 466),
           (1636, 436), (1646, 405), (1672, 402)]

# Painted (alpha > 8) extent of each atlas sprite, atlas pixels relative to its RECTS origin:
# (left, top, right, bottom).  Scaled by width/source-width to give scene-space boxes.
PAINTED = {'explorer': (-240, -89, 238, 86), 'fighter': (-210, -115, 204, 97), 'airplane': (-239, -84, 241, 59)}
BOX_PAD = 2
# Exhaust trails in the object's own frame: (left, top, right, bottom) including stroke width.
TRAIL_BOX = {'explorer': (115, -18.5, 208, 8.5), 'fighter': (44, -10, 117, 10), 'airplane': (-174, 0, -57, 2)}


def _pad_u(keys):
    """[(u, value)] held at its first/last value out to u=0 and u=1."""
    keys = list(keys)
    if keys[0][0] > 0:
        keys.insert(0, (0, keys[0][1]))
    if keys[-1][0] < 1:
        keys.append((1, keys[-1][1]))
    return keys


def _x_keys(start, end, pairs):
    """[(x, value)] along a straight route -> [(u, value)] padded to u=0 and u=1."""
    return _pad_u([((x-start)/(end-start), v) for x, v in pairs])


def _interp(keys, u):
    for (u0, v0), (u1, v1) in zip(keys, keys[1:]):
        if u <= u1:
            return v0 + (v1-v0)*(u-u0)/(u1-u0) if u1 > u0 else v1
    return keys[-1][1]


def _route(oid, sprite_name, width, y_at, fade_at, start, end, period, phase, warp=None):
    route = dict(id=oid, sprite=sprite_name, width=width, start=start, end=end, period=period, phase=phase,
                 y_keys=_x_keys(start, end, y_at), fade_keys=_x_keys(start, end, fade_at))
    if warp:
        route['warp'] = _build_warp(route, warp)
    return route


def _build_warp(route, spec):
    """Warp description -> Tracks on the route's own clock (same period and begin as its motion).

    Channels are ``[(seconds relative to the warp event, value)]``; ``spec['x']`` is the scene x of the
    event (the instant the ship has just vanished 'out', or has just finished materialising 'in').
    """
    start, end, period = route['start'], route['end'], route['period']
    u0 = (spec['x']-start)/(end-start)

    def track(pairs):
        keys = _pad_u([(u0+dt/period, v) for dt, v in pairs])
        return Track([v for _, v in keys], [u for u, _ in keys], period, -route['phase']*period)

    lines = [{**line, **{k: track(line[k]) if isinstance(line[k], list) else line[k] for k in ('x1', 'x2', 'y')}}
             for line in spec['lines']]
    return dict(kind=spec['kind'], x=spec['x'], u0=u0, span=spec['span'], nose=spec.get('nose', 0),
                stretch=track(spec['stretch']) if 'stretch' in spec else None,
                ship=track(spec['ship']), streak=track(spec['streak']), lines=lines,
                flash=({'a': track(spec['flash']['opacity']), 'pos': track(spec['flash']['pos']), 'size': spec['flash']['size']}
                       if 'flash' in spec else None))


def _at(route_start, route_end, period, x, seconds):
    """Scene x of a ship that is at ``x`` ``seconds`` later (negative: earlier) on its straight route."""
    return x+(route_end-route_start)/period*seconds


# Explorer: goes to warp.  In its last half second the hull stretches along the flight axis from the nose
# (up to 3x) while a short cyan-white streak runs ahead of the nose, then it is gone.  The ship leaves
# well right of the galaxy and the text block, so the streak never reaches TEXT_RECT.
EXPLORER_NOSE = -240*295/500  # painted left (nose) edge in the hull's frame
EXPLORER_STREAK = [(-.5, EXPLORER_NOSE), (-.3, EXPLORER_NOSE-50), (-.12, EXPLORER_NOSE-130),
                   (.08, EXPLORER_NOSE-130), (.1, EXPLORER_NOSE)]
# The jump happens at the flash (-.12 s): the sparkle peaks where the streak ends, the hull is gone 0.06 s later and
# the sparkle holds through the next frame and has faded by 0.2 s after its start.  The route stays visible a little longer so that fade can play out.
EXPLORER_WARP = dict(
    kind='out', x=980, span=.5, nose=EXPLORER_NOSE,
    stretch=[(-.5, (1, 1)), (-.3, (1.35, 1)), (-.2, (2, 1)), (-.1, (3, 1)), (.14, (3, 1)), (.2, (1, 1))],
    ship=[(-.5, 1), (-.2, 1), (-.12, .4), (-.06, 0), (.14, 0), (.2, 1)],
    streak=[(-.5, 0), (-.32, .55), (-.16, 1), (-.08, 1), (0, 0)],
    lines=[dict(y=-4, stroke='#43c6ff', width=10, opacity=.25, x1=EXPLORER_STREAK, x2=EXPLORER_NOSE+10),
           dict(y=-4, stroke='#8af0ff', width=5, opacity=.6, x1=EXPLORER_STREAK, x2=EXPLORER_NOSE+10),
           dict(y=-4, stroke='#f2ffff', width=2.4, opacity=.95, x1=EXPLORER_STREAK, x2=EXPLORER_NOSE+10)],
    # 4-point sparkle (like the star twinkles) centred on the streak's far end
    flash=dict(opacity=[(-.18, 0), (-.12, 1), (-.03, 1), (.09, 0)], pos=[(-.5, (EXPLORER_NOSE, -4)), (-.12, (EXPLORER_NOSE-130, -4)),
                                                              (.14, (EXPLORER_NOSE-130, -4))], size=13))


def _fighter_warp(x, k):
    """Fighter drops out of hyperspace: magenta/white streaks collapse into the ship over 0.4 s, then it flies on."""
    def line(y, stroke, width, back, front):
        # the streaks start spread out around the flight axis and converge on the hull as they shorten
        return dict(y=[(-.4, y*2.2*k), (0, y*.5*k)], stroke=stroke, width=width, opacity=.9,
                    x1=[(-.4, -back*k), (0, 0)], x2=[(-.4, front*k), (0, 0)])
    return dict(kind='in', x=x, span=.4,
                ship=[(-.4, 0), (-.2, 0), (0, 1)],
                streak=[(-.44, 0), (-.4, .75), (-.1, .75), (0, 0)],
                lines=[line(-12, '#ed78fc', 1.6, 55, 95), line(-2, '#fff0ff', 1.4, 65, 110),
                       line(8, '#ed78fc', 1.6, 50, 90)])


_FIGHTER_SPEED = (1840+170)/12  # px/s along the lane
# Fades are written as (x, opacity); every key is a straight segment, so SMIL keyTimes reproduce them.
ROUTES = [
    # Hero ship: flies on at full strength, then jumps to warp (see EXPLORER_WARP).
    _route('explorer', 'explorer', 295, [(1900, 338)], [(_at(1900, 490, 24, 980, .12), 1), (_at(1900, 490, 24, 980, .14), 0)], 1900, 490, 24, .31,
           warp=EXPLORER_WARP),
    # Fighters are invisible until their streaks appear 0.4 s before they finish dropping out of hyperspace.
    _route('fighter-a', 'fighter', 133, [(1840, 434)],
           [(_at(1840, -170, 12, 1250, -.44), 0), (_at(1840, -170, 12, 1250, -.4), 1)], 1840, -170, 12, .15,
           warp=_fighter_warp(1250, 1)),
    _route('fighter-b', 'fighter', 103, [(1840, 458)],
           [(_at(1840, -170, 12, 1230, -.44), 0), (_at(1840, -170, 12, 1230, -.4), 1)], 1840, -170, 12, .245,
           warp=_fighter_warp(1230, .8)),
    # Airliner stays in open sky and dissolves before the workshop roof and right-hand trees.
    _route('airplane', 'airplane', 142, [(-200, 518)], [(1180, 1), (1330, 0)], -200, 1830, 24, .23),
]
# Daily variants of the airliner (altitude, phase); index 0 is the published route. Every variant passes the same
# traffic tests as ROUTES (open sky, clear of the name, the finder and the other craft). A sweep found only 512-518 px
# safe between the fighters and the skyline, while any phase works, so the days differ mainly in when it crosses.
# The warp ships stay fixed: their choreography is tuned against each other.
AIRLINER_VARIANTS = [(518, .23), (512, .53), (518, .71), (512, .89)]


def routes_for(variant):
    """ROUTES with the airliner on one of its checked daily variants (0 is ROUTES itself)."""
    return ROUTES if variant == 0 else _airliner_routes(variant)


@functools.lru_cache(maxsize=None)
def _airliner_routes(variant):
    y, phase = AIRLINER_VARIANTS[variant]
    plane = _route('airplane', 'airplane', 142, [(-200, y)], [(1180, 1), (1330, 0)], -200, 1830, 24, phase)
    return [plane if route['id'] == 'airplane' else route for route in ROUTES]


def _stretch_box(box, nose, sx):
    return (nose+(box[0]-nose)*sx, box[1], nose+(box[2]-nose)*sx, box[3])


def _union(boxes):
    boxes = [b for b in boxes if b]
    return (min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes))


def _shift(box, x, y):
    return (box[0]+x, box[1]+y, box[2]+x, box[3]+y)


def _unshift(box, x, y):
    return _shift(box, -x, -y)


def traffic_state(t, routes=None):
    """Pure description of every traffic object at time t (seconds); ``routes`` defaults to ROUTES."""
    states = []
    for route in routes or ROUTES:
        u = (t/route['period']+route['phase']) % 1
        x = route['start']+(route['end']-route['start'])*u
        y = _interp(route['y_keys'], u)
        opacity = _interp(route['fade_keys'], u)
        l, tp, r, b = PAINTED[route['sprite']]
        scale = route['width']/RECTS[route['sprite']][0][2]
        sprite_loc = (l*scale-BOX_PAD, tp*scale-BOX_PAD, r*scale+BOX_PAD, b*scale+BOX_PAD)
        trail_loc = TRAIL_BOX[route['sprite']]
        warp, streak_box, info = route.get('warp'), None, None
        if warp:
            sx = warp['stretch'].at(t)[0] if warp['stretch'] else 1.0
            ship, streak = warp['ship'].at(t), warp['streak'].at(t)
            if sx != 1:
                sprite_loc, trail_loc = _stretch_box(sprite_loc, warp['nose'], sx), _stretch_box(trail_loc, warp['nose'], sx)
            if streak > VISIBLE_OPACITY:
                boxes = []
                for ln in warp['lines']:
                    a, c, ly = (v.at(t) if isinstance(v, Track) else v for v in (ln['x1'], ln['x2'], ln['y']))
                    h = ln.get('h', 0)
                    side = ln['width']/2 if h else 0  # a vertical bar is as wide as its stroke
                    boxes.append((min(a, c)-side, ly-h-(0 if h else ln['width']/2),
                                  max(a, c)+side, ly+h+(0 if h else ln['width']/2)))
                streak_box = _shift(_union(boxes), x, y)
            if warp['flash'] and warp['flash']['a'].at(t) > VISIBLE_OPACITY:
                fx, fy = warp['flash']['pos'].at(t)
                half = warp["flash"]["size"]/2*1.6  # the halo is the largest part
                streak_box = _shift(_union([streak_box and _unshift(streak_box, x, y),
                                            (fx-half, fy-half, fx+half, fy+half)]), x, y)
            lead, tail = (warp['span']+.05)/route['period'], .22/route['period']
            info = dict(kind=warp['kind'], sx=sx, ship=ship, streak=streak,
                        active=warp['u0']-lead <= u <= warp['u0']+tail)
        sprite_box, trail_box = _shift(sprite_loc, x, y), _shift(trail_loc, x, y)
        states.append(dict(id=route['id'], sprite=route['sprite'], width=route['width'], x=x, y=y, u=u,
                           opacity=opacity, sprite_bbox=sprite_box, trail_bbox=trail_box, streak_bbox=streak_box,
                           warp=info, bbox=_union([sprite_box, trail_box, streak_box])))
    return states


def skyline_top(x0, x1):
    """Smallest SKYLINE y over [x0, x1] clamped to the canvas (None when entirely off canvas)."""
    x0, x1 = max(x0, 0), min(x1, W)
    if x0 > x1:
        return None
    ys = [_interp_pts(SKYLINE, x0), _interp_pts(SKYLINE, x1)]
    ys += [y for x, y in SKYLINE if x0 < x < x1]
    return min(ys)


def _interp_pts(points, x):
    for (x0, y0), (x1, y1) in zip(points, points[1:]):
        if x <= x1:
            return y0+(y1-y0)*(x-x0)/(x1-x0)
    return points[-1][1]


def _trail_markup(sprite_name):
    if sprite_name == 'explorer':
        return '<path d="M115 -17H208M115 7H192" stroke="#50d8f5" stroke-width="3" opacity=".65"/>'
    if sprite_name == 'fighter':
        return '<path d="M44 -9H117M44 9H104" stroke="#ed78fc" stroke-width="2" opacity=".55"/>'
    return '<path d="M-57 1H-174" stroke="#dbf3fa" stroke-width="2" stroke-dasharray="14 7" opacity=".4"/>'


def _key_times(keys):
    return ';'.join(f'{u:.6f}' for u, _ in keys)


# Airliner navigation lights in the fuselage frame (heading right, seen from its starboard side): the far (port, red)
# wing tip peeks out above the fuselage, the near (starboard, green) lamp sits out on the near wing by the engine,
# and the white anti-collision strobe is on the fin tip.  Sizes are in scene px.
NAV_RED, NAV_GREEN, NAV_STROBE = (-26.5, -17.1), (11, 4.5), (-51.3, -22.1)
STROBE_PERIOD = 1.5  # divides the 24 s master cycle exactly (16 double flashes per loop)
# Two short flashes, 0.2 s apart; the peaks sit on 0.1 s multiples, so every 10 fps GIF frame sees either a
# full flash or none.
STROBE_KEYS = [(0, 0), (.02, 0), (.1, 1), (.18, 0), (.22, 0), (.3, 1), (.38, 0), (STROBE_PERIOD, 0)]


def nav_lights(t, animated, night=None):
    strobe = Track([v for _, v in STROBE_KEYS], [s/STROBE_PERIOD for s, _ in STROBE_KEYS], STROBE_PERIOD)
    parts = []
    for (x, y), colour, glow, phase in ((NAV_RED, '#ff3b3b', '#ff7070', 0), (NAV_GREEN, '#38ff7a', '#8dffb2', .5)):
        pulse = Track.sine(.85, .15, 3, phase)  # steady lamps with a faint breathing so they read as lamps
        parts.append(f'<g opacity="{pulse.value_text(t)}">{pulse.smil("opacity") if animated else ""}'
                     f'<rect x="{_num(x-3.5)}" y="{_num(y-3.5)}" width="7" height="7" fill="{glow}" opacity=".22"/>'
                     f'<rect x="{_num(x-1.5)}" y="{_num(y-1.5)}" width="3" height="3" fill="{colour}"/></g>')
    x, y = NAV_STROBE
    parts.append(f'<g opacity="{strobe.value_text(t)}">{strobe.smil("opacity") if animated else ""}'
                 f'<rect x="{_num(x-4)}" y="{_num(y-4)}" width="8" height="8" fill="#ffffff" opacity=".28"/>'
                 f'<rect x="{_num(x-1.5)}" y="{_num(y-1.5)}" width="3" height="3" fill="#ffffff"/></g>')
    return night_group('nav-lights', f'<g data-lights="airplane">{"".join(parts)}</g>', night)


def _warp_streaks(warp, t, animated):
    lines = []
    for line in warp['lines']:
        half = line.get('h', 0)
        coords, anim = {}, ''
        for name, key, offset in (('x1', 'x1', 0), ('x2', 'x2', 0), ('y1', 'y', -half), ('y2', 'y', half)):
            value = line[key]
            if isinstance(value, Track):
                assert not offset
                coords[name] = value.value_text(t)
                anim += value.smil(name) if animated else ''
            else:
                coords[name] = _num(value+offset)
        lines.append(f'<line x1="{coords["x1"]}" y1="{coords["y1"]}" x2="{coords["x2"]}" y2="{coords["y2"]}" '
                     f'stroke="{line["stroke"]}" stroke-width="{line["width"]}" opacity="{line["opacity"]}">{anim}</line>')
    streak = warp['streak']
    return (f'<g data-warp="{warp["kind"]}" opacity="{streak.value_text(t)}">'
            f'{streak.smil("opacity") if animated else ""}{"".join(lines)}</g>')


def _warp_flash(warp, t, animated):
    """Small 4-point sparkle at the far end of the streak (position, opacity are Tracks)."""
    flash = warp['flash']
    r, h = flash['size']/2, flash['size']/2*.3
    star = lambda k: ('M0 {a}L{h} {h}L{a} 0L{h} -{h}L0 -{a}L-{h} -{h}L-{a} 0L-{h} {h}Z'
                      .format(a=_num(r*k), h=_num(h*k)))
    pos, a = flash['pos'], flash['a']
    return (f'<g data-warp-flash="{warp["kind"]}" opacity="{a.value_text(t)}">{a.smil("opacity") if animated else ""}'
            f'<g transform="translate({pos.value_text(t)})">{pos.smil("transform", "translate") if animated else ""}'
            f'<path d="{star(1.6)}" fill="#8af0ff" opacity=".5"/><path d="{star(1)}" fill="#f2ffff"/></g></g>')


def _ship_markup(route, t, animated):
    """Exhaust + sprite, wrapped for the warp (stretch from the nose, opacity) when the route has one."""
    body = _trail_markup(route['sprite'])+sprite(route['sprite'], route['width'])
    warp = route.get('warp')
    if not warp:
        return body
    if warp['stretch']:
        nose = _num(warp['nose'])
        body = (f'<g transform="translate({nose} 0)"><g transform="scale({warp["stretch"].value_text(t)})">'
                f'{warp["stretch"].smil("transform", "scale") if animated else ""}'
                f'<g transform="translate({_num(-warp["nose"])} 0)">{body}</g></g></g>')
    ship = warp['ship']
    return f'<g opacity="{ship.value_text(t)}">{ship.smil("opacity") if animated else ""}{body}</g>'


def traffic(t, animated, night=None, routes=None):
    parts = []
    routes = routes or ROUTES
    for route, state in zip(routes, traffic_state(t, routes)):
        motion = fade = ''
        if animated:
            # Position breakpoints are the y_keys; x is linear in u so it needs no extra keys.
            times = sorted({0, 1, *(u for u, _ in route['y_keys'])})
            values = ';'.join(f'{route["start"]+(route["end"]-route["start"])*u:.3f} {_interp(route["y_keys"], u):.3f}'
                              for u in times)
            begin = f'{-route["phase"]*route["period"]:.4f}s'
            motion = (f'<animateTransform attributeName="transform" type="translate" values="{values}" '
                      f'keyTimes="{";".join(f"{u:.6f}" for u in times)}" dur="{route["period"]}s" begin="{begin}" repeatCount="indefinite"/>')
            fade = (f'<animate attributeName="opacity" values="{";".join(f"{v:.4f}" for _, v in route["fade_keys"])}" '
                    f'keyTimes="{_key_times(route["fade_keys"])}" dur="{route["period"]}s" begin="{begin}" repeatCount="indefinite"/>')
        parts.append(f'<g data-traffic="{route["id"]}" opacity="{state["opacity"]:.4f}">{fade}'
                     f'<g transform="translate({state["x"]:.3f} {state["y"]:.3f})">{motion}')
        # Exhaust is part of the moving object, rather than a fixed streak.
        parts.append(_ship_markup(route, t, animated))
        if route.get('warp'):
            parts.append(_warp_streaks(route['warp'], t, animated))
            if route['warp']['flash']:
                parts.append(_warp_flash(route['warp'], t, animated))
        if route['sprite'] == 'airplane':
            parts.append(nav_lights(t, animated, night))
        parts.append('</g></g>')
    return ''.join(parts)


# The background plate already paints a glowing wireframe cube on the wall (outline x 1438..1484, y 689..734,
# centre (1461, 711.3), measured from the bright cyan pixels).  Two cubes would show, so the painted one is
# covered by a patch made only from the plate's own wall (no new artwork, no flat fill) and the animated cube
# is drawn where the painted one was.
PAINTED_CUBE = (1438, 689, 1484, 734)
CUBE_CENTER = (1461, 709.1)  # projection centre; with the perspective below the rest-pose box is centred on (1461, 711.5)
CUBE_HALF = 15.5    # half edge
CUBE_DISTANCE = 140  # camera distance in px: weak perspective, so a face-on pose still shows nested near/far faces
CUBE_YAW0 = math.pi/4   # rest pose looks down a body diagonal, like the painted cube
CUBE_PITCH = math.radians(22)  # fixed downward tilt: top faces stay visible at every yaw
GLOW = [(7, .12), (4, .24)]    # (stroke width, opacity) of the soft under-strokes that echo the painted halo

# PATCH_TARGET is the area covered (x, y, w, h).  The wall darkens downward, so it is built from two clean strips
# of plate wall in the same columns (the vertical wall seams continue): PATCH_SOURCE (just above the cube) over
# all of it, and PATCH_LOW (just below) faded in over the lower part so the bottom edge matches the plate there.
PATCH_TARGET = (1432, 683, 60, 58)
PATCH_SOURCE = (1432, 685, 60, 3)
PATCH_LOW = (1432, 738, 60, 3)
PATCH_LOW_FADE = (716, 732)   # y where the low strip starts to show and where it is fully opaque
PATCH_FEATHER = 2


def _stretched(target, source):
    x, y, w, h = target
    sx, sy, sw, sh = source
    return (f'<svg x="{x}" y="{y}" width="{w}" height="{h}" viewBox="{sx} {sy} {sw} {sh}" '
            f'preserveAspectRatio="none" overflow="hidden"><use href="#plate" xlink:href="#plate"/></svg>')


def cube_patch():
    x, y, w, h = PATCH_TARGET
    low = (x, PATCH_LOW_FADE[0], w, y+h-PATCH_LOW_FADE[0])
    return (f'<g mask="url(#cube-feather)">{_stretched(PATCH_TARGET, PATCH_SOURCE)}</g>'
            f'<g mask="url(#cube-feather-low)">{_stretched(low, PATCH_LOW)}</g>')


def cube_points(theta):
    points=[]
    cp,sp=math.cos(CUBE_PITCH),math.sin(CUBE_PITCH)
    for x,y,z in [(-1,-1,-1),(1,-1,-1),(1,1,-1),(-1,1,-1),(-1,-1,1),(1,-1,1),(1,1,1),(-1,1,1)]:
        yaw=theta+CUBE_YAW0
        rx=x*math.cos(yaw)+z*math.sin(yaw)
        rz=-x*math.sin(yaw)+z*math.cos(yaw)   # larger rz = farther away = higher on screen
        screen_y=y*cp-rz*sp
        depth=rz*cp+y*sp                      # after the downward tilt; the top face is nearest the camera
        scale=CUBE_HALF*CUBE_DISTANCE/(CUBE_DISTANCE+depth*CUBE_HALF)
        points.append((CUBE_CENTER[0]+rx*scale,CUBE_CENTER[1]+screen_y*scale))
    return points


def workshop(t, animated):
    parts=[cube_patch()]
    edges=[(0,1),(1,2),(2,3),(3,0),(4,5),(5,6),(6,7),(7,4),(0,4),(1,5),(2,6),(3,7)]
    # Each projected vertex coordinate is one 24-pose track, shared by every edge that uses it.
    poses=[cube_points(i*2*math.pi/24) for i in range(24)]
    poses.append(poses[0])
    cube=[[Track([pose[k][axis] for pose in poses], None, 6, digits=2) for axis in (0,1)] for k in range(8)]
    # Glow first (wide faint copies of every edge, same Tracks, plain strokes so both engines agree), then the crisp edges.
    for width,opacity,colour in [(w,o,'#36bfe8') for w,o in GLOW]+[(1.8,.9,'#72f0ff')]:
        for i,j in edges:
            tracks=[('x1',cube[i][0]),('y1',cube[i][1]),('x2',cube[j][0]),('y2',cube[j][1])]
            anim=''.join(track.smil(name) for name,track in tracks) if animated else ''
            x1,y1,x2,y2=(track.value_text(t) for _,track in tracks)
            parts.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{colour}" stroke-width="{width}" '
                         f'stroke-linecap="round" opacity="{opacity}">{anim}</line>')
    nozzle=Track.sine(1335,20,3)
    parts.append(f'<rect x="{nozzle.value_text(t)}" y="727" width="9" height="5" fill="#71edff">{nozzle.smil("x") if animated else ""}</rect>')
    scan=Track.sine(749,18,6)
    parts.append(f'<rect x="1318" y="{scan.value_text(t)}" width="39" height="1.6" fill="#83eaff" opacity=".55">{scan.smil("y") if animated else ""}</rect>')
    for x,y,c,phase in [(1596,775,'#fa6cec',0),(1380,733,'#48dffc',.4),(1196,816,'#66eeeb',.7),(1505,591,'#e760e7',.2)]:
        # .35 + .65*(.5+.5*sin(2*pi*t/3 + phase)), phase in radians.
        led=Track.sine(.675,.325,3,phase/(2*math.pi))
        parts.append(f'<rect x="{x}" y="{y}" width="4" height="3" fill="{c}" opacity="{led.value_text(t)}">{led.smil("opacity") if animated else ""}</rect>')
    return ''.join(parts)


# ---------------------------------------------------------------------------
# Telescope lock-on: once per loop the telescope acquires the main galaxy (M51, the Whirlpool).
# ---------------------------------------------------------------------------
# Pixel font, 3 columns by 5 rows (a few glyphs are wider), drawn as filled rectangles so the readout looks the
# same in every renderer; <text> would depend on installed fonts.
FONT = {
    'A': ('.#.', '#.#', '###', '#.#', '#.#'), 'C': ('.##', '#..', '#..', '#..', '.##'),
    'D': ('##.', '#.#', '#.#', '#.#', '##.'), 'E': ('###', '#..', '##.', '#..', '###'),
    'G': ('.##', '#..', '#.#', '#.#', '.##'), 'K': ('#.#', '#.#', '##.', '#.#', '#.#'),
    'L': ('#..', '#..', '#..', '#..', '###'), 'M': ('#...#', '##.##', '#.#.#', '#...#', '#...#'),
    'O': ('###', '#.#', '#.#', '#.#', '###'), 'R': ('##.', '#.#', '##.', '#.#', '#.#'),
    'T': ('###', '.#.', '.#.', '.#.', '.#.'),
    '1': ('.#.', '##.', '.#.', '.#.', '###'), '2': ('##.', '..#', '.#.', '#..', '###'),
    '3': ('##.', '..#', '.#.', '..#', '##.'), '4': ('#.#', '#.#', '###', '..#', '..#'),
    '5': ('###', '#..', '##.', '..#', '##.'), '7': ('###', '..#', '.#.', '.#.', '.#.'),
    '9': ('###', '#.#', '###', '..#', '..#'),
    'h': ('#..', '#..', '##.', '#.#', '#.#'), 'm': ('.....', '.....', '####.', '#.#.#', '#.#.#'),
    '+': ('...', '.#.', '###', '.#.', '...'), '\u00b0': ('.#.', '#.#', '.#.', '...', '...'),
    "'": ('#', '#', '.', '.', '.'), '\u00b7': ('.', '.', '#', '.', '.'), ' ': ('..', '..', '..', '..', '..'),
}
CELL = 3  # scene px per font cell (1.5 px in the 840 px GIF)


def pixel_text(text, x, y, cell=CELL):
    """Filled-rectangle path for ``text`` with its top-left at (x, y); returns (d, width, height)."""
    rows, cursor = [[] for _ in range(5)], 0
    for char in text:
        glyph = FONT[char]
        for r, bits in enumerate(glyph):
            rows[r] += [cursor+c for c, ch in enumerate(bits) if ch == '#']
        cursor += len(glyph[0])+1
    d = []
    for r, cells in enumerate(rows):
        for run in _runs(sorted(cells)):
            d.append(f'M{_num(x+run[0]*cell)} {_num(y+r*cell)}h{_num((run[1]-run[0]+1)*cell)}v{cell}h{_num(-(run[1]-run[0]+1)*cell)}z')
    return ''.join(d), (cursor-1)*cell, 5*cell


def _runs(cells):
    runs = []
    for c in cells:
        if runs and runs[-1][1] == c-1:
            runs[-1][1] = c
        else:
            runs.append([c, c])
    return runs


LOCK_CORE = (810, 184)        # main galaxy core
LOCK_FROM = (811, 551)        # telescope finder, where the dotted line starts
LOCK_HALF = 44                # final half-size of the reticle
LOCK_ARM = 14                 # length of each bracket arm
LOCK_END = (810, LOCK_CORE[1]+LOCK_HALF+6)  # the dotted line stops just below the reticle
LOCK_READOUT = ("TARGET LOCK \u00b7 M51", "RA 13h29m", "DEC +47\u00b011'")  # M51 J2000: RA 13h29m52.7s, Dec +47d11m43s
LOCK_TEXT_XY = (946, 98)
LOCK_LINE_PITCH = 7*CELL
LOCK_LEADER = 'M860 134L890 106H938'
LOCK_OPACITY = (.95, .8, .8)   # readout line opacities: title a little brighter than the coordinates


def _lock_tracks():
    t = {}
    # Timeline (seconds): the dotted line grows 12.8-14.4, the reticle flies in 13.4-14.6, snaps tight at 14.75 with a
    # brighter pulse, the readout types in line by line from 14.9, everything holds until 20.0 and fades by 20.9.
    # Fighters fade in and the explorer is away around then; the old idle reticle steps aside meanwhile.
    t['line_x'] = Track.timeline([(12.8, LOCK_FROM[0]), (14.4, LOCK_END[0]), (20.9, LOCK_END[0]), (21.0, LOCK_FROM[0])], LOCK_FROM[0])
    t['line_y'] = Track.timeline([(12.8, LOCK_FROM[1]), (14.4, LOCK_END[1]), (20.9, LOCK_END[1]), (21.0, LOCK_FROM[1])], LOCK_FROM[1])
    t['line_a'] = Track.timeline([(12.8, 0), (13.1, .85), (20.0, .85), (20.9, 0)], 0)
    t['half'] = Track.timeline([(13.4, 100), (14.6, 50), (14.75, 38), (14.95, LOCK_HALF), (20.9, LOCK_HALF), (21.0, 100)], 100)
    t['ret_a'] = Track.timeline([(13.4, 0), (13.8, .65), (14.75, .9), (20.0, .9), (20.9, 0)], 0)
    t['pulse'] = Track.timeline([(14.5, 0), (14.75, 1), (15.3, 0)], 0)
    t['leader_a'] = Track.timeline([(14.9, 0), (15.3, .6), (20.0, .6), (20.9, 0)], 0)
    t['text_a'] = [Track.timeline([(15.0+.3*i, 0), (15.3+.3*i, LOCK_OPACITY[i]), (20.0, LOCK_OPACITY[i]), (20.9, 0)], 0)
                   for i in range(3)]
    # The always-on target path/reticle steps aside while the lock sequence owns the sky (no two reticles at once).
    t['idle'] = Track.timeline([(12.4, 1), (13.0, 0), (20.9, 0), (21.9, 1)], 1)
    return t


LOCK = _lock_tracks()
LOCK_LINES = []  # (path d, x, y, width, height) of each readout line
for _i, _text in enumerate(LOCK_READOUT):
    _d, _w, _h = pixel_text(_text, LOCK_TEXT_XY[0], LOCK_TEXT_XY[1]+_i*LOCK_LINE_PITCH)
    LOCK_LINES.append((_d, LOCK_TEXT_XY[0], LOCK_TEXT_XY[1]+_i*LOCK_LINE_PITCH, _w, _h))
LOCK_READOUT_BOX = (LOCK_TEXT_XY[0], LOCK_TEXT_XY[1], LOCK_TEXT_XY[0]+max(l[3] for l in LOCK_LINES),
                    LOCK_LINES[-1][2]+LOCK_LINES[-1][4])
LOCK_STROKE = 2.5
LOCK_BOX = (min(LOCK_FROM[0], LOCK_END[0])-3, LOCK_END[1]-3, max(LOCK_FROM[0], LOCK_END[0])+3, LOCK_FROM[1]+3)


def lock_state(t):
    """Boxes (x0, y0, x1, y1) and opacities of each lock-on part at time t, derived from the same tracks."""
    half = LOCK['half'].at(t)+LOCK_STROKE/2
    line_end = (LOCK['line_x'].at(t), LOCK['line_y'].at(t))
    cx, cy = LOCK_CORE
    return dict(
        line=dict(opacity=LOCK['line_a'].at(t), bbox=(min(LOCK_FROM[0], line_end[0])-3, line_end[1]-3,
                                                      max(LOCK_FROM[0], line_end[0])+3, LOCK_FROM[1]+3)),
        reticle=dict(opacity=LOCK['ret_a'].at(t), bbox=(cx-half, cy-half, cx+half, cy+half)),
        leader=dict(opacity=LOCK['leader_a'].at(t), bbox=(860-1, 106-1, 938, 134+1)),
        readout=dict(opacity=max(track.at(t) for track in LOCK['text_a']), bbox=LOCK_READOUT_BOX),
        idle=LOCK['idle'].at(t))


def lock_on(t, animated):
    anim = lambda track, name, kind=None: track.smil(name, kind) if animated else ''
    cx, cy = LOCK_CORE
    parts = []
    # dotted targeting line, drawn on by moving its end point so the dots stay put
    x2, y2 = LOCK['line_x'], LOCK['line_y']
    parts.append(f'<g data-lock="line" opacity="{LOCK["line_a"].value_text(t)}">{anim(LOCK["line_a"], "opacity")}'
                 # dark under-stroke (a dash 2 px longer than each dot on both sides) separates the dots from the bright band
                 f'<line x1="{LOCK_FROM[0]}" y1="{LOCK_FROM[1]}" x2="{x2.value_text(t)}" y2="{y2.value_text(t)}" '
                 f'stroke="#04101c" stroke-width="6" stroke-dasharray="9 3" stroke-dashoffset="2" opacity=".55">{anim(x2, "x2")}{anim(y2, "y2")}</line>'
                 f'<line x1="{LOCK_FROM[0]}" y1="{LOCK_FROM[1]}" x2="{x2.value_text(t)}" y2="{y2.value_text(t)}" '
                 f'stroke="#a8f6ff" stroke-width="3" stroke-dasharray="5 7">{anim(x2, "x2")}{anim(y2, "y2")}</line></g>')
    # reticle: four corner brackets that fly in and snap around the core; each corner is a translate of one shape
    half = LOCK['half']
    corners = []
    for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
        pose = Track([(cx+sx*h, cy+sy*h) for h in half.values], half.key_times, half.dur, half.begin, half.digits)
        arm = f'M0 0H{-sx*LOCK_ARM}M0 0V{-sy*LOCK_ARM}'
        corners.append(f'<g transform="translate({pose.value_text(t)})">{anim(pose, "transform", "translate")}'
                       f'<path d="{arm}" fill="none" stroke="#6cf4ff" stroke-width="{LOCK_STROKE}"/>'
                       f'<path d="{arm}" fill="none" stroke="#f2ffff" stroke-width="{LOCK_STROKE}" opacity="{LOCK["pulse"].value_text(t)}">'
                       f'{anim(LOCK["pulse"], "opacity")}</path></g>')
    parts.append(f'<g data-lock="reticle" opacity="{LOCK["ret_a"].value_text(t)}">{anim(LOCK["ret_a"], "opacity")}{"".join(corners)}</g>')
    parts.append(f'<g data-lock="leader" opacity="{LOCK["leader_a"].value_text(t)}">{anim(LOCK["leader_a"], "opacity")}'
                 f'<path d="{LOCK_LEADER}" fill="none" stroke="#40daed" stroke-width="1.2"/></g>')
    rows = []
    for (d, *_), track in zip(LOCK_LINES, LOCK['text_a']):
        rows.append(f'<g opacity="{track.value_text(t)}">{anim(track, "opacity")}<path d="{d}" fill="#72f0ff"/></g>')
    parts.append(f'<g data-lock="readout">{"".join(rows)}</g>')
    return ''.join(parts)


def sky_details(t, animated, seed=29):
    rng=random.Random(seed)
    parts=[]
    for i in range(32):
        x,y=rng.randint(20,1650),rng.randint(18,500)
        if 30<x<565 and 218<y<375:
            continue
        period=rng.choice([3,4,6,8])
        phase=rng.random()
        twinkle=Track.sine(.6,.4,period,phase)
        parts.append(f'<path d="M{x-3} {y}h6M{x} {y-3}v6" stroke="#a7deff" stroke-width="1.4" opacity="{twinkle.value_text(t)}">'
                     f'{twinkle.smil("opacity") if animated else ""}</path>')
    idle=LOCK['idle']
    parts.append(f'<g data-idle="target" opacity="{idle.value_text(t)}">{idle.smil("opacity") if animated else ""}'
                 '<path d="M811 551L1020 97L1460 133" fill="none" stroke="#40daed" stroke-width="1.6" stroke-dasharray="6 11" opacity=".38"/>')
    reticle=Track.sine(.5,.3,3)
    parts.append(f'<g opacity="{reticle.value_text(t)}">{reticle.smil("opacity") if animated else ""}'
                 '<path d="M996 94V72H1013M1028 72H1045V94M1045 104V121H1028M1013 121H996V104" fill="none" stroke="#4ae8f2" stroke-width="2"/></g></g>')
    parts.append(lock_on(t,animated))
    u=(t/12)%1
    mx,my=1100+390*u,380+150*u
    # Meteor is visible for the first 16% of its 12s cycle: sin^2 fade-in/out, then hidden.
    steps=24
    meteor=Track([math.sin(math.pi*i/steps)**2 for i in range(steps+1)]+[0],
                 [.16*i/steps for i in range(steps+1)]+[1],12)
    move=('<animateTransform attributeName="transform" type="translate" from="1100 380" to="1490 530" dur="12s" repeatCount="indefinite"/>' if animated else '')
    parts.append(f'<g transform="translate({mx:.3f} {my:.3f})" opacity="{meteor.value_text(t)}">{move}{meteor.smil("opacity") if animated else ""}'
                 '<path d="M-58 -23L0 0" stroke="#88e4fc" stroke-width="2"/><rect x="-2" y="-2" width="4" height="4" fill="#ebfdff"/></g>')
    return ''.join(parts)


# ---------------------------------------------------------------------------
# Living sky: painted stars twinkle, shooting stars streak by, a satellite drifts over.
# ---------------------------------------------------------------------------
# Regions where twinkles and meteors must not appear: the name block, the telescope, the workshop,
# everything at or below the horizon, and the lock-on readout.
QUIET = [(20, 205, 575, 390), (735, 535, 885, 941), (1150, 470, 1672, 941), (0, 560, 1672, 941),
         tuple(v+d for v, d in zip(LOCK_READOUT_BOX, (-12, -12, 12, 12)))]
TWINKLE_COUNT = 110
TWINKLE_BIG = 45  # the brightest stars pulse slowly and widely, the rest flicker faster


def quiet(x, y, pad=0):
    return any(x0-pad <= x <= x1+pad and y0-pad <= y <= y1+pad for x0, y0, x1, y1 in QUIET)


@functools.lru_cache(maxsize=1)
def bright_stars():
    """The brightest painted stars of the background plate as (x, y, big, star_rgb, sky_rgb), brightest first."""
    from PIL import Image, ImageFilter
    image = Image.open(ASSETS/'observatory-background.png').convert('RGB')
    lum = image.convert('L')
    lp, pp, rgb = lum.load(), lum.filter(ImageFilter.MaxFilter(9)).load(), image.load()
    candidates = []
    for y in range(8, 560):
        for x in range(8, W-8):
            v = lp[x, y]
            if v < 200 or v != pp[x, y] or quiet(x, y, 10):
                continue
            base = sorted(lp[x+dx, y+dy] for dx, dy in [(-11, 0), (11, 0), (0, -11), (0, 11), (-8, -8), (8, 8), (-8, 8), (8, -8)])[3]
            if v-base < 80:
                continue
            energy = sum(max(0, lp[x+i, y+j]-base-40) for i in range(-6, 7) for j in range(-6, 7))
            candidates.append((energy, x, y))
    candidates.sort(reverse=True)
    kept = []
    for energy, x, y in candidates:
        if all((x-a)**2+(y-b)**2 > 16**2 for _, a, b in kept):
            kept.append((energy, x, y))
    stars = []
    for i, (_, x, y) in enumerate(kept[:TWINKLE_COUNT]):
        ring = [rgb[x+dx, y+dy] for dx, dy in [(-12, 0), (12, 0), (0, -12), (0, 12), (-9, -9), (9, 9), (-9, 9), (9, -9)]]
        sky = tuple(sorted(c[k] for c in ring)[3] for k in range(3))
        core = [rgb[x+dx, y+dy] for dx in (-2, 0, 2) for dy in (-2, 0, 2)]
        tint = tuple(min(255, int(sum(c[k] for c in core)/len(core)*.6+110)) for k in range(3))
        stars.append((x, y, i < TWINKLE_BIG, tint, sky))
    return stars


def _wave(u, phase2):
    a = 2*math.pi*u
    return .75*math.sin(a)+.25*math.sin(2*a+2*math.pi*phase2)


@functools.lru_cache(maxsize=4)
def twinkle_plan(seed=41):
    """Per star: position, colours, sparkle size and its dim/flare opacity tracks (12 keyframes per period).

    The stars are always the painted ones; the seed only changes their rhythm, phase and sparkle size."""
    rng = random.Random(seed)
    plan = []
    for x, y, big, tint, sky in bright_stars():
        period = rng.choice([3, 4, 6] if big else [1.5, 2, 3])
        phase, phase2 = rng.random(), rng.random()
        arm = rng.choice([10, 12, 14]) if big else rng.choice([5, 6])
        dim_peak, flare_peak = (.8, 1) if big else (.9, .75)
        waves = [_wave(i/12, phase2) for i in range(12)]
        waves.append(waves[0])
        dim = Track([dim_peak*max(0, -w) for w in waves], None, period, -phase*period)
        flare = Track([flare_peak*max(0, w)**1.5 for w in waves], None, period, -phase*period)
        plan.append((x, y, big, '#%02x%02x%02x' % tint, '#%02x%02x%02x' % sky, arm, dim, flare))
    return plan


def twinkle_defs(seed=41):
    return ''.join(f'<radialGradient id="tw{k}"><stop offset="0" stop-color="{sky}"/><stop offset=".55" stop-color="{sky}" stop-opacity=".95"/>'
                   f'<stop offset="1" stop-color="{sky}" stop-opacity="0"/></radialGradient>'
                   for k, (*_, sky, _arm, _dim, _flare) in enumerate(twinkle_plan(seed)))


def twinkles(t, animated, seed=41):
    """Each painted star alternately fades toward the surrounding sky and flares into a small pixel sparkle."""
    anim = lambda track: track.smil('opacity') if animated else ''
    dims, flares = [], []
    for k, (x, y, big, tint, sky, arm, dim, flare) in enumerate(twinkle_plan(seed)):
        r = 7 if big else 4.5
        diag = arm*.45
        dims.append(f'<g opacity="{dim.value_text(t)}">{anim(dim)}<circle cx="{x}" cy="{y}" r="{r}" fill="url(#tw{k})"/></g>')
        flares.append(f'<g opacity="{flare.value_text(t)}">{anim(flare)}<circle cx="{x}" cy="{y}" r="{arm*.55:.1f}" fill="{tint}" opacity=".22"/>'
                      f'<path d="M{x-arm} {y}H{x+arm}M{x} {y-arm}V{y+arm}" stroke="{tint}" stroke-width="{2 if big else 1.5}"/>'
                      f'<path d="M{x-diag:.1f} {y-diag:.1f}L{x+diag:.1f} {y+diag:.1f}M{x-diag:.1f} {y+diag:.1f}L{x+diag:.1f} {y-diag:.1f}" '
                      f'stroke="{tint}" stroke-width="1" opacity=".55"/><rect x="{x-1.5}" y="{y-1.5}" width="3" height="3" fill="#ffffff"/></g>')
    return f'<g data-sky="twinkles">{"".join(dims)}{"".join(flares)}</g>'


METEOR_COUNT = 6  # one per four-second slot, so something streaks by about every fourth second
METEOR_BRIGHT = 3  # slot index of the one big, bright shooting star


METEOR_SHOWER_COUNT = 12  # on a meteor shower's peak nights: one per two-second slot
METEOR_ATTEMPTS = 500
METEOR_GAP = 6  # seconds


@functools.lru_cache(maxsize=4)
def meteor_plan(seed=7, count=METEOR_COUNT):
    """Shooting stars at irregular times, angles and lengths whose whole path and tail stay in open sky.

    The loop is cut into ``count`` equal slots with one meteor each, finished (and reset) inside the cycle."""
    rng = random.Random(seed)
    slot_length = PERIOD/count
    latest = min(.65*slot_length, slot_length-1.25)
    plan = []
    for slot in range(count):
        for _ in range(METEOR_ATTEMPTS):
            start = slot*slot_length+rng.uniform(0, latest)
            duration = rng.uniform(.7, 1.15)
            x0, y0 = rng.uniform(60, 1640), rng.uniform(15, 330)
            side, heading = rng.choice([1, -1]), math.radians(rng.uniform(18, 42))
            travel = rng.uniform(260, 460)
            dx, dy = side*math.cos(heading)*travel, math.sin(heading)*travel
            tail = rng.uniform(110, 190) if slot != METEOR_BRIGHT else 240
            ux, uy = dx/travel, dy/travel
            # Every point the head or tail ever covers lies on one segment: from the tail behind the start to the end.
            reach = tail+travel
            points = [(x0-ux*tail+ux*reach*i/40, y0-uy*tail+uy*reach*i/40) for i in range(41)]
            # never more than METEOR_GAP seconds without a meteor, including across the loop's wrap
            gap = start-(plan[-1][0] if plan else start)
            wrap = plan[0][0]+PERIOD-start if plan and slot == count-1 else 0
            if gap <= METEOR_GAP and wrap <= METEOR_GAP and \
                    all(0 < px < W and py < 540 and not quiet(px, py, 18) for px, py in points):
                plan.append((start, duration, x0, y0, dx, dy, tail, slot == METEOR_BRIGHT))
                break
        else:
            raise RuntimeError(f'no open-sky path for meteor slot {slot} with seed {seed}')
    return plan


def meteor_tracks(start, duration, x0, y0, dx, dy):
    """Fade and position tracks: in over 12% of the flight, out over the last 35%, linear motion.

    The position snaps back to the start 0.05 s after the meteor has faded out, so every track closes its loop.
    """
    at = lambda f: (x0+dx*f, y0+dy*f)
    fade = Track.timeline([(start, 0), (start+.12*duration, 1), (start+.65*duration, 1), (start+duration, 0)], 0, digits=4)
    move = Track.timeline([(start, at(0)), (start+.12*duration, at(.12)), (start+.65*duration, at(.65)),
                           (start+duration, at(1)), (start+duration+.05, at(0))], at(0), digits=2)
    return fade, move


def meteor_defs(seed=7, count=METEOR_COUNT):
    parts = []
    for k, (_, _, _, _, dx, dy, tail, _) in enumerate(meteor_plan(seed, count)):
        length = math.hypot(dx, dy)
        ux, uy = dx/length, dy/length
        parts.append(f'<linearGradient id="mt{k}" gradientUnits="userSpaceOnUse" x1="{-ux*tail:.1f}" y1="{-uy*tail:.1f}" x2="0" y2="0">'
                     f'<stop offset="0" stop-color="#7fd8ff" stop-opacity="0"/><stop offset=".7" stop-color="#bfeeff" stop-opacity=".6"/>'
                     f'<stop offset="1" stop-color="#ffffff"/></linearGradient>')
    return ''.join(parts)


def meteors(t, animated, seed=7, count=METEOR_COUNT):
    parts = []
    for k, (start, duration, x0, y0, dx, dy, tail, bright) in enumerate(meteor_plan(seed, count)):
        length = math.hypot(dx, dy)
        ux, uy = dx/length, dy/length
        width = 4 if bright else 3
        trail = f'M{-ux*tail:.1f} {-uy*tail:.1f}L0 0'
        fade, move = meteor_tracks(start, duration, x0, y0, dx, dy)
        parts.append(f'<g opacity="{fade.value_text(t)}">{fade.smil("opacity") if animated else ""}'
                     f'<g transform="translate({move.value_text(t)})">{move.smil("transform", "translate") if animated else ""}'
                     f'<path d="{trail}" stroke="url(#mt{k})" stroke-width="{width*2.5}" fill="none" opacity=".25"/>'
                     f'<path d="{trail}" stroke="url(#mt{k})" stroke-width="{width}" fill="none"/>'
                     f'<circle r="{7 if bright else 5}" fill="#bff3ff" opacity=".35"/>'
                     f'<rect x="-2.5" y="-2.5" width="5" height="5" fill="#ffffff"/></g></g>')
    return f'<g data-sky="meteors">{"".join(parts)}</g>'


SATELLITE = ((-20, 34), (1700, 104))  # enters and leaves off canvas
# Daily variants (index 0 is the published pass); all cross left to right above y 120, clear of the name.
SATELLITE_PATHS = [SATELLITE, ((-20, 96), (1700, 26)), ((-20, 58), (1700, 114)), ((-20, 112), (1700, 44))]


def satellite_tracks(path=SATELLITE):
    (x0, y0), (x1, y1) = path
    at = lambda s: (x0+(x1-x0)*s/23.8, y0+(y1-y0)*s/23.8)
    move = Track.timeline([(0, at(0)), (23.8, at(23.8)), (PERIOD, at(0))], at(0), digits=2)
    fade = Track.timeline([(0, 0), (.6, 1), (23.2, 1), (23.8, 0)], 0)
    return fade, move


def satellite(t, animated, path=SATELLITE):
    """A slow satellite gliding across the top of the sky once per loop; it returns while invisible."""
    fade, move = satellite_tracks(path)
    return (f'<g data-sky="satellite" opacity="{fade.value_text(t)}">{fade.smil("opacity") if animated else ""}'
            f'<g transform="translate({move.value_text(t)})">{move.smil("transform", "translate") if animated else ""}'
            '<circle r="4" fill="#d9f4ff" opacity=".2"/><rect x="-1.5" y="-1.5" width="3" height="3" fill="#e9f8ff"/></g></g>')


def night_group(name, markup, night):
    """Celestial markup that fades with the night factor; unchanged when no lighting is in force."""
    return markup if night is None else f'<g data-night="{name}" opacity="{_num(night, 4)}">{markup}</g>'


def layers(t, animated, light=None):
    """All animated layers.  ``light`` (see ``lighting``) adds the sky overlay and fades the celestial ones."""
    night = None if light is None else light['night']
    day = DEFAULT_DAY if light is None else light['day']
    overlay = '' if light is None else light['markup']
    weather = '' if light is None else light['weather']
    showers = '' if light is None else rain(t, animated, light)
    city = '' if light is None else light['city']+city_beacons(t, animated, light)
    return (night_group('twinkles', twinkles(t, animated, day['twinkles']), night)+overlay
            +night_group('celestial', celestial(t, animated), night)
            +night_group('satellite', satellite(t, animated, SATELLITE_PATHS[day['satellite']]), night)
            +('' if light is None else light['bodies'])+weather+city+('' if light is None else light['title'])
            +traffic(t, animated, night, routes_for(day['airliner']))
            +night_group('sky-details', sky_details(t, animated, day['crosses']), night)
            +night_group('meteors', meteors(t, animated, day['meteors'], day['meteor_count']), night)
            +('' if light is None else portfolio(t, animated, light))+showers+workshop(t, animated))


# ---------------------------------------------------------------------------
# Day/night lighting (Phase 3): continuous functions of the sun's altitude and azimuth.
# ---------------------------------------------------------------------------
# The night plate is the only artwork, so a state-dependent overlay is drawn over it: a sky gradient clipped to the
# region above SKYLINE (so trees, telescope and roof occlude it), a warm glow under the sun, a pixel-styled sun, and a
# faint uniform lift on everything below SKYLINE.  This is an interim tint until deliberate day art exists.
HORIZON_Y = 690            # the plate's distant horizon (mountain and city line)
FAR_BAND = [(330, 655), (1190, 655), (1190, 742), (1040, 742), (1040, 798), (865, 798), (865, 742), (330, 742)]
SUN_RADIUS = 22
SUN_VISIBLE_ALT = -2       # degrees; below this the disc is never drawn
SUN_PIXEL = 4              # sun centre and rings snap to this grid for a pixel-art look
FOREGROUND_LIFT = (.34, (170, 190, 225))   # twilight lift on the night ground, gone once the day plates are in
# Foreground plates derived from the night painting by scripts/build_day_art.py; (sun altitude, opacity) keys.
GOLDEN_KEYS = [(-5, 0), (1, 1), (8, 1), (14, 0)]
DAY_KEYS = [(4, 0), (14, 1)]
COUNTERWEIGHT_BOX = (728, 636, 786, 700)   # telescope counterweight and arm, above SKYLINE but not sky
SKY_THRESHOLD = .55        # a band pixel joins the sky when brighter than this share of its column's sky above
TITLE_OUTLINE = '#050c1c'  # dark pixel outline that keeps the painted name legible on a bright sky
# (sun altitude, top rgb, top opacity, horizon rgb, horizon opacity), interpolated linearly in between.  Both
# opacities never decrease as the sun climbs.  Nautical dusk lifts only the low sky; civil twilight deepens the blue
# above; by +12 degrees the overlay is opaque, which hides the painted stars and Milky Way.
SKY_KEYS = [(-18, (8, 14, 40), 0, (12, 30, 70), 0),
            (-12, (14, 26, 78), .04, (30, 64, 140), .38),
            (-6, (26, 52, 128), .32, (74, 104, 176), .78),
            (-.8, (54, 98, 186), .86, (190, 150, 160), .92),
            (4, (68, 124, 210), .97, (238, 208, 178), .98),
            (12, (66, 138, 226), 1, (166, 208, 246), 1),
            (30, (52, 124, 220), 1, (150, 200, 245), 1)]
CELESTIAL_FADE = (-14, -4)  # sun altitudes (degrees) where faint sky art starts and finishes fading out
GLOW_CENTRE_ALT, GLOW_SPREAD, GLOW_PEAK = -1.0, 5.5, .85   # warm band: strongest at sunrise/sunset
GLOW_RADII = (860, 300)


def _mix(a, b, f):
    return tuple(x+(y-x)*f for x, y in zip(a, b)) if isinstance(a, tuple) else a+(b-a)*f


def _smooth(x):
    x = min(1.0, max(0.0, x))
    return x*x*(3-2*x)


def sky_colours(altitude):
    """(top rgb, top opacity, horizon rgb, horizon opacity) for a sun altitude in degrees."""
    keys = SKY_KEYS
    if altitude <= keys[0][0]:
        return keys[0][1:]
    for lo, hi in zip(keys, keys[1:]):
        if altitude <= hi[0]:
            f = (altitude-lo[0])/(hi[0]-lo[0])
            return tuple(_mix(a, b, f) for a, b in zip(lo[1:], hi[1:]))
    return keys[-1][1:]


def _keyed(keys, altitude):
    """Piecewise-smoothstep value through (altitude, value) keys, flat outside them."""
    if altitude <= keys[0][0]:
        return keys[0][1]
    for (a0, v0), (a1, v1) in zip(keys, keys[1:]):
        if altitude <= a1:
            return round(v0+(v1-v0)*_smooth((altitude-a0)/(a1-a0)), 4)
    return keys[-1][1]


def night_factor(altitude):
    """Opacity of stars, galaxies and other faint sky art: full below -14 degrees, gone by -4 (before civil dusk)."""
    return 1-_smooth((altitude-CELESTIAL_FADE[0])/(CELESTIAL_FADE[1]-CELESTIAL_FADE[0]))


SKY_TOP_ALT = 90           # altitude drawn at y=40 (the zenith), so a high moon or sun stays in the picture


OVERHEAD_ALT = 60          # above this altitude an object is in view whatever its azimuth


def sun_screen(altitude, azimuth):
    """Scene position of a sky object on the south-facing dome: east at the left edge, west at the right, the zenith
    at the top centre (x follows the east-west direction, so objects near the zenith converge on the middle)."""
    x = W/2+math.sin(math.radians(azimuth-180))*math.cos(math.radians(altitude))*(W/2)
    return x, HORIZON_Y-altitude/SKY_TOP_ALT*(HORIZON_Y-40)


def in_view(altitude, azimuth):
    """The southern half of the sky, plus everything high overhead; the northern sky is behind the viewer."""
    return altitude >= OVERHEAD_ALT or 90 <= azimuth % 360 <= 270


def lighting(state):
    """Everything the renderer needs for one moment, from a SceneState dict (computed once per render)."""
    sun = state['astronomy']['sun']
    altitude, azimuth = sun['altitude_deg'], sun['azimuth_deg']
    daylight = state['lighting']['daylight']
    top, top_a, horizon, horizon_a = sky_colours(altitude)
    x, y = sun_screen(altitude, azimuth)
    visible = altitude > SUN_VISIBLE_ALT and in_view(altitude, azimuth)
    glow = GLOW_PEAK*math.exp(-((altitude-GLOW_CENTRE_ALT)/GLOW_SPREAD)**2)
    light = dict(daylight=daylight, night=round(night_factor(altitude), 4), altitude=altitude, azimuth=azimuth,
                 top=top, top_opacity=top_a, horizon=horizon, horizon_opacity=horizon_a,
                 glow=glow, glow_x=min(max(x, -400), W+400), sun=(x, y) if visible else None,
                 plates={'golden': _keyed(GOLDEN_KEYS, altitude), 'day': _keyed(DAY_KEYS, altitude)})
    light['foreground'] = FOREGROUND_LIFT[0]*daylight*(1-max(light['plates'].values()))
    season(light, state)
    light['markup'], light['title'] = lighting_markup(light)
    return light


def _rgb(c):
    return 'rgb(%d,%d,%d)' % tuple(round(v) for v in c)


def _png_uri(image):
    import io
    buffer = io.BytesIO()
    image.save(buffer, 'PNG', optimize=True)
    return 'data:image/png;base64,'+base64.b64encode(buffer.getvalue()).decode()


@functools.lru_cache(maxsize=None)
def day_plate(name):
    """Data URI of a derived foreground plate (assets/observatory-<name>.png), loaded only when it is drawn."""
    return png_uri(f'observatory-{name}.png')


@functools.lru_cache(maxsize=1)
def plate_masks():
    """Pixel-exact masks measured from the plate: sky, ground (its inverse), name glyphs and their outline.

    Everything above SKYLINE is sky. Below it, sky continues only through pixels brighter than SKY_THRESHOLD times
    that column's sky just above SKYLINE, flood-filled from the top and stopped at the horizon, so trees, the
    telescope, the van, the roof and the darker mountains stay out. Returns PNG data URIs (white = selected).
    """
    from PIL import Image, ImageChops, ImageDraw, ImageFilter
    plate = Image.open(ASSETS/'observatory-background.png').convert('RGB')
    lum = plate.convert('L')
    px = lum.load()
    threshold = Image.new('L', (W, H), 0)
    draw = ImageDraw.Draw(threshold)
    for x in range(W):
        top = int(_interp_pts(SKYLINE, x))
        above = sorted(px[x, y] for y in range(max(0, top-40), max(1, top-4)))
        draw.line([(x, 0), (x, H)], fill=max(12, round(SKY_THRESHOLD*above[len(above)//2])))
    passable = ImageChops.subtract(lum, threshold).point(lambda v: 255 if v > 0 else 0)
    measured = passable.crop(COUNTERWEIGHT_BOX)
    fill = ImageDraw.Draw(passable)
    fill.polygon([(0, 0), (W, 0)]+[(x, y) for x, y in SKYLINE[::-1]], fill=255)
    passable.paste(measured, COUNTERWEIGHT_BOX[:2])   # the counterweight arm pokes above SKYLINE: measure it too
    fill.rectangle([0, HORIZON_Y+10, W, H], fill=0)
    ImageDraw.floodfill(passable, (W//2, 2), 128)
    sky = passable.point(lambda v: 255 if v == 128 else 0).convert('1')
    # Name glyphs: the three painted text lines are found from their cyan pixels (rows with several of them, grouped
    # into lines, x-extent trimmed of stray stars); every bright pixel inside a line box belongs to the lettering,
    # including the white letter cores. The outline is the glyphs grown by two pixels.
    x0, y0, x1, y1 = TEXT_RECT
    rgb = plate.load()
    cyan = {(x, y) for x in range(x0, x1) for y in range(y0, y1)
            if px[x, y] > 110 and (rgb[x, y][1]+rgb[x, y][2])/2 > rgb[x, y][0]+20}
    rows = sorted({y for _, y in cyan if sum(1 for x in range(x0, x1) if (x, y) in cyan) >= 6})
    lines, start = [], None
    for prev, y in zip([None]+rows, rows):
        if prev is None or y-prev > 3:
            if start is not None:
                lines.append((start, prev))
            start = y
    if start is not None:
        lines.append((start, rows[-1]))
    lines = [(top, bottom) for top, bottom in lines if bottom-top >= 4]   # a lone row of bright stars is not text
    glyphs = Image.new('L', (W, H), 0)
    out = glyphs.load()
    for top, bottom in lines:
        xs = sorted(x for x, y in cyan if top <= y <= bottom)
        left, right = xs[len(xs)//100], xs[-1-len(xs)//100]
        for x in range(left-2, right+3):
            for y in range(top-2, bottom+3):
                if px[x, y] > 90:
                    out[x, y] = 255
    outline = glyphs.filter(ImageFilter.MaxFilter(5))
    return dict(sky=_png_uri(sky), ground=_png_uri(ImageChops.invert(sky.convert('L')).convert('1')),
                glyphs=_png_uri(glyphs.convert('1')), outline=_png_uri(outline.convert('1')))


def lighting_defs(light):
    """Gradients, clip paths and the name-block carve; their ids are unique, so layers() may repeat the markup."""
    top, horizon = light['top'], light['horizon']
    stops = ''.join(f'<stop offset="{o}" stop-color="{_rgb(_mix(top, horizon, o**2.2))}" '
                    f'stop-opacity="{_num(_mix(light["top_opacity"], light["horizon_opacity"], o**2.2), 3)}"/>'
                    for o in (0, .35, .65, .85, 1))
    warm = _rgb(_mix((255, 112, 118), (255, 196, 122), _smooth((light['altitude']+3)/8)))
    plates = ''.join(f'<image id="plate-{name}" width="{W}" height="{H}" href="{day_plate(name)}" '
                     f'xlink:href="{day_plate(name)}"/>' for name, opacity in light['plates'].items() if opacity > 0)
    masks = ''.join(f'<mask id="{name}-mask" maskUnits="userSpaceOnUse" x="0" y="0" width="{W}" height="{H}">'
                    f'<image width="{W}" height="{H}" href="{uri}" xlink:href="{uri}"/></mask>'
                    for name, uri in plate_masks().items())+season_defs(light)
    return (f'<linearGradient id="sky-grad" gradientUnits="userSpaceOnUse" x1="0" y1="0" x2="0" y2="{HORIZON_Y}">{stops}</linearGradient>'
            f'<radialGradient id="sky-glow"><stop offset="0" stop-color="{warm}" stop-opacity="1"/>'
            f'<stop offset=".4" stop-color="{warm}" stop-opacity=".55"/><stop offset="1" stop-color="{warm}" stop-opacity="0"/></radialGradient>'
            f'{masks}{plates}')


def sun_markup(light):
    x, y = (round(v/SUN_PIXEL)*SUN_PIXEL for v in light['sun'])
    colour = _rgb(_mix((255, 150, 70), (255, 246, 206), _smooth((light['altitude']-2)/22)))
    halo = ''.join(f'<circle cx="{x}" cy="{y}" r="{r}" fill="{colour}" opacity="{o}"/>'
                   for r, o in ((92, .10), (68, .14), (48, .2), (34, .32)))
    return (f'<g data-sun="disc">{halo}'
            f'<circle cx="{x}" cy="{y}" r="{SUN_RADIUS}" fill="{colour}"/>'
            f'<circle cx="{x}" cy="{y}" r="{SUN_RADIUS-8}" fill="#fffbe6" opacity=".7"/></g>')


def lighting_markup(light):
    """(Sky overlay with sun, day plates and foreground lift; the redrawn name), drawn between the plate and the moving art."""
    gx, gr = light['glow_x'], GLOW_RADII
    sky = ''
    if light['top_opacity'] > 0 or light['horizon_opacity'] > 0:
        sky += f'<rect data-light="sky" width="{W}" height="{HORIZON_Y+10}" fill="url(#sky-grad)"/>'
    if light['glow'] > .005:
        sky += (f'<ellipse data-light="glow" cx="{_num(gx, 1)}" cy="{HORIZON_Y+30}" rx="{gr[0]}" ry="{gr[1]}" '
                f'fill="url(#sky-glow)" opacity="{_num(light["glow"], 4)}"/>')
    if light['sun']:
        sky += sun_markup(light)
    # The plate's own silhouettes occlude the sky pixel for pixel. The painted name is returned separately so the
    # renderer can redraw it above sky, clouds and haze, with a dark pixel outline whose strength follows how much
    # bright sky sits behind it.
    out = f'<g data-light="sky-group" mask="url(#sky-mask)">{sky}</g>' if sky else ''
    outline = max(light['top_opacity'], light['glow'])
    title = '<g data-light="title">'
    if outline > .001:
        title += (f'<rect width="{W}" height="{H}" fill="{TITLE_OUTLINE}" opacity="{_num(min(.9, outline), 4)}" '
                  f'mask="url(#outline-mask)"/>')
    title += '<use href="#plate" xlink:href="#plate" mask="url(#glyphs-mask)"/></g>'
    # Day and golden-hour foregrounds (transparent sky) replace the moonlit ground; day is drawn over golden.
    for name, opacity in light['plates'].items():
        if opacity > 0:
            out += (f'<use data-light="plate-{name}" href="#plate-{name}" xlink:href="#plate-{name}" '
                    f'opacity="{_num(opacity, 4)}"/>')
    if light['foreground'] > .001:
        out += (f'<rect data-light="foreground" width="{W}" height="{H}" fill="{_rgb(FOREGROUND_LIFT[1])}" '
                f'opacity="{_num(light["foreground"], 4)}" mask="url(#ground-mask)"/>')
    return out, title


# ---------------------------------------------------------------------------
# Seasons (Phase 4): continuous effects of SceneState['environment'], never keyed on the season's name, so the six
# seasons blend into each other day by day.  Cloud layout and showers come from the daily seed.
# ---------------------------------------------------------------------------
CLOUD_CELL = 6                       # clouds are drawn on this pixel grid
CLOUD_BAND = (36, 540)               # y range clouds may occupy
CLOUD_CLEAR = (TEXT_RECT[0]-24, TEXT_RECT[1]-24, TEXT_RECT[2]+24, TEXT_RECT[3]+24)   # the name stays clear
OVERCAST = (.6, .9, .62)             # cloud density where the grey deck starts, where it is full, its full opacity
DRY = (.85, .6, .9)                  # greenery where drying starts, span to full dryness, maximum dry-plate opacity
HAZE_PEAK = .55                      # horizon haze opacity at haze = 1
HAZE_TOP, HAZE_BOTTOM = HORIZON_Y-320, HORIZON_Y+110
WET_DARKEN = .2                      # ground darkening at wetness = 1
VISIBILITY_FLOOR = .3                # stars at night_visibility = 0 keep this share
RAIN = dict(start=.62, span=.25, tile=320, slant=.22)
SHELTER = [(1162, 612), (1672, 478), (1672, 941), (1162, 941)]       # under the workshop roof: no rain
PUDDLES = [(930, 904, 66, 6), (1004, 924, 44, 4), (1268, 916, 40, 4)]   # x, y, width, height on the earth path


def season(light, state):
    """Add the season's values and its static markup (sky veils, clouds, haze, wet ground) to ``light``."""
    env = state['environment']
    light['env'] = env
    light['seed'] = state['seed_int']
    light['day'] = daily_variation(state)
    visibility = VISIBILITY_FLOOR+(1-VISIBILITY_FLOOR)*env['night_visibility']
    light['night'] = round(light['night']*visibility, 4)
    light['overcast'] = OVERCAST[2]*_smooth((env['cloud_density']-OVERCAST[0])/(OVERCAST[1]-OVERCAST[0]))
    light['dry'] = round(DRY[2]*_smooth((DRY[0]-env['greenery'])/DRY[1])*light['plates']['day'], 4)
    light['rain'] = shower(state, env)
    light['haze'] = HAZE_PEAK*env['haze']
    light['haze_colour'] = _colour_for(light, (40, 46, 70), _mix((214, 220, 226), (226, 210, 180),
                                                                 _smooth((env['haze']-.5)/.3)), (240, 176, 150))
    light['deck'] = _colour_for(light, (18, 22, 34), (150, 158, 170), (190, 130, 128))
    light['city'] = city_markup(light)+city_glow(light)
    light['weather'] = season_markup(light)
    light['bodies'] = sky_bodies(light, state)
    return light


DEFAULT_DAY = dict(twinkles=41, meteors=7, crosses=29, satellite=0, airliner=0, meteor_count=METEOR_COUNT)


def layer_seed(seed, name):
    """An independent seed per layer, so twinkles, meteors, clouds and traffic do not move in lockstep."""
    import hashlib
    return int(hashlib.sha256(f'{seed}-{name}'.encode()).hexdigest()[:12], 16)


def daily_variation(state):
    """Phase 6: what changes from one day to the next, all from the daily seed (the hour plays no part)."""
    seed = state['seed']
    shower = (state.get('sky_events') or {}).get('meteor_shower')
    return dict(twinkles=layer_seed(seed, 'twinkles'), meteors=layer_seed(seed, 'meteors'),
                crosses=layer_seed(seed, 'crosses'),
                satellite=layer_seed(seed, 'satellite') % len(SATELLITE_PATHS),
                airliner=layer_seed(seed, 'airliner') % len(AIRLINER_VARIANTS),
                meteor_count=METEOR_SHOWER_COUNT if shower else METEOR_COUNT, shower=shower)


def shower(state, env):
    """Rain amount 0..1: heavy cloud and a wet season make showers likely; the seed decides which hours rain."""
    likely = _smooth((env['cloud_density']-RAIN['start'])/RAIN['span'])
    if likely <= 0:
        return 0
    import hashlib
    hour = state['time'][:2]
    roll = int(hashlib.sha256(f"{state['seed']}-rain-{hour}".encode()).hexdigest()[:8], 16)/0xffffffff
    chance = .35+.55*env['ground_wetness']
    return round(likely*(.55+.45*roll/chance), 4) if roll < chance else 0


def _colour_for(light, night, day, warm):
    """Interpolate a colour from night to day by daylight, then towards warm by the sunrise/sunset glow."""
    return _mix(_mix(night, day, light['daylight']), warm, .7*light['glow'])


def cloud_shapes(seed, density):
    """Cloud boxes and puffs for the day: positions come from the seed, the count and size from the density."""
    rng = random.Random(seed)
    count = round(2+14*density)
    clouds = []
    for _ in range(200):
        if len(clouds) >= count:
            break
        w = rng.uniform(150, 240+420*density)
        h = w*rng.uniform(.26, .36)
        x = rng.uniform(-w*.3, W-w*.7)
        y = rng.uniform(CLOUD_BAND[0], CLOUD_BAND[1]-h)
        puffs = [(x+w*f, y+h*rng.uniform(.3, .6), h*rng.uniform(.34, .5))
                 for f in (rng.uniform(.18, .3), rng.uniform(.42, .58), rng.uniform(.68, .82))]
        a, b, c, d = CLOUD_CLEAR
        if x < c and x+w > a and y < d and y+h > b:
            continue
        clouds.append(((x, y, w, h), puffs))
    return clouds


def cloud_cells(box, puffs):
    """Pixel cells of one cloud: (row y, [(x0, x1, tone)]) where tone 0 = lit top, 1 = body, 2 = shadowed base."""
    x, y, w, h = box
    bottom = y+h*.8
    base = (x+w/2, y+h*.6, w*.48, h*.22)
    inside = lambda cx, cy: cy <= bottom and (
        any((cx-px)**2+(cy-py)**2 <= r*r for px, py, r in puffs)
        or ((cx-base[0])/base[2])**2+((cy-base[1])/base[3])**2 <= 1)
    rows = []
    gx0 = int(x//CLOUD_CELL)*CLOUD_CELL
    for gy in range(int(y//CLOUD_CELL)*CLOUD_CELL, int(bottom)+CLOUD_CELL, CLOUD_CELL):
        runs = []
        for gx in range(gx0, int(x+w)+CLOUD_CELL, CLOUD_CELL):
            cx, cy = gx+CLOUD_CELL/2, gy+CLOUD_CELL/2
            if not inside(cx, cy):
                continue
            tone = 0 if not inside(cx, cy-CLOUD_CELL) else (2 if cy > y+h*.58 else 1)
            if runs and runs[-1][1] == gx and runs[-1][2] == tone:
                runs[-1][1] = gx+CLOUD_CELL
            else:
                runs.append([gx, gx+CLOUD_CELL, tone])
        if runs:
            rows.append((gy, runs))
    return rows


def season_defs(light):
    """The rain mask (everywhere but under the roof), the haze gradient and, when it is drawn, the dry plate."""
    roof = ' '.join(f'{x},{y}' for x, y in SHELTER)
    return (f'<mask id="rain-mask" maskUnits="userSpaceOnUse" x="0" y="0" width="{W}" height="{H}">'
            f'<rect width="{W}" height="{H}" fill="#fff"/><polygon points="{roof}" fill="#000"/></mask>'
            f'<linearGradient id="haze-grad" gradientUnits="userSpaceOnUse" x1="0" y1="{HAZE_TOP}" x2="0" y2="{HAZE_BOTTOM}">'
            f'<stop offset="0" stop-color="{_rgb(light["haze_colour"])}" stop-opacity="0"/>'
            f'<stop offset=".74" stop-color="{_rgb(light["haze_colour"])}" stop-opacity="1"/>'
            f'<stop offset="1" stop-color="{_rgb(light["haze_colour"])}" stop-opacity="1"/></linearGradient>'
            + (f'<image id="plate-dry" width="{W}" height="{H}" href="{day_plate("dry")}" xlink:href="{day_plate("dry")}"/>'
               if light['dry'] > 0 else '')+city_defs())


def season_markup(light):
    env = light['env']
    out = ''
    if light['dry'] > 0:
        out += f'<use data-season="dry" href="#plate-dry" xlink:href="#plate-dry" opacity="{_num(light["dry"], 4)}"/>'
    wet = env['ground_wetness']
    if wet > .01:
        out += (f'<rect data-season="wet" width="{W}" height="{H}" fill="rgb(8,18,26)" '
                f'opacity="{_num(WET_DARKEN*wet, 4)}" mask="url(#ground-mask)"/>')
        sky = _colour_for(light, (22, 30, 56), light['horizon'], (255, 180, 140))
        shine = _colour_for(light, (60, 74, 110), (236, 244, 252), (255, 214, 170))
        out += f'<g data-season="puddles" opacity="{_num(.85*wet, 4)}">'
        for x, y, w, h in PUDDLES:
            out += (f'<rect x="{x+4}" y="{y}" width="{w-8}" height="{h}" fill="{_rgb(sky)}"/>'
                    f'<rect x="{x}" y="{y+2}" width="{w}" height="{h-2}" fill="{_rgb(sky)}"/>'
                    f'<rect x="{x+w//3}" y="{y+1}" width="{w//4}" height="2" fill="{_rgb(shine)}"/>')
        out += '</g>'
    veil = ''
    if light['overcast'] > .005:
        veil += (f'<rect data-season="overcast" width="{W}" height="{HORIZON_Y+10}" fill="{_rgb(light["deck"])}" '
                 f'opacity="{_num(light["overcast"], 4)}"/>')
    murk = (1-env['night_visibility'])*.45*night_factor(light['altitude'])
    if murk > .005:
        veil += (f'<rect data-season="murk" width="{W}" height="{HORIZON_Y+10}" fill="rgb(10,16,32)" '
                 f'opacity="{_num(murk, 4)}"/>')
    density = env['cloud_density']
    grey = _smooth((density-.4)/.5)
    # Fair-weather clouds are white with blue-grey bases; rain clouds are darker than the overcast deck behind them.
    under = CLOUD_UNDERGLOW*env['urban_glow']
    night_tones = [_mix(c, (176, 96, 58), under*f) for c, f in (((52, 60, 88), .5), ((36, 42, 66), .8), ((24, 28, 46), 1))]
    tones = (_colour_for(light, night_tones[0], _mix((250, 250, 252), (168, 176, 188), grey), (255, 196, 160)),
             _colour_for(light, night_tones[1], _mix((226, 232, 240), (126, 134, 148), grey), (238, 150, 140)),
             _colour_for(light, night_tones[2], _mix((184, 194, 210), (90, 98, 112), grey), (150, 96, 124)))
    # One path per tone, so neighbouring cells merge without anti-aliased seams; later clouds cover earlier ones.
    clouds = ''
    for box, puffs in cloud_shapes(layer_seed(light['seed'], 'clouds'), density):
        paths = ['', '', '']
        for gy, runs in cloud_cells(box, puffs):
            for x0, x1, tone in runs:
                paths[tone] += f'M{x0} {gy}h{x1-x0}v{CLOUD_CELL}h{x0-x1}z'
        clouds += ''.join(f'<path d="{d}" fill="{_rgb(tones[tone])}"/>' for tone, d in enumerate(paths) if d)
    if veil or clouds:
        out += f'<g data-season="sky" mask="url(#sky-mask)">{veil}<g data-season="clouds" opacity=".96">{clouds}</g></g>'
    if light['haze'] > .005:
        out += (f'<rect data-season="haze" y="{HAZE_TOP}" width="{W}" height="{HAZE_BOTTOM-HAZE_TOP}" '
                f'fill="url(#haze-grad)" opacity="{_num(light["haze"], 4)}" mask="url(#sky-mask)"/>')
    return out


@functools.lru_cache(maxsize=8)
def rain_paths(seed):
    """Two layers of streaks (near and far) as single paths, tiled so a shift of one tile loops seamlessly."""
    rng = random.Random(seed ^ 0x5EED)
    tile, slant = RAIN['tile'], RAIN['slant']
    copies = range(-1, math.ceil(H/tile)+1)
    layers = []
    for dur, count, length in ((.75, 70, 16), (1, 90, 9)):
        streaks = [(rng.uniform(-60, W+slant*tile*(len(copies)+1)), rng.uniform(0, tile)) for _ in range(count)]
        d = ''.join(f'M{_num(x-k*slant*tile, 1)} {_num(y+k*tile, 1)}l{_num(-slant*length, 1)} {length}'
                    for k in copies for x, y in streaks)
        layers.append((dur, d))
    return layers


def rain(t, animated, light):
    """Falling rain over everything except the workshop interior; strength follows ``light['rain']``."""
    amount = light['rain']
    if amount <= 0:
        return ''
    colour = _colour_for(light, (120, 134, 162), (214, 224, 238), (236, 200, 180))
    out = f'<g data-season="rain" mask="url(#rain-mask)" opacity="{_num(.25+.45*amount, 4)}">'
    tile, slant = RAIN['tile'], RAIN['slant']
    for (dur, d), width in zip(rain_paths(light['seed']), (2, 1.5)):
        fall = Track([(0, 0), (-slant*tile, tile)], dur=dur)
        out += (f'<g transform="translate({fall.value_text(t)})">{fall.smil("transform", "translate") if animated else ""}'
                f'<path d="{d}" stroke="{_rgb(colour)}" stroke-width="{width}" fill="none"/></g>')
    return out+'</g>'


# ---------------------------------------------------------------------------
# Mumbai (Phase 5): a fixed pixel skyline on both shores of the bay, the sea link across it, lit windows and aviation
# lights at night, and the city's sodium glow on the low sky and the undersides of clouds.
# ---------------------------------------------------------------------------
CITY_SHORES = [(424, 640, 714), (884, 1104, 716)]   # x from, x to, base y of each tower cluster
CITY_OCCLUDER = 24          # plate luminance below which a far-band pixel is a near silhouette (trees, rock)
CITY_REGION = (330, 600, 1190, 770)
SEA_LINK = dict(x0=900, x1=1076, deck=745, pylons=(958, 1018), height=34)
CITY_GLOW = dict(colour=(255, 140, 60), peak=.62, centre=(760, 716), radii=(700, 190))
CLOUD_UNDERGLOW = .55       # share of the night cloud colour taken from the city glow at urban_glow = 1


@functools.lru_cache(maxsize=1)
def city_mask():
    """White where the skyline may show: far-band pixels that are not near silhouettes (closed to fill highlights)."""
    from PIL import Image, ImageChops, ImageFilter
    lum = Image.open(ASSETS/'observatory-background.png').convert('L')
    near = lum.point(lambda v: 255 if v < CITY_OCCLUDER else 0)
    near = near.filter(ImageFilter.MaxFilter(5)).filter(ImageFilter.MinFilter(5))   # close the trees' bright specks
    region = Image.new('L', (W, H), 0)
    region.paste(255, CITY_REGION)
    return _png_uri(ImageChops.subtract(region, near).convert('1'))


@functools.lru_cache(maxsize=1)
def city_towers():
    """(x, top, width, base, cap) for every tower; fixed, so Mumbai keeps the same skyline all year."""
    rng = random.Random(1534)   # the year Bombay's islands were ceded to Portugal; any fixed seed would do
    towers = []
    for x0, x1, base in CITY_SHORES:
        x = x0
        while x < x1:
            w = rng.choice((6, 8, 8, 10, 12, 14))
            tall = rng.random()
            h = rng.randint(44, 58) if tall > .9 else rng.randint(24, 40) if tall > .55 else rng.randint(10, 22)
            cap = rng.choice(('flat', 'flat', 'flat', 'step', 'spire')) if h > 20 else 'flat'
            towers.append((x, base-h, w, base, cap))
            x += w+rng.choice((0, 0, 2, 4, 6))
    return towers   # towers never overlap, so drawing order does not matter


def _city_colours(light):
    env = light['env']
    # Distance haze and the overcast deck are baked into the colours, since the skyline is drawn over the weather.
    haze = .2+.45*env['haze']
    lit = _colour_for(light, (26, 32, 58), _mix((178, 190, 208), light['haze_colour'], haze), (222, 156, 132))
    shade = _colour_for(light, (16, 20, 40), _mix((104, 118, 146), light['haze_colour'], haze*.7), (132, 92, 108))
    overcast = light['overcast']/OVERCAST[2]   # 0..1
    lit = _mix(lit, light['deck'], .6*overcast)
    shade = _mix(shade, _mix(light['deck'], (0, 0, 0), .2), .45*overcast)
    return lit, shade


def city_markup(light):
    """Static skyline, sea link, windows and the city glow (masked so trees, rock and telescope stay in front)."""
    lit, shade = _city_colours(light)
    paths = {'lit': '', 'shade': ''}
    for x, top, w, base, cap in city_towers():
        half = w//2
        paths['lit'] += f'M{x} {top}h{half}V{base}h{-half}z'
        paths['shade'] += f'M{x+half} {top}h{w-half}V{base}h{half-w}z'
        if cap == 'step':
            paths['lit'] += f'M{x+2} {top-4}h{w-4}v4h{4-w}z'
        elif cap == 'spire':
            paths['shade'] += f'M{x+half-1} {top-10}h2v10h-2z'
    s = SEA_LINK
    link = f'M{s["x0"]} {s["deck"]}H{s["x1"]}v2H{s["x0"]}z'
    for px in s['pylons']:
        link += f'M{px-1} {s["deck"]-s["height"]}h3V{s["deck"]+4}h-3z'
    cables = ''.join(f'M{px} {s["deck"]-s["height"]+3+i*5}L{px+d*(10+i*9)} {s["deck"]}'
                     for px in s['pylons'] for d in (-1, 1) for i in range(4))
    out = (f'<g data-city="skyline" mask="url(#city-mask)">'
           f'<path d="{paths["shade"]}" fill="{_rgb(shade)}"/><path d="{paths["lit"]}" fill="{_rgb(lit)}"/>'
           f'<path data-city="sea-link" d="{link}" fill="{_rgb(shade)}"/>'
           f'<path d="{cables}" stroke="{_rgb(lit)}" stroke-width="1" fill="none" opacity=".8"/>')
    darkness = 1-light['daylight']
    urban = light['env']['urban_glow']
    if darkness > .02:
        out += city_windows(urban, darkness)
    return out+'</g>'


def city_windows(urban, darkness):
    rng = random.Random(1661)   # Bombay's islands passed to England as a dowry
    chance = .16+.3*urban
    warm, cool = '', ''
    for x, top, w, base, _ in city_towers():
        for wy in range(top+3, base-2, 4):
            for wx in range(x+2, x+w-1, 3):
                roll = rng.random()
                if roll < chance:
                    if rng.random() < .8:
                        warm += f'M{wx} {wy}h1v2h-1z'
                    else:
                        cool += f'M{wx} {wy}h1v2h-1z'
    deck = SEA_LINK
    lamps = ''.join(f'M{x} {deck["deck"]-1}h1v1h-1z' for x in range(deck['x0']+3, deck['x1'], 7))
    return (f'<g data-city="windows" opacity="{_num(darkness, 4)}"><path d="{warm}" fill="rgb(255,206,128)"/>'
            f'<path d="{cool}" fill="rgb(206,226,255)"/><path d="{lamps}" fill="rgb(255,180,90)"/></g>')


def city_beacons(t, animated, light):
    """Red aviation lights on the tallest towers and the sea link pylons, blinking once every two seconds."""
    darkness = 1-light['daylight']
    if darkness <= .02:
        return ''
    tops = [(x+w//2-1, top-(10 if cap == 'spire' else 4 if cap == 'step' else 0)-2)
            for x, top, w, base, cap in city_towers() if base-top > 40]
    tops += [(px, SEA_LINK['deck']-SEA_LINK['height']-2) for px in SEA_LINK['pylons']]
    blink = Track([1, 1, .15, .15, 1], [0, .45, .5, .95, 1], dur=2)
    lights = ''.join(f'M{x} {y}h2v2h-2z' for x, y in tops)
    return (f'<g data-city="beacons" mask="url(#city-mask)" opacity="{_num(darkness, 4)}">'
            f'<path d="{lights}" fill="rgb(255,58,48)" opacity="{blink.value_text(t)}">'
            f'{blink.smil("opacity") if animated else ""}</path></g>')


def city_glow(light):
    """Sodium glow over the city on the low sky, strongest on dark, hazy, cloudy nights."""
    g = CITY_GLOW
    env = light['env']
    strength = g['peak']*env['urban_glow']*(1-light['daylight'])*(.7+.3*env['haze']+.3*env['cloud_density'])
    if strength < .005:
        return ''
    (cx, cy), (rx, ry) = g['centre'], g['radii']
    return (f'<ellipse data-city="glow" cx="{cx}" cy="{cy}" rx="{rx}" ry="{ry}" fill="url(#city-glow)" '
            f'opacity="{_num(min(.75, strength), 4)}" mask="url(#sky-mask)"/>')


def city_defs():
    colour = _rgb(CITY_GLOW['colour'])
    uri = city_mask()
    return (f'<mask id="city-mask" maskUnits="userSpaceOnUse" x="0" y="0" width="{W}" height="{H}">'
            f'<image width="{W}" height="{H}" href="{uri}" xlink:href="{uri}"/></mask>'
            f'<radialGradient id="city-glow"><stop offset="0" stop-color="{colour}" stop-opacity="1"/>'
            f'<stop offset=".5" stop-color="{colour}" stop-opacity=".45"/>'
            f'<stop offset="1" stop-color="{colour}" stop-opacity="0"/></radialGradient>')


# ---------------------------------------------------------------------------
# Portfolio objects (Phase 7): things from Kush's own work, confirmed by the CV. A drone pad with a hovering quadcopter
# (NETRA and the ESP32-S3 micro drone, as art), a field ground station with a scrolling telemetry trace, the star
# tracker's controller on the tripod, and a PCB with a soldering iron on the lantern crate. No labels, specs or numbers.
# ---------------------------------------------------------------------------
DRONE_PAD = (1034, 886, 26, 6)            # centre x, centre y, half width, half height
DRONE_HOVER = (1034, 826)                 # hover centre; it drifts +-4 px and bobs +-3 px
DRONE_SCALE = 1.6                         # drawn larger than life so it reads at the README's 840 px
DRONE_DRIFT = 8                           # seconds per drift loop (bob runs twice as fast)
STATION = (898, 858)                      # ground station: laptop screen top-left; its crate sits below
TRACKER_BOX = (780, 726, 18, 16)          # x, y, w, h on the tripod's left, beside the centre column
PCB = (1556, 860)                         # board top-left on the lantern crate
TRACE_COLUMNS = 12
# Painted things the objects must never cover (x0, y0, x1, y1); checked by the tests.
PROTECTED = dict(rover=(1082, 796, 1262, 908), lantern=(1620, 760, 1668, 868), printer=(1270, 688, 1404, 818),
                 ship=(1418, 738, 1604, 812), cube=(PATCH_TARGET[0], PATCH_TARGET[1], PATCH_TARGET[0]+PATCH_TARGET[2],
                                                      PATCH_TARGET[1]+PATCH_TARGET[3]),
                 right_leg=(812, 664, 872, 840), centre_column=(800, 660, 812, 840))


def _boxes(rects):
    return ''.join(f'M{_num(x, 2)} {_num(y, 2)}h{_num(w, 2)}v{_num(h, 2)}h{_num(-w, 2)}z' for x, y, w, h in rects)


def _outdoor(light, night, day, warm=None):
    """An outdoor colour: night to day by daylight, warmed at sunrise/sunset, darker when the ground is wet."""
    colour = _colour_for(light, night, day, warm or _mix(day, (255, 170, 110), .5))
    return _mix(colour, (0, 0, 0), WET_DARKEN*.8*light['env']['ground_wetness'])


def drone_parts():
    """Quadcopter seen from the side, centred on 0,0: rects per material (2 px grid)."""
    return dict(frame=[(-18, -1, 36, 2), (-20, -3, 4, 4), (16, -3, 4, 4), (-8, 4, 2, 4), (6, 4, 2, 4)],
                body=[(-6, -4, 12, 8)], top=[(-6, -4, 12, 2)], lens=[(-2, 4, 4, 2)],
                props=[(-26, -6, 16, 2), (10, -6, 16, 2)])


def object_boxes():
    """Bounding boxes of every portfolio object in scene pixels (for the collision tests)."""
    px, py, hw, hh = DRONE_PAD
    hx, hy = DRONE_HOVER
    sx, sy = STATION
    tx, ty, tw, th = TRACKER_BOX
    bx, by = PCB
    k = DRONE_SCALE
    return dict(pad=(px-hw, py-hh, px+hw, py+hh), drone=(hx-4-26*k, hy-3-10*k, hx+4+26*k, hy+3+12*k),
                station=(sx-2, sy-2, sx+32, sy+44), tracker=(tx, ty, tx+tw, ty+th), pcb=(bx, by-22, bx+62, by+12))


def drone(t, animated, light):
    darkness = 1-light['daylight']
    frame = _outdoor(light, (30, 34, 44), (64, 68, 78))
    body = _outdoor(light, (44, 50, 66), (210, 214, 222))
    top = _mix(body, (255, 255, 255), .35)
    hx, hy = DRONE_HOVER
    path = [(4*math.sin(2*math.pi*i/24), 3*math.sin(4*math.pi*i/24)) for i in range(24)]
    move = Track([(hx+x, hy+y) for x, y in path]+[(hx+path[0][0], hy+path[0][1])], None, DRONE_DRIFT, digits=2)
    strobe = Track([v for _, v in STROBE_KEYS], [s/STROBE_PERIOD for s, _ in STROBE_KEYS], STROBE_PERIOD)
    parts = drone_parts()
    pad_x, pad_y, hw, hh = DRONE_PAD
    pad = _outdoor(light, (28, 30, 36), (96, 98, 104))
    mark = _outdoor(light, (70, 74, 84), (226, 226, 214))
    pad_rects = [(pad_x-hw+6, pad_y-hh, 2*hw-12, 2), (pad_x-hw+2, pad_y-hh+2, 2*hw-4, 2*hh-4), (pad_x-hw, pad_y-2, 2*hw, 4),
                 (pad_x-hw+6, pad_y+hh-2, 2*hw-12, 2)]
    h_mark = [(pad_x-7, pad_y-3, 2, 6), (pad_x+5, pad_y-3, 2, 6), (pad_x-5, pad_y-1, 10, 2)]
    out = (f'<g data-portfolio="drone-pad"><path d="{_boxes(pad_rects)}" fill="{_rgb(pad)}"/>'
           f'<path d="{_boxes(h_mark)}" fill="{_rgb(mark)}"/>'
           f'<ellipse cx="{hx}" cy="{pad_y-1}" rx="14" ry="3" fill="#000" opacity=".3"/></g>')
    leds = (f'<path d="{_boxes([(-20, 1, 2, 2)])}" fill="#ff3b3b"/><path d="{_boxes([(18, 1, 2, 2)])}" fill="#38ff7a"/>'
            f'<circle cx="-19" cy="2" r="4" fill="#ff3b3b" opacity="{_num(.35*darkness, 3)}"/>'
            f'<circle cx="19" cy="2" r="4" fill="#38ff7a" opacity="{_num(.35*darkness, 3)}"/>'
            f'<g opacity="{strobe.value_text(t)}">{strobe.smil("opacity") if animated else ""}'
            f'<path d="{_boxes([(-1, -8, 2, 2)])}" fill="#ffffff"/>'
            f'<circle cy="-7" r="5" fill="#ffffff" opacity="{_num(.4*darkness, 3)}"/></g>')
    out += (f'<g data-portfolio="drone" transform="translate({move.value_text(t)})">'
            f'{move.smil("transform", "translate") if animated else ""}<g transform="scale({DRONE_SCALE})">'
            f'<path d="{_boxes(parts["props"])}" fill="{_rgb(_mix(top, (200, 210, 220), .5))}" opacity=".55"/>'
            f'<path d="{_boxes(parts["frame"])}" fill="{_rgb(frame)}"/>'
            f'<path d="{_boxes(parts["body"])}" fill="{_rgb(body)}"/>'
            f'<path d="{_boxes(parts["top"])}" fill="{_rgb(top)}"/>'
            f'<path d="{_boxes(parts["lens"])}" fill="#0a1020"/>{leds}</g></g>')
    return out


def ground_station(t, animated, light):
    """A rugged laptop on a crate, its screen showing a generic scrolling trace and a blinking fix light."""
    darkness = 1-light['daylight']
    sx, sy = STATION
    crate = _outdoor(light, (38, 30, 28), (128, 96, 62))
    shell = _outdoor(light, (30, 34, 40), (70, 76, 86))
    out = (f'<g data-portfolio="ground-station">'
           f'<rect x="{sx-4}" y="{sy-4}" width="36" height="26" fill="#5af0b0" opacity="{_num(.18*darkness, 3)}"/>'
           f'<path d="{_boxes([(sx, sy+22, 30, 20)])}" fill="{_rgb(crate)}"/>'
           f'<path d="{_boxes([(sx, sy+30, 30, 2), (sx+14, sy+22, 2, 20)])}" fill="{_rgb(_mix(crate, (0, 0, 0), .35))}"/>'
           f'<path d="{_boxes([(sx-2, sy-2, 32, 22), (sx-2, sy+18, 34, 4)])}" fill="{_rgb(shell)}"/>'
           f'<path d="{_boxes([(sx, sy, 28, 18)])}" fill="#06140f"/>'
           f'<path d="{_boxes([(sx+2, sy+14, 10, 2), (sx+16, sy+14, 6, 2)])}" fill="#2a6a50"/>')
    for k in range(TRACE_COLUMNS):
        wave = Track.sine(sy+8, 4, 3, phase=k/TRACE_COLUMNS, digits=2)
        out += (f'<rect x="{sx+2+2*k}" y="{wave.value_text(t)}" width="2" height="2" fill="#6dffb8">'
                f'{wave.smil("y") if animated else ""}</rect>')
    fix = Track([1, 1, .2, .2, 1], [0, .5, .5, .99, 1], 1)
    out += (f'<rect x="{sx+24}" y="{sy+2}" width="2" height="2" fill="#7dff8a" opacity="{fix.value_text(t)}">'
            f'{fix.smil("opacity") if animated else ""}</rect></g>')
    return out


def tracker_controller(t, animated, light):
    """A small controller box clamped to the tripod: a steady green power light and a slow red step light."""
    x, y, w, h = TRACKER_BOX
    box = _outdoor(light, (26, 30, 38), (84, 90, 100))
    edge = _mix(box, (255, 255, 255), .25)
    step = Track([1, 1, .15, .15, 1], [0, .45, .5, .95, 1], 2)
    return (f'<g data-portfolio="tracker"><path d="{_boxes([(x, y, w, h)])}" fill="{_rgb(box)}"/>'
            f'<path d="{_boxes([(x, y, w, 2), (x+w, y+4, 2, 2)])}" fill="{_rgb(edge)}"/>'
            f'<path d="{_boxes([(x+3, y+4, 4, 4)])}" fill="#38ff7a"/>'
            f'<rect x="{x+10}" y="{y+4}" width="4" height="4" fill="#ff4a3b" opacity="{step.value_text(t)}">'
            f'{step.smil("opacity") if animated else ""}</rect>'
            f'<path d="{_boxes([(x+3, y+11, 12, 2)])}" fill="{_rgb(_mix(box, (0, 0, 0), .4))}"/></g>')


def pcb_bench(t, animated):
    """A green board with chips and pads, and a soldering iron whose tip sends up a thin wisp (lit by the lantern)."""
    x, y = PCB
    board = [(x, y, 34, 8)]
    chips = [(x+4, y+2, 6, 4), (x+14, y+2, 4, 4), (x+22, y+2, 8, 2)]
    pads = [(x+2, y, 2, 2), (x+12, y+6, 2, 2), (x+20, y, 2, 2), (x+30, y+6, 2, 2), (x+26, y+4, 2, 2)]
    iron = [(x+40, y+6, 6, 2), (x+46, y+4, 6, 2), (x+52, y+2, 6, 2)]
    tip = (x+38, y+6)
    out = (f'<g data-portfolio="pcb"><path d="{_boxes(board)}" fill="rgb(40,128,70)"/>'
           f'<path d="{_boxes([(x, y+6, 34, 2)])}" fill="rgb(24,84,48)"/>'
           f'<path d="{_boxes(chips)}" fill="rgb(22,22,26)"/><path d="{_boxes(pads)}" fill="rgb(236,190,96)"/>'
           f'<path d="{_boxes([(x+31, y+2, 2, 2)])}" fill="#ff4a3b"/>'
           f'<path d="{_boxes(iron)}" fill="rgb(120,124,132)"/><path d="{_boxes([(tip[0], tip[1], 2, 2)])}" fill="rgb(255,150,60)"/>')
    for k in range(3):
        offset = -k  # three puffs, one second apart; each rises, fades, and returns while invisible
        move = Track([(tip[0], tip[1]-2), (tip[0]-2, tip[1]-20), (tip[0], tip[1]-2)], [0, .9, 1], 3, begin=offset, digits=2)
        fade = Track([0, .55, 0, 0], [0, .15, .9, 1], 3, begin=offset)
        out += (f'<g opacity="{fade.value_text(t)}">{fade.smil("opacity") if animated else ""}'
                f'<rect x="0" y="0" width="2" height="2" fill="rgb(222,222,226)" '
                f'transform="translate({move.value_text(t)})">{move.smil("transform", "translate") if animated else ""}</rect></g>')
    return out+'</g>'


def portfolio(t, animated, light):
    return (f'<g data-portfolio="objects">{drone(t, animated, light)}{ground_station(t, animated, light)}'
            f'{tracker_controller(t, animated, light)}{pcb_bench(t, animated)}</g>')


# ---------------------------------------------------------------------------
# Real Moon and planets (Phase 8), placed with the same south-facing projection as the sun. The painted stars, Milky
# Way, spiral galaxies and ringed planet stay as art; no real star catalogue is drawn.
# ---------------------------------------------------------------------------
MOON_RADIUS = 18
MOON_CELL = 2
MOONLIGHT = (.2, (150, 172, 214))         # night ground lift at a full moon overhead, colour
DAY_MOON = .55                            # opacity of the pale daytime moon
PLANET_COLOURS = dict(Mercury=(232, 222, 210), Venus=(255, 250, 232), Mars=(255, 156, 112),
                      Jupiter=(255, 238, 208), Saturn=(240, 222, 172))


def _vector(alt, az):
    a, z = math.radians(alt), math.radians(az)
    return (math.cos(a)*math.sin(z), math.cos(a)*math.cos(z), math.sin(a))


def _horizontal(v):
    x, y, z = v
    return math.degrees(math.asin(max(-1, min(1, z)))), math.degrees(math.atan2(x, y)) % 360


def sun_direction(moon_alt, moon_az, sun_alt, sun_az, step=4):
    """Screen-space unit vector from the moon towards the sun along the great circle joining them."""
    m, s = _vector(moon_alt, moon_az), _vector(sun_alt, sun_az)
    dot = sum(a*b for a, b in zip(m, s))
    d = [b-dot*a for a, b in zip(m, s)]
    norm = math.sqrt(sum(c*c for c in d)) or 1
    p = [a*math.cos(math.radians(step))+c/norm*math.sin(math.radians(step)) for a, c in zip(m, d)]
    (x0, y0), (x1, y1) = sun_screen(moon_alt, moon_az), sun_screen(*_horizontal(p))
    length = math.hypot(x1-x0, y1-y0) or 1
    return (x1-x0)/length, (y1-y0)/length


def moon_cells(phase_angle, direction, radius=MOON_RADIUS, cell=MOON_CELL):
    """Pixel cells of the disc as (dx, dy, lit, mare) around its centre, lit towards ``direction`` (screen vector).

    In the moon's own frame (x towards the sun) a point is lit when x >= -cos(phase_angle) * sqrt(1 - y^2), so the lit
    share is (1 + cos(phase_angle)) / 2: all of it at full moon (0 degrees), none at new moon (180 degrees).
    """
    ux, uy = direction
    k = -math.cos(math.radians(phase_angle))
    mare_rng = random.Random(1969)
    maria = [(mare_rng.uniform(-.6, .5), mare_rng.uniform(-.6, .5), mare_rng.uniform(.18, .32)) for _ in range(5)]
    cells = []
    for gy in range(-radius, radius, cell):
        for gx in range(-radius, radius, cell):
            cx, cy = (gx+cell/2)/radius, (gy+cell/2)/radius
            if cx*cx+cy*cy > 1:
                continue
            along, across = cx*ux+cy*uy, -cx*uy+cy*ux
            lit = along >= k*math.sqrt(max(0, 1-across*across))
            mare = any((cx-a)**2+(cy-b)**2 < r*r for a, b, r in maria)
            cells.append((gx, gy, lit, mare))
    return cells


def moon_markup(light, state):
    moon, sun = state['astronomy']['moon'], state['astronomy']['sun']
    if moon['altitude_deg'] < -1 or not in_view(moon['altitude_deg'], moon['azimuth_deg']):
        return ''
    x, y = (round(v/MOON_CELL)*MOON_CELL for v in sun_screen(moon['altitude_deg'], moon['azimuth_deg']))
    if not (-MOON_RADIUS < x < W+MOON_RADIUS and y > -MOON_RADIUS):
        return ''
    direction = sun_direction(moon['altitude_deg'], moon['azimuth_deg'], sun['altitude_deg'], sun['azimuth_deg'])
    darkness = 1-light['daylight']
    bright = _mix((214, 226, 240), (246, 244, 230), darkness)
    mare = _mix(bright, (120, 128, 140), .35)
    shadow = (40, 48, 70)
    paths = {'bright': '', 'mare': '', 'shadow': ''}
    for gx, gy, lit, is_mare in moon_cells(moon['phase_angle_deg'], direction):
        key = ('mare' if is_mare else 'bright') if lit else 'shadow'
        paths[key] += f'M{x+gx} {y+gy}h{MOON_CELL}v{MOON_CELL}h{-MOON_CELL}z'
    fraction = moon['illuminated_fraction']
    opacity = DAY_MOON+(1-DAY_MOON)*darkness
    halo = .5*fraction*darkness
    out = f'<g data-moon="disc" opacity="{_num(opacity, 4)}">'
    if halo > .01:
        out += (f'<circle cx="{x}" cy="{y}" r="{MOON_RADIUS*3.2:.0f}" fill="{_rgb(bright)}" opacity="{_num(halo*.18, 4)}"/>'
                f'<circle cx="{x}" cy="{y}" r="{MOON_RADIUS*1.8:.0f}" fill="{_rgb(bright)}" opacity="{_num(halo*.3, 4)}"/>')
    out += (f'<path d="{paths["shadow"]}" fill="{_rgb(shadow)}" opacity="{_num(.35*darkness, 4)}"/>'
            f'<path d="{paths["bright"]}" fill="{_rgb(bright)}"/><path d="{paths["mare"]}" fill="{_rgb(mare)}"/></g>')
    return out


def planet_visibility(magnitude, sun_altitude):
    """0..1: a planet appears once the sun is low enough for its brightness (Venus in twilight, Saturn at dark)."""
    limit = -1-2.2*(magnitude+4.5)   # Venus (-4.5) once the sun is 1 degree down, Saturn (+0.7) near -12
    return _smooth((limit-sun_altitude)/3)


def planets_markup(light, state):
    sun_alt = state['astronomy']['sun']['altitude_deg']
    visibility = VISIBILITY_FLOOR+(1-VISIBILITY_FLOOR)*light['env']['night_visibility']
    out = ''
    for name, body in state['astronomy'].get('planets', {}).items():
        seen = planet_visibility(body['magnitude'], sun_alt)*visibility
        if body['altitude_deg'] <= 0 or seen < .02 or not in_view(body['altitude_deg'], body['azimuth_deg']):
            continue
        x, y = (round(v) for v in sun_screen(body['altitude_deg'], body['azimuth_deg']))
        if not (0 < x < W and y > 0):
            continue
        size = 8 if body['magnitude'] < -3 else 6 if body['magnitude'] < -1 else 4   # readable at 840 px
        colour = _rgb(PLANET_COLOURS[name])
        out += (f'<g data-planet="{name.lower()}" opacity="{_num(seen, 4)}">'
                f'<circle cx="{x}" cy="{y}" r="{size*1.6:.1f}" fill="{colour}" opacity=".22"/>'
                f'<rect x="{x-size/2:g}" y="{y-size/2:g}" width="{size}" height="{size}" fill="{colour}"/></g>')
    return out


def moonlight(light, state):
    moon = state['astronomy']['moon']
    lift = MOONLIGHT[0]*moon['illuminated_fraction']*max(0, math.sin(math.radians(moon['altitude_deg'])))*(1-light['daylight'])
    if lift < .005:
        return ''
    return (f'<rect data-moon="light" width="{W}" height="{H}" fill="{_rgb(MOONLIGHT[1])}" '
            f'opacity="{_num(lift, 4)}" mask="url(#ground-mask)"/>')


def sky_bodies(light, state):
    """Real Moon and planets in front of the painted sky, behind the trees, clouds and the name."""
    inner = planets_markup(light, state)+moon_markup(light, state)
    sky = f'<g data-sky="bodies" mask="url(#sky-mask)">{inner}</g>' if inner else ''
    return sky+moonlight(light, state)


def feather_defs():
    x, y, w, h = PATCH_TARGET
    f = PATCH_FEATHER
    region = f'maskUnits="userSpaceOnUse" x="{x-4*f}" y="{y-4*f}" width="{w+8*f}" height="{h+8*f}"'
    top, full = PATCH_LOW_FADE
    return (f'<filter id="cube-blur" filterUnits="userSpaceOnUse" x="{x-4*f}" y="{y-4*f}" width="{w+8*f}" height="{h+8*f}">'
            f'<feGaussianBlur stdDeviation="{f}"/></filter>'
            f'<linearGradient id="cube-fade" gradientUnits="userSpaceOnUse" x1="0" y1="{top}" x2="0" y2="{full}">'
            f'<stop offset="0" stop-color="#fff" stop-opacity="0"/><stop offset="1" stop-color="#fff"/></linearGradient>'
            f'<mask id="cube-feather" {region}>'
            f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="#fff" filter="url(#cube-blur)"/></mask>'
            f'<mask id="cube-feather-low" {region}>'
            f'<rect x="{x}" y="{top}" width="{w}" height="{y+h-top}" fill="url(#cube-fade)" filter="url(#cube-blur)"/></mask>')


def scene(t=0, animated=False, embedded=True, state=None):
    parts=[f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-labelledby="title desc">',
           '<title id="title">Kush Modi — building toward the unexplored</title>',
           '<desc id="desc">Pixel observatory based on Kush\'s telescope photograph. Slowly turning galaxies, twinkling stars, shooting stars, a satellite, planetary moons, exploration spacecraft, an airplane and a working maker workshop.</desc>',
           '<defs>',
           f'<image id="atlas" width="1536" height="1024" href="{ATLAS}" xlink:href="{ATLAS}"/>']
    light=None if state is None else lighting(state)
    day=DEFAULT_DAY if light is None else light['day']
    parts+=[feather_defs(),twinkle_defs(day['twinkles']),meteor_defs(day['meteors'],day['meteor_count'])]+([] if light is None else [lighting_defs(light)])
    parts+=['</defs>',
            f'<image id="plate" width="{W}" height="{H}" href="{BACKGROUND}" xlink:href="{BACKGROUND}"/>']
    if animated:
        parts.append('<style>.still{display:none}@media(prefers-reduced-motion:reduce){.moving{display:none}.still{display:inline}}</style>')
        parts.append('<g class="moving">'+layers(t,True,light)+'</g><g class="still">'+layers(0,False,light)+'</g>')
    else:
        parts.append(layers(t,False,light))
    parts.append('</svg>')
    # SVG2 href and xlink fallback need only one copy of raster data.
    result=''.join(parts)
    result=result.replace(f' href="{ATLAS}"','').replace(f' href="{BACKGROUND}"','')
    return result


def rasterize(svg_path,png_path,width=GIF_WIDTH):
    subprocess.run(['ffmpeg','-v','error','-threads','1','-width',str(width),'-i',str(svg_path),
                    '-frames:v','1','-threads','1','-y',str(png_path)],check=True)


def export_gif(fps,width):
    with tempfile.TemporaryDirectory(prefix='observatory-frames-',dir=ROOT) as directory:
        temp=Path(directory)
        def render(i):
            svg=temp/f'frame-{i:04d}.svg'
            png=temp/f'frame-{i:04d}.png'
            svg.write_text(scene(i/fps,False))
            rasterize(svg,png,width)
            svg.unlink()
            return i
        count=PERIOD*fps
        with ThreadPoolExecutor(max_workers=4) as pool:
            for i in pool.map(render,range(count)):
                if i%fps==0:
                    print(f'Rendered {i}/{count} frames',flush=True)
        # A single fixed palette avoids flickering colors across this pixel scene.
        # Settings chosen from measured T08 experiments (same rendered frames, only the encoder varied):
        # - stats_mode=full beats diff: diff weights only moving pixels, so the static background is
        #   quantised worse (about 1.4x the error against the source frames) and the file grows ~8%.
        # - Ordered Bayer dither is position-locked, so static areas never crawl between frames; error
        #   diffusion (sierra2_4a) added flicker and doubled the file. bayer_scale=5 keeps the finer,
        #   less visible texture and a slightly smaller file than scale 3; dither=none was rejected
        #   because it risks banding in the sky gradients for almost no extra saving.
        # - FFmpeg's GIF muxer already writes changed-rectangle frames, so diff_mode=rectangle and
        #   gifsicle -O3 gain nothing. The real size lever is resolution: 840px (about the 830px
        #   GitHub shows it at) is ~28% smaller than 1000px with no visible loss at display size.
        subprocess.run(['ffmpeg','-v','error','-framerate',str(fps),'-i',str(temp/'frame-%04d.png'),
                        '-vf','palettegen=max_colors=256:stats_mode=full','-frames:v','1','-threads','1','-y',str(temp/'palette.png')],check=True)
        subprocess.run(['ffmpeg','-v','error','-framerate',str(fps),'-i',str(temp/'frame-%04d.png'),
                        '-i',str(temp/'palette.png'),'-lavfi','paletteuse=dither=bayer:bayer_scale=5',
                        '-loop','0','-threads','1','-y',str(ASSETS/'observatory.gif')],check=True)
        shutil.copyfile(temp/'frame-0000.png',ASSETS/'observatory-poster.png')
    print(f'GIF exported: {(ASSETS/"observatory.gif").stat().st_size:,} bytes',flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--gif',action='store_true')
    parser.add_argument('--fps',type=int,default=10)
    parser.add_argument('--width',type=int,default=GIF_WIDTH)
    args=parser.parse_args()
    (ASSETS/'observatory.svg').write_text(scene(animated=True))
    (ASSETS/'poster.svg').write_text(scene(0,False))
    rasterize(ASSETS/'poster.svg',ASSETS/'observatory-poster.png',args.width)
    print('Animated SVG and poster exported',flush=True)
    if args.gif:
        export_gif(args.fps,args.width)


if __name__=='__main__':
    main()
