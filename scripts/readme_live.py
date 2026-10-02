#!/usr/bin/env python3
"""Switch the README hero between the repo-hosted animation and the VPS live view, or back.

    python scripts/readme_live.py status
    python scripts/readme_live.py live --host sky.example.com   # after deploy/check.sh passes on that host
    python scripts/readme_live.py repo                          # back to the repo animation, byte for byte

Only the block between <!-- hero:start --> and <!-- hero:end --> changes; the host is stored in
config/observatory.json (it is public, not a secret). GitHub cannot fall back automatically when an image fails to
load, so live mode also shows a link to the repo animation, and switching back is one command.
"""
import argparse
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
README = ROOT/'README.md'
CONFIG = ROOT/'config'/'observatory.json'
START, END = '<!-- hero:start -->\n', '<!-- hero:end -->\n'
HOST = re.compile(r'^([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$')   # the same rule as deploy/install.sh

REPO_HERO = '''<picture>
  <source media="(prefers-reduced-motion: reduce)" srcset="./assets/observatory-poster.png" />
  <img src="./assets/observatory.gif" width="100%" alt="Kush Modi's pixel observatory: telescope under a galaxy, orbiting moons, passing spacecraft, and an illuminated maker workshop" />
</picture>
'''


def live_hero(host):
    return f'''<picture>
  <source media="(prefers-reduced-motion: reduce)" srcset="https://{host}/live.png" />
  <img src="https://{host}/live.svg" width="100%" alt="Kush Modi's observatory live from Mumbai: the real sky, season and weather over the telescope and maker workshop, redrawn through the day" />
</picture>

<sub>Live from Mumbai, redrawn through the day · if it does not load, <a href="./assets/observatory.gif">open the animated observatory</a></sub>
'''


def split(text):
    if text.count(START) != 1 or text.count(END) != 1 or text.index(START) > text.index(END):
        raise ValueError('README must contain exactly one hero:start/hero:end pair')
    head, rest = text.split(START)
    hero, tail = rest.split(END)
    return head, hero, tail


def mode(text):
    hero = split(text)[1]
    if hero == REPO_HERO:
        return 'repo'
    match = re.search(r'src="https://([^/"]+)/live\.svg"', hero)
    if match and hero == live_hero(match.group(1)):
        return f'live ({match.group(1)})'
    return 'custom'


def switch(text, host=None):
    """README text with the hero in repo mode (host None) or live mode for ``host``."""
    if host is not None and not HOST.match(host):
        raise ValueError(f'not a valid lowercase host name: {host!r}')
    head, _, tail = split(text)
    return head+START+(REPO_HERO if host is None else live_hero(host))+END+tail


def set_host(config_text, host):
    """The config text with only live.host changed, so the hand-kept layout survives."""
    pattern = re.compile(r'("live": \{[^}]*?"host": )(null|"[^"]*")', re.S)
    if not pattern.search(config_text):
        raise ValueError('config/observatory.json has no live.host')
    new = pattern.sub(lambda m: m.group(1)+json.dumps(host), config_text, count=1)
    assert json.loads(new)['live']['host'] == host
    return new


def main():
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('status')
    live = sub.add_parser('live')
    live.add_argument('--host', required=True)
    sub.add_parser('repo')
    args = parser.parse_args()
    text = README.read_text()
    if args.command == 'status':
        print(mode(text))
        return
    host = args.host if args.command == 'live' else None
    try:
        new = switch(text, host)
    except ValueError as error:
        sys.exit(f'readme_live: {error}')
    README.write_text(new)
    CONFIG.write_text(set_host(CONFIG.read_text(), host))
    print(f'README hero: {mode(new)}')


if __name__ == '__main__':
    main()
