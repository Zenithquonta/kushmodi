"""Markdown gallery pages for the daily archive (stdlib only; used by archive_tool.py on the server).

archive/README.md shows the latest day large, the six before it smaller, and links to one page per month
(archive/YYYY/YYYY-MM.md). Pages are a pure function of the merged index and the frames present, with no timestamps,
so regenerating an unchanged archive changes nothing. Index fields are checked against fixed vocabularies before they
reach a public page; anything unexpected is dropped, not escaped.
"""
from datetime import date
import re

SEASONS = dict(vasanta='Vasanta', grishma='Grishma', varsha='Varsha', sharad='Sharad', hemanta='Hemanta',
               shishira='Shishira')
PLANETS = ('Mercury', 'Venus', 'Mars', 'Jupiter', 'Saturn')
SHOWER = re.compile(r'^[A-Z][a-z]{2,20}$')
DAY = re.compile(r'^(\d{4})-(\d{2})-(\d{2})$')
LATEST_DAYS = 7


def clean(entry):
    """The few facts a page shows, each validated; missing or unexpected values become None or are left out."""
    entry = entry if isinstance(entry, dict) else {}
    season = SEASONS.get(entry.get('season'))
    moon = entry.get('moon_illuminated')
    moon = moon if isinstance(moon, (int, float)) and not isinstance(moon, bool) and 0 <= moon <= 1 else None
    shower = entry.get('meteor_shower')
    shower = shower if isinstance(shower, str) and SHOWER.match(shower) else None
    planets = entry.get('planets_at_night')
    planets = [p for p in PLANETS if isinstance(planets, list) and p in planets]
    return dict(season=season, moon=moon, shower=shower, planets=planets)


def label(day, year=True):
    d = date.fromisoformat(day)
    return f'{d.day} {d:%b}' + (f' {d.year}' if year else '')


def notes(facts):
    parts = [facts['season']] if facts['season'] else []
    if facts['moon'] is not None:
        parts.append(f'moon {round(facts["moon"]*100)}%')
    if facts['shower']:
        parts.append(f'{facts["shower"]} meteor shower')
    if facts['planets']:
        parts.append(', '.join(facts['planets']))
    return ' · '.join(parts)


def alt(day, kind, facts):
    when = 'noon' if kind == 'day' else '21:00'
    extra = ', '.join(p for p in (facts['season'], facts['moon'] is not None and f'moon {round(facts["moon"]*100)}%') if p)
    return f'{label(day)}, {when}' + (f', {extra}' if extra else '')


def archived_days(index, dest):
    """Dates in the index whose two frames are present in ``dest``, newest first."""
    days = []
    for day in index.get('frames', {}):
        match = DAY.match(day)
        if match and all((dest/match.group(1)/f'{day}-{kind}.webp').is_file() for kind in ('day', 'night')):
            days.append(day)
    return sorted(days, reverse=True)


def image(src, day, kind, facts, width):
    return f'<img src="{src}" width="{width}" alt="{alt(day, kind, facts)}">'


def front_page(days, index):
    frames = index.get('frames', {})
    lines = ['# Sky archive', '',
             'One frame at local solar noon and one at 21:00, every day, rendered by the live observatory over Mumbai.', '']
    if not days:
        return '\n'.join(lines+['The first frames arrive with the first daily run.', ''])
    latest, facts = days[0], clean(frames[days[0]])
    lines += [f'## {label(latest)}', '', notes(facts), '',
              '<table><tr>',
              f'<td>{image(f"{latest[:4]}/{latest}-day.webp", latest, "day", facts, "100%")}</td>',
              f'<td>{image(f"{latest[:4]}/{latest}-night.webp", latest, "night", facts, "100%")}</td>',
              '</tr></table>', '']
    if len(days) > 1:
        lines += ['## Earlier days', '', '| Date | Noon | 21:00 | Sky |', '| --- | --- | --- | --- |']
        for day in days[1:LATEST_DAYS]:
            f = clean(frames[day])
            lines.append(f'| {label(day)} | {image(f"{day[:4]}/{day}-day.webp", day, "day", f, 220)} | '
                         f'{image(f"{day[:4]}/{day}-night.webp", day, "night", f, 220)} | {notes(f)} |')
        lines.append('')
    lines += ['## Months', '']
    months = sorted({day[:7] for day in days}, reverse=True)
    for month in months:
        count = sum(1 for day in days if day.startswith(month))
        name = date.fromisoformat(month+'-01')
        lines.append(f'- [{name:%B} {name.year}]({month[:4]}/{month}.md) ({count} {"day" if count == 1 else "days"})')
    return '\n'.join(lines+[''])


def month_page(month, days, index):
    frames = index.get('frames', {})
    name = date.fromisoformat(month+'-01')
    lines = [f'# {name:%B} {name.year}', '', '[Sky archive](../README.md)', '',
             '| Date | Noon | 21:00 | Sky |', '| --- | --- | --- | --- |']
    for day in sorted((d for d in days if d.startswith(month)), reverse=True):
        f = clean(frames[day])
        lines.append(f'| {label(day, year=False)} | {image(f"{day}-day.webp", day, "day", f, 280)} | '
                     f'{image(f"{day}-night.webp", day, "night", f, 280)} | {notes(f)} |')
    return '\n'.join(lines+[''])


def pages(index, dest):
    """{relative path: markdown} for the whole gallery."""
    days = archived_days(index, dest)
    out = {'README.md': front_page(days, index)}
    for month in sorted({day[:7] for day in days}):
        out[f'{month[:4]}/{month}.md'] = month_page(month, days, index)
    return out
