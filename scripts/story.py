"""Story beats for the live observatory (Phase 15d): short log entries chosen from the real sky, the weather and the
season, so the picture tells a slightly different story at every redraw.

Every beat is built only from the scene state (computed astronomy, a validated weather observation, the season) and
fixed strings. Nothing comes from the network as text. A beat is a dict:

    id        stable name of the template (for tests and the log)
    lines     a title and up to three detail lines, upper case, drawn with the renderer's pixel font
    inset     None, 'saturn', 'jupiter', 'planet' or 'moon': the small eyepiece view beside the text
    target    a planet name when the beat is about a planet (the renderer may put a reticle on it), else None
    priority  rank for must-show beats (lower first); None for ordinary beats, which are picked by weight

The library is a list of template functions; each returns a beat or None when its conditions do not hold.
"""
from datetime import datetime, timedelta
import random

LINE_LIMIT = 4                      # title + three detail lines
SHORT = dict(Mercury='MER', Venus='VEN', Mars='MAR', Jupiter='JUP', Saturn='SAT', Uranus='URA', Neptune='NEP')
NAKED_EYE = ('Mercury', 'Venus', 'Mars', 'Jupiter', 'Saturn')
OUTER = ('Mars', 'Jupiter', 'Saturn', 'Uranus', 'Neptune')   # the planets that have an opposition
APPROX_CHARS = dict(plain=29, inset=22)   # the line lengths the default fit rule allows (12 px per character)
OPPOSITION_WINDOW_DAYS = 7
SEASON_NOTES = dict(vasanta='SPRING', grishma='SUMMER HEAT', varsha='MONSOON', sharad='AUTUMN · SKIES CLEARING',
                    hemanta='EARLY WINTER', shishira='WINTER NIGHTS')

# On this day: (month, day) -> [(year, line, line)]. Only well-documented dates, as usually cited.
ON_THIS_DAY = {
    (1, 1): [(1801, 'PIAZZI FINDS CERES', 'FIRST ASTEROID SEEN')],
    (1, 7): [(1610, 'GALILEO SEES JUPITER', 'AND THREE OF ITS MOONS')],
    (1, 28): [(1958, 'LEGO BRICK PATENT FILED', 'STUD AND TUBE DESIGN')],
    (2, 14): [(1990, 'VOYAGER 1 LOOKS BACK', 'THE PALE BLUE DOT')],
    (2, 18): [(1930, 'PLUTO DISCOVERED', 'CLYDE TOMBAUGH')],
    (3, 13): [(1781, 'HERSCHEL FINDS URANUS', 'FIRST NEW PLANET')],
    (4, 3): [(1984, 'RAKESH SHARMA IN SPACE', 'FIRST INDIAN IN ORBIT')],
    (4, 12): [(1961, 'GAGARIN IN ORBIT', 'FIRST HUMAN IN SPACE')],
    (4, 19): [(1975, 'ARYABHATA LAUNCHED', "INDIA'S FIRST SATELLITE")],
    (4, 24): [(1990, 'HUBBLE LAUNCHED', 'TELESCOPE IN ORBIT')],
    (6, 16): [(1963, 'TERESHKOVA IN ORBIT', 'FIRST WOMAN IN SPACE')],
    (7, 14): [(2015, 'NEW HORIZONS AT PLUTO', 'FIRST CLOSE FLYBY'),
              (2023, 'CHANDRAYAAN-3 LAUNCHED', 'BOUND FOR THE MOON')],
    (7, 20): [(1969, 'APOLLO 11 ON THE MOON', 'TRANQUILITY BASE')],
    (8, 6): [(2012, 'CURIOSITY LANDS', 'GALE CRATER · MARS')],
    (8, 23): [(2023, 'CHANDRAYAAN-3 LANDS', 'NEAR THE SOUTH POLE')],
    (9, 2): [(2023, 'ADITYA-L1 LAUNCHED', "INDIA'S SUN MISSION")],
    (9, 5): [(1977, 'VOYAGER 1 LAUNCHED', 'NOW IN INTERSTELLAR SPACE')],
    (9, 23): [(1846, 'NEPTUNE FOUND', 'WHERE MATHS SAID IT WOULD BE')],
    (9, 24): [(2014, 'MANGALYAAN AT MARS', 'ORBIT ON THE FIRST TRY')],
    (10, 4): [(1957, 'SPUTNIK 1 LAUNCHED', 'THE SPACE AGE BEGINS')],
    (10, 15): [(1932, 'JRD TATA FLIES THE MAIL', 'KARACHI TO BOMBAY')],
    (10, 22): [(2008, 'CHANDRAYAAN-1 LAUNCHED', "INDIA'S FIRST MOON PROBE")],
    (11, 3): [(1957, 'SPUTNIK 2 LAUNCHED', 'LAIKA IN ORBIT')],
    (11, 5): [(2013, 'MANGALYAAN LAUNCHED', 'MARS ORBITER MISSION')],
    (12, 17): [(1903, 'WRIGHT FLYER FLIES', 'FIRST POWERED FLIGHT')],
    (12, 25): [(2021, 'WEBB TELESCOPE LAUNCHED', 'JWST LEAVES FOR L2')],
}


