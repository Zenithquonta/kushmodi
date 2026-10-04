"""Derive the 2.5D website scenery sprites from the committed reference artwork.

Pillow + numpy only (numpy ships with Pillow's usual install; it is a build-time tool, not used by CI).
Run from the repository root:  python scripts/site_sprites.py [--only name,...] [--preview DIR]
Originals under assets/ are never modified. Outputs go to site/data/scenery/*.webp.
Every derived file and its method is recorded in docs/WEBSITE-ART.md.
"""
from __future__ import annotations
import argparse, collections, math, os
import numpy as np
from PIL import Image, ImageFilter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'site', 'data', 'scenery')
BG = Image.open(os.path.join(ROOT, 'assets', 'observatory-background.png')).convert('RGB')


def lum(a):
    return (a[..., 0] * 0.3 + a[..., 1] * 0.55 + a[..., 2] * 0.15)


def shift(m, dx, dy):
    out = np.zeros_like(m)
    h, w = m.shape
    ys, yd = (slice(max(0, -dy), h - max(0, dy)), slice(max(0, dy), h - max(0, -dy)))
    xs, xd = (slice(max(0, -dx), w - max(0, dx)), slice(max(0, dx), w - max(0, -dx)))
    out[yd, xd] = m[ys, xs]
    return out


def dilate(m, r):
    out = m.copy()
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            if dx * dx + dy * dy <= r * r + 1:
                out |= shift(m, dx, dy)
    return out


def erode(m, r):
    return ~dilate(~m, r)


def close(m, r):
    return erode(dilate(m, r), r)


def open_(m, r):
    return dilate(erode(m, r), r)


def component(mask, seeds):
    """Connected region(s) of `mask` (4-connected) reachable from the seed points."""
    h, w = mask.shape
    seen = np.zeros_like(mask)
    q = collections.deque()
    for x, y in seeds:
        if mask[y, x] and not seen[y, x]:
            seen[y, x] = True
            q.append((x, y))
    while q:
        x, y = q.popleft()
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if 0 <= nx < w and 0 <= ny < h and mask[ny, nx] and not seen[ny, nx]:
                seen[ny, nx] = True
                q.append((nx, ny))
    return seen


def fill_holes(m, max_area=40):
    """Fill enclosed holes smaller than max_area px; larger enclosed gaps (sky between tripod legs) stay open."""
    h, w = m.shape
    outside = component(~m, [(0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)] + [(x, 0) for x in range(0, w, 7)])
    holes = ~m & ~outside
    out = m.copy()
    seen = np.zeros_like(m)
    for y, x in zip(*np.nonzero(holes)):
        if seen[y, x]:
            continue
        comp = component(holes, [(x, y)])
        seen |= comp
        if comp.sum() <= max_area:
            out |= comp
    return out


def defringe(img, strength=0.3):
    """Darken the one-pixel rim so the sky colour that bled into edge pixels does not glow around the sprite."""
    arr = np.asarray(img).copy()
    a = arr[..., 3] > 128
    rim = a & ~erode(a, 1)
    arr[rim, :3] = (arr[rim, :3] * strength).astype(np.uint8)
    return Image.fromarray(arr, 'RGBA')


def to_rgba(box, mask, feather=0.0, fade=None):
    crop = np.asarray(BG.crop(box)).astype(np.uint8)
    alpha = (np.clip(mask, 0, 1) * 255).astype(np.uint8)
    img = Image.fromarray(np.dstack([crop, alpha]), 'RGBA')
    if feather:
        a = img.getchannel('A').filter(ImageFilter.GaussianBlur(feather))
        a = a.point(lambda v: 255 if v > 150 else (0 if v < 60 else int((v - 60) * 255 / 90)))
        img.putalpha(a)
    if fade:                                   # fade: (left, right, top, bottom) fractions that taper to transparent
        arr = np.asarray(img).copy()
        h, w = arr.shape[:2]
        f = np.ones((h, w))
        l, r, t, b = fade
        xs = np.linspace(0, 1, w)[None, :]
        ys = np.linspace(0, 1, h)[:, None]
        if l: f *= np.clip(xs / l, 0, 1)
        if r: f *= np.clip((1 - xs) / r, 0, 1)
        if t: f *= np.clip(ys / t, 0, 1)
        if b: f *= np.clip((1 - ys) / b, 0, 1)
        arr[..., 3] = (arr[..., 3] * f).astype(np.uint8)
        img = Image.fromarray(arr, 'RGBA')
    return img


