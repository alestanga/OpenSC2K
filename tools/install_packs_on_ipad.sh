#!/bin/sh
# Copy imported original-game packs into the iPad app's Documents folder.
# The game looks in <user://>/packs, so this makes the packs available without
# an in-game import dialog. Install the app once before running this script.
# Usage: tools/install_packs_on_ipad.sh [device-udid] [source-directory]
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
DEVICE=${1:-00008122-001A05EC0CFA401C}
SOURCE=${2:-"$ROOT/game/bundled_packs"}
DEVELOPER_DIR=${DEVELOPER_DIR:-/Applications/Xcode.app/Contents/Developer}

if [ ! -f "$SOURCE/graphics/pack.json" ]; then
	echo "No graphics pack in $SOURCE. Run tools/bundle_packs_for_ipad.py first." >&2
	exit 1
fi

export DEVELOPER_DIR
xcrun devicectl device copy to \
	--device "$DEVICE" \
	--source "$SOURCE" \
	--destination Documents/packs \
	--domain-type appDataContainer \
	--domain-identifier net.22b5.opensc2k

SOUNDFONT="$SOURCE/soundfont/FluidR3Mono_GM.sf3"
if [ -f "$SOUNDFONT" ]; then
	xcrun devicectl device copy to \
		--device "$DEVICE" \
		--source "$SOUNDFONT" \
		--destination Documents/FluidR3Mono_GM.sf3 \
		--domain-type appDataContainer \
		--domain-identifier net.22b5.opensc2k
fi
