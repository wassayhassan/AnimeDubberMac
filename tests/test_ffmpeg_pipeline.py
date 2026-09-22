import platform
import shutil
import subprocess
import tempfile
import unittest
import wave
from unittest.mock import patch
from pathlib import Path

from anime_dubber.core import (
    CommandRunner,
    Config,
    Segment,
    ffprobe_duration,
    mix_background_and_dub,
    build_dialogue_safe_background,
    render_dub_timeline,
    prepare_tts_clip,
    synthesize_macos,
    _pitch_filters,
    _ffconcat_quote,
)


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "ffmpeg/ffprobe required")
class FfmpegPipelineTests(unittest.TestCase):
    def test_local_wav_tts_renders_to_distinct_output_and_resumes(self):
        with tempfile.TemporaryDirectory() as td:
            directory = Path(td)
            raw = directory / "raw.wav"
            subprocess.run([
                "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                "-f", "lavfi", "-i", "sine=frequency=440:duration=2.0",
                "-ac", "1", "-ar", "44100", str(raw),
            ], check=True)

            cfg = Config(source="x", output_dir=directory, tts_engine="chatterbox")
            segment = Segment(0.0, 0.5, "你好", "Hello")
            runner = CommandRunner()
            with patch("anime_dubber.providers.tts.synthesize_chatterbox", side_effect=lambda _text, path, **_kw: shutil.copyfile(raw, path)) as synthesize:
                first = prepare_tts_clip(segment, 0, directory / "tts", cfg, runner, lambda _m: None)
                second = prepare_tts_clip(segment, 0, directory / "tts", cfg, runner, lambda _m: None)

            self.assertEqual(first, second)
            self.assertIn("_processed.wav", first.name)
            self.assertEqual(synthesize.call_count, 1)
            self.assertGreater(ffprobe_duration(first, runner), 0.1)
            self.assertLessEqual(ffprobe_duration(first, runner), 0.53)
            self.assertFalse(any((directory / "tts").glob("*_rendering.wav")))

    def test_timeline_and_music_sfx_mix_keep_duration(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            subprocess.run([
                "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                "-f", "lavfi", "-i", "sine=frequency=220:duration=31",
                "-ac", "2", "-ar", "44100", str(d / "bg.wav"),
            ], check=True)
            clips = []
            for i, freq in enumerate((880, 660)):
                p = d / f"clip_{i}.wav"
                subprocess.run([
                    "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                    "-f", "lavfi", "-i", f"sine=frequency={freq}:duration=0.4",
                    "-ac", "2", "-ar", "44100", str(p),
                ], check=True)
                clips.append(p)
            segs = [Segment(0.5, 0.9, "a", "A"), Segment(30.2, 30.6, "b", "B")]
            cfg = Config(source="x", output_dir=d, chunk_seconds=30, ducking=True)
            runner = CommandRunner()
            timeline = render_dub_timeline(segs, clips, 31.0, d, cfg, runner, lambda _m: None)
            mixed = mix_background_and_dub(d / "bg.wav", timeline, d, cfg, runner, lambda _m: None)
            self.assertGreaterEqual(ffprobe_duration(timeline, runner), 30.99)
            self.assertGreaterEqual(ffprobe_duration(mixed, runner), 30.99)


    def test_dialogue_safe_background_keeps_duration(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            original = d / "original.wav"
            separated = d / "no_vocals.wav"
            subprocess.run([
                "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                "-f", "lavfi", "-i", "sine=frequency=220:duration=3",
                "-ac", "2", "-ar", "44100", str(original),
            ], check=True)
            subprocess.run([
                "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                "-f", "lavfi", "-i", "sine=frequency=440:duration=3",
                "-ac", "2", "-ar", "44100", str(separated),
            ], check=True)
            cfg = Config(source="x", output_dir=d, chunk_seconds=30, ducking=False)
            runner = CommandRunner()
            bed = build_dialogue_safe_background(
                original, separated, [Segment(1.0, 1.5, "hello")], 3.0, d, cfg, runner, lambda _m: None
            )
            self.assertTrue(bed.exists())
            self.assertGreaterEqual(ffprobe_duration(bed, runner), 2.99)

    def test_ffconcat_quote_handles_apostrophe(self):
        quoted = _ffconcat_quote(Path("/tmp/O'Brien/chunk.wav"))
        self.assertEqual(quoted, "'/tmp/O'\\''Brien/chunk.wav'")

    def test_timeline_places_voice_at_segment_start_with_ms_precision(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            clip = d / "sync_clip.wav"
            subprocess.run([
                "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                "-f", "lavfi", "-i", "sine=frequency=1000:duration=0.20",
                "-ac", "2", "-ar", "44100", str(clip),
            ], check=True)

            seg = Segment(1.234, 1.434, "a", "A")
            cfg = Config(source="x", output_dir=d, chunk_seconds=30, force=True)
            runner = CommandRunner()
            timeline = render_dub_timeline([seg], [clip], 2.0, d, cfg, runner, lambda _m: None)

            with wave.open(str(timeline), "rb") as wav:
                rate = wav.getframerate()
                channels = wav.getnchannels()
                width = wav.getsampwidth()
                self.assertEqual(width, 2)
                frames = wav.readframes(wav.getnframes())

            import array
            samples = array.array("h")
            samples.frombytes(frames)
            first_frame = None
            threshold = 100
            for frame_index in range(len(samples) // channels):
                base = frame_index * channels
                if any(abs(samples[base + ch]) > threshold for ch in range(channels)):
                    first_frame = frame_index
                    break

            self.assertIsNotNone(first_frame)
            onset = first_frame / rate
            self.assertLessEqual(abs(onset - 1.234), 0.012)

    def test_timeline_works_in_apostrophe_path(self):
        with tempfile.TemporaryDirectory(prefix="anime_dubber_O'Brien_") as td:
            d = Path(td)
            clip = d / "clip.wav"
            subprocess.run([
                "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                "-f", "lavfi", "-i", "sine=frequency=440:duration=0.25",
                "-ac", "2", "-ar", "44100", str(clip),
            ], check=True)
            segs = [Segment(0.2, 0.45, "a", "A")]
            cfg = Config(source="x", output_dir=d, chunk_seconds=30, ducking=False)
            runner = CommandRunner()
            timeline = render_dub_timeline(segs, [clip], 1.0, d, cfg, runner, lambda _m: None)
            self.assertTrue(timeline.exists())
            self.assertGreaterEqual(ffprobe_duration(timeline, runner), 0.99)

    def test_tts_clip_cannot_overrun_source_dialogue_window(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            long_source = d / "long.wav"
            subprocess.run([
                "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                "-f", "lavfi", "-i", "sine=frequency=440:duration=2.0",
                "-ac", "1", "-ar", "44100", str(long_source),
            ], check=True)

            def fake_say(_text, out_aiff, _config, _runner, voice="", rate=205):
                shutil.copyfile(long_source, out_aiff)

            cfg = Config(source="x", output_dir=d, tts_engine="macos", force=True)
            seg = Segment(5.0, 5.40, "你好", "Hello")
            runner = CommandRunner()
            with patch("anime_dubber.core.synthesize_macos", side_effect=fake_say):
                clip = prepare_tts_clip(seg, 0, d / "tts", cfg, runner, lambda _m: None)

            duration = ffprobe_duration(clip, runner)
            self.assertLessEqual(duration, 0.43)

    def test_pitch_and_style_filter_chain_is_valid(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            src = d / "src.wav"
            out = d / "out.wav"
            subprocess.run([
                "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                "-f", "lavfi", "-i", "sine=frequency=220:duration=1",
                "-ac", "2", "-ar", "44100", str(src),
            ], check=True)
            filters = _pitch_filters(3.2) + [
                "acompressor=threshold=0.125:ratio=3:attack=5:release=90",
                "volume=1.2",
                "aresample=44100",
                "aformat=sample_fmts=s16:channel_layouts=stereo",
            ]
            subprocess.run([
                "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                "-i", str(src), "-af", ",".join(filters),
                "-c:a", "pcm_s16le", str(out),
            ], check=True)
            dur = ffprobe_duration(out, CommandRunner())
            self.assertTrue(0.95 <= dur <= 1.05)


@unittest.skipUnless(platform.system() == "Darwin" and shutil.which("say"), "macOS say required")
class MacTtsTests(unittest.TestCase):
    def test_say_can_render_to_file(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            out = d / "test.aiff"
            cfg = Config(source="x", output_dir=d, tts_rate=210)
            runner = CommandRunner()
            synthesize_macos("This is a local voice test.", out, cfg, runner)
            self.assertTrue(out.exists())
            self.assertGreater(out.stat().st_size, 1000)


if __name__ == "__main__":
    unittest.main()
