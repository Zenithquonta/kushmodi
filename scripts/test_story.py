"""Phase 15d: the observatory log (story beats), the planet reticle and the planets page on the shed screen."""
import copy
import functools
import re
from datetime import datetime, timedelta
import unittest
from unittest import mock
from zoneinfo import ZoneInfo

import build_animation as scene
import scene_state
import story
import test_daily
import test_scene
from test_portfolio import overlap
from test_storm import clear, storm, weather
from test_weather import observation

IST = ZoneInfo('Asia/Kolkata')
NIGHT = datetime(2026, 10, 2, 21, 0, tzinfo=IST)
DAY = datetime(2026, 10, 2, 15, 0, tzinfo=IST)
QUIET = datetime(2026, 3, 14, 21, 0, tzinfo=IST)   # no priority beat: the log is all weighted picks
OPPOSITION = datetime(2026, 10, 4, 21, 0, tzinfo=IST)   # Saturn's opposition was 04 Oct 17:42 IST
HOURS = (0, 5, 11, 18, 21)
BEAT_NAMES = ('Mercury', 'Venus', 'Mars', 'Jupiter', 'Saturn', 'Uranus', 'Neptune')


def variants(when):
    """The weather the log must cope with: none (seasonal model), the recorded drizzle, and the clear, hot, humid,
    windy, cloudy and thunderstorm observations."""
    return [None, observation(time=when.isoformat()), clear(when),
            clear(when, temperature_c=36.0), clear(when, humidity_pct=92.0),
            clear(when, wind_kmh=25.0, gust_kmh=45.0),
            weather(when, condition='overcast', weather_code=3, cloud_cover_pct=90.0), storm(when)]


@functools.lru_cache(maxsize=None)
def state_at(when):
    return scene_state.scene_state(when)


def with_weather(state, obs):
    return dict(state, weather=obs)


def eligible(state, light=None):
    """Every beat the templates offer for a state, the way the renderer gathers them."""
    light = light or scene.lighting(state)
    extras = dict(mood=scene.mood(light), flicker=bool(scene.light_events(light)), grounded=bool(scene.grounded(light)))
    return story.eligible(story.context(state, dict(light, **extras), fits=scene.story_fits))


def limit(beat):
    return scene.INSET_TEXT_LIMIT if beat['inset'] else scene.STORY_BOX[2]-12


class Fits(unittest.TestCase):
    def check(self, beat, note=''):
        self.assertLessEqual(len(beat['lines']), story.LINE_LIMIT, (note, beat['id']))
        self.assertTrue(beat['lines'], beat['id'])
        for text in beat['lines']:
            _, width, _ = scene.pixel_text(text, scene.STORY_BOX[0]+16, 0)   # KeyError: a glyph is missing
            self.assertLessEqual(scene.STORY_BOX[0]+16+width, limit(beat), (note, beat['id'], text))

    def test_every_beat_over_the_year_and_the_weather_fits(self):
        start, seen = datetime(2026, 1, 1, tzinfo=IST), set()
        for day in range(0, 365, 9):
            for hour in HOURS:
                when = start+timedelta(days=day, hours=hour)
                state = state_at(when)
                for obs in variants(when):
                    for beat in eligible(with_weather(state, obs)):
                        seen.add(beat['id'])
                        self.check(beat, f"{when:%Y-%m-%d %H:%M} {obs and obs['condition']}")
        for expected in ('opposition-saturn', 'planet-up-jupiter', 'moon-phase', 'clear-night', 'rain', 'hot', 'humid',
                         'breezy', 'clouds', 'season', 'lock-star', 'jupiter-moons', 'printer'):
            self.assertIn(expected, seen)

    def test_the_longest_possible_planet_lines_fit(self):
        """All planets high, bright or faint, far away, in the longest constellations, with every opposition state."""
        real = state_at(NIGHT)
        light = scene.lighting(real)
        for altitude, rise in ((88, None), (-5, (NIGHT+timedelta(hours=2)).isoformat())):
            for magnitude in (-4.7, 7.9):
                for constellation, symbol in (('Sagittarius', 'Sgr'), ('Capricornus', 'Cap'), ('Ophiuchus', 'Oph')):
                    for days in (3, -3, 0):
                        state = copy.deepcopy(real)
                        opposition = (NIGHT+timedelta(days=days)).isoformat()
                        for name in BEAT_NAMES:
                            state['astronomy']['planets'][name].update(
                                altitude_deg=altitude, magnitude=magnitude, distance_au=30.07, rise=rise,
                                constellation=constellation, constellation_symbol=symbol,
                                **(dict(opposition=opposition) if name in story.OUTER else {}))
                        beats = eligible(state, light)
                        ids = {b['id'] for b in beats}
                        self.assertTrue(any(i.startswith('opposition-') for i in ids))
                        self.assertTrue(any(i.startswith(('planet-up-', 'planet-rising-')) for i in ids), ids)
                        for beat in beats:
                            self.check(beat, f'{altitude} {magnitude} {constellation} {days}')

    def test_a_beat_that_does_not_fit_falls_back_to_the_shortest_option(self):
        c = dict(fits=lambda text, inset: len(text) <= 5)
        self.assertEqual(story.pick(c, None, 'LONG LINE', 'MEDIUM', 'TINY'), 'TINY')
        self.assertEqual(story.pick(c, None, 'LONG LINE', 'ABCDE', 'A'), 'ABCDE')
        self.assertEqual(story.pick(c, None, 'LONG LINE', 'ALSO LONG'), 'ALSO LONG')
        self.assertEqual(story.pick(c, None, ['TINY', 'LONG LINE'], ['TINY', 'ABC']), ['TINY', 'ABC'])

    def test_only_the_outer_planets_have_an_opposition_beat(self):
        state = copy.deepcopy(state_at(OPPOSITION))
        for name in BEAT_NAMES:
            state['astronomy']['planets'][name]['opposition'] = OPPOSITION.isoformat()
        names = {b['id'] for b in eligible(state) if b['id'].startswith('opposition-')}
        self.assertEqual(names, {f'opposition-{n.lower()}' for n in story.OUTER})

    def test_on_this_day_entries_fit_and_have_real_dates(self):
        for (month, day), entries in story.ON_THIS_DAY.items():
            datetime(2024, month, day)   # raises for an impossible date
            self.assertTrue(entries)
            for year, first, second in entries:
                self.assertTrue(1500 < year <= 2026, year)
                self.check(story.beat('x', [f'ON THIS DAY · {year}', first, second]), (month, day))


