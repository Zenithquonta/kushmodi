"""Phase 7 portfolio objects, and the generic animation checks rerun on real lit scenes (Phases 3-7)."""
from datetime import datetime
import unittest
from unittest import mock
from zoneinfo import ZoneInfo

import build_animation as scene
import scene_state
import test_daily
import test_scene

IST = ZoneInfo('Asia/Kolkata')
NOON = datetime(2026, 12, 14, 12, 30, tzinfo=IST)
NIGHT = datetime(2026, 12, 14, 23, 0, tzinfo=IST)


def overlap(a, b):
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def rainy_monsoon_night():
    for hour in range(19, 24):
        when = datetime(2027, 7, 15, hour, 0, tzinfo=IST)
        if scene.lighting(scene_state.scene_state(when))['rain'] > 0:
            return when
    raise AssertionError('no rainy hour found')


class Placement(unittest.TestCase):
    def test_objects_never_cover_painted_things_or_each_other(self):
        boxes = scene.object_boxes()
        protected = dict(scene.PROTECTED, **{f'puddle{k}': (x, y, x+w, y+h) for k, (x, y, w, h) in enumerate(scene.PUDDLES)})
        for name, box in boxes.items():
            for other, guard in protected.items():
                self.assertFalse(overlap(box, guard), (name, other))
        names = list(boxes)
        for i, a in enumerate(names):
            for b in names[i+1:]:
                self.assertFalse(overlap(boxes[a], boxes[b]), (a, b))

    def test_objects_stay_out_of_the_name_and_the_sky(self):
        for name, box in scene.object_boxes().items():
            self.assertFalse(overlap(box, scene.TEXT_RECT), name)
            self.assertGreater(box[1], scene.HORIZON_Y, name)

    def test_objects_are_live_only_and_carry_no_text(self):
        self.assertNotIn('data-portfolio', scene.scene(0, True))
        svg = scene.scene(0, False, state=scene_state.scene_state(NIGHT))
        for name in ('drone', 'drone-pad', 'ground-station', 'tracker', 'pcb'):
            self.assertIn(f'data-portfolio="{name}"', svg)
        objects = svg[svg.index('data-portfolio="objects"'):]
        self.assertNotIn('<text', objects)

    def test_drone_lights_glow_at_night_only(self):
        noon = scene.drone(0, False, scene.lighting(scene_state.scene_state(NOON)))
        night = scene.drone(0, False, scene.lighting(scene_state.scene_state(NIGHT)))
        self.assertIn('r="4" fill="#ff3b3b" opacity="0"', noon)
        self.assertNotIn('r="4" fill="#ff3b3b" opacity="0"', night)

    def test_outdoor_objects_darken_when_the_ground_is_wet(self):
        dry = scene.lighting(scene_state.scene_state(NOON))
        wet = dict(dry, env=dict(dry['env'], ground_wetness=1))
        self.assertLess(sum(scene._outdoor(wet, (30, 30, 30), (200, 200, 200))),
                        sum(scene._outdoor(dry, (30, 30, 30), (200, 200, 200))))


class LitAnimations(unittest.TestCase):
    """The generic SMIL-vs-raster and loop checks, on lit scenes with weather, city lights and the portfolio."""

    def check(self, when):
        state = scene_state.scene_state(when)
        light = scene.lighting(state)
        original = scene.layers
        with mock.patch.object(scene, 'layers', lambda t, animated, _=None: original(t, animated, light)), \
                mock.patch.object(scene, 'ROUTES', scene.routes_for(light['day']['airliner'])):
            test_daily.run(test_daily.GENERIC)

    def test_clear_winter_night(self):
        self.check(NIGHT)

    def test_rainy_monsoon_night(self):
        self.check(rainy_monsoon_night())

    def test_noon(self):
        self.check(NOON)


if __name__ == '__main__':
    unittest.main()
