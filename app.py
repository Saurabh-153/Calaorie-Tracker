"""Flask application — routes, DB init, and entry point."""

import os
import sys
import json
from datetime import date, datetime, timedelta

from flask import Flask, render_template, request, redirect, url_for, jsonify, session, flash
from flask_login import (
    LoginManager, UserMixin, login_user, logout_user,
    login_required, current_user,
)

# Ensure the project root is on sys.path so local imports work when run directly
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import database as db
from models import FoodEntry, DailyGoal, AiResponseAuditLog, PromptVersion
from ai_config import get_provider, list_providers, ACTIVE_PROVIDER, set_active_provider, parse_food_with_fallback
from auth import send_otp, verify_otp, SESSION_DAYS
from datetime import datetime

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY") or os.urandom(32)

# ---------------------------------------------------------------------------
# Flask-Login
# ---------------------------------------------------------------------------

login_manager = LoginManager(app)
login_manager.login_view = "login"
login_manager.login_message = "Please log in to continue."


class User(UserMixin):
    def __init__(self, user_row: dict):
        self.id    = str(user_row["id"])
        self.email = user_row["email"]
        self.is_admin = bool(user_row.get("is_admin", 0))


@login_manager.user_loader
def load_user(user_id: str):
    row = db.get_user_by_id(int(user_id))
    return User(row) if row else None


@login_manager.unauthorized_handler
def unauthorized():
    """Return JSON 401 for API/fetch requests, redirect otherwise."""
    if request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest" \
            or request.path.startswith("/api/") or request.path.startswith("/add"):
        return jsonify({"error": "Session expired. Please log in again."}), 401
    return redirect(url_for("login"))


@app.template_filter("prev_day")
def prev_day_filter(d: str) -> str:
    """Return the ISO date string for the day before d."""
    return (date.fromisoformat(d) - timedelta(days=1)).isoformat()


@app.template_filter("next_day")
def next_day_filter(d: str) -> str:
    """Return the ISO date string for the day after d."""
    return (date.fromisoformat(d) + timedelta(days=1)).isoformat()

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def today_str() -> str:
    """Return today's date as an ISO string YYYY-MM-DD."""
    return date.today().isoformat()


def now_iso() -> str:
    """Return current datetime as an ISO string for the timestamp column."""
    return datetime.now().isoformat()


def daily_totals(entries):
    """Sum calories and macros across a list of FoodEntry objects."""
    return {
        "calories": sum(e.calories for e in entries),
        "protein": round(sum(e.protein for e in entries), 1),
        "carbs": round(sum(e.carbs for e in entries), 1),
        "fat": round(sum(e.fat for e in entries), 1),
    }


def save_ai_response(result, text, provider_name: str):
    """Persist the AI response to the database for audit logging."""
    status = "error" if isinstance(result, dict) and "error" in result else "ok"
    log = AiResponseAuditLog(
        id=None,
        timestamp=datetime.now().isoformat(),
        input_text=text,
        response_payload=json.dumps(result, ensure_ascii=False, default=str),
        provider=provider_name,
        status=status,
    )
    return db.insert_ai_response_log(log)


def normalize_ai_result(result):
    """Return a UI-friendly AI response regardless of provider schema."""
    if not isinstance(result, dict):
        return {"error": "Invalid AI response"}

    if "error" in result:
        return result

    items = result.get("items", []) or []
    normalized_items = []
    for item in items:
        if not isinstance(item, dict):
            continue
        normalized_item = dict(item)
        if "portion" not in normalized_item and "quantity" in normalized_item:
            normalized_item["portion"] = normalized_item["quantity"]
        normalized_items.append(normalized_item)

    total = result.get("total")
    if not isinstance(total, dict):
        total = {
            "calories": result.get("total_calories", 0),
            "protein": result.get("total_protein", 0),
            "carbs": result.get("total_carbs", 0),
            "fat": result.get("total_fat", 0),
        }

    return {
        "items": normalized_items,
        "total": total,
    }


# ---------------------------------------------------------------------------
# Auth routes
# ---------------------------------------------------------------------------

