import json
import os
import sqlite3
import urllib.request
import urllib.error

DB_PATH = "calorie_tracker.db"
SARVAM_ENDPOINT = "https://api.sarvam.ai/v1/chat/completions"
DEFAULT_MODEL = os.getenv("SARVAM_MODEL", "sarvam-105b").strip() or "sarvam-105b"


def get_db_api_key(provider: str = "sarvam") -> tuple[str | None, str]:
    """Return the stored API key and a source label."""
    if os.path.exists(DB_PATH):
        try:
            conn = sqlite3.connect(DB_PATH)
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT provider, api_key FROM api_keys WHERE provider = ? ORDER BY created_at DESC, id DESC LIMIT 1",
                (provider,),
            ).fetchone()
            if row:
                return row["api_key"], "database"
        except Exception:
            pass
        finally:
            conn.close()

    env_key = os.getenv("SARVAM_API_KEY")
    return env_key, "environment" if env_key else (None, "none")


def validate_sarvam_key(api_key: str) -> bool:
    """Call Sarvam with a minimal request and return True if the key authenticates."""
    payload = {
        "model": DEFAULT_MODEL,
        "messages": [{"role": "user", "content": "Hello, this is a Sarvam API key test."}],
        "temperature": 0.0,
        "max_tokens": 10,
    }

    req = urllib.request.Request(
        SARVAM_ENDPOINT,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "api-subscription-key": api_key,
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            result = json.loads(response.read().decode("utf-8"))
            print("Received response:")
            print(json.dumps(result, indent=2))
            return True

    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="ignore")
        print(f"HTTP error {exc.code}: {body}")
        return False
    except urllib.error.URLError as exc:
        print(f"Network error: {exc}")
        return False
    except json.JSONDecodeError as exc:
        print(f"Failed to parse Sarvam response: {exc}")
        return False
    except Exception as exc:  # noqa: BLE001
        print(f"Unexpected error: {type(exc).__name__}: {exc}")
        return False


if __name__ == "__main__":
    api_key, source = get_db_api_key("sarvam")
    if not api_key:
        print("No Sarvam API key found in database or environment.")
        print("Add a SARVAM_API_KEY to the DB or set the SARVAM_API_KEY environment variable.")
        raise SystemExit(1)

    print(f"Testing Sarvam API key from {source}...")
    success = validate_sarvam_key(api_key)
    if success:
        print("Sarvam API key is valid and authenticated successfully.")
        raise SystemExit(0)
    print("Sarvam API key validation failed.")
    raise SystemExit(2)
