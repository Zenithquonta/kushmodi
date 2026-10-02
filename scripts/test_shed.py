"""Phase 15c: flickering shed lights, the sun and moon tracking screen, and the reactive rover robot (live only)."""
from datetime import datetime, timedelta
import unittest
from unittest import mock
from zoneinfo import ZoneInfo

import build_animation as scene
import scene_state
import test_daily
import test_scene
from test_portfolio import overlap
from test_storm import clear, storm, weather

IST = ZoneInfo('Asia/Kolkata')
NIGHT = datetime(2026, 10, 2, 21, 7, tzinfo=IST)
DAY = datetime(2026, 10, 2, 11, 0, tzinfo=IST)


def lit(when, obs=None):
    return scene.lighting(scene_state.scene_state(when, None, obs))


def rises(tracks, step=1/200):
    """Times where the combined darkening (the deepest of all tracks) crosses 0.05 upward."""
    samples = [i*step for i in range(int(scene.PERIOD/step))]
    level = [max(track.at(t) for track in tracks) for t in samples]
    return level, [samples[i] for i in range(1, len(level)) if level[i-1] < .05 <= level[i]]


class Lights(unittest.TestCase):
    def test_nothing_new_without_a_state(self):
        markup = scene.scene(0, True)
        for marker in ('data-light=', 'data-shed', 'data-screen', 'data-robot', 'light-lamp'):
            self.assertNotIn(marker, markup)

    def test_flickers_are_seeded_per_quarter_hour_and_never_overlap(self):
        seen = set()
        for minutes in range(0, 24*60, 15):
            light = lit(NIGHT.replace(hour=0, minute=0)+timedelta(minutes=minutes))
            events = scene.light_events(light)
            seen.add(tuple(events))
            self.assertTrue(2 <= len(events) <= 4)
            spans = sorted((start, start+scene.FLICKER_SHAPES[kind][-1][0]) for start, _, kind in events)
            for (a0, a1), (b0, b1) in zip(spans, spans[1:]):
                self.assertGreater(b0-a1, .9, spans)
            for start, name, kind in events:
                self.assertIn(kind, scene.LIGHT_SHAPES[name])
                self.assertGreater(start, 1)
                self.assertLess(start+scene.FLICKER_SHAPES[kind][-1][0], scene.PERIOD)
        self.assertGreater(len(seen), 40)   # the story moves with each redraw

    def test_flicker_is_photosensitivity_safe_with_lightning_included(self):
        cases = [lit(NIGHT+timedelta(minutes=15*k)) for k in range(24)]
        cases += [lit(NIGHT+timedelta(minutes=15*k), storm(NIGHT+timedelta(minutes=15*k))) for k in range(8)]
        for light in cases:
            tracks = [track for name in scene.LIGHTS for track in [scene.light_track(light, name)] if track]
            if scene._thunderstorm(light):
                tracks += [scene.strike_track(when, scene.SKY_FLASH) for when, _ in scene.strikes(light['seed'])]
            level, starts = rises(tracks)
            self.assertEqual(level[0], 0)   # the still frame is never mid-flicker
            for start in starts:
                self.assertLessEqual(sum(start <= r < start+1 for r in starts), 3, starts)

    def test_a_storm_surge_dims_every_light_together(self):
        light = lit(NIGHT, storm())
        events = scene.light_events(light)
        for when, _ in scene.strikes(light['seed']):
            names = {name for start, name, _ in events if abs(start-(when+scene.STORM_SURGE)) < .01}
            self.assertEqual(names, set(scene.LIGHTS))

    def test_flicker_is_deeper_at_night(self):
        night, day = lit(NIGHT), lit(DAY, clear())
        deepest = lambda light: max(max(track.values) for name in scene.LIGHTS
                                    for track in [scene.light_track(light, name)] if track)
        self.assertGreater(deepest(night), deepest(day))
        self.assertLessEqual(deepest(night), max(spec['depth'] for spec in scene.LIGHTS.values()))

    def test_masks_cover_their_light_and_spare_the_lantern_and_screen(self):
        import base64
        import io
        from PIL import Image
        for name, spec in scene.LIGHTS.items():
            uri = scene._light_mask(name)
            image = Image.open(io.BytesIO(base64.b64decode(uri.split(',', 1)[1]))).convert('L')
            self.assertGreater(image.getextrema()[1], 200, name)
            x0, y0, x1, y1 = spec['box']
            if name == 'lamp':
                kx0, ky0, kx1, ky1 = scene.SHED_KEEP
                lantern = image.crop(((kx0-x0)//2+4, (ky0-y0)//2+4, (min(kx1, x1)-x0)//2-4, (ky1-y0)//2-4))
                self.assertLess(lantern.getextrema()[1], 40)
            else:
                self.assertFalse(overlap(spec['box'], scene.SCREEN), name)


class Screen(unittest.TestCase):
    def test_pages_fit_for_any_value(self):
        x0, y0, x1, y1 = scene.SCREEN
        for alt, az, fraction in ((-90, 359.9, 1.0), (90, 0, 0.0), (-5, 180, .5)):
            astronomy = dict(sun=dict(altitude_deg=alt, azimuth_deg=az),
                             moon=dict(altitude_deg=alt, azimuth_deg=az, illuminated_fraction=fraction, waxing=True),
                             sun_times={},
                             planets={name: dict(altitude_deg=alt, azimuth_deg=az, constellation_symbol='Sgr', rise=None)
                                      for name in scene.PLANET_SHORT})
            satellites = {name: dict(next_pass=dict(start='2026-10-02T23:59:00+05:30', max_altitude_deg=88.6,
                                                    start_direction=direction))
                          for name in scene.SAT_SHORT for direction in ('NW',)}
            for page in ('sun', 'moon', 'planets', 'sats'):
                for text in scene.screen_lines(page, astronomy, satellites):
                    _, width, _ = scene.pixel_text(text, x0+scene.SCREEN_MARGIN, y0, cell=2)
                    self.assertLessEqual(x0+scene.SCREEN_MARGIN+width, x1-1, text)

    def test_lines_come_from_the_computed_sky(self):
        light = lit(NIGHT)
        sun, moon = (scene.screen_lines(page, light['astronomy']) for page in ('sun', 'moon'))
        self.assertEqual(sun[0], 'SUN TRACK')
        self.assertEqual(sun[2], 'RISES 06:29')
        self.assertEqual(moon[2], f"{round(100*light['astronomy']['moon']['illuminated_fraction'])}% WANING")
        self.assertEqual(scene.screen_lines('sun', lit(DAY, clear())['astronomy'])[2], 'SETS 18:26')

    def test_the_paths_are_the_real_altitudes(self):
        astronomy = lit(NIGHT)['astronomy']
        path = astronomy['altitude_by_hour']
        self.assertEqual([len(path['sun']), len(path['moon'])], [25, 25])
        at_nine = scene_state.scene_state(NIGHT.replace(minute=0))['astronomy']
        self.assertAlmostEqual(path['sun'][21], at_nine['sun']['altitude_deg'], delta=.6)
        self.assertAlmostEqual(path['moon'][21], at_nine['moon']['altitude_deg'], delta=.6)
        self.assertEqual(max(range(25), key=path['sun'].__getitem__) in (12, 13), True)   # local noon

    def test_the_content_stays_inside_the_painted_bezel(self):
        bx = [x for x, _ in scene.SCREEN_BEZEL]
        by = [y for _, y in scene.SCREEN_BEZEL]
        x0, y0, x1, y1 = scene.SCREEN
        left_top, right_top = scene.SCREEN_BEZEL[0][1], scene.SCREEN_BEZEL[1][1]
        self.assertTrue(min(bx) <= x0 and x1 <= max(bx) and max(left_top, right_top) <= y0 and y1 <= min(by[2:]))
        astronomy = lit(NIGHT)['astronomy']
        rows = scene.screen_lines('planets', astronomy)
        self.assertLessEqual(y0+3+(len(rows)-1)*scene.SCREEN_ROW_PITCH+10, y1)   # 10 px glyphs, every row inside
        markup = scene.screen(0, False, lit(NIGHT), astronomy)
        self.assertIn('M'+'L'.join(f'{x} {y}' for x, y in scene.SCREEN_BEZEL)+'z', markup)   # the backing covers the bezel

    def test_the_screen_sits_on_the_painted_screen_only(self):
        self.assertFalse(overlap(scene.SCREEN, (scene.PATCH_TARGET[0], scene.PATCH_TARGET[1],
                                                scene.PATCH_TARGET[0]+scene.PATCH_TARGET[2],
                                                scene.PATCH_TARGET[1]+scene.PATCH_TARGET[3])))
        for name, box in dict(scene.object_boxes(), **scene.PROTECTED).items():
            self.assertFalse(overlap(scene.SCREEN, box), name)
        markup = scene.screen(0, False, lit(NIGHT), lit(NIGHT)['astronomy'])
        self.assertIn('data-screen="sun" opacity="1"', markup)
        self.assertIn('data-screen="moon" opacity="0"', markup)
        self.assertIn('data-screen="planets" opacity="0"', markup)
        self.assertIn('data-screen="sats" opacity="0"', markup)


class Robot(unittest.TestCase):
    def test_moods_follow_the_weather(self):
        self.assertEqual(scene.mood(lit(NIGHT)), 'calm')
        self.assertEqual(scene.mood(lit(NIGHT, weather(NIGHT, is_day=0))), 'rain')
        self.assertEqual(scene.mood(lit(NIGHT, storm())), 'alert')
        self.assertEqual(scene.mood(lit(DAY, clear(gust_kmh=80.0))), 'alert')
        self.assertIn('data-robot="rain"', scene.robot(0, False, lit(NIGHT, weather(NIGHT, is_day=0))))

    def test_reactions_answer_real_events(self):
        light = lit(NIGHT, storm())
        reactions = scene.robot_reactions(light)
        kinds = {kind for _, kind, _ in reactions}
        self.assertIn('lock', kinds)
        self.assertIn('strike', kinds)
        for (a, _, _), (b, _, _) in zip(reactions, reactions[1:]):
            self.assertGreater(b-a, 2.2)
        self.assertLess(reactions[-1][0]+.45+1.4, scene.PERIOD)
        self.assertIn(round(scene.lock_moment(), 2), scene.robot_pings(light))
        calm = scene.robot_reactions(lit(NIGHT))
        flicker_times = [start for start, _, _ in scene.light_events(lit(NIGHT))]
        for when, kind, _ in calm:
            if kind == 'flicker':
                self.assertTrue(any(abs(when-(start+.15)) < .01 for start in flicker_times))

    def test_the_robot_stays_on_the_rover(self):
        x, y, w, h = scene.ROBOT_HEAD
        self.assertTrue(overlap((x, y, x+w, y+h), scene.PROTECTED['rover']))
        rx0, ry0, rx1, ry1 = scene.PROTECTED['rover']
        self.assertTrue(rx0 <= x and x+w <= rx1 and ry0 <= y and y+h <= ry1)
        for px, py in (scene.ROBOT_LENS, scene.ROBOT_SMALL_LENS, scene.ROBOT_PANEL):
            self.assertTrue(x <= px <= x+w or rx0 <= px <= rx1, (px, py))

    def test_headlight_and_eye_glow_follow_the_dark(self):
        night, day = scene.robot(0, False, lit(NIGHT)), scene.robot(0, False, lit(DAY, clear()))
        self.assertIn('data-robot="headlight" cx="1205" cy="857" rx="12" ry="5" fill="#5ef2ff" opacity="0.45"', night)
        self.assertIn('opacity="0"/></g>', day)
        self.assertGreater(scene.robot_glow(lit(NIGHT)).values[0], scene.robot_glow(lit(DAY, clear())).values[0])


class ShedAnimations(unittest.TestCase):
    """The generic SMIL-vs-raster and loop checks, sampled inside every flicker, glance, ping and page change."""

    def check(self, when, obs=None):
        light = lit(when, obs)
        original = scene.layers
        moments = [start+dt for start, _, _ in scene.light_events(light) for dt in (.03, .1, .25, .5)]
        moments += [when_+dt for when_, _, _ in scene.robot_reactions(light) for dt in (0, .08, .2, 1.2, 1.7)]
        moments += [p+dt for p in scene.robot_pings(light) for dt in (.03, .5, 1.3)]
        moments += [s+dt for _, s, e in scene.SCREEN_PAGES for s in (s, e) for dt in (-.1, .1, .3)]
        times = sorted({round(m % scene.PERIOD, 3) for m in moments} | set(test_scene.CHECK_TIMES))
        with mock.patch.object(scene, 'layers', lambda t, animated, _=None: original(t, animated, light)), \
                mock.patch.object(scene, 'ROUTES', scene.flying_routes(light['day']['airliner'], light)), \
                mock.patch.object(test_scene, 'CHECK_TIMES', times), \
                mock.patch.object(test_scene, 'LINEAR', 1e-3), mock.patch.object(test_scene, 'PX', .05):
            # The starships' warp-flash scale keyframes print three decimals, so between keyframes the raster and the
            # SMIL scale differ by up to 3e-4 (0.04 px). The default check times never land there; these do.
            test_daily.run(test_daily.GENERIC[:2])

    def test_calm_night(self):
        self.check(NIGHT)

    def test_storm_night(self):
        self.check(NIGHT, storm())

    def test_clear_day(self):
        self.check(DAY, clear())


if __name__ == '__main__':
    unittest.main()