@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("index"))
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        if not email:
            flash("Please enter your email.", "error")
            return render_template("login.html")
        ok, msg = send_otp(email)
        if not ok:
            flash(msg, "error")
            return render_template("login.html")
        session["otp_email"] = email
        return redirect(url_for("verify"))
    return render_template("login.html")


@app.route("/verify", methods=["GET", "POST"])
def verify():
    email = session.get("otp_email")
    if not email:
        return redirect(url_for("login"))
    if request.method == "POST":
        code = request.form.get("code", "").strip()
        ok, msg = verify_otp(email, code)
        if not ok:
            flash(msg, "error")
            return render_template("verify.html", email=email)
        # Log the user in
        row = db.get_or_create_user(email)
        user = User(row)
        login_user(user, remember=True, duration=timedelta(days=SESSION_DAYS))
        session.pop("otp_email", None)
        return redirect(url_for("index"))
    return render_template("verify.html", email=email)


@app.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.route("/")
@login_required
def index():
    """Main dashboard — food log, progress bar, and goal form for a given date."""
    selected_date = request.args.get("date", "").strip() or today_str()
    goal_saved = request.args.get("goal_saved", "") == "1"
    entries = db.get_entries_for_date(selected_date, int(current_user.id))
    totals = daily_totals(entries)
    goal = db.get_goal_for_date_or_default(selected_date, int(current_user.id))
    return render_template(
        "index.html",
        today=today_str(),
        selected_date=selected_date,
        entries=entries,
        totals=totals,
        goal=goal,
        goal_saved=goal_saved,
    )


@app.route("/delete/<int:entry_id>", methods=["POST"])
@login_required
def delete_entry(entry_id: int):
    """Delete a food entry by id, then redirect back to dashboard."""
    date = request.form.get("date", "").strip() or today_str()
    db.delete_entry(entry_id, int(current_user.id))
    return redirect(url_for("index", date=date))


@app.route("/goal", methods=["POST"])
@login_required
def save_goal():
    """Save (upsert) the calorie/protein/carbs goal for the submitted date."""
    goal_date = request.form.get("goal_date", "").strip() or today_str()
    goal = DailyGoal(
        user_id=int(current_user.id),
        date=goal_date,
        calorie_goal=int(request.form.get("calorie_goal", 2000)),
        protein_goal=float(request.form.get("protein_goal", 0) or 0),
        carbs_goal=float(request.form.get("carbs_goal", 0) or 0),
    )
    db.upsert_goal(goal, int(current_user.id))
    return redirect(url_for("index", date=goal_date, goal_saved="1"))


@app.route("/api/goal/<date>")
@login_required
def api_get_goal(date: str):
    """Return the goal for a specific date as JSON."""
    goal = db.get_goal_for_date_or_default(date, int(current_user.id))
    return jsonify({"date": date, "calorie_goal": goal.calorie_goal,
                    "protein_goal": goal.protein_goal, "carbs_goal": goal.carbs_goal})


@app.route("/api/day/<date>")
@login_required
def api_get_day(date: str):
    """Return entries, totals, and goal for a date — used for in-place dashboard refresh."""
    entries = db.get_entries_for_date(date, int(current_user.id))
    totals = daily_totals(entries)
    goal = db.get_goal_for_date_or_default(date, int(current_user.id))
    return jsonify({
        "date": date,
        "goal_calorie": goal.calorie_goal,
        "goal_protein": goal.protein_goal,
        "goal_carbs": goal.carbs_goal,
        "totals": totals,
        "entries": [
            {
                "id": e.id,
                "name": e.name,
                "calories": e.calories,
                "protein": e.protein,
                "carbs": e.carbs,
                "fat": e.fat,
            }
            for e in entries
        ],
    })


@app.route("/api/food-search")
@login_required
def api_food_search():
    query = request.args.get("q", "").strip()
    if not query:
        return jsonify({"items": []})
    items = db.search_food_entries(query, int(current_user.id), limit=20)
    return jsonify({"items": items})


