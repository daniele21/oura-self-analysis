"""Direct upload of locally enriched Oura files to private Google Drive via rclone.

Requires a separately configured rclone Google Drive OAuth remote. No Google
Drive Desktop mount, Google token or credentials in the repository.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
import re
import shutil
import subprocess

from oura_self_analysis import OuraError

REMOTE_PATTERN = re.compile(r"[A-Za-z0-9_-]+:")
FOLDER_ID_PATTERN = re.compile(r"[A-Za-z0-9_-]{10,128}")
HASH_PATTERN = re.compile(r"^[a-fA-F0-9]{32}$")
FILES = ("daily_enriched.csv", "manifest.json")


def validate_remote(remote: str, folder_id: str) -> None:
    if not REMOTE_PATTERN.fullmatch(remote):
        raise OuraError("Use a bare named rclone Drive remote such as 'gdrive:' (no path).")
    if not FOLDER_ID_PATTERN.fullmatch(folder_id):
        raise OuraError("Invalid Google Drive folder ID.")
    if not shutil.which("rclone"):
        raise OuraError("rclone is not installed. Install it, then authorize with 'rclone config'.")


def execute(args: list[str]) -> str:
    try:
        result = subprocess.run(args, capture_output=True, text=True,
                                timeout=180, check=True)
    except FileNotFoundError as exc:
        raise OuraError("rclone command not found.") from exc
    except subprocess.TimeoutExpired as exc:
        raise OuraError("Google Drive upload/check timed out.") from exc
    except subprocess.CalledProcessError as exc:
        # Do not include the entire command or environment (which may be sensitive).
        details = (exc.stderr or "").strip()[-600:]
        raise OuraError(f"rclone failed (exit {exc.returncode}): {details}") from exc
    return result.stdout


def publish_rclone(csv_path: Path, manifest_path: Path,
                   *, remote: str, folder_id: str) -> None:
    """Upsert two files into the *exact* Drive folder specified by its ID.

    Write manifest last. Verify both remote MD5 hashes match the local files.
    No deletion or bulk folder sync; additional Drive files are untouched.
    """
    validate_remote(remote, folder_id)
    if csv_path.name != FILES[0] or manifest_path.name != FILES[1]:
        raise OuraError("Unexpected enrichment filenames.")
    for file in (csv_path, manifest_path):
        if not file.is_file() or file.is_symlink():
            raise OuraError(f"Missing or unsafe local file: {file.name}")

    command = shutil.which("rclone")
    base = [command, "--drive-root-folder-id", folder_id]

    for file in (csv_path, manifest_path):
        target = remote + file.name
        execute(base + ["copyto", "--retries", "3", str(file), target])
        md5 = hashlib.md5(file.read_bytes()).hexdigest()  # Transport integrity; not a security signature.
        stdout = execute(base + ["md5sum", target])
        # Typical rclone output: "<32-digit MD5>  filename"
        lines = [line.split() for line in stdout.splitlines() if line.strip()]
        if len(lines) != 1 or len(lines[0]) < 2 or not HASH_PATTERN.fullmatch(lines[0][0]):
            raise OuraError(f"Couldn't verify remote checksum for {file.name}.")
        if lines[0][0].lower() != md5:
            raise OuraError(f"Remote checksum mismatch for {file.name}.")
