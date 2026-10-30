#!/usr/bin/env python3
"""Install a per-user macOS launchd agent for local Oura sync + enrichment.

The job runs when the Mac is available; Drive uploads can use either
a local Google Drive Desktop folder or a configured rclone remote.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import plistlib
import shutil
import subprocess
import sys
import tempfile

LABEL = "com.oura-self-analysis.daily"
PLIST_PATH = Path.home() / "Library" / "LaunchAgents" / f"{LABEL}.plist"
REPO = Path(__file__).resolve().parent.parent
HOME = Path.home() / "Library" / "Application Support" / "OuraSelfAnalysis"


def job_spec(uv: str, drive_dir: Path | None, hour: int = 9, minute: int = 15,
             days: int = 30, *, drive_remote: str | None = None,
             drive_folder_id: str | None = None) -> dict:
    if not (0 <= hour <= 23 and 0 <= minute <= 59 and 1 <= days <= 90):
        raise ValueError("Invalid time or days (1-90).")
    if bool(drive_dir) == bool(drive_remote):
        raise ValueError("Select exactly one Drive destination: local directory or remote.")
    if drive_remote and not drive_folder_id:
        raise ValueError("A Google Drive folder ID is required for rclone.")
    destination = (
        ["--drive-remote", drive_remote, "--drive-folder-id", drive_folder_id]
        if drive_remote else ["--drive-dir", str(drive_dir)]
    )
    return {
        "Label": LABEL,
        "ProgramArguments": [
            uv, "run", "--no-project", "--with", "keyring", "python",
            str(REPO / "local_enrichment.py"), "run", "--days", str(days),
            *destination,
        ],
        "WorkingDirectory": str(REPO),
        "StartCalendarInterval": {"Hour": hour, "Minute": minute},
        "RunAtLoad": False,
        "EnvironmentVariables": {
            "HOME": str(Path.home()),
            "PATH": "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin",
        },
        "StandardOutPath": str(HOME / "daily-stdout.log"),
        "StandardErrorPath": str(HOME / "daily-stderr.log"),
    }


def launchctl(*args: str, check: bool = True):
    return subprocess.run(["launchctl", *args], capture_output=True, text=True, check=check)


def install(args):
    if sys.platform != "darwin":
        raise RuntimeError("launchd is available on macOS only.")
    uv = shutil.which("uv")
    if uv is None:
        raise RuntimeError("uv not found in PATH; install uv first.")
    folder = None
    if args.drive_remote:
        if not shutil.which("rclone"):
            raise RuntimeError("rclone is not installed; configure it before scheduling.")
        if not args.drive_folder_id:
            raise RuntimeError("--drive-folder-id is required when using --drive-remote.")
    else:
        folder = args.drive_dir.expanduser()
        if folder.is_symlink() or not folder.is_dir():
            raise RuntimeError("Select an existing, non-symlinked Google Drive Desktop folder.")
        folder = folder.resolve()
    if not (REPO / "local_enrichment.py").is_file():
        raise RuntimeError("Missing local_enrichment.py; run from the checked-out repository.")
    spec = job_spec(uv, folder, args.hour, args.minute, args.days,
                    drive_remote=args.drive_remote, drive_folder_id=args.drive_folder_id)
    HOME.mkdir(parents=True, exist_ok=True, mode=0o700)
    PLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".oura-launchd-", dir=PLIST_PATH.parent)
    try:
        os.chmod(tmp, 0o600)
        with os.fdopen(fd, "wb") as stream:
            plistlib.dump(spec, stream)
        os.replace(tmp, PLIST_PATH)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
    target = f"gui/{os.getuid()}"
    # A previously loaded agent may exist; ignore only the 'not loaded' case.
    launchctl("bootout", f"{target}/{LABEL}", check=False)
    try:
        launchctl("bootstrap", target, str(PLIST_PATH))
        launchctl("print", f"{target}/{LABEL}")
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(
            f"LaunchAgent saved but could not be activated: {exc.stderr.strip()}. "
            "Check macOS login session and try again."
        ) from exc
    print(f"Installed and registered {LABEL}")
    print(f"Schedule: daily at {args.hour:02d}:{args.minute:02d} local time; Mac must be available.")
    print(f"Drive destination: {args.drive_remote} (folder ID: {args.drive_folder_id})" if args.drive_remote
          else f"Drive Desktop folder: {folder}")
    print(f"Logs: {HOME}/daily-stdout.log and daily-stderr.log")
    print("This only registers the schedule; verify the first live sync and Drive upload manually.")


def uninstall(_args):
    if sys.platform != "darwin":
        raise RuntimeError("macOS only")
    launchctl("bootout", f"gui/{os.getuid()}/{LABEL}", check=False)
    PLIST_PATH.unlink(missing_ok=True)
    print("LaunchAgent removed. Local data and Oura credentials were not changed.")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Manage the macOS Oura daily LaunchAgent")
    commands = parser.add_subparsers(dest="command", required=True)
    add = commands.add_parser("install")
    dest = add.add_mutually_exclusive_group(required=True)
    dest.add_argument("--drive-dir", type=Path,
                      help="Existing private Drive Desktop synced folder")
    dest.add_argument("--drive-remote",
                      help="Configured Google Drive rclone remote, e.g. gdrive:")
    add.add_argument("--drive-folder-id",
                     help="Drive folder ID, required for rclone upload")
    add.add_argument("--hour", default=9, type=int)
    add.add_argument("--minute", default=15, type=int)
    add.add_argument("--days", default=30, type=int)
    commands.add_parser("uninstall")
    args = parser.parse_args(argv)
    try:
        (install if args.command == "install" else uninstall)(args)
        return 0
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
