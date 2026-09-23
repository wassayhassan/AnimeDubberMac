from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from anime_dubber.review import review_subtitles


def srt(texts):
    return "\n\n".join(
        f"{n}\n00:00:0{n-1},000 --> 00:00:0{n-1},500\n{text}"
        for n, text in enumerate(texts, 1)
    ) + "\n"


class ReviewTests(unittest.TestCase):
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

    def test_non_chinese_source_is_prioritized_for_retranscription(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            a, b = base / "zh.srt", base / "en.srt"
            a.write_text(srt(["ール Muchasdal whats nave kali"]), encoding="utf-8")
            b.write_text(srt(["Ruu, Muchasdal, what's nave kali?"]), encoding="utf-8")
            result = review_subtitles(a, b, base / "review.json", sample_seconds=300)
            self.assertIn("non_chinese_source", result["flags"][0]["reasons"])
            self.assertEqual(result["sampled_cues"], 1)


if __name__ == "__main__":
    unittest.main()