@app.route("/history")
@login_required
def history():
    """
    Show recent history with weekly or monthly charting.
    For each day we compute totals and attach the goal for chart rendering.
    """
    from datetime import timedelta

    view = request.args.get("view", "weekly").lower()
    if view not in {"weekly", "monthly"}:
        view = "weekly"

    # Determine start/end dates for the selected view. For weekly we use
    # the last 7 days. For monthly we align to the requested calendar month
    # (first -> last day). Users can pass `year` and `month` query params.
    import calendar

    if view == "weekly":
        window_days = 6
        start_dt = date.today() - timedelta(days=window_days)
        end_dt = date.today()
    else:
        # calendar month. Accept optional ?year=YYYY&month=M, default to current
        q_year = request.args.get("year")
        q_month = request.args.get("month")
        if q_year and q_month:
            try:
                year = int(q_year)
                month = int(q_month)
            except ValueError:
                year = date.today().year
                month = date.today().month
        else:
            year = date.today().year
            month = date.today().month

        last_day = calendar.monthrange(year, month)[1]
        start_dt = date(year, month, 1)
        end_dt = date(year, month, last_day)
        window_days = (end_dt - start_dt).days

    start_date = start_dt.isoformat()
    end_date = end_dt.isoformat()

    entries = db.get_entries_in_range(start_date, end_date, int(current_user.id))
    goals_by_date = {goal.date: goal for goal in db.get_goals_in_range(start_date, end_date, int(current_user.id))}
    entries_by_date = {}
    for entry in entries:
        entries_by_date.setdefault(entry.date, []).append(entry)

    # Build list of date strings (ISO format) for the selected window
    date_list = []
    if view == "monthly":
        for i in range(0, window_days + 1):
            date_list.append((start_dt + timedelta(days=i)).isoformat())
    else:
        for i in range(window_days, -1, -1):
            date_list.append((date.today() - timedelta(days=i)).isoformat())

    days = []
    for d in date_list:
        day_entries = entries_by_date.get(d, [])
        totals = daily_totals(day_entries)
        goal = goals_by_date.get(d) or DailyGoal(user_id=int(current_user.id), date=d, calorie_goal=2000, protein_goal=0.0, carbs_goal=0.0)
        if d == today_str():
            label = "Today"
            weekday_name = date.fromisoformat(d).strftime("%a")
        else:
            dt = date.fromisoformat(d)
            if view == "weekly":
                label = dt.strftime("%a")
                weekday_name = label
            else:
                label = dt.strftime("%d")
                weekday_name = dt.strftime("%a")
        days.append(
            {
                "date": d,
                "label": label,
                "weekday_name": weekday_name,
                "entries": day_entries,
                "totals": totals,
                "goal": goal,
                "weekday": date.fromisoformat(d).weekday(),
            }
        )

    max_cal = max((d["totals"]["calories"] for d in days), default=0)
    goal_max = max((d["goal"].calorie_goal for d in days), default=2000)
    chart_max = max(max_cal, goal_max) or 1
    goal_line         = int(sum(d["goal"].calorie_goal for d in days) / len(days)) if days else 0
    protein_goal_line = round(sum(d["goal"].protein_goal for d in days) / len(days), 1) if days else 0
    carbs_goal_line   = round(sum(d["goal"].carbs_goal   for d in days) / len(days), 1) if days else 0
    total_calories = sum(d["totals"]["calories"] for d in days)
    average_calories = round(total_calories / len(days)) if days else 0

    weeks = []
    if view == "monthly":
        # Align weeks so the calendar grid starts on Sunday
        first_weekday = start_dt.weekday()  # Monday=0..Sunday=6
        # Convert to Sunday=0..Saturday=6 mapping
        leading = [None] * ((first_weekday + 1) % 7)
        padded_days = leading + list(days)
        while len(padded_days) % 7 != 0:
            padded_days.append(None)
        for i in range(0, len(padded_days), 7):
            weeks.append(padded_days[i : i + 7])
    # Compute a month title for the monthly calendar using the requested
    # start/end dates; also expose previous/next month links.
    month_title = None
    prev_month = next_month = None
    if view == "monthly":
        first_dt = start_dt
        last_dt = end_dt
        if first_dt.year == last_dt.year and first_dt.month == last_dt.month:
            month_title = first_dt.strftime("%B %Y")
        elif first_dt.year == last_dt.year:
            month_title = f"{first_dt.strftime('%b')} – {last_dt.strftime('%b %Y')}"
        else:
            month_title = f"{first_dt.strftime('%b %Y')} – {last_dt.strftime('%b %Y')}"

        # prev/next month calculation
        if first_dt.month == 1:
            prev_month = (first_dt.year - 1, 12)
        else:
            prev_month = (first_dt.year, first_dt.month - 1)

        if first_dt.month == 12:
            next_month = (first_dt.year + 1, 1)
        else:
            next_month = (first_dt.year, first_dt.month + 1)

    return render_template(
        "history.html",
        today=today_str(),
        days=days,
        weeks=weeks,
        chart_max=chart_max,
        goal_line=goal_line,
        protein_goal_line=protein_goal_line,
        carbs_goal_line=carbs_goal_line,
        view=view,
        summary={
            "total_calories": total_calories,
            "average_calories": average_calories,
            "days": len(days),
        },
        month_title=month_title,
        prev_month=prev_month,
        next_month=next_month,
    )


