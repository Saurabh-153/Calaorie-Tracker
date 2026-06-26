"""AI provider factory and configuration."""

import os
import database as db

from ai_provider import AIProvider
from gemini import gemini_provider
from openai_provider import openai_provider
from anthropic_provider import anthropic_provider
from sarvam_provider import sarvam_provider
from grok_provider import grok_provider
from deepseek_provider import deepseek_provider
from config import (
    ACTIVE_PROVIDER,
    API_KEY_NAMES,
    DEFAULT_MODELS,
    get_active_provider,
    get_model_for_provider,
    set_active_provider as set_config_active_provider,
    set_model_for_provider as set_config_model,
)

# Configuration: Set which AI provider to use
# Options: "gemini", "openai", "anthropic", "sarvam", "grok", "deepseek"
ACTIVE_PROVIDER = get_active_provider()

# Provider registry
PROVIDERS = {
    "gemini": gemini_provider,
    "openai": openai_provider,
    "anthropic": anthropic_provider,
    "sarvam": sarvam_provider,
    "grok": grok_provider,
    "deepseek": deepseek_provider,
}

# API Keys: prefer DB-stored keys, fallback to environment variables
API_KEYS = {
    name: os.getenv(key_name)
    for name, key_name in API_KEY_NAMES.items()
}

# Override with DB-stored keys if present (DB is the source of truth)
try:
    db_keys = {r["provider"]: r["api_key"] for r in db.get_api_keys()}
    for provider_name, key in db_keys.items():
        # if provider is in our known names, map it
        if provider_name in API_KEYS:
            API_KEYS[provider_name] = key
except Exception:
    # If DB isn't available yet during import, silently continue using env
    pass


def get_provider() -> AIProvider:
    """Get the currently configured AI provider."""
    provider = PROVIDERS.get(ACTIVE_PROVIDER)
    if not provider:
        raise ValueError(
            f"Unknown provider: {ACTIVE_PROVIDER}. Available: {list(PROVIDERS.keys())}"
        )
    return provider


def list_providers() -> list:
    """List all available providers."""
    return list(PROVIDERS.keys())


def get_configured_providers() -> list:
    """Return list of providers that have API keys configured."""
    configured = []
    for provider_name, api_key in API_KEYS.items():
        if api_key and not api_key.startswith("your_"):
            configured.append(provider_name)
    return configured


def set_active_provider(provider_name: str):
    """Set the active provider (runtime only, doesn't persist to .env)."""
    global ACTIVE_PROVIDER
    ACTIVE_PROVIDER = set_config_active_provider(provider_name)


def get_model(provider_name: str | None = None) -> str:
    """Get the current model for a provider from config."""
    return get_model_for_provider(provider_name)


def set_model(provider_name: str, model_name: str) -> str:
    """Set the model for a provider from config."""
    return set_config_model(provider_name, model_name)
