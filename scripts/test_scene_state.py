import math
import unittest
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import astronomy as ae
import scene_state as ss

IST = ZoneInfo('Asia/Kolkata')
CFG = ss.load_config()
LAT, LON = CFG['location']['latitude'], CFG['location']['longitude']
SEASON_ORDER = [s['id'] for s in CFG['seasons']]


def days(start, end):
    d = start
    while d <= end:
        yield d
        d += timedelta(days=1)


# --- independent reference implementations (stdlib only) -------------------------------------

def noaa_sun(jd):
    """NOAA simplified solar position: returns (declination_deg, equation_of_time_min)."""
    t = (jd - 2451545.0) / 36525
    l0 = (280.46646 + t * (36000.76983 + t * 0.0003032)) % 360
    m = 357.52911 + t * (35999.05029 - 0.0001537 * t)
    e = 0.016708634 - t * (0.000042037 + 0.0000001267 * t)
    mr = math.radians(m)
    c = (math.sin(mr) * (1.914602 - t * (0.004817 + 0.000014 * t))
         + math.sin(2 * mr) * (0.019993 - 0.000101 * t) + math.sin(3 * mr) * 0.000289)
    true_long = l0 + c
    omega = 125.04 - 1934.136 * t
    app = true_long - 0.00569 - 0.00478 * math.sin(math.radians(omega))
    eps0 = 23 + (26 + (21.448 - t * (46.815 + t * (0.00059 - t * 0.001813))) / 60) / 60
    eps = eps0 + 0.00256 * math.cos(math.radians(omega))
    dec = math.degrees(math.asin(math.sin(math.radians(eps)) * math.sin(math.radians(app))))
    y = math.tan(math.radians(eps / 2)) ** 2
    l0r = math.radians(l0)
    eqt = 4 * math.degrees(y * math.sin(2 * l0r) - 2 * e * math.sin(mr) + 4 * e * y * math.sin(mr) * math.cos(2 * l0r)
                           - 0.5 * y * y * math.sin(4 * l0r) - 1.25 * e * e * math.sin(2 * mr))
    return dec, eqt


def julian_day(dt_utc):
    return dt_utc.timestamp() / 86400 + 2440587.5


def noaa_altitude(dt_utc):
    dec, eqt = noaa_sun(julian_day(dt_utc))
    minutes = dt_utc.hour * 60 + dt_utc.minute + dt_utc.second / 60
    ha = math.radians((minutes + eqt + 4 * LON) / 4 - 180)
    lat, d = math.radians(LAT), math.radians(dec)
    return math.degrees(math.asin(math.sin(lat) * math.sin(d) + math.cos(lat) * math.cos(d) * math.cos(ha)))


def noaa_rise_set(d):
    """Local sunrise/sunset in minutes after local midnight (IST, +5:30) for a date."""
    noon_utc = datetime(d.year, d.month, d.day, 6, 30, tzinfo=timezone.utc)  # local noon, IST
    dec, eqt = noaa_sun(julian_day(noon_utc))
    lat, dr = math.radians(LAT), math.radians(dec)
    ha = math.degrees(math.acos(math.cos(math.radians(90.833)) / (math.cos(lat) * math.cos(dr)) - math.tan(lat) * math.tan(dr)))
    solar_noon = 720 - 4 * LON - eqt + 330
    return solar_noon - 4 * ha, solar_noon + 4 * ha


def minutes_of(iso):
    dt = datetime.fromisoformat(iso)
    return dt.hour * 60 + dt.minute + dt.second / 60


def mean_phase(dt_utc):
    """Fraction of the synodic month since the 2000-01-06 18:14 UTC new moon."""
    ref = datetime(2000, 1, 6, 18, 14, tzinfo=timezone.utc)
    return ((dt_utc - ref).total_seconds() / 86400 / 29.530588853) % 1


def mean_illum(phase):
    return (1 - math.cos(2 * math.pi * phase)) / 2


