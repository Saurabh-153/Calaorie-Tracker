"""Central configuration for AI providers and default models."""

import os
from dotenv import load_dotenv

load_dotenv()

# Active provider used by the app
ACTIVE_PROVIDER = os.getenv("ACTIVE_PROVIDER", "sarvam").strip().lower() or "sarvam"

# Provider-specific default models
DEFAULT_MODELS = {
    "gemini": os.getenv("GEMINI_MODEL", "gemini-2.0-flash").strip() or "gemini-2.0-flash",
    "openai": os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip() or "gpt-4o-mini",
    "anthropic": os.getenv("ANTHROPIC_MODEL", "claude-3-haiku-20240307").strip() or "claude-3-haiku-20240307",
    "sarvam": os.getenv("SARVAM_MODEL", "sarvam-105b").strip() or "sarvam-105b",
    "grok": os.getenv("GROK_MODEL", "grok-beta").strip() or "grok-beta",
    "deepseek": os.getenv("DEEPSEEK_MODEL", "deepseek-chat").strip() or "deepseek-chat",
    "openrouter": os.getenv("OPENROUTER_MODEL", "openai/gpt-4o-mini").strip() or "openai/gpt-4o-mini",
}

# API key names used by the app
API_KEY_NAMES = {
    "gemini": "GEMINI_API_KEY",
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "sarvam": "SARVAM_API_KEY",
    "grok": "GROK_API_KEY",
    "deepseek": "DEEPSEEK_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
}


def get_active_provider() -> str:
    """Return the configured active provider name."""
    return ACTIVE_PROVIDER


def set_active_provider(provider_name: str) -> str:
    """Set the active provider and return it."""
    global ACTIVE_PROVIDER
    provider_name = provider_name.strip().lower()
    if provider_name not in DEFAULT_MODELS:
        raise ValueError(f"Unknown provider: {provider_name}")
    ACTIVE_PROVIDER = provider_name
    return ACTIVE_PROVIDER


def get_model_for_provider(provider_name: str | None = None) -> str:
    """Return the configured model for the given provider."""
    provider = (provider_name or ACTIVE_PROVIDER).strip().lower()
    return DEFAULT_MODELS.get(provider, DEFAULT_MODELS["gemini"])


def set_model_for_provider(provider_name: str, model_name: str) -> str:
    """Set the model name for a specific provider."""
    provider_name = provider_name.strip().lower()
    if provider_name not in DEFAULT_MODELS:
        raise ValueError(f"Unknown provider: {provider_name}")
    DEFAULT_MODELS[provider_name] = model_name.strip() or DEFAULT_MODELS[provider_name]
    return DEFAULT_MODELS[provider_name]
