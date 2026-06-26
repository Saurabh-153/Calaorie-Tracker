"""Helpers for loading the active system prompt from the database."""

from datetime import datetime
from pathlib import Path

from database import create_prompt_version, get_active_prompt_version
from models import PromptVersion

DEFAULT_PROMPT_PATH = Path(__file__).with_name("system_prompt.txt")

DEFAULT_PROMPT = (
    "You are a highly accurate nutrition expert specialising in Indian and "
    "international foods. Analyse the meal description and return ONLY a valid "
    "JSON object — no markdown, no code fences, no extra text. "
    "Schema: "
    '{"items":[{"name":"string","quantity":"string","calories":0,'
    '"protein":0.0,"carbs":0.0,"fat":0.0}],'
    '"total_calories":0,"total_protein":0.0,"total_carbs":0.0,"total_fat":0.0}'
)


def load_active_system_prompt() -> str:
    """Return the active prompt from the database, falling back to the file."""
    try:
        version = get_active_prompt_version()
        if version and version.content and version.content.strip():
            return version.content.strip()
    except Exception:
        pass

    try:
        with DEFAULT_PROMPT_PATH.open("r", encoding="utf-8", errors="replace") as handle:
            prompt = handle.read().strip()
            if prompt:
                try:
                    create_prompt_version(
                        PromptVersion(
                            id=None,
                            name="Initial Prompt",
                            content=prompt,
                            created_at=datetime.now().isoformat(),
                            is_active=True,
                        )
                    )
                except Exception:
                    pass
                return prompt
    except FileNotFoundError:
        pass

    return DEFAULT_PROMPT
