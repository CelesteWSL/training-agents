from training_agents.default_config import DEFAULT_CONFIG


def get_language_instruction() -> str:
    """Return a prompt instruction for the configured output language.

    Returns empty string when Chinese (no extra tokens needed).
    Returns a dedicated instruction string for other languages,
    appended to the system prompt.
    """
    lang = DEFAULT_CONFIG.get("output_language", "Chinese")
    if lang.strip().lower() in ("chinese", "中文"):
        return ""
    return f" Write your entire response in {lang}."