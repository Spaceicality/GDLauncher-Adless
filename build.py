#!/usr/bin/env python3

from pathlib import Path
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
INJECTOR_BUILD = ROOT / "injector-dist" / "gdlauncher-no-ads-injector"
INJECTOR_DEST = MACOS / "gdlauncher-no-ads-injector"

ICON_DEST = RESOURCES / "GDLauncher.icns"
APP_EXECUTABLE = MACOS / "GDLauncher-No-Ads"


def clean_build():
    if DIST.exists():
        print(f"Removing existing build directory: {DIST}")
        shutil.rmtree(DIST)

    if (ROOT / "injector-build").exists():
        print("Removing previous injector build...")
        shutil.rmtree(ROOT / "injector-build")

    if (ROOT / "injector-dist").exists():
        print("Removing previous injector distribution...")
        shutil.rmtree(ROOT / "injector-dist")


def create_directories():
    MACOS.mkdir(parents=True, exist_ok=True)
    RESOURCES.mkdir(parents=True, exist_ok=True)


def verify_injector():
    if not INJECTOR_BUILD.is_file():
        raise RuntimeError(
            "Could not find the bundled injector executable:\n"
            f"{INJECTOR_BUILD}\n\n"
            "Make sure PyInstaller has been run before build.py."
        )


def copy_injector():
    verify_injector()

    print("Copying bundled injector...")
    shutil.copy2(INJECTOR_BUILD, INJECTOR_DEST)

    INJECTOR_DEST.chmod(0o755)


def create_icon():
    print("Generating application icon...")

    try:
        from icon import create_icon
    except ImportError as exc:
        raise RuntimeError(
            "Could not import icon.py."
        ) from exc

    create_icon("mac", ICON_DEST)


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
    create_directories()
    copy_injector()
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