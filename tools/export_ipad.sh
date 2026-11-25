#!/bin/sh
# Export the iPad Xcode project. Requires Godot 4.7 and full Xcode on macOS.
# Usage: tools/export_ipad.sh [output-directory]
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
GODOT=${GODOT:-"$ROOT/../tools/Godot.app/Contents/MacOS/Godot"}
DEVELOPER_DIR=${DEVELOPER_DIR:-/Applications/Xcode.app/Contents/Developer}
OUTPUT=${1:-"$ROOT/../local/releases/OpenSC2K-iPad"}

if [ ! -x "$GODOT" ]; then
	echo "Godot not found at $GODOT; set GODOT to the Godot 4.7 executable." >&2
	exit 1
fi

if [ ! -d "$DEVELOPER_DIR" ]; then
	echo "Xcode not found at $DEVELOPER_DIR; set DEVELOPER_DIR to Xcode.app/Contents/Developer." >&2
	exit 1
fi

export DEVELOPER_DIR
exec "$GODOT" --headless --audio-driver Dummy --path "$ROOT/game" \
	--export-debug "iPad" "$OUTPUT"
