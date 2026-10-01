"""Phase 8: the real Moon (position, phase, lit side) and planets, placed on the south-facing dome."""
from datetime import datetime
import math
import unittest
from zoneinfo import ZoneInfo

import astronomy as ae

import build_animation as scene
import scene_state
import test_portfolio

IST = ZoneInfo('Asia/Kolkata')
CRESCENT_DUSK = datetime(2026, 12, 13, 19, 0, tzinfo=IST)
FULL_NIGHT = datetime(2026, 10, 27, 0, 0, tzinfo=IST)


def lit_share(phase_angle, direction=(1, 0)):
    cells = scene.moon_cells(phase_angle, direction)
    return sum(1 for c in cells if c[2])/len(cells)


class MoonPhase(unittest.TestCase):
    def test_full_and_new_moon(self):
        full = ae.SearchMoonPhase(180, ae.Time.Make(2026, 10, 1, 0, 0, 0), 40)
        new = ae.SearchMoonPhase(0, ae.Time.Make(2026, 10, 1, 0, 0, 0), 40)
        self.assertGreater(lit_share(ae.Illumination(ae.Body.Moon, full).phase_angle), .97)
        self.assertLess(lit_share(ae.Illumination(ae.Body.Moon, new).phase_angle), .03)

    def test_lit_area_tracks_the_illuminated_fraction(self):
        for angle in range(0, 181, 15):
            fraction = (1+math.cos(math.radians(angle)))/2
            for direction in ((1, 0), (0, 1), (-.6, .8)):
                self.assertAlmostEqual(lit_share(angle, direction), fraction, delta=.06)

    def test_waxing_crescent_after_sunset_is_lit_on_its_lower_right(self):
        state = scene_state.scene_state(CRESCENT_DUSK)
        moon, sun = state['astronomy']['moon'], state['astronomy']['sun']
        self.assertTrue(moon['waxing'])
        dx, dy = scene.sun_direction(moon['altitude_deg'], moon['azimuth_deg'], sun['altitude_deg'], sun['azimuth_deg'])
        self.assertGreater(dx, 0)   # the set sun is to the west, on the right
        self.assertGreater(dy, 0)   # and below the horizon
        lit = [(x, y) for x, y, is_lit, _ in scene.moon_cells(moon['phase_angle_deg'], (dx, dy)) if is_lit]
        self.assertGreater(sum(x for x, _ in lit)/len(lit), 0)
        self.assertGreater(sum(y for _, y in lit)/len(lit), 0)


class Placement(unittest.TestCase):
    def test_dome_projection(self):
        self.assertAlmostEqual(scene.sun_screen(0, 90)[0], 0)
        self.assertAlmostEqual(scene.sun_screen(0, 270)[0], scene.W)
        x, y = scene.sun_screen(90, 37)
        self.assertAlmostEqual(x, scene.W/2)
        self.assertAlmostEqual(y, 40)
        self.assertTrue(scene.in_view(75, 20))
        self.assertFalse(scene.in_view(20, 20))

    def test_a_high_full_moon_in_the_east_is_drawn(self):
        svg = scene.scene(0, False, state=scene_state.scene_state(FULL_NIGHT))
        self.assertIn('data-moon="disc"', svg)
        self.assertIn('data-moon="light"', svg)

    def test_moon_and_planets_sit_behind_clouds_and_the_name(self):
        svg = scene.scene(0, False, state=scene_state.scene_state(CRESCENT_DUSK))
        self.assertLess(svg.index('data-sky="bodies" mask="url(#sky-mask)"'), svg.index('data-light="title"'))
        weather = svg.find('data-season="sky"')
        if weather > 0:
            self.assertLess(svg.index('data-sky="bodies"'), weather)

    def test_moon_is_drawn_at_deep_night_without_a_sky_overlay(self):
        state = scene_state.scene_state(FULL_NIGHT)
        self.assertLess(state['astronomy']['sun']['altitude_deg'], -18)
        self.assertIn('data-moon="disc"', scene.scene(0, False, state=state))

    def test_planets_appear_by_brightness(self):
        self.assertGreater(scene.planet_visibility(-4.5, -4), .9)   # Venus in civil twilight
        self.assertEqual(scene.planet_visibility(.7, -4), 0)        # Saturn needs a darker sky
        self.assertGreater(scene.planet_visibility(.7, -18), .9)

    def test_daytime_moon_is_pale(self):
        state = scene_state.scene_state(datetime(2026, 10, 18, 16, 0, tzinfo=IST))
        svg = scene.moon_markup(scene.lighting(state), state)
        self.assertIn(f'data-moon="disc" opacity="{scene.DAY_MOON}"', svg)


class LitMoonAnimations(unittest.TestCase):
    def test_full_moon_night(self):
        test_portfolio.LitAnimations.check(self, FULL_NIGHT)


if __name__ == '__main__':
    unittest.main()
