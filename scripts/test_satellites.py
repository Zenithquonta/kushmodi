"""Phase 15e: the ISS, Hubble and Tiangong. The fetcher's validation, the offline computation (against an independent
SGP4 and Earth-rotation calculation), the screen page, the log beats and the animated pass.

The element sets are synthetic but valid: the published layout of a CelesTrak ISS entry with the epoch set a few hours
before the test time, the checksums computed here, and the orbit's node and phase chosen (by a one-off search) so that
the ISS passes over Mumbai on the evening of 2 Oct 2026."""
from datetime import date, datetime, timedelta, timezone
import json
import math
import os
from pathlib import Path
import re
import socket
import tempfile
import unittest
from unittest import mock
from zoneinfo import ZoneInfo

import astronomy as ae
import numpy as np
from sgp4.api import Satrec, jday

import build_animation as scene
import render_daily
import render_live
import satellites as sat
import scene_state
import story
import test_daily
import test_render_daily
import test_scene
from test_story import eligible

IST = ZoneInfo('Asia/Kolkata')
UTC = timezone.utc
EPOCH = datetime(2026, 10, 2, 5, 0, tzinfo=UTC)
FETCHED = datetime(2026, 10, 2, 6, 0, tzinfo=UTC)
CONFIG = scene_state.load_config()
LOC = CONFIG['location']
LOC_KEY = (LOC['latitude'], LOC['longitude'], LOC['elevation_m'], LOC['timezone'])
BEFORE = datetime(2026, 10, 2, 19, 20, tzinfo=IST)   # the ISS pass starts at 19:32
HOUR_BEFORE = datetime(2026, 10, 2, 18, 30, tzinfo=IST)
MORNING = datetime(2026, 10, 2, 9, 0, tzinfo=IST)
DURING = datetime(2026, 10, 2, 19, 34, tzinfo=IST)
AFTER = datetime(2026, 10, 2, 19, 40, tzinfo=IST)


def make_tle(catnr, epoch, inclination, raan, eccentricity, perigee, anomaly, motion):
    """A valid two-line element set (published layout, computed checksums)."""
    day = (epoch-datetime(epoch.year, 1, 1, tzinfo=UTC)).total_seconds()/86400+1
    line1 = f'1 {catnr:05d}U 98067A   {epoch.year % 100:02d}{day:012.8f}  .00016717  00000-0  10270-3 0  999'
    line2 = (f'2 {catnr:05d} {inclination:8.4f} {raan:8.4f} {round(eccentricity*1e7):07d} {perigee:8.4f} '
             f'{anomaly:8.4f} {motion:11.8f}    1')
    line1, line2 = line1.ljust(68)[:68], line2.ljust(68)[:68]
    return line1+str(sat.checksum(line1)), line2+str(sat.checksum(line2))


ISS = make_tle(25544, EPOCH, 51.6416, 280, 0.0006703, 130.5360, 270, 15.72125391)
HUBBLE = make_tle(20580, EPOCH, 28.4700, 100, 0.0002, 60, 200, 15.10)
TIANGONG = make_tle(48274, EPOCH, 41.4700, 200, 0.0004, 90, 10, 15.60)


def elements(**changes):
    out = {catnr: sat.entry_for(catnr, *lines, sat.epoch_of(lines[0]))
           for catnr, lines in ((25544, ISS), (20580, HUBBLE), (48274, TIANGONG))}
    out.update(changes)
    return out


def feed(catnr, lines, name='ISS (ZARYA)', eol='\r\n'):
    return (name+eol+lines[0]+eol+lines[1]+eol).encode()


def state_at(when, tles=None):
    return scene_state.scene_state(when, CONFIG, None, elements() if tles is None else tles)


def sat_state(when, **cache):
    return state_at(when)


def with_checksum(line):
    return line[:68]+str(sat.checksum(line))


