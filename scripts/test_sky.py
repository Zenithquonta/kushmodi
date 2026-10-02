"""Phase 17: the real night sky. The catalogue conversion, the north-facing dome (west left, east right, nothing behind
the viewer), where real stars land, the telescope's lock-on on a real object, the trails behind the planets and the
Moon, and the generic SMIL-versus-raster and loop checks on a live night state. No test here uses the network."""
from datetime import datetime, timedelta, timezone
import json
import math
from pathlib import Path
import re
import unittest
from unittest import mock
from zoneinfo import ZoneInfo

import astronomy as ae

import build_animation as scene
import night_sky
import scene_state
import sky_catalog
import story
import test_daily
import test_scene
from test_storm import clear, storm

IST = ZoneInfo('Asia/Kolkata')
NIGHT = datetime(2026, 10, 4, 23, 30, tzinfo=IST)         # clear night: no planet or Moon in the northern sky
PLANET_NIGHT = datetime(2026, 10, 31, 4, 0, tzinfo=IST)   # Mars and Jupiter rise in the north-east before dawn
MOON_NIGHT = datetime(2026, 10, 26, 22, 0, tzinfo=IST)    # the full Moon is in the front half of the sky
DUSK = datetime(2026, 10, 4, 18, 45, tzinfo=IST)
NOON = datetime(2026, 10, 4, 12, 0, tzinfo=IST)
ASSETS = Path(__file__).resolve().parents[1]/'assets'
MUMBAI = (19.076, 72.8777, 14)
W, HORIZON_Y = scene.W, scene.HORIZON_Y


def live(when, observed=True):
    return scene_state.scene_state(when, None, clear(when) if observed else None)


def lock_parts(plan, t):
    """{part name: [(bbox, opacity)]} of every leaf of the lock-on drawn for ``plan`` in the static frame at t."""
    root = test_scene.ET.fromstring(test_scene.WRAP.format(scene.lock_on(t, False, plan)))
    return {g.attrib['data-lock']: [(test_scene.leaf_bbox(l), l[3]) for l in test_scene.flatten(g) if test_scene.leaf_bbox(l)]
            for g in root}


def hr_star(layout, hr):
    return next(s for s in layout['stars'] if s['hr'] == hr)


def expected_position(ra_deg, dec_deg, when):
    """Where astronomy-engine puts a J2000 position at ``when`` over Mumbai on the north-facing dome (independent of
    night_sky's own transform)."""
    utc = when.astimezone(timezone.utc)
    t = ae.Time.Make(utc.year, utc.month, utc.day, utc.hour, utc.minute, utc.second)
    r, d = math.radians(ra_deg), math.radians(dec_deg)
    vector = ae.RotateVector(ae.Rotation_EQJ_EQD(t), ae.Vector(math.cos(d)*math.cos(r), math.cos(d)*math.sin(r), math.sin(d), t))
    eq = ae.EquatorFromVector(vector)
    h = ae.Horizon(t, ae.Observer(*MUMBAI), eq.ra, eq.dec, ae.Refraction.Airless)
    x = W/2+math.sin(math.radians(h.azimuth))*math.cos(math.radians(h.altitude))*W/2
    return h.altitude, h.azimuth, x, HORIZON_Y-h.altitude/90*(HORIZON_Y-40)


