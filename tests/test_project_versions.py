import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from anime_dubber.application.service import ApplicationService
from anime_dubber.core import Config, Segment, run_pipeline


class ProjectVersionsTests(unittest.TestCase):
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
