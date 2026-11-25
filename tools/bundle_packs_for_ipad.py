#!/usr/bin/env python3
"""Copy locally imported original-game packs into the Godot project.

The iOS prototype has no way to point the game at a mounted game folder, so the
four imported packs are bundled as resources. This script copies the output of
tools/export_original_packs.gd (normally ext/) into game/bundled_packs/, which
is git-ignored because it contains copyrighted original media.

Usage: python3 tools/bundle_packs_for_ipad.py [source-directory]
"""
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / 'ext'
DESTINATION = ROOT / 'game' / 'bundled_packs'
KINDS = ('graphics', 'sound', 'music', 'data')


def main():
    for kind in KINDS:
        source = SOURCE / kind
        if not (source / 'pack.json').is_file():
            print(f'Missing pack: {source / "pack.json"}', file=sys.stderr)
            print('Run tools/export_original_packs.gd first.', file=sys.stderr)
            return 1

        target = DESTINATION / kind
        shutil.rmtree(target, ignore_errors=True)
        shutil.copytree(source, target)
        print(f'Bundled {target.relative_to(ROOT)}')

    return 0


if __name__ == '__main__':
    sys.exit(main())
