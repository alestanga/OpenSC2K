# iPadOS port (prototype)

This document tracks the work to run OpenSC2K on an iPad. The first prototype
targets an iPad Air with a Magic Keyboard and trackpad. Touch gestures and a
touch-first UI are deliberately deferred.

## Target and signing

- Device used for testing: iPad Air 11-inch (M3), iPadOS 27.2.
- Apple Developer Team ID: `5NLYCB4UAX` (reused from the wowee iPadOS port).
- Bundle identifier: `net.22b5.opensc2k` (same as the macOS app; bundle IDs are
  not shared across platforms in a conflicting way).
- The Mac has full Xcode installed. `xcode-select` still points at the Command
  Line Tools, so commands that need the iOS SDK use
  `DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer`.
- The login keychain can re-lock; if Xcode codesigning fails with
  `errSecInternalComponent`, unlock the Mac and retry.

## Toolchain

Installed on this Mac for the port:

- Godot 4.7 stable (project requirement) and its export templates.
- Rust 1.100 with `aarch64-apple-ios` and `aarch64-apple-ios-sim` targets.
- Xcode 27.2 with the iOS 27.2 SDK.

From a fresh checkout, the setup is:

```sh
rustup target add aarch64-apple-ios aarch64-apple-ios-sim
python3 tools/build_native.py --ios
```

`--ios` builds only the five Godot GDExtension crates. The standalone desktop
binary (`native/app`, X11/Wayland) is not part of the iOS build.

## How the iOS build fits together

1. `tools/build_native.py --ios` cross-compiles the five bridge crates for
   `aarch64-apple-ios` and copies the dylibs into
   `game/bin/opensc2k_<module>/ios/`.
2. The `.gdextension` files list `ios.debug` and `ios.release` library paths.
3. The Godot iOS exporter turns dylibs into signed `.framework` bundles inside
   the generated Xcode project and codesigns them. No custom export template is
   needed for this step.
4. The `iPad` export preset in `game/export_presets.cfg` targets iPad only,
   forces landscape, and enables ETC2/ASTC textures. The renderer override in
   `game/project.godot` selects the Mobile renderer on iOS (Metal), while the
   simulator keeps the Compatibility renderer.

## Bundling the original game assets

The iPad has no mounted game folder and the game's file dialogs use the
desktop filesystem, so the prototype carries imported packs inside the app:

```sh
# from the repository root; the source folder is the user's own game files
godot --headless --audio-driver Dummy --path game \
  --script tools/export_original_packs.gd -- /path/to/SIMCITY2000 ext
python3 tools/bundle_packs_for_ipad.py
```

`game/bundled_packs/` is git-ignored because it holds copyrighted original
media. The original files are never modified.

Copy the packs into the app container on the device after the first launch:

```sh
tools/install_packs_on_ipad.sh
```

The game looks in `<user://>/packs`, which on iOS is `Documents/packs` inside
the app's data container. The `res://bundled_packs` fallback in
`MediaPack.default_folder()` is a secondary path; copying the packs into
`Documents/packs` is what makes them load reliably on the current iPadOS build.
The iPad preset still includes `bundled_packs/*` in the export.

Export an Xcode project:

```sh
DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer \
  "$GODOT" --headless --path game --export-debug "iPad" ../local/releases/OpenSC2K-iPad
```

## Simulator path (no device registration needed)

The simulator uses the Compatibility renderer and its own dylibs:

```sh
python3 tools/build_native.py --ios --ios-simulator
DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer \
  godot --headless --audio-driver Dummy --path game \
  --export-debug "iOS Simulator" ../local/sim/OpenSC2K-iPadSimulator
DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer \
  xcodebuild -project ../local/sim/OpenSC2K-iPadSimulator.xcodeproj \
    -scheme OpenSC2K-iPadSimulator -configuration Debug \
    -destination 'generic/platform=iOS Simulator' \
    CODE_SIGNING_ALLOWED=NO CODE_SIGNING_REQUIRED=NO \
    -derivedDataPath ../local/sim/derived build
xcrun simctl boot 2A9BAA34-EE16-4053-A2AE-1DB47CC3BB95
xcrun simctl install booted ../local/sim/derived/Build/Products/Debug-iphonesimulator/OpenSC2K-iPadSimulator.app
xcrun simctl launch booted net.22b5.opensc2k.simulator
xcrun simctl io booted screenshot /tmp/opensc2k-sim.png
```

