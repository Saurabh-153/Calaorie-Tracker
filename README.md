# Calorie Tracker

Lightweight Flask-based calorie tracker with multi-model AI food parsing, audit logging, and prompt version management.

## Quickstart

### 1. Create a virtual environment and install dependencies

```bash
python -m venv .venv
source .venv/bin/activate   # PowerShell: .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 2. Configure API keys

Copy the `.env` file (already provided) and fill in the keys for the providers you want to use:

```
ACTIVE_PROVIDER=sarvam        # gemini | openai | anthropic | sarvam | grok | deepseek

GEMINI_API_KEY=your_gemini_api_key_here
OPENAI_API_KEY=your_openai_api_key_here
ANTHROPIC_API_KEY=your_anthropic_api_key_here
SARVAM_API_KEY=your_sarvam_api_key_here
GROK_API_KEY=your_grok_api_key_here
DEEPSEEK_API_KEY=your_deepseek_api_key_here
```

You can also override the model used per provider:

```
GEMINI_MODEL=gemini-2.0-flash
OPENAI_MODEL=gpt-4o-mini
ANTHROPIC_MODEL=claude-3-haiku-20240307
SARVAM_MODEL=sarvam-105b
GROK_MODEL=grok-beta
DEEPSEEK_MODEL=deepseek-chat
```

> `.env` is in `.gitignore` — your keys are never committed.

### 3. Run the app

```bash
python app.py
# opens on http://localhost:3000
```

The SQLite database is created automatically on first run.

---

## Deployment (Render)

- Create a new **Web Service** and connect your repo.
- **Build command:** `pip install -r requirements.txt`
- **Start command:** `gunicorn app:app --bind 0.0.0.0:$PORT` (uses `Procfile`)
- Add your API keys as **Environment Variables** in the Render dashboard.

---

## Admin pages

| URL | Purpose |
|-----|---------|
| `/admin/prompts` | Manage and switch system prompt versions |
| `/admin/audit-logs` | View AI response audit log |

---

## Project structure

```
app.py                  — Flask routes and entry point
config.py               — Provider/model configuration, reads from .env
ai_config.py            — Provider factory, API key loading
database.py             — SQLite helpers and schema
models.py               — Dataclasses for domain objects
prompt_service.py       — System prompt loading
.env                    — API keys and active provider (not committed)
templates/              — Jinja2 HTML templates
static/                 — CSS
*_provider.py           — Per-provider AI implementations (openai, gemini, sarvam, …)
```

---

## Supported AI providers

| Provider | Key variable | Default model |
|----------|-------------|---------------|
| Sarvam | `SARVAM_API_KEY` | `sarvam-105b` |
| Gemini | `GEMINI_API_KEY` | `gemini-2.0-flash` |
| OpenAI | `OPENAI_API_KEY` | `gpt-4o-mini` |
| Anthropic | `ANTHROPIC_API_KEY` | `claude-3-haiku-20240307` |
| Grok | `GROK_API_KEY` | `grok-beta` |
| DeepSeek | `DEEPSEEK_API_KEY` | `deepseek-chat` |