def trim(img, pad=2):
    bbox = img.getchannel('A').point(lambda v: 255 if v > 8 else 0).getbbox()
    if not bbox:
        return img
    l, t, r, b = bbox
    return img.crop((max(0, l - pad), max(0, t - pad), min(img.width, r + pad), min(img.height, b + pad)))


def silhouette(box, seeds, thr=46, closing=2, grow=1, keep_bottom=False):
    a = np.asarray(BG.crop(box)).astype(float)
    dark = lum(a) < thr
    dark = close(dark, closing)
    m = component(dark, seeds)
    m = fill_holes(m)
    m = open_(m, 1)
    if grow:
        m = dilate(m, grow)
    return m


def lift(img, gamma=0.62, blue=1.06):
    """Open up the near-black silhouette body so it keeps some form against a dark real sky."""
    arr = np.asarray(img).astype(float)
    rgb = 255.0 * (arr[..., :3] / 255.0) ** gamma
    rgb[..., 2] = np.minimum(255, rgb[..., 2] * blue)
    arr[..., :3] = rgb
    return Image.fromarray(arr.astype(np.uint8), 'RGBA')


def telescope():
    box = (612, 522, 900, 842)
    m = silhouette(box, [(180, 260), (150, 270), (110, 130), (100, 100)], thr=52, closing=2, grow=1)
    a = np.asarray(BG.crop(box)).astype(float)
    extra = np.zeros_like(m)                       # counterweight bar, a thin shaft the global threshold drops
    extra[135:172, 118:170] = lum(a)[135:172, 118:170] < 62
    extra = close(extra, 2)
    m |= extra
    yy, xx = np.mgrid[0:m.shape[0], 0:m.shape[1]]
    m &= ~((yy > 205) & (xx > 236 + (yy - 205) * 0.22))     # distant mountains and city lights behind the right leg
    img = lift(defringe(to_rgba(box, m, feather=0.7)))
    arr = np.asarray(img).copy()
    h, w = arr.shape[:2]
    yy, xx = np.mgrid[0:h, 0:w]
    # The rock under the tripod was cut by the reference crop. Drop the dark rock mass and keep only the lit tripod legs and pier
    # (a separate authored rock stands behind the telescope in the scene), then dissolve the leg ends into the ground.
    lumv = lum(arr[..., :3].astype(float))
    lit = (arr[..., 3] > 128) & (lumv > 40)
    keep = dilate(lit & (yy > 190), 7)
    from PIL import ImageDraw
    tri = Image.new('L', (w, h), 0)
    ImageDraw.Draw(tri).polygon([(176, 185), (256, 185), (264, h), (84, h), (82, 292), (96, 268)], fill=255)
    keep &= np.asarray(tri) > 0
    drop = (yy > 190) & ~keep
    arr[..., 3] = np.where(drop, 0, arr[..., 3])
    arr[..., 3] = (arr[..., 3] * np.clip((h - yy) / 30.0, 0, 1)).astype(np.uint8)
    return Image.fromarray(arr, 'RGBA')


def van():
    box = (0, 560, 300, 800)
    m = silhouette(box, [(150, 150), (40, 150), (230, 120), (150, 220)], thr=58, closing=2, grow=0)
    return lift(defringe(to_rgba(box, m, feather=0.6, fade=(0.24, 0, 0, 0.14))), 0.7)


def roofline_mask(shape, box_off):
    """Polygon under the workshop roof edge, in crop coordinates (found by overlaying a grid on the reference)."""
    h, w = shape
    img = Image.new('L', (w, h), 0)
    from PIL import ImageDraw
    d = ImageDraw.Draw(img)
    ox = box_off
    pts = [(82 - ox, 141), (400 - ox, 60), (w + 5, 14), (w + 5, h), (152 - ox, h), (152 - ox, 322), (103 - ox, 322), (103 - ox, 152), (82 - ox, 150)]
    d.polygon(pts, fill=255)
    return np.asarray(img) > 128


def workshop():
    box = (1085 + 80, 480, 1672, 941)
    m = roofline_mask((461, 1672 - 1085 - 80 + 0), 80 - 0)
    m = m[:, : box[2] - box[0]]
    img = to_rgba(box, m, feather=0.6, fade=(0, 0, 0, 0.05))
    return hang_sign(img)