def _time(stamp):
    return datetime.fromisoformat(stamp) if stamp else None


def _clock(stamp):
    return stamp[11:16] if stamp else '--:--'


def _num(value, digits=1):
    text = f'{value:.{digits}f}'
    return text.rstrip('0').rstrip('.') if '.' in text else text


def _approx_fits(text, inset):
    return len(text) <= APPROX_CHARS['inset' if inset else 'plain']


def context(state, light, fits=None):
    """Everything the templates may read, gathered once. ``fits(text, inset)`` says whether a line of text fits the
    log panel (beside the eyepiece when ``inset`` is set); the renderer passes one measured with its real font."""
    astronomy = state['astronomy']
    now = datetime.fromisoformat(state['timestamp_local'])
    night_start = datetime.combine((now-timedelta(hours=6)).date(), datetime.min.time(), now.tzinfo)+timedelta(hours=12)
    return dict(now=now, night=(night_start, night_start+timedelta(days=1)), astronomy=astronomy,
                sun=astronomy['sun'], moon=astronomy['moon'], planets=astronomy.get('planets', {}),
                moon_times=astronomy.get('moon_times', {}), sun_times=astronomy.get('sun_times', {}),
                dark=1-light['daylight'], observation=light.get('observation'), season=state['season'],
                shower=state.get('sky_events', {}).get('meteor_shower'), mood=light.get('mood', 'calm'),
                flicker=light.get('flicker', False), grounded=light.get('grounded', False),
                lst=astronomy.get('local_sidereal_time_hours'), fits=fits or _approx_fits)


def beat(id, lines, inset=None, target=None, priority=None, weight=1.0, body=None):
    return dict(id=id, lines=[line for line in lines if line][:LINE_LIMIT], inset=inset, target=target,
                priority=priority, weight=weight, body=body or target)


def pick(c, inset, *options):
    """The first option that fits the panel: a line of text, or a list of lines that must all fit. Options run from
    the most to the least descriptive; when none fits the last (the shortest) is used."""
    for option in options:
        lines = [option] if isinstance(option, str) else option
        if all(c['fits'](line, inset) for line in lines):
            return option
    return options[-1]


def _symbol(body):
    """The three-letter constellation abbreviation, upper case."""
    return (body.get('constellation_symbol') or body['constellation'][:3]).upper()


def _in(c, inset, body):
    """'IN SAGITTARIUS' or, when that is too long for the panel, 'IN SGR'."""
    return pick(c, inset, f"IN {body['constellation'].upper()}", f"IN {_symbol(body)}")


def _inset_for(name):
    return 'saturn' if name == 'Saturn' else 'jupiter' if name == 'Jupiter' else 'planet'