class Choose(unittest.TestCase):
    def context(self, when, obs=None):
        state = with_weather(state_at(when), obs)
        light = scene.lighting(state)
        return story.context(state, dict(light, mood='calm', flicker=False, grounded=False), fits=scene.story_fits)

    def test_deterministic_for_a_seed_and_never_two_of_the_same(self):
        c = self.context(QUIET)
        for seed in range(30):
            first, again = story.choose(c, seed), story.choose(c, seed)
            self.assertEqual([b['id'] for b in first], [b['id'] for b in again])
            self.assertEqual(len(first), 2)
            self.assertNotEqual(first[0]['id'], first[1]['id'])
            targets = [b['target'] for b in first if b['target']]
            self.assertEqual(len(targets), len(set(targets)))
        self.assertGreater(len({tuple(b['id'] for b in story.choose(c, seed)) for seed in range(30)}), 5)

    def test_priority_beats_always_win(self):
        c = self.context(OPPOSITION)
        for seed in range(30):
            ids = [b['id'] for b in story.choose(c, seed)]
            self.assertEqual(ids, ['opposition-saturn', 'on-this-day-1957'], seed)
        c = self.context(OPPOSITION.replace(day=5, hour=0, minute=30))   # only the opposition is left to announce
        for seed in range(30):
            first, second = story.choose(c, seed)
            self.assertEqual(first['id'], 'opposition-saturn')
            self.assertIsNone(second['priority'])

    def test_the_pairs_vary_across_the_quarter_hours_of_a_day(self):
        start = QUIET.replace(hour=0)
        pairs = set()
        for slot in range(96):
            light = scene.lighting(scene_state.scene_state(start+timedelta(minutes=15*slot)))
            pairs.add(tuple(b['id'] for b in light['story']))
            self.assertEqual(len(light['story']), 2)
        self.assertGreater(len(pairs), 40)


