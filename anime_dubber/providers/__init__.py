"""Optional platform/provider integrations used by the shared pipeline."""

from .asr import faster_whisper_segments, resolve_asr_provider
from .translation import translate_with_ollama
from .tts import piper_available, synthesize_piper

__all__ = [
    "faster_whisper_segments",
    "resolve_asr_provider",
    "translate_with_ollama",
    "piper_available",
    "synthesize_piper",
]
