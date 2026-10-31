#!/usr/bin/env python3
"""Install/uninstall the read-only Oura dashboard as a macOS user LaunchAgent.

No external network listener is created: dashboard_server always binds
127.0.0.1 and a separate Tailscale Serve setup is needed for phone access.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import plistlib
import subprocess
import sys
import tempfile
import time
from urllib.error import URLError
from urllib.request import urlopen

LABEL = "com.oura-self-analysis.dashboard"
PLIST = Path.home() / "Library" / "LaunchAgents" / (LABEL + ".plist")
REPO = Path(__file__).resolve().parent.parent
APP_LOGS = Path.home() / "Library" / "Application Support" / "OuraSelfAnalysis"


def spec(python: Path, *, port: int = 8765) -> dict:
    if not 1024 <= port <= 65535:
        raise ValueError("Port must be between 1024 and 65535.")
    if not (REPO / "dashboard_server.py").is_file():
        raise ValueError("dashboard_server.py not found in the repository.")
    return {
        "Label": LABEL,
        "ProgramArguments": [str(python), str(REPO / "dashboard_server.py"), "--port", str(port)],
        "WorkingDirectory": str(REPO),
        "RunAtLoad": True,
        "KeepAlive": True,
        "ProcessType": "Background",
        "Umask": 0o077,
        "EnvironmentVariables": {"HOME": str(Path.home()),
                                  "PYTHONUNBUFFERED": "1",
                                  "PATH": "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"},
        "StandardOutPath": str(APP_LOGS / "dashboard-stdout.log"),
        "StandardErrorPath": str(APP_LOGS / "dashboard-stderr.log"),
    }


def ctl(*arguments, check=True):
    return subprocess.run(["launchctl", *arguments], text=True,
                          capture_output=True, check=check)


def activate_agent(configuration: dict, previous: dict | None) -> None:
    """Idempotently refresh an existing LaunchAgent.

    A loaded service with unchanged command can be kickstarted without a
    fragile bootout/bootstrap race. Reconfigure only when arguments differ.
    """
    target = "gui/" + str(os.getuid())
    service = target + "/" + LABEL
    loaded = ctl("print", service, check=False).returncode == 0
    if loaded and previous and previous.get("ProgramArguments") == configuration["ProgramArguments"]:
        ctl("kickstart", "-k", service)
        return
    ctl("bootout", service, check=False)
    for _ in range(8):
        outcome = ctl("bootstrap", target, str(PLIST), check=False)
        if outcome.returncode == 0:
            ctl("kickstart", "-k", service)
            return
        # launchd may still see the previous service after bootout; if the
        # service is loaded despite a bootstrap race, restart it instead.
        if ctl("print", service, check=False).returncode == 0:
            ctl("kickstart", "-k", service)
            return
        time.sleep(0.25)
    raise RuntimeError("Could not register the dashboard LaunchAgent after bounded retries.")


def install(port: int):
    if sys.platform != "darwin":
        raise RuntimeError("LaunchAgents require macOS.")
    configuration = spec(Path(sys.executable), port=port)
    APP_LOGS.mkdir(parents=True, exist_ok=True, mode=0o700)
    PLIST.parent.mkdir(parents=True, exist_ok=True)
    previous = None
    if PLIST.is_file():
        try:
            with PLIST.open("rb") as old:
                previous = plistlib.load(old)
        except (OSError, ValueError, TypeError):
            previous = None
    fd, temp = tempfile.mkstemp(prefix=".oura-dashboard-", dir=PLIST.parent)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "wb") as fp:
            plistlib.dump(configuration, fp)
        os.replace(temp, PLIST)
    finally:
        Path(temp).unlink(missing_ok=True)
    try:
        activate_agent(configuration, previous)
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(
            "The LaunchAgent was saved but could not be activated (launchctl failed)."
        ) from exc
    # Give launchd time to start it, but check only local shell/health-free HTML.
    success = False
    for _ in range(8):
        try:
            with urlopen("http://127.0.0.1:" + str(port) + "/", timeout=1) as response:
                success = response.status == 200 and response.headers.get("X-Frame-Options") == "DENY"
            if success:
                break
        except (URLError, OSError):
            time.sleep(0.25)
    if not success:
        raise RuntimeError("LaunchAgent was registered but local dashboard did not answer; inspect private stderr log.")
    print("Dashboard avviata: http://127.0.0.1:" + str(port))
    print("Accesso solo locale. Per il telefono serve configurare Tailscale Serve.")


def uninstall():
    if sys.platform != "darwin":
        raise RuntimeError("macOS only")
    ctl("bootout", "gui/" + str(os.getuid()) + "/" + LABEL, check=False)
    PLIST.unlink(missing_ok=True)
    print("Servizio dashboard disinstallato. I dati Oura restano intatti.")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Manage the local Oura dashboard service")
    sub = parser.add_subparsers(dest="action", required=True)
    p = sub.add_parser("install")
    p.add_argument("--port", type=int, default=8765)
    sub.add_parser("uninstall")
    args = parser.parse_args(argv)
    try:
        if args.action == "install":
            install(args.port)
        else:
            uninstall()
        return 0
    except (RuntimeError, ValueError, OSError) as exc:
        print("Error: " + str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
