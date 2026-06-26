"""Gemini API integration for natural language food parsing."""

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

# Gemini API configuration
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = get_model_for_provider("gemini")
# Try multiple model names in order of preference
GEMINI_MODELS = [
    GEMINI_MODEL,
    "gemini-1.5-flash-latest",
    "gemini-1.5-flash",
    "gemini-pro",
]
GEMINI_ENDPOINT_BASE = "https://generativelanguage.googleapis.com/v1beta/models"


class GeminiProvider(AIProvider):
    """Gemini AI provider implementation."""

    def get_name(self) -> str:
        return "Google Gemini"

    def parse_food(self, text: str) -> dict:
        """
        Parse natural language food description using Gemini API.

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
            "contents": [
                {"parts": [{"text": system_prompt}]},
                {"parts": [{"text": user_message}]}
            ],
            "generationConfig": {"temperature": 0.1, "maxOutputTokens": 1024},
        }

        try:
            # Try each model in order of preference
            last_error = None
            for model in GEMINI_MODELS:
                url = f"{GEMINI_ENDPOINT_BASE}/{model}:generateContent?key={GEMINI_API_KEY}"
                req = urllib.request.Request(
                    url,
                    data=json.dumps(payload).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )

                try:
                    with urllib.request.urlopen(req, timeout=15) as response:
                        result = json.loads(response.read().decode("utf-8"))
                    break  # Success, exit the model loop
                except urllib.error.HTTPError as e:
                    last_error = e
                    error_body = e.read().decode("utf-8") if e.fp else str(e)
                    # If it's a 404 (model not found), try next model
                    if e.code == 404:
                        continue
                    # If it's a 429 (rate limit), return error immediately
                    elif e.code == 429:
                        return {
                            "error": f"Gemini API rate limit exceeded. Please try again in a moment. ({error_body[:200]})"
                        }
                    else:
                        return {"error": f"Gemini API error: {e.code} - {error_body}"}
            else:
                # All models failed
                if last_error:
                    return {
                        "error": f"All Gemini models failed. Last error: {last_error}"
                    }
                return {"error": "No Gemini models available"}

            # Extract text from response
            if "candidates" not in result or len(result["candidates"]) == 0:
                return {"error": "No response from Gemini API"}

            content = result["candidates"][0]["content"]["parts"][0]["text"]

            # Parse JSON from response (handle potential markdown code blocks)
            content = content.strip()
            if content.startswith("```"):
                # Remove markdown code blocks
                lines = content.split("\n")
                content = "\n".join(lines[1:-1])

            parsed = json.loads(content)

            # Validate structure
            if "items" not in parsed or "total" not in parsed:
                return {"error": "Invalid response format from Gemini"}

            return parsed

        except urllib.error.URLError as e:
            return {"error": f"Network error: {str(e)}"}
        except json.JSONDecodeError as e:
            return {"error": f"Failed to parse Gemini response: {str(e)}"}
        except Exception as e:
            return {"error": f"Unexpected error: {str(e)}"}


# Singleton instance for easy import
gemini_provider = GeminiProvider()
