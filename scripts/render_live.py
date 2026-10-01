#!/usr/bin/env python3
"""Render the observatory for one moment: live.svg (animated), live.png (still) and live.json (the SceneState).

All three files are built in a temporary directory beside the destination, validated, and only then moved into
place, so a failed run never leaves a half-written or mismatched set behind.
"""
import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import tempfile
import xml.etree.ElementTree as ET
from zoneinfo import ZoneInfo

import build_animation as scene
import scene_state

MIN_SVG_BYTES = 100_000   # the embedded plate alone is several MB
MIN_PNG_BYTES = 10_000


def validate_svg(path):
    if path.stat().st_size < MIN_SVG_BYTES:
        raise ValueError(f'{path.name} is too small ({path.stat().st_size} bytes)')
    root = ET.parse(path).getroot()
    if (root.get('width'), root.get('height')) != (str(scene.W), str(scene.H)):
        raise ValueError(f'{path.name} has unexpected dimensions')


def validate_png(path, width):
    from PIL import Image
    if path.stat().st_size < MIN_PNG_BYTES:
        raise ValueError(f'{path.name} is too small ({path.stat().st_size} bytes)')
    with Image.open(path) as image:
        image.load()
        expected = (width, round(width*scene.H/scene.W))
        if abs(image.width-expected[0]) > 1 or abs(image.height-expected[1]) > 1:
            raise ValueError(f'{path.name} is {image.size}, expected about {expected}')


def validate_json(path):
    state = json.loads(path.read_text())
    for key in ('timestamp_local', 'astronomy', 'lighting'):
        if key not in state:
            raise ValueError(f'{path.name} lacks {key}')


def render(when, out, png_width=scene.GIF_WIDTH, config=None):
    """Write live.svg/live.png/live.json for ``when`` into ``out``; returns the SceneState."""
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    state = scene_state.scene_state(when, config)
    with tempfile.TemporaryDirectory(prefix='.live-', dir=out) as directory:
        temp = Path(directory)
        (temp/'live.svg').write_text(scene.scene(animated=True, state=state))
        still = temp/'still.svg'
        still.write_text(scene.scene(0, False, state=state))
        scene.rasterize(still, temp/'live.png', png_width)
        still.unlink()
        (temp/'live.json').write_text(json.dumps(state, indent=2)+'\n')
        validate_svg(temp/'live.svg')
        validate_png(temp/'live.png', png_width)
        validate_json(temp/'live.json')
        for name in ('live.svg', 'live.png', 'live.json'):   # only reached when every file is valid
            os.replace(temp/name, out/name)
    return state


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--at', help='aware ISO 8601 time (default: now in the configured time zone)')
    parser.add_argument('--out', default='live', help='output directory')
    parser.add_argument('--png-width', type=int, default=scene.GIF_WIDTH)
    args = parser.parse_args()
    config = scene_state.load_config()
    when = datetime.fromisoformat(args.at) if args.at else datetime.now(ZoneInfo(config['location']['timezone']))
    state = render(when, args.out, args.png_width, config)
    sun = state['astronomy']['sun']
    print(f'{state["timestamp_local"]} sun {sun["altitude_deg"]:.1f} deg az {sun["azimuth_deg"]:.1f} '
          f'daylight {state["lighting"]["daylight"]} -> {args.out}')


if __name__ == '__main__':
    main()