class SeasonTests(unittest.TestCase):
    def test_every_day_has_exactly_one_season(self):
        starts = {tuple(map(int, s['start'].split('-'))): s['id'] for s in CFG['seasons']}
        for d in days(date(2026, 1, 1), date(2028, 12, 31)):
            got = ss.season_for(d, CFG)
            self.assertIn(got['id'], SEASON_ORDER)
            expected = max((k for k in starts if k <= (d.month, d.day)), default=max(starts))
            self.assertEqual(got['id'], starts[expected], d)
            self.assertTrue(0 <= got['fraction'] < 1)

    def test_boundary_days(self):
        for s in CFG['seasons']:
            m, dd = map(int, s['start'].split('-'))
            for y in (2026, 2027, 2028):
                first = ss.season_for(date(y, m, dd), CFG)
                self.assertEqual((first['id'], first['day_index_in_season']), (s['id'], 0))
                prev = ss.season_for(date(y, m, dd) - timedelta(days=1), CFG)
                self.assertNotEqual(prev['id'], s['id'])

    def test_wraps_december_to_february(self):
        self.assertEqual(ss.season_for(date(2026, 12, 21), CFG)['id'], 'hemanta')
        for d in (date(2026, 12, 22), date(2026, 12, 31), date(2027, 1, 1), date(2027, 2, 18)):
            self.assertEqual(ss.season_for(d, CFG)['id'], 'shishira', d)
        self.assertEqual(ss.season_for(date(2027, 2, 19), CFG)['id'], 'vasanta')
        self.assertEqual(ss.season_for(date(2027, 1, 1), CFG)['day_index_in_season'], 10)

    def test_leap_day(self):
        got = ss.season_for(date(2028, 2, 29), CFG)
        self.assertEqual((got['id'], got['day_index_in_season']), ('vasanta', 10))
        self.assertEqual(ss.season_for(date(2028, 2, 18), CFG)['id'], 'shishira')


class EnvironmentTests(unittest.TestCase):
    def test_range_and_day_to_day_continuity(self):
        prev = None
        for d in days(date(2026, 10, 1), date(2027, 10, 1)):
            env = ss.environment_for(d, CFG)
            self.assertEqual(set(env), set(ss.PARAMS))
            for k, v in env.items():
                self.assertTrue(0 <= v <= 1, (d, k, v))
                if prev:
                    self.assertLessEqual(abs(v - prev[k]), 0.03, (d, k))
            prev = env

    def test_continuity_across_leap_year_and_year_end(self):
        prev = None
        for d in days(date(2027, 12, 1), date(2028, 3, 15)):
            env = ss.environment_for(d, CFG)
            if prev:
                self.assertTrue(all(abs(env[k] - prev[k]) <= 0.03 for k in env), d)
            prev = env

    def test_seasonal_character(self):
        varsha = ss.environment_for(date(2027, 7, 22), CFG)    # centre of varsha
        shishira = ss.environment_for(date(2027, 1, 20), CFG)  # centre of shishira
        grishma = ss.environment_for(date(2027, 5, 21), CFG)
        self.assertGreater(varsha['cloud_density'], shishira['cloud_density'])
        self.assertGreater(varsha['ground_wetness'], max(shishira['ground_wetness'], grishma['ground_wetness']))
        self.assertGreater(grishma['haze'], max(varsha['haze'], shishira['haze']))
        centres = [date(2027, 3, 20), date(2027, 5, 21), date(2027, 7, 22), date(2027, 9, 22),
                   date(2026, 11, 22), date(2027, 1, 20)]
        best = max(centres, key=lambda d: ss.environment_for(d, CFG)['night_visibility'])
        self.assertEqual(ss.season_for(best, CFG)['id'], 'shishira')
        worst = min(centres, key=lambda d: ss.environment_for(d, CFG)['night_visibility'])
        self.assertEqual(ss.season_for(worst, CFG)['id'], 'varsha')


