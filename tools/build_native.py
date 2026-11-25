#!/usr/bin/env python3
"""Build the native libraries and copy them into the Godot project.

With no options, build the library for this computer. Use --package to build
the library that a desktop package needs on this platform: a universal library
on macOS, and the library of this architecture (x86_64 or arm64) on Windows
and Linux. Use --ios to build the five Godot extensions and FluidSynth for an
iPad or iPhone; the standalone desktop binary is not part of that build.

The audio library loads FluidSynth at run time. This also builds the FluidSynth
shared library (tools/build_fluidsynth.py, which needs CMake). Without it, no
MIDI music plays.
"""
import argparse
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

import build_fluidsynth

ROOT = Path(__file__).resolve().parents[1]
# one Cargo workspace holds every crate, so they share dependencies and build in parallel
WORKSPACE = ROOT / 'native'
TARGET = WORKSPACE / 'target'
MODULES = ('simulation', 'rendering', 'formats', 'audio', 'scripting')
MACOS_TARGETS = ('aarch64-apple-darwin', 'x86_64-apple-darwin')
# iOS extensions are loaded by Godot as dylibs. The Apple embedded exporter turns
# them into signed frameworks when it creates the Xcode project.
IOS_TARGET = 'aarch64-apple-ios'
IOS_SIMULATOR_TARGET = 'aarch64-apple-ios-sim'
IOS_PACKAGES = tuple(f'opensc2k_{module}' for module in MODULES)
# the Windows and Linux folders that desktop packages include, and their Rust targets.
# An explicit target stops an emulated x86_64 toolchain from building the wrong library
PACKAGE_TARGETS = {
    'linux-x86_64': 'x86_64-unknown-linux-gnu',
    'linux-arm64': 'aarch64-unknown-linux-gnu',
    'windows-x86_64': 'x86_64-pc-windows-msvc',
    'windows-arm64': 'aarch64-pc-windows-msvc',
}


def host_folder():
    machine = platform.machine().lower()
    arch = 'arm64' if machine in ('arm64', 'aarch64') else 'x86_64'
    if sys.platform == 'darwin':
        return 'macos'
    if sys.platform == 'win32':
        return f'windows-{arch}'
    return f'linux-{arch}'


def library_name(module):
    name = f'opensc2k_{module}'
    if sys.platform == 'darwin':
        return f'lib{name}.dylib'
    if sys.platform == 'win32':
        return f'{name}.dll'
    return f'lib{name}.so'


def _cargo(arguments, quiet):
    if shutil.which('cargo') is None:
        raise OSError('cargo is required to build the native libraries (https://rustup.rs)')
    command = ['cargo', *arguments, '--workspace']
    if quiet:
        command.append('--quiet')
    subprocess.run(command, cwd=WORKSPACE, check=True)


def _cargo_packages(arguments, packages, quiet, environment=None):
    """Build named packages instead of the whole workspace (the app crate is desktop-only)."""
    command = ['cargo', 'build', *arguments]
    for package in packages:
        command.extend(['-p', package])
    if quiet:
        command.append('--quiet')
    subprocess.run(command, cwd=WORKSPACE, check=True, env=environment)


def _add_targets(triples):
    subprocess.run(['rustup', 'target', 'add', *triples], cwd=WORKSPACE, check=True)


def _apple_sdk_environment(triple, sdk):
    """Point the cc crate at the iOS SDK for vendored C code (QuickJS)."""
    def xcrun(*arguments):
        return subprocess.check_output(['xcrun', '--sdk', sdk, *arguments], text=True).strip()

    environment = dict(os.environ)
    # The cc crate looks up these variables with a lowercase target prefix.
    prefix = triple.replace('-', '_')
    version_flag = '-mios-simulator-version-min=17.0' if sdk == 'iphonesimulator' else '-miphoneos-version-min=17.0'
    environment[f'CC_{prefix}'] = xcrun('--find', 'clang')
    # A larger probe size keeps QuickJS from calling ___chkstk_darwin, which
    # would otherwise need the target-specific compiler-rt archive.
    environment[f'CFLAGS_{prefix}'] = f'-isysroot {xcrun("--show-sdk-path")} {version_flag} -mstack-probe-size=65536'

    flags = []

    if sdk == 'iphoneos':
        # The device objects still call ___chkstk_darwin. It lives in
        # compiler-rt, which Rust does not link for iOS.
        resource_dir = subprocess.check_output(['xcrun', '--sdk', sdk, 'clang', '-print-resource-dir'], text=True).strip()
        runtime = Path(resource_dir) / 'lib' / 'darwin'
        flags.extend(['-C', f'link-arg=-L{runtime}', '-C', 'link-arg=-lclang_rt.ios'])
    else:
        # Xcode 27's linker rejects a simulator dylib whose LINKEDIT string
        # pool is only 4-byte aligned; Rust's debuginfo stripping causes it.
        flags.extend(['-C', 'strip=none'])

    environment[f'CARGO_TARGET_{prefix.upper()}_RUSTFLAGS'] = ' '.join(flags)
    return environment