# --- priority beats -------------------------------------------------------------------------------------------
def oppositions(c):
    out = []
    for name, body in c['planets'].items():
        when = _time(body.get('opposition'))
        if name not in OUTER or when is None:
            continue
        days = (when-c['now']).total_seconds()/86400
        if abs(days) > OPPOSITION_WINDOW_DAYS:
            continue
        inset, label = _inset_for(name), name.upper()
        tonight = c['night'][0] <= when < c['night'][1]
        if tonight or when.date() == c['now'].date():
            title = pick(c, inset, f'{label} AT OPPOSITION', f'{label} · OPPOSITION')
            timing = f"{when:%d %b %H:%M}".upper()+' IST'
        elif days > 0:
            n = max(1, round(days))
            title = pick(c, inset, f'{label} NEARS OPPOSITION', f'{label} · OPPOSITION')
            timing = f"IN {n} DAY{'S' if n > 1 else ''} · {when:%d %b}".upper()
        else:
            n = max(1, round(-days))
            title = pick(c, inset, f'{label} PAST OPPOSITION', f'{label} · OPPOSITION')
            timing = f"{n} DAY{'S' if n > 1 else ''} AGO · {when:%d %b}".upper()
        up = body['altitude_deg'] > 0
        where = (pick(c, inset, f"IN {body['constellation'].upper()} · ALT {round(body['altitude_deg'])}°",
                      f"{_symbol(body)} · ALT {round(body['altitude_deg'])}°", f"ALT {round(body['altitude_deg'])}°")
                 if up else f"RISES {_clock(body.get('rise'))}")
        out.append(beat(f'opposition-{name.lower()}',
                        [title, timing, f"MAG {_num(body['magnitude'])} · {_num(body['distance_au'], 2)} AU", where],
                        inset, name if up else None, priority=0, body=name))
    return out


def on_this_day(c):
    entries = ON_THIS_DAY.get((c['now'].month, c['now'].day), [])
    return [beat(f'on-this-day-{year}', [f'ON THIS DAY · {year}', first, second], priority=1)
            for year, first, second in entries]


def meteor_shower(c):
    if not c['shower']:
        return []
    return [beat('meteor-shower', [f"{c['shower'].upper()} ACTIVE", 'METEOR SHOWER TONIGHT', 'BEST AFTER MIDNIGHT'],
                 priority=2)]


def moon_extremes(c):
    moon, times = c['moon'], c['moon_times']
    if moon['illuminated_fraction'] >= .98:
        return [beat('full-moon', ['FULL MOON', f"MOONRISE {_clock(times.get('rise'))}", 'TOO BRIGHT FOR GALAXIES'],
                     'moon', priority=3)]
    if moon['illuminated_fraction'] <= .02:
        return [beat('new-moon', ['NEW MOON', 'DARK SKIES TONIGHT', 'GALAXY HUNTING'], 'moon', priority=3)]
    return []


# --- ordinary beats -------------------------------------------------------------------------------------------
def planets_up(c):
    if c['dark'] < .5:
        return []
    out = []
    for name in NAKED_EYE:
        body = c['planets'].get(name)
        if body and body['altitude_deg'] > 10:
            inset = _inset_for(name)
            title = pick(c, inset, f"{name.upper()} UP IN {body['constellation'].upper()}",
                         f"{name.upper()} UP IN {_symbol(body)}", f"{name.upper()} UP")
            out.append(beat(f'planet-up-{name.lower()}',
                            [title, f"MAG {_num(body['magnitude'])} · ALT {round(body['altitude_deg'])}°",
                             f"{_num(body['distance_au'], 2)} AU AWAY"], inset, name, weight=3))
    return out


def planets_rising(c):
    out = []
    for name in NAKED_EYE:
        body = c['planets'].get(name)
        rise = _time(body.get('rise')) if body else None
        if body and body['altitude_deg'] <= 0 and rise and c['now'] < rise <= c['now']+timedelta(hours=10):
            inset = _inset_for(name)
            out.append(beat(f'planet-rising-{name.lower()}',
                            [f'{name.upper()} RISES {rise:%H:%M}', _in(c, inset, body),
                             f"MAG {_num(body['magnitude'])}"], inset, weight=2, body=name))
    return out


def jupiter_moons(c):
    body, moons = c['planets'].get('Jupiter'), c['astronomy'].get('jupiter_moons')
    if not body or not moons or body['altitude_deg'] <= 5 or c['dark'] < .5:
        return []
    order = ''.join(name[0] for name, _ in sorted(moons.items(), key=lambda item: -item[1][0]))
    return [beat('jupiter-moons', ['GALILEAN MOONS', f'EAST {order} WEST', 'REAL POSITIONS TONIGHT'],
                 'jupiter', 'Jupiter', weight=3)]


