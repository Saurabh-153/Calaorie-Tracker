"""AI provider factory, configuration, and fallback chain."""

import os
import logging
from dotenv import load_dotenv

load_dotenv()

from ai_provider import AIProvider
from gemini import gemini_provider
from openai_provider import openai_provider
from anthropic_provider import anthropic_provider
from sarvam_provider import sarvam_provider
from grok_provider import grok_provider
from deepseek_provider import deepseek_provider
from openrouter_provider import openrouter_provider
from config import (
    ACTIVE_PROVIDER,
    API_KEY_NAMES,
    DEFAULT_MODELS,
    get_active_provider,
    get_model_for_provider,
    set_active_provider as set_config_active_provider,
    set_model_for_provider as set_config_model,
)

logger = logging.getLogger(__name__)

# Configuration: Set which AI provider to use
ACTIVE_PROVIDER = get_active_provider()

# Provider registry
PROVIDERS = {
    "gemini": gemini_provider,
    "openai": openai_provider,
    "anthropic": anthropic_provider,
    "sarvam": sarvam_provider,
    "grok": grok_provider,
    "deepseek": deepseek_provider,
    "openrouter": openrouter_provider,
}

# API Keys: read from .env / environment variables
API_KEYS = {
    name: os.getenv(key_name)
    for name, key_name in API_KEY_NAMES.items()
}

# ---------------------------------------------------------------------------
# Fallback chain — sarvam is primary; others used in order if sarvam fails.
# Only providers with a configured (non-placeholder) key are tried.
# ---------------------------------------------------------------------------
_FALLBACK_ORDER = ["sarvam", "gemini", "openai", "anthropic", "openrouter", "grok", "deepseek"]


def _is_configured(provider_name: str) -> bool:
    key = API_KEYS.get(provider_name, "")
    return bool(key) and not key.startswith("your_")


def parse_food_with_fallback(text: str) -> tuple[dict, str]:
    """
    Try to parse *text* using sarvam first, then fall through the fallback
    chain until one succeeds.

    Returns:
        (result_dict, provider_name_used)

    If every provider fails, returns an error dict with provider="all_failed".
    """
    tried = []

    for name in _FALLBACK_ORDER:
        if not _is_configured(name):
            continue

        provider = PROVIDERS.get(name)
        if provider is None:
            continue

        try:
            result = provider.parse_food(text)
        except Exception as exc:
            logger.warning("Provider %s raised exception: %s", name, exc)
            tried.append(f"{name}: exception ({exc})")
            continue

        if "error" not in result:
            if tried:
                logger.info("Fallback succeeded with provider: %s (tried: %s)", name, tried)
            return result, provider.get_name()

        tried.append(f"{name}: {result['error'][:120]}")
        logger.warning("Provider %s failed: %s", name, result["error"])

    error_detail = "; ".join(tried) if tried else "No providers configured."
    logger.error("All AI providers failed. Details: %s", error_detail)
    return {
        "error": "All AI providers failed. Please check your API keys or try again later.",
        "details": error_detail,
    }, "all_failed"


def get_provider() -> AIProvider:
    """Get the currently configured AI provider (used for direct single-provider calls)."""
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
    return [name for name in PROVIDERS if _is_configured(name)]


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

def set_model(provider_name: str, model_name: str) -> str:
    """Set the model for a provider from config."""
    return set_config_model(provider_name, model_name)
