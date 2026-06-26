"""Sarvam AI API integration for natural language food parsing."""

import os
import json
import urllib.request
import urllib.error
from ai_provider import AIProvider
from config import get_model_for_provider
from prompt_service import load_active_system_prompt
# ---------------------------------------------------------------------------
# Helper to fetch API key at runtime (avoids circular imports)
# ---------------------------------------------------------------------------


def _get_api_key():
    try:
        from ai_config import API_KEYS

        key = API_KEYS.get("sarvam")
        if key:
            return key
    except Exception:
        pass
    return os.getenv("SARVAM_API_KEY")


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SARVAM_MODEL = get_model_for_provider("sarvam")
SARVAM_ENDPOINT = "https://api.sarvam.ai/v1/chat/completions"

# Timeout in seconds — reasoning models can be slow
REQUEST_TIMEOUT = 60

# Higher token budget prevents the model from truncating long JSON replies.
SARVAM_MAX_TOKENS = int(os.getenv("SARVAM_MAX_TOKENS", "2048"))

# Required top-level keys in every valid nutrition response
REQUIRED_KEYS = {"items", "total_calories", "total_protein", "total_carbs", "total_fat"}

# Required keys inside each item
REQUIRED_ITEM_KEYS = {"name", "quantity", "calories", "protein", "carbs", "fat"}


# ---------------------------------------------------------------------------
# System prompt loader
# ---------------------------------------------------------------------------

def _load_system_prompt() -> str:
    """Load the nutrition system prompt from the active database version."""
    return load_active_system_prompt()


# ---------------------------------------------------------------------------
# JSON extraction helpers
# ---------------------------------------------------------------------------

def _strip_markdown_fences(text: str) -> str:
    """Remove code-fence wrappers and inline backtick wrappers around JSON."""
    text = text.strip()
    if not text:
        return text

    # Remove any surrounding triple-backtick fences repeatedly
    while text.startswith("```"):
        lines = text.splitlines()
        if not lines:
            break
        inner = lines[1:] if len(lines) > 1 else []
        if inner and inner[-1].strip() == "```":
            inner = inner[:-1]
        text = "\n".join(inner).strip()
        if not text:
            break

    # Remove single backtick wrappers like `{"a":1}`
    while len(text) >= 2 and text.startswith("`") and text.endswith("`"):
        text = text[1:-1].strip()

    # Remove stray backticks that may wrap the JSON object
    text = text.replace("`", "").strip()
    return text


def _extract_json_object(text: str) -> str | None:
    """
    Find and return the first complete JSON object in *text* by counting braces.
    Returns None if no complete object is found.
    """
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
                return text[start : i + 1]

    return None  # unbalanced


def _parse_content(content: str) -> dict:
    """
    Try to extract and parse a JSON object from *content*.
    Returns a dict with an 'error' key on failure.
    """
    if content is None:
        return {"error": "Sarvam AI returned no content."}

    content = _strip_markdown_fences(content)
    if not content:
        return {"error": "Sarvam AI returned empty content."}

    json_str = _extract_json_object(content)

    if json_str is None:
        preview = content[:300]
        return {"error": f"No valid JSON object found in response: {preview}"}

    try:
        return json.loads(json_str)
    except json.JSONDecodeError as exc:
        return {"error": f"JSON parse error — {exc}: {json_str[:300]}"}


# ---------------------------------------------------------------------------
# Response validation
# ---------------------------------------------------------------------------

def _validate(parsed: dict) -> dict | None:
    """
    Validate the parsed nutrition dict.
    Returns an error dict if invalid, or None if everything is fine.
    """
    # Top-level keys
    missing_top = REQUIRED_KEYS - parsed.keys()
    if missing_top:
        return {
            "error": (
                f"Response missing top-level fields: {sorted(missing_top)}. "
                f"Got: {sorted(parsed.keys())}"
            )
        }

    items = parsed.get("items")
    if not isinstance(items, list) or len(items) == 0:
        return {"error": "'items' must be a non-empty list."}

    # Per-item keys
    for idx, item in enumerate(items):
        missing_item = REQUIRED_ITEM_KEYS - item.keys()
        if missing_item:
            return {
                "error": (
                    f"Item {idx} missing fields: {sorted(missing_item)}. "
                    f"Got: {sorted(item.keys())}"
                )
            }

        # Type checks
        if not isinstance(item["calories"], (int, float)):
            return {"error": f"Item {idx} 'calories' must be numeric."}
        for field in ("protein", "carbs", "fat"):
            if not isinstance(item[field], (int, float)):
                return {"error": f"Item {idx} '{field}' must be numeric."}

    # Numeric total checks
    for field in ("total_calories", "total_protein", "total_carbs", "total_fat"):
        if not isinstance(parsed[field], (int, float)):
            return {"error": f"'{field}' must be numeric."}

    return None  # all good


# ---------------------------------------------------------------------------
# Provider
# ---------------------------------------------------------------------------

