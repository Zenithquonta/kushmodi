"""Day/night lighting: unchanged default output, sky/title masks, fades, sun, day plates, atomic live render."""
import base64
from datetime import datetime
import hashlib
import importlib.util
import io
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock
from zoneinfo import ZoneInfo

import build_animation as scene
import render_live
import scene_state

IST = ZoneInfo('Asia/Kolkata')
NIGHT = datetime(2026, 12, 14, 23, 0, tzinfo=IST)
NOON = datetime(2026, 12, 14, 12, 30, tzinfo=IST)


def mask_image(name):
    from PIL import Image
    return Image.open(io.BytesIO(base64.b64decode(scene.plate_masks()[name].split(',', 1)[1]))).convert('L')


def has_librsvg():
    if not shutil.which('ffmpeg'):
        return False
    decoders = subprocess.run(['ffmpeg', '-hide_banner', '-decoders'], capture_output=True, text=True).stdout
    return 'librsvg' in decoders


class DefaultOutput(unittest.TestCase):
    def test_scene_without_state_matches_the_published_assets(self):
        assets = scene.ASSETS
        self.assertEqual(hashlib.sha256(scene.scene(animated=True).encode()).hexdigest(),
                         hashlib.sha256((assets/'observatory.svg').read_bytes()).hexdigest())
        self.assertEqual(scene.scene(0, False), (assets/'poster.svg').read_text())


class Lighting(unittest.TestCase):
    def test_night_keeps_the_sky_and_has_no_sun(self):
        svg = scene.scene(0, False, state=scene_state.scene_state(NIGHT))
        self.assertTrue(re.findall(r'data-night="[^"]+" opacity="([^"]+)"', svg))
        self.assertTrue(all(float(v) == 1 for v in re.findall(r'data-night="[^"]+" opacity="([^"]+)"', svg)))
        self.assertNotIn('data-sun', svg)

    def test_noon_hides_celestial_layers_and_shows_the_sun(self):
        svg = scene.scene(0, False, state=scene_state.scene_state(NOON))
        self.assertTrue(all(float(v) == 0 for v in re.findall(r'data-night="[^"]+" opacity="([^"]+)"', svg)))
        self.assertIn('data-sun="disc"', svg)
        self.assertIn('mask="url(#sky-mask)"', svg)
        self.assertNotIn('clip-path="url(#sky-clip)"', svg)

    def test_sky_overlay_never_dims_as_the_sun_climbs(self):
        previous = None
        for tenth in range(-250, 650):
            _, top, _, horizon = scene.sky_colours(tenth/10)
            if previous:
                self.assertGreaterEqual(top, previous[0]-1e-9)
                self.assertGreaterEqual(horizon, previous[1]-1e-9)
            previous = (top, horizon)

    def test_faint_sky_art_is_gone_before_civil_twilight_and_full_in_darkness(self):
        self.assertEqual(scene.night_factor(-18), 1)
        self.assertEqual(scene.night_factor(-14), 1)
        self.assertEqual(scene.night_factor(-4), 0)
        self.assertEqual(scene.night_factor(0), 0)
        values = [scene.night_factor(a/10) for a in range(-200, 100)]
        self.assertEqual(values, sorted(values, reverse=True))

    def test_sun_faces_south_with_east_on_the_left(self):
        self.assertAlmostEqual(scene.sun_screen(0, 90)[0], 0)
        self.assertAlmostEqual(scene.sun_screen(0, 180)[0], scene.W/2)
        self.assertAlmostEqual(scene.sun_screen(0, 270)[0], scene.W)
        self.assertAlmostEqual(scene.sun_screen(0, 180)[1], scene.HORIZON_Y)