class SaturnOpposition(unittest.TestCase):
    """Saturn was at opposition on 04 Oct 2026 at 17:42 IST: the log announces it all night, and the sky agrees."""

    def test_the_log_announces_it(self):
        for when, second in ((OPPOSITION, 'on-this-day-1957'),
                             (OPPOSITION.replace(day=5, hour=0, minute=30), None),
                             (OPPOSITION.replace(hour=11), 'on-this-day-1957')):
            story_beats = scene.lighting(scene_state.scene_state(when))['story']
            first = story_beats[0]
            self.assertEqual(first['id'], 'opposition-saturn', when)
            self.assertEqual(first['lines'][:2], ['SATURN AT OPPOSITION', '04 OCT 17:42 IST'])
            self.assertEqual(first['inset'], 'saturn')
            if second:
                self.assertEqual(story_beats[1]['id'], second)
                self.assertEqual(story_beats[1]['lines'][1:], ['SPUTNIK 1 LAUNCHED', 'THE SPACE AGE BEGINS'])

    def test_the_facts_come_from_the_computed_sky(self):
        for when in (OPPOSITION, OPPOSITION.replace(day=5, hour=0, minute=30), OPPOSITION.replace(hour=11)):
            planets = scene_state.scene_state(when)['astronomy']['planets']
            saturn = planets['Saturn']
            self.assertEqual(saturn['constellation'], 'Cetus')
            self.assertAlmostEqual(saturn['distance_au'], 8.434, delta=.002)
            self.assertEqual(saturn['magnitude'], .2)
            self.assertEqual(saturn['rise'][:16], '2026-10-04T18:26', when)   # the night of the 4th, also at 11:00
            self.assertEqual(saturn['opposition'][:16], '2026-10-04T17:42')
            self.assertEqual((planets['Mars']['rise'][:16], planets['Mars']['constellation']), ('2026-10-05T01:38', 'Cancer'))
            self.assertEqual((planets['Jupiter']['rise'][:16], planets['Jupiter']['constellation']),
                             ('2026-10-05T02:51', 'Leo'))
            self.assertNotIn('opposition-mars', {b['id'] for b in eligible(scene_state.scene_state(when))})

    def test_jupiters_moons_are_close_to_jupiter(self):
        for when in (NIGHT, OPPOSITION, datetime(2026, 12, 20, 3, 0, tzinfo=IST)):
            moons = scene_state.scene_state(when)['astronomy']['jupiter_moons']
            self.assertEqual(sorted(moons), ['Callisto', 'Europa', 'Ganymede', 'Io'])
            for east, north in moons.values():
                self.assertLess(abs(east), 800)
                self.assertLess(abs(north), 800)


def svg(when, obs=None, t=0, animated=False):
    return scene.scene(t, animated, state=scene_state.scene_state(when, None, obs))


class Panel(unittest.TestCase):
    def test_the_story_and_the_advisory_never_share_the_panel(self):
        stormy = svg(NIGHT, storm())
        self.assertIn('data-advisory="hologram"', stormy)
        self.assertNotIn('data-story', stormy)
        self.assertNotIn('data-beat', stormy)
        calm = svg(DAY, clear())
        self.assertIn('data-story="log"', calm)
        self.assertNotIn('data-advisory', calm)
        self.assertEqual(calm.count('data-beat='), 2)

    def test_the_first_beat_shows_in_the_still_frame(self):
        for when, obs in ((NIGHT, None), (DAY, clear()), (OPPOSITION, None)):
            markup = svg(when, obs)
            opacities = [float(v) for v in re.findall(r'<g data-beat="[^"]+" opacity="([^"]+)"', markup)]
            self.assertEqual(opacities, [1, 0])
            self.assertEqual(scene.story_fades()[0].at(0), 1)
            self.assertEqual(scene.story_fades()[1].at(0), 0)
            self.assertEqual([f.at(20) for f in scene.story_fades()], [0, 1])   # the second beat holds to the loop's end

    def test_the_panel_keeps_to_its_box_and_the_default_scene_has_no_story(self):
        for markup in (scene.scene(0, False), scene.scene(0, True), scene.scene(animated=True)):
            for marker in ('data-story', 'data-beat', 'data-reticle', 'data-screen="planets"'):
                self.assertNotIn(marker, markup)
        x, y = scene.INSET[0], scene.INSET[1]
        box = scene.STORY_BOX
        self.assertTrue(box[0] < x-scene.INSET[2] and x+scene.INSET[2] < box[2])
        self.assertTrue(box[1] < y-scene.INSET[2] and y+scene.INSET[2] < box[3])
        self.assertLess(scene.INSET_TEXT_LIMIT, x-scene.INSET[2])


class Reticle(unittest.TestCase):
    def test_it_stays_clear_of_everything_and_follows_the_planet(self):
        start, found = datetime(2026, 11, 18, 2, 0, tzinfo=IST), 0   # Jupiter climbs the north-eastern sky before dawn
        for step in range(24):   # 02:00 .. 08:00
            when = start+timedelta(minutes=15*step)
            light = scene.lighting(scene_state.scene_state(when))
            place = scene.reticle_place(light, 'Jupiter')
            if place is None:
                continue
            found += 1
            box = scene.reticle_box(*place)
            for name in scene.RETICLE_AVOID:
                self.assertFalse(overlap(box, getattr(scene, name)), (when, name))
            self.assertTrue(box[0] >= 0 and box[2] <= scene.W and box[1] >= 0, (when, box))
            self.assertLessEqual(box[3], scene.skyline_top(box[0], box[2]), when)
            self.assertEqual(place, scene.planet_place(light, light['astronomy'], 'Jupiter')[:2])
        self.assertGreater(found, 0)

    def test_none_under_cloud(self):
        for step in range(0, 45, 4):
            when = datetime(2026, 11, 18, 2, 0, tzinfo=IST)+timedelta(minutes=15*step)
            light = scene.lighting(scene_state.scene_state(when, None, storm(when)))
            self.assertIsNone(scene.reticle_place(light, 'Jupiter'), when)

    def test_the_marker_is_in_the_picture_only_for_a_drawn_planet(self):
        for step in range(45):
            when = datetime(2026, 10, 4, 19, 0, tzinfo=IST)+timedelta(minutes=15*step)
            light = scene.lighting(scene_state.scene_state(when))
            markup = scene.story_panel(0, False, light)
            if light['story'][0]['target'] and scene.reticle_place(light, light['story'][0]['target']):
                self.assertIn('data-reticle="saturn"', markup)
            else:
                self.assertNotIn('data-reticle', markup)