def hang_sign(img):
    """Paint a small hanging name board under the roof beam (the old 3D shed carried the same label)."""
    from PIL import ImageDraw, ImageFont
    d = ImageDraw.Draw(img)
    x0, y0, x1, y1 = 30, 152, 168, 182
    d.line([(x0 + 14, 148), (x0 + 14, y0)], fill=(60, 44, 30, 255), width=2)
    d.line([(x1 - 14, 140), (x1 - 14, y0)], fill=(60, 44, 30, 255), width=2)
    d.rectangle([x0, y0, x1, y1], fill=(24, 40, 46, 255), outline=(72, 147, 155, 255), width=2)
    try:
        big = ImageFont.load_default(size=12)
        small = ImageFont.load_default(size=7)
    except TypeError:                                   # very old Pillow: bitmap font
        big = small = ImageFont.load_default()
    d.text((x0 + 8, y0 + 3), 'MAKER WORKSHOP', font=big, fill=(196, 225, 216, 255))
    d.text((x0 + 9, y0 + 20), 'CAD / ROBOTICS / FABRICATION', font=small, fill=(213, 170, 113, 255))
    return img


def rover():
    """Hand-traced outline of the rover (pixel coordinates read off a gridded crop of the reference)."""
    from PIL import ImageDraw
    box = (1085, 805, 1235, 925)
    h, w = box[3] - box[1], box[2] - box[0]
    pts = [(95, 0), (127, 0), (128, 20), (118, 24), (116, 38), (126, 43), (140, 44), (140, 56), (122, 58), (126, 66), (138, 76),
           (136, 90), (122, 92), (100, 102), (80, 102), (66, 90), (52, 80), (42, 82), (32, 100), (14, 98), (6, 84), (6, 64),
           (14, 56), (26, 56), (27, 38), (66, 28), (90, 26), (94, 14)]
    mask = Image.new('L', (w, h), 0)
    ImageDraw.Draw(mask).polygon(pts, fill=255)
    return defringe(to_rgba(box, np.asarray(mask) > 128, feather=0.6), 0.5)


def crown(box, seeds, thr=40, fade_bottom=0.35):
    """Cut a tree crown from the reference where it is bounded by open sky; the dark lower mass fades into the foreground."""
    m = silhouette(box, seeds, thr=thr, closing=2, grow=0)
    return trim(lift(defringe(to_rgba(box, m, feather=0.6, fade=(0, 0, 0, fade_bottom))), 0.8, 1.0))


def tree_a():
    return crown((262, 622, 342, 716), [(30, 50), (40, 60), (20, 70), (50, 80)])


def tree_b():
    return crown((392, 664, 452, 752), [(30, 40), (25, 60), (35, 70)])


def tree_c():
    return crown((1094, 634, 1162, 736), [(40, 40), (45, 60), (30, 70), (40, 80)])


def rng_seed(seed):
    return np.random.default_rng(seed)


def periodic_profile(n, seed, octaves=70, slope=1.05):
    r = rng_seed(seed)
    u = np.arange(n) / n
    h = np.zeros(n)
    for k in range(1, octaves):
        h += (k ** -slope) * np.sin(2 * math.pi * (k * u + r.random()))
    h = (h - h.min()) / (h.max() - h.min())
    return h


