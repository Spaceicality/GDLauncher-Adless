from pathlib import Path
import asyncio
import json
import plistlib
import subprocess
import sys
import time
import urllib.request

import websockets


DEBUG_PORT = 9223

APP_SUPPORT = (
    Path.home()
    / "Library"
    / "Application Support"
    / "GDLauncher No Ads"
)

CONFIG_FILE = APP_SUPPORT / "config.json"


INJECTION = r"""
(() => {
    const STYLE_ID = "__gdlauncher_no_ads";

    const css = `
        div[style*="view-transition-name: ad"] {
            display: none !important;
        }

        div[style*="width: calc(-440px + 100vw)"] {
            width: 100vw !important;
            margin-left: 0 !important;
            margin-right: 0 !important;
            transform: none !important;
        }

        owadview[cid="gdlauncher_horizontal_400_60"],
        owadview[cid="gdlauncher_rectangle_440_730_high_impact"] {
            display: none !important;
        }
    `;

    function applyPatch() {
        let style = document.getElementById(STYLE_ID);

        if (!style) {
            style = document.createElement("style");
            style.id = STYLE_ID;

            const parent =
                document.head ||
                document.documentElement;

            if (parent) {
                parent.appendChild(style);
            }
        }

        if (style && style.textContent !== css) {
            style.textContent = css;
        }
    }

    applyPatch();

    if (!window.__gdlauncherNoAdsObserver) {
        window.__gdlauncherNoAdsObserver =
            new MutationObserver(applyPatch);

        const startObserver = () => {
            if (!document.documentElement) {
                return;
            }

            window.__gdlauncherNoAdsObserver.observe(
                document.documentElement,
                {
                    childList: true,
                    subtree: true
                }
            );
        };

        startObserver();
    }

    return "GDLauncher No Ads patch installed";
})()
"""