def _install(built, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists() or target.read_bytes() != built.read_bytes():
        # Replace the file instead of writing over it. macOS stops new processes
        # that load a signed library whose file changed while it was mapped.
        staged = target.with_name(target.name + '.new')
        shutil.copy2(built, staged)
        os.replace(staged, target)
    return target


def build(profile='release', quiet=False):
    """Build the host libraries. Cargo skips unchanged sources."""
    _cargo(['build', *(['--release'] if profile == 'release' else [])], quiet)
    targets = []
    for module in MODULES:
        built = TARGET / profile / library_name(module)
        target = ROOT / 'game/bin' / f'opensc2k_{module}' / host_folder() / library_name(module)
        targets.append(_install(built, target))
    return targets + build_fluidsynth.build(quiet=quiet)


def build_package(quiet=False):
    """Build the release libraries of a desktop package for this platform."""
    if sys.platform == 'darwin':
        # one Cargo call builds both architectures, so they also build in parallel
        _add_targets(MACOS_TARGETS)
        _cargo(['build', '--release', *(f'--target={triple}' for triple in MACOS_TARGETS)], quiet)
        targets = []
        for module in MODULES:
            slices = [str(TARGET / triple / 'release' / library_name(module)) for triple in MACOS_TARGETS]
            universal = TARGET / 'universal' / library_name(module)
            universal.parent.mkdir(parents=True, exist_ok=True)
            subprocess.run(['lipo', '-create', *slices, '-output', str(universal)], check=True)
            targets.append(_install(universal, ROOT / 'game/bin' / f'opensc2k_{module}' / 'macos' / library_name(module)))
        return targets + build_fluidsynth.build(quiet=quiet)
    if host_folder() not in PACKAGE_TARGETS:
        raise OSError(f'desktop packages do not include {host_folder()}')
    triple = PACKAGE_TARGETS[host_folder()]
    _add_targets([triple])
    _cargo(['build', '--release', '--target', triple], quiet)
    targets = []
    for module in MODULES:
        built = TARGET / triple / 'release' / library_name(module)
        targets.append(_install(built, ROOT / 'game/bin' / f'opensc2k_{module}' / host_folder() / library_name(module)))
    return targets + build_fluidsynth.build(quiet=quiet)


def build_ios(quiet=False, simulator=False):
    """Build the five Godot extensions for iOS. FluidSynth is deliberately absent:
    the audio extension reports it as unavailable and the rest of the game runs."""
    if sys.platform != 'darwin':
        raise OSError('iOS libraries must be built on macOS with Xcode installed')
    triples = [IOS_TARGET]
    if simulator:
        triples.append(IOS_SIMULATOR_TARGET)
    _add_targets(triples)
    targets = []
    for triple in triples:
        sdk = 'iphonesimulator' if triple == IOS_SIMULATOR_TARGET else 'iphoneos'
        folder = 'ios-simulator' if triple == IOS_SIMULATOR_TARGET else 'ios'
        _cargo_packages(['--release', f'--target={triple}'], IOS_PACKAGES, quiet,
                        _apple_sdk_environment(triple, sdk))
        for module in MODULES:
            name = f'libopensc2k_{module}.dylib'
            built = TARGET / triple / 'release' / name
            target = ROOT / 'game/bin' / f'opensc2k_{module}' / folder / name
            targets.append(_install(built, target))
    return targets + build_fluidsynth.build_ios(quiet=quiet, simulator=simulator)


def test(quiet=False):
    """Run unit tests for each native library. The audio tests use the built FluidSynth."""
    environment = dict(os.environ)
    fluidsynth = build_fluidsynth.output_folder(host_folder()) / build_fluidsynth.LIBRARY_NAMES[host_folder()][0]
    if fluidsynth.is_file():
        environment.setdefault('OPENSC2K_FLUIDSYNTH', str(fluidsynth))
        environment.setdefault('OPENSC2K_REQUIRE_FLUIDSYNTH', '1')
    # the crates in native/core must build without Godot
    subprocess.run(['cargo', 'xtask', 'check-cores'], cwd=WORKSPACE, check=True, capture_output=quiet,
                   env=environment)
    command = ['cargo', 'test', '--release', '--workspace']
    if quiet:
        command.append('--quiet')
    subprocess.run(command, cwd=WORKSPACE, check=True, capture_output=quiet, env=environment)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--debug', action='store_true', help='Build without optimizations')
    parser.add_argument('--package', action='store_true', help='Build the library of a desktop package')
    parser.add_argument('--ios', action='store_true', help='Build the Godot extensions for iOS devices')
    parser.add_argument('--ios-simulator', action='store_true', help='Also build the iOS simulator extensions')
    args = parser.parse_args()
    if args.ios:
        targets = build_ios(simulator=args.ios_simulator)
    else:
        targets = build_package() if args.package else build('debug' if args.debug else 'release')
    for target in targets:
        print(f'Native library: {target.relative_to(ROOT)}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
