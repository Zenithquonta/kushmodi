"""Day/night lighting: unchanged default output, sky/title masks, fades, sun, day plates, atomic live render."""
import base64
from datetime import datetime, timedelta
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
        svg = scene.scene(0, False, state=scene_state.scene_state(NIGHT))   # the faint layers that remain follow the night
        self.assertTrue(re.findall(r'data-night="[^"]+" opacity="([^"]+)"', svg))
        state = scene_state.scene_state(NIGHT)
        visibility = scene.VISIBILITY_FLOOR+(1-scene.VISIBILITY_FLOOR)*state['environment']['night_visibility']
        self.assertTrue(all(float(v) == round(visibility, 4) for v in re.findall(r'data-night="[^"]+" opacity="([^"]+)"', svg)))
        self.assertNotIn('data-sun', svg)

    def test_noon_hides_celestial_layers_and_shows_the_sun(self):
        svg = scene.scene(0, False, state=scene_state.scene_state(NOON))
        self.assertTrue(all(float(v) == 0 for v in re.findall(r'data-night="[^"]+" opacity="([^"]+)"', svg)))
        self.assertNotIn('data-nightsky', svg)                       # the real stars are not even drawn by day
        # the sun is in front of the north-facing viewer on a May evening (it sets north of west)
        summer = scene.scene(0, False, state=scene_state.scene_state(datetime(2027, 5, 10, 17, 30, tzinfo=IST)))
        self.assertIn('data-sun="disc"', summer)
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

    def test_sun_faces_north_with_west_on_the_left(self):
        self.assertAlmostEqual(scene.sun_screen(0, 270)[0], 0)
        self.assertAlmostEqual(scene.sun_screen(0, 0)[0], scene.W/2)
        self.assertAlmostEqual(scene.sun_screen(0, 90)[0], scene.W)
        self.assertAlmostEqual(scene.sun_screen(0, 0)[1], scene.HORIZON_Y)


class PlateMasks(unittest.TestCase):
    def test_sky_mask_follows_the_painted_silhouettes(self):
        sky = mask_image('sky')
        for point in ((757, 672), (752, 675), (830, 600), (812, 556), (150, 630), (1400, 575), (1640, 433), (1500, 500), (950, 712), (60, 650)):
            self.assertEqual(sky.getpixel(point), 0, f'foreground {point} must not be sky')
        for point in ((800, 20), (100, 260), (950, 670), (700, 600), (200, 610)):
            self.assertEqual(sky.getpixel(point), 255, f'{point} must be sky')

    def test_everything_above_the_skyline_is_sky_and_ground_is_its_inverse(self):
        from PIL import ImageChops
        sky, ground = mask_image('sky'), mask_image('ground')
        for x in range(0, scene.W, 7):
            for y in range(0, int(scene._interp_pts(scene.SKYLINE, x))-1, 13):
                bx0, by0, bx1, by1 = scene.COUNTERWEIGHT_BOX
                if not (bx0 <= x < bx1 and by0 <= y < by1):
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

    def test_dry_plate_stays_inside_the_ground(self):
        from PIL import Image, ImageChops
        with Image.open(scene.ASSETS/'observatory-dry.png') as dry:
            outside = ImageChops.multiply(dry.getchannel('A'), ImageChops.invert(mask_image('ground')))
            self.assertIsNone(outside.getbbox())
            self.assertIsNotNone(dry.getchannel('A').getbbox())

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
        for name in ('day', 'golden', 'dry'):
            with Image.open(scene.ASSETS/f'observatory-{name}.png') as committed:
                self.assertIsNone(ImageChops.difference(build_day_art.build(name), committed.convert('RGBA')).getbbox(), name)


MONSOON_NOON = datetime(2027, 7, 15, 12, 0, tzinfo=IST)
SUMMER_NOON = datetime(2027, 5, 10, 12, 0, tzinfo=IST)


def light_at(when):
    return scene.lighting(scene_state.scene_state(when))


