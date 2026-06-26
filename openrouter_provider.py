"""OpenRouter API integration for natural language food parsing.

OpenRouter provides a unified endpoint for many models (Claude, GPT-4, Llama, etc.)
Set OPENROUTER_API_KEY and optionally OPENROUTER_MODEL in your .env file.
"""

import os
import json
import urllib.request
import urllib.error

from ai_provider import AIProvider
from config import get_model_for_provider
from prompt_service import load_active_system_prompt

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

OPENROUTER_ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"
REQUEST_TIMEOUT = 60
MAX_TOKENS = int(os.getenv("OPENROUTER_MAX_TOKENS", "2048"))

REQUIRED_KEYS = {"items", "total_calories", "total_protein", "total_carbs", "total_fat"}
REQUIRED_ITEM_KEYS = {"name", "quantity", "calories", "protein", "carbs", "fat"}


def _get_api_key() -> str | None:
    try:
        from ai_config import API_KEYS
        key = API_KEYS.get("openrouter")
        if key:
            return key
    except Exception:
        pass
    return os.getenv("OPENROUTER_API_KEY")


def _load_system_prompt() -> str:
    return load_active_system_prompt()


# ---------------------------------------------------------------------------
# JSON parsing helpers (same logic as sarvam_provider)
# ---------------------------------------------------------------------------

def _strip_markdown_fences(text: str) -> str:
    text = text.strip()
    while text.startswith("```"):
        lines = text.splitlines()
        inner = lines[1:] if len(lines) > 1 else []
        if inner and inner[-1].strip() == "```":
            inner = inner[:-1]
        text = "\n".join(inner).strip()
        if not text:
            break
    while len(text) >= 2 and text.startswith("`") and text.endswith("`"):
        text = text[1:-1].strip()
    text = text.replace("`", "").strip()
    return text


def _extract_json_object(text: str) -> str | None:
    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    in_string = False
    escape_next = False
    for i in range(start, len(text)):
        ch = text[i]
        if escape_next:
            escape_next = False
            continue
        if ch == "\\" and in_string:
            escape_next = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start: i + 1]
    return None


def _parse_content(content: str) -> dict:
    if not content:
        return {"error": "OpenRouter returned empty content."}
    content = _strip_markdown_fences(content)
    json_str = _extract_json_object(content)
    if json_str is None:
        return {"error": f"No valid JSON object found in response: {content[:300]}"}
    try:
        return json.loads(json_str)
    except json.JSONDecodeError as exc:
        return {"error": f"JSON parse error — {exc}: {json_str[:300]}"}


def _validate(parsed: dict) -> dict | None:
    missing_top = REQUIRED_KEYS - parsed.keys()
    if missing_top:
        return {"error": f"Response missing top-level fields: {sorted(missing_top)}"}
    items = parsed.get("items")
    if not isinstance(items, list) or len(items) == 0:
        return {"error": "'items' must be a non-empty list."}
    for idx, item in enumerate(items):
        missing_item = REQUIRED_ITEM_KEYS - item.keys()
        if missing_item:
            return {"error": f"Item {idx} missing fields: {sorted(missing_item)}"}
        if not isinstance(item["calories"], (int, float)):
            return {"error": f"Item {idx} 'calories' must be numeric."}
        for field in ("protein", "carbs", "fat"):
            if not isinstance(item[field], (int, float)):
                return {"error": f"Item {idx} '{field}' must be numeric."}
    for field in REQUIRED_KEYS - {"items"}:
        if not isinstance(parsed[field], (int, float)):
            return {"error": f"'{field}' must be numeric."}
    return None


# ---------------------------------------------------------------------------
# Provider
# ---------------------------------------------------------------------------

class OpenRouterProvider(AIProvider):
    """OpenRouter unified API provider."""

    def get_name(self) -> str:
        return "OpenRouter"

    def parse_food(self, text: str) -> dict:
        key = _get_api_key()
        if not key or key.startswith("your_"):
            return {"error": "OPENROUTER_API_KEY is not configured."}

        model = os.getenv("OPENROUTER_MODEL", "openai/gpt-4o-mini")
        system_prompt = _load_system_prompt()

        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text.strip()},
            ],
            "temperature": 0.1,
            "max_tokens": MAX_TOKENS,
        }

        try:
            req = urllib.request.Request(
                OPENROUTER_ENDPOINT,
                data=json.dumps(payload).encode("utf-8"),
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {key}",
                    "HTTP-Referer": os.getenv("OPENROUTER_REFERER", "http://localhost:3000"),
                    "X-Title": "Calorie Tracker",
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
                body = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            try:
                detail = exc.read().decode("utf-8")
            except Exception:
                detail = str(exc)
            return {"error": f"OpenRouter HTTP {exc.code}: {detail[:300]}"}
        except urllib.error.URLError as exc:
            return {"error": f"OpenRouter connection error: {exc.reason}"}
        except Exception as exc:
            return {"error": f"OpenRouter unexpected error: {exc}"}

        try:
            content = body["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            return {"error": f"Unexpected OpenRouter response structure: {exc}. Body: {str(body)[:300]}"}

        parsed = _parse_content(content)
        if "error" in parsed:
            return parsed

        err = _validate(parsed)
        if err:
            return err

        return parsed


openrouter_provider = OpenRouterProvider()
