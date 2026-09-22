from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from anime_dubber.application.project import ProjectStore, get_project, list_projects
from anime_dubber.application.service import ApplicationService


class ProjectStoreTests(unittest.TestCase):
    def test_manifest_lifecycle_and_redaction(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td)
            store = ProjectStore(out, "https://youtu.be/example")
            store.begin(
                job_id="job_1",
                kind="run",
                config={
                    "source": "https://youtu.be/example",
                    "series_id": "demo",
                    "elevenlabs_api_key": "secret",
                    "tts": {"provider": "elevenlabs", "api_key": "nested-secret"},
                },
            )
            store.update_stage(stage="transcribing", title="Transcribing Mandarin", progress=0.5)
            store.append_log("line one\nline two")
            store.finish(status="completed", artifacts={"dubbed_video": "/tmp/out.mp4"})

            rows = list_projects(out)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["status"], "completed")
            self.assertEqual(rows[0]["stage"], "completed")

            detail = get_project(out, store.project_id)
            self.assertEqual(detail["artifacts"]["dubbed_video"], "/tmp/out.mp4")
            self.assertEqual(detail["config"]["elevenlabs_api_key"], "<redacted>")
            self.assertEqual(detail["config"]["tts"]["api_key"], "<redacted>")
            self.assertTrue(Path(detail["log_path"]).exists())

    def test_service_persists_fake_job(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td)
            service = ApplicationService()

            def fake_pipeline(config, progress, runner):
                progress("Transcribing Mandarin…")
                progress("Generating English voice: 1/2")
                progress("Generating English voice: 2/2")
                return {"dubbed_video": out / "final.mp4"}

            with patch("anime_dubber.application.service.run_pipeline", side_effect=fake_pipeline):
                job = service.run_sync({
                    "source": "video.mp4",
                    "output_dir": str(out),
                    "series_id": "demo",
                })

            self.assertEqual(job["status"], "completed")
            projects = service.list_projects(str(out))
            self.assertEqual(len(projects), 1)
            self.assertEqual(projects[0]["status"], "completed")
            self.assertEqual(projects[0]["artifacts"]["dubbed_video"], str(out / "final.mp4"))


if __name__ == "__main__":
    unittest.main()
