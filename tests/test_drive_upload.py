import hashlib
from pathlib import Path
import subprocess
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import drive_upload
import local_enrichment as enrich
import oura_self_analysis as oura
from scripts.install_launch_agent import job_spec


class TestDirectDriveUpload(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.csv = self.root / "daily_enriched.csv"
        self.manifest = self.root / "manifest.json"
        self.csv.write_text("day,sleep_score\n2026-10-30,81\n")
        self.manifest.write_text('{"row_count":1}')
        self.folder_id = "1lwlNWLxiRuFJvYJ4NzuLvCJJWkTfSdq3"

    def test_upload_and_verify_both_files_with_google_folder_id(self):
        calls = []
        def simulate(cmd, **kwargs):
            calls.append(cmd)
            if "md5sum" in cmd:
                filename = cmd[-1].split(":")[-1]
                path = self.root / filename
                md5 = hashlib.md5(path.read_bytes()).hexdigest()
                return SimpleNamespace(stdout=f"{md5}  {filename}\n")
            return SimpleNamespace(stdout="")
        with patch.object(drive_upload.shutil, "which", return_value="/usr/local/bin/rclone"), \
             patch.object(drive_upload.subprocess, "run", side_effect=simulate):
            drive_upload.publish_rclone(self.csv, self.manifest,
                                       remote="gdrive:", folder_id=self.folder_id)
        self.assertEqual(len(calls), 4)
        self.assertIn("copyto", calls[0])
        self.assertIn("md5sum", calls[1])
        self.assertEqual(calls[0][-1], "gdrive:daily_enriched.csv")
        self.assertEqual(calls[2][-1], "gdrive:manifest.json")
        self.assertIn(self.folder_id, calls[0])

    def test_wrong_remote_checksum_fails_before_manifest(self):
        calls = []
        def simulate(cmd, **kwargs):
            calls.append(cmd)
            return SimpleNamespace(stdout=("0" * 32 + "  daily_enriched.csv\n"
                                          if "md5sum" in cmd else ""))
        with patch.object(drive_upload.shutil, "which", return_value="/usr/local/bin/rclone"), \
             patch.object(drive_upload.subprocess, "run", side_effect=simulate):
            with self.assertRaises(oura.OuraError):
                drive_upload.publish_rclone(self.csv, self.manifest,
                                           remote="gdrive:", folder_id=self.folder_id)
        self.assertEqual(len(calls), 2)

    def test_remote_validation_blocks_paths_and_missing_rclone(self):
        with patch.object(drive_upload.shutil, "which", return_value="/bin/rclone"):
            for invalid in ("gdrive:/other", "gdrive:folder", "https://drive.google.com"):
                with self.subTest(invalid=invalid):
                    with self.assertRaises(oura.OuraError):
                        drive_upload.validate_remote(invalid, self.folder_id)
        with patch.object(drive_upload.shutil, "which", return_value=None):
            with self.assertRaises(oura.OuraError):
                drive_upload.validate_remote("gdrive:", self.folder_id)

    def test_subprocess_error_is_reported(self):
        err = subprocess.CalledProcessError(1, ["rclone"], stderr="permission denied")
        with patch.object(drive_upload.shutil, "which", return_value="/bin/rclone"), \
             patch.object(drive_upload.subprocess, "run", side_effect=err):
            with self.assertRaisesRegex(oura.OuraError, "permission denied"):
                drive_upload.publish_rclone(self.csv, self.manifest,
                                           remote="gdrive:", folder_id=self.folder_id)

    def test_cli_rclone_publish_without_drive_dir(self):
        with patch.object(enrich, "export_local",
                          return_value=(self.csv, self.manifest, {"row_count": 1})), \
             patch.object(enrich, "publish_rclone") as publish:
            result = enrich.main(["publish", "--days", "30",
                                  "--drive-remote", "gdrive:",
                                  "--drive-folder-id", self.folder_id])
        self.assertEqual(result, 0)
        publish.assert_called_once_with(
            self.csv, self.manifest, remote="gdrive:", folder_id=self.folder_id)

    def test_scheduler_has_rclone_destination_and_no_credentials(self):
        spec = job_spec("/usr/local/bin/uv", None, 9, 15, 30,
                        drive_remote="gdrive:", drive_folder_id=self.folder_id)
        args = spec["ProgramArguments"]
        self.assertEqual(args[-4:],
                         ["--drive-remote", "gdrive:",
                          "--drive-folder-id", self.folder_id])
        self.assertNotIn("token", str(args).lower())
        self.assertNotIn("client_secret", str(args))


if __name__ == "__main__":
    unittest.main()
