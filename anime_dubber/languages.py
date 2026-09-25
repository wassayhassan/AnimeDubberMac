"""Language codes and target-language capabilities shared by UI-facing jobs."""

TARGET_LANGUAGES = {
    "en": "English", "es": "Spanish", "fr": "French", "de": "German",
    "ja": "Japanese", "ko": "Korean", "zh": "Chinese", "pt": "Portuguese",
    "it": "Italian", "hi": "Hindi", "ar": "Arabic",
}


def source_name(code: str) -> str:
    return TARGET_LANGUAGES.get(code, code.upper() if code != "auto" else "the detected language")


def target_name(code: str) -> str:
    return TARGET_LANGUAGES[code]
