from __future__ import annotations

import json
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from anime_dubber.application.service import config_from_dict
from anime_dubber.cli import build_parser
from anime_dubber.core import CommandRunner, Config, transcribe_audio
from anime_dubber.providers.asr import resolve_asr_provider
from anime_dubber.providers.translation import ollama_generate
from anime_dubber.providers.tts import (
    _prepare_chatterbox_watermarker,
    automatic_kokoro_voice,
    synthesize_piper,
)


class CrossPlatformProviderTests(unittest.TestCase):
    def test_nested_provider_config(self):
        cfg = config_from_dict({
            "source": "input.mp4",
            "output_dir": "./out",
            "asr": {
                "provider": "faster-whisper",
                "model": "large-v3",
                "device": "cuda",
                "compute_type": "float16",
            },
            "translation": {
                "provider": "ollama",
                "model": "qwen3:8b",
                "ollama_url": "http://localhost:11434",
            },
            "tts": {
                "provider": "piper",
                "piper_model": "./voice.onnx",
                "piper_speaker": 2,
                "rate": 215,
            },
        })
        self.assertEqual(cfg.asr_provider, "faster-whisper")
        self.assertEqual(cfg.faster_whisper_device, "cuda")
        self.assertEqual(cfg.translation, "ollama")
        self.assertEqual(cfg.ollama_model, "qwen3:8b")
        self.assertEqual(cfg.tts_engine, "piper")
        self.assertEqual(cfg.piper_speaker, 2)

    def test_premium_voice_config(self):
        cfg = config_from_dict({
            "source": "input.mp4",
            "output_dir": "./out",
            "tts": {
                "provider": "chatterbox",
                "chatterbox_reference_audio": "./ref.wav",
                "chatterbox_expressiveness": 0.8,
                "chatterbox_device": "mps",
                "chatterbox_turbo": True,
                "kokoro_voice": "af_bella",
            },
        })
        self.assertEqual(cfg.tts_engine, "chatterbox")
        self.assertEqual(cfg.chatterbox_reference_audio, "./ref.wav")
        self.assertAlmostEqual(cfg.chatterbox_expressiveness, 0.8)
        self.assertEqual(cfg.chatterbox_device, "mps")
        self.assertTrue(cfg.chatterbox_turbo)
        self.assertEqual(cfg.kokoro_voice, "af_bella")

    def test_chatterbox_perth_none_falls_back_to_dummy_watermarker(self):
        class DummyWatermarker:
            pass

        fake_perth = types.SimpleNamespace(
            PerthImplicitWatermarker=None,
            DummyWatermarker=DummyWatermarker,
        )
        with patch.dict("sys.modules", {"perth": fake_perth}):
            mode = _prepare_chatterbox_watermarker()

        self.assertEqual(mode, "dummy")
        self.assertIs(fake_perth.PerthImplicitWatermarker, DummyWatermarker)

    def test_chatterbox_keeps_real_perth_watermarker_when_available(self):
        class RealWatermarker:
            pass

        class DummyWatermarker:
            pass

        fake_perth = types.SimpleNamespace(
            PerthImplicitWatermarker=RealWatermarker,
            DummyWatermarker=DummyWatermarker,
        )
        with patch.dict("sys.modules", {"perth": fake_perth}):
            mode = _prepare_chatterbox_watermarker()

        self.assertEqual(mode, "implicit")
        self.assertIs(fake_perth.PerthImplicitWatermarker, RealWatermarker)

    def test_automatic_kokoro_character_voice(self):
        self.assertEqual(
            automatic_kokoro_voice({"voice_class": "female", "age_group": "adult"}),
            "af_bella",
        )
        self.assertEqual(
            automatic_kokoro_voice({"voice_class": "male", "age_group": "older"}),
            "am_michael",
        )

    def test_cli_cross_platform_flags(self):
        args = build_parser().parse_args([
            "run", "input.mp4",
            "--asr", "faster-whisper",
            "--faster-whisper-device", "cuda",
            "--translation", "ollama",
            "--ollama-model", "qwen3:8b",
            "--tts", "piper",
            "--piper-model", "voice.onnx",
        ])
        self.assertEqual(args.asr, "faster-whisper")
        self.assertEqual(args.translation, "ollama")
        self.assertEqual(args.tts, "piper")
        self.assertEqual(args.piper_model, "voice.onnx")

        premium = build_parser().parse_args([
            "run", "input.mp4",
            "--tts", "chatterbox",
            "--chatterbox-reference", "hero.wav",
            "--chatterbox-expressiveness", "0.7",
            "--chatterbox-device", "mps",
        ])
        self.assertEqual(premium.tts, "chatterbox")
        self.assertEqual(premium.chatterbox_reference, "hero.wav")
        self.assertAlmostEqual(premium.chatterbox_expressiveness, 0.7)
        self.assertEqual(premium.chatterbox_device, "mps")

        kokoro = build_parser().parse_args([
            "run", "input.mp4",
            "--tts", "kokoro",
            "--kokoro-voice", "am_adam",
        ])
        self.assertEqual(kokoro.tts, "kokoro")
        self.assertEqual(kokoro.kokoro_voice, "am_adam")

    def test_explicit_asr_aliases(self):
        self.assertEqual(resolve_asr_provider("faster-whisper"), "faster_whisper")
        self.assertEqual(resolve_asr_provider("mlx-whisper"), "mlx_whisper")

    def test_transcribe_routes_to_faster_whisper(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            audio = root / "a.wav"
            audio.write_bytes(b"fake")
            cfg = Config(
                source="input.mp4",
                output_dir=root,
                asr_provider="faster-whisper",
                multi_character=True,
            )
            rows = [
                {"start": 0.0, "end": 1.0, "text": "你好"},
                {"start": 1.0, "end": 2.0, "text": "世界"},
            ]
            with patch("anime_dubber.providers.asr.faster_whisper_segments", return_value=rows) as mocked:
                out = transcribe_audio(audio, cfg, root, CommandRunner(), lambda _m: None)
            self.assertEqual([x.text for x in out], ["你好", "世界"])
            mocked.assert_called_once()

    def test_mlx_provider_migrates_legacy_transcript_cache(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            audio = root / "a.wav"
            audio.write_bytes(b"fake")
            legacy = root / "transcript_zh_v3.json"
            legacy.write_text(json.dumps([
                {"start": 0.0, "end": 1.0, "text": "你好"},
            ]), encoding="utf-8")
            cfg = Config(
                source="input.mp4",
                output_dir=root,
                asr_provider="mlx-whisper",
                resume=True,
            )
            with patch("anime_dubber.providers.asr.resolve_asr_provider", return_value="mlx_whisper"):
                out = transcribe_audio(audio, cfg, root, CommandRunner(), lambda _m: None)
            self.assertEqual(out[0].text, "你好")
            self.assertTrue((root / "transcript_zh_mlx_whisper_v4.json").exists())

    def test_ollama_generate_parses_response(self):
        class Response:
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return False
            def read(self):
                return json.dumps({"response": "Hello"}).encode("utf-8")

        with patch("urllib.request.urlopen", return_value=Response()):
            text = ollama_generate(
                base_url="http://127.0.0.1:11434",
                model="qwen3:4b",
                prompt="translate",
            )
        self.assertEqual(text, "Hello")

    def test_piper_cli_writes_output(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            model = root / "voice.onnx"
            model.write_bytes(b"model")
            output = root / "out.wav"

            class FakeProcess:
                returncode = 0
                def __init__(self, cmd, **_kwargs):
                    self.cmd = cmd
                def communicate(self, _text):
                    path = Path(self.cmd[self.cmd.index("--output_file") + 1])
                    path.write_bytes(b"RIFF" + b"x" * 100)
                    return "", ""

            with patch("anime_dubber.providers.tts.piper_executable", return_value="piper"), patch(
                "anime_dubber.providers.tts.subprocess.Popen", FakeProcess
            ):
                synthesize_piper("hello", output, model_path=str(model), rate=205)
            self.assertTrue(output.exists())
            self.assertGreater(output.stat().st_size, 44)


if __name__ == "__main__":
    unittest.main()