def outer_planets(c):
    if c['dark'] < .5:
        return []
    up = [name for name in ('Uranus', 'Neptune') if c['planets'].get(name, {}).get('altitude_deg', -1) > 15]
    if not up:
        return []
    body, label = c['planets'][up[0]], up[0].upper()
    title = pick(c, 'planet', f'{label} IN {body["constellation"].upper()}', f'{label} IN {_symbol(body)}', label)
    mag = f"MAG {_num(body['magnitude'])}"
    return [beat(f'ice-giant-{up[0].lower()}', [title, pick(c, 'planet', f'{mag} · TELESCOPE ONLY', f'{mag} · SCOPE ONLY', mag),
                                                f"{_num(body['distance_au'], 1)} AU AWAY"], 'planet', weight=1,
                 body=up[0])]


MOON_PHASES = ((.03, 'NEW MOON'), (.35, 'CRESCENT'), (.65, 'QUARTER'), (.97, 'GIBBOUS'), (1.01, 'FULL MOON'))


def moon_phase(c):
    moon, times = c['moon'], c['moon_times']
    fraction = moon['illuminated_fraction']
    name = next(label for limit, label in MOON_PHASES if fraction < limit)
    if name in ('CRESCENT', 'GIBBOUS'):
        name = ('WAXING ' if moon['waxing'] else 'WANING ')+name
    elif name == 'QUARTER':
        name = 'FIRST QUARTER' if moon['waxing'] else 'LAST QUARTER'
    up = moon['altitude_deg'] > 0
    when = f"MOONSET {_clock(times.get('set'))}" if up else f"MOONRISE {_clock(times.get('rise'))}"
    return [beat('moon-phase', [name, f'{round(100*fraction)}% LIT', when], 'moon', weight=2)]


def sun_events(c):
    now, times = c['now'], c['sun_times']
    sunrise, sunset = _time(times.get('sunrise')), _time(times.get('sunset'))
    dawn, dusk = _time(times.get('civil_dawn')), _time(times.get('civil_dusk'))
    out = []
    if sunset and timedelta(0) < sunset-now <= timedelta(minutes=90):
        out.append(beat('sunset-soon', [f'SUNSET {sunset:%H:%M}', 'ROOF OPENS AT DUSK'], weight=4))
    if sunset and dusk and sunset <= now <= dusk+timedelta(minutes=60):
        out.append(beat('dusk', [f'CIVIL DUSK {dusk:%H:%M}', 'OPTICS COOLING DOWN'], weight=4))
    if dawn and sunrise and dawn-timedelta(minutes=60) <= now <= sunrise+timedelta(minutes=30):
        out.append(beat('dawn', [f'CIVIL DAWN {dawn:%H:%M}', 'CLOSING THE ROOF', 'LOGGING THE NIGHT'], weight=4))
    if c['dark'] < .5 and sunrise and sunset:
        length = sunset-sunrise
        hours, minutes = divmod(round(length.total_seconds()/60), 60)
        out.append(beat('daylight', [f"SUN ALT {round(c['sun']['altitude_deg'])}°", f'DAY LENGTH {hours}H {minutes}M',
                                     f'SUNSET {sunset:%H:%M}'], weight=2))
    return out