def show_error(title, message):
    """
    Show a native macOS error dialog.
    """

    script = f'''
        display alert {json.dumps(title)}
        message {json.dumps(message)}
        as critical
        buttons {{"OK"}}
        default button "OK"
    '''

    subprocess.run(
        [
            "/usr/bin/osascript",
            "-e",
            script,
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )


def ask_to_select_gdlauncher():
    """
    Explain why manual selection is necessary.

    Returns:
        True if the user wants to select GDLauncher.
        False if the user wants to quit.
    """

    script = r'''
        set result to display dialog ¬
            "GDLauncher No Ads couldn't find GDLauncher in the standard locations." & return & return & ¬
            "Please select your GDLauncher application manually." ¬
            with title "GDLauncher No Ads" ¬
            buttons {"Quit", "Select GDLauncher…"} ¬
            default button "Select GDLauncher…"

        return button returned of result
    '''

    try:
        result = subprocess.run(
            [
                "/usr/bin/osascript",
                "-e",
                script,
            ],
            capture_output=True,
            text=True,
            check=True,
        )

        return result.stdout.strip() == "Select GDLauncher…"

    except subprocess.CalledProcessError:
        return False


def select_gdlauncher():
    """
    Ask macOS to let the user select a GDLauncher application.

    This intentionally uses Apple's normal `choose file`
    application-bundle picker rather than `choose application`.
    """

    script = r'''
        set selectedApp to choose file ¬
            of type {"com.apple.application-bundle"} ¬
            with prompt "Select your GDLauncher application"

        POSIX path of selectedApp
    '''

    try:
        result = subprocess.run(
            [
                "/usr/bin/osascript",
                "-e",
                script,
            ],
            capture_output=True,
            text=True,
            check=True,
        )

        path = result.stdout.strip()

        if not path:
            return None

        app = Path(path)

        if not app.is_dir() or app.suffix != ".app":
            show_error(
                "Invalid Application",
                "The selected item is not a valid application.",
            )
            return None

        return app

    except subprocess.CalledProcessError:
        # This normally means the user cancelled the picker.
        return None


def get_bundle_value(app, key):
    """
    Read a value from an application's Info.plist.
    """

    plist = app / "Contents" / "Info.plist"

    if not plist.exists():
        return None

    try:
        with plist.open("rb") as file:
            data = plistlib.load(file)

        return data.get(key)

    except Exception:
        return None


def get_bundle_executable(app):
    """
    Find the executable specified by CFBundleExecutable.
    """

    executable_name = get_bundle_value(
        app,
        "CFBundleExecutable",
    )

    if executable_name:
        executable = (
            app
            / "Contents"
            / "MacOS"
            / str(executable_name)
        )

        if executable.exists() and executable.is_file():
            return executable

    # Fallback for GDLauncher installations that use the
    # conventional executable name.
    fallback = (
        app
        / "Contents"
        / "MacOS"
        / "GDLauncher"
    )

    if fallback.exists() and fallback.is_file():
        return fallback

    return None


def is_gdlauncher_app(app):
    """
    Determine whether a path appears to be a GDLauncher app.
    """

    if app is None:
        return False

    app = Path(app)

    if app.suffix != ".app":
        return False

    if not app.is_dir():
        return False

    info_plist = (
        app
        / "Contents"
        / "Info.plist"
    )

    if not info_plist.exists():
        return False

    executable = get_bundle_executable(app)

    if executable is None:
        return False

    bundle_identifier = str(
        get_bundle_value(
            app,
            "CFBundleIdentifier",
        )
        or ""
    ).lower()

    bundle_name = str(
        get_bundle_value(
            app,
            "CFBundleName",
        )
        or ""
    ).lower()

    display_name = str(
        get_bundle_value(
            app,
            "CFBundleDisplayName",
        )
        or ""
    ).lower()

    executable_name = executable.name.lower()

    metadata = " ".join(
        [
            bundle_identifier,
            bundle_name,
            display_name,
            executable_name,
        ]
    )

    return "gdlauncher" in metadata


def load_saved_path():
    """
    Load the previously selected GDLauncher .app path.
    """

    if not CONFIG_FILE.exists():
        return None

    try:
        with CONFIG_FILE.open(
            "r",
            encoding="utf-8",
        ) as file:
            config = json.load(file)

        saved_path = config.get(
            "gdlauncher_path"
        )

        if not saved_path:
            return None

        app = Path(saved_path)

        if is_gdlauncher_app(app):
            return app

    except Exception:
        pass

    return None


def save_gdlauncher_path(app):
    """
    Save the selected GDLauncher .app path.
    """

    try:
        APP_SUPPORT.mkdir(
            parents=True,
            exist_ok=True,
        )

        with CONFIG_FILE.open(
            "w",
            encoding="utf-8",
        ) as file:
            json.dump(
                {
                    "gdlauncher_path": str(app),
                },
                file,
                indent=4,
            )

    except Exception as error:
        print(
            f"Warning: could not save GDLauncher path: {error}"
        )


def find_default_gdlauncher():
    """
    Search the standard macOS GDLauncher locations.
    """

    locations = [
        Path("/Applications/GDLauncher.app"),
        Path.home()
        / "Applications"
        / "GDLauncher.app",
    ]

    for app in locations:
        if is_gdlauncher_app(app):
            return app

    return None


def find_gdlauncher():
    """
    Find GDLauncher in this order:

    1. Previously saved path
    2. /Applications/GDLauncher.app
    3. ~/Applications/GDLauncher.app
    4. Manual selection
    """

    saved = load_saved_path()

    if saved:
        print("Using saved GDLauncher:")
        print(saved)
        return saved

    default = find_default_gdlauncher()

    if default:
        print("Found GDLauncher:")
        print(default)
        return default

    print("GDLauncher was not found automatically.")

    if not ask_to_select_gdlauncher():
        print("No GDLauncher selected.")
        return None

    while True:
        selected = select_gdlauncher()

        if selected is None:
            print("No GDLauncher selected.")
            return None

        print("Selected application:")
        print(selected)

        if is_gdlauncher_app(selected):
            save_gdlauncher_path(selected)

            print("GDLauncher path saved.")

            return selected

        show_error(
            "Invalid Application",
            "The selected application does not appear to be GDLauncher.\n\nPlease select your GDLauncher application.",
        )

        if not ask_to_select_gdlauncher():
            print("No GDLauncher selected.")
            return None


def get_targets():
    """
    Retrieve Chrome DevTools Protocol targets.
    """

    try:
        with urllib.request.urlopen(
            f"http://127.0.0.1:{DEBUG_PORT}/json",
            timeout=1,
        ) as response:
            return json.load(response)

    except Exception:
        return []


def find_carbon_target():
    """
    Find GDLauncher's Carbon main window.
    """

    for target in get_targets():
        if (
            target.get("type") == "page"
            and "mainWindow/index.html"
            in target.get("url", "")
            and target.get("webSocketDebuggerUrl")
        ):
            return target["webSocketDebuggerUrl"]

    return None


async def install_patch(ws_url):
    """
    Install the patch into the current Carbon document
    and future documents.
    """

    async with websockets.connect(
        ws_url,
        max_size=None,
    ) as ws:

        await ws.send(
            json.dumps(
                {
                    "id": 1,
                    "method":
                        "Page.addScriptToEvaluateOnNewDocument",
                    "params": {
                        "source": INJECTION,
                    },
                }
            )
        )

        while True:
            message = json.loads(
                await ws.recv()
            )

            if message.get("id") == 1:
                break

        await ws.send(
            json.dumps(
                {
                    "id": 2,
                    "method":
                        "Runtime.evaluate",
                    "params": {
                        "expression": INJECTION,
                        "returnByValue": True,
                    },
                }
            )
        )

        while True:
            message = json.loads(
                await ws.recv()
            )

            if message.get("id") == 2:
                return message


def launch_gdlauncher(app):
    """
    Launch GDLauncher from its application bundle.
    """

    executable = get_bundle_executable(app)

    if executable is None:
        raise RuntimeError(
            "Could not find the GDLauncher executable inside the selected application."
        )

    print("Launching:")
    print(executable)

    return subprocess.Popen(
        [
            str(executable),
            f"--remote-debugging-port={DEBUG_PORT}",
            "--gdl_allow_multiple_instances",
        ],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def monitor_gdlauncher(process):
    """
    Keep the injector alive while GDLauncher is running.

    Carbon can recreate or replace its document, so the patch
    is reapplied whenever a new CDP target appears.
    """

    last_ws = None

    while process.poll() is None:

        ws_url = find_carbon_target()

        if ws_url:

            if ws_url != last_ws:
                print("Carbon target detected.")
                print("Installing No Ads patch...")

                try:
                    result = asyncio.run(
                        install_patch(ws_url)
                    )

                    print("Patch installed.")
                    print(result)

                    last_ws = ws_url

                except Exception as error:
                    print(
                        f"Patch installation failed: {error}"
                    )

            else:
                # Reapply the patch to the current document.
                # This keeps the ad-removal CSS alive if Carbon
                # modifies/replaces parts of the DOM.
                try:
                    asyncio.run(
                        install_patch(ws_url)
                    )

                except Exception:
                    pass

        time.sleep(1)


def main():
    print("GDLauncher No Ads")
    print()

    if sys.platform != "darwin":
        print(
            "This version of GDLauncher No Ads currently "
            "supports macOS only."
        )

        return 1

    app = find_gdlauncher()

    if app is None:
        return 0

    print()
    print("GDLauncher:")
    print(app)
    print()

    try:
        process = launch_gdlauncher(app)

    except Exception as error:
        print(
            f"Could not launch GDLauncher: {error}"
        )

        show_error(
            "Could Not Launch GDLauncher",
            f"GDLauncher No Ads could not launch GDLauncher.\n\n{error}",
        )

        return 1

    print(
        f"GDLauncher PID: {process.pid}"
    )

    print(
        "Waiting for Carbon..."
    )

    monitor_gdlauncher(process)

    return process.returncode or 0


if __name__ == "__main__":
    raise SystemExit(main())