Keep the simulator export in a directory with no other iOS export beside it.
Godot's generated project searches `$(PROJECT_DIR)/**` for frameworks, so a
sibling device export would otherwise supply arm64-device dylibs to the
simulator link.

Then build, install, launch and inspect on the paired iPad:

```sh
DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer \
  xcodebuild -project ../local/releases/OpenSC2K-iPad/OpenSC2K-iPad.xcodeproj \
    -scheme OpenSC2K-iPad -configuration Debug \
    -destination 'id=00008122-001A05EC0CFA401C' build

xcrun devicectl device install app --device 00008122-001A05EC0CFA401C <path-to-app>
xcrun devicectl device process launch --device 00008122-001A05EC0CFA401C net.22b5.opensc2k
xcrun devicectl device capture screenshot --device 00008122-001A05EC0CFA401C \
  --destination /tmp/opensc2k-ipad.png
```

## Status

Done:

- iOS export preset and renderer override.
- iOS entries in all five `.gdextension` files.
- iOS device and simulator cross-builds of the native extensions. Device
  dylibs link the device compiler-rt for QuickJS; simulator dylibs keep debug
  symbols (`-C strip=none`) because Xcode 27 rejects the 4-byte-aligned
  LINKEDIT string pool from stripped simulator dylibs.
- A Python 3.11 compatibility fallback in `tools/build_fluidsynth.py` so the
  desktop FluidSynth build works with the system Python on this Mac.
- An `export_ipad.sh` helper that sets `DEVELOPER_DIR` and runs the export.
- An iOS fallback to bundled original-game packs, plus a script to copy them
  into the project before export.
- iPad-specific UI rules: no Exit button, no hidden custom mouse cursor.

Verified on device:

- The signed Xcode project exports, installs and launches on the iPad Air.
- The main menu shows with live buttons, the original city background, no Exit
  button, and no Import Assets prompt once packs are in `Documents/packs`.
- Install over the existing app with `devicectl device install app` instead of
  uninstalling first; uninstalling clears the developer-trust record and makes
  iOS ask for approval again.

Not yet done (ordered by priority):

1. A proper iOS asset import flow. `FileDialog.ACCESS_FILESYSTEM` is
   desktop-only; for now packs are copied in with `install_packs_on_ipad.sh`.
3. Music: the iOS build has no FluidSynth library and no SoundFont. The audio
   extension loads but reports FluidSynth unavailable. Building FluidSynth for
   iOS also needs a decision on the LGPL replaceability requirement.
4. UI: fixed 1280x800 whole-pixel scaling, dense 32 px toolbar buttons, a
   custom hidden mouse cursor, and an Exit button need iPad-specific rules.
   Safe-area insets are not applied yet.
5. Input: Godot's iOS backend reports touch events and emulates mouse events
   from them. Raw trackpad pointer support in Godot is incomplete, so confirm
   pointer motion and right-click behaviour on the device before planning any
   touch gestures. The custom binding system accepts only `InputEventKey` and
   `InputEventMouse*` and will need a touch path later.
6. Mods, script storage, clipboard and "Open Mods Folder" assume desktop paths
   and a shell `open` command; review before a release build.

## Known constraints

- The iOS simulator only supports the Compatibility renderer, while the device
  build uses Metal. A separate simulator preset with a custom `simulator`
  feature tag and Compatibility renderer is a later step.
- The JavaScript runtime uses vendored QuickJS compiled with `cc`. The iOS
  build passes the iOS SDK to `cc` through target-specific `CC_*`/`CFLAGS_*`
  environment variables.
- The remote API and validation suites run on macOS; they are not available
  inside the iOS app. Use the iPad log and screenshots for device validation.
