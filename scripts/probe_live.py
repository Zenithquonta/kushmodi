#!/usr/bin/env python3
"""Probe the public live view before switching the README:  python scripts/probe_live.py sky.example.com

Checks the three URLs (status, content type, size, Cache-Control), that live.json is recent, and that nothing else
is served. Read-only; standard library only.
"""
from datetime import datetime, timezone
import json
import sys
import urllib.error
import urllib.request

EXPECTED = {'live.svg': 'image/svg+xml', 'live.png': 'image/png', 'live.json': 'application/json'}
MAX_AGE_MINUTES = 15


def fetch(url):
    request = urllib.request.Request(url, headers={'User-Agent': 'kushmodi-observatory-probe'})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.status, dict(response.headers), response.read()
    except urllib.error.HTTPError as error:
        return error.code, dict(error.headers), b''
    except (urllib.error.URLError, OSError) as error:
        return 0, {'Content-Type': f'unreachable ({getattr(error, "reason", error)})'}, b''


def probe(host):
    problems = []
    for name, kind in EXPECTED.items():
        status, headers, body = fetch(f'https://{host}/{name}')
        content_type = headers.get('Content-Type', '')
        print(f'/{name}: {status} {content_type} {len(body)} bytes, Cache-Control: {headers.get("Cache-Control")}')
        if status != 200 or not content_type.startswith(kind):
            problems.append(f'/{name} is {status} {content_type}')
        if name == 'live.json' and status == 200:
            stamp = datetime.fromisoformat(json.loads(body)['timestamp_utc'].replace('Z', '+00:00'))
            age = (datetime.now(timezone.utc)-stamp).total_seconds()/60
            print(f'  rendered {age:.1f} minutes ago')
            if age > MAX_AGE_MINUTES:
                problems.append(f'live.json is {age:.0f} minutes old')
    for path in ('/', '/index.json', '/.live-x/'):
        status = fetch(f'https://{host}{path}')[0]
        if status != 404:
            problems.append(f'{path} returned {status}, expected 404')
    return problems


if __name__ == '__main__':
    if len(sys.argv) != 2:
        sys.exit('usage: probe_live.py HOST')
    found = probe(sys.argv[1])
    print('\n'.join(['problems:']+found) if found else 'live view looks ready')
    sys.exit(1 if found else 0)