class Seasons(unittest.TestCase):
    def test_dry_vegetation_shows_in_the_hot_season_only_by_day(self):
        self.assertGreater(light_at(SUMMER_NOON)['dry'], .8)
        self.assertEqual(light_at(MONSOON_NOON)['dry'], 0)
        self.assertEqual(light_at(datetime(2027, 5, 10, 23, 0, tzinfo=IST))['dry'], 0)
        self.assertIn('data-season="dry"', scene.scene(0, False, state=scene_state.scene_state(SUMMER_NOON)))
        self.assertNotIn('plate-dry', scene.scene(0, False, state=scene_state.scene_state(MONSOON_NOON)))

    def test_monsoon_brings_overcast_and_a_dry_winter_does_not(self):
        self.assertGreater(light_at(MONSOON_NOON)['overcast'], .4)
        self.assertEqual(light_at(NOON)['overcast'], 0)

    def test_showers_need_monsoon_cloud_and_are_fixed_for_the_hour(self):
        self.assertEqual(light_at(NOON)['rain'], 0)
        self.assertEqual(light_at(SUMMER_NOON)['rain'], 0)
        hours = [light_at(datetime(2027, 7, 15, h, 0, tzinfo=IST))['rain'] for h in range(24)]
        self.assertGreater(sum(1 for r in hours if r > 0), 12, 'mid-monsoon rains most hours')
        self.assertTrue(all(0 <= r <= 1 for r in hours))
        self.assertEqual(light_at(datetime(2027, 7, 15, 9, 5, tzinfo=IST))['rain'],
                         light_at(datetime(2027, 7, 15, 9, 55, tzinfo=IST))['rain'])

    def test_rain_streaks_loop_and_stay_out_of_the_workshop(self):
        rainy = next(datetime(2027, 7, 15, h, 0, tzinfo=IST) for h in range(24)
                     if light_at(datetime(2027, 7, 15, h, 0, tzinfo=IST))['rain'] > 0)
        svg = scene.scene(0, True, state=scene_state.scene_state(rainy))
        self.assertIn('data-season="rain" mask="url(#rain-mask)"', svg)
        tile, slant = scene.RAIN['tile'], scene.RAIN['slant']
        for dur, _ in scene.rain_paths(1):
            fall = scene.Track([(0, 0), (-slant*tile, tile)], dur=dur)
            self.assertEqual(scene.PERIOD % dur, 0)
            self.assertEqual(fall.at(0), (0, 0))

    def test_clouds_never_cover_the_name_and_grow_with_density(self):
        a, b, c, d = scene.TEXT_RECT
        for seed in range(60):
            for box, _ in scene.cloud_shapes(seed, .9):
                x, y, w, h = box
                self.assertFalse(x < c and x+w > a and y < d and y+h > b, seed)
        self.assertLess(len(scene.cloud_shapes(7, .1)), len(scene.cloud_shapes(7, .9)))

    def test_the_name_is_drawn_above_the_weather(self):
        svg = scene.scene(0, False, state=scene_state.scene_state(MONSOON_NOON))
        self.assertLess(svg.index('data-season="sky"'), svg.index('data-light="title"'))

    def test_monsoon_nights_hide_more_of_the_sky_than_winter_nights(self):
        self.assertLess(light_at(datetime(2027, 7, 15, 23, 0, tzinfo=IST))['night'],
                        light_at(datetime(2027, 1, 10, 23, 0, tzinfo=IST))['night'])

    def test_season_effects_change_smoothly_from_day_to_day(self):
        previous = None
        for day in range(0, 365, 3):
            when = datetime(2026, 10, 1, 12, 0, tzinfo=IST)+timedelta(days=day)
            light = light_at(when)
            values = (light['overcast'], light['haze'], light['dry'])
            if previous:
                self.assertTrue(all(abs(x-y) < .15 for x, y in zip(values, previous)), when)   # < .05 a day
            previous = values


WINTER_NIGHT = datetime(2027, 1, 10, 23, 0, tzinfo=IST)


class Mumbai(unittest.TestCase):
    def test_city_mask_keeps_near_trees_and_the_rock_in_front(self):
        # No tower stands behind the telescope (x 640-884), so its bright metal legs need no mask.
        from PIL import Image
        mask = Image.open(io.BytesIO(base64.b64decode(scene.city_mask().split(',', 1)[1]))).convert('L')
        for point in ((740, 720), (400, 740), (420, 750), (1150, 700)):
            self.assertEqual(mask.getpixel(point), 0, f'{point} is a near silhouette')
        for point in ((500, 690), (980, 700), (1000, 740)):
            self.assertEqual(mask.getpixel(point), 255, f'{point} is open far band')

    def test_skyline_is_fixed_and_stands_on_its_shores(self):
        towers = scene.city_towers()
        self.assertGreater(len(towers), 20)
        for x, top, w, base, cap in towers:
            self.assertTrue(any(x0 <= x < x1 and base == b for x0, x1, b in scene.CITY_SHORES))
            self.assertGreater(top, scene.HORIZON_Y-70)
        self.assertEqual(scene.city_towers.__wrapped__(), towers)

    def test_windows_beacons_and_glow_belong_to_the_night(self):
        night = scene.scene(0, False, state=scene_state.scene_state(WINTER_NIGHT))
        noon = scene.scene(0, False, state=scene_state.scene_state(NOON))
        for marker in ('data-city="windows"', 'data-city="beacons"', 'data-city="glow"'):
            self.assertIn(marker, night)
            self.assertNotIn(marker, noon)
        self.assertIn('data-city="skyline"', noon)
        self.assertIn('data-city="sea-link"', noon)

    def test_beacons_blink_within_the_loop(self):
        svg = scene.scene(0, True, state=scene_state.scene_state(WINTER_NIGHT))
        self.assertIn('dur="2s"', svg[svg.index('data-city="beacons"'):])
        self.assertEqual(scene.PERIOD % 2, 0)

    def test_city_glow_warms_the_undersides_of_night_clouds(self):
        state = scene_state.scene_state(WINTER_NIGHT)
        glowing = scene.season_markup(scene.lighting(state))
        state['environment'] = dict(state['environment'], urban_glow=0)
        dark = scene.season_markup(scene.lighting(state))
        self.assertNotEqual(glowing, dark)

    def test_skyline_sits_over_the_haze_and_under_the_name(self):
        svg = scene.scene(0, False, state=scene_state.scene_state(SUMMER_NOON))
        self.assertLess(svg.index('data-season="haze"'), svg.index('data-city="skyline"'))
        self.assertLess(svg.index('data-city="skyline"'), svg.index('data-light="title"'))


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
