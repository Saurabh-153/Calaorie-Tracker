"""Anthropic Claude API integration for natural language food parsing."""

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

# Anthropic API configuration
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
ANTHROPIC_MODEL = get_model_for_provider("anthropic")
ANTHROPIC_ENDPOINT = "https://api.anthropic.com/v1/messages"


class AnthropicProvider(AIProvider):
    """Anthropic Claude provider implementation."""

    def get_name(self) -> str:
        return "Anthropic Claude"

    def parse_food(self, text: str) -> dict:
        """
        Parse natural language food description using Anthropic Claude API.

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
            "model": ANTHROPIC_MODEL,
            "messages": [{"role": "user", "content": user_message}],
            "system": system_prompt,
            "max_tokens": 1024,
            "temperature": 0.1,
        }

        try:
            req = urllib.request.Request(
                ANTHROPIC_ENDPOINT,
                data=json.dumps(payload).encode("utf-8"),
                headers={
                    "Content-Type": "application/json",
                    "x-api-key": ANTHROPIC_API_KEY,
                    "anthropic-version": "2023-06-01",
                },
                method="POST",
            )

            with urllib.request.urlopen(req, timeout=15) as response:
                result = json.loads(response.read().decode("utf-8"))

            # Extract content from response
            content = result["content"][0]["text"]

            # Parse JSON from response (handle potential markdown code blocks)
            content = content.strip()
            if content.startswith("```"):
                lines = content.split("\n")
                content = "\n".join(lines[1:-1])

            parsed = json.loads(content)

            # Validate structure
            if "items" not in parsed or "total" not in parsed:
                return {"error": "Invalid response format from Anthropic"}

            return parsed

        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8") if e.fp else str(e)
            if e.code == 429:
                return {
                    "error": f"Anthropic API rate limit exceeded. ({error_body[:200]})"
                }
            return {"error": f"Anthropic API error: {e.code} - {error_body}"}
        except urllib.error.URLError as e:
            return {"error": f"Network error: {str(e)}"}
        except json.JSONDecodeError as e:
            return {"error": f"Failed to parse Anthropic response: {str(e)}"}
        except Exception as e:
            return {"error": f"Unexpected error: {str(e)}"}


# Singleton instance
anthropic_provider = AnthropicProvider()