class Catalogue(unittest.TestCase):
    BSC = [{'HR': '7001', 'V': '0.03', 'K': '10000', 'RA': '18h 36m 56.3s', 'Dec': '+38° 47′ 01″', 'N': 'Vega'},
           {'HR': '2491', 'V': '-1.46', 'K': '9750', 'RA': '06h 45m 08.9s', 'Dec': '-16° 42′ 58″', 'N': 'Sirius'},
           {'HR': '1', 'V': '6.70', 'K': '9750', 'RA': '00h 05m 09.9s', 'Dec': '+45° 13′ 45″'},          # too faint
           {'HR': '5', 'V': '4.50', 'RA': '00h 00m 00.0s', 'Dec': '-00° 30′ 00″'},                         # no temperature
           {'HR': '9', 'V': '3.20', 'K': '5000', 'RA': '12h 00m 00s', 'Dec': '+10° 00′ 00″', 'N': 'Café'}]   # unsafe name

    def test_conversion_of_a_small_sample(self):
        data = sky_catalog.convert_stars(self.BSC)
        self.assertEqual([row[4] for row in data['stars']], [2491, 7001, 9, 5])   # brightest first, the faint one gone
        self.assertEqual(data['stars'][1], [279.235, 38.784, .03, 10000, 7001])   # 18h36m56.3s = 279.2346 deg
        self.assertEqual(data['stars'][0][:2], [101.287, -16.716])                # a negative declination
        self.assertEqual(data['stars'][3][1:4], [-.5, 4.5, 0])                    # -00 deg 30': the sign survives a zero degree
        self.assertEqual(data['names'], {'2491': 'Sirius', '7001': 'Vega'})       # only plain names
        self.assertEqual(sky_catalog.convert_stars(self.BSC), data)               # reproducible
        self.assertEqual(sky_catalog.dump(data), sky_catalog.dump(sky_catalog.convert_stars(list(self.BSC))))

    def test_milky_way_conversion_thins_and_wraps(self):
        ring = [[0.0 + i*.05, 10.0] for i in range(200)] + [[-.3, 20.0], [-.3, 15.0]]
        geo = {'features': [{'id': 'ol2', 'geometry': {'coordinates': [[ring + [ring[0]], [[1, 1], [1.01, 1], [1.02, 1.01]]]]}},
                            {'id': 'ol1', 'geometry': {'coordinates': [[ring]]}}]}
        data = sky_catalog.convert_milkyway(geo)
        self.assertEqual(len(data['levels']), 2)
        outer = data['levels'][0]   # ol1 sorts first
        self.assertEqual(len(outer), 1)
        self.assertLess(len(outer[0]), 40)                    # 200 points 0.05 degrees apart thin to about 0.45 degrees
        self.assertTrue(all(0 <= lon < 360 for lon, _ in outer[0]))
        self.assertIn([359.7, 20.0], outer[0])                # -0.3 degrees wraps to 359.7
        self.assertEqual(len(data['levels'][1]), 1)           # the tiny ring thins away and is dropped
        self.assertEqual(sky_catalog.convert_milkyway(geo), data)

    def test_constellation_conversion(self):
        geo = {'features': [{'id': 'Lyr', 'geometry': {'coordinates': [[[-5.4658, 43.2681], [10.5, 20]], [[3, 4], [5, 6]]]}}]}
        self.assertEqual(sky_catalog.convert_constellations(geo),
                         {'epoch': 'J2000', 'lines': [[[354.534, 43.268], [10.5, 20]], [[3, 4], [5, 6]]]})

    def test_the_committed_files_hold_the_real_catalogue(self):
        stars = json.loads((ASSETS/'sky'/'stars.json').read_text())
        by_hr = {row[4]: row for row in stars['stars']}
        self.assertEqual(stars['columns'], ['ra_deg', 'dec_deg', 'v_mag', 'kelvin', 'hr'])
        self.assertEqual(by_hr[7001][:4], [279.235, 38.784, .03, 10000])                 # Vega
        self.assertAlmostEqual(by_hr[424][1], 89.264, delta=.001)                        # Polaris
        self.assertEqual(stars['names']['2491'], 'Sirius')
        self.assertEqual([row[2] for row in stars['stars']], sorted(row[2] for row in stars['stars']))
        self.assertTrue(1500 < len(stars['stars']) < 1700 and max(row[2] for row in stars['stars']) <= 5.0)
        self.assertEqual(len(json.loads((ASSETS/'sky'/'milkyway.json').read_text())['levels']), 5)
        self.assertGreater(len(json.loads((ASSETS/'sky'/'constellations.json').read_text())['lines']), 100)
        sources = (ASSETS/'sky'/'SOURCES.md').read_text()
        for needle in ('Yale Bright Star Catalogue', 'Olaf Frohn', 'BSD 3-Clause', 'Redistribution and use in source and binary'):
            self.assertIn(needle, sources)
        for name in ('stars.json', 'milkyway.json', 'constellations.json'):
            self.assertLess((ASSETS/'sky'/name).stat().st_size, 120_000, name)

    def test_the_milky_way_outlines_follow_the_galactic_plane(self):
        """Even-odd across the five outlines: the Galactic centre is inside the band, the north galactic pole and the
        south galactic pole (the reference outside point) are not."""
        def depth(ra, dec):
            point = night_sky._unit(ra, dec)
            return sum(night_sky.contains(ring, point, night_sky.GALACTIC_SOUTH) for ring in night_sky.milky_way()[0])
        self.assertEqual(depth(266.4, -28.9) % 2, 1)
        self.assertEqual(depth(192.86, 27.13) % 2, 0)
        self.assertEqual(depth(12.86, -27.13) % 2, 0)


class Dome(unittest.TestCase):
    def test_the_dome_faces_north_with_west_left_and_east_right(self):
        self.assertEqual(scene.FACING, 0)
        self.assertAlmostEqual(scene.sun_screen(0, 270)[0], 0)           # west: the left edge
        self.assertAlmostEqual(scene.sun_screen(0, 0)[0], W/2)           # north: the centre
        self.assertAlmostEqual(scene.sun_screen(0, 90)[0], W)            # east: the right edge
        self.assertAlmostEqual(scene.sun_screen(0, 0)[1], HORIZON_Y)
        x, y = scene.sun_screen(90, 123)
        self.assertAlmostEqual(x, W/2)
        self.assertAlmostEqual(y, 40)                                    # the zenith: top centre
        self.assertLess(scene.sun_screen(30, 315)[0], W/2)
        self.assertGreater(scene.sun_screen(30, 45)[0], W/2)
        self.assertAlmostEqual(scene.sun_screen(0, 180, facing=180)[0], W/2)   # a south-facing viewer still works
        self.assertAlmostEqual(scene.sun_screen(0, 90, facing=180)[0], 0)

    def test_nothing_behind_the_viewer_is_in_view_however_high(self):
        for altitude in (0, 30, 60, 75, 89):
            self.assertFalse(scene.in_view(altitude, 180), altitude)
            self.assertFalse(scene.in_view(altitude, 120), altitude)
            self.assertFalse(scene.in_view(altitude, 240), altitude)
            self.assertTrue(scene.in_view(altitude, 0), altitude)
            self.assertTrue(scene.in_view(altitude, 60), altitude)
        self.assertTrue(scene.in_view(10, 90) and scene.in_view(10, 270))   # the edges themselves are in
        self.assertFalse(scene.in_view(10, 91))
        self.assertTrue(scene.in_view(80, 180, facing=180))

    def test_sunrise_is_on_the_right_and_sunset_on_the_left(self):
        for day in (datetime(2027, 5, 5, tzinfo=IST), datetime(2027, 6, 21, tzinfo=IST)):   # the sun rises north of east
            times = live(day.replace(hour=12), False)['astronomy']['sun_times']
            rise, set_ = (scene_state.scene_state(datetime.fromisoformat(times[k]), None, None) for k in ('sunrise', 'sunset'))
            for state, side in ((rise, 1), (set_, -1)):
                sun = state['astronomy']['sun']
                light = scene.lighting(state)
                x = scene.sun_screen(sun['altitude_deg'], sun['azimuth_deg'])[0]
                self.assertGreater((x-W/2)*side, W*.3, (day, side))
                self.assertGreater((light['glow_x']-W/2)*side, W*.3, (day, side))   # the sunrise/sunset glow follows
        winter = scene_state.scene_state(datetime(2026, 12, 21, 7, 30, tzinfo=IST))   # the winter sun rises south of east
        self.assertFalse(scene.in_view(winter['astronomy']['sun']['altitude_deg'], winter['astronomy']['sun']['azimuth_deg']))
        self.assertIsNone(scene.lighting(winter)['sun'])