class Fetch(unittest.TestCase):
    def parse(self, text, catnr=25544, now=FETCHED):
        return sat.parse(text, catnr, now)

    def test_a_good_response_is_accepted_and_named_from_the_catalogue(self):
        entry = self.parse(feed(25544, ISS))
        self.assertEqual((entry['name'], entry['line1'], entry['line2']), ('ISS', *ISS))
        self.assertEqual(entry['epoch'], EPOCH.isoformat())
        evil = self.parse(feed(25544, ISS, name='<script>alert(1)</script> HACKED', eol='\n'))
        self.assertEqual(evil['name'], 'ISS')
        self.assertNotIn('HACKED', json.dumps(evil))
        self.assertEqual(self.parse(feed(25544, ISS, name='', eol='\n'))['name'], 'ISS')

    def test_a_checksum_error_is_refused(self):
        digits = ISS[0][:20]+str((int(ISS[0][20])+1) % 10)+ISS[0][21:]   # a changed digit, the old checksum
        for lines in ((digits, ISS[1]), (ISS[0], ISS[1][:30]+str((int(ISS[1][30])+3) % 10)+ISS[1][31:])):
            with self.assertRaises(sat.Invalid):
                self.parse(feed(25544, lines))
        wrong_digit = ISS[0][:68]+str((int(ISS[0][68])+1) % 10)
        with self.assertRaises(sat.Invalid):
            self.parse(feed(25544, (wrong_digit, ISS[1])))
        self.assertEqual(sat.checksum(ISS[0]), int(ISS[0][68]))

    def test_the_catalogue_number_must_be_the_one_asked_for(self):
        with self.assertRaises(sat.Invalid):
            self.parse(feed(25544, ISS), catnr=20580)   # an ISS answer to a Hubble request
        other = make_tle(25545, EPOCH, 51.6, 280, 0.0006, 130, 270, 15.7)
        with self.assertRaises(sat.Invalid):
            self.parse(feed(25544, (ISS[0], other[1])))   # the two lines disagree
        with self.assertRaises(sat.Invalid):
            self.parse(feed(25545, other))                 # not in the catalogue we ask for

    def test_the_layout_must_be_exact(self):
        bad = {
            'long line': feed(25544, (ISS[0]+' ', ISS[1])),
            'short line': feed(25544, (ISS[0][:-1], ISS[1])),
            'swapped lines': feed(25544, (ISS[1], ISS[0])),
            'line numbers': feed(25544, ('3'+ISS[0][1:], ISS[1])),
            'two lines only': (ISS[0]+'\n'+ISS[1]+'\n').encode(),
            'four lines': feed(25544, ISS)+b'extra\n',
            'no data': b'No GP data found\n',
            'empty': b'',
            'html': b'<html><body>blocked</body></html>',
            'non-ascii': feed(25544, ISS, name='ISS é').replace(b'\xc3', b'\xff'),
            'letters in the elements': feed(25544, (ISS[0][:30]+'Q'+ISS[0][31:], ISS[1])),
        }
        bad['non-ascii'] = 'ISS é\n'.encode()+ISS[0].encode()+b'\n'+ISS[1].encode()+b'\n'
        for what, body in bad.items():
            with self.subTest(what), self.assertRaises(sat.Invalid):
                self.parse(body)

    def test_the_epoch_must_be_fresh_and_not_from_the_future(self):
        def at(days):
            lines = make_tle(25544, FETCHED+timedelta(days=days), 51.6416, 280, 0.0006703, 130.5360, 270, 15.72125391)
            return feed(25544, lines)
        self.parse(at(-6.9))
        self.parse(at(.9))
        for days in (-7.1, -30, 1.1, 40):
            with self.subTest(days), self.assertRaises(sat.Invalid):
                self.parse(at(days))

    def test_the_epoch_columns_are_read_with_the_two_digit_year_rule(self):
        self.assertEqual(sat.epoch_of(ISS[0]), EPOCH)
        old = '1 25544U 98067A   99365.50000000  .00016717  00000-0  10270-3 0  9990'
        self.assertEqual(sat.epoch_of(old), datetime(1999, 12, 31, 12, tzinfo=UTC))
        with self.assertRaises(sat.Invalid):
            sat.epoch_of('1 25544U 98067A   26400.50000000')

    def test_an_oversized_response_is_refused_before_it_is_parsed(self):
        class Response:
            def __init__(self, body):
                self.body, self.asked = body, None

            def read(self, limit):
                self.asked = limit
                return self.body[:limit]

            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

        big = Response(feed(25544, ISS)+b' '*(sat.MAX_BYTES+10))
        with self.assertRaises(sat.Invalid):
            sat.fetch_one(25544, FETCHED, lambda request, timeout: big)
        self.assertEqual(big.asked, sat.MAX_BYTES+1)   # it never reads more than the cap, plus one byte
        good = Response(feed(25544, ISS))
        self.assertEqual(sat.fetch_one(25544, FETCHED, lambda request, timeout: good)['name'], 'ISS')

    def test_it_asks_celestrak_for_the_three_fixed_numbers_only(self):
        asked = []

        def opener(request, timeout):
            asked.append((request.full_url, timeout))
            lines = {25544: ISS, 20580: HUBBLE, 48274: TIANGONG}[int(re.search(r'CATNR=(\d+)', request.full_url)[1])]
            body = feed(0, lines)

            class Response:
                def read(self, limit):
                    return body[:limit]
                def __enter__(self):
                    return self
                def __exit__(self, *exc):
                    return False
            return Response()

        found = sat.fetch(FETCHED, opener)
        self.assertEqual(sorted(found), [20580, 25544, 48274])
        self.assertEqual([name for name in (found[n]['name'] for n in sorted(found))], ['HUBBLE', 'ISS', 'TIANGONG'])
        self.assertEqual(sorted(url for url, _ in asked),
                         sorted(f'https://celestrak.org/NORAD/elements/gp.php?CATNR={n}&FORMAT=TLE' for n in sat.SATELLITES))
        self.assertTrue(all(timeout <= 30 for _, timeout in asked))

    def test_one_bad_satellite_never_stops_the_others(self):
        def opener(request, timeout):
            number = int(re.search(r'CATNR=(\d+)', request.full_url)[1])
            if number == 20580:
                raise OSError('connection reset')
            if number == 48274:
                body = b'No GP data found\n'
            else:
                body = feed(number, ISS)

            class Response:
                def read(self, limit):
                    return body[:limit]
                def __enter__(self):
                    return self
                def __exit__(self, *exc):
                    return False
            return Response()

        notes = []
        found = sat.fetch(FETCHED, opener, log=notes.append)
        self.assertEqual(list(found), [25544])
        self.assertEqual(len(notes), 2)
        self.assertTrue(any('HUBBLE' in note for note in notes) and any('TIANGONG' in note for note in notes))


