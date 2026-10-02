"""Phase 15a: real Mumbai weather, validated, optional, and never trusted from disk or network."""
from datetime import datetime, timedelta
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock
from zoneinfo import ZoneInfo

import build_animation as scene
import render_live
import scene_state
import test_render_daily
import weather

IST = ZoneInfo('Asia/Kolkata')
FIXTURE = json.loads((Path(__file__).parent/'fixtures'/'open-meteo-2026-10-02T1600.json').read_text())
WHEN = datetime(2026, 10, 2, 16, 0, tzinfo=IST)


def observation(**changes):
    obs = weather.parse(FIXTURE)
    obs.update(changes)
    return obs


class Parse(unittest.TestCase):
    def test_real_response(self):
        obs = weather.parse(FIXTURE)
        self.assertEqual((obs['condition'], obs['weather_code'], obs['cloud_cover_pct'], obs['precipitation_mm']),
                         ('drizzle', 53, 69.0, .2))
        self.assertEqual((obs['wind_kmh'], obs['gust_kmh'], obs['is_day']), (11.4, 31.0, 1))
        self.assertEqual(obs['time'], '2026-10-02T16:00:00+05:30')
        self.assertEqual(set(obs), set(weather.FIELDS) | {'time', 'weather_code', 'condition', 'is_day'})

    def test_unexpected_values_are_refused(self):
        def broken(**current):
            payload = json.loads(json.dumps(FIXTURE))
            payload['current'].update(current)
            return payload
        for bad in (dict(weather_code=42), dict(weather_code='53'), dict(wind_speed_10m=9999), dict(cloud_cover=-1),
                    dict(precipitation='0.2'), dict(temperature_2m=True), dict(is_day=2), dict(time='yesterday')):
            with self.assertRaises(weather.Invalid, msg=bad):
                weather.parse(broken(**bad))
        with self.assertRaises(weather.Invalid):
            weather.parse({'current': None})

    def test_stored_files_are_checked_again(self):
        for tampered in (dict(condition='<script>'), dict(condition='thunderstorm'), dict(wind_kmh=1e9), dict(time='2026-10-02T16:00')):
            with self.assertRaises(ValueError, msg=tampered):
                weather.check(observation(**tampered))
        extra = observation(note='<img src=x onerror=alert(1)>')
        self.assertNotIn('note', weather.check(extra))


class Files(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.out = Path(self.directory.name)

    def tearDown(self):
        self.directory.cleanup()

    def test_store_load_and_freshness(self):
        weather.store(observation(), self.out)
        self.assertEqual(weather.load_current(self.out/'current.json', WHEN+timedelta(minutes=30))['condition'], 'drizzle')
        self.assertIsNone(weather.load_current(self.out/'current.json', WHEN+timedelta(hours=3)))
        (self.out/'current.json').write_text('{"condition": "clear"}')
        self.assertIsNone(weather.load_current(self.out/'current.json', WHEN))
        self.assertIsNone(weather.load_current(self.out/'missing.json', WHEN))
        self.assertEqual(sorted(p.name for p in self.out.iterdir()), ['current.json', 'history.json'])

    def test_history_keeps_two_days_and_finds_the_nearest_reading(self):
        for minutes in range(0, 60*60, 15):
            stamp = (WHEN+timedelta(minutes=minutes)).isoformat()
            weather.store(observation(time=stamp, cloud_cover_pct=float(minutes % 100)), self.out)
        history = json.loads((self.out/'history.json').read_text())
        self.assertLessEqual(len(history), 48*4+1)
        newest = WHEN+timedelta(minutes=60*60-15)
        near = weather.nearest(self.out/'history.json', newest-timedelta(minutes=8))   # 7 from the one before
        self.assertEqual(near['time'], (newest-timedelta(minutes=15)).isoformat())
        self.assertIsNone(weather.nearest(self.out/'history.json', WHEN-timedelta(days=5)))

    def test_fetch_limits_the_response(self):
        class Response:
            def __init__(self, body):
                self.body = body
            def read(self, limit):
                return self.body[:limit]
            def __enter__(self):
                return self
            def __exit__(self, *exc):
                return False
        config = scene_state.load_config()
        good = weather.fetch(config, lambda request, timeout: Response(json.dumps(FIXTURE).encode()))
        self.assertEqual(good['condition'], 'drizzle')
        with self.assertRaises(weather.Invalid):
            weather.fetch(config, lambda request, timeout: Response(b' '*(weather.MAX_BYTES+10)))


class Scene(unittest.TestCase):
    def test_no_weather_keeps_the_seasonal_model(self):
        light = scene.lighting(scene_state.scene_state(WHEN))
        self.assertIsNone(light['observation'])
        self.assertEqual(light['rain'], scene.shower(scene_state.scene_state(WHEN), light['env']))

    def test_real_drizzle_brings_rain_cloud_and_wet_ground(self):
        light = scene.lighting(scene_state.scene_state(WHEN, None, observation()))
        self.assertGreater(light['rain'], .25)
        self.assertGreaterEqual(light['env']['cloud_density'], .72)
        self.assertGreater(light['env']['ground_wetness'], .6)
        self.assertIn('data-season="rain"', scene.scene(0, False, state=scene_state.scene_state(WHEN, None, observation())))

    def test_clear_weather_means_no_rain_and_fog_means_haze(self):
        clear = scene.lighting(scene_state.scene_state(WHEN, None, observation(condition='clear', weather_code=0,
                                                                                precipitation_mm=0.0, cloud_cover_pct=5.0)))
        self.assertEqual(clear['rain'], 0)
        self.assertEqual(clear['env']['cloud_density'], .05)
        fog = scene.lighting(scene_state.scene_state(WHEN, None, observation(condition='fog', weather_code=45, precipitation_mm=0.0)))
        self.assertGreaterEqual(fog['env']['haze'], .9)

    @mock.patch.object(scene, 'rasterize', test_render_daily.fake_rasterize)
    def test_render_live_reads_fresh_weather_and_ignores_stale(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            weather.store(observation(), folder/'weather')
            state = render_live.render(WHEN, folder/'live', weather_file=folder/'weather'/'current.json')
            self.assertEqual(state['weather']['condition'], 'drizzle')
            self.assertEqual(json.loads((folder/'live'/'live.json').read_text())['weather']['condition'], 'drizzle')
            stale = render_live.render(WHEN+timedelta(hours=4), folder/'live', weather_file=folder/'weather'/'current.json')
            self.assertIsNone(stale['weather'])


if __name__ == '__main__':
    unittest.main()
