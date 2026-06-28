import os

_TRAININGAGENTS_HOME = os.path.join(os.path.expanduser("~"), ".training_agents")

_ENV_OVERRIDES = {
    "LLM_PROVIDER":         "llm_provider",
    "DEEP_THINK_LLM":       "deep_think_llm",
    "QUICK_THINK_LLM":      "quick_think_llm",
    "LLM_BACKEND_URL":      "backend_url",
    "OUTPUT_LANGUAGE":      "output_language",
    "CHECKPOINT_ENABLED":   "checkpoint_enabled",
}

def _coerce(value: str, reference):
    """Coerce env-var string to the type of the existing default value."""
    if isinstance(reference, bool):
        return value.strip().lower() in ("true", "1", "yes", "on")
    if isinstance(reference, int) and not isinstance(reference, bool):
        return int(value)
    if isinstance(reference, float):
        return float(value)
    return value

def _apply_env_overrides(config: dict) -> dict:
    """Apply env vars to the config dict in-place."""
    for env_var, key in _ENV_OVERRIDES.items():
        raw = os.environ.get(env_var)   # env 数据就在 os.environ
        if raw is None or raw == "":
            continue
        config[key] = _coerce(raw, config.get(key))
    return config


DEFAULT_CONFIG = _apply_env_overrides({
    "project_dir": os.path.abspath(os.path.join(os.path.dirname(__file__), ".")),
    "results_dir": os.getenv("RESULTS_DIR", os.path.join(_TRAININGAGENTS_HOME, "logs")),
    # LLM settings
    "llm_provider": "openai",
    "deep_think_llm": "gpt-5.4",
    "quick_think_llm": "gpt-5.4-mini",
    "backend_url": None,
    # Provider-specific thinking configuration
    "google_thinking_level": None,
    "openai_reasoning_effort": None,
    "anthropic_effort": None,
    "checkpoint_enabled": False,
    "output_language": "Chinese",
})

