import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from anime_dubber.characters import CharacterProfile
from anime_dubber.core import CommandRunner, Config, Segment, run_pipeline


class PipelineOrchestrationTests(unittest.TestCase):
    def test_multi_character_profiles_reach_tts(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            video = d / "video.mp4"; video.write_bytes(b"video")
            audio = d / "audio.wav"; audio.write_bytes(b"audio")
            vocals = d / "vocals.wav"; vocals.write_bytes(b"vocals")
            bg = d / "bg.wav"; bg.write_bytes(b"bg")
            timeline = d / "timeline.wav"; timeline.write_bytes(b"timeline")
            mixed = d / "mixed.m4a"; mixed.write_bytes(b"mixed")
            segs = [Segment(0, 1, "甲"), Segment(1, 2, "乙")]
            p1 = CharacterProfile(id="CHAR_001", display_name="Lead", role="lead", voice_class="male", macos_voice="Alex", tts_rate=200)
            p2 = CharacterProfile(id="CHAR_002", display_name="Side", role="supporting", voice_class="female", macos_voice="Samantha", tts_rate=210)

            def fake_translate(items, *_args, **_kwargs):
                items[0].translated = "One"; items[1].translated = "Two"; return items

            def fake_analyze(_vocals, items, *_args, **_kwargs):
                items[0].speaker_id = "CHAR_001"; items[0].style = "shouting"
                items[1].speaker_id = "CHAR_002"; items[1].style = "whispering"
                payload = {"version": 3, "characters": [p1.to_dict(), p2.to_dict()], "segments": []}
                return [p1, p2], payload

            seen = []
            published = []
            runner = CommandRunner()
            runner.artifact = lambda kind, path, language: published.append((kind, Path(path).exists()))
            def fake_tts(seg, index, tts_dir, config, runner, progress, profile=None):
                self.assertIn(("translated_srt", True), published)
                seen.append((seg.speaker_id, seg.style, (profile or {}).get("macos_voice")))
                out = d / f"clip{index}.wav"; out.write_bytes(b"clip"); return out

            cfg = Config(source=str(video), output_dir=d / "out", mode="dub", translation="llm", multi_character=True, series_id="series")
            with patch("anime_dubber.core.download_source", return_value=video), \
                 patch("anime_dubber.core.extract_audio", return_value=audio), \
                 patch("anime_dubber.core.separate_dialogue", return_value=(vocals, bg)), \
                 patch("anime_dubber.core.transcribe_audio", return_value=segs), \
                 patch("anime_dubber.core.translate_with_llm", side_effect=fake_translate), \
                 patch("anime_dubber.core.list_macos_voices", return_value=["Alex", "Samantha"]), \
                 patch("anime_dubber.characters.analyze_characters", side_effect=fake_analyze), \
                 patch("anime_dubber.core.prepare_tts_clip", side_effect=fake_tts), \
                 patch("anime_dubber.core.ffprobe_duration", return_value=2.0), \
                 patch("anime_dubber.core.render_dub_timeline", return_value=timeline), \
                 patch("anime_dubber.core.build_dialogue_safe_background", return_value=bg), \
                 patch("anime_dubber.core.mix_background_and_dub", return_value=mixed), \
                 patch("anime_dubber.core.mux_video", side_effect=lambda _v, _a, f, _r, _p: f.write_bytes(b"final")):
                results = run_pipeline(cfg, lambda _m: None, runner)

            self.assertEqual(seen, [
                ("CHAR_001", "shouting", "Alex"),
                ("CHAR_002", "whispering", "Samantha"),
            ])
            self.assertTrue(results["dubbed_video"].exists())
            self.assertTrue(results["character_map"].exists())


if __name__ == "__main__":
    unittest.main()
