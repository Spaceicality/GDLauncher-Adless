#!/usr/bin/env python3

from pathlib import Path
import os
import shutil
import subprocess
import sys


ROOT = Path(__file__).resolve().parent

DIST = ROOT / "dist"
APP = DIST / "GDLauncher No Ads.app"

CONTENTS = APP / "Contents"
MACOS = CONTENTS / "MacOS"
RESOURCES = CONTENTS / "Resources"

INJECTOR_SOURCE = ROOT / "injector.py"
INJECTOR_DIST = ROOT / "injector-dist"
INJECTOR_BUILD = ROOT / "injector-build"

INJECTOR_BINARY = (
    INJECTOR_DIST / "gdlauncher-no-ads-injector"
)

INJECTOR_DEST = (
    MACOS / "gdlauncher-no-ads-injector"
)

ICON_DEST = RESOURCES / "GDLauncher.icns"
APP_EXECUTABLE = MACOS / "GDLauncher-No-Ads"


def clean_build():
    if DIST.exists():
        print(f"Removing existing build directory: {DIST}")
        shutil.rmtree(DIST)


def create_directories():
    MACOS.mkdir(parents=True, exist_ok=True)
    RESOURCES.mkdir(parents=True, exist_ok=True)


def build_injector():
    configured_path = os.environ.get("INJECTOR_BINARY")

    if configured_path:
        configured_binary = Path(configured_path)

        if configured_binary.is_file():
            print("Using injector supplied by environment:")
            print(f"  {configured_binary}")
            return configured_binary

        raise RuntimeError(
            "INJECTOR_BINARY was specified, but the file does not exist:\n"
            f"{configured_binary}"
        )

    if INJECTOR_BINARY.is_file():
        print("Using existing injector:")
        print(f"  {INJECTOR_BINARY}")
        return INJECTOR_BINARY

    if not INJECTOR_SOURCE.is_file():
        raise RuntimeError(
            f"Could not find injector.py at:\n{INJECTOR_SOURCE}"
        )

    print("Building injector with PyInstaller...")

    if INJECTOR_BUILD.exists():
        shutil.rmtree(INJECTOR_BUILD)

    if INJECTOR_DIST.exists():
        shutil.rmtree(INJECTOR_DIST)

    try:
        subprocess.run(
            [
                sys.executable,
                "-m",
                "PyInstaller",
                "--onefile",
                "--name",
                "gdlauncher-no-ads-injector",
                "--distpath",
                str(INJECTOR_DIST),
                "--workpath",
                str(INJECTOR_BUILD),
                "--specpath",
                str(INJECTOR_BUILD),
                str(INJECTOR_SOURCE),
            ],
            cwd=ROOT,
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(
            "PyInstaller failed while building the injector."
        ) from exc

    if not INJECTOR_BINARY.is_file():
        raise RuntimeError(
            "PyInstaller completed, but the injector executable was not found:\n"
            f"{INJECTOR_BINARY}"
        )

    print("Injector built successfully:")
    print(f"  {INJECTOR_BINARY}")

    return INJECTOR_BINARY


def copy_injector(injector):
    print("Copying bundled injector...")
    print(f"  Source: {injector}")
    print(f"  Target: {INJECTOR_DEST}")

    shutil.copy2(
        injector,
        INJECTOR_DEST,
    )

    INJECTOR_DEST.chmod(0o755)


def create_icon():
    print("Generating application icon...")

    try:
        from icon import create_icon
    except ImportError as exc:
        raise RuntimeError(
            "Could not import icon.py."
        ) from exc

    create_icon(
        "mac",
        ICON_DEST,
    )


def create_launcher():
    print("Creating application launcher...")

    launcher = '''#!/bin/zsh

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

exec "$SCRIPT_DIR/gdlauncher-no-ads-injector"
'''

    APP_EXECUTABLE.write_text(
        launcher,
        encoding="utf-8",
    )

    APP_EXECUTABLE.chmod(0o755)


def create_info_plist():
    print("Creating Info.plist...")

    plist = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
    "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleDisplayName</key>
    <string>GDLauncher No Ads</string>

    <key>CFBundleExecutable</key>
    <string>GDLauncher-No-Ads</string>

    <key>CFBundleIconFile</key>
    <string>GDLauncher.icns</string>

    <key>CFBundleIdentifier</key>
    <string>dev.nolananderson.gdlauncher-no-ads</string>

    <key>CFBundleName</key>
    <string>GDLauncher No Ads</string>

    <key>CFBundlePackageType</key>
    <string>APPL</string>

    <key>CFBundleShortVersionString</key>
    <string>1.0</string>

    <key>CFBundleVersion</key>
    <string>1</string>

    <key>LSUIElement</key>
    <false/>
</dict>
</plist>
"""

    plist_path = CONTENTS / "Info.plist"

    plist_path.write_text(
        plist,
        encoding="utf-8",
    )


def refresh_launch_services():
    lsregister = (
        "/System/Library/Frameworks/CoreServices.framework/"
        "Frameworks/LaunchServices.framework/Support/lsregister"
    )

    if not Path(lsregister).exists():
        return

    print("Refreshing Launch Services...")

    subprocess.run(
        [
            lsregister,
            "-f",
            str(APP),
        ],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def main():
    print()
    print("========================================")
    print("       GDLauncher No Ads Builder")
    print("========================================")
    print()

    print(f"Project: {ROOT}")
    print(f"Output:  {APP}")
    print(f"Python:  {sys.executable}")
    print()

    clean_build()

    injector = build_injector()

    create_directories()
    copy_injector(injector)
    create_icon()
    create_launcher()
    create_info_plist()
    refresh_launch_services()

    print()
    print("========================================")
    print("             Build Complete")
    print("========================================")
    print()

    print("Application:")
    print(f"  {APP}")
    print()


if __name__ == "__main__":
    main()