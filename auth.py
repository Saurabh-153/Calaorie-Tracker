"""Authentication helpers — OTP generation and Gmail email sending."""

import os
import secrets
import smtplib
import logging
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

import database as db

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config (read from .env)
# ---------------------------------------------------------------------------

SMTP_HOST     = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT     = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER     = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
APP_NAME      = os.getenv("APP_NAME", "CalTrack")

# Comma-separated list of allowed email addresses
_raw = os.getenv("ALLOWED_EMAILS", "")
ALLOWED_EMAILS = {e.strip().lower() for e in _raw.split(",") if e.strip()}

OTP_TTL_MINUTES  = int(os.getenv("OTP_TTL_MINUTES", "5"))
OTP_MAX_ATTEMPTS = int(os.getenv("OTP_MAX_ATTEMPTS", "5"))
SESSION_DAYS     = int(os.getenv("SESSION_DAYS", "7"))


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

def is_allowed(email: str) -> bool:
    """Return True if the email is on the whitelist (or whitelist is empty = open)."""
    if not ALLOWED_EMAILS:
        return True
    return email.strip().lower() in ALLOWED_EMAILS


def send_otp(email: str) -> tuple[bool, str]:
    """
    Generate a 6-digit OTP, persist it, and email it.
    Returns (success: bool, message: str).
    """
    if not is_allowed(email):
        return False, "This email is not authorised to access the app."

    if not SMTP_USER or not SMTP_PASSWORD:
        return False, "SMTP is not configured. Set SMTP_USER and SMTP_PASSWORD in .env."

    code = f"{secrets.randbelow(1_000_000):06d}"
    expires_at = (datetime.now() + timedelta(minutes=OTP_TTL_MINUTES)).isoformat()

    try:
        db.create_otp(email, code, expires_at)
    except Exception as exc:
        logger.error("Failed to save OTP for %s: %s", email, exc)
        return False, "Internal error. Please try again."

    try:
        _send_email(email, code)
    except Exception as exc:
        logger.error("Failed to send OTP email to %s: %s", email, exc)
        return False, "Failed to send email. Check SMTP settings."

    return True, f"OTP sent to {email}. Valid for {OTP_TTL_MINUTES} minutes."


def verify_otp(email: str, code: str) -> tuple[bool, str]:
    """
    Verify the submitted OTP code for the email.
    Returns (success: bool, message: str).
    On success the user row is also created/fetched (side effect).
    """
    otp = db.get_active_otp(email)

    if otp is None:
        return False, "No active OTP found. Please request a new one."

    if otp["attempts"] >= OTP_MAX_ATTEMPTS:
        return False, "Too many failed attempts. Please request a new OTP."

    if otp["code"] != code.strip():
        db.increment_otp_attempts(otp["id"])
        remaining = OTP_MAX_ATTEMPTS - otp["attempts"] - 1
        return False, f"Incorrect code. {remaining} attempt(s) remaining."

    db.mark_otp_used(otp["id"])
    db.get_or_create_user(email)          # ensure user row exists
    return True, "Verified."


# ---------------------------------------------------------------------------
# Internal email sender
# ---------------------------------------------------------------------------

def _send_email(to: str, code: str):
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"{APP_NAME} — your login code: {code}"
    msg["From"]    = SMTP_USER
    msg["To"]      = to

    text = f"Your {APP_NAME} login code is: {code}\n\nValid for {OTP_TTL_MINUTES} minutes.\nDo not share this code."
    html = f"""
    <div style="font-family:sans-serif;max-width:400px;margin:auto;padding:32px;">
      <h2 style="color:#0D9E8A">{APP_NAME}</h2>
      <p>Your one-time login code is:</p>
      <div style="font-size:2.5rem;font-weight:700;letter-spacing:.3rem;
                  color:#0D9E8A;text-align:center;padding:16px 0">{code}</div>
      <p style="color:#666;font-size:.85rem;">
        Valid for <strong>{OTP_TTL_MINUTES} minutes</strong>.<br>
        If you didn't request this, ignore this email.
      </p>
    </div>
    """

    msg.attach(MIMEText(text, "plain"))
    msg.attach(MIMEText(html, "html"))

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.ehlo()
        server.starttls()
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.sendmail(SMTP_USER, to, msg.as_string())
