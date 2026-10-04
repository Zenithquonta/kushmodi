"""Phase 16: the Living Observatory website (site/), its Caddy deployment and its data builder. No network."""
import gzip
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

import build_site_data as bsd

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT/'site'
DEPLOY = ROOT/'deploy'
OWN_JS = sorted((SITE/'js').glob('*.js'))
LIVE_FILES = ('/live.svg', '/live.png', '/live.json')     # served by Caddy from the renderer's directory, not from site/

LIVE_BLOCK = '''	@live path /live.svg /live.png /live.json
	handle @live {
		header {
			Cache-Control "public, max-age=240"
			X-Content-Type-Options "nosniff"
			Content-Security-Policy "default-src 'none'; img-src data:; style-src 'unsafe-inline'"
			Access-Control-Allow-Origin "*"
			Referrer-Policy "no-referrer"
			-Server
		}
		file_server
	}
'''
EXCLUDED = re.compile(r'GR\s*Modi|Modi\s*Fintelli|clerical|employer|Apps\s*Script|VBA|Workspace\s+automation|web\s*scrap|TradingView|Model\s*UN\b',
                      re.I)
NO_NAMES = re.compile(r'\b(claude|anthropic|opus|sonnet|haiku)\b', re.I)


def site_text_files(vendor=False):
    for path in sorted(SITE.rglob('*')):
        if path.is_file() and path.suffix in ('.html', '.js', '.css', '.json', '.md', '.svg') and (vendor or 'vendor' not in path.parts):
            yield path


def render_template(site='observatorysky.duckdns.org', live='/var/lib/observatory/live', site_root='/opt/observatory/repo/site'):
    text = (DEPLOY/'Caddyfile.template').read_text()
    return text.replace('__SITE_ROOT__', site_root).replace('__SITE__', site).replace('__ROOT__', live)


