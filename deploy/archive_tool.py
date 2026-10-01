#!/usr/bin/env python3
"""Stage the server's archive into the sync clone: well-formed WebP frames, a merged index and gallery pages (stdlib).

    python3 archive_tool.py stage /var/lib/observatory/archive /var/lib/obsync/repo/archive

Runs as the sync user from the read-only code checkout, never from the clone it writes to. Holds a shared lock on the
source so it never copies an index in the middle of a render. The index is merged as a union, the server's entry
winning for the same date, so a reinstalled server with an empty archive cannot wipe the history in git.
"""
import argparse
import fcntl
import json
import os
from pathlib import Path
import re
import sys
import tempfile

import archive_gallery   # sits beside this file in the read-only code checkout

FRAME = re.compile(r'^(\d{4})/(\d{4})-(\d{2})-(\d{2})-(day|night)\.webp$')
MAX_FRAME_BYTES = 2_000_000


class Refused(Exception):
    pass


def check_frame(src, rel):
    path = src/rel
    match = FRAME.match(rel)
    if not match or match.group(1) != match.group(2):
        raise Refused(f'unexpected file name: {rel}')
    if path.is_symlink() or not path.is_file():
        raise Refused(f'not a regular file: {rel}')
    size = path.stat().st_size
    if not 0 < size <= MAX_FRAME_BYTES:
        raise Refused(f'{rel} has an implausible size ({size} bytes)')
    with open(path, 'rb') as handle:
        head = handle.read(12)
    if head[:4] != b'RIFF' or head[8:12] != b'WEBP':
        raise Refused(f'{rel} is not a WebP file')


def _write_atomic(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile('wb', dir=path.parent, prefix='.stage-', delete=False) as handle:
        handle.write(data)
    os.replace(handle.name, path)


def merge_index(existing, incoming):
    frames = dict(existing.get('frames', {}))
    for day, entry in incoming.get('frames', {}).items():
        if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', day):
            raise Refused(f'unexpected index date: {day}')
        for kind in ('day', 'night'):
            if not FRAME.match(entry['files'][kind]['path']):
                raise Refused(f'unexpected index path for {day}')
        frames[day] = entry
    return dict(version=incoming.get('version', existing.get('version', 1)), frames=dict(sorted(frames.items())))


def stage(src, dest):
    """Copy every valid frame that differs and merge the index; returns the dates whose frames changed."""
    src, dest = Path(src), Path(dest)
    if not (src/'index.json').exists():
        return []
    with open(src/'.lock') as lock:
        fcntl.flock(lock, fcntl.LOCK_SH)
        names = sorted(p.relative_to(src).as_posix() for p in src.rglob('*.webp')
                       if not any(part.startswith('.') for part in p.relative_to(src).parts))
        for rel in names:
            check_frame(src, rel)
        incoming = json.loads((src/'index.json').read_text())
        changed = set()
        for rel in names:
            data = (src/rel).read_bytes()
            target = dest/rel
            if not target.exists() or target.read_bytes() != data:
                _write_atomic(target, data)
                changed.add(rel.split('/')[1][:10])
    existing = json.loads((dest/'index.json').read_text()) if (dest/'index.json').exists() else {}
    merged = merge_index(existing, incoming)
    text = json.dumps(merged, indent=1)+'\n'
    if not (dest/'index.json').exists() or (dest/'index.json').read_text() != text:
        _write_atomic(dest/'index.json', text.encode())
    for rel, page in archive_gallery.pages(merged, dest).items():   # gallery pages, deterministic
        if not (dest/rel).exists() or (dest/rel).read_text() != page:
            _write_atomic(dest/rel, page.encode())
    return sorted(changed)


def main():
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('command', choices=['stage'])
    parser.add_argument('src')
    parser.add_argument('dest')
    args = parser.parse_args()
    try:
        print(' '.join(stage(args.src, args.dest)))
    except Refused as error:
        print(f'archive_tool: refused: {error}', file=sys.stderr)
        sys.exit(2)


if __name__ == '__main__':
    main()
