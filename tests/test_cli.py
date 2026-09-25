from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from anime_dubber.cli import build_parser, default_output_dir


class CliTests(unittest.TestCase):
    def test_default_output_keeps_existing_projects(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            legacy = root / "AnimeDubberOutput"
            current = root / "DubCanvasOutput"
            self.assertEqual(default_output_dir(root), str(current))
            legacy.mkdir()
            self.assertEqual(default_output_dir(root), str(legacy))
            current.mkdir()
            self.assertEqual(default_output_dir(root), str(current))

    def test_run_parser(self):
        args = build_parser().parse_args([
            "run",
            "video.mp4",
            "--series-id",
            "demo",
            "--subtitles-only",
        ])
        self.assertEqual(args.command, "run")
        self.assertEqual(args.source, "video.mp4")
        self.assertEqual(args.series_id, "demo")
        self.assertTrue(args.subtitles_only)
        self.assertEqual(args.source_language, "auto")

    def test_multilingual_languages_and_source_override(self):
        args = build_parser().parse_args(["run", "video.mp4", "--source-language", "ko", "--target-language", "ar"])
        self.assertEqual((args.source_language, args.target_language), ("ko", "ar"))

    def test_analyze_parser(self):
        args = build_parser().parse_args(["analyze", "video.mp4"])
        self.assertEqual(args.command, "analyze")
        self.assertEqual(args.max_speakers, 12)


if __name__ == "__main__":
    unittest.main()
