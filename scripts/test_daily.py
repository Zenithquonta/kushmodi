"""Phase 6 daily variation: every variant the seed can pick passes the same guarantees as the published scene."""
from datetime import datetime, timedelta
import functools
import unittest
from unittest import mock
from zoneinfo import ZoneInfo

import build_animation as scene
import scene_state
import test_scene

IST = ZoneInfo('Asia/Kolkata')
SEEDS = range(40)
GENERIC = ('test_every_animation_reproduces_the_raster_frame', 'test_every_animation_loops_without_a_jump',
           'test_navigation_lights_ride_the_airplane_and_their_periods_divide_the_loop')
TRAFFIC = ('test_traffic_stays_out_of_text_and_in_open_sky',
           'test_airplane_clears_telescope_finder_and_right_edge_foreground',
           'test_traffic_sprites_never_overlap_each_other', 'test_no_hard_clip_and_traffic_fades_smoothly',
           'test_animated_traffic_smil_reproduces_traffic_state')


def run(names):
    """Run SceneTests methods in the current (patched) world, with its caches cleared before and after."""
    test_scene.static_cached.cache_clear()
    try:
        for name in names:
            getattr(test_scene.SceneTests(name), name)()
    finally:
        test_scene.static_cached.cache_clear()


def day_for(when):
    return scene.daily_variation(scene_state.scene_state(when))


class Variants(unittest.TestCase):
    def test_every_airliner_variant_passes_the_traffic_tests(self):
        for variant in range(len(scene.AIRLINER_VARIANTS)):
            with self.subTest(variant=variant), mock.patch.object(scene, 'ROUTES', scene.routes_for(variant)):
                run(TRAFFIC)

    def test_every_satellite_path_crosses_once_clear_of_the_name(self):
        original = scene.satellite_tracks
        for path in scene.SATELLITE_PATHS:
            with self.subTest(path=path), mock.patch.object(scene, 'satellite_tracks', functools.partial(original, path)):
                run(('test_satellite_crosses_once_and_returns_while_invisible',))

    def test_meteors_stay_in_open_sky_for_any_seed_and_on_shower_nights(self):
        original = scene.meteor_plan
        for count in (scene.METEOR_COUNT, scene.METEOR_SHOWER_COUNT):
            for seed in SEEDS:
                with self.subTest(seed=seed, count=count), \
                        mock.patch.object(scene, 'meteor_plan', functools.partial(original, seed, count)), \
                        mock.patch.object(scene, 'METEOR_COUNT', count):
                    run(('test_shooting_stars_stay_in_open_sky_and_reset_while_invisible',))

    def test_seeded_days_pass_the_generic_animation_checks(self):
        for when in (datetime(2026, 12, 14, 23, 0, tzinfo=IST), datetime(2027, 3, 2, 23, 0, tzinfo=IST)):
            with self.subTest(when=when), mock.patch.object(scene, 'DEFAULT_DAY', day_for(when)), \
                    mock.patch.object(scene, 'ROUTES', scene.routes_for(day_for(when)['airliner'])):
                run(GENERIC)


class Days(unittest.TestCase):
    def test_default_day_is_the_published_scene(self):
        self.assertEqual(scene.DEFAULT_DAY, dict(twinkles=41, meteors=7, crosses=29, satellite=0, airliner=0,
                                                 meteor_count=scene.METEOR_COUNT))

    def test_consecutive_days_differ_and_the_hour_does_not_matter(self):
        a = day_for(datetime(2027, 2, 10, 21, 0, tzinfo=IST))
        b = day_for(datetime(2027, 2, 11, 21, 0, tzinfo=IST))
        self.assertNotEqual(a, b)
        self.assertEqual(a, day_for(datetime(2027, 2, 10, 3, 0, tzinfo=IST)))
        night = lambda when: scene.scene(0, False, state=scene_state.scene_state(when))
        self.assertNotEqual(night(datetime(2027, 2, 10, 23, 0, tzinfo=IST)), night(datetime(2027, 2, 11, 23, 0, tzinfo=IST)))

    def test_layers_get_independent_seeds(self):
        seeds = [scene.layer_seed('kushmodi-2027-02-10', name) for name in ('twinkles', 'meteors', 'crosses', 'clouds')]
        self.assertEqual(len(set(seeds)), 4)

    def test_every_variant_is_used_over_a_year(self):
        start = datetime(2026, 10, 1, 21, 0, tzinfo=IST)
        days = [scene.daily_variation(dict(seed=scene_state.seed_for((start+timedelta(days=d)).date())[0]))
                for d in range(365)]
        self.assertEqual({d['airliner'] for d in days}, set(range(len(scene.AIRLINER_VARIANTS))))
        self.assertEqual({d['satellite'] for d in days}, set(range(len(scene.SATELLITE_PATHS))))

    def test_meteor_shower_nights_bring_more_meteors(self):
        geminids = scene_state.scene_state(datetime(2026, 12, 14, 23, 0, tzinfo=IST))
        self.assertEqual(geminids['sky_events']['meteor_shower'], 'Geminids')
        self.assertEqual(scene.daily_variation(geminids)['meteor_count'], scene.METEOR_SHOWER_COUNT)
        quiet = scene_state.scene_state(datetime(2026, 12, 20, 23, 0, tzinfo=IST))
        self.assertIsNone(quiet['sky_events']['meteor_shower'])
        self.assertEqual(scene.daily_variation(quiet)['meteor_count'], scene.METEOR_COUNT)
        self.assertEqual(scene_state.meteor_shower_for(datetime(2027, 1, 2).date()), 'Quadrantids')
        self.assertEqual(scene_state.meteor_shower_for(datetime(2027, 8, 11).date()), 'Perseids')

    def test_meteor_gradients_follow_the_seeded_meteors(self):
        state = scene_state.scene_state(datetime(2026, 12, 14, 23, 0, tzinfo=IST))
        day = scene.daily_variation(state)
        svg = scene.scene(0, False, state=state)
        self.assertIn(scene.meteor_defs(day['meteors'], day['meteor_count']), svg)
        self.assertNotIn(scene.meteor_defs(), svg)
        self.assertNotIn(scene.twinkle_defs(day['twinkles']), svg)   # the live sky has real stars, not painted twinkles


if __name__ == '__main__':
    unittest.main()
