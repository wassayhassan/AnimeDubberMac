import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from anime_dubber.application.service import ApplicationService
from anime_dubber.core import Config, Segment, run_pipeline, translate_with_llm, LLM_MODEL, CommandRunner
import hashlib
import json


class ProjectVersionsTests(unittest.TestCase):
    def test_failed_dub_retries_in_place_after_restart(self):
        with tempfile.TemporaryDirectory() as temp:
            first_service = ApplicationService()
            project = first_service.create_project(temp, "video.mp4")
            calls = []

            def interrupted(config, progress, runner):
                calls.append(config.version_id)
                raise RuntimeError("TTS line 50 failed")

            with patch("anime_dubber.application.service.run_pipeline", side_effect=interrupted):
                with self.assertRaisesRegex(RuntimeError, "TTS line 50 failed"):
                    first_service.run_sync({"source": "video.mp4", "output_dir": temp})
            dub = first_service.get_project(temp, project["project_id"])["dubs"][0]
            # Simulate a version made before source voice selection existed.
            manifest = Path(first_service.get_project(temp, project["project_id"])["manifest_path"])
            old_manifest = json.loads(manifest.read_text(encoding="utf-8"))
            old_manifest["dubs"][0]["config"].pop("auto_voice_references", None)
            manifest.write_text(json.dumps(old_manifest), encoding="utf-8")
            resumed = ApplicationService()
            def resume_pipeline(cfg, progress, runner):
                self.assertFalse(cfg.auto_voice_references)
                calls.append(cfg.version_id)
                return {}
            with patch("anime_dubber.application.service.run_pipeline", side_effect=resume_pipeline):
                job_id = resumed.resume_dub(temp, project["project_id"], dub["id"])
                for _ in range(100):
                    if resumed.get_job(job_id)["status"] not in {"queued", "running"}:
                        break
                    time.sleep(.01)
            self.assertEqual(resumed.get_job(job_id)["status"], "completed")
            self.assertEqual(calls, [dub["id"], dub["id"]])
            self.assertEqual(len(resumed.get_project(temp, project["project_id"])["dubs"]), 1)
            for _ in range(100):
                if resumed.get_project(temp, project["project_id"])["status"] == "completed":
                    break
                time.sleep(.01)

    def test_pause_then_resume_reuses_the_same_version_and_keeps_subtitles(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp)
            service = ApplicationService()
            project = service.create_project(str(output), "source.mp4", "Episode")
            at_voice = threading.Event()
            calls = []

            def pipeline(config, progress, runner):
                calls.append(config.version_id)
                subtitles = output / "versions" / config.version_id / "en.srt"
                subtitles.parent.mkdir(parents=True, exist_ok=True)
                if not subtitles.exists():
                    subtitles.write_text("Translation finished")
                runner.artifact("translated_srt", subtitles, "en")
                if len(calls) == 1:
                    at_voice.set()
                    while not runner.cancel_event.wait(.01):
                        pass
                    runner.check_cancel()
                self.assertTrue(config.resume)
                self.assertFalse(config.force)
                return {"translated_srt": subtitles}

            with patch("anime_dubber.application.service.run_pipeline", side_effect=pipeline):
                first = service.start_job({"source": "source.mp4", "output_dir": temp})
                self.assertTrue(at_voice.wait(2))
                self.assertTrue(service.pause_job(first))
                for _ in range(100):
                    if service.get_job(first)["status"] == "paused":
                        break
                    time.sleep(.01)
                self.assertEqual(service.get_job(first)["status"], "paused")
                state = service.get_project(temp, project["project_id"])
                self.assertTrue(Path(state["dubs"][0]["artifacts"]["translated_srt"]).exists())
                dub_id = state["dubs"][0]["id"]
                second = service.resume_dub(temp, project["project_id"], dub_id)
                for _ in range(100):
                    if service.get_job(second)["status"] == "completed":
                        break
                    time.sleep(.01)
            self.assertEqual(service.get_job(second)["status"], "completed")
            self.assertEqual(calls, [dub_id, dub_id])
            self.assertEqual(len(service.get_project(temp, project["project_id"])["dubs"]), 1)

    def test_old_english_translation_cache_is_reused_without_loading_model(self):
        with tempfile.TemporaryDirectory() as temp:
            config = Config(source="source.mp4", output_dir=Path(temp), translation="llm")
            segments = [Segment(0, 1, "你好")]
            signature = hashlib.sha1(json.dumps({
                "model": LLM_MODEL, "context": config.context,
                "glossary": config.glossary, "source_text": ["你好"],
            }, ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:12]
            Path(temp, f"translations_llm_{signature}.json").write_text('{"0":"Hello"}')
            result = translate_with_llm(segments, config, Path(temp), CommandRunner(), lambda _: None)
            self.assertEqual(result[0].translated, "Hello")
            # Migration writes a new signature but preserves the old artifact.
            self.assertEqual(len(list(Path(temp).glob("translations_llm_*.json"))), 2)

    def test_multiple_dubs_preserve_versions_and_deletion_is_isolated(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp)
            service = ApplicationService()
            project = service.create_project(str(output), "source.mp4", "Episode One")

            def fake_pipeline(config, progress, runner):
                folder = output / "versions" / config.version_id
                folder.mkdir(parents=True)
                subtitles = folder / "translation.srt"
                subtitles.write_text("1\n00:00:00,000 --> 00:00:01,000\nHello\n")
                runner.artifact("translated_srt", subtitles, config.target_language)
                video = folder / "final.mp4"
                video.write_bytes(config.tts_engine.encode())
                return {"translated_srt": subtitles, "dubbed_video": video}

            with patch("anime_dubber.application.service.run_pipeline", side_effect=fake_pipeline):
                service.run_sync({"source": "source.mp4", "output_dir": str(output), "dub_name": "Version A", "tts": {"provider": "macos"}})
                service.run_sync({"source": "source.mp4", "output_dir": str(output), "dub_name": "Version B", "tts": {"provider": "kokoro"}})

            detail = service.get_project(str(output), project["project_id"])
            self.assertEqual(len(detail["dubs"]), 2)
            self.assertEqual(len(detail["subtitles"]), 2)
            first, second = detail["dubs"]
            first_video = Path(first["artifacts"]["dubbed_video"])
            second_video = Path(second["artifacts"]["dubbed_video"])
            self.assertNotEqual(first_video, second_video)
            self.assertEqual(first_video.read_bytes(), b"macos")
            self.assertEqual(second_video.read_bytes(), b"kokoro")
            service.delete_dub(str(output), project["project_id"], first["id"])
            self.assertFalse(first_video.exists())
            self.assertTrue(second_video.exists())
            self.assertEqual(len(service.get_project(str(output), project["project_id"])["dubs"]), 1)

    def test_srt_and_vtt_are_published_before_voice_generation(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp)
            video = output / "source.mp4"; video.write_bytes(b"video")
            audio = output / "audio.wav"; audio.write_bytes(b"audio")
            events = []
            class Runner:
                def check_cancel(self): pass
                def artifact(self, kind, path, language):
                    events.append((kind, Path(path).exists(), language))

            def translation(segments, *_args):
                segments[0].translated = "Hello"
                return segments

            with patch("anime_dubber.core.download_source", return_value=video), \
                 patch("anime_dubber.core.extract_audio", return_value=audio), \
                 patch("anime_dubber.core.transcribe_audio", return_value=[Segment(0, 1, "你好")]), \
                 patch("anime_dubber.core.translate_with_llm", side_effect=translation):
                config = Config(source=str(video), output_dir=output, mode="subtitles", translation="llm", version_id="sub_test")
                results = run_pipeline(config, lambda _: None, Runner())

            self.assertEqual([e[0] for e in events], ["source_video", "chinese_srt", "chinese_vtt", "translated_srt", "translated_vtt"])
            self.assertTrue(all(exists for _, exists, _ in events))
            self.assertIn("WEBVTT", results["translated_vtt"].read_text())
            self.assertIn("Hello", results["translated_srt"].read_text())
            self.assertEqual(results["translated_srt"].parent.name, "sub_test")

    def test_non_english_voice_constraints_are_explicit(self):
        with tempfile.TemporaryDirectory() as temp:
            service = ApplicationService()
            with self.assertRaisesRegex(ValueError, "ElevenLabs"):
                service.run_sync({"source": "source.mp4", "output_dir": temp, "target_language": "es", "tts": {"provider": "chatterbox"}})
            with self.assertRaisesRegex(ValueError, "Whisper direct"):
                service.run_sync({"source": "source.mp4", "output_dir": temp, "target_language": "es", "mode": "subtitles", "translation": {"provider": "whisper"}})


if __name__ == "__main__":
    unittest.main()