class RealStars(unittest.TestCase):
    def layout(self, when, facing=0):
        utc = when.astimezone(timezone.utc).isoformat().replace('+00:00', 'Z')
        return night_sky.layout(utc, MUMBAI[0], MUMBAI[1], scene.DOME._replace(facing=facing))

    def test_polaris_sits_near_the_centre_at_about_the_latitude(self):
        for when in (NIGHT, PLANET_NIGHT, MOON_NIGHT):
            polaris = hr_star(self.layout(when), 424)
            self.assertAlmostEqual(polaris['alt'], 19.076, delta=1.3, msg=when)             # latitude +- its circle round the pole
            self.assertLess(abs(polaris['x']-W/2), 40, when)
            self.assertAlmostEqual(polaris['y'], HORIZON_Y-polaris['alt']/90*(HORIZON_Y-40), places=6)
        self.assertGreater(hr_star(self.layout(NIGHT), 424)['y'], 530)                      # low in the sky: about y 550

    def test_real_stars_land_where_the_ephemeris_puts_them(self):
        stars = {row[4]: row for row in json.loads((ASSETS/'sky'/'stars.json').read_text())['stars']}
        for when in (NIGHT, PLANET_NIGHT):
            layout = self.layout(when)
            for hr, name in ((7001, 'Vega'), (7924, 'Deneb'), (1708, 'Capella'), (4301, 'Dubhe'), (4295, 'Merak'), (424, 'Polaris'),
                             (168, 'Schedar'), (1017, 'Mirfak'), (2491, 'Sirius'), (5340, 'Arcturus')):
                alt, az, x, y = expected_position(stars[hr][0], stars[hr][1], when)
                shown = [s for s in layout['stars'] if s['hr'] == hr]
                if shown:
                    self.assertAlmostEqual(shown[0]['x'], x, delta=.05, msg=(when, name))
                    self.assertAlmostEqual(shown[0]['y'], y, delta=.05, msg=(when, name))
                    self.assertAlmostEqual(shown[0]['alt'], alt, delta=.001, msg=(when, name))
                else:   # behind the viewer or below the horizon
                    self.assertTrue(alt < night_sky.HORIZON_FLOOR or not scene.in_view(alt, az), (when, name, alt, az))
        # a known evening: Vega in the north-west (left of centre), Capella rising in the north-east (right of centre)
        layout = self.layout(NIGHT)
        vega, capella = hr_star(layout, 7001), hr_star(layout, 1708)
        self.assertAlmostEqual(vega['alt'], 21.86, delta=.05)
        self.assertLess(vega['x'], W/2-500)
        self.assertAlmostEqual(capella['alt'], 18.1, delta=.2)
        self.assertGreater(capella['x'], W/2+400)

    def test_west_is_left_east_is_right_and_nothing_is_behind(self):
        for when in (NIGHT, PLANET_NIGHT, MOON_NIGHT, datetime(2027, 3, 1, 21, 0, tzinfo=IST)):
            layout = self.layout(when)
            stars = {row[4]: row for row in json.loads((ASSETS/'sky'/'stars.json').read_text())['stars']}
            self.assertGreater(len(layout['stars']), 150, when)
            for s in layout['stars']:
                alt, az, x, _ = expected_position(stars[s['hr']][0], stars[s['hr']][1], when)
                self.assertTrue(scene.in_view(alt, az), (when, s['hr'], az))                     # the front half only
                self.assertTrue(0 <= s['x'] <= W and 40-1e-6 <= s['y'] <= HORIZON_Y+1.5*7.2+20, (when, s))
                self.assertEqual(s['x'] > W/2, math.sin(math.radians(az)) > 0, (when, s['hr'], az))   # east right, west left
                self.assertGreater(s['alt'], night_sky.HORIZON_FLOOR-1e-9)

    def test_the_milky_way_and_the_lines_stay_on_the_dome(self):
        for when in (NIGHT, MOON_NIGHT):
            layout = self.layout(when)
            self.assertEqual(len(layout['milky_way']), 5)
            self.assertTrue(layout['milky_way'][0] and layout['lines'])
            for d in layout['milky_way']+[layout['lines']]:
                for x, y in re.findall(r'(-?[\d.]+) (-?[\d.]+)', d):
                    x, y = float(x), float(y)
                    self.assertTrue(-1 <= x <= W+1 and 39 <= y, (when, x, y))
                    # inside the dome: no point is farther sideways than the edge circle allows at its altitude
                    alt = (HORIZON_Y-y)/(HORIZON_Y-40)*90
                    self.assertLessEqual(abs(x-W/2), W/2*math.cos(math.radians(max(alt, 0)))+1.5 if alt >= 0 else W/2+1.5, (when, x, y))

    def test_the_layout_is_cached_per_moment(self):
        a = self.layout(NIGHT)
        self.assertIs(self.layout(NIGHT), a)
        self.assertIsNot(self.layout(NIGHT+timedelta(minutes=15)), a)

    def test_clipping_keeps_the_inside_of_a_ring(self):
        def circle(radius, centre=(0.0, 1.0, 0.0), count=72):
            """A small circle of ``radius`` degrees about ``centre`` (a unit vector in the viewer frame)."""
            cx, cy, cz = centre
            a = (1.0, 0.0, 0.0) if abs(cx) < .9 else (0.0, 0.0, 1.0)
            u = night_sky._norm(night_sky._cross3(centre, a))
            v = night_sky._cross3(centre, u)
            r = math.radians(radius)
            return [tuple(math.cos(r)*c+math.sin(r)*(math.cos(t)*uu+math.sin(t)*vv) for c, uu, vv in zip(centre, u, v))
                    for t in (2*math.pi*i/count for i in range(count))]
        behind = (0.0, -1.0, 0.0)
        whole = circle(60)                                           # wholly in front: untouched
        self.assertEqual(night_sky.clip_ring(whole, behind), whole)
        self.assertEqual(night_sky.clip_ring(circle(30, behind), (0.0, 0.0, -1.0)), [])   # wholly behind, its inside holds only the back
        full = night_sky.clip_ring(circle(100), behind)              # wholly behind, but its inside is the whole front
        self.assertGreater(len(full), 60)
        self.assertTrue(all(abs(p[1]) < 1e-9 for p in full))         # the whole edge of the dome
        tilted = night_sky._norm((0.0, .3, 1.0))
        cut = night_sky.clip_ring(circle(60, tilted), behind)        # straddles the edge: cut exactly there
        self.assertTrue(cut and all(p[1] >= -1e-9 for p in cut))
        self.assertTrue(any(abs(p[1]) < 1e-9 for p in cut))
        self.assertTrue(all(abs(math.sqrt(sum(c*c for c in p))-1) < 1e-9 for p in cut))
        inside_arc = [p for p in cut if abs(p[1]) < 1e-9]            # the closing arc runs through the circle's inside
        mid = night_sky._norm(tuple(sum(p[k] for p in inside_arc) for k in range(3)))
        self.assertLess(night_sky._angle(mid, tilted), 60)
        runs = night_sky.clip_line([(1.0, -0.5, 0.0), (0.0, .5, 0.0), (-1.0, -.5, 0.0)])
        self.assertEqual(len(runs), 1)
        self.assertTrue(all(p[1] >= -1e-9 for p in runs[0]))


