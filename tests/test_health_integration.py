import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import health_analytics
import local_enrichment
import oura_self_analysis as oura
import drive_upload
from scripts.install_launch_agent import job_spec


class TestPipelineHealthIntegration(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name)
        self.csv = self.folder / "daily_enriched.csv"
        self.manifest = self.folder / "manifest.json"
        self.health_csv = self.folder / "health_features.csv"
        self.health_json = self.folder / "health_insights.json"
        self.csv.write_text("day,sleep_score\n2026-10-30,79\n")
        self.manifest.write_text('{"schema_version":"1.0","row_count":1}')
        self.health_csv.write_text("day,hrv_ms\n2026-10-30,52\n")
        self.health_json.write_text('{"insights":[]}')
        self.report = {"schema_version": "1.0", "insights": [{"id":"sleep"}]}

    def test_include_health_syncs_workouts_and_exports_four_files(self):
        with patch.object(oura, "sync") as sync, \
             patch.object(local_enrichment, "export_local",
                          return_value=(self.csv, self.manifest, {"row_count":1})), \
             patch.object(health_analytics, "export",
                          return_value=(self.health_csv, self.health_json, self.report)), \
             patch.object(local_enrichment, "publish_to_drive") as publish:
            result = local_enrichment.main(["run", "--days", "30",
                                            "--include-health", "--drive-dir",
                                            str(self.folder)])
        self.assertEqual(result, 0)
        self.assertIn("workout", sync.call_args.args[0].collections)
        self.assertEqual(sync.call_args.args[0].days, 7)
        self.assertEqual(publish.call_args.kwargs["extras"],
                         (self.health_csv, self.health_json))
        manifest = json.loads(self.manifest.read_text())
        self.assertEqual(manifest["health_analysis"]["insights_count"], 1)
        self.assertEqual(manifest["health_analysis"]["files"]["health_features.csv"],
                         hashlib.sha256(self.health_csv.read_bytes()).hexdigest())

    def test_default_sync_does_not_trigger_health(self):
        with patch.object(oura, "sync") as sync, \
             patch.object(local_enrichment, "export_local",
                          return_value=(self.csv, self.manifest, {"row_count":1})), \
             patch.object(health_analytics, "export") as health, \
             patch.object(local_enrichment, "publish_to_drive"):
            self.assertEqual(local_enrichment.main([
                "run", "--days", "30", "--drive-dir", str(self.folder)]), 0)
        self.assertNotIn("workout", sync.call_args.args[0].collections)
        health.assert_not_called()

    def test_extra_drive_files_are_allowed_and_manifest_uploaded_last(self):
        copied = []
        import types
        def simulate(cmd, **kwargs):
            copied.append(cmd)
            if "md5sum" in cmd:
                name = cmd[-1].split(":")[-1]
                md5 = hashlib.md5((self.folder / name).read_bytes()).hexdigest()
                return types.SimpleNamespace(stdout=f"{md5}  {name}\n")
            return types.SimpleNamespace(stdout="")
        with patch.object(drive_upload.shutil, "which", return_value="/usr/bin/rclone"), \
             patch.object(drive_upload.subprocess, "run", side_effect=simulate):
            drive_upload.publish_rclone(
                self.csv, self.manifest, remote="gdrive:",
                folder_id="1lwlNWLxiRuFJvYJ4NzuLvCJJWkTfSdq3",
                extras=(self.health_csv, self.health_json))
        self.assertEqual(sum("copyto" in cmd for cmd in copied), 4)
        self.assertTrue(copied[-2][-1].endswith("manifest.json"))
        self.assertTrue(copied[-1][-1].endswith("manifest.json"))

    def test_daily_agent_opt_in_flag(self):
        spec = job_spec("/bin/uv", self.folder, include_health=True)
        self.assertIn("--include-health", spec["ProgramArguments"])
        spec_without = job_spec("/bin/uv", self.folder)
        self.assertNotIn("--include-health", spec_without["ProgramArguments"])


if __name__ == "__main__":
    unittest.main()
