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


def _stretch_box(box, nose, sx):
    return (nose+(box[0]-nose)*sx, box[1], nose+(box[2]-nose)*sx, box[3])


def _union(boxes):
    boxes = [b for b in boxes if b]
    return (min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes))


def _shift(box, x, y):
    return (box[0]+x, box[1]+y, box[2]+x, box[3]+y)


def _unshift(box, x, y):
    return _shift(box, -x, -y)


def traffic_state(t):
    """Pure description of every traffic object at time t (seconds)."""
    states = []
    for route in ROUTES:
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


def traffic(t, animated, night=None):
    parts = []
    for route, state in zip(ROUTES, traffic_state(t)):
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


def sky_details(t, animated):
    rng=random.Random(29)
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


@functools.lru_cache(maxsize=1)
def twinkle_plan():
    """Per star: position, colours, sparkle size and its dim/flare opacity tracks (12 keyframes per period)."""
    rng = random.Random(41)
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


def twinkle_defs():
    return ''.join(f'<radialGradient id="tw{k}"><stop offset="0" stop-color="{sky}"/><stop offset=".55" stop-color="{sky}" stop-opacity=".95"/>'
                   f'<stop offset="1" stop-color="{sky}" stop-opacity="0"/></radialGradient>'
                   for k, (*_, sky, _arm, _dim, _flare) in enumerate(twinkle_plan()))


def twinkles(t, animated):
    """Each painted star alternately fades toward the surrounding sky and flares into a small pixel sparkle."""
    anim = lambda track: track.smil('opacity') if animated else ''
    dims, flares = [], []
    for k, (x, y, big, tint, sky, arm, dim, flare) in enumerate(twinkle_plan()):
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


@functools.lru_cache(maxsize=1)
def meteor_plan():
    """Shooting stars at irregular times, angles and lengths whose whole path and tail stay in open sky."""
    rng = random.Random(7)
    plan = []
    for slot in range(METEOR_COUNT):
        while True:
            start = slot*4+rng.uniform(0, 2.6)
            duration = rng.uniform(.7, 1.15)
            x0, y0 = rng.uniform(60, 1640), rng.uniform(15, 330)
            side, heading = rng.choice([1, -1]), math.radians(rng.uniform(18, 42))
            travel = rng.uniform(260, 460)
            dx, dy = side*math.cos(heading)*travel, math.sin(heading)*travel
            tail = rng.uniform(110, 190) if slot != METEOR_BRIGHT else 240
            ux, uy = dx/travel, dy/travel
            points = [(x0+dx*i/20, y0+dy*i/20) for i in range(21)]+[(x0-ux*tail, y0-uy*tail)]
            if all(0 < px < W and py < 540 and not quiet(px, py, 18) for px, py in points):
                plan.append((start, duration, x0, y0, dx, dy, tail, slot == METEOR_BRIGHT))
                break
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


def meteor_defs():
    parts = []
    for k, (_, _, _, _, dx, dy, tail, _) in enumerate(meteor_plan()):
        length = math.hypot(dx, dy)
        ux, uy = dx/length, dy/length
        parts.append(f'<linearGradient id="mt{k}" gradientUnits="userSpaceOnUse" x1="{-ux*tail:.1f}" y1="{-uy*tail:.1f}" x2="0" y2="0">'
                     f'<stop offset="0" stop-color="#7fd8ff" stop-opacity="0"/><stop offset=".7" stop-color="#bfeeff" stop-opacity=".6"/>'
                     f'<stop offset="1" stop-color="#ffffff"/></linearGradient>')
    return ''.join(parts)


def meteors(t, animated):
    parts = []
    for k, (start, duration, x0, y0, dx, dy, tail, bright) in enumerate(meteor_plan()):
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


def satellite_tracks():
    (x0, y0), (x1, y1) = SATELLITE
    at = lambda s: (x0+(x1-x0)*s/23.8, y0+(y1-y0)*s/23.8)
    move = Track.timeline([(0, at(0)), (23.8, at(23.8)), (PERIOD, at(0))], at(0), digits=2)
    fade = Track.timeline([(0, 0), (.6, 1), (23.2, 1), (23.8, 0)], 0)
    return fade, move


def satellite(t, animated):
    """A slow satellite gliding across the top of the sky once per loop; it returns while invisible."""
    fade, move = satellite_tracks()
    return (f'<g data-sky="satellite" opacity="{fade.value_text(t)}">{fade.smil("opacity") if animated else ""}'
            f'<g transform="translate({move.value_text(t)})">{move.smil("transform", "translate") if animated else ""}'
            '<circle r="4" fill="#d9f4ff" opacity=".2"/><rect x="-1.5" y="-1.5" width="3" height="3" fill="#e9f8ff"/></g></g>')


