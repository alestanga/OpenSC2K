#!/usr/bin/env python3
"""Download the MIT FluidR3 Mono GM SoundFont for the iPad prototype.

The file is kept beside the imported packs in game/bundled_packs, which is
git-ignored. tools/install_packs_on_ipad.sh copies it into the app container.
"""
import hashlib
import shutil
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
URL = ('https://raw.githubusercontent.com/musescore/MuseScore/v2.3.2/'
       'share/sound/FluidR3Mono_GM.sf3')
SHA256 = 'cfcd66d89e8386823400eca64934b14fbea7bf48ba1f00d21189af1262794ec2'
TARGET = ROOT / 'game' / 'bundled_packs' / 'soundfont' / 'FluidR3Mono_GM.sf3'


def main():
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    if TARGET.is_file() and hashlib.sha256(TARGET.read_bytes()).hexdigest() == SHA256:
        print(f'SoundFont already present: {TARGET.relative_to(ROOT)}')
        return 0

    staged = TARGET.with_name(TARGET.name + '.part')
    with urllib.request.urlopen(URL, timeout=120) as response, staged.open('wb') as stream:
        shutil.copyfileobj(response, stream)
    actual = hashlib.sha256(staged.read_bytes()).hexdigest()
    if actual != SHA256:
        staged.unlink()
        raise SystemExit(f'SHA-256 is {actual}, expected {SHA256}')
    staged.replace(TARGET)
    print(f'SoundFont: {TARGET.relative_to(ROOT)}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