class PlanetScreen(unittest.TestCase):
    def check(self, astronomy):
        lines = scene.screen_lines('planets', astronomy)
        self.assertLessEqual(len(lines), 7)
        self.assertEqual(lines[0], 'PLANET TRACK')
        for text in lines:
            _, width, _ = scene.pixel_text(text, scene.SCREEN[0]+scene.SCREEN_MARGIN, 0, cell=2)
            self.assertLessEqual(scene.SCREEN[0]+scene.SCREEN_MARGIN+width, scene.SCREEN[2]-1, text)
        below = False
        for text in lines[1:]:
            if ' RISE ' in text:
                below = True
            else:
                self.assertFalse(below, lines)   # planets above the horizon come first
        return lines

    def test_real_skies_fit_with_the_visible_planets_first(self):
        start = datetime(2026, 1, 1, tzinfo=IST)
        for day in range(0, 365, 9):
            for hour in HOURS:
                self.check(state_at(start+timedelta(days=day, hours=hour))['astronomy'])
        lines = self.check(state_at(OPPOSITION)['astronomy'])
        self.assertTrue(any(line.startswith('SAT ') and 'CET' in line for line in lines), lines)

    def test_extreme_numbers_fit(self):
        planets = {name: dict(altitude_deg=alt, azimuth_deg=0, magnitude=0, constellation_symbol='Sgr',
                              rise='2026-10-05T01:38:22+05:30')
                   for alt, name in zip((123, -100, 100, -5, 88, -88, 5), BEAT_NAMES)}
        planets['Mercury']['rise'] = None
        lines = self.check(dict(planets=planets))
        self.assertEqual(len(lines), 1+scene.SCREEN_PLANET_ROWS)
        self.check(dict(planets={name: dict(body, altitude_deg=-123) for name, body in planets.items()}))
        self.check(dict(planets={name: dict(body, altitude_deg=123, constellation_symbol='Cap')
                                 for name, body in planets.items()}))

    def test_the_page_is_on_the_screen_between_10_and_15_seconds(self):
        self.assertEqual([page for page, _, _ in scene.SCREEN_PAGES], ['sun', 'moon', 'planets', 'sats'])
        self.assertEqual(scene.SCREEN_PAGES[2][1:], (10.0, 15.0))
        markup = scene.screen(0, False, scene.lighting(state_at(OPPOSITION)), state_at(OPPOSITION)['astronomy'])
        self.assertIn('data-screen="planets" opacity="0"', markup)


class StoryAnimations(unittest.TestCase):
    """The generic SMIL-vs-raster and loop checks on the night of Saturn's opposition, sampled at the story swap and
    fade, the screen's page changes and the reticle's pulse."""

    STORY_TIMES = [11.5, 11.7, 12.0, 12.2, 23.5, 23.7, 23.95, 4.9, 5.1, 9.9, 10.1, 11.9, 12.1, 14.9, 15.1, 19.9, 20.1]

    def test_opposition_night(self):
        when = datetime(2026, 10, 5, 0, 0, tzinfo=IST)
        state = scene_state.scene_state(when)
        light = scene.lighting(state)
        original = scene.layers
        times = sorted(set(test_scene.CHECK_TIMES+self.STORY_TIMES))
        with mock.patch.object(scene, 'layers', lambda t, animated, _=None: original(t, animated, light)), \
                mock.patch.object(scene, 'ROUTES', scene.flying_routes(light['day']['airliner'], light)), \
                mock.patch.object(test_scene, 'CHECK_TIMES', times), \
                mock.patch.object(test_scene, 'LINEAR', 1e-3), mock.patch.object(test_scene, 'PX', .05):
            # The starships' warp-flash scale keyframes print three decimals, so between keyframes the raster and the
            # SMIL scale differ by up to 3e-4 (0.04 px). The default check times never land there; these do.
            test_daily.run(test_daily.GENERIC[:2])


if __name__ == '__main__':
    unittest.main()