def night_group(name, markup, night):
    """Celestial markup that fades with the night factor; unchanged when no lighting is in force."""
    return markup if night is None else f'<g data-night="{name}" opacity="{_num(night, 4)}">{markup}</g>'


def layers(t, animated, light=None):
    """All animated layers.  ``light`` (see ``lighting``) adds the sky overlay and fades the celestial ones."""
    night = None if light is None else light['night']
    overlay = '' if light is None else light['markup']
    return (night_group('twinkles', twinkles(t, animated), night)+overlay
            +night_group('celestial', celestial(t, animated), night)+night_group('satellite', satellite(t, animated), night)
            +traffic(t, animated, night)+night_group('sky-details', sky_details(t, animated), night)
            +night_group('meteors', meteors(t, animated), night)+workshop(t, animated))


# ---------------------------------------------------------------------------
# Day/night lighting (Phase 3): continuous functions of the sun's altitude and azimuth.
# ---------------------------------------------------------------------------
# The night plate is the only artwork, so a state-dependent overlay is drawn over it: a sky gradient clipped to the
# region above SKYLINE (so trees, telescope and roof occlude it), a warm glow under the sun, a pixel-styled sun, and a
# faint uniform lift on everything below SKYLINE.  This is an interim tint until deliberate day art exists.
HORIZON_Y = 690            # the plate's distant horizon (mountain and city line)
SUN_RADIUS = 22
SUN_VISIBLE_ALT = -2       # degrees; below this the disc is never drawn
SUN_PIXEL = 4              # sun centre and rings snap to this grid for a pixel-art look
FOREGROUND_LIFT = (.34, (170, 190, 225))   # opacity at full daylight, colour
TITLE_CARVE_PAD, TITLE_CARVE_BLUR = 24, 16
SKY_TITLE_KEEP = .22       # fraction of the sky overlay left over the name block so the lettering stays readable
# (sun altitude, top rgb, top opacity, horizon rgb, horizon opacity), interpolated linearly in between.  Both
# opacities never decrease as the sun climbs.  Nautical dusk lifts only the low sky; civil twilight deepens the blue
# above; by +12 degrees the overlay is opaque, which hides the painted stars and Milky Way.
SKY_KEYS = [(-18, (8, 14, 40), 0, (12, 30, 70), 0),
            (-12, (14, 26, 78), .04, (30, 64, 140), .38),
            (-6, (26, 52, 128), .32, (74, 104, 176), .78),
            (-.8, (54, 98, 186), .74, (190, 150, 160), .92),
            (4, (68, 124, 210), .92, (238, 208, 178), .98),
            (12, (66, 138, 226), 1, (166, 208, 246), 1),
            (30, (52, 124, 220), 1, (150, 200, 245), 1)]
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


def sun_screen(altitude, azimuth):
    """Scene position of the sun: the view faces due south, east on the left, 60 degrees up reaches y=40."""
    x = W/2+(((azimuth-180+180) % 360)-180)/90*(W/2)
    return x, HORIZON_Y-altitude/60*(HORIZON_Y-40)


def lighting(state):
    """Everything the renderer needs for one moment, from a SceneState dict (computed once per render)."""
    sun = state['astronomy']['sun']
    altitude, azimuth = sun['altitude_deg'], sun['azimuth_deg']
    daylight = state['lighting']['daylight']
    top, top_a, horizon, horizon_a = sky_colours(altitude)
    x, y = sun_screen(altitude, azimuth)
    visible = altitude > SUN_VISIBLE_ALT and -60 <= x <= W+60 and y >= -60
    glow = GLOW_PEAK*math.exp(-((altitude-GLOW_CENTRE_ALT)/GLOW_SPREAD)**2)
    light = dict(daylight=daylight, night=round(1-daylight, 4), altitude=altitude, azimuth=azimuth,
                 top=top, top_opacity=top_a, horizon=horizon, horizon_opacity=horizon_a,
                 glow=glow, glow_x=min(max(x, -400), W+400), sun=(x, y) if visible else None,
                 foreground=FOREGROUND_LIFT[0]*daylight)
    light['markup'] = lighting_markup(light)
    return light


def _rgb(c):
    return 'rgb(%d,%d,%d)' % tuple(round(v) for v in c)


def _sky_polygon():
    return 'M'+'L'.join(f'{x} {y}' for x, y in [(0, 0), (W, 0)]+SKYLINE[::-1])+'Z'


