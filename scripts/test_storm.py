"""Phase 15b: lightning, the grounded-flights hologram and the wind-swept meadow, driven by real weather only."""
from datetime import datetime
import unittest
from unittest import mock
from zoneinfo import ZoneInfo

import build_animation as scene
import scene_state
import test_daily
import test_scene
from test_portfolio import overlap
from test_weather import observation

IST = ZoneInfo('Asia/Kolkata')
NIGHT = datetime(2026, 10, 2, 21, 0, tzinfo=IST)
DAY = datetime(2026, 10, 2, 15, 0, tzinfo=IST)


def weather(when, **changes):
    return observation(**dict(changes, time=when.isoformat()))


def storm(when=NIGHT, **changes):
    return weather(when, **dict(dict(condition='thunderstorm', weather_code=95, wind_kmh=34.0, gust_kmh=70.0,
                                     precipitation_mm=6.0, rain_mm=6.0, cloud_cover_pct=100.0), **changes))


def clear(when=DAY, **changes):
    return weather(when, **dict(dict(condition='clear', weather_code=0, wind_kmh=8.0, gust_kmh=14.0,
                                     precipitation_mm=0.0, rain_mm=0.0, cloud_cover_pct=5.0), **changes))


def lit(when, obs):
    return scene.lighting(scene_state.scene_state(when, None, obs))


def svg(when, obs, t=0):
    return scene.scene(t, False, state=scene_state.scene_state(when, None, obs))


class Grounding(unittest.TestCase):
    def test_bad_weather_grounds_the_airliner_and_shows_the_hologram(self):
        for when, obs in ((NIGHT, storm()), (DAY, storm(DAY)),
                          (DAY, weather(DAY, condition='heavy-rain', weather_code=65, precipitation_mm=5.0)),
                          (DAY, weather(DAY, condition='fog', weather_code=45, precipitation_mm=0.0)),
                          (DAY, clear(gust_kmh=float(scene.GALE_GUST_KMH)))):
            with self.subTest(condition=obs['condition'], gust=obs['gust_kmh']):
                markup = svg(when, obs)
                self.assertNotIn('data-traffic="airplane"', markup)
                self.assertIn('data-advisory="hologram"', markup)
                self.assertTrue(scene.grounded(lit(when, obs)))

    def test_fair_weather_and_the_seasonal_model_keep_the_airliner(self):
        for when, obs in ((DAY, clear()), (DAY, observation()), (NIGHT, None),
                          (DAY, clear(gust_kmh=scene.GALE_GUST_KMH-.5))):
            with self.subTest(obs=obs and obs['condition']):
                markup = svg(when, obs)
                self.assertIn('data-traffic="airplane"', markup)
                self.assertNotIn('data-advisory', markup)

    def test_the_hologram_reads_from_validated_numbers_and_fits_its_panel(self):
        x0, y0, x1, y1 = scene.ADVISORY_BOX
        for gusts in (14.0, 70.0, 400.0):
            light = lit(NIGHT, storm(wind_kmh=min(300.0, gusts), gust_kmh=gusts))
            lines = scene.advisory_lines(light)
            self.assertEqual(lines[1], 'FLIGHTS SUSPENDED')
            self.assertEqual(lines[2], 'THUNDERSTORM OVER MUMBAI')
            for i, text in enumerate(lines):
                _, width, height = scene.pixel_text(text, x0+16, y0+14+i*24)   # every glyph exists
                self.assertLessEqual(x0+16+width, x1-8, text)
                self.assertLessEqual(y0+14+i*24+height, y1-8, text)

    def test_the_hologram_stays_clear_of_the_name_the_sky_events_and_the_land(self):
        box = scene.ADVISORY_BOX
        self.assertFalse(overlap(box, scene.TEXT_RECT))
        self.assertFalse(overlap(box, scene.LOCK_READOUT_BOX))
        self.assertLess(box[2], scene.BOLT_ZONE[0])
        self.assertLess(box[3], min(y for x, y in scene.SKYLINE if x <= box[2]+20))
        for name, other in dict(scene.object_boxes(), **scene.PROTECTED).items():
            self.assertFalse(overlap(box, other), name)


