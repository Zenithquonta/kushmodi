"""Phase 11: the daily archive sync against a local bare repository standing in for GitHub (needs only git)."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SYNC = ROOT/'deploy'/'sync.sh'
TOOL = ROOT/'deploy'/'archive_tool.py'
WEBP = b'RIFF\x24\x00\x00\x00WEBPVP8 ' + bytes(range(24))


def git(cwd, *args, check=True):
    env = dict(os.environ, GIT_AUTHOR_NAME='t', GIT_AUTHOR_EMAIL='t@t.invalid', GIT_COMMITTER_NAME='t',
               GIT_COMMITTER_EMAIL='t@t.invalid')
    return subprocess.run(['git', '-C', str(cwd), *args], check=check, capture_output=True, text=True, env=env)


def entry(day):
    return dict(date=day, files={kind: dict(path=f'{day[:4]}/{day}-{kind}.webp', bytes=len(WEBP)) for kind in ('day', 'night')})


class Gallery(unittest.TestCase):
    def setUp(self):
        import sys
        sys.path.insert(0, str(ROOT/'deploy'))
        import archive_gallery
        self.gallery = archive_gallery
        self.tmp = Path(tempfile.mkdtemp())
        (self.tmp/'2026').mkdir()
        for day in ('2026-12-13', '2026-12-14'):
            for kind in ('day', 'night'):
                (self.tmp/'2026'/f'{day}-{kind}.webp').write_bytes(WEBP)

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_hostile_index_fields_never_reach_a_page(self):
        evil = dict(entry('2026-12-14'), season='<img src=x onerror=alert(1)>', moon_illuminated='1; DROP',
                    meteor_shower='](javascript:alert(1))', planets_at_night=['Venus', '<script>', 'Saturn'])
        index = dict(frames={'2026-12-14': evil, '2026-12-13': entry('2026-12-13')})
        text = ''.join(self.gallery.pages(index, self.tmp).values())
        for bad in ('onerror', 'javascript', '<script', 'DROP', 'src=x'):
            self.assertNotIn(bad, text)
        self.assertIn('Venus, Saturn', text)

    def test_sparse_entries_and_missing_frames(self):
        index = dict(frames={'2026-12-14': entry('2026-12-14'), '2026-12-13': {}, '2026-12-20': entry('2026-12-20'),
                             '../etc': entry('2026-12-14')})
        pages = self.gallery.pages(index, self.tmp)
        self.assertEqual(sorted(pages), ['2026/2026-12.md', 'README.md'])
        self.assertNotIn('20 Dec', pages['2026/2026-12.md'])     # its frames are not present
        self.assertIn('13 Dec', pages['2026/2026-12.md'])

    def test_pages_are_deterministic(self):
        index = dict(frames={'2026-12-14': dict(entry('2026-12-14'), season='hemanta', moon_illuminated=.257)})
        self.assertEqual(self.gallery.pages(index, self.tmp), self.gallery.pages(index, self.tmp))
        self.assertIn('Hemanta · moon 26%', self.gallery.pages(index, self.tmp)['README.md'])


@unittest.skipUnless(shutil.which('git') and shutil.which('bash'), 'needs git and bash')
class Sync(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.origin = self.tmp/'origin.git'
        git(self.tmp, 'init', '--quiet', '--bare', '-b', 'main', str(self.origin))
        git(self.origin, 'config', 'uploadpack.allowFilter', 'true')
        seed = self.tmp/'seed'
        git(self.tmp, 'init', '--quiet', '-b', 'main', str(seed))
        (seed/'README.md').write_text('profile\n')
        (seed/'scripts').mkdir()
        (seed/'scripts'/'code.py').write_text('print(1)\n')
        (seed/'archive'/'2026').mkdir(parents=True)
        (seed/'archive'/'2026'/'2026-10-01-day.webp').write_bytes(WEBP)
        (seed/'archive'/'2026'/'2026-10-01-night.webp').write_bytes(WEBP)
        (seed/'archive'/'index.json').write_text(json.dumps(dict(version=1, frames={'2026-10-01': entry('2026-10-01')})))
        git(seed, 'add', '-A')
        git(seed, 'commit', '--quiet', '-m', 'seed')
        git(seed, 'push', '--quiet', str(self.origin), 'main')
        self.clone = self.tmp/'clone'
        git(self.tmp, 'clone', '--quiet', '--filter=blob:none', '--no-checkout', f'file://{self.origin}', str(self.clone))
        git(self.clone, 'sparse-checkout', 'set', '--no-cone', '/archive/')
        git(self.clone, 'checkout', '--quiet', 'main')
        self.src = self.tmp/'src'
        (self.src/'2026').mkdir(parents=True)
        (self.src/'.lock').write_text('')
        self.add_day('2026-10-02')

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def add_day(self, day):
        for kind in ('day', 'night'):
            (self.src/day[:4]/f'{day}-{kind}.webp').write_bytes(WEBP+day.encode())
        index_path = self.src/'index.json'
        index = json.loads(index_path.read_text()) if index_path.exists() else dict(version=1, frames={})
        index['frames'][day] = entry(day)
        index_path.write_text(json.dumps(index))

    def sync(self):
        env = dict(os.environ, SYNC_HOME=str(self.tmp/'home'), SYNC_CLONE=str(self.clone), ARCHIVE_SRC=str(self.src),
                   ARCHIVE_TOOL=str(TOOL), SYNC_RETRY_SECONDS='0')
        return subprocess.run(['bash', str(SYNC)], capture_output=True, text=True, env=env)

    def origin_log(self):
        return git(self.origin, 'log', '--format=%an|%ae|%s', 'main').stdout.splitlines()

    def changed_paths(self, rev='main'):
        return git(self.origin, 'show', '--name-only', '--format=', rev).stdout.split()

    def test_first_run_commits_only_archive_files_and_a_rerun_does_nothing(self):
        result = self.sync()
        self.assertEqual(result.returncode, 0, result.stderr)
        log = self.origin_log()
        self.assertEqual(log[0], 'Observatory archive|archive@observatory.invalid|Archive 2026-10-02')
        self.assertTrue(all(p.startswith('archive/') for p in self.changed_paths()))
        self.assertEqual(self.sync().returncode, 0)
        self.assertEqual(len(self.origin_log()), len(log))

    def test_gallery_pages_arrive_with_the_frames_and_a_rerun_changes_nothing(self):
        self.assertEqual(self.sync().returncode, 0)
        paths = self.changed_paths()
        for page in ('archive/README.md', 'archive/2026/2026-10.md'):
            self.assertIn(page, paths)
        self.assertTrue(all(p.startswith('archive/') for p in paths))
        front = git(self.origin, 'show', 'main:archive/README.md').stdout
        self.assertIn('## 2 Oct 2026', front)
        self.assertIn('[October 2026](2026/2026-10.md) (2 days)', front)   # the repo's 1 Oct is kept
        commits = len(self.origin_log())
        self.assertEqual(self.sync().returncode, 0)
        self.assertEqual(len(self.origin_log()), commits)

    def test_the_index_keeps_dates_the_server_no_longer_has(self):
        self.assertEqual(self.sync().returncode, 0, )
        index = json.loads(git(self.origin, 'show', 'main:archive/index.json').stdout)
        self.assertEqual(sorted(index['frames']), ['2026-10-01', '2026-10-02'])

    def test_a_rejected_push_is_retried_from_the_new_main(self):
        hook = self.origin/'hooks'/'pre-receive'
        marker = self.tmp/'rejected-once'
        hook.write_text(f'#!/bin/sh\nif [ ! -e "{marker}" ]; then touch "{marker}"; echo busy >&2; exit 1; fi\nexit 0\n')
        hook.chmod(0o755)
        result = self.sync()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('push rejected (attempt 1)', result.stderr)
        self.assertEqual([line.split('|')[2] for line in self.origin_log()], ['Archive 2026-10-02', 'seed'])

    def test_upstream_work_is_kept(self):
        other = self.tmp/'other'
        git(self.tmp, 'clone', '--quiet', f'file://{self.origin}', str(other))
        (other/'README.md').write_text('profile, edited\n')
        git(other, 'commit', '--quiet', '-am', 'edit readme')
        git(other, 'push', '--quiet', 'origin', 'main')
        self.assertEqual(self.sync().returncode, 0)
        self.assertEqual(git(self.origin, 'show', 'main:README.md').stdout, 'profile, edited\n')
        self.assertEqual(self.changed_paths(), ['archive/2026/2026-10-02-day.webp', 'archive/2026/2026-10-02-night.webp',
                                                'archive/2026/2026-10.md', 'archive/README.md', 'archive/index.json'])

    def test_junk_in_the_archive_stops_the_sync(self):
        (self.src/'2026'/'payload.webp').write_bytes(WEBP)
        result = self.sync()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('unexpected file name', result.stderr)
        self.assertEqual(len(self.origin_log()), 1)

    def test_a_file_that_is_not_webp_stops_the_sync(self):
        (self.src/'2026'/'2026-10-02-day.webp').write_bytes(b'#!/bin/sh\necho hi\n')
        result = self.sync()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('is not a WebP file', result.stderr)

    def test_the_clone_holds_no_code(self):
        self.assertFalse((self.clone/'scripts').exists())
        self.assertFalse((self.clone/'README.md').exists())
        self.assertTrue((self.clone/'archive'/'index.json').exists())


if __name__ == '__main__':
    unittest.main()
