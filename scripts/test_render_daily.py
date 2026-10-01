"""Phase 9 daily archive: frame times, Mumbai's date on a UTC machine, atomic and idempotent writes."""
from datetime import date, datetime, timedelta, timezone
import json
from pathlib import Path
import random
import tempfile
import unittest
from unittest import mock

import build_animation as scene
import render_daily
import scene_state
import test_lighting

CFG = scene_state.load_config()


def fake_rasterize(svg, png, width):
    """A small, valid, non-blank PNG of the right size instead of a librsvg render."""
    from PIL import Image
    rng = random.Random(str(png))
    height = round(width*scene.H/scene.W)
    image = Image.effect_noise((width, height), 60).convert('RGB')
    image.putpixel((0, 0), (rng.randrange(256), 0, 0))
    image.save(png)


def blank_rasterize(svg, png, width):
    from PIL import Image
    Image.new('RGB', (width, round(width*scene.H/scene.W)), (10, 10, 10)).save(png)


class Times(unittest.TestCase):
    def test_today_is_mumbais_date_on_a_utc_clock(self):
        self.assertEqual(render_daily.today_local(CFG, datetime(2026, 10, 1, 20, 0, tzinfo=timezone.utc)), date(2026, 10, 2))
        self.assertEqual(render_daily.today_local(CFG, datetime(2026, 10, 1, 18, 0, tzinfo=timezone.utc)), date(2026, 10, 1))

    def test_recent_catches_up_inside_the_year_window_only(self):
        self.assertEqual(render_daily.recent_dates(date(2026, 10, 2), 3, CFG), [date(2026, 10, 1), date(2026, 10, 2)])
        self.assertEqual(render_daily.recent_dates(date(2027, 10, 1), 3, CFG), [date(2027, 9, 29), date(2027, 9, 30)])
        self.assertEqual(render_daily.recent_dates(date(2027, 10, 4), 3, CFG), [])   # year complete: nothing, no error

    def test_night_frames_are_dark_and_day_frames_are_at_the_highest_sun(self):
        d = date.fromisoformat(CFG['year_window']['start'])
        while d < date.fromisoformat(CFG['year_window']['end']):
            day, night = render_daily.frame_times(d, CFG)
            self.assertEqual((day.date(), night.date()), (d, d))
            self.assertLess(scene_state.scene_state(night, CFG)['astronomy']['sun']['altitude_deg'], -18, d)
            noon = scene_state.scene_state(day, CFG)['astronomy']['sun']['altitude_deg']
            for minutes in (-20, 20):
                other = scene_state.scene_state(day+timedelta(minutes=minutes), CFG)['astronomy']['sun']['altitude_deg']
                self.assertGreaterEqual(noon, other, d)
            d += timedelta(days=11)


class Archive(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.out = Path(self.directory.name)
        self.log = []

    def tearDown(self):
        self.directory.cleanup()

    def run_dates(self, dates, **kw):
        return render_daily.run(dates, self.out, CFG, log=self.log.append, **kw)

    @mock.patch.object(scene, 'rasterize', fake_rasterize)
    def test_renders_validates_indexes_and_skips_what_exists(self):
        dates = [date(2026, 12, 13), date(2026, 12, 14)]
        self.assertEqual(self.run_dates(dates), dates)
        for d in dates:
            for kind in render_daily.KINDS:
                self.assertTrue(render_daily.frame_path(self.out, d, kind).exists())
        index = json.loads((self.out/'index.json').read_text())
        entry = index['frames']['2026-12-14']
        self.assertEqual(entry['meteor_shower'], 'Geminids')
        self.assertEqual(entry['files']['night']['path'], '2026/2026-12-14-night.webp')
        self.assertEqual(self.run_dates(dates), [])                      # idempotent
        self.assertEqual(self.run_dates(dates[:1], force=True), dates[:1])
        self.assertEqual(sorted(p.name for p in self.out.iterdir()), ['.lock', '2026', 'index.json'])

    @mock.patch.object(scene, 'rasterize', fake_rasterize)
    def test_a_missing_frame_is_rendered_again(self):
        d = date(2026, 12, 14)
        self.run_dates([d])
        render_daily.frame_path(self.out, d, 'day').unlink()
        self.assertEqual(self.run_dates([d]), [d])

    @mock.patch.object(scene, 'rasterize', blank_rasterize)
    def test_a_blank_render_installs_nothing(self):
        with self.assertRaises(ValueError):
            self.run_dates([date(2026, 12, 14)])
        self.assertFalse((self.out/'2026'/'2026-12-14-day.webp').exists())
        self.assertFalse((self.out/'index.json').exists())
        self.assertEqual([p.name for p in self.out.iterdir() if p.name.startswith('.frames-')], [])

    def test_dates_outside_the_year_window_are_refused(self):
        with self.assertRaises(ValueError):
            self.run_dates([date(2027, 10, 1)])

    @unittest.skipUnless(test_lighting.has_librsvg(), 'FFmpeg with librsvg is needed to rasterize')
    def test_one_real_date(self):
        self.run_dates([date(2027, 7, 15)])
        for kind in render_daily.KINDS:
            render_daily.validate_frame(render_daily.frame_path(self.out, date(2027, 7, 15), kind), CFG['archive']['width'])


if __name__ == '__main__':
    unittest.main()