class TimeAndSeedTests(unittest.TestCase):
    def test_utc_to_kolkata(self):
        s = ss.scene_state(datetime(2026, 12, 14, 16, 7, tzinfo=timezone.utc), CFG)
        self.assertEqual((s['date'], s['time']), ('2026-12-14', '21:37:00'))
        self.assertEqual(s['timestamp_local'], '2026-12-14T21:37:00+05:30')
        self.assertEqual(s['timestamp_utc'], '2026-12-14T16:07:00Z')
        self.assertEqual(s['timezone'], 'Asia/Kolkata')

    def test_naive_datetime_rejected(self):
        with self.assertRaises(ValueError):
            ss.scene_state(datetime(2026, 12, 14, 21, 37), CFG)

    def test_deterministic(self):
        when = datetime(2027, 3, 3, 3, 3, tzinfo=IST)
        self.assertEqual(ss.scene_state(when, CFG), ss.scene_state(when, CFG))
        self.assertEqual(ss.scene_state(when, CFG), ss.scene_state(when.astimezone(timezone.utc), CFG))

    def test_seed_depends_only_on_local_date(self):
        a = ss.scene_state(datetime(2026, 12, 14, 0, 30, tzinfo=IST), CFG)
        b = ss.scene_state(datetime(2026, 12, 14, 23, 59, tzinfo=IST), CFG)
        c = ss.scene_state(datetime(2026, 12, 15, 0, 1, tzinfo=IST), CFG)
        self.assertEqual((a['seed'], a['seed_int']), (b['seed'], b['seed_int']))
        self.assertNotEqual(b['seed'], c['seed'])
        # 23:59 IST and 00:01 IST next day fall on the same UTC date
        self.assertEqual(datetime(2026, 12, 14, 23, 59, tzinfo=IST).astimezone(timezone.utc).date(),
                         datetime(2026, 12, 15, 0, 1, tzinfo=IST).astimezone(timezone.utc).date())
        self.assertEqual(len(a['seed']), 64)
        self.assertEqual(a['seed_int'], int(a['seed'][:16], 16))

    def test_output_shape(self):
        s = ss.scene_state(datetime(2026, 12, 14, 21, 37, tzinfo=IST), CFG)
        self.assertEqual(set(s), {'date', 'time', 'timezone', 'timestamp_local', 'timestamp_utc', 'season', 'environment',
                                  'astronomy', 'lighting', 'seed', 'seed_int', 'renderer_version'})
        self.assertEqual(s['renderer_version'], CFG['renderer_version'])


class AstronomyTests(unittest.TestCase):
    DATES = [date(2026, 10, 1), date(2026, 12, 21), date(2027, 2, 14), date(2027, 4, 20), date(2027, 6, 21),
             date(2027, 8, 10), date(2027, 9, 23)]

    def test_sunrise_sunset_against_noaa(self):
        for d in self.DATES:
            st = ss.scene_state(datetime(d.year, d.month, d.day, 12, tzinfo=IST), CFG)['astronomy']['sun_times']
            rise, set_ = noaa_rise_set(d)
            self.assertAlmostEqual(minutes_of(st['sunrise']), rise, delta=3, msg=f'sunrise {d}')
            self.assertAlmostEqual(minutes_of(st['sunset']), set_, delta=3, msg=f'sunset {d}')

    def test_sun_altitude_against_noaa(self):
        for dt in (datetime(2026, 10, 1, 6, 0, tzinfo=IST), datetime(2026, 12, 14, 21, 37, tzinfo=IST),
                   datetime(2027, 3, 21, 12, 0, tzinfo=IST), datetime(2027, 7, 15, 13, 0, tzinfo=IST),
                   datetime(2027, 7, 15, 17, 30, tzinfo=IST), datetime(2027, 1, 5, 7, 30, tzinfo=IST)):
            got = ss.scene_state(dt, CFG)['astronomy']['sun']['altitude_deg']
            self.assertAlmostEqual(got, noaa_altitude(dt.astimezone(timezone.utc)), delta=0.5, msg=str(dt))

    def test_twilight_ordering(self):
        for d in self.DATES:
            a = ss.scene_state(datetime(d.year, d.month, d.day, 12, tzinfo=IST), CFG)['astronomy']
            t = a['sun_times']
            order = [t['civil_dawn'], t['sunrise'], t['sunset'], t['civil_dusk']]
            self.assertEqual(order, sorted(order), d)
            self.assertEqual(len(set(order)), 4)

    def test_twilight_labels_by_altitude(self):
        for alt, label in ((-30, 'night'), (-18.1, 'night'), (-18, 'astronomical'), (-12.1, 'astronomical'),
                           (-12, 'nautical'), (-6.1, 'nautical'), (-6, 'civil'), (-0.9, 'civil'),
                           (-0.833, 'day'), (45, 'day')):
            self.assertEqual(ss.twilight_label(alt), label, alt)
        # real instants around one sunset: day -> civil -> nautical -> astronomical -> night
        labels = [ss.scene_state(datetime(2027, 1, 5, 17, 40, tzinfo=IST) + timedelta(minutes=m), CFG)['astronomy']['twilight']
                  for m in range(0, 140, 10)]
        self.assertEqual(labels[0], 'day')
        self.assertEqual(labels[-1], 'night')
        self.assertEqual([k for k, _ in zip(dict.fromkeys(labels), range(5))],
                         ['day', 'civil', 'nautical', 'astronomical', 'night'])

    def test_sidereal_time_range_and_rate(self):
        a = ss.scene_state(datetime(2027, 3, 1, 22, 0, tzinfo=IST), CFG)['astronomy']['local_sidereal_time_hours']
        b = ss.scene_state(datetime(2027, 3, 2, 22, 0, tzinfo=IST), CFG)['astronomy']['local_sidereal_time_hours']
        self.assertTrue(0 <= a < 24 and 0 <= b < 24)
        self.assertAlmostEqual((b - a) % 24, 24 / 365.2422 * 1, delta=0.01)  # a solar day gains ~3.94 min