class DefaultScene(unittest.TestCase):
    def test_the_published_scene_is_unchanged(self):
        self.assertEqual(scene.scene(animated=True), (ASSETS/'observatory.svg').read_text())
        self.assertEqual(scene.scene(0, False), (ASSETS/'poster.svg').read_text())

    def test_the_default_scene_keeps_its_painted_sky_and_has_no_live_markup(self):
        svg = scene.scene(0, False)
        for marker in ('data-spin', 'data-sky="satellite"', 'data-sky="twinkles"', 'data-idle="target"', 'data-lock="reticle"'):
            self.assertIn(marker, svg)
        for marker in ('data-sky="night"', 'data-nightsky="stars"', 'data-trail', 'night-grad', 'mw-blur'):
            self.assertNotIn(marker, svg)
        self.assertIn('TARGET LOCK · M51', scene.LOCK_READOUT[0])


class LiveSky(unittest.TestCase):
    def test_a_live_night_has_the_real_sky_and_none_of_the_painted_one(self):
        svg = scene.scene(0, True, state=live(NIGHT))
        for marker in ('data-spin', 'data-sky="satellite"', 'data-sky="twinkles"', 'data-idle="target"', 'id="tw0"',
                       'stroke="#a7deff"', 'data-night="celestial"', 'data-night="satellite"', 'data-night="twinkles"'):
            self.assertNotIn(marker, svg, marker)
        for marker in ('data-sky="night" mask="url(#sky-mask)"', 'data-nightsky="cover"', 'data-nightsky="milky-way"',
                       'data-nightsky="lines"', 'data-nightsky="stars"', 'data-sky="meteors"'):
            self.assertIn(marker, svg, marker)
        self.assertEqual(svg.count('data-nightsky="milky-way"'), 2)   # the moving copy and the reduced-motion copy
        # the galaxies' sprites are not drawn: the atlas rectangle of the galaxy (and the ringed planet) is unused
        x, y, w, h = scene.RECTS['galaxy'][0]
        self.assertNotIn(f'viewBox="{x} {y} {w} {h}"', svg)
        x, y, w, h = scene.RECTS['planet'][0]
        self.assertNotIn(f'viewBox="{x} {y} {w} {h}"', svg)

    def test_the_night_gradient_is_opaque_at_night_and_the_day_overlay_keeps_dusk_and_day(self):
        night = scene.lighting(live(NIGHT))
        self.assertEqual(night['night_cover'], 1)
        self.assertIn(f'<rect data-nightsky="cover" width="{W}" height="{HORIZON_Y+10}" fill="url(#night-grad)" opacity="1"/>',
                      scene.night_sky_layer(0, False, night))
        dusk, noon = scene.lighting(live(DUSK)), scene.lighting(live(NOON))
        self.assertLess(dusk['night_cover'], 1)
        self.assertEqual(noon['night_cover'], 0)
        self.assertEqual(scene.night_sky_layer(0, False, noon), '')
        self.assertNotIn('night-grad', scene.scene(0, False, state=live(NOON)))
        self.assertIsNone(noon['sky'])

    def test_stars_fade_with_the_night_the_visibility_and_the_overcast_and_clouds_stay_above(self):
        def opacity(state):
            light = scene.lighting(state)
            found = re.search(r'data-nightsky="stars" opacity="([^"]+)"', scene.night_sky_layer(0, False, light))
            return float(found[1]) if found else 0
        clear_night = opacity(live(NIGHT))
        self.assertGreater(clear_night, .7)
        self.assertLess(opacity(scene_state.scene_state(NIGHT, None, storm(NIGHT))), clear_night/4)   # a storm hides them
        self.assertLess(opacity(live(DUSK)), .15)
        self.assertEqual(opacity(live(NOON)), 0)
        murky = clear(NIGHT, cloud_cover_pct=85.0)
        self.assertLess(opacity(scene_state.scene_state(NIGHT, None, murky)), clear_night)
        svg = scene.scene(0, False, state=scene_state.scene_state(NIGHT, None, clear(NIGHT, cloud_cover_pct=85.0)))
        self.assertLess(svg.index('data-nightsky="stars"'), svg.index('data-season="clouds"'))
        self.assertLess(svg.index('data-nightsky="stars"'), svg.index('data-light="title"'))   # and under the redrawn name

    def test_the_brightest_stars_twinkle_gently_on_clean_tracks(self):
        light = scene.lighting(live(NIGHT))
        sky = light['sky']
        self.assertEqual(len(sky['twinkle']), scene.TWINKLE_STARS)
        magnitudes = [s['mag'] for s in sky['twinkle']]
        self.assertEqual(magnitudes, sorted(magnitudes))
        plain = [s['mag'] for s in sky['stars'] if s['hr'] not in {t['hr'] for t in sky['twinkle']}]
        self.assertLessEqual(max(magnitudes), sorted(plain)[len(plain)//2])         # the twinkling ones are among the brightest
        for s in sky['twinkle']:
            self.assertLess(s['y'], scene.skyline_top(s['x'], s['x'])-7)              # only stars in open sky
            track = scene.twinkle_track(s['hr'])
            self.assertEqual(scene.PERIOD % track.dur, 0)
            self.assertLessEqual(track.begin, 0)
            self.assertGreaterEqual(min(track.values), 1-scene.TWINKLE_DEPTH-1e-9)
            self.assertLessEqual(max(track.values), 1+1e-9)
            step = track.dur/(len(track.values)-1)
            slope = max(abs(b-a) for a, b in zip(track.values, track.values[1:]))/step
            self.assertLess(slope, .7, s['hr'])                                       # never a flash
        markup = scene.night_stars(0, True, light)
        self.assertEqual(markup.count('<animate '), len(sky['twinkle']))
        self.assertEqual(scene.night_stars(0, False, light).count('<animate'), 0)

    def test_stars_keep_clear_of_the_name_and_use_catalogue_sizes_and_colours(self):
        sky = scene.lighting(live(NIGHT))['sky']
        x0, y0, x1, y1 = scene.TEXT_RECT
        for s in sky['stars']:
            self.assertFalse(x0 <= s['x'] <= x1 and y0 <= s['y'] <= y1, s)
            self.assertEqual((s['x'] % 2, s['y'] % 2), (0, 0))
            self.assertLessEqual(s['mag'], scene.star_limit(scene.lighting(live(NIGHT))['env']))
        self.assertEqual([scene.star_size(m) for m in (-1.4, 0.0, 1.0, 2.0, 3.0, 4.9)], [10, 10, 8, 6, 4, 3])
        self.assertLess(scene.star_colour(3300)[2], scene.star_colour(3300)[0])      # cool stars are orange
        self.assertGreater(scene.star_colour(30000)[2], scene.star_colour(30000)[0])  # hot stars are blue
        self.assertEqual(scene.star_colour(0), (255, 255, 255))
        self.assertGreater(scene.star_opacity(1, 40), scene.star_opacity(4.5, 40))
        self.assertGreater(scene.star_opacity(3, 40), scene.star_opacity(3, 2))        # thicker air near the horizon

    def test_the_still_frame_shows_no_flash_and_the_shape_of_the_sky_is_deterministic(self):
        a = scene.scene(0, False, state=live(NIGHT))
        self.assertEqual(a, scene.scene(0, False, state=live(NIGHT)))
        self.assertNotEqual(a, scene.scene(0, False, state=live(NIGHT+timedelta(hours=1))))   # the sky really turns


class LockOn(unittest.TestCase):
    def plan(self, when, observed=True):
        return scene.lighting(live(when, observed))['lock']

    def test_the_target_is_a_planet_else_the_moon_else_a_star(self):
        planet = self.plan(PLANET_NIGHT)
        self.assertEqual((planet['kind'], planet['name']), ('planet', 'MARS'))
        moon = self.plan(MOON_NIGHT)
        self.assertEqual((moon['kind'], moon['name']), ('moon', 'MOON'))
        star = self.plan(NIGHT)
        self.assertEqual((star['kind'], star['name']), ('star', 'MIRFAK'))
        self.assertEqual(self.plan(NOON), None)                                           # no lock-on in daylight
        self.assertIsNone(scene.lighting(scene_state.scene_state(NIGHT, None, storm(NIGHT)))['lock'])   # nor under thick cloud

    def test_the_first_candidate_that_fits_wins_in_the_order_given(self):
        light = scene.lighting(live(NIGHT))
        good = dict(kind='star', name='TEST ONE', x=700, y=250, ra_hours=1.0, dec_deg=50.0, mag=1.0, alt=40)
        inside_text = dict(good, name='HIDDEN', x=300, y=300)           # in the name block
        inside_log = dict(good, name='LOG', x=200, y=480)               # in the log panel
        off_canvas = dict(good, name='EDGE', x=20, y=250)
        below_skyline = dict(good, name='LOW', x=300, y=640)
        under_readout = dict(good, name='READOUT', x=1000, y=130)
        for bad in (inside_text, inside_log, off_canvas, below_skyline, under_readout):
            self.assertIsNone(scene.lock_plan(bad), bad['name'])
        with mock.patch.object(scene, 'lock_candidates', lambda _: [inside_text, inside_log, good, dict(good, name='LATER')]):
            self.assertEqual(scene.lock_target(light)['name'], 'TEST ONE')
        with mock.patch.object(scene, 'lock_candidates', lambda _: [inside_text, inside_log, off_canvas]):
            self.assertIsNone(scene.lock_target(light))                 # nothing fits: no lock-on at all
            svg = scene.layers(0, True, dict(light, lock=scene.lock_target(light)))
            self.assertNotIn('data-lock=', svg)
            self.assertNotIn('TARGET LOCK', svg)

    def test_the_reticle_line_leader_and_readout_avoid_everything_all_night_long(self):
        found = set()
        for when in (NIGHT+timedelta(minutes=15*i) for i in range(0, 40)):
            light = scene.lighting(live(when))
            plan = light['lock']
            if plan is None:
                continue
            found.add(plan['name'])
            boxes = plan['boxes']
            keep_clear = [scene._padded(scene.TEXT_RECT), scene._padded(scene.STORY_BOX)]
            for name in ('target', 'line', 'readout'):
                for box in keep_clear:
                    self.assertFalse(test_scene.overlap(boxes[name], box), (when, name))
            self.assertFalse(test_scene.overlap(boxes['target'], boxes['readout']), when)
            self.assertTrue(boxes['target'][0] >= 0 and boxes['target'][2] <= W and boxes['target'][1] >= 0, when)
            self.assertLessEqual(boxes['target'][3], scene.skyline_top(boxes['target'][0], boxes['target'][2]), when)
            self.assertLessEqual(boxes['readout'][2], W-12, when)
            # the drawn parts stay inside their boxes once the reticle has settled
            for t in (15.5, 17.0, 20.0):
                for name, box in (('reticle', boxes['target']), ('line', boxes['line']), ('readout', boxes['readout'])):
                    for bbox, opacity in lock_parts(plan, t)[name]:
                        self.assertTrue(test_scene.contains(box, bbox, 1.5), (when, t, name, bbox, box))
        self.assertGreaterEqual(len(found), 3, found)

    def test_the_readout_shows_the_real_name_and_coordinates(self):
        star = self.plan(NIGHT)
        texts = ['TARGET LOCK · MIRFAK', 'RA 03h24m', "DEC +49°52'"]         # Mirfak, J2000: 03h24m19s +49d51m40s
        for (d, x, y, _, _), text, row in zip(star['lines'], texts, range(3)):
            self.assertEqual(d, scene.pixel_text(text, scene.LOCK_TEXT_XY[0], scene.LOCK_TEXT_XY[1]+row*scene.LOCK_LINE_PITCH)[0])
        self.assertEqual((star['constellation'], star['constellation_symbol']), ('Perseus', 'Per'))
        planet = self.plan(PLANET_NIGHT)
        state = live(PLANET_NIGHT)
        mars = state['astronomy']['planets']['Mars']
        self.assertEqual((planet['ra_hours'], planet['dec_deg']), (mars['ra_hours'], mars['dec_deg']))
        self.assertEqual(planet['lines'][1][0], scene.pixel_text(f"RA {night_sky.ra_text(mars['ra_hours'])}", *planet['lines'][1][1:3])[0])
        self.assertEqual(planet['constellation'], 'Leo')
        moon = self.plan(MOON_NIGHT)
        self.assertEqual((moon['ra_hours'], moon['dec_deg']), tuple(live(MOON_NIGHT)['astronomy']['moon'][k] for k in ('ra_hours', 'dec_deg')))
        self.assertEqual(night_sky.ra_text(13.4979), '13h30m')
        self.assertEqual(night_sky.dec_text(-5.5), "-05°30'")
        self.assertEqual(night_sky.dec_text(47.195), "+47°12'")

    def test_the_planets_and_moon_state_carries_ra_and_dec_from_the_ephemeris(self):
        state = live(PLANET_NIGHT)
        t = ae.Time.Make(2026, 10, 30, 22, 30, 0)
        eq = ae.Equator(ae.Body.Mars, t, ae.Observer(*MUMBAI), False, True)
        mars = state['astronomy']['planets']['Mars']
        self.assertAlmostEqual(mars['ra_hours'], eq.ra, delta=.0002)
        self.assertAlmostEqual(mars['dec_deg'], eq.dec, delta=.002)

    def test_the_lock_on_keeps_its_timing_and_the_robot_still_reacts(self):
        self.assertTrue(13.7 <= scene.lock_moment() <= 13.72)   # unchanged: the reticle's opacity passes .5 there
        plan = self.plan(NIGHT)
        self.assertEqual(plan['tracks']['ret_a'].values, scene.LOCK['ret_a'].values)
        self.assertEqual(plan['tracks']['ret_a'].key_times, scene.LOCK['ret_a'].key_times)
        self.assertEqual(plan['tracks']['half'].values, scene.LOCK['half'].values)
        self.assertEqual((plan['tracks']['line_x'].values[0], plan['tracks']['line_y'].values[0]), scene.LOCK_FROM)
        self.assertEqual((plan['tracks']['line_x'].values[2], plan['tracks']['line_y'].values[2]), plan['end'])
        light = scene.lighting(live(NIGHT))
        self.assertIn('lock', [kind for _, kind, _ in scene.robot_reactions(light)])

    def test_the_log_beat_is_about_the_real_target(self):
        for when, kind, word in ((NIGHT, 'star', 'MIRFAK'), (PLANET_NIGHT, 'planet', 'MARS'), (MOON_NIGHT, 'moon', 'MOON')):
            state = live(when)
            light = scene.lighting(state)
            context = story.context(state, dict(light, lock=light['lock']), fits=scene.story_fits)
            beats = {b['id']: b for b in story.eligible(context)}
            self.assertNotIn('m51', beats)
            beat = beats[f'lock-{kind}']
            self.assertIn(word, beat['lines'][0])
            self.assertTrue(beat['lines'][0].startswith(('TELESCOPE ON', 'LOCK')) or kind == 'star')
            if kind == 'star':
                self.assertEqual(beat['lines'][2], 'IN PERSEUS')
                self.assertIsNone(beat['inset'])
                self.assertIn(f"MAG {story._num(light['lock']['mag'])}", beat['lines'][1])
            if kind == 'planet':
                self.assertEqual(beat['inset'], 'planet')
                self.assertEqual(beat['lines'][2], 'IN LEO')
            if kind == 'moon':
                self.assertEqual(beat['inset'], 'moon')
                self.assertTrue(beat['lines'][1].endswith('% LIT'))
        daylight = story.context(live(NOON), scene.lighting(live(NOON)), fits=scene.story_fits)
        self.assertFalse([b for b in story.eligible(daylight) if b['id'].startswith('lock-')])

    def test_a_planet_that_has_the_lock_gets_no_second_reticle_and_the_boxes_are_kept_clear(self):
        light = scene.lighting(live(PLANET_NIGHT))
        self.assertEqual(light['lock']['name'], 'MARS')
        self.assertIsNone(scene.reticle_place(light, 'Mars'))
        self.assertIsNotNone(scene.planet_place(light, light['astronomy'], 'Mars'))


class Trails(unittest.TestCase):
    def test_points_run_back_in_time_from_the_body_along_its_real_path(self):
        state = live(PLANET_NIGHT)
        mars = state['astronomy']['planets']['Mars']
        self.assertEqual(len(mars['trail']), 18)                                  # every 10 minutes for 3 hours
        run = scene.trail_points(mars)
        self.assertEqual([age for age, _, _ in run], list(range(0, 10*len(run), 10)))   # ordered in time, newest first
        self.assertGreater(len(run), 5)
        self.assertEqual(run[0][1:], scene.sun_screen(mars['altitude_deg'], mars['azimuth_deg']))
        # Mars is rising: its past positions are lower in the sky than where it is now
        self.assertTrue(all(b[2] >= a[2] for a, b in zip(run, run[1:])))
        # and match the ephemeris three hours earlier
        t = ae.Time.Make(2026, 10, 30, 22, 30, 0).AddDays(-10/1440)               # 10 minutes before the render
        eq = ae.Equator(ae.Body.Mars, t, ae.Observer(*MUMBAI), True, True)
        h = ae.Horizon(t, ae.Observer(*MUMBAI), eq.ra, eq.dec, ae.Refraction.Airless)
        self.assertAlmostEqual(mars['trail'][0][0], h.altitude, delta=.01)
        self.assertAlmostEqual(mars['trail'][0][1], h.azimuth, delta=.01)

    def test_the_trail_dims_with_age_and_is_one_continuous_line(self):
        self.assertAlmostEqual(scene.trail_opacity(0, 10), scene.TRAIL_PEAK*(1-5/180))
        self.assertLess(scene.trail_opacity(170, 180), .02)
        ages = [(a, a+10) for a in range(0, 180, 10)]
        opacities = [scene.trail_opacity(*pair) for pair in ages]
        self.assertTrue(all(b < a for a, b in zip(opacities, opacities[1:])))      # strictly decreasing with age
        self.assertLessEqual(max(opacities), .5)
        body = live(PLANET_NIGHT)['astronomy']['planets']['Mars']
        markup = scene.trail_markup(body, (255, 156, 112), 'mars')
        segments = re.findall(r'<line x1="([^"]+)" y1="([^"]+)" x2="([^"]+)" y2="([^"]+)" opacity="([^"]+)"/>', markup)
        self.assertGreater(len(segments), 5)
        values = [float(s[4]) for s in segments]
        self.assertTrue(all(b < a for a, b in zip(values, values[1:])), values)
        for a, b in zip(segments, segments[1:]):
            self.assertEqual((a[2], a[3]), (b[0], b[1]))                            # each segment starts where the last ended
        self.assertIn('stroke-width="1.5"', markup)

    def test_nothing_behind_the_viewer_or_below_the_horizon(self):
        body = dict(altitude_deg=30, azimuth_deg=350, trail=[[28, 355], [26, 358], [24, 5], [-2, 10], [20, 20], [18, 25]])
        run = scene.trail_points(body)
        self.assertEqual(len(run), 4)                                                # stops at the first point below the horizon
        body = dict(altitude_deg=30, azimuth_deg=60, trail=[[30, 80], [30, 95], [30, 100]])
        self.assertEqual(len(scene.trail_points(body)), 2)                           # stops where the path leaves the front
        for when in (PLANET_NIGHT, MOON_NIGHT, NIGHT, datetime(2026, 11, 7, 4, 0, tzinfo=IST)):
            astronomy = live(when)['astronomy']
            for name, body in list(astronomy['planets'].items())+[('Moon', astronomy['moon'])]:
                run = scene.trail_points(body)
                for k, (age, x, y) in enumerate(run):
                    alt, az = (body['altitude_deg'], body['azimuth_deg']) if k == 0 else body['trail'][k-1]
                    self.assertGreater(alt, 0, (when, name, age))
                    self.assertTrue(scene.in_view(alt, az), (when, name, age))
                    self.assertTrue(0 <= x <= W and y < HORIZON_Y, (when, name, age, x, y))

    def test_only_bodies_drawn_in_the_sky_have_a_trail_and_it_sits_in_the_sky_mask_behind_the_clouds(self):
        svg = scene.scene(0, False, state=live(PLANET_NIGHT))
        self.assertIn('data-trail="mars"', svg)
        self.assertIn('data-trail="jupiter"', svg)
        self.assertIn('data-trail="moon"', svg)
        self.assertLess(svg.index('data-trail="mars"'), svg.index('data-planet="mars"')+200)   # inside the planet's group
        bodies = svg.index('data-sky="bodies" mask="url(#sky-mask)"')
        self.assertLess(bodies, svg.index('data-trail="mars"'))
        clouds = svg.find('data-season="sky"')
        if clouds > 0:
            self.assertLess(svg.index('data-trail="mars"'), clouds)
        self.assertNotIn('data-trail="mars"', scene.scene(0, False, state=live(NOON)))     # a planet is not drawn by day
        self.assertNotIn('data-trail', scene.scene(0, False))
        self.assertNotIn('data-trail', scene.scene(animated=True))
        # a planet that is not in view has none
        self.assertNotIn('data-trail="saturn"', svg)

    def test_the_trail_is_static_and_thin(self):
        svg = scene.scene(0, True, state=live(PLANET_NIGHT))
        trail = re.search(r'<g data-trail="mars".*?</g>', svg)[0]
        self.assertNotIn('<animate', trail)
        self.assertIn('stroke-width="1.5"', trail)
        self.assertTrue(1.0 <= scene.TRAIL_WIDTH <= 2.0)


class LiveSkyAnimations(unittest.TestCase):
    """The generic SMIL-vs-raster and loop checks on a live night with twinkling stars, meteors, clouds and the lock-on,
    sampled across the lock-on's whole sequence and at times that fall between twinkle keyframes."""

    TWINKLE_TIMES = [.25, .75, 1.1, 1.9, 2.3, 3.7, 4.2, 5.3, 6.1, 7.1, 8.4, 10.6, 13.3, 16.9, 19.3, 21.7]
    LOCK_TIMES = [12.7, 12.9, 13.1, 13.4, 13.8, 14.4, 14.6, 14.75, 14.9, 15.0, 15.3, 15.6, 17.0, 20.0, 20.5, 20.9, 21.0]

    def run_for(self, when, observation):
        state = scene_state.scene_state(when, None, observation)
        light = scene.lighting(state)
        original = scene.layers
        times = sorted(set(test_scene.CHECK_TIMES+self.TWINKLE_TIMES+self.LOCK_TIMES))
        with mock.patch.object(scene, 'layers', lambda t, animated, _=None: original(t, animated, light)), \
                mock.patch.object(scene, 'ROUTES', scene.flying_routes(light['day']['airliner'], light)), \
                mock.patch.object(test_scene, 'CHECK_TIMES', times), \
                mock.patch.object(test_scene, 'LINEAR', 1e-3), mock.patch.object(test_scene, 'PX', .05):
            # The starships' warp-flash scale keyframes print three decimals, so between keyframes the raster and the
            # SMIL scale differ by up to 3e-4 (0.04 px). The default check times never land there; these do.
            test_daily.run(test_daily.GENERIC[:2])
        return light

    def test_clear_night_with_a_star_lock_on(self):
        light = self.run_for(NIGHT, clear(NIGHT))
        self.assertEqual(light['lock']['kind'], 'star')
        self.assertEqual(len(light['sky']['twinkle']), scene.TWINKLE_STARS)

    def test_pre_dawn_with_planets_trails_and_a_planet_lock_on(self):
        light = self.run_for(PLANET_NIGHT, clear(PLANET_NIGHT))
        self.assertEqual(light['lock']['kind'], 'planet')


if __name__ == '__main__':
    unittest.main()
