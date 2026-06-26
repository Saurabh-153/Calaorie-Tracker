# Calorie Tracker

Lightweight Flask-based calorie tracker with multi-model AI food parsing, audit logging, and prompt version management.

## Quickstart

### 1. Create a virtual environment and install dependencies

```bash
python -m venv .venv
source .venv/bin/activate   # PowerShell: .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 2. Configure API keys and authentication

Copy the `.env` file (already provided) and fill in the values:

```
# \u2500\u2500 AI provider
ACTIVE_PROVIDER=sarvam

# \u2500\u2500 Flask session (change in production)
SECRET_KEY=change-me-to-a-long-random-string

# \u2500\u2500 Who can log in (comma-separated)
ALLOWED_EMAILS=you@gmail.com,friend@gmail.com

# \u2500\u2500 Gmail SMTP (for sending OTP)
SMTP_USER=your-gmail@gmail.com
SMTP_PASSWORD=your-16-char-app-password   # Google App Password

# \u2500\u2500 API keys
GEMINI_API_KEY=your_gemini_api_key_here
...
```

#### How to get a Gmail App Password

1. Enable **2-Step Verification** on your Google account
2. Go to [https://myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)
3. Select app → **Mail**, device → **Other**, generate
4. Copy the 16-character password (no spaces) into `SMTP_PASSWORD`

#### How authentication works

- Users visit the app → enter their email
- If the email is in `ALLOWED_EMAILS`, a **6-digit OTP** is sent to their Gmail
- They enter the code → session is created, valid for **7 days**
- No passwords stored anywhere — the OTP is the credential
- To add a new user: add their email to `ALLOWED_EMAILS` and restart the app
- Max 5 wrong OTP attempts before the code is invalidated
- Each OTP expires after 5 minutes

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
