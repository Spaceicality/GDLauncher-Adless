#!/usr/bin/env python3

from pathlib import Path
import shutil
import ssl
import subprocess
import tempfile
import urllib.request


ROOT = Path(__file__).resolve().parent

ICON_URL = (
    "https://raw.githubusercontent.com/"
    "gorilla-devs/GDLauncher-Carbon/"
    "develop/apps/desktop/build/icon.png"
)


def create_ssl_context():
    """
    Create a certificate-verifying SSL context.

    The Python.org macOS installer does not always use the
    macOS system certificate store automatically.
    """

    try:
        import certifi
    except ImportError:
        raise RuntimeError(
            "The Python 'certifi' package is required.\n\n"
            "Install it with:\n"
            f'  "{Path("/Library/Frameworks/Python.framework/Versions/3.13/bin/python3")}" '
            "-m pip install certifi"
        )

    return ssl.create_default_context(
        cafile=certifi.where()
    )


def download_source_icon(destination: Path):
    """
    Download the current stable GDLauncher Carbon icon.
    """

    print("Downloading GDLauncher Carbon icon...")
    print(f"  URL: {ICON_URL}")

    request = urllib.request.Request(
        ICON_URL,
        headers={
            "User-Agent": "GDLauncher-No-Ads-Build"
        },
    )

    try:
        with urllib.request.urlopen(
            request,
            context=create_ssl_context(),
        ) as response:
            data = response.read()

    except Exception as exc:
        raise RuntimeError(
            f"Failed to download the GDLauncher icon:\n{exc}"
        ) from exc

    if not data:
        raise RuntimeError(
            "The downloaded GDLauncher icon is empty."
        )

    destination.write_bytes(data)

    print(
        f"Downloaded icon "
        f"({len(data):,} bytes)"
    )


def create_macos_icon(source: Path, destination: Path):
    """
    Create the macOS application icon.

    The Carbon project supplies icon.png directly to electron-builder.
    Rather than manually adding a background or modifying the artwork,
    use Apple's native icon tooling for the resulting .icns.
    """

    iconutil = Path("/usr/bin/iconutil")

    if not iconutil.exists():
        raise RuntimeError(
            "Could not find Apple's iconutil."
        )

    print("Creating macOS icon...")

    iconset = Path(
        tempfile.mkdtemp(
            prefix="gdlauncher-no-ads-",
            suffix=".iconset",
        )
    )

    try:
        # Apple's iconutil expects these exact filenames.
        sizes = [
            (16, "icon_16x16.png"),
            (32, "icon_16x16@2x.png"),
            (32, "icon_32x32.png"),
            (64, "icon_32x32@2x.png"),
            (128, "icon_128x128.png"),
            (256, "icon_128x128@2x.png"),
            (256, "icon_256x256.png"),
            (512, "icon_256x256@2x.png"),
            (512, "icon_512x512.png"),
            (1024, "icon_512x512@2x.png"),
        ]

        # Use macOS's built-in sips to resize the source PNG.
        for size, filename in sizes:
            output = iconset / filename

            shutil.copy2(
                source,
                output,
            )

            result = subprocess.run(
                [
                    "/usr/bin/sips",
                    "--resampleHeightWidth",
                    str(size),
                    str(size),
                    str(output),
                    "--out",
                    str(output),
                ],
                capture_output=True,
                text=True,
            )

            if result.returncode != 0:
                raise RuntimeError(
                    f"sips failed while creating {filename}:\n"
                    f"{result.stderr.strip()}"
                )

        result = subprocess.run(
            [
                str(iconutil),
                "-c",
                "icns",
                str(iconset),
                "-o",
                str(destination),
            ],
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            raise RuntimeError(
                "iconutil failed:\n"
                f"{result.stderr.strip()}"
            )

    finally:
        shutil.rmtree(
            iconset,
            ignore_errors=True,
        )

    print(f"Created: {destination}")


def create_icon(
    platform: str,
    destination: Path,
):
    """
    Generate an icon for the requested platform.

    Supported platforms:
        mac
    """

    platform = platform.lower()

    with tempfile.TemporaryDirectory(
        prefix="gdlauncher-no-ads-icon-"
    ) as temp_dir:
        source = Path(temp_dir) / "icon.png"

        download_source_icon(source)

        if platform == "mac":
            create_macos_icon(
                source,
                destination,
            )

        else:
            raise ValueError(
                f"Unsupported icon platform: {platform}"
            )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Generate GDLauncher No Ads application icons."
    )

    parser.add_argument(
        "platform",
        choices=["mac"],
        help="Platform to generate the icon for.",
    )

    parser.add_argument(
        "output",
        type=Path,
        help="Output icon path.",
    )

    args = parser.parse_args()

    create_icon(
        args.platform,
        args.output,
    )