@app.route("/api/today")
def api_today():
    """Return today's totals as JSON — handy for optional JS widgets."""
    today = today_str()
    entries = db.get_entries_for_date(today)
    totals = daily_totals(entries)
    goal = db.get_goal_for_date_or_default(today)
    return jsonify(
        {
            "date": today,
            "totals": totals,
            "goal": goal.calorie_goal,
        }
    )


@app.route("/api/parse-food", methods=["POST"])
@login_required
def api_parse_food():
    """Parse natural language food description via AI provider with automatic fallback."""
    data = request.get_json()
    if not data or "text" not in data:
        return jsonify({"error": "Missing 'text' field"}), 400

    text = data["text"].strip()
    if not text:
        return jsonify({"error": "Empty text"}), 400

    result, provider_name = parse_food_with_fallback(text)
    normalized = normalize_ai_result(result)
    save_ai_response(normalized, text, provider_name)
    if "error" in normalized:
        return jsonify(normalized), 503
    return jsonify(normalized)


@app.route("/add-bulk", methods=["POST"])
@login_required
def add_bulk_entries():
    """Add multiple food entries from parsed AI results."""
    data = request.get_json()
    if not data or "items" not in data:
        return jsonify({"error": "Missing 'items' field"}), 400

    entry_date = data.get("date", "").strip() or today_str()
    items = data["items"]
    added = []
    for item in items:
        name = item.get("name", "Unnamed")
        portion = item.get("portion", "")
        display_name = f"{name} ({portion})" if portion else name

        entry = FoodEntry(
            id=None,
            user_id=int(current_user.id),
            date=entry_date,
            name=display_name,
            calories=int(item.get("calories", 0)),
            protein=float(item.get("protein", 0)),
            carbs=float(item.get("carbs", 0)),
            fat=float(item.get("fat", 0)),
            timestamp=now_iso(),
        )
        entry_id = db.insert_entry(entry, int(current_user.id))
        added.append({"id": entry_id, "name": display_name})

    return jsonify({"added": added, "count": len(added)})


@app.route("/api/providers")
def api_get_providers():
    """Get list of available AI providers."""
    from ai_config import get_configured_providers

    return jsonify(
        {
            "providers": list_providers(),
            "configured": get_configured_providers(),
            "active": ACTIVE_PROVIDER,
        }
    )


@app.route("/api/providers/active", methods=["POST"])
def api_set_active_provider():
    """Set the active AI provider."""
    data = request.get_json()
    if not data or "provider" not in data:
        return jsonify({"error": "Missing 'provider' field"}), 400

    provider = data["provider"]
    try:
        set_active_provider(provider)
        return jsonify({"success": True, "active": provider})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@app.route("/admin/audit-logs")
@login_required
def audit_logs():
    """Render a small admin page showing recent AI response audit logs."""
    limit = request.args.get("limit", 50, type=int)
    limit = max(1, min(limit, 200))
    logs = db.get_ai_response_logs(limit)
    return render_template(
        "audit_logs.html",
        today=today_str(),
        logs=logs,
        limit=limit,
    )


