# Calorie Tracker - AI Provider Architecture

## Overview
The application now uses a **pluggable AI provider architecture** for natural language food parsing. This makes it easy to switch between different AI services without modifying the core application logic.

## Architecture

### Core Components

1. **ai_provider.py** - Abstract base class defining the AI provider interface
   - `AIProvider` ABC with `parse_food()` and `get_name()` methods
   - All providers must implement this interface

2. **ai_config.py** - Provider factory and configuration
   - `ACTIVE_PROVIDER` - Set which provider to use ("gemini", "openai", "anthropic")
   - `get_provider()` - Returns the configured provider instance
   - `list_providers()` - Lists all available providers

3. **Provider Implementations**
   - `gemini.py` - Google Gemini (fully implemented)
   - `openai_provider.py` - OpenAI GPT (placeholder - needs API key and implementation)
   - `anthropic_provider.py` - Anthropic Claude (placeholder - needs API key and implementation)

## How to Switch Providers

Edit `ai_config.py` and change:
```python
ACTIVE_PROVIDER = "gemini"  # Change to "openai" or "anthropic"
```

## How to Implement a New Provider

1. Create a new file (e.g., `mistral_provider.py`)
2. Implement the `AIProvider` interface:
```python
from ai_provider import AIProvider

class MistralProvider(AIProvider):
    def get_name(self) -> str:
        return "Mistral AI"
    
    def parse_food(self, text: str) -> dict:
        # Your API call here
        # Return: {"items": [...], "total": {...}}
        pass

mistral_provider = MistralProvider()
```

3. Register it in `ai_config.py`:
```python
from mistral_provider import mistral_provider

PROVIDERS = {
    "gemini": gemini_provider,
    "openai": openai_provider,
    "anthropic": anthropic_provider,
    "mistral": mistral_provider,  # Add new provider
}
```

4. Set as active:
```python
ACTIVE_PROVIDER = "mistral"
```

## Current Implementation

### Gemini Provider (Active)
- Uses Google's Gemini API
- Tries multiple models in order: gemini-2.0-flash, gemini-1.5-flash-latest, gemini-1.5-flash, gemini-pro
- Handles rate limiting and model availability errors gracefully
- API key configured in `gemini.py`

### OpenAI Provider (Placeholder)
- File: `openai_provider.py`
- Needs: API key and implementation
- Endpoint: `https://api.openai.com/v1/chat/completions`
- Model: gpt-4o-mini (configurable)

### Anthropic Provider (Placeholder)
- File: `anthropic_provider.py`
- Needs: API key and implementation
- Endpoint: `https://api.anthropic.com/v1/messages`
- Model: claude-3-haiku-20240307 (configurable)

## Application Flow

1. User enters natural language in the UI (e.g., "1 roti, 1 cup dal, 100g rice")
2. Frontend calls `POST /api/parse-food` with the text
3. `app.py` calls `get_provider().parse_food(text)`
4. The active provider makes the API call and returns structured data
5. Frontend displays parsed items for user to select
6. User clicks "Add Selected to Log"
7. Frontend calls `POST /add-bulk` to save items to database
8. Dashboard updates with new entries

## Benefits of This Architecture

- **No vendor lock-in** - Easy to switch providers
- **Testability** - Can mock providers for testing
- **Extensibility** - Add new providers without changing core code
- **Fallback capability** - Could implement automatic fallback if one provider fails
- **Configuration-driven** - Switch providers with a single line change
