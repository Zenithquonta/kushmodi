"""Phase 12: the README hero switch (repo animation <-> VPS live view) and the quality gate in both modes."""
import json
from pathlib import Path
import unittest

import quality_gate
import readme_live

ROOT = Path(__file__).resolve().parents[1]
README = (ROOT/'README.md').read_text()
CONFIG_TEXT = (ROOT/'config'/'observatory.json').read_text()
HOST = 'sky.example.com'


class Switch(unittest.TestCase):
    def test_published_readme_is_in_repo_mode_with_no_host(self):
        self.assertEqual(readme_live.mode(README), 'repo')
        self.assertIsNone(json.loads(CONFIG_TEXT)['live']['host'])

    def test_round_trip_restores_the_readme_byte_for_byte(self):
        live = readme_live.switch(README, HOST)
        self.assertEqual(readme_live.mode(live), f'live ({HOST})')
        self.assertEqual(readme_live.switch(live), README)

    def test_only_the_hero_changes(self):
        live = readme_live.switch(README, HOST)
        head, _, tail = readme_live.split(README)
        self.assertTrue(live.startswith(head) and live.endswith(tail))

    def test_live_hero_has_reduced_motion_still_and_a_visible_way_back(self):
        hero = readme_live.split(readme_live.switch(README, HOST))[1]
        self.assertIn(f'<source media="(prefers-reduced-motion: reduce)" srcset="https://{HOST}/live.png" />', hero)
        self.assertIn(f'<img src="https://{HOST}/live.svg"', hero)
        self.assertIn('href="./assets/observatory.gif"', hero)

    def test_bad_hosts_are_refused(self):
        for host in ('http://sky.example.com', 'Sky.Example.com', 'sky.example.com" onerror="x', 'localhost',
                     'sky.example.com/live.svg', '', '-x.example.com'):
            with self.assertRaises(ValueError, msg=host):
                readme_live.switch(README, host)

    def test_config_edit_changes_only_the_host(self):
        new = readme_live.set_host(CONFIG_TEXT, HOST)
        self.assertEqual(json.loads(new)['live']['host'], HOST)
        self.assertEqual(new.replace(f'"host": "{HOST}"', '"host": null'), CONFIG_TEXT)


class Gate(unittest.TestCase):
    def test_gate_passes_in_both_modes(self):
        config = json.loads(CONFIG_TEXT)
        quality_gate.readme(README, config)
        quality_gate.readme(readme_live.switch(README, HOST), dict(config, live=dict(host=HOST)))

    def test_gate_rejects_an_external_image_from_another_host(self):
        live = readme_live.switch(README, HOST)
        with self.assertRaises(AssertionError):
            quality_gate.readme(live, dict(json.loads(CONFIG_TEXT), live=dict(host='other.example.com')))
        with self.assertRaises(AssertionError):
            quality_gate.readme(live, json.loads(CONFIG_TEXT))   # host not configured


if __name__ == '__main__':
    unittest.main()