@app.route("/api/audit-logs")
@login_required
def api_audit_logs():
    """Return recent AI response audit logs as JSON."""
    limit = request.args.get("limit", 50, type=int)
    limit = max(1, min(limit, 200))
    logs = db.get_ai_response_logs(limit)
    return jsonify(
        [
            {
                "id": log.id,
                "timestamp": log.timestamp,
                "provider": log.provider,
                "status": log.status,
                "input_text": log.input_text,
                "response_payload": log.response_payload,
            }
            for log in logs
        ]
    )


@app.route("/admin/audit-logs/delete/<int:log_id>", methods=["POST"])
@login_required
def delete_audit_log(log_id: int):
    """Delete an AI response audit log entry."""
    db.delete_ai_response_log(log_id)
    return redirect(url_for("audit_logs"))


@app.route("/admin/prompts")
@login_required
def prompt_versions_page():
    """Display all prompt versions and let the admin switch or edit them."""
    versions = db.get_prompt_versions()
    active = db.get_active_prompt_version()
    return render_template(
        "prompt_versions.html",
        today=today_str(),
        versions=versions,
        active=active,
    )


@app.route("/admin/prompts", methods=["POST"])
@login_required
def save_prompt_version():
    """Create a new prompt version or update an existing one."""
    version_id = request.form.get("version_id")
    name = request.form.get("name", "").strip() or "Prompt"
    content = request.form.get("content", "").strip()
    if not content:
        return redirect(url_for("prompt_versions_page"))

    db.create_prompt_version(
        PromptVersion(
            id=None,
            name=name,
            content=content,
            created_at=now_iso(),
            is_active=True,
        )
    )
    return redirect(url_for("prompt_versions_page"))


@app.route("/admin/prompts/activate/<int:version_id>", methods=["POST"])
@login_required
def activate_prompt_version(version_id: int):
    """Make a prompt version the active one."""
    db.set_active_prompt_version(version_id)
    return redirect(url_for("prompt_versions_page"))


@app.route("/admin/prompts/delete/<int:version_id>", methods=["POST"])
@login_required
def delete_prompt_version(version_id: int):
    """Delete an old prompt version from the database."""
    db.delete_prompt_version(version_id)
    return redirect(url_for("prompt_versions_page"))


# ---------------------------------------------------------------------------
# Admin user management
# ---------------------------------------------------------------------------

def admin_required(f):
    """Decorator to require admin access."""
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash("Admin access required.", "error")
            return redirect(url_for("index"))
        return f(*args, **kwargs)
    return decorated_function


@app.route("/admin/users")
@login_required
@admin_required
def admin_users():
    """Show all users (admin only)."""
    users = db.get_all_users()
    return render_template(
        "admin_users.html",
        today=today_str(),
        users=users,
    )


@app.route("/admin/users/make-admin/<int:user_id>", methods=["POST"])
@login_required
@admin_required
def make_user_admin(user_id: int):
    """Make a user admin (admin only)."""
    is_admin = request.form.get("is_admin", "false").lower() == "true"
    db.set_user_admin(user_id, is_admin)
    flash(f"User admin status updated.", "info")
    return redirect(url_for("admin_users"))


@app.route("/admin/users/delete/<int:user_id>", methods=["POST"])
@login_required
@admin_required
def delete_user_route(user_id: int):
    """Delete a user (admin only)."""
    # Prevent deleting yourself
    if int(current_user.id) == user_id:
        flash("Cannot delete your own account.", "error")
        return redirect(url_for("admin_users"))
    
    user = db.get_user_by_id(user_id)
    if user:
        db.delete_user(user_id)
        flash(f"User {user['email']} deleted.", "info")
    return redirect(url_for("admin_users"))


# ---------------------------------------------------------------------------
# Startup
# ---------------------------------------------------------------------------

# Initialise the database schema as soon as the module is imported.
db.init_db()

if __name__ == "__main__":
    app.run(debug=False, host="0.0.0.0", port=3000)