class SarvamProvider(AIProvider):
    """Sarvam AI provider implementation."""

    def get_name(self) -> str:
        return "Sarvam AI"

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def parse_food(self, text: str) -> dict:
        """
        Parse a natural language meal description using Sarvam AI.

        Args:
            text: e.g. "2 rotis, 1 cup dal, 100g rice, 1 glass milk"

        Returns:
            dict with keys:
                items         – list of {name, quantity, calories, protein, carbs, fat}
                total_calories, total_protein, total_carbs, total_fat
                error         – present only on failure
        """
        key = _get_api_key()
        if not key:
            return {"error": "SARVAM API key is not configured."}

        system_prompt = _load_system_prompt()

        payload = {
            "model": SARVAM_MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text.strip()},
            ],
            "temperature": 0.1,
            "max_tokens": SARVAM_MAX_TOKENS,
            # Ask for JSON mode; caught gracefully if unsupported (HTTP 422)
            "response_format": {"type": "json_object"},
        }

        raw_result = self._call_api(payload)

        # _call_api returns an error dict on failure
        if "error" in raw_result:
            # If the model doesn't support response_format, retry without it
            if raw_result.get("_retry_without_response_format"):
                payload.pop("response_format", None)
                raw_result = self._call_api(payload)
                if "error" in raw_result:
                    return raw_result
            else:
                return raw_result

        content = raw_result.get("content", "")
        parsed = _parse_content(content)

        if "error" in parsed:
            return parsed

        validation_error = _validate(parsed)
        if validation_error:
            return validation_error

        # Normalise types: calories → int, macros → float rounded to 1dp
        return self._normalise(parsed)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _call_api(self, payload: dict) -> dict:
        """
        Make the HTTP POST to Sarvam AI.

        Returns:
            {"content": "<model text>"} on success.
            {"error": "...", "_retry_without_response_format": True} when HTTP 422.
            {"error": "..."} on other failures.
        """
        try:
            req = urllib.request.Request(
                SARVAM_ENDPOINT,
                data=json.dumps(payload).encode("utf-8"),
                headers={
                    "Content-Type": "application/json",
                    "api-subscription-key": _get_api_key(),
                },
                method="POST",
            )

            with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as response:
                result = json.loads(response.read().decode("utf-8"))

            return self._extract_content(result)

        except urllib.error.HTTPError as exc:
            return self._handle_http_error(exc)
        except urllib.error.URLError as exc:
            return {"error": f"Network error connecting to Sarvam AI: {exc}"}
        except json.JSONDecodeError as exc:
            return {"error": f"Could not decode Sarvam AI API response as JSON: {exc}"}
        except TimeoutError:
            return {"error": f"Request timed out after {REQUEST_TIMEOUT}s."}
        except Exception as exc:  # noqa: BLE001
            return {"error": f"Unexpected error: {type(exc).__name__}: {exc}"}

    @staticmethod
    def _extract_content(result: dict) -> dict:
        """
        Pull the model's text out of an OpenAI-compatible response dict.

        For reasoning models:
          - `content`          → the final answer  (preferred)
          - `reasoning_content`→ chain-of-thought scratchpad (fallback only)
        """
        message = result.get("choices", [{}])[0].get("message", {})

        content = (message.get("content") or "").strip()

        if not content:
            # Last resort: try to fish JSON out of the reasoning trace
            reasoning = (message.get("reasoning_content") or "").strip()
            if reasoning:
                content = reasoning
            else:
                return {
                    "error": (
                        "Sarvam AI returned no usable content. "
                        f"Full response: {json.dumps(result)[:500]}"
                    )
                }

        return {"content": content}

    @staticmethod
    def _handle_http_error(exc: urllib.error.HTTPError) -> dict:
        """Map HTTP error codes to human-readable messages."""
        try:
            body = exc.read().decode("utf-8") if exc.fp else ""
        except Exception:  # noqa: BLE001
            body = str(exc)

        preview = body[:300]

        if exc.code == 401:
            return {
                "error": (
                    "Sarvam AI authentication failed (401). "
                    "Check your SARVAM_API_KEY."
                )
            }
        if exc.code == 422:
            # response_format may not be supported — caller will retry without it
            return {
                "error": f"Sarvam AI rejected request (422): {preview}",
                "_retry_without_response_format": True,
            }
        if exc.code == 429:
            return {
                "error": f"Sarvam AI rate limit exceeded (429). {preview}"
            }
        if exc.code == 500:
            return {"error": f"Sarvam AI internal server error (500). {preview}"}
        if exc.code == 503:
            return {"error": f"Sarvam AI service unavailable (503). {preview}"}

        return {"error": f"Sarvam AI HTTP error {exc.code}: {preview}"}

    @staticmethod
    def _normalise(parsed: dict) -> dict:
        """
        Coerce types to match the schema exactly:
          calories → int
          protein / carbs / fat → float, 1 decimal place
        """
        for item in parsed["items"]:
            item["calories"] = int(round(item["calories"]))
            item["protein"] = round(float(item["protein"]), 1)
            item["carbs"] = round(float(item["carbs"]), 1)
            item["fat"] = round(float(item["fat"]), 1)

        parsed["total_calories"] = int(round(parsed["total_calories"]))
        parsed["total_protein"] = round(float(parsed["total_protein"]), 1)
        parsed["total_carbs"] = round(float(parsed["total_carbs"]), 1)
        parsed["total_fat"] = round(float(parsed["total_fat"]), 1)

        return parsed


# ---------------------------------------------------------------------------
# Singleton instance
# ---------------------------------------------------------------------------

sarvam_provider = SarvamProvider()