def lighting_defs(light):
    """Gradients, clip paths and the name-block carve; their ids are unique, so layers() may repeat the markup."""
    top, horizon = light['top'], light['horizon']
    stops = ''.join(f'<stop offset="{o}" stop-color="{_rgb(_mix(top, horizon, o**2.2))}" '
                    f'stop-opacity="{_num(_mix(light["top_opacity"], light["horizon_opacity"], o**2.2), 3)}"/>'
                    for o in (0, .35, .65, .85, 1))
    warm = _rgb(_mix((255, 112, 118), (255, 196, 122), _smooth((light['altitude']+3)/8)))
    x0, y0, x1, y1 = TEXT_RECT
    carve = (x0-TITLE_CARVE_PAD, y0-TITLE_CARVE_PAD, x1-x0+2*TITLE_CARVE_PAD, y1-y0+2*TITLE_CARVE_PAD)
    pad = 3*TITLE_CARVE_BLUR
    masks = ''.join(
        f'<mask id="{name}" maskUnits="userSpaceOnUse" x="0" y="0" width="{W}" height="{H}">'
        f'<rect width="{W}" height="{H}" fill="#fff"/><rect x="{carve[0]}" y="{carve[1]}" width="{carve[2]}" height="{carve[3]}" '
        f'fill="#000" opacity="{1-keep}" filter="url(#title-blur)"/></mask>'
        for name, keep in (('title-carve-sky', SKY_TITLE_KEEP), ('title-carve-sun', 0)))
    return (f'<linearGradient id="sky-grad" gradientUnits="userSpaceOnUse" x1="0" y1="0" x2="0" y2="{HORIZON_Y}">{stops}</linearGradient>'
            f'<radialGradient id="sky-glow"><stop offset="0" stop-color="{warm}" stop-opacity="1"/>'
            f'<stop offset=".4" stop-color="{warm}" stop-opacity=".55"/><stop offset="1" stop-color="{warm}" stop-opacity="0"/></radialGradient>'
            f'<clipPath id="sky-clip"><path d="{_sky_polygon()}"/></clipPath>'
            f'<filter id="title-blur" filterUnits="userSpaceOnUse" x="{carve[0]-pad}" y="{carve[1]-pad}" width="{carve[2]+2*pad}" height="{carve[3]+2*pad}">'
            f'<feGaussianBlur stdDeviation="{TITLE_CARVE_BLUR}"/></filter>{masks}')


def sun_markup(light):
    x, y = (round(v/SUN_PIXEL)*SUN_PIXEL for v in light['sun'])
    colour = _rgb(_mix((255, 150, 70), (255, 246, 206), _smooth((light['altitude']-2)/22)))
    halo = ''.join(f'<circle cx="{x}" cy="{y}" r="{r}" fill="{colour}" opacity="{o}"/>'
                   for r, o in ((92, .10), (68, .14), (48, .2), (34, .32)))
    return (f'<g data-sun="disc" mask="url(#title-carve-sun)">{halo}'
            f'<circle cx="{x}" cy="{y}" r="{SUN_RADIUS}" fill="{colour}"/>'
            f'<circle cx="{x}" cy="{y}" r="{SUN_RADIUS-8}" fill="#fffbe6" opacity=".7"/></g>')


def lighting_markup(light):
    """Sky overlay (clipped to the sky), sun, and foreground lift, drawn between the plate and the moving art."""
    gx, gr = light['glow_x'], GLOW_RADII
    sky = ''
    if light['top_opacity'] > 0 or light['horizon_opacity'] > 0:
        sky += f'<g data-light="sky" mask="url(#title-carve-sky)"><rect width="{W}" height="{HORIZON_Y+8}" fill="url(#sky-grad)"/></g>'
    if light['glow'] > .005:
        sky += (f'<g mask="url(#title-carve-sky)"><ellipse data-light="glow" cx="{_num(gx, 1)}" cy="{HORIZON_Y+30}" rx="{gr[0]}" ry="{gr[1]}" '
                f'fill="url(#sky-glow)" opacity="{_num(light["glow"], 4)}"/></g>')
    if light['sun']:
        sky += sun_markup(light)
    out = f'<g data-light="sky-group" clip-path="url(#sky-clip)">{sky}</g>' if sky else ''
    if light['foreground'] > .001:
        edge = 'M'+'L'.join(f'{x} {y}' for x, y in SKYLINE+[(W, H), (0, H)])+'Z'
        out += (f'<path data-light="foreground" d="{edge}" fill="{_rgb(FOREGROUND_LIFT[1])}" '
                f'opacity="{_num(light["foreground"], 4)}"/>')
    return out


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
    parts+=[feather_defs(),twinkle_defs(),meteor_defs()]+([] if light is None else [lighting_defs(light)])
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