class MoonTests(unittest.TestCase):
    def test_phase_against_mean_synodic_model(self):
        start = datetime(2026, 10, 1, 18, 0, tzinfo=timezone.utc)
        for k in range(0, 60 * 4):  # every 6 hours for 60 days
            when = start + timedelta(hours=6 * k)
            moon = ss.scene_state(when, CFG)['astronomy']['moon']
            near = [mean_phase(when + timedelta(days=x / 4)) for x in range(-6, 7)]  # +-1.5 days
            lo, hi = (mean_illum(p) for p in (min(near, key=mean_illum), max(near, key=mean_illum)))
            self.assertTrue(lo - 0.02 <= moon['illuminated_fraction'] <= hi + 0.02, when)
            p = mean_phase(when)
            edge = min(abs(((p - q + 0.5) % 1) - 0.5) for q in (0, 0.5)) * 29.530588853  # days to new/full
            if edge > 1.5:
                self.assertEqual(moon['waxing'], p < 0.5, when)

    def test_full_moon_is_bright(self):
        t = ae.SearchMoonPhase(180, ae.Time.Make(2026, 10, 1, 0, 0, 0), 40)
        when = t.Utc().replace(tzinfo=timezone.utc)
        moon = ss.scene_state(when, CFG)['astronomy']['moon']
        self.assertGreater(moon['illuminated_fraction'], 0.97)
        self.assertLess(moon['phase_angle_deg'], 5)

    def test_new_moon_is_dark_and_flag_flips(self):
        t = ae.SearchMoonPhase(0, ae.Time.Make(2026, 10, 1, 0, 0, 0), 40)
        when = t.Utc().replace(tzinfo=timezone.utc)
        self.assertLess(ss.scene_state(when, CFG)['astronomy']['moon']['illuminated_fraction'], 0.03)
        self.assertFalse(ss.scene_state(when - timedelta(days=3), CFG)['astronomy']['moon']['waxing'])
        self.assertTrue(ss.scene_state(when + timedelta(days=3), CFG)['astronomy']['moon']['waxing'])


class DaylightTests(unittest.TestCase):
    def test_endpoints_and_monotonic(self):
        self.assertEqual(ss.daylight(-12), 0)
        self.assertEqual(ss.daylight(-40), 0)
        self.assertEqual(ss.daylight(10), 1)
        self.assertEqual(ss.daylight(90), 1)
        values = [ss.daylight(-30 + i * 0.25) for i in range(0, 4 * 125)]
        self.assertTrue(all(b >= a for a, b in zip(values, values[1:])))
        self.assertTrue(all(0 <= v <= 1 for v in values))
        self.assertAlmostEqual(ss.daylight(-1), 0.5, delta=0.1)

    def test_scene_state_daylight_follows_sun(self):
        noon = ss.scene_state(datetime(2027, 3, 21, 12, tzinfo=IST), CFG)
        night = ss.scene_state(datetime(2027, 3, 21, 0, 30, tzinfo=IST), CFG)
        self.assertEqual(noon['lighting']['daylight'], 1.0)
        self.assertEqual(night['lighting']['daylight'], 0.0)
        # smooth: sample every minute across dawn, no step larger than 0.02
        vals = [ss.scene_state(datetime(2027, 3, 21, 6, 0, tzinfo=IST) + timedelta(minutes=m), CFG)['lighting']['daylight']
                for m in range(0, 60, 2)]
        self.assertTrue(all(abs(b - a) < 0.1 for a, b in zip(vals, vals[1:])))


if __name__ == '__main__':
    unittest.main()
