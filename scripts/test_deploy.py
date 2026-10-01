"""Phase 10: the compact live SVG and the deployment files (what can be checked without a server)."""
from datetime import datetime
from pathlib import Path
import re
import tempfile
import unittest
from unittest import mock
from zoneinfo import ZoneInfo

import build_animation as scene
import render_live
import scene_state
import test_render_daily

ROOT = Path(__file__).resolve().parents[1]
DEPLOY = ROOT/'deploy'
NOON = datetime(2027, 5, 15, 12, 0, tzinfo=ZoneInfo('Asia/Kolkata'))


class Compact(unittest.TestCase):
    def test_compact_live_svg_is_small_and_reencoded(self):
        state = scene_state.scene_state(NOON)
        full, compact = scene.scene(0, True, state=state), scene.scene(0, True, state=state, compact=True)
        self.assertLess(len(compact), 2_600_000)
        self.assertLess(len(compact), len(full)/3)
        self.assertIn('data:image/jpeg;base64,', compact)
        self.assertIn('data:image/webp;base64,', compact)
        for png, _ in scene.compact_sources():
            self.assertNotIn(png, compact)

    def test_each_large_raster_is_embedded_once(self):
        compact = scene.scene(0, True, state=scene_state.scene_state(NOON), compact=True)
        for uri in set(re.findall(r'"(data:image/(?:jpeg|webp);base64,[^"]+)"', compact)):
            self.assertEqual(compact.count(uri), 1)

    def test_day_plates_are_drawn_through_the_ground_mask(self):
        svg = scene.scene(0, False, state=scene_state.scene_state(NOON))
        self.assertIn('data-light="plate-day" href="#plate-day" xlink:href="#plate-day" opacity="1" mask="url(#ground-mask)"', svg)

    def test_default_scene_is_untouched_by_compact_mode(self):
        self.assertEqual(scene.scene(0, False, compact=True).count('data:image/jpeg'), 1)
        self.assertNotIn('data:image/jpeg', scene.scene(0, False))

    @mock.patch.object(scene, 'rasterize', test_render_daily.fake_rasterize)
    def test_render_live_writes_the_compact_svg(self):
        with tempfile.TemporaryDirectory() as directory:
            render_live.render(NOON, directory)
            self.assertIn('data:image/jpeg;base64,', (Path(directory)/'live.svg').read_text())


class DeployFiles(unittest.TestCase):
    def test_caddy_serves_only_the_three_live_files(self):
        text = (DEPLOY/'Caddyfile.template').read_text()
        self.assertIn('@live path /live.svg /live.png /live.json', text)
        self.assertIn('respond 404', text)
        self.assertEqual(text.count('file_server'), 1)
        self.assertIn('X-Content-Type-Options "nosniff"', text)

    def test_service_is_sandboxed_and_cannot_reach_the_network(self):
        unit = (DEPLOY/'observatory-live.service').read_text()
        for line in ('User=observatory', 'PrivateNetwork=yes', 'ProtectSystem=strict', 'NoNewPrivileges=yes',
                     'ReadWritePaths=/var/lib/observatory/live', 'CapabilityBoundingSet=', 'UMask=0022'):
            self.assertIn(line, unit)
        self.assertIn('OnCalendar=*:0/5', (DEPLOY/'observatory-live.timer').read_text())

    def test_scripts_hold_no_secrets_and_never_pull_code_automatically(self):
        for path in DEPLOY.glob('*'):
            text = path.read_text()
            self.assertNotRegex(text, r'(?i)(ghp_|github_pat_|token=|password=|BEGIN [A-Z ]*PRIVATE KEY)')
        self.assertNotIn('git pull', (DEPLOY/'observatory-live.service').read_text())
        self.assertIn('--ff-only', (DEPLOY/'update.sh').read_text())

    def test_install_validates_the_hostname_before_using_it(self):
        text = (DEPLOY/'install.sh').read_text()
        self.assertLess(text.index('[[ "$HOST" =~'), text.index('sed -e "s|__SITE__|$HOST|"'))
        self.assertIn('set -euo pipefail', text)


if __name__ == '__main__':
    unittest.main()
