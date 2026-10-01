#!/usr/bin/env python3
"""Build the observatory SVG and render a portable GIF with FFmpeg/librsvg.

The background and transparent sprites are authored with image generation.
This script composes those layers and defines their animation timelines.
"""
import argparse
import base64
from concurrent.futures import ThreadPoolExecutor
import math
from pathlib import Path
import random
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / 'assets'
W, H, PERIOD = 1672, 941, 24
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


def rotate_node(name, width, x, y, angle, animated, seconds=24):
    motion = (f'<animateTransform attributeName="transform" type="rotate" '
              f'from="{angle}" to="{angle+360}" dur="{seconds}s" repeatCount="indefinite"/>' if animated else '')
    return f'<g transform="translate({x:.3f} {y:.3f})"><g transform="rotate({angle:.3f})">{motion}{sprite(name,width)}</g></g>'


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


def celestial(t, animated):
    parts = [rotate_node('galaxy', 390, 810, 184, t*360/PERIOD, animated),
             rotate_node('galaxy', 137, 1128, 228, -t*360/12, animated, seconds=12)]
    # Secondary galaxy counter-rotates with an independent 12-second loop.
    if animated:
        parts[1] = (f'<g transform="translate(1128 228)"><g><animateTransform attributeName="transform" '
                    f'type="rotate" from="0" to="-360" dur="12s" repeatCount="indefinite"/>{sprite("galaxy",137)}</g></g>')
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


def _x_keys(start, end, pairs):
    """[(x, value)] along a straight route -> [(u, value)] padded to u=0 and u=1."""
    keys = [((x-start)/(end-start), v) for x, v in pairs]
    if keys[0][0] > 0:
        keys.insert(0, (0, keys[0][1]))
    if keys[-1][0] < 1:
        keys.append((1, keys[-1][1]))
    return keys


def _interp(keys, u):
    for (u0, v0), (u1, v1) in zip(keys, keys[1:]):
        if u <= u1:
            return v0 + (v1-v0)*(u-u0)/(u1-u0) if u1 > u0 else v1
    return keys[-1][1]


def _route(oid, sprite_name, width, y_at, fade_at, start, end, period, phase):
    return dict(id=oid, sprite=sprite_name, width=width, start=start, end=end, period=period, phase=phase,
                y_keys=_x_keys(start, end, y_at), fade_keys=_x_keys(start, end, fade_at))


# Fades are written as (x, opacity); every key is a straight segment, so SMIL keyTimes reproduce them.
ROUTES = [
    # Hero ship: leaves visibility before the text block instead of being clipped by a hard edge.
    _route('explorer', 'explorer', 295, [(1900, 338)], [(900, 1), (720, 0)], 1900, 490, 24, .31),
    _route('fighter-a', 'fighter', 133, [(1840, 434)], [(1340, 0), (1170, 1)], 1840, -170, 12, .15),
    _route('fighter-b', 'fighter', 103, [(1840, 458)], [(1330, 0), (1150, 1)], 1840, -170, 12, .245),
    # Airliner stays in open sky and dissolves before the workshop roof and right-hand trees.
    _route('airplane', 'airplane', 142, [(-200, 518)], [(1180, 1), (1330, 0)], -200, 1830, 24, .23),
]


def _box(rel, scale, node):
    l, t, r, b = rel
    return (node[0]+l*scale, node[1]+t*scale, node[0]+r*scale, node[1]+b*scale)


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
        sprite_box = _box((l-BOX_PAD/scale, tp-BOX_PAD/scale, r+BOX_PAD/scale, b+BOX_PAD/scale), scale, (x, y))
        trail_box = _box(TRAIL_BOX[route['sprite']], 1, (x, y))
        states.append(dict(id=route['id'], sprite=route['sprite'], width=route['width'], x=x, y=y, u=u,
                           opacity=opacity, sprite_bbox=sprite_box, trail_bbox=trail_box,
                           bbox=(min(sprite_box[0], trail_box[0]), min(sprite_box[1], trail_box[1]),
                                 max(sprite_box[2], trail_box[2]), max(sprite_box[3], trail_box[3]))))
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


def traffic(t, animated):
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
        parts.append(_trail_markup(route['sprite'])+sprite(route['sprite'], route['width'])+'</g></g>')
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
    parts.append('<path d="M811 551L1020 97L1460 133" fill="none" stroke="#40daed" stroke-width="1.6" stroke-dasharray="6 11" opacity=".38"/>')
    reticle=Track.sine(.5,.3,3)
    parts.append(f'<g opacity="{reticle.value_text(t)}">{reticle.smil("opacity") if animated else ""}'
                 '<path d="M996 94V72H1013M1028 72H1045V94M1045 104V121H1028M1013 121H996V104" fill="none" stroke="#4ae8f2" stroke-width="2"/></g>')
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


def layers(t, animated):
    return celestial(t,animated)+traffic(t,animated)+sky_details(t,animated)+workshop(t,animated)


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


def scene(t=0, animated=False, embedded=True):
    parts=[f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-labelledby="title desc">',
           '<title id="title">Kush Modi — building toward the unexplored</title>',
           '<desc id="desc">Pixel observatory based on Kush\'s telescope photograph. Rotating galaxies, planetary moons, exploration spacecraft, an airplane and a working maker workshop.</desc>',
           '<defs>',
           f'<image id="atlas" width="1536" height="1024" href="{ATLAS}" xlink:href="{ATLAS}"/>']
    parts+=[feather_defs(),'</defs>',
            f'<image id="plate" width="{W}" height="{H}" href="{BACKGROUND}" xlink:href="{BACKGROUND}"/>']
    if animated:
        parts.append('<style>.still{display:none}@media(prefers-reduced-motion:reduce){.moving{display:none}.still{display:inline}}</style>')
        parts.append('<g class="moving">'+layers(t,True)+'</g><g class="still">'+layers(0,False)+'</g>')
    else:
        parts.append(layers(t,False))
    parts.append('</svg>')
    # SVG2 href and xlink fallback need only one copy of raster data.
    result=''.join(parts)
    result=result.replace(f' href="{ATLAS}"','').replace(f' href="{BACKGROUND}"','')
    return result


def rasterize(svg_path,png_path,width=1000):
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
        subprocess.run(['ffmpeg','-v','error','-framerate',str(fps),'-i',str(temp/'frame-%04d.png'),
                        '-vf','palettegen=max_colors=256:stats_mode=full','-frames:v','1','-threads','1','-y',str(temp/'palette.png')],check=True)
        subprocess.run(['ffmpeg','-v','error','-framerate',str(fps),'-i',str(temp/'frame-%04d.png'),
                        '-i',str(temp/'palette.png'),'-lavfi','paletteuse=dither=bayer:bayer_scale=3',
                        '-loop','0','-threads','1','-y',str(ASSETS/'observatory.gif')],check=True)
        shutil.copyfile(temp/'frame-0000.png',ASSETS/'observatory-poster.png')
    print(f'GIF exported: {(ASSETS/"observatory.gif").stat().st_size:,} bytes',flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--gif',action='store_true')
    parser.add_argument('--fps',type=int,default=10)
    parser.add_argument('--width',type=int,default=1000)
    args=parser.parse_args()
    (ASSETS/'observatory.svg').write_text(scene(animated=True))
    (ASSETS/'poster.svg').write_text(scene(0,False))
    rasterize(ASSETS/'poster.svg',ASSETS/'observatory-poster.png',args.width)
    print('Animated SVG and poster exported',flush=True)
    if args.gif:
        export_gif(args.fps,args.width)


if __name__=='__main__':
    main()