class Lightning(unittest.TestCase):
    def test_only_thunderstorms_strike(self):
        self.assertIn('data-storm="lightning"', svg(NIGHT, storm()))
        for when, obs in ((NIGHT, None), (DAY, weather(DAY, condition='heavy-rain', weather_code=65)), (DAY, clear())):
            self.assertNotIn('data-storm', svg(when, obs))

    def test_flashes_are_photosensitivity_safe(self):
        light = lit(NIGHT, storm())
        for seed in range(40):
            tracks = [scene.strike_track(when, scene.SKY_FLASH) for when, _ in scene.strikes(seed)]
            self.assertEqual(len(tracks), len(scene.STRIKE_SLOTS))
            samples = [i/200 for i in range(200*scene.PERIOD)]
            level = [max(track.at(t) for track in tracks) for t in samples]
            self.assertLessEqual(max(level), scene.SKY_FLASH+1e-9)
            self.assertEqual(level[0], 0, seed)   # the still PNG and the reduced-motion copy never flash
            rises = [samples[i] for i in range(1, len(level)) if level[i-1] < .05 <= level[i]]
            for start in rises:
                self.assertLessEqual(sum(start <= r < start+1 for r in rises), 3, (seed, rises))
        self.assertIn('opacity="0"', scene.lightning(0, False, light))

    def test_the_storm_deck_hides_the_sky_and_shades_the_land(self):
        calm, wild = lit(DAY, clear()), lit(DAY, storm(DAY))
        self.assertGreaterEqual(wild['overcast'], scene.STORM_DECK['thunderstorm'][0])
        self.assertLess(sum(wild['deck']), sum(calm['deck']))
        self.assertIn('data-season="storm-shade"', wild['weather'])
        self.assertNotIn('data-season="storm-shade"', calm['weather'])


class Meadow(unittest.TestCase):
    def test_grass_sways_harder_in_stronger_wind(self):
        amps = [scene.sway_amplitude(w, w*1.8) for w in (0, 5, 15, 30, 60, 200)]
        self.assertEqual(amps, sorted(amps))
        self.assertLess(amps[0], amps[-1])
        self.assertLessEqual(amps[-1], 22)
        self.assertLess(scene.sway_amplitude(*scene.wind_of(lit(DAY, clear()))),
                        scene.sway_amplitude(*scene.wind_of(lit(NIGHT, storm()))))
        self.assertEqual(scene.wind_of(lit(NIGHT, storm())), (34.0, 70.0))

    def test_tufts_grow_on_open_ground_only(self):
        tufts = scene.meadow_tufts()
        self.assertGreater(len(tufts), 30)
        guards = dict(scene.object_boxes(), **scene.PROTECTED,
                      **{f'puddle{k}': (x, y, x+w, y+h) for k, (x, y, w, h) in enumerate(scene.PUDDLES)})
        for x, y, blades in tufts:
            reach = max(h for _, h in blades)
            box = (x-reach, y-reach, x+reach, y+2)   # any sway angle
            for name, guard in guards.items():
                self.assertFalse(overlap(box, guard), (x, y, name))

    def test_sway_loops_with_the_scene(self):
        markup = scene.meadow(0, True, lit(NIGHT, storm()))
        self.assertEqual(scene.PERIOD % scene.SWAY_PERIOD, 0)
        self.assertEqual(markup.count('<animateTransform'), len(scene.meadow_tufts()))
        self.assertNotIn('begin="0.', markup)   # phases are negative offsets, never delays


class StormAnimations(unittest.TestCase):
    """The generic SMIL-vs-raster and loop checks on a stormy night, sampled inside every lightning strike."""

    def test_storm_night(self):
        obs = storm()
        light = lit(NIGHT, obs)
        original = scene.layers
        times = sorted(set(test_scene.CHECK_TIMES+[round(when+dt, 3) for when, _ in scene.strikes(light['seed'])
                                                   for dt in (.01, .05, .1, .2)]))
        with mock.patch.object(scene, 'layers', lambda t, animated, _=None: original(t, animated, light)), \
                mock.patch.object(scene, 'ROUTES', scene.flying_routes(light['day']['airliner'], light)), \
                mock.patch.object(test_scene, 'CHECK_TIMES', times):
            test_daily.run(test_daily.GENERIC[:2])


if __name__ == '__main__':
    unittest.main()
