# Calorie Tracker

Lightweight Flask-based calorie tracker with multimodel AI parsing and admin tools.

Quickstart

1. Create a Python 3.11/3.12 virtual environment and install requirements:

```bash
python -m venv .venv
source .venv/bin/activate   # PowerShell: .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

2. Initialize the SQLite DB (happens automatically on app start):

```bash
python app.py
# opens on http://0.0.0.0:3000
```

3. Open the admin page to configure API keys:

- Admin API keys: `http://localhost:3000/admin/apis`
- Prompt versions: `http://localhost:3000/admin/prompts`

Notes

- API keys are stored in the SQLite DB (`calorie_tracker.db`) and take precedence over environment variables.
- The app runs on port `3000` by default.

Project structure (current)

- `app.py` — Flask routes and entrypoint
- `database.py` — SQLite helpers and schema
- `models.py` — dataclasses for domain objects
- `prompt_service.py` — system prompt loading
- `templates/` — Jinja2 templates
- `static/` — CSS
- Provider implementations: `*provider.py` (openai, sarvam, gemini, etc.)

Recommended structure improvements

- Move provider modules into a `providers/` package: `providers/sarvam.py`, `providers/openai.py`, etc.
- Convert `app.py` into a package `calorie_tracker/__init__.py` and `calorie_tracker/app.py` to enable imports and easier testing.
- Add `calorie_tracker/config.py` for centralized configuration.
- Add a small `scripts/` folder for maintenance tasks (DB migration, key export/import).

Git compatibility

- This repo now includes a `.gitignore` (see below) to exclude virtualenvs, DB, and pycache.

If you want, I can:

- Apply the recommended refactor (move files into packages) and update imports.
- Add basic auth for admin pages.
- Add key encryption for stored API keys.

Which of the above should I do next?