class Files(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.out = Path(self.directory.name)

    def tearDown(self):
        self.directory.cleanup()

    def test_store_and_load_round_trip(self):
        sat.store(elements(), self.out, FETCHED)
        self.assertEqual([p.name for p in self.out.iterdir()], ['tle.json'])   # the temp file was moved into place
        self.assertEqual(oct((self.out/'tle.json').stat().st_mode & 0o777), '0o644')
        loaded = sat.load(self.out/'tle.json', FETCHED)
        self.assertEqual(loaded, elements())
        self.assertEqual({entry['name'] for entry in loaded.values()}, set(sat.SATELLITES.values()))

    def test_stale_future_and_missing_elements_are_ignored(self):
        sat.store(elements(), self.out, FETCHED)
        path = self.out/'tle.json'
        self.assertIsNotNone(sat.load(path, EPOCH+timedelta(days=13.9)))
        self.assertIsNone(sat.load(path, EPOCH+timedelta(days=14.1)))
        self.assertIsNotNone(sat.load(path, EPOCH-timedelta(days=.9)))
        self.assertIsNone(sat.load(path, EPOCH-timedelta(days=1.1)))
        self.assertIsNotNone(sat.load(path, EPOCH-timedelta(days=2), future=sat.STALE_AFTER))   # the archive's catch-up
        self.assertIsNone(sat.load(self.out/'missing.json', EPOCH))
        path.write_text('not json')
        self.assertIsNone(sat.load(path, EPOCH))
        path.write_text('{"satellites": []}')
        self.assertIsNone(sat.load(path, EPOCH))

    def test_a_tampered_file_is_checked_again_and_names_come_from_the_catalogue(self):
        sat.store(elements(), self.out, FETCHED)
        path = self.out/'tle.json'
        data = json.loads(path.read_text())
        data['satellites']['25544']['name'] = '<img src=x onerror=alert(1)>'
        data['satellites']['20580']['line1'] = data['satellites']['20580']['line1'][:20]+'9'+data['satellites']['20580']['line1'][21:]
        data['satellites']['48274']['line2'] = data['satellites']['25544']['line2']   # the wrong catalogue number
        data['satellites']['99999'] = data['satellites']['25544']                      # not a satellite we track
        path.write_text(json.dumps(data))
        loaded = sat.load(path, EPOCH)
        self.assertEqual(list(loaded), [25544])
        self.assertEqual(loaded[25544]['name'], 'ISS')
        self.assertNotIn('img', json.dumps(loaded))

    def test_a_failed_download_keeps_the_previous_elements_of_that_satellite(self):
        sat.store(elements(), self.out, FETCHED)
        newer = make_tle(25544, EPOCH+timedelta(hours=12), 51.6416, 280, 0.0006703, 130.5360, 270, 15.72125391)
        kept = sat.store({25544: sat.entry_for(25544, *newer, sat.epoch_of(newer[0]))}, self.out, FETCHED+timedelta(hours=12))
        self.assertEqual(sorted(kept), [20580, 25544, 48274])
        self.assertEqual(kept[25544]['line1'], newer[0])
        self.assertEqual(kept[20580]['line1'], HUBBLE[0])
        self.assertEqual(sorted(sat.load(self.out/'tle.json', EPOCH+timedelta(hours=13))), [20580, 25544, 48274])
        later = sat.store({}, self.out, FETCHED+timedelta(days=14))   # what is older than 14 days drops out; the 12 h newer ISS set stays
        self.assertEqual(list(later), [25544])


def independent_altitude_azimuth(lines, when):
    """Altitude and azimuth in degrees from raw SGP4 and an Earth rotation written here (IAU 1982 GMST, TEME to
    the Earth-fixed frame about the pole, WGS84 geodetic observer, east-north-up), with UT1 taken as UTC (the
    difference is below 0.9 s, which turns the Earth by less than 0.004 degrees)."""
    satrec = Satrec.twoline2rv(*lines)
    when = when.astimezone(UTC)
    jd, fraction = jday(when.year, when.month, when.day, when.hour, when.minute, when.second+when.microsecond/1e6)
    error, r, _ = satrec.sgp4(jd, fraction)
    assert error == 0
    t = (jd+fraction-2451545.0)/36525
    seconds = 67310.54841+(876600*3600+8640184.812866)*t+.093104*t*t-6.2e-6*t**3
    theta = math.radians((seconds/240) % 360)
    x, y, z = (math.cos(theta)*r[0]+math.sin(theta)*r[1], -math.sin(theta)*r[0]+math.cos(theta)*r[1], r[2])
    lat, lon = math.radians(LOC['latitude']), math.radians(LOC['longitude'])
    a, f = 6378.137, 1/298.257223563
    e2 = f*(2-f)
    n = a/math.sqrt(1-e2*math.sin(lat)**2)
    h = LOC['elevation_m']/1000
    site = ((n+h)*math.cos(lat)*math.cos(lon), (n+h)*math.cos(lat)*math.sin(lon), (n*(1-e2)+h)*math.sin(lat))
    dx, dy, dz = x-site[0], y-site[1], z-site[2]
    east = -math.sin(lon)*dx+math.cos(lon)*dy
    north = -math.sin(lat)*math.cos(lon)*dx-math.sin(lat)*math.sin(lon)*dy+math.cos(lat)*dz
    up = math.cos(lat)*math.cos(lon)*dx+math.cos(lat)*math.sin(lon)*dy+math.sin(lat)*dz
    rng = math.sqrt(dx*dx+dy*dy+dz*dz)
    return math.degrees(math.asin(up/rng)), math.degrees(math.atan2(east, north)) % 360


def separation(alt1, az1, alt2, az2):
    """Angle in degrees between two directions given as altitude and azimuth."""
    unit = lambda alt, az: np.array([math.cos(math.radians(alt))*math.sin(math.radians(az)),
                                     math.cos(math.radians(alt))*math.cos(math.radians(az)), math.sin(math.radians(alt))])
    return math.degrees(math.acos(min(1.0, float(unit(alt1, az1) @ unit(alt2, az2)))))


class RealFixture(unittest.TestCase):
    """Three element sets downloaded from CelesTrak on 2 Oct 2026 (scripts/fixtures): the real feed's format passes
    the validation and gives plausible, consistent orbits and passes."""
    NOW = datetime(2026, 10, 2, 8, 0, tzinfo=UTC)

    def real(self):
        lines = (Path(__file__).parent/'fixtures'/'celestrak-2026-10-02.tle').read_text().splitlines()
        return {catnr: sat.parse(('\r\n'.join(lines[i:i+3])+'\r\n').encode(), catnr, self.NOW)
                for catnr, i in ((25544, 0), (20580, 3), (48274, 6))}

    def test_the_real_feed_is_accepted_and_gives_plausible_orbits(self):
        found = self.real()
        self.assertEqual(sorted(found), [20580, 25544, 48274])
        state = scene_state.scene_state(datetime(2026, 10, 2, 13, 0, tzinfo=UTC), CONFIG, None, found)['satellites']
        for name, low, high in (('ISS', 380, 450), ('HUBBLE', 450, 560), ('TIANGONG', 370, 420)):
            self.assertTrue(low <= state[name]['height_km'] <= high, (name, state[name]['height_km']))
        iss = state['ISS']['next_pass']
        self.assertEqual(iss['start'][:16], '2026-10-02T18:49')   # a real visible pass, found from the real elements
        self.assertTrue(10 < iss['max_altitude_deg'] < 90)


class Geometry(unittest.TestCase):
    def test_skyfield_agrees_with_an_independent_sgp4_and_earth_rotation(self):
        worst = 0
        for catnr, lines in ((25544, ISS), (20580, HUBBLE), (48274, TIANGONG)):
            entry = elements()[catnr]
            offsets = [0, 61, 1234, 3333, 9000, 20000, 43210, 80000]
            for when in (BEFORE, BEFORE+timedelta(days=1, hours=7)):
                alt, az, _, _ = sat.look(entry, when, offsets, LOC_KEY)
                for i, offset in enumerate(offsets):
                    ours = independent_altitude_azimuth(lines, when+timedelta(seconds=offset))
                    worst = max(worst, separation(alt[i], az[i], *ours))
        self.assertLess(worst, .1, worst)

    def test_the_shadow_model(self):
        sun = [1.5e8, 0, 0]
        self.assertFalse(sat.in_sunlight([-7000, 0, 0], sun))        # straight behind the Earth
        self.assertFalse(sat.in_sunlight([-7000, 5000, 3000], sun))   # behind it, inside the cylinder (off axis 5831)
        self.assertTrue(sat.in_sunlight([-7000, 6400, 0], sun))       # behind it but outside the cylinder (6400 km)
        self.assertTrue(sat.in_sunlight([7000, 0, 0], sun))           # high above the day side
        self.assertTrue(sat.in_sunlight([0, 6900, 0], sun))           # over the terminator, outside the cylinder
        self.assertTrue(sat.in_sunlight([0, 0, 6900], sun))
        self.assertTrue(sat.in_sunlight([42164, 0, 0], sun))
        together = sat.in_sunlight(np.array([[-7000, 7000, 0], [0, 0, 6900], [0, 0, 0]], float), np.array([[1.5e8]*3, [0]*3, [0]*3]))
        self.assertEqual(list(together), [False, True, True])
        tilted = [1e8, 1e8, 0]   # the shadow follows the sun's direction, not a fixed axis
        self.assertFalse(sat.in_sunlight([-5000, -5000, 0], tilted))
        self.assertTrue(sat.in_sunlight([-5000, 5000, 0], tilted))

    def test_a_low_orbit_spends_about_a_third_of_its_time_in_shadow_at_this_season(self):
        entry = elements()[25544]
        start = datetime(2026, 10, 2, 12, tzinfo=IST)
        offsets = np.arange(0, 86400, 60.0)
        _, _, position, _ = sat.look(entry, start, offsets, LOC_KEY)
        sun_km, _ = sat._sun(start, 86400, LOC_KEY)
        lit = sat.in_sunlight(position, sat._interp(offsets, sun_km))
        shadow = 1-lit.mean()
        self.assertTrue(.2 < shadow < .45, shadow)

    def test_compass_points(self):
        self.assertEqual([sat.compass(az) for az in (0, 22.4, 22.6, 90, 180, 225, 270, 337.4, 337.6, 359.9, 360, -10)],
                         ['N', 'N', 'NE', 'E', 'S', 'SW', 'W', 'NW', 'N', 'N', 'N', 'N'])

    def test_no_network_is_used_to_compute_anything(self):
        def refuse(*args, **kwargs):
            raise AssertionError('a socket was opened')
        sat._window.cache_clear()
        sat._sun.cache_clear()
        sat._timescale.cache_clear()
        env = {key: value for key, value in os.environ.items() if key not in ('OBSERVATORY_CACHE', 'CACHE_DIRECTORY')}
        with mock.patch.dict(os.environ, env, clear=True), mock.patch.object(socket, 'socket', refuse), \
                mock.patch.object(socket, 'create_connection', refuse), mock.patch.object(socket, 'getaddrinfo', refuse):
            state = scene_state.scene_state(BEFORE, CONFIG, None, elements())
            light = scene.lighting(state)
            scene.scene(0, True, state=state)
        self.assertEqual(sorted(state['satellites']), ['HUBBLE', 'ISS', 'TIANGONG'])
        self.assertIsNotNone(state['satellites']['ISS']['next_pass'])
        self.assertIsNotNone(light['pass'])


class Passes(unittest.TestCase):
    def test_the_state_describes_each_satellite_and_survives_json(self):
        state = state_at(BEFORE)
        self.assertEqual(list(state['satellites']), ['ISS', 'HUBBLE', 'TIANGONG'])
        for name, data in state['satellites'].items():
            self.assertEqual(data['name'], name)
            self.assertEqual(data['norad'], {v: k for k, v in sat.SATELLITES.items()}[name])
            self.assertTrue(-90 <= data['altitude_deg'] <= 90 and 0 <= data['azimuth_deg'] < 360)
            self.assertIsInstance(data['sunlit'], bool)
            self.assertIsInstance(data['visible'], bool)
            self.assertTrue(300 < data['height_km'] < 600, data['height_km'])
            alt, az = independent_altitude_azimuth(elements()[data['norad']] and (elements()[data['norad']]['line1'],
                                                                                 elements()[data['norad']]['line2']), BEFORE)
            self.assertLess(separation(data['altitude_deg'], data['azimuth_deg'], alt, az), .1)
        again = json.loads(json.dumps(state))
        self.assertEqual(again['satellites'], state['satellites'])

    def test_nothing_without_elements(self):
        self.assertIsNone(scene_state.scene_state(BEFORE, CONFIG)['satellites'])
        self.assertIsNone(scene_state.scene_state(BEFORE, CONFIG, None, {})['satellites'])
        self.assertIsNone(sat.compute({}, BEFORE, CONFIG))
        only = elements()
        del only[25544], only[20580]
        self.assertEqual(list(state_at(BEFORE, only)['satellites']), ['TIANGONG'])

    def test_the_iss_passes_over_mumbai_on_the_evening_of_the_fixture_date(self):
        p = state_at(BEFORE)['satellites']['ISS']['next_pass']
        self.assertEqual((p['start'][:16], p['end'][:16]), ('2026-10-02T19:32', '2026-10-02T19:36'))
        self.assertEqual((p['start_direction'], p['end_direction']), ('SW', 'N'))
        self.assertAlmostEqual(p['max_altitude_deg'], 67.6, delta=1)
        self.assertEqual(p['track'][0][0], 0)

    def test_passes_are_consistent_over_several_days(self):
        checked = 0
        for catnr, entry in elements().items():
            for offset in range(-1, 4):
                day = date(2026, 10, 2)+timedelta(days=offset)
                for p in sat._window(catnr, entry['line1'], entry['line2'], day, LOC_KEY):
                    start, top, end, max_alt, start_az, end_az, track = p
                    checked += 1
                    self.assertTrue(start <= top <= end, p[:3])
                    self.assertTrue(datetime.combine(day, datetime.min.time(), IST)+timedelta(hours=12) <= start
                                    and end < datetime.combine(day+timedelta(days=1), datetime.min.time(), IST)+timedelta(hours=12))
                    self.assertEqual([s for s, _, _ in track], list(range(0, int((end-start).total_seconds())+1, sat.STEP_S)))
                    alts = [alt for _, alt, _ in track]
                    self.assertEqual(max(alts), max_alt)
                    self.assertGreaterEqual(max_alt, alts[0])    # the highest point is never below the ends
                    self.assertGreaterEqual(max_alt, alts[-1])
                    self.assertTrue(all(alt >= sat.MIN_ALTITUDE_DEG for alt in alts))
                    self.assertEqual((track[0][2], track[-1][2]), (start_az, end_az))
                    self.assertEqual(top-start, timedelta(seconds=round((top-start).total_seconds())))
                    self.assertTrue(timedelta(seconds=10) <= end-start+timedelta(seconds=10) <= timedelta(minutes=16))
                    sun = ae.Equator(ae.Body.Sun, scene_state._ae_time(start.astimezone(UTC)),
                                     ae.Observer(*LOC_KEY[:3]), True, True)
                    sun_alt = ae.Horizon(scene_state._ae_time(start.astimezone(UTC)), ae.Observer(*LOC_KEY[:3]),
                                         sun.ra, sun.dec, ae.Refraction.Airless).altitude
                    self.assertLess(sun_alt, sat.SUN_LIMIT_DEG+.2)   # dark enough at the start
        self.assertGreater(checked, 3)

    def test_every_sample_of_a_pass_is_sunlit_and_above_ten_degrees_by_the_independent_calculation(self):
        entry = elements()[25544]
        p = state_at(BEFORE)['satellites']['ISS']['next_pass']
        start = datetime.fromisoformat(p['start'])
        for offset, alt, az in p['track'][::4]:
            ours = independent_altitude_azimuth((entry['line1'], entry['line2']), start+timedelta(seconds=offset))
            self.assertLess(separation(alt, az, *ours), .1)
            self.assertGreater(ours[0], 9.9)
        offsets = [s for s, _, _ in p['track']]
        _, _, position, _ = sat.look(entry, start, offsets, LOC_KEY)
        sun_km, _ = sat._sun(start, 600, LOC_KEY)
        self.assertTrue(sat.in_sunlight(position, sat._interp(np.array(offsets, float), sun_km)).all())

    def test_the_next_pass_is_the_first_one_still_to_end(self):
        for when, expected in ((BEFORE, '19:32'), (DURING, '19:32')):
            self.assertEqual(state_at(when)['satellites']['ISS']['next_pass']['start'][11:16], expected)
        after = state_at(AFTER)['satellites']['ISS']['next_pass']
        self.assertTrue(after is None or after['start'] > AFTER.isoformat())
        self.assertTrue(after is None or datetime.fromisoformat(after['start'])-AFTER < timedelta(days=1))

    def test_visible_needs_dark_sky_sunlight_and_height(self):
        state = state_at(DURING)
        self.assertEqual(state['satellites']['ISS']['visible'],
                         state['satellites']['ISS']['sunlit'] and state['satellites']['ISS']['altitude_deg'] > 10
                         and state['astronomy']['sun']['altitude_deg'] < -6)
        self.assertTrue(state['satellites']['ISS']['visible'])
        noon = state_at(datetime(2026, 10, 2, 12, tzinfo=IST))
        self.assertFalse(any(data['visible'] for data in noon['satellites'].values()))   # never in daylight

    def test_the_search_is_cached_per_element_set_and_night(self):
        sat._window.cache_clear()
        state_at(BEFORE)
        misses = sat._window.cache_info().misses
        state_at(BEFORE+timedelta(minutes=5))
        self.assertEqual(sat._window.cache_info().misses, misses)
        self.assertGreater(sat._window.cache_info().hits, 0)
        newer = elements()
        newer[25544] = sat.entry_for(25544, *make_tle(25544, EPOCH+timedelta(hours=3), 51.6416, 281, 0.0006703, 130.5360, 270,
                                                      15.72125391), EPOCH+timedelta(hours=3))
        state_at(BEFORE, newer)
        self.assertGreater(sat._window.cache_info().misses, misses)

    def test_the_disk_cache_serves_later_renders_and_is_never_trusted(self):
        with tempfile.TemporaryDirectory() as directory, mock.patch.dict(os.environ, {'OBSERVATORY_CACHE': directory}):
            sat._window.cache_clear()
            first = state_at(BEFORE)['satellites']
            files = sorted(Path(directory).glob('satellites-*.json'))
            self.assertEqual(len(files), 6)   # three satellites, two observing nights
            sat._window.cache_clear()
            with mock.patch.object(sat, '_search', side_effect=AssertionError('searched again')):
                self.assertEqual(state_at(BEFORE+timedelta(minutes=10))['satellites']['ISS']['next_pass'],
                                 first['ISS']['next_pass'])
            # a poisoned cache entry is refused and recomputed
            poisoned = next(p for p in files if json.loads(p.read_text()))
            data = json.loads(poisoned.read_text())
            data[0][3] = 999
            poisoned.write_text(json.dumps(data))
            garbage = next(p for p in files if p != poisoned)
            garbage.write_text('{{{ nope')
            sat._window.cache_clear()
            self.assertEqual(state_at(BEFORE)['satellites'], first)
            self.assertLess(max(json.loads(poisoned.read_text())[0][3] if json.loads(poisoned.read_text()) else 0, 0), 999)
            # old cache files are pruned
            old = Path(directory)/'satellites-old.json'
            old.write_text('[]')
            os.utime(old, (0, 0))
            sat._window.cache_clear()
            state_at(BEFORE+timedelta(days=3))
            self.assertFalse(old.exists())


class ScreenPage(unittest.TestCase):
    def worst_rows(self):
        out = {}
        for directions in ('NW', 'SW', 'SE', 'NE', 'S', 'N', 'E', 'W'):
            out[directions] = {name: dict(next_pass=dict(start='2026-10-02T23:59:00+05:30', max_altitude_deg=88.4,
                                                         start_direction=directions)) for name in scene.SAT_SHORT}
        return out

    def test_the_schedule_gives_the_page_five_seconds_and_the_blueprint_four(self):
        self.assertEqual(scene.SCREEN_PAGES, (('sun', 0.0, 5.0), ('moon', 5.0, 10.0), ('planets', 10.0, 15.0),
                                              ('sats', 15.0, 20.0)))
        self.assertEqual(scene.SAT_SHORT, story.SAT_SHORT)
        pages = scene.SCREEN_PAGES
        self.assertTrue(all(a[2] == b[1] for a, b in zip(pages, pages[1:])))
        self.assertEqual(pages[-1][2], 20.0)   # the painted blueprint shows from 20 s to the end

    def test_the_lines_come_from_the_computed_passes(self):
        state = state_at(BEFORE)
        lines = scene.screen_lines('sats', state['astronomy'], state['satellites'])
        self.assertEqual(lines[0], 'SAT TRACK')
        self.assertEqual(lines[1], 'ISS 19:32 68°SW')
        self.assertEqual(lines[2:], ['HST --:--', 'CSS --:--'])
        self.assertEqual(scene.screen_lines('sats', state['astronomy'], None), ['SAT TRACK', 'NO ORBIT DATA'])
        self.assertEqual(scene.screen_lines('sats', state['astronomy'], {}), ['SAT TRACK', 'NO ORBIT DATA'])

    def test_every_row_fits_for_any_pass(self):
        for directions, satellites in self.worst_rows().items():
            lines = scene.screen_lines('sats', {}, satellites)
            self.assertEqual(len(lines), 4)
            for text in lines:
                _, width, _ = scene.pixel_text(text, scene.SCREEN[0]+scene.SCREEN_MARGIN, 0, cell=2)   # KeyError: a glyph is missing
                self.assertLessEqual(scene.SCREEN[0]+scene.SCREEN_MARGIN+width, scene.SCREEN[2]-1, (directions, text))
        spaced = scene.screen_lines('sats', {}, self.worst_rows()['S'])
        self.assertEqual(spaced[1], 'ISS 23:59 88° S')   # a one-letter direction keeps its space
        self.assertEqual(scene.screen_lines('sats', {}, self.worst_rows()['NW'])[1], 'ISS 23:59 88 NW')   # no degree sign when it would overrun

    def test_the_page_is_in_the_picture_and_off_at_t0(self):
        state = state_at(BEFORE)
        markup = scene.screen(0, False, scene.lighting(state), state['astronomy'])
        self.assertIn('data-screen="sats" opacity="0"', markup)
        self.assertEqual(markup.count('data-screen="'), 5)   # the wrapper and four pages
        animated = scene.screen(0, True, scene.lighting(state), state['astronomy'])
        self.assertIn('values="0;0;1;1;0;0"', animated.split('data-screen="sats"')[1].split('<path')[0])
        none = scene.screen(0, False, scene.lighting(state_at(BEFORE, {})), state['astronomy'])
        self.assertIn('data-screen="sats"', none)   # without elements the page says so instead of vanishing


class Beats(unittest.TestCase):
    def check(self, beat, note=''):
        self.assertLessEqual(len(beat['lines']), story.LINE_LIMIT, (note, beat['id']))
        for text in beat['lines']:
            _, width, _ = scene.pixel_text(text, scene.STORY_BOX[0]+16, 0)
            self.assertLessEqual(scene.STORY_BOX[0]+16+width, scene.STORY_BOX[2]-12, (note, beat['id'], text))
            self.assertTrue(scene.story_fits(text, None), (note, text))
            self.assertNotRegex(text, r'\bNOW\b|OVERHEAD')

    def sat_beats(self, when, tles=None):
        return [b for b in eligible(state_at(when, tles)) if b['id'].startswith('sat-')]

    def test_a_pass_within_90_minutes_is_announced_with_its_real_time(self):
        beats = {b['id']: b for b in self.sat_beats(HOUR_BEFORE)}
        self.assertEqual(beats['sat-pass-iss']['lines'],
                         ['ISS PASS 19:32', 'MAX 68° · SW TO N', 'VISIBLE 4 MIN', 'LOOK UP AFTER DUSK'])
        self.assertEqual(beats['sat-pass-iss']['priority'], -1)
        self.assertNotIn('sat-next-iss', beats)   # not announced twice
        self.assertNotIn('sat-pass-hubble', beats)
        for when in (BEFORE, DURING):   # still announced while it is under way
            self.assertIn('sat-pass-iss', {b['id'] for b in self.sat_beats(when)}, when)
        self.assertNotIn('sat-pass-iss', {b['id'] for b in self.sat_beats(HOUR_BEFORE-timedelta(minutes=40))})
        self.assertNotIn('sat-pass-iss', {b['id'] for b in self.sat_beats(AFTER)})

    def test_otherwise_the_beats_are_ordinary_and_factual(self):
        beats = {b['id']: b for b in self.sat_beats(MORNING)}
        self.assertEqual(sorted(beats), ['sat-fact-hubble', 'sat-fact-iss', 'sat-fact-tiangong', 'sat-next-iss'])
        self.assertEqual(beats['sat-next-iss']['lines'][:2], ['ISS NEXT PASS', '19:32 · MAX 68°'])
        self.assertEqual(beats['sat-next-iss']['lines'][2], 'SW TO N')
        self.assertIsNone(beats['sat-next-iss']['priority'])
        state = state_at(MORNING)['satellites']
        self.assertEqual(beats['sat-fact-hubble']['lines'][0], 'HUBBLE IN ORBIT SINCE 1990')
        for name in ('hubble', 'iss', 'tiangong'):
            self.assertEqual(beats[f'sat-fact-{name}']['lines'][1], f"ORBIT HEIGHT {state[name.upper()]['height_km']} KM")
        tomorrow = datetime(2026, 10, 2, 19, 40, tzinfo=IST)   # the ISS has no visible pass tonight after 19:36
        for beat in self.sat_beats(tomorrow):
            if beat['id'] == 'sat-next-iss':
                self.assertIn('TOMORROW', beat['lines'][1])

    def test_the_pass_leads_the_log_and_nothing_appears_without_data(self):
        c = story.context(state_at(HOUR_BEFORE), dict(scene.lighting(state_at(HOUR_BEFORE)), mood='calm', flicker=False,
                                                       grounded=False), fits=scene.story_fits)
        for seed in range(20):
            self.assertEqual(story.choose(c, seed)[0]['id'], 'sat-pass-iss')
        plain = [b for b in eligible(scene_state.scene_state(HOUR_BEFORE, CONFIG)) if b['id'].startswith('sat-')]
        self.assertEqual(plain, [])
        self.assertEqual(story.context(scene_state.scene_state(HOUR_BEFORE, CONFIG), dict(daylight=0))['satellites'], {})

    def test_every_line_fits_through_the_day_and_the_extremes(self):
        seen = set()
        for step in range(0, 24*60*2, 50):
            when = datetime(2026, 10, 2, tzinfo=IST)+timedelta(minutes=step)
            for beat in self.sat_beats(when):
                seen.add(beat['id'])
                self.check(beat, when)
        self.assertTrue({'sat-pass-iss', 'sat-next-iss', 'sat-fact-iss', 'sat-fact-hubble', 'sat-fact-tiangong'} <= seen, seen)
        base = state_at(HOUR_BEFORE)
        light = scene.lighting(base)
        for directions in ('NW', 'SW', 'SE', 'NE'):
            for hour, alt in (('23:59', 90.0), ('05:05', 10.0)):
                for lead in (timedelta(minutes=60), timedelta(hours=6), timedelta(hours=30)):
                    state = json.loads(json.dumps(base))
                    start = datetime.fromisoformat(state['timestamp_local'])+lead
                    start = start.replace(hour=int(hour[:2]), minute=int(hour[3:]))
                    for name, data in state['satellites'].items():
                        data['height_km'] = 8888
                        data['next_pass'] = dict(start=start.isoformat(), end=(start+timedelta(minutes=14)).isoformat(),
                                                 max=start.isoformat(), max_altitude_deg=alt, start_direction=directions,
                                                 end_direction=directions, track=[])
                    for beat in eligible(state, light):
                        if beat['id'].startswith('sat-'):
                            self.check(beat, (directions, hour, alt, lead))

    def test_a_pass_that_is_not_fresh_never_appears(self):
        state = json.loads(json.dumps(state_at(HOUR_BEFORE)))
        state['satellites']['ISS']['next_pass'] = None
        ids = {b['id'] for b in eligible(state)}
        self.assertTrue({'sat-fact-iss'} <= ids)
        self.assertFalse({'sat-pass-iss', 'sat-next-iss'} & ids)


def lit(when, tles=None, weather=None):
    return scene.lighting(scene_state.scene_state(when, CONFIG, weather, elements() if tles is None else tles))


def parse_values(markup, kind):
    """The SMIL values of the first animation of that type in a piece of markup, as lists of numbers."""
    node = re.search(rf'<animate{kind} attributeName="[a-z0-9]+"[^>]*? values="([^"]+)"', markup)
    return [[float(n) for n in v.split()] for v in node[1].split(';')]


class PassAnimation(unittest.TestCase):
    def test_a_pass_due_in_the_next_quarter_hour_is_drawn_with_its_real_time(self):
        light = lit(BEFORE)
        plan = light['pass']
        self.assertEqual((plan['name'], plan['label']), ('ISS', 'ISS 19:32'))
        self.assertIsNotNone(plan['label_at'])
        markup = scene.sat_pass(0, True, light)
        self.assertIn('data-sky="pass" data-pass="iss" mask="url(#sky-mask)"', markup)
        self.assertIn('data-pass-label="iss"', markup)
        d, width, height = scene.pixel_text('ISS 19:32', *plan['label_at'], cell=scene.PASS_LABEL_CELL)
        self.assertIn(f'<path d="{d}" fill="{scene.PASS_COLOURS["label"]}"/>', markup)   # the real pass time, in pixel text
        self.assertEqual(markup.count('<animateTransform'), 1)
        self.assertEqual(scene.sat_pass(0, True, light), scene.sat_pass(0, True, lit(BEFORE)))

    def test_only_the_part_of_the_track_in_view_is_drawn(self):
        light = lit(BEFORE)
        plan, track = light['pass'], light['satellites']['ISS']['next_pass']['track']
        run = scene.pass_view(track)
        self.assertEqual(plan['points'], run)
        in_view = [(alt, az) for _, alt, az in track if scene.in_view(alt, az)]
        self.assertTrue(3 <= len(run) <= len(in_view))
        self.assertLess(len(run), len(track))   # the pass starts in the south-west (behind us) and ends in the north: part is in front
        positions = {tuple(round(v, 1) for v in scene.sun_screen(alt, az)) for alt, az in in_view}
        self.assertTrue(set(run) <= positions)
        for x, y in run:
            self.assertTrue(0 <= x <= scene.W and 0 < y < scene.HORIZON_Y, (x, y))
        # the animated dot only ever takes those positions
        values = parse_values(scene.sat_pass(0, True, light), 'Transform')
        self.assertEqual({tuple(v) for v in values}, set(run))
        head, tail, fade, label = scene.pass_tracks(plan)
        for point in run:
            self.assertIn(point, set(head.values))
        self.assertEqual(scene.pass_view([(0, 30, 170), (10, 20, 180), (20, 15, 200)]), [])   # all south: behind the viewer

    def test_nothing_is_drawn_unless_a_pass_overlaps_the_next_fifteen_minutes(self):
        for when, drawn in ((BEFORE-timedelta(minutes=3), False), (BEFORE-timedelta(minutes=2), True), (BEFORE, True),
                            (DURING, True), (AFTER, False), (HOUR_BEFORE, False), (MORNING, False)):
            light = lit(when)
            self.assertEqual(light['pass'] is not None, drawn, when)
            self.assertEqual('data-pass=' in scene.sat_pass(0, True, light), drawn, when)
            self.assertEqual('data-sky="pass"' in scene.scene(0, True, state=scene_state.scene_state(when, CONFIG, None, elements())), drawn)

    def test_nothing_at_all_without_data_and_the_default_scene_is_untouched(self):
        light = scene.lighting(scene_state.scene_state(BEFORE, CONFIG))
        self.assertIsNone(light['pass'])
        self.assertEqual(scene.sat_pass(0, True, light), '')
        svg = scene.scene(0, True, state=scene_state.scene_state(BEFORE, CONFIG))
        for marker in ('data-pass', 'data-sky="pass"'):
            self.assertNotIn(marker, svg)
        assets = Path(__file__).resolve().parents[1]/'assets'
        self.assertEqual(scene.scene(animated=True), (assets/'observatory.svg').read_text())
        self.assertEqual(scene.scene(0, False), (assets/'poster.svg').read_text())

    def test_thick_cloud_hides_it(self):
        import test_storm
        light = lit(BEFORE, weather=test_storm.storm(BEFORE))
        self.assertGreater(light['overcast'], .3)
        self.assertIsNone(light['pass'])

    def test_it_never_flashes_and_the_still_frame_shows_nothing(self):
        light = lit(BEFORE)
        head, tail, fade, label = scene.pass_tracks(light['pass'])
        for track in (fade, label):
            self.assertEqual((track.at(0), track.at(scene.PERIOD)), (0, 0))   # nothing in the still PNG, a clean wrap
            self.assertEqual(track.values[0], track.values[-1])
            ups = sum(b > a for a, b in zip(track.values, track.values[1:]))
            downs = sum(b < a for a, b in zip(track.values, track.values[1:]))
            self.assertEqual((ups, downs), (1, 1))                           # one fade in and one fade out
            steepest = max(abs(b-a)/((k1-k0)*scene.PERIOD) for a, b, k0, k1
                           in zip(track.values, track.values[1:], track.key_times, track.key_times[1:]) if k1 > k0)
            self.assertLessEqual(steepest, 1/.25)                            # no change faster than a 0.25 s fade
        self.assertGreater(scene.PASS_AT, 0)
        self.assertLess(scene.PASS_AT+scene.PASS_SPAN+1, scene.PERIOD)
        still = scene.scene(0, False, state=scene_state.scene_state(BEFORE, CONFIG, None, elements()))
        self.assertIn('data-sky="pass"', still)
        shown = re.findall(r'data-pass="iss" mask="url\(#sky-mask\)"><g opacity="([^"]+)"', still)
        self.assertEqual(shown, ['0'])
        self.assertIn('data-pass-label="iss" opacity="0"', still)
        self.assertEqual(fade.at(scene.PASS_AT+scene.PASS_SPAN/2), 1)
        # the dot moves through the pass in order, never backwards in time
        self.assertEqual(list(head.key_times), sorted(head.key_times))

    def test_the_label_stays_clear_of_the_name_the_log_and_the_skyline(self):
        found = 0
        for when in (BEFORE, BEFORE+timedelta(minutes=10), DURING):
            plan = lit(when)['pass']
            if not plan or not plan['label_at']:
                continue
            found += 1
            x, y = plan['label_at']
            _, width, height = scene.pixel_text(plan['label'], x, y, cell=scene.PASS_LABEL_CELL)
            box = (x-2, y-2, x+width+2, y+height+2)
            for name in scene.RETICLE_AVOID:
                self.assertFalse(scene.overlaps(box, getattr(scene, name)), name)
            self.assertTrue(box[0] >= 0 and box[2] <= scene.W and box[1] >= 0 and box[3] <= scene.skyline_top(box[0], box[2]))
        self.assertGreater(found, 0)

    def test_the_label_search_gives_up_cleanly(self):
        self.assertIsNone(scene.pass_label_place('ISS 19:32', [(5, 600)]))   # a point behind the skyline: nowhere to stand
        self.assertIsNone(scene.pass_label_place('ISS 19:32', []))

    def test_render_live_reads_fresh_elements_and_ignores_stale_ones(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            sat.store(elements(), folder/'satellites', FETCHED)
            with mock.patch.object(scene, 'rasterize', test_render_daily.fake_rasterize):
                state = render_live.render(BEFORE, folder/'live', satellites_file=folder/'satellites'/'tle.json')
                self.assertEqual(sorted(state['satellites']), ['HUBBLE', 'ISS', 'TIANGONG'])
                written = json.loads((folder/'live'/'live.json').read_text())
                self.assertEqual(written['satellites']['ISS']['next_pass']['start'][11:16], '19:32')
                self.assertIn('data-sky="pass"', (folder/'live'/'live.svg').read_text())
                stale = render_live.render(BEFORE+timedelta(days=15), folder/'live',
                                           satellites_file=folder/'satellites'/'tle.json')
                self.assertIsNone(stale['satellites'])
                none = render_live.render(BEFORE, folder/'live')
                self.assertIsNone(none['satellites'])

    def test_the_daily_archive_uses_the_latest_elements_for_earlier_frames(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'tle.json'
            sat.store(elements(), path.parent, FETCHED)
            two_days_before = BEFORE-timedelta(days=2)
            self.assertIsNone(sat.load(path, two_days_before))   # live rendering would refuse these
            self.assertEqual(sorted(render_daily.elements_for(path, two_days_before)), [20580, 25544, 48274])
            self.assertIsNone(render_daily.elements_for(None, BEFORE))


class PassAnimations(unittest.TestCase):
    """The generic SMIL-vs-raster and loop checks on a night with a pass due, sampled through the dot's fades and
    crossing, the label's fades, and every change of page on the wall screen (now at 5, 10, 15 and 20 s)."""

    PASS_TIMES = [scene.PASS_AT-.4, scene.PASS_AT-.3, scene.PASS_AT-.1, scene.PASS_AT, scene.PASS_AT+.15,
                  scene.PASS_AT+.3, scene.PASS_AT+1.7, scene.PASS_AT+scene.PASS_SPAN/2, scene.PASS_AT+scene.PASS_SPAN-.45,
                  scene.PASS_AT+scene.PASS_SPAN-.3, scene.PASS_AT+scene.PASS_SPAN-.1, scene.PASS_AT+scene.PASS_SPAN,
                  scene.PASS_AT+scene.PASS_SPAN+.3, scene.PASS_AT+scene.PASS_SPAN+.6, scene.PASS_AT+scene.PASS_SPAN+.75,
                  scene.PASS_AT+scene.PASS_SPAN+.9]
    SCREEN_TIMES = [4.9, 5.1, 9.9, 10.1, 14.9, 15.1, 15.3, 19.9, 20.1, 23.8, 23.95]

    def test_the_night_of_the_pass(self):
        light = lit(BEFORE)
        self.assertIsNotNone(light['pass'])
        original = scene.layers
        times = sorted(set(test_scene.CHECK_TIMES+self.PASS_TIMES+self.SCREEN_TIMES))
        with mock.patch.object(scene, 'layers', lambda t, animated, _=None: original(t, animated, light)), \
                mock.patch.object(scene, 'ROUTES', scene.flying_routes(light['day']['airliner'], light)), \
                mock.patch.object(test_scene, 'CHECK_TIMES', times), \
                mock.patch.object(test_scene, 'LINEAR', 1e-3), mock.patch.object(test_scene, 'PX', .05):
            # The starships' warp-flash scale keyframes print three decimals, so between keyframes the raster and the
            # SMIL scale differ by up to 3e-4 (0.04 px). The default check times never land there; these do.
            test_daily.run(test_daily.GENERIC[:2])


if __name__ == '__main__':
    unittest.main()
