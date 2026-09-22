import math
import shutil
import tempfile
import unittest
from pathlib import Path

import numpy as np

from anime_dubber.characters import (
    AudioFeatures,
    _acoustic_features,
    _greedy_cluster,
    _infer_voice_class,
    _style_for_segment,
    cosine,
    analyze_characters,
)
from anime_dubber.core import CommandRunner, Segment


class CharacterLogicTests(unittest.TestCase):
    def tone(self, freq, amp=0.2, seconds=1.0, sr=16000):
        t = np.arange(int(sr * seconds), dtype=np.float32) / sr
        return (amp * np.sin(2 * np.pi * freq * t)).astype(np.float32)

    def test_pitch_and_voice_class(self):
        low = _acoustic_features(self.tone(120))
        high = _acoustic_features(self.tone(260))
        self.assertTrue(105 <= low.f0_median <= 140)
        self.assertTrue(235 <= high.f0_median <= 285)
        self.assertEqual(_infer_voice_class(low.f0_median)[0], "male")
        self.assertEqual(_infer_voice_class(high.f0_median)[0], "female")

    def test_acoustic_embeddings_cluster_two_speakers(self):
        embs = [_acoustic_features(self.tone(f)).embedding for f in (120, 125, 280, 275)]
        labels = _greedy_cluster(embs, max_speakers=6, threshold=0.91)
        self.assertEqual(labels[0], labels[1])
        self.assertEqual(labels[2], labels[3])
        self.assertNotEqual(labels[0], labels[2])
        self.assertGreater(cosine(embs[0], embs[1]), 0.95)

    def test_style_detection(self):
        baseline = {"rms": -25.0, "f0": 130.0, "flat": 0.02}
        shout = AudioFeatures(rms_db=-15, f0_median=170, voiced_ratio=.9, flatness=.02)
        whisper = AudioFeatures(rms_db=-36, f0_median=0, voiced_ratio=.20, flatness=.05)
        normal = AudioFeatures(rms_db=-25, f0_median=130, voiced_ratio=.9, flatness=.02)
        self.assertEqual(_style_for_segment(shout, baseline, "住手！")[0], "shouting")
        self.assertEqual(_style_for_segment(whisper, baseline, "别出声")[0], "whispering")
        self.assertEqual(_style_for_segment(normal, baseline, "你好")[0], "normal")


@unittest.skipUnless(shutil.which("ffmpeg"), "ffmpeg required")
class CharacterIntegrationTests(unittest.TestCase):
    def test_full_character_analysis_on_synthetic_audio(self):
        try:
            import soundfile as sf
        except Exception:
            self.skipTest("soundfile unavailable")
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            sr = 16000
            def tone(freq):
                t = np.arange(sr, dtype=np.float32) / sr
                return 0.2 * np.sin(2 * np.pi * freq * t)
            audio = np.concatenate([tone(120), tone(280), tone(125), tone(275)]).astype(np.float32)
            src = d / "vocals.wav"
            sf.write(src, audio, sr, subtype="PCM_16")
            segs = [
                Segment(0, 1, "甲说话"), Segment(1, 2, "乙说话"),
                Segment(2, 3, "甲继续"), Segment(3, 4, "乙继续"),
            ]
            profiles, payload = analyze_characters(
                src, segs, d / "work", d, CommandRunner(), lambda _m: None,
                resume=False, force=True, max_speakers=6, speaker_threshold=.91,
                series_id="test-series", available_voices=[], override_path=None, speaker_backend="acoustic",
            )
            self.assertEqual(len(profiles), 2)
            self.assertEqual(segs[0].speaker_id, segs[2].speaker_id)
            self.assertEqual(segs[1].speaker_id, segs[3].speaker_id)
            self.assertNotEqual(segs[0].speaker_id, segs[1].speaker_id)
            self.assertIn("characters", payload)
            self.assertTrue(all(s.style in {"normal", "shouting", "whispering"} for s in segs))


if __name__ == "__main__":
    unittest.main()
