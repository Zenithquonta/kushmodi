"""Build the day and golden-hour foreground plates from the night painting (offline; the outputs are committed).

The painted plate is night-only. Its silhouettes still hold the painted texture in the darks, so a daytime version is
derived per region rather than tinted: moonlit blues become sunlit foliage, wood, metal or haze, the lamp-lit wood
and glowing screens keep their own colours, and a shadow floor stops pure black from reading as night. The result is
an RGBA image covering only the ground (the sky mask is transparent), which the renderer fades in over the plate.

    python scripts/build_day_art.py   # writes assets/observatory-day.png, -golden.png and -dry.png (vegetation only)

Build-time dependencies: Pillow and NumPy. The renderer itself never needs NumPy.
"""
import argparse
import base64
import io
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

import build_animation as scene

# Regions in plate pixels. Each becomes a feathered weight map; whatever no region claims is vegetation and earth.
TELESCOPE = [(782, 540), (868, 540), (872, 660), (885, 842), (690, 842), (735, 700), (745, 640)]
VAN = [(0, 572), (285, 572), (285, 778), (0, 778)]
WORKSHOP = [(1162, 612), (1672, 478), (1672, 941), (1250, 941), (1250, 905), (1162, 905)]
ROVER = [(1082, 796), (1262, 796), (1262, 908), (1082, 908)]
ROCK = [(622, 770), (650, 702), (700, 682), (760, 690), (800, 712), (880, 740), (884, 805), (622, 805)]
DISTANCE = scene.FAR_BAND   # mountains, city and the far tree line
FEATHER = 4
DISTANCE_FEATHER = 18

# (hue for moonlit blues, saturation gain, saturation cap, shadow floor rgb) per region.
MATERIALS = dict(vegetation=(86, .85, .6, (.06, .085, .045)),
                 telescope=(40, .12, .08, (.16, .17, .18)),
                 van=(48, .45, .32, (.12, .12, .09)),
                 workshop=(30, .7, .5, (.10, .075, .05)),
                 rover=(40, .2, .15, (.14, .14, .14)),
                 rock=(34, .25, .16, (.11, .105, .095)))
DRY_VEGETATION = (38, .9, .5, (.1, .08, .04))   # straw and dust for the dry seasons

# (gamma, exposure, final rgb multiplier, haze rgb, haze share in the far band)
GRADES = dict(day=(.5, 1.0, (1.0, 1.0, .95), (.66, .74, .84), .55),
              golden=(.6, .88, (1.14, .9, .64), (.78, .72, .74), .45))
GRADES['dry'] = GRADES['day']   # vegetation only, laid over the day plate as the land dries out


def _hsv(a):
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    mx, mn = a.max(-1), a.min(-1)
    d = mx-mn
    h = np.zeros_like(mx)
    nz = d > 1e-6
    rm = nz & (mx == r)
    gm = nz & (mx == g) & ~rm
    bm = nz & ~rm & ~gm
    h[rm] = ((g-b)[rm]/d[rm]) % 6
    h[gm] = (b-r)[gm]/d[gm]+2
    h[bm] = (r-g)[bm]/d[bm]+4
    return h*60, np.where(mx > 1e-6, d/np.maximum(mx, 1e-6), 0), mx


def _rgb(h, s, v):
    c = v*s
    hp = (h % 360)/60
    x = c*(1-np.abs(hp % 2-1))
    z = np.zeros_like(h)
    sector = np.minimum(hp.astype(int), 5)
    r = np.choose(sector, [c, x, z, z, x, c])
    g = np.choose(sector, [x, c, c, x, z, z])
    b = np.choose(sector, [z, z, x, c, c, x])
    return np.stack([r, g, b], -1)+(v-c)[..., None]


def _weight(polygon, feather):
    image = Image.new('L', (scene.W, scene.H), 0)
    ImageDraw.Draw(image).polygon(polygon, fill=255)
    return np.asarray(image.filter(ImageFilter.GaussianBlur(feather)), float)/255


def _ground():
    uri = scene.plate_masks()['ground']
    return np.asarray(Image.open(io.BytesIO(base64.b64decode(uri.split(',', 1)[1]))).convert('L')) > 0


def build(grade):
    gamma, exposure, multiplier, haze, haze_share = GRADES[grade]
    plate = np.asarray(Image.open(scene.ASSETS/'observatory-background.png').convert('RGB'), float)/255
    h, s, v = _hsv(plate)
    cool = (h > 170) & (h < 320)
    # Light sources keep their colour: lamp-lit wood and the lantern (warm, saturated) and glowing screens and neon.
    emissive = ((h >= 12) & (h <= 62) & (s > .35) & (v > .35)) | ((s > .45) & (v > .55))
    lifted = np.clip(exposure*v**gamma, 0, 1)

    weights = {name: _weight(poly, FEATHER) for name, poly in
               (('telescope', TELESCOPE), ('van', VAN), ('workshop', WORKSHOP), ('rover', ROVER), ('rock', ROCK))}
    # The telescope stands in front of the rock.
    weights['rock'] = weights['rock']*(1-weights['telescope'])
    weights['vegetation'] = np.clip(1-sum(weights.values()), 0, 1)
    out = np.zeros_like(plate)
    materials = dict(MATERIALS, vegetation=DRY_VEGETATION) if grade == 'dry' else MATERIALS
    for name, (hue, gain, cap, floor) in materials.items():
        hue_map = np.where(cool, hue+(h-245)*.12, h)
        sat_map = np.where(cool, np.minimum(s*gain, cap), np.minimum(s, .75))
        relit = _rgb(hue_map, sat_map, lifted)
        floor = np.array(floor)
        out += weights[name][..., None]*(floor+relit*(1-floor))

    # The far band keeps its own blue and fades into haze; its city lights are off by day.
    far = _weight(DISTANCE, DISTANCE_FEATHER)
    distant = np.array(haze)*haze_share+_rgb(h, np.minimum(s*.5, .3), lifted)*(1-haze_share)
    out = out*(1-far[..., None])+distant*far[..., None]
    out = out*np.array(multiplier)
    keep = (emissive & (far < .5))[..., None]
    out = np.where(keep, plate*.65+out*.35, out)
    ground = _ground()
    alpha = ground.astype(float)
    if grade == 'dry':
        alpha = alpha*weights['vegetation']*(1-far)*~emissive
    alpha = (alpha*255).round().astype(np.uint8)
    rgb = (np.clip(out, 0, 1)*255).round().astype(np.uint8)*(alpha > 0)[..., None]   # zeroed sky compresses to nothing
    rgba = np.dstack([rgb, alpha])
    return Image.fromarray(rgba, 'RGBA')


def main():
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('--out', type=Path, default=scene.ASSETS)
    args = parser.parse_args()
    for grade in GRADES:
        path = args.out/f'observatory-{grade}.png'
        build(grade).save(path, optimize=True)
        print(path, path.stat().st_size)


if __name__ == '__main__':
    main()
