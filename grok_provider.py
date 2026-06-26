"""Grok (xAI) API integration for natural language food parsing."""

import os
import json
import urllib.request
import urllib.error
from ai_provider import AIProvider
from config import get_model_for_provider
from prompt_service import load_active_system_prompt


def _load_system_prompt() -> str:
    """Load the nutrition system prompt from the active database version."""
    return load_active_system_prompt()

# Grok API configuration
GROK_API_KEY = os.getenv("GROK_API_KEY")
GROK_MODEL = get_model_for_provider("grok")
GROK_ENDPOINT = "https://api.x.ai/v1/chat/completions"


class GrokProvider(AIProvider):
    """Grok provider implementation."""

    def get_name(self) -> str:
        return "Grok (xAI)"

    def parse_food(self, text: str) -> dict:
        """
        Parse natural language food description using Grok API.

        Args:
            text: Natural language input like "1 roti, 1 cup dal, 100 gm rice"

        Returns:
            dict with keys:
                - items: list of {name, portion, calories, protein, carbs, fat}
                - total: {calories, protein, carbs, fat}
                - error: error message if failed
        """
        system_prompt = _load_system_prompt()
        user_message = f"Analyze this meal: {text}"

        payload = {
            "model": GROK_MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            "temperature": 0.1,
            "max_tokens": 1024,
        }

        try:
            req = urllib.request.Request(
                GROK_ENDPOINT,
                data=json.dumps(payload).encode("utf-8"),
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {GROK_API_KEY}",
                },
                method="POST",
            )

            with urllib.request.urlopen(req, timeout=15) as response:
                result = json.loads(response.read().decode("utf-8"))

            # Extract content from response
            content = result["choices"][0]["message"]["content"]

            # Parse JSON from response (handle potential markdown code blocks)
            content = content.strip()
            if content.startswith("```"):
                lines = content.split("\n")
                content = "\n".join(lines[1:-1])

            parsed = json.loads(content)

            # Validate structure
            if "items" not in parsed or "total" not in parsed:
                return {"error": "Invalid response format from Grok"}

            return parsed

        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8") if e.fp else str(e)
            if e.code == 429:
                return {"error": f"Grok API rate limit exceeded. ({error_body[:200]})"}
            return {"error": f"Grok API error: {e.code} - {error_body}"}
        except urllib.error.URLError as e:
            return {"error": f"Network error: {str(e)}"}
        except json.JSONDecodeError as e:
            return {"error": f"Failed to parse Grok response: {str(e)}"}
        except Exception as e:
            return {"error": f"Unexpected error: {str(e)}"}


# Singleton instance
grok_provider = GrokProvider()