class CaddyDeployment(unittest.TestCase):
    def test_live_block_is_unchanged(self):
        self.assertIn(LIVE_BLOCK, (DEPLOY/'Caddyfile.template').read_text())

    def test_site_is_served_at_root_with_security_headers(self):
        text = render_template()
        site = text.split('handle @site {', 1)[1].split('\n\thandle {', 1)[0]
        self.assertIn('root * /opt/observatory/repo/site', site)
        for header in ('''Content-Security-Policy "default-src 'self'; img-src 'self' data:; connect-src 'self'; style-src 'self'; script-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"''',
                       'X-Content-Type-Options "nosniff"', 'Referrer-Policy "no-referrer"',
                       'Permissions-Policy "camera=(), microphone=(), geolocation=()"'):
            self.assertIn(header, site)
        self.assertNotIn('browse', text)                       # no directory listing
        self.assertIn('hide *.md', site)
        self.assertTrue(text.rstrip().endswith('handle {\n\t\trespond 404\n\t}\n}'))   # everything else is a 404
        self.assertNotIn('__', text.replace('__init__', ''))

    def test_site_allowlist_covers_exactly_the_published_directories(self):
        match = re.search(r'@site path (.+)', (DEPLOY/'Caddyfile.template').read_text())
        allowed = set(match.group(1).split())
        self.assertEqual(allowed, {'/', '/index.html', '/favicon.svg', '/css/*', '/js/*', '/vendor/*', '/data/*'})
        for entry in SITE.iterdir():
            self.assertTrue(entry.name in ('index.html', 'favicon.svg', 'css', 'js', 'vendor', 'data'), f'unserved file {entry.name}')

    @unittest.skipUnless(shutil.which('caddy'), 'caddy is not installed')
    def test_rendered_caddyfile_validates(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'Caddyfile'
            path.write_text(render_template(site_root=str(SITE)))
            result = subprocess.run(['caddy', 'validate', '--config', str(path), '--adapter', 'caddyfile'], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_scripts_fill_the_site_root_and_check_the_page(self):
        for script in ('install.sh', 'update.sh'):
            text = (DEPLOY/script).read_text()
            self.assertIn('s|__SITE_ROOT__|', text)
            self.assertIn('caddy validate', text)
        self.assertIn('$APP/repo/site', (DEPLOY/'install.sh').read_text())
        check = (DEPLOY/'check.sh').read_text()
        self.assertIn('https://$HOST/"', check)
        self.assertIn('200*text/html*', check)
        self.assertNotIn('for path in / /index.json', check)    # '/' is no longer expected to be a 404
        self.assertIn('/data/SOURCES.md', check)
        self.assertIn('## The website', (DEPLOY/'README.md').read_text())


class Files(unittest.TestCase):
    def resolve(self, source, ref):
        ref = ref.split('#')[0].split('?')[0]
        if ref.startswith('/'):
            return SITE/ref.lstrip('/')
        return (source.parent/ref).resolve()

    def test_everything_the_page_references_exists(self):
        html = (SITE/'index.html').read_text()
        refs = re.findall(r'(?:href|src)="([^"]+)"', html) + [u for s in re.findall(r'srcset="([^"]+)"', html) for u in s.split(',')]
        checked = 0
        for ref in refs:
            ref = ref.strip().split(' ')[0]
            if re.match(r'(https?:|mailto:|#)', ref) or ref in LIVE_FILES:
                continue
            self.assertTrue(self.resolve(SITE/'index.html', ref).is_file(), f'index.html references missing {ref}')
            checked += 1
        self.assertGreaterEqual(checked, 3)

    def test_every_import_and_fetch_exists(self):
        checked = 0
        for path in OWN_JS + sorted((SITE/'vendor').rglob('*.js')):
            text = path.read_text()
            for ref in re.findall(r'''(?:from|import)\s*\(?\s*['"](\.{1,2}/[^'"]+)['"]''', text):
                self.assertTrue(self.resolve(path, ref).is_file(), f'{path.name} imports missing {ref}')
                checked += 1
            self.assertIsNone(re.search(r'''(?:from|import)\s*\(?\s*['"][A-Za-z@][^'"/]*['"]''', text), f'{path.name} has a bare import (needs an import map, i.e. inline script)')
        for path in OWN_JS:
            for ref in re.findall(r'''(?:getJson|fetch)\(\s*['"]([^'"]+)['"]''', path.read_text()):
                if ref in LIVE_FILES:
                    continue
                self.assertTrue(self.resolve(SITE/'index.html', ref).is_file(), f'{path.name} fetches missing {ref}')
                checked += 1
        self.assertGreater(checked, 15)

    def test_no_dotfiles_and_no_large_surprises(self):
        for path in SITE.rglob('*'):
            self.assertFalse(path.name.startswith('.'), path)
            if path.is_file():
                self.assertLess(path.stat().st_size, 2_000_000, path)

    def test_the_site_stays_inside_the_transfer_budget(self):
        total = sum(len(gzip.compress(p.read_bytes(), 9)) for p in SITE.rglob('*') if p.is_file())
        self.assertLess(total, 2_500_000)
        # the 2.5D painted sprites (site/data/scenery, about 0.25 MB) lift the earlier 1 MB target; keep a ceiling
        self.assertLess(total, 1_500_000, 'the target is under 1.5 MB gzipped including the painted scenery')

    def test_vendored_libraries_are_pinned_and_licensed(self):
        three = json.loads((SITE/'vendor/three/package.json').read_text())
        astro = json.loads((SITE/'vendor/astronomy-engine/package.json').read_text())
        self.assertEqual((three['name'], three['version']), ('three', '0.186.1'))
        self.assertEqual((astro['name'], astro['version']), ('astronomy-engine', '2.1.19'))
        for lib in ('three', 'astronomy-engine'):
            self.assertIn('MIT', (SITE/'vendor'/lib/'LICENSE').read_text())
        sources = (SITE/'data/SOURCES.md').read_text()
        for name in ('Yale Bright Star Catalog', 'd3-celestial', 'BSD'):
            self.assertIn(name, sources)


class Data(unittest.TestCase):
    def test_data_files_are_valid_and_small(self):
        stars = json.loads((SITE/'data/stars.json').read_text())
        self.assertEqual(stars['cols'], ['ra_deg', 'dec_deg', 'mag', 'kelvin'])
        self.assertGreater(len(stars['stars']), 4500)
        self.assertLessEqual(max(s[2] for s in stars['stars']), 6.0)
        self.assertEqual(stars['stars'][0][2], min(s[2] for s in stars['stars']))
        names = dict(stars['names'])
        self.assertEqual(stars['stars'][next(i for i, n in names.items() if n == 'Polaris')][0:2], [37.953, 89.264])
        mw = json.loads((SITE/'data/milkyway.json').read_text())
        self.assertEqual(len(mw['levels']), 5)
        self.assertTrue(all(len(ring) % 2 == 0 for level in mw['levels'] for ring in level))
        lines = json.loads((SITE/'data/constellations.json').read_text())
        self.assertGreater(len(lines['constellations']), 80)
        site = json.loads((SITE/'data/site.json').read_text())
        config = json.loads((ROOT/'config/observatory.json').read_text())
        self.assertEqual(site, bsd.build_site(config))
        self.assertEqual((site['latitude'], site['longitude']), (19.076, 72.8777))
        for name, limit in (('stars.json', 200_000), ('milkyway.json', 40_000), ('constellations.json', 30_000)):
            self.assertLess((SITE/'data'/name).stat().st_size, limit)

    def test_committed_files_are_in_the_builders_canonical_form(self):
        for name in ('stars.json', 'milkyway.json', 'constellations.json', 'site.json'):
            text = (SITE/'data'/name).read_text()
            self.assertEqual(bsd.dumps(json.loads(text)), text, name)


class Builder(unittest.TestCase):
    CATALOG = [
        {'HR': '2491', 'N': 'Sirius', 'RA': '06h 45m 08.9s', 'Dec': '-16° 42′ 58″', 'V': '-1.46', 'K': '9750'},
        {'HR': '424', 'N': 'Polaris', 'RA': '02h 31m 49.1s', 'Dec': '+89° 15′ 51″', 'V': '2.02', 'K': '6450'},
        {'HR': '1', 'N': '', 'RA': '00h 05m 09.9s', 'Dec': '-00° 30′ 11″', 'V': '5.5', 'K': '8201'},
        {'HR': '2', 'RA': '00h 05m 09.9s', 'Dec': '+10° 00′ 00″', 'V': '6.5'},     # too faint
        {'HR': '3', 'RA': 'broken', 'Dec': '+10° 00′ 00″', 'V': '3.0'},           # unusable
        {'HR': '4', 'RA': '01h 00m 00s', 'Dec': '+10° 00′ 00″', 'V': ' '},        # no magnitude
    ]

    def test_coordinates_parse_with_signs(self):
        self.assertAlmostEqual(bsd.parse_ra('06h 45m 08.9s'), 101.287, 2)
        self.assertAlmostEqual(bsd.parse_dec('-16° 42′ 58″'), -16.716, 2)
        self.assertLess(bsd.parse_dec('-00° 30′ 11″'), 0)          # the sign of a zero-degree declination survives
        with self.assertRaises(ValueError):
            bsd.parse_ra('nonsense')

    def test_stars_are_filtered_sorted_and_deterministic(self):
        first = bsd.build_stars(self.CATALOG)
        self.assertEqual(first, bsd.build_stars(list(self.CATALOG)))
        self.assertEqual([s[2] for s in first['stars']], [-1.46, 2.02, 5.5])
        self.assertEqual(first['names'], [[0, 'Sirius'], [1, 'Polaris']])
        self.assertEqual(first['stars'][2][3], 8200)               # kelvin rounded to 50
        self.assertEqual(bsd.dumps(first), bsd.dumps(bsd.build_stars(self.CATALOG)))

    def test_simplify_keeps_the_ends_and_corners(self):
        line = [(0, 0), (1, 0.05), (2, 0), (3, 0), (4, 3), (5, 0)]
        out = bsd.simplify(line, 0.4)
        self.assertEqual(out[0], (0, 0))
        self.assertEqual(out[-1], (5, 0))
        self.assertIn((4, 3), out)
        self.assertNotIn((1, 0.05), out)
        self.assertEqual(bsd.simplify(line, 0), line)

    def test_milky_way_and_constellations_convert_reproducibly(self):
        square = [[[-10, -10], [10, -10], [10, 10], [-10, 10], [-10, -10]]]
        mw = {'features': [{'id': 'ol2', 'geometry': {'coordinates': [square]}}, {'id': 'ol1', 'geometry': {'coordinates': [square]}}]}
        out = bsd.build_milkyway(mw)
        self.assertEqual(len(out['levels']), 2)
        self.assertEqual(out, bsd.build_milkyway(mw))
        self.assertEqual(out['levels'][0][0][:2], [-10.0, -10.0])
        lines = {'features': [{'id': 'Ori', 'geometry': {'coordinates': [[[-30.5, 1], [10, 2]], [[5, 5]]]}}]}
        built = bsd.build_constellations(lines)
        self.assertEqual(built, {'constellations': [{'id': 'Ori', 'lines': [[329.5, 1.0, 10.0, 2.0]]}]})


class Safety(unittest.TestCase):
    def test_no_html_injection_sinks_in_our_scripts(self):
        sink = re.compile(r'innerHTML|outerHTML|insertAdjacentHTML|document\.write|\beval\s*\(|new\s+Function|setTimeout\s*\(\s*[\'"`]|setInterval\s*\(\s*[\'"`]')
        for path in OWN_JS:
            self.assertIsNone(sink.search(path.read_text()), path.name)
        for path in (SITE/'vendor').rglob('*.js'):
            self.assertIsNone(re.search(r'\beval\s*\(|new\s+Function\s*\(', path.read_text()), path.name)

    def test_page_works_under_the_content_security_policy(self):
        html = (SITE/'index.html').read_text()
        self.assertNotRegex(html, r'<script(?![^>]*\bsrc=)')                      # no inline script
        self.assertNotRegex(html, r'<style')                                      # no inline stylesheet
        self.assertNotRegex(html, r'\sstyle\s*=')                                 # no style attributes
        self.assertNotRegex(html, r'\son[a-z]+\s*=')                              # no inline handlers
        self.assertNotRegex(html, r'(?:src|href)="https?://(?!(?:github\.com|www\.linkedin\.com)/)')   # no third-party loads
        for path in OWN_JS:
            self.assertNotRegex(path.read_text(), r'''setAttribute\(\s*['"]style['"]''', path.name)
            self.assertNotRegex(path.read_text(), r'''['"]https?://''', path.name)
        self.assertNotIn('@import', (SITE/'css/site.css').read_text())
        self.assertNotIn('url(', (SITE/'css/site.css').read_text())

    def test_live_json_is_validated_not_trusted(self):
        text = (SITE/'js/live.js').read_text()
        for guard in ('Object.hasOwn(SEASONS', 'Object.hasOwn(CONDITIONS', 'clamp('):
            self.assertIn(guard, text)
        self.assertNotIn('.innerHTML', (SITE/'js/hud.js').read_text())

    def test_no_excluded_content_and_no_tool_names_anywhere_on_the_site(self):
        for path in site_text_files():
            text = path.read_text()
            self.assertIsNone(EXCLUDED.search(text), f'{path.relative_to(ROOT)}: excluded content')
            self.assertIsNone(NO_NAMES.search(text), f'{path.relative_to(ROOT)}: tool or model name')
        self.assertIsNone(NO_NAMES.search((ROOT/'docs/WEBSITE.md').read_text()))


class Fallback(unittest.TestCase):
    @staticmethod
    def readme_sections():
        text = (ROOT/'README.md').read_text()
        out = {}
        for match in re.finditer(r'^## ([^\n]+)\n(.*?)(?=^## |^---)', text, re.S | re.M):
            body = re.sub(r'</?details>\n?|<summary>.*?</summary>\n?', '', match.group(2)).strip()
            out[match.group(1)] = [p.strip() for p in body.split('\n\n') if p.strip()]
        return out

    @staticmethod
    def plain(markdown):
        text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', markdown)
        return re.sub(r'\*\*|^- ', '', text, flags=re.M)

    @staticmethod
    def html_text(html):
        import html as h
        return h.unescape(re.sub(r'<[^>]+>', '', html))

    def test_fallback_has_the_readme_titles_and_first_paragraphs_verbatim(self):
        page = self.html_text((SITE/'index.html').read_text())
        sections = self.readme_sections()
        self.assertEqual(list(sections), ['Observatory', 'Flight deck', 'Fab lab', 'Mission log'])
        for title, paragraphs in sections.items():
            self.assertIn(title, page)
            first = self.plain(paragraphs[0].splitlines()[0])
            self.assertIn(first, page, f'{title}: first paragraph missing')
        self.assertIn('Kush Modi', page)
        self.assertIn('Astronomy first. Building toward the unexplored.', page)

    def test_fallback_has_the_live_picture_and_the_readme_contacts(self):
        html = (SITE/'index.html').read_text()
        self.assertIn('<noscript><picture><source media="(prefers-reduced-motion: reduce)" srcset="/live.png"><img src="/live.svg"', html)
        readme = (ROOT/'README.md').read_text()
        contacts = re.findall(r'\[(GitHub|LinkedIn|Email)\]\(([^)]+)\)', readme.split('---')[-1])
        self.assertEqual([c[0] for c in contacts], ['GitHub', 'LinkedIn', 'Email'])
        self.assertEqual(dict(contacts)['Email'], 'mailto:kushmodi@gmail.com')
        for label, url in contacts:
            self.assertIn(f'<a href="{url}">{label}</a>', html)
        self.assertNotIn('kushmodi13', html)

    def test_page_has_a_canvas_hud_and_touch_controls(self):
        html = (SITE/'index.html').read_text()
        for needle in ('id="view"', 'id="hud"', 'id="joy"', 'id="compass-strip"', 'aria-live="polite"', 'id="btn-text"',
                       'BUILDING TOWARD THE UNEXPLORED', 'KUSH MODI'):
            self.assertIn(needle, html)
        css = (SITE/'css/site.css').read_text()
        self.assertIn('image-rendering: pixelated', css)
        self.assertIn('prefers-reduced-motion', css)
        self.assertIn('--cyan: #a8f8ff', css)
        self.assertIn('--amber: #ffc44d', css)


@unittest.skipUnless(shutil.which('node'), 'node is not installed')
class SkyMath(unittest.TestCase):
    def test_nightly_target_is_stable_and_tracks_real_coordinates(self):
        script = '''
import fs from "node:fs";
import {makeObserver, skyState} from "%s/site/js/ephemeris.js";
import {brightStars, nightlyTargetPicker, observingNight} from "%s/site/js/target.js";
const obs=makeObserver(JSON.parse(fs.readFileSync("%s/site/data/site.json")));
const bright=brightStars(JSON.parse(fs.readFileSync("%s/site/data/stars.json")));
const picker=nightlyTargetPicker(bright,obs);
const at=iso=>{const d=new Date(iso);return picker(d,skyState(d,obs));};
const evening=at("2026-10-04T21:00:00+05:30"), midnight=at("2026-10-05T00:30:00+05:30");
const reloaded=nightlyTargetPicker(bright,obs)(new Date("2026-10-05T00:30:00+05:30"),skyState(new Date("2026-10-05T00:30:00+05:30"),obs));
const nights=Array.from({length:14},(_,i)=>at(`2026-10-${String(i+4).padStart(2,'0')}T23:30:00+05:30`));
const day=at("2026-10-04T13:00:00+05:30");
console.log(JSON.stringify({evening,midnight,reloaded,nights,day,key:observingNight(new Date("2026-10-05T11:59:00+05:30")),nextKey:observingNight(new Date("2026-10-05T12:00:00+05:30"))}));
''' % (ROOT.as_uri(), ROOT.as_uri(), ROOT.as_posix(), ROOT.as_posix())
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'nightly.mjs'
            path.write_text(script)
            result = subprocess.run(['node', str(path)], capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout.strip().splitlines()[-1])
        self.assertEqual(data['evening']['name'], data['midnight']['name'])
        self.assertEqual(data['midnight']['name'], data['reloaded']['name'])
        self.assertNotEqual(data['evening']['azimuth'], data['midnight']['azimuth'])
        self.assertEqual((data['key'], data['nextKey']), ('2026-10-04', '2026-10-05'))
        self.assertGreater(len({t['name'] for t in data['nights']}), 1)
        self.assertTrue(all(t['name'] != 'Sun' and t['altitude'] > 0 and not t['daylight'] for t in data['nights']))
        self.assertTrue(data['day']['daylight'])

    def test_polaris_and_saturn_match_the_renderers_numbers(self):
        script = '''
import * as e from "%s/site/js/ephemeris.js";
import fs from "node:fs";
const site = JSON.parse(fs.readFileSync("%s/site/data/site.json"));
const obs = e.makeObserver(site);
const s = e.skyState(new Date("2026-10-04T18:00:00Z"), obs);
const stars = JSON.parse(fs.readFileSync("%s/site/data/stars.json"));
const p = stars.stars[stars.names.find(([, n]) => n === "Polaris")[0]];
const w = e.applyMatrix(s.matrix, ...e.eqjUnit(p[0], p[1]));
const polaris = e.altAz(w);
const trails = e.bodyTrails(new Date("2026-10-04T18:00:00Z"), obs, ["Saturn"], 60, 30);
console.log(JSON.stringify({ saturn: s.planets.find((x) => x.name === "Saturn"), polaris, trail: Array.from(trails[0]) }));
''' % (ROOT.as_uri(), ROOT.as_posix(), ROOT.as_posix())
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'check.mjs'
            path.write_text(script)
            result = subprocess.run(['node', str(path)], capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout.strip().splitlines()[-1])
        self.assertAlmostEqual(data['saturn']['altitude'], 67.378, delta=0.05)        # live.json of the renderer
        self.assertAlmostEqual(data['saturn']['azimuth'], 137.352, delta=0.05)
        self.assertAlmostEqual(data['polaris']['alt'], 19.47, delta=0.1)              # about the latitude
        self.assertLess(abs(data['polaris']['az'] - 0.5), 0.3)
        self.assertEqual(len(data['trail']), 9)                                       # 3 samples: now, 30 and 60 minutes ago
        self.assertNotEqual(data['trail'][0:3], data['trail'][6:9])


if __name__ == '__main__':
    unittest.main()