def ridge(seed, base, amp, serrate, light_top, light_bot, width=4096, height=320, north_low=0.35):
    """A tileable painted ridge silhouette (luminance only; the page tints it by the real horizon colour)."""
    h = periodic_profile(width, seed)
    u = np.arange(width) / width
    north = np.cos(2 * math.pi * u)                       # +1 at north (u=0), -1 at south
    mod = 1 - (1 - north_low) * np.clip((north + 0.2) / 1.0, 0, 1) ** 1.3
    top = base + amp * h * mod
    r = rng_seed(seed + 7)
    if serrate:                                          # conifer / canopy teeth along the crest
        tooth = np.repeat(r.random(width // 6 + 1), 6)[:width]
        tri = (np.arange(width) % 14) / 14.0
        top += serrate * (np.abs(tri - 0.5) * 2) * (0.45 + 0.55 * tooth)
    top = np.round(top / 3) * 3                           # stepped, pixel-art crest
    ys = np.arange(height)[:, None]
    crest = (height - top)[None, :]
    alpha = (ys >= crest)
    depth = np.clip((ys - crest) / 160.0, 0, 1)
    lum = light_top + (light_bot - light_top) * depth
    strata = (r.random((height, width // 8 + 1)).repeat(8, axis=1)[:, :width] - 0.5) * 24
    lum = lum + strata * (0.5 + depth)
    edge = (ys >= crest) & (ys < crest + 3)
    lum = np.where(edge, np.minimum(255, lum + 34), lum)
    lum = np.clip(lum, 0, 255).astype(np.uint8)
    rgb = np.dstack([lum, lum, np.clip(lum * 1.05, 0, 255).astype(np.uint8)])
    a = (alpha * 255).astype(np.uint8)
    return Image.fromarray(np.dstack([rgb, a]), 'RGBA')


def ridge_far():
    return ridge(11, base=60, amp=95, serrate=0, light_top=255, light_bot=200)


def ridge_mid():
    return ridge(23, base=48, amp=80, serrate=6, light_top=235, light_bot=150)


def ridge_near():
    return ridge(37, base=40, amp=62, serrate=16, light_top=205, light_bot=120, north_low=0.2)


def tile_noise(n, seed, cells):
    r = rng_seed(seed)
    g = r.random((cells, cells))
    big = np.kron(g, np.ones((n // cells, n // cells)))
    out = np.zeros((n, n))
    # smooth periodic interpolation via FFT low-pass of white noise
    f = np.fft.fft2(r.standard_normal((n, n)))
    ky = np.fft.fftfreq(n)[:, None]; kx = np.fft.fftfreq(n)[None, :]
    k = np.sqrt(kx * kx + ky * ky) + 1e-6
    return np.real(np.fft.ifft2(f * (cells / n) ** 0 * np.exp(-(k * cells / 2.2) ** 2) * 1.0)), big


def ground():
    n = 256
    r = rng_seed(5)
    acc = np.zeros((n, n))
    for cells, wgt, sd in ((6, 1.0, 1), (16, 0.55, 2), (48, 0.3, 3)):
        a, _ = tile_noise(n, sd, cells)
        a = (a - a.min()) / (a.max() - a.min())
        acc += wgt * a
    acc = (acc - acc.min()) / (acc.max() - acc.min())
    lum = 0.52 + 0.3 * acc
    # grass tufts (short vertical strokes), pebbles and dry flecks
    img = lum.copy()
    for _ in range(900):
        x, y = r.integers(0, n), r.integers(0, n)
        for j in range(r.integers(2, 5)):
            img[(y - j) % n, (x + (j // 2) * (1 if r.random() < .5 else 0)) % n] *= 0.72
    for _ in range(220):
        x, y = r.integers(0, n), r.integers(0, n)
        v = 1.18 + 0.2 * r.random()
        img[y, x] *= v; img[y, (x + 1) % n] *= v * 0.95; img[(y + 1) % n, x] *= 0.8
    for _ in range(160):
        x, y = r.integers(0, n), r.integers(0, n)
        img[y, x] = min(1.2, img[y, x] * 1.5); img[(y - 1) % n, x] *= 1.3
    img = np.clip(img, 0, 1.0)
    rgb = np.dstack([img * 0.97, img * 0.97, img * 0.92])
    return Image.fromarray((rgb * 255).astype(np.uint8), 'RGB')


def rock(seed, w=170, h=120):
    """A dark boulder in the reference's style: lumpy fractal relief, cool moonlit upper edge, warm bounce, grain and fissures."""
    r = rng_seed(seed)
    yy, xx = np.mgrid[0:h, 0:w]
    cx, cy = w / 2, h * 0.62
    ang = np.arctan2((yy - cy) / (h * 0.5), (xx - cx) / (w * 0.5))
    rad = np.hypot((xx - cx) / (w * 0.5), (yy - cy) / (h * 0.62))
    wob = sum(r.random() * 0.08 / k * np.sin(k * ang + r.random() * 6.28) for k in range(2, 12))
    edge = 0.92 + wob
    inside = (rad < edge) & (yy < h - 2)
    dome = np.sqrt(np.clip(1 - np.minimum(rad / edge, 1) ** 2, 0, 1))
    n1, _ = tile_noise(256, seed, 5)
    n2, _ = tile_noise(256, seed + 1, 22)
    f = lambda a: (a - a.min()) / (a.max() - a.min())
    relief = dome * 0.9 + 0.35 * f(n1)[:h, :w] + 0.12 * f(n2)[:h, :w]
    gy, gx = np.gradient(relief)
    nx, ny = -gx * 7, -gy * 7
    ln = np.sqrt(nx * nx + ny * ny + 1)
    light = np.clip((nx * -0.5 + ny * -0.8 + 0.6) / ln, 0, 1)
    rim = np.clip((rad / edge - 0.7) / 0.3, 0, 1) * (yy < cy) * (xx < cx * 1.25)
    light = np.floor(np.clip(light * 0.8 + rim * 0.55, 0, 1) * 6) / 6
    base = np.array([20, 26, 38]) / 255.0
    cool = np.array([88, 118, 150]) / 255.0
    rgb = base * (0.7 + 0.5 * light[..., None]) + cool * (light[..., None] ** 2.2) * 0.55
    rgb += np.array([0.09, 0.045, 0.0]) * np.clip((yy[..., None] / h - 0.55) / 0.45, 0, 1)
    grain = r.random((h, w, 1))
    rgb *= 0.82 + 0.3 * grain ** 2
    ridge_line = np.abs(f(n2)[:h, :w] - 0.5) < 0.012
    rgb[ridge_line] *= 0.55
    moss = (f(n1)[:h, :w] > 0.8) & (yy < cy + 6) & (light < 0.75)
    rgb[moss] = rgb[moss] * 0.6 + np.array([0.03, 0.12, 0.08])
    rgb = np.clip(rgb, 0, 1)
    a = (inside * 255).astype(np.uint8)
    img = Image.fromarray(np.dstack([(rgb * 255).astype(np.uint8), a]), 'RGBA')
    return img.filter(ImageFilter.UnsharpMask(1, 40, 2)) if False else img


def rock_a(): return trim(rock(3))
def rock_b(): return trim(rock(8, 130, 90))
def rock_c(): return trim(rock(13, 100, 70))


def lantern():
    """A small pixel-art path lantern on a post, matching the amber lanterns in the reference."""
    from PIL import ImageDraw
    img = Image.new('RGBA', (20, 40), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rectangle([9, 18, 10, 39], fill=(38, 52, 58, 255))                       # post
    d.rectangle([5, 14, 14, 17], fill=(70, 88, 90, 255))                       # base plate
    d.rectangle([6, 5, 13, 13], fill=(255, 190, 100, 255))                     # glass
    d.rectangle([7, 6, 12, 12], fill=(255, 232, 170, 255))
    d.rectangle([8, 7, 11, 11], fill=(255, 250, 220, 255))
    for x in (6, 13):
        d.line([(x, 5), (x, 13)], fill=(40, 48, 52, 255))
    d.rectangle([5, 3, 14, 4], fill=(70, 88, 90, 255))                         # cap
    d.rectangle([8, 1, 11, 2], fill=(70, 88, 90, 255))
    return img


JOBS = {'lantern': lantern, 'tree_c': tree_c, 'ridge_far': ridge_far, 'ridge_mid': ridge_mid, 'ridge_near': ridge_near, 'ground': ground, 'rock_a': rock_a, 'rock_b': rock_b, 'rock_c': rock_c, 'workshop': workshop, 'rover': rover, 'tree_a': tree_a, 'tree_b': tree_b, 'telescope': telescope, 'van': van}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--only')
    ap.add_argument('--preview')
    args = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    for name, fn in JOBS.items():
        if args.only and name not in args.only.split(','):
            continue
        img = fn()
        if img.mode == 'RGBA':                       # clean colour under fully transparent pixels so mip filtering cannot bleed sky colour
            arr = np.asarray(img).copy()
            arr[arr[..., 3] == 0, :3] = 0
            img = Image.fromarray(arr, 'RGBA')
        img.save(os.path.join(OUT, name + '.webp'), 'WEBP', quality=88, method=6)
        if args.preview:
            os.makedirs(args.preview, exist_ok=True)
            bgc = Image.new('RGBA', img.size, (200, 60, 200, 255))
            bgc.alpha_composite(img.convert('RGBA'))
            bgc.save(os.path.join(args.preview, name + '.png'))
        print(name, img.size, os.path.getsize(os.path.join(OUT, name + '.webp')))


if __name__ == '__main__':
    main()
