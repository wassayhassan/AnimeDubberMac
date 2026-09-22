"""Optional platform/provider integrations used by the shared pipeline."""

from .asr import faster_whisper_segments, resolve_asr_provider
from .translation import translate_with_ollama
from .tts import (
    automatic_kokoro_voice,
    chatterbox_available,
    kokoro_available,
    piper_available,
    premium_voice_status,
    synthesize_chatterbox,
    synthesize_kokoro,
    synthesize_piper,
)

__all__ = [
    "faster_whisper_segments",
    "resolve_asr_provider",
    "translate_with_ollama",
    "automatic_kokoro_voice",
    "chatterbox_available",
    "kokoro_available",
    "piper_available",
    "premium_voice_status",
    "synthesize_chatterbox",
    "synthesize_kokoro",
    "synthesize_piper",
]