def weather(c):
    o = c['observation']
    if not o:
        return []
    out = []
    condition = o['condition']
    if condition in ('clear', 'partly-cloudy') and c['dark'] >= .5:
        out.append(beat('clear-night', ['CLEAR SKIES OVER MUMBAI', f"CLOUD COVER {round(o['cloud_cover_pct'])}%",
                                        f"HUMIDITY {round(o['humidity_pct'])}%"], weight=3))
    if o['cloud_cover_pct'] >= 70 and condition not in ('drizzle', 'rain', 'heavy-rain', 'thunderstorm'):
        out.append(beat('clouds', ['CLOUDS OVER MUMBAI', f"CLOUD COVER {round(o['cloud_cover_pct'])}%",
                                   'WAITING FOR A GAP'], weight=3))
    if condition in ('drizzle', 'rain'):
        out.append(beat('rain', ['RAIN OVER MUMBAI', f"{_num(o['precipitation_mm'])} MM IN 15 MIN", 'ROOF CLOSED'],
                        weight=4))
    if o['temperature_c'] >= 33:
        out.append(beat('hot', ['HOT NIGHT IN MUMBAI' if c['dark'] >= .5 else 'HOT DAY IN MUMBAI', f"{_num(o['temperature_c'])}°C · HUMIDITY {round(o['humidity_pct'])}%"],
                        weight=2))
    if o['humidity_pct'] >= 80 and c['dark'] >= .5:
        out.append(beat('humid', ['HUMID NIGHT', f"HUMIDITY {round(o['humidity_pct'])}%", 'WATCHING FOR DEW'], weight=2))
    if 20 <= o['wind_kmh'] and o['gust_kmh'] < 60:
        out.append(beat('breezy', ['BREEZY OVER THE FIELD', f"WIND {round(o['wind_kmh'])} KM/H",
                                   f"GUSTS {round(o['gust_kmh'])} KM/H"], weight=2))
    if not c['grounded']:
        out.append(beat('flights', ['FLIGHTS ON SCHEDULE', 'MUMBAI AIRSPACE OPEN'], weight=1))
    return out


def season(c):
    s = c['season']
    return [beat('season', [f"{s['name'].upper()} SEASON", SEASON_NOTES.get(s['id'], ''),
                            f"DAY {s['day_index_in_season']+1} OF {s['name'].upper()}"], weight=1)]


def night_sky(c):
    if c['dark'] < .5:
        return []
    out = [beat('m51', ['TELESCOPE ON M51', 'WHIRLPOOL GALAXY', 'IN CANES VENATICI'], weight=2)]
    if c['lst'] is not None:
        hours, minutes = divmod(round(c['lst']*60) % 1440, 60)
        out.append(beat('sidereal', ['LOCAL SIDEREAL TIME', f'{hours:02d}:{minutes:02d}',
                                     f'RA {hours}H{minutes:02d}M ON THE MERIDIAN'], weight=1))
    return out


def workshop(c):
    out = [beat('printer', ['3D PRINTER RUNNING', 'ROCKET MODEL ON THE BED'], weight=1),
           beat('lego', ['LEGO STARSHIP DOCKED', 'BRICKS SORTED BY COLOUR'], weight=1),
           beat('blueprint', ['BLUEPRINT ON THE SCREEN', 'STARSHIP WIREFRAME'], weight=1),
           beat('drone', ['DRONE HOVER TEST', 'HOLDING POSITION'], weight=1),
           beat('tracking', ['SKY TRACKING ONLINE', 'SUN · MOON · PLANETS'], weight=1)]
    if c['mood'] == 'rain':
        out.append(beat('rover-shelter', ['ROVER SHELTERING', 'SENSORS STAYING DRY'], weight=3))
    elif c['dark'] >= .5:
        out.append(beat('rover-patrol', ['ROVER ON NIGHT PATROL', 'LIDAR SWEEPING THE FIELD'], weight=2))
    if c['flicker']:
        out.append(beat('flicker', ['SHED POWER FLICKERS', 'CHECKING THE WIRING'], weight=1))
    return out


TEMPLATES = (oppositions, on_this_day, meteor_shower, moon_extremes, planets_up, planets_rising, jupiter_moons,
             outer_planets, moon_phase, sun_events, weather, season, night_sky, workshop)


def eligible(c):
    return [b for template in TEMPLATES for b in template(c)]


def choose(c, seed, count=2):
    """``count`` different beats: every eligible priority beat first (by rank), then weighted picks."""
    beats = eligible(c)
    rng = random.Random(seed)
    chosen = sorted((b for b in beats if b['priority'] is not None), key=lambda b: (b['priority'], b['id']))[:count]
    pool = [b for b in beats if b['priority'] is None]
    while len(chosen) < count and pool:
        pick = rng.choices(pool, weights=[b['weight'] for b in pool])[0]
        chosen.append(pick)
        pool = [b for b in pool if b['id'] != pick['id'] and not (pick['target'] and b['target'] == pick['target'])]
    return chosen