class PlateMasks(unittest.TestCase):
    def test_sky_mask_follows_the_painted_silhouettes(self):
        sky = mask_image('sky')
        for point in ((830, 600), (812, 556), (150, 630), (1400, 575), (1640, 433), (1500, 500), (950, 712), (60, 650)):
            self.assertEqual(sky.getpixel(point), 0, f'foreground {point} must not be sky')
        for point in ((800, 20), (100, 260), (950, 670), (700, 600), (200, 610)):
            self.assertEqual(sky.getpixel(point), 255, f'{point} must be sky')

    def test_everything_above_the_skyline_is_sky_and_ground_is_its_inverse(self):
        from PIL import ImageChops
        sky, ground = mask_image('sky'), mask_image('ground')
        for x in range(0, scene.W, 7):
            for y in range(0, int(scene._interp_pts(scene.SKYLINE, x))-1, 13):
                self.assertEqual(sky.getpixel((x, y)), 255)
        self.assertIsNone(ImageChops.difference(ImageChops.invert(sky), ground).getbbox())

    def test_glyph_mask_covers_the_three_title_lines_and_nothing_else(self):
        glyphs = mask_image('glyphs')
        x0, y0, x1, y1 = scene.TEXT_RECT
        self.assertEqual(glyphs.crop((0, 0, scene.W, y0-4)).getbbox(), None)
        self.assertEqual(glyphs.crop((0, y1+4, scene.W, scene.H)).getbbox(), None)
        rows = [y for y in range(y0, y1) if glyphs.crop((x0, y, x1, y+1)).getbbox()]
        bands = sum(1 for a, b in zip([None]+rows, rows) if a is None or b-a > 3)
        self.assertEqual(bands, 3)
        self.assertGreater(glyphs.getpixel((60, 260)) + sum(glyphs.getpixel((x, 260)) for x in range(44, 80)), 0)

    @unittest.skipUnless(has_librsvg(), 'FFmpeg with librsvg is needed to rasterize')
    def test_title_keeps_at_least_three_to_one_contrast_at_noon(self):
        from PIL import Image, ImageChops
        with tempfile.TemporaryDirectory() as directory:
            svg, png = Path(directory)/'noon.svg', Path(directory)/'noon.png'
            svg.write_text(scene.scene(0, False, state=scene_state.scene_state(NOON)))
            scene.rasterize(svg, png, scene.W)
            frame = Image.open(png).convert('RGB')

        def luminance(pixels):
            def channel(v):
                v /= 255
                return v/12.92 if v <= .03928 else ((v+.055)/1.055)**2.4
            values = [.2126*channel(r)+.7152*channel(g)+.0722*channel(b) for r, g, b in pixels]
            return sum(values)/len(values)
        glyphs = mask_image('glyphs')
        ring = ImageChops.subtract(mask_image('outline'), glyphs)
        x0, y0, x1, y1 = scene.TEXT_RECT
        inside = [frame.getpixel((x, y)) for x in range(x0, x1) for y in range(y0, y1) if glyphs.getpixel((x, y))]
        around = [frame.getpixel((x, y)) for x in range(x0, x1) for y in range(y0, y1) if ring.getpixel((x, y))]
        contrast = (luminance(inside)+.05)/(luminance(around)+.05)
        self.assertGreaterEqual(contrast, 3, f'title contrast {contrast:.2f}')


class DayPlates(unittest.TestCase):
    def test_noon_draws_the_day_plate_and_embeds_nothing_unused(self):
        svg = scene.scene(0, False, state=scene_state.scene_state(NOON))
        self.assertIn('data-light="plate-day" href="#plate-day"', svg)
        self.assertNotIn('plate-golden', svg)
        self.assertEqual(svg.count('id="plate-day"'), 1)

    def test_night_draws_no_day_art(self):
        self.assertNotIn('plate-', scene.scene(0, False, state=scene_state.scene_state(NIGHT)).replace('id="plate"', ''))

    def test_low_sun_uses_the_golden_plate_and_hands_over_to_day(self):
        self.assertEqual(scene._keyed(scene.GOLDEN_KEYS, 3), 1)
        self.assertEqual(scene._keyed(scene.DAY_KEYS, 3), 0)
        self.assertEqual(scene._keyed(scene.GOLDEN_KEYS, -6), 0)
        self.assertEqual(scene._keyed(scene.DAY_KEYS, 20), 1)
        for keys in (scene.DAY_KEYS, scene.GOLDEN_KEYS):
            values = [scene._keyed(keys, a/10) for a in range(-200, 400)]
            self.assertTrue(all(0 <= v <= 1 for v in values))
            self.assertTrue(all(abs(b-a) < .05 for a, b in zip(values, values[1:])), 'no visible step')

    def test_twilight_lift_is_gone_once_a_day_plate_is_fully_in(self):
        self.assertNotIn('data-light="foreground"', scene.scene(0, False, state=scene_state.scene_state(NOON)))

    def test_plates_cover_exactly_the_ground(self):
        from PIL import Image, ImageChops
        ground = mask_image('ground')
        for name in ('day', 'golden'):
            with Image.open(scene.ASSETS/f'observatory-{name}.png') as plate:
                self.assertEqual((plate.mode, plate.size), ('RGBA', (scene.W, scene.H)))
                self.assertIsNone(ImageChops.difference(plate.getchannel('A'), ground).getbbox(), name)

    @unittest.skipUnless(importlib.util.find_spec('numpy'), 'NumPy is a build-time dependency of the day art')
    def test_committed_plates_match_the_builder(self):
        import build_day_art
        from PIL import Image, ImageChops
        for name in ('day', 'golden'):
            with Image.open(scene.ASSETS/f'observatory-{name}.png') as committed:
                self.assertIsNone(ImageChops.difference(build_day_art.build(name), committed.convert('RGBA')).getbbox(), name)


class LiveRender(unittest.TestCase):
    def test_a_failed_render_leaves_the_previous_files_untouched(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)
            for name in ('live.svg', 'live.png', 'live.json'):
                (out/name).write_text('previous '+name)
            with mock.patch.object(scene, 'rasterize', side_effect=RuntimeError('render failed')):
                with self.assertRaises(RuntimeError):
                    render_live.render(NOON, out)
            for name in ('live.svg', 'live.png', 'live.json'):
                self.assertEqual((out/name).read_text(), 'previous '+name)
            self.assertEqual(sorted(p.name for p in out.iterdir()), ['live.json', 'live.png', 'live.svg'])


if __name__ == '__main__':
    unittest.main()
