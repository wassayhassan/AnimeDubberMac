from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from anime_dubber.application.events import progress_to_event
from anime_dubber.application.service import ApplicationService, config_from_dict


class ApplicationServiceTests(unittest.TestCase):
    def test_config_accepts_nested_v4_schema(self):
        cfg = config_from_dict({
            "source": "video.mp4",
            "output_dir": "~/AnimeDubberOut",
            "series_id": "series-a",
            "translation": {"provider": "mlx_llm"},
            "tts": {"provider": "macos", "fallback_voice": "Daniel", "rate": 220},
            "speaker_analysis": {
                "enabled": True,
                "backend": "auto",
                "max_speakers": 8,
                "threshold": None,
            },
            "audio": {
                "background_volume": 0.9,
                "dub_volume": 1.2,
                "ducking": False,
            },
        })
        self.assertEqual(cfg.translation, "llm")
        self.assertEqual(cfg.tts_engine, "macos")
        self.assertEqual(cfg.voice, "Daniel")
        self.assertEqual(cfg.tts_rate, 220)
        self.assertEqual(cfg.max_speakers, 8)
        self.assertEqual(cfg.speaker_threshold, 0.0)
        self.assertAlmostEqual(cfg.background_volume, 0.9)
        self.assertAlmostEqual(cfg.dub_volume, 1.2)
        self.assertTrue(str(cfg.output_dir).endswith("AnimeDubberOut"))

    def test_job_snapshot_redacts_elevenlabs_key(self):
        service = ApplicationService()
        cfg = config_from_dict({
            "source": "video.mp4",
            "output_dir": "/tmp/out",
            "tts": {
                "provider": "elevenlabs",
                "api_key": "secret-value",
            },
        })
        normalized = service._normalized_config_dict(cfg)
        self.assertEqual(normalized["elevenlabs_api_key"], "<redacted>")

    def test_progress_download_is_structured(self):
        event = progress_to_event(
            "__DOWNLOAD_PROGRESS__|42.5|8.1MiB/s|00:31|1.2GiB|2|3",
            "job_x",
        )
        self.assertEqual(event.event, "progress")
        self.assertEqual(event.job_id, "job_x")
        self.assertEqual(event.data["stage"], "downloading")
        self.assertAlmostEqual(event.data["fraction"], 0.425)
        self.assertEqual(event.data["attempt"], "2")

    def test_progress_tts_count_becomes_fraction(self):
        event = progress_to_event("Generating English voice: 25/100 (spk_1, normal)", "job_x")
        self.assertEqual(event.data["stage"], "synthesizing")
        self.assertEqual(event.data["completed"], 25)
        self.assertEqual(event.data["total"], 100)
        self.assertAlmostEqual(event.data["fraction"], 0.25)

    def test_sync_job_wraps_legacy_pipeline(self):
        events = []
        service = ApplicationService(event_sink=events.append)

        def fake_pipeline(config, progress, runner):
            progress("Transcribing Mandarin…")
            progress("Generating English voice: 2/2")
            return {"dubbed_video": Path("/tmp/out.mp4")}

        with patch("anime_dubber.application.service.run_pipeline", side_effect=fake_pipeline):
            job = service.run_sync({
                "source": "video.mp4",
                "output_dir": "/tmp/out",
            })

        self.assertEqual(job["status"], "completed")
        self.assertEqual(job["result"]["dubbed_video"], str(Path("/tmp/out.mp4")))
        self.assertTrue(any(e.event == "job_started" for e in events))
        self.assertTrue(any(e.event == "artifact" for e in events))
        self.assertTrue(any(e.event == "finished" for e in events))


if __name__ == "__main__":
    unittest.main()
