from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from anime_dubber.core import CommandRunner, Config, ReviewRequired, Segment, TimingOverlapError, run_pipeline
from anime_dubber.review import review_subtitles
from anime_dubber.timing import TimingRewriter, usable_rewrite


def srt(texts):
    return "\n\n".join(
        f"{n}\n00:00:0{n-1},000 --> 00:00:0{n-1},500\n{text}"
        for n, text in enumerate(texts, 1)
    ) + "\n"


class ReviewTests(unittest.TestCase):
    def test_auto_rewrite_measures_voice_and_finishes_without_review(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            video = base / "source.mp4"; video.write_bytes(b"video")
            audio = base / "audio.wav"; audio.write_bytes(b"audio")
            cfg = Config(source=str(video), output_dir=base / "out", version_id="auto_fit",
                         translation="llm", multi_character=False)
            original = "The once famous Tang Sect"
            tested = []

            def prepare(seg, *_args, **_kwargs):
                tested.append(seg.translated)
                if seg.translated in (original, "The Tang Sect"):
                    raise TimingOverlapError(0, 3.2 if seg.translated == original else 3.0,
                                             2.8, seg.translated)
                return audio

            def transcribe(*_args, **_kwargs):
                return [Segment(0, .5, "唐门")]

            def translate(items, *_args):
                items[0].translated = original
                return items

            with patch("anime_dubber.core.download_source", return_value=video), \
                 patch("anime_dubber.core.extract_audio", return_value=audio), \
                 patch("anime_dubber.core.separate_dialogue", return_value=(audio, audio)), \
                 patch("anime_dubber.core.transcribe_audio", side_effect=transcribe), \
                 patch("anime_dubber.core.translate_with_llm", side_effect=translate), \
                 patch("anime_dubber.core.prepare_tts_clip", side_effect=prepare), \
                 patch("anime_dubber.timing.TimingRewriter.candidate", side_effect=["The Tang Sect", "Tang Sect"]) as candidate, \
                 patch("anime_dubber.core.ffprobe_duration", return_value=2.8), \
                 patch("anime_dubber.core.render_dub_timeline", return_value=audio), \
                 patch("anime_dubber.core.build_dialogue_safe_background", return_value=audio), \
                 patch("anime_dubber.core.mix_background_and_dub", return_value=audio), \
                 patch("anime_dubber.core.mux_video", side_effect=lambda _v, _a, dest, *_: dest.write_bytes(b"video")):
                result = run_pipeline(cfg, lambda _: None, CommandRunner())
                resumed = run_pipeline(cfg, lambda _: None, CommandRunner())
            self.assertEqual(candidate.call_count, 2)
            self.assertEqual(tested, [original, "The Tang Sect", "Tang Sect", "Tang Sect"])
            self.assertIn("Tang Sect", result["translated_srt"].read_text())
            self.assertIn("Tang Sect", resumed["translated_srt"].read_text())
            fixes = json.loads(next((base / "out" / "versions" / "auto_fit").glob("*.timing-fixes.json")).read_text())
            self.assertEqual(fixes["1"]["replacement"], "Tang Sect")

    def test_timing_candidate_keeps_names_and_numbers(self):
        self.assertFalse(usable_rewrite("The Tang Sect has 3 gates", "The sect has three gates"))
        self.assertFalse(usable_rewrite("The Tang Sect has 3 gates", "The Tang Sect has gates"))
        self.assertTrue(usable_rewrite("The Tang Sect has 3 gates", "Tang Sect: 3 gates"))

    def test_timing_fallback_speeds_original_and_resumes_without_rewriting(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            video = base / "source.mp4"; video.write_bytes(b"video")
            audio = base / "audio.wav"; audio.write_bytes(b"audio")
            cfg = Config(source=str(video), output_dir=base / "out", version_id="tempo",
                         translation="llm", multi_character=False)
            calls = []

            def prepare(seg, *_args, **kwargs):
                calls.append((seg.translated, kwargs.get("max_tempo", 1.0)))
                if kwargs.get("max_tempo", 1.0) < 1.5:
                    raise TimingOverlapError(0, 3.2, 2.8, seg.translated)
                return audio

            def transcribe(*_args, **_kwargs):
                return [Segment(0, .5, "唐门")]

            def translate(items, *_args):
                items[0].translated = "The once famous Tang Sect"
                return items

            with patch("anime_dubber.core.download_source", return_value=video), \
                 patch("anime_dubber.core.extract_audio", return_value=audio), \
                 patch("anime_dubber.core.separate_dialogue", return_value=(audio, audio)), \
                 patch("anime_dubber.core.transcribe_audio", side_effect=transcribe), \
                 patch("anime_dubber.core.translate_with_llm", side_effect=translate), \
                 patch("anime_dubber.core.prepare_tts_clip", side_effect=prepare), \
                 patch("anime_dubber.timing.TimingRewriter.candidate", return_value=None) as candidate, \
                 patch("anime_dubber.core.ffprobe_duration", return_value=2.8), \
                 patch("anime_dubber.core.render_dub_timeline", return_value=audio), \
                 patch("anime_dubber.core.build_dialogue_safe_background", return_value=audio), \
                 patch("anime_dubber.core.mix_background_and_dub", return_value=audio), \
                 patch("anime_dubber.core.mux_video", side_effect=lambda _v, _a, dest, *_: dest.write_bytes(b"video")):
                result = run_pipeline(cfg, lambda _: None, CommandRunner())
                run_pipeline(cfg, lambda _: None, CommandRunner())
            self.assertEqual(candidate.call_count, 3)
            self.assertEqual(calls, [("The once famous Tang Sect", 1.0),
                                     ("The once famous Tang Sect", 1.5),
                                     ("The once famous Tang Sect", 1.5)])
            self.assertIn("The once famous Tang Sect", result["translated_srt"].read_text())
            fixes = json.loads(next((base / "out" / "versions" / "tempo").glob("*.timing-fixes.json")).read_text())
            self.assertEqual(fixes["1"]["max_tempo"], 1.5)

    def test_rewriter_requests_measured_gap_and_checks_candidate(self):
        prompts = []
        fake = type("FakeMLX", (), {
            "load": staticmethod(lambda _: (object(), object())),
            "generate": staticmethod(lambda _model, _tokenizer, **kwargs: (
                prompts.append(kwargs["prompt"]) or '[{"id": 1, "text": "Tang Sect, once famous"}]')),
        })()
        cfg = Config(source="video", output_dir=Path("out"))
        with patch.dict(sys.modules, {"mlx_lm": fake}):
            candidate = TimingRewriter(cfg).candidate("唐门", "The Tang Sect was once famous",
                                                       3.29, 2.82, 0, [], CommandRunner())
        self.assertEqual(candidate, "Tang Sect, once famous")
        self.assertIn("3.29s", prompts[0])
        self.assertIn("2.82s", prompts[0])

    def test_natural_speech_overlap_pauses_for_edit_and_resumes(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            video = base / "source.mp4"; video.write_bytes(b"video")
            audio = base / "audio.wav"; audio.write_bytes(b"audio")
            cfg = Config(source=str(video), output_dir=base / "out", version_id="dub_timing",
                         translation="llm", multi_character=False, review_before_dub=False)
            runner = CommandRunner()
            generated = []

            def transcribe(*_args, **_kwargs):
                return [Segment(0, 0.5, "你好")]

            def translate(items, *_args):
                items[0].translated = "A long greeting"
                return items

            def prepare(seg, *_args, **_kwargs):
                generated.append(seg.translated)
                if seg.translated == "A long greeting":
                    raise TimingOverlapError(0, 1.5, 1.0, seg.translated)
                return audio

            model_attempts = []
            def model_review(command, **_kwargs):
                model = command[command.index("--model") + 1]
                model_attempts.append(model)
                if model == cfg.review_model:
                    raise ValueError("Larger model unavailable")
                report = Path(command[command.index("--report") + 1])
                data = json.loads(report.read_text(encoding="utf-8"))
                data["flags"][0]["suggestion"] = "Hi"
                report.write_text(json.dumps(data), encoding="utf-8")
            runner.run = model_review

            with patch("anime_dubber.core.download_source", return_value=video), \
                 patch("anime_dubber.core.extract_audio", return_value=audio), \
                 patch("anime_dubber.core.separate_dialogue", return_value=(audio, audio)), \
                 patch("anime_dubber.core.transcribe_audio", side_effect=transcribe), \
                 patch("anime_dubber.core.translate_with_llm", side_effect=translate), \
                 patch("anime_dubber.core.prepare_tts_clip", side_effect=prepare), \
                 patch("anime_dubber.core.ffprobe_duration", return_value=1.0), \
                 patch("anime_dubber.core.render_dub_timeline", return_value=audio), \
                 patch("anime_dubber.core.build_dialogue_safe_background", return_value=audio), \
                 patch("anime_dubber.core.mix_background_and_dub", return_value=audio), \
                 patch("anime_dubber.core.mux_video", side_effect=lambda _v, _a, dest, *_: dest.write_bytes(b"video")):
                with patch("anime_dubber.core.platform.system", return_value="Darwin"), \
                     patch("anime_dubber.core.platform.machine", return_value="arm64"):
                    with self.assertRaises(ReviewRequired):
                        run_pipeline(cfg, lambda _: None, runner)
                report = next((base / "out" / "versions" / "dub_timing").glob("*.review.json"))
                flagged = json.loads(report.read_text())
                self.assertEqual(flagged["priority_cues"], [1])
                self.assertIn("speech_overlap", flagged["flags"][0]["reasons"])
                self.assertEqual(flagged["flags"][0]["suggestion"], "Hi")
                self.assertEqual(model_attempts, [cfg.review_model, cfg.llm_model])
                approval = report.with_name(report.name.replace(".review.json", ".review-approval.json"))
                approval.write_text(json.dumps({"signature": flagged["signature"],
                                                "revisions": {"1": "Hello"}}))
                result = run_pipeline(cfg, lambda _: None, runner)
            self.assertEqual(generated, ["A long greeting", "A long greeting", "Hello"])
            self.assertIn("Hello", result["translated_srt"].read_text())

    def test_flags_source_and_translation_without_changing_srt(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            original = base / "zh.srt"
            translated = base / "en.srt"
            report = base / "review.json"
            original.write_text(srt(["老六", "Привет 你好"]), encoding="utf-8")
            translated.write_text(srt(["Old Six", "Chinese 你好"]), encoding="utf-8")
            before = translated.read_bytes()
            result = review_subtitles(original, translated, report)
            self.assertEqual(result["flagged_cues"], 2)
            self.assertIn("literal_idiom", result["flags"][0]["reasons"])
            self.assertIn("mixed_script_in_source", result["flags"][1]["reasons"])
            self.assertIn("untranslated_chinese", result["flags"][1]["reasons"])
            self.assertEqual(before, translated.read_bytes())
            self.assertEqual(json.loads(report.read_text())["flags"], result["flags"])

    def test_review_resume_skips_completed_model_suggestions(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            a, b, report = base / "zh.srt", base / "en.srt", base / "review.json"
            a.write_text(srt(["老六", "逼王"]), encoding="utf-8")
            b.write_text(srt(["Old Six", "Force the King"]), encoding="utf-8")
            class Tokenizer:
                chat_template = None
            calls = []
            def fake_generate(*args, **kwargs):
                calls.append(kwargs["prompt"])
                return '[{"id": %s, "text": "Better line"}]' % len(calls)
            with patch.dict("sys.modules", {"mlx_lm": type("FakeMLX", (), {
                "load": staticmethod(lambda _: (object(), Tokenizer())),
                "generate": staticmethod(fake_generate),
            })()}):
                one = review_subtitles(a, b, report, model="test", max_lines=1)
                self.assertEqual(one["flagged_cues"], 2)
                self.assertEqual(one["sampled_cues"], 1)
                two = review_subtitles(a, b, report, model="test", max_lines=1)
                self.assertEqual(len(calls), 1)
                self.assertEqual(two["flags"][0]["suggestion"], "Better line")
            # Pipeline's fast flagging pass must retain an earlier model review.
            three = review_subtitles(a, b, report)
            self.assertEqual(three["flags"][0]["suggestion"], "Better line")

    def test_focused_model_review_retains_all_priority_cues(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            a, b, report = base / "zh.srt", base / "en.srt", base / "review.json"
            a.write_text(srt(["老六", "逼王"]), encoding="utf-8")
            b.write_text(srt(["Old Six", "Force the King"]), encoding="utf-8")
            class Tokenizer:
                chat_template = None
            prompts = []
            def fake_generate(*args, **kwargs):
                prompts.append(kwargs["prompt"])
                return '[{"id": 2, "text": "Show-off"}]'
            with patch.dict("sys.modules", {"mlx_lm": type("FakeMLX", (), {
                "load": staticmethod(lambda _: (object(), Tokenizer())),
                "generate": staticmethod(fake_generate),
            })()}):
                result = review_subtitles(a, b, report, model="test", focus_cues={2})
            self.assertEqual(result["priority_cues"], [1, 2])
            self.assertEqual(len(prompts), 1)
            self.assertEqual(result["flags"][1]["suggestion"], "Show-off")

    def test_timing_suggestion_uses_measured_gap_instead_of_subtitle_window(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            a, b, report = base / "zh.srt", base / "en.srt", base / "en.review.json"
            a.write_text(srt(["来听故事"]), encoding="utf-8")
            b.write_text(srt(["Come and listen to this very long story about the world"]), encoding="utf-8")
            (base / "en.timing.json").write_text(json.dumps({"1": {
                "attempted_translation": "Come and listen to this very long story about the world",
                "duration": 13.4, "available": 11.5}}), encoding="utf-8")
            class Tokenizer:
                chat_template = None
            prompts = []
            def fake_generate(*args, **kwargs):
                prompts.append(kwargs["prompt"])
                return '[{"id": 1, "text": "Hear the story of this world."}]'
            with patch.dict("sys.modules", {"mlx_lm": type("FakeMLX", (), {
                "load": staticmethod(lambda _: (object(), Tokenizer())),
                "generate": staticmethod(fake_generate),
            })()}):
                result = review_subtitles(a, b, report, model="test", focus_cues={1})
            self.assertIn("13.40s", prompts[0])
            self.assertIn("11.50s", prompts[0])
            self.assertNotIn("Subtitle time window: 0.50s", prompts[0])
            self.assertEqual(result["flags"][0]["suggestion"], "Hear the story of this world.")

    def test_non_chinese_source_is_prioritized_for_retranscription(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            a, b = base / "zh.srt", base / "en.srt"
            a.write_text(srt(["ール Muchasdal whats nave kali"]), encoding="utf-8")
            b.write_text(srt(["Ruu, Muchasdal, what's nave kali?"]), encoding="utf-8")
            result = review_subtitles(a, b, base / "review.json", sample_seconds=300)
            self.assertIn("non_chinese_source", result["flags"][0]["reasons"])
            self.assertEqual(result["sampled_cues"], 1)

    def test_review_pauses_before_voices_and_resume_applies_approved_cue(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            video = base / "source.mp4"; video.write_bytes(b"video")
            audio = base / "audio.wav"; audio.write_bytes(b"audio")
            vocals = base / "vocals.wav"; vocals.write_bytes(b"vocals")
            background = base / "background.wav"; background.write_bytes(b"background")
            timeline = base / "timeline.wav"; timeline.write_bytes(b"timeline")
            mixed = base / "mixed.m4a"; mixed.write_bytes(b"mixed")
            clips = []
            config = Config(source=str(video), output_dir=base / "out", version_id="dub_review",
                            translation="llm", multi_character=False, review_before_dub=True)
            runner = CommandRunner()
            def model_review(command, **_kwargs):
                self.assertIn("review-subtitles", command)
                report = Path(command[command.index("--report") + 1])
                data = json.loads(report.read_text())
                data["flags"][0]["suggestion"] = "A sly trickster"
                report.write_text(json.dumps(data))
            runner.run = model_review
            def transcribe(*_args, **_kwargs):
                return [Segment(0, .5, "老六")]
            def translate(items, *_args):
                items[0].translated = "Old Six"
                return items
            def prepare(seg, *_args, **_kwargs):
                clips.append(seg.translated)
                return audio
            with patch("anime_dubber.core.download_source", return_value=video), \
                 patch("anime_dubber.core.extract_audio", return_value=audio), \
                 patch("anime_dubber.core.separate_dialogue", return_value=(vocals, background)), \
                 patch("anime_dubber.core.transcribe_audio", side_effect=transcribe), \
                 patch("anime_dubber.core.translate_with_llm", side_effect=translate), \
                 patch("anime_dubber.core.platform.system", return_value="Darwin"), \
                 patch("anime_dubber.core.platform.machine", return_value="arm64"), \
                 patch("anime_dubber.core.prepare_tts_clip", side_effect=prepare), \
                 patch("anime_dubber.core.ffprobe_duration", return_value=1.0), \
                 patch("anime_dubber.core.render_dub_timeline", return_value=timeline), \
                 patch("anime_dubber.core.build_dialogue_safe_background", return_value=background), \
                 patch("anime_dubber.core.mix_background_and_dub", return_value=mixed), \
                 patch("anime_dubber.core.mux_video", side_effect=lambda _v, _a, dest, *_: dest.write_bytes(b"video")):
                with self.assertRaises(ReviewRequired):
                    run_pipeline(config, lambda _: None, runner)
                self.assertEqual(clips, [])
                report = next((base / "out" / "versions" / "dub_review").glob("*.review.json"))
                data = json.loads(report.read_text())
                approval = report.with_name(report.name.replace(".review.json", ".review-approval.json"))
                approval.write_text(json.dumps({"signature": data["signature"], "revisions": {"1": "A sly trickster"}}))
                runner.run = lambda *_args, **_kwargs: self.fail("Model must not run after approval")
                result = run_pipeline(config, lambda _: None, runner)
            self.assertEqual(clips, ["A sly trickster"])
            self.assertIn("A sly trickster", result["translated_srt"].read_text())


if __name__ == "__main__":
    unittest.main()
