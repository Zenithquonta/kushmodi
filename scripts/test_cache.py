"""Phase 14: the optional disk cache changes nothing in the output and never trusts what it reads back."""
from datetime import datetime
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock
from zoneinfo import ZoneInfo

import build_animation as scene
import scene_state

STATE = scene_state.scene_state(datetime(2027, 5, 15, 12, 0, tzinfo=ZoneInfo('Asia/Kolkata')))
CACHED = (scene.bright_stars, scene.plate_masks, scene.city_mask, scene.compact_uri, scene.twinkle_plan)


def clear_memory():
    for function in CACHED:
        function.cache_clear()


def render():
    clear_memory()
    return scene.scene(0, True, state=STATE, compact=True)


class DiskCache(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        self.env = mock.patch.dict(os.environ, {'OBSERVATORY_CACHE': str(self.root)})

    def tearDown(self):
        clear_memory()
        self.directory.cleanup()

    def test_off_by_default_and_writes_nothing(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertIsNone(scene._cache_root())
            render()
        self.assertEqual(list(self.root.iterdir()), [])

    def test_cold_and_warm_renders_are_identical_to_the_uncached_one(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            plain = render()
        with self.env:
            cold = render()
            files = sorted(p.name for p in self.root.iterdir())
            warm = render()
        self.assertEqual(cold, plain)
        self.assertEqual(warm, plain)
        self.assertTrue(any(name.startswith('compact-') for name in files))
        self.assertTrue(any(name.startswith('plate-masks-') for name in files))

    def cheap(self):
        clear_memory()
        return scene.plate_masks(), scene.city_mask(), scene.bright_stars(), scene.compact_uri('observatory-dry.png')

    def test_corrupt_or_hostile_entries_are_recomputed(self):
        with self.env:
            good = self.cheap()
            for path in self.root.glob('*.json'):
                if path.name.startswith('compact-'):
                    path.write_text(json.dumps('data:image/png;base64,AAAA" onload="alert(1)'))
                elif path.name.startswith('bright-stars-'):
                    path.write_text('[[1, 2, "yes", [1, 2], [3, 4, 5]]]')
                else:
                    path.write_text('{not json')
            again = self.cheap()
            self.assertEqual(again, good)
            for path in self.root.glob('compact-*.json'):
                self.assertTrue(scene.DATA_URI.match(json.loads(path.read_text())))

    def test_a_code_change_uses_new_entries(self):
        with self.env:
            clear_memory()
            scene.plate_masks()
            before = {p.name for p in self.root.iterdir()}
            with mock.patch.object(scene, '_code_hash', return_value='0'*64):
                clear_memory()
                scene.plate_masks()
            after = {p.name for p in self.root.iterdir()}
        self.assertEqual(len(after), len(before)+1)

    def test_star_colours_come_back_as_tuples(self):
        with self.env:
            clear_memory()
            scene.bright_stars()
            clear_memory()
            stars = scene.bright_stars()
        self.assertTrue(all(isinstance(s[3], tuple) and isinstance(s[4], tuple) for s in stars))


if __name__ == '__main__':
    unittest.main()
