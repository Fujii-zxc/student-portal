import os
import secrets
import smtplib
from email.mime.text import MIMEText
from functools import wraps

from flask import session, redirect, url_for, flash, request, abort, current_app
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

from db import query

VERIFY_SALT = "email-verify-salt"


# ---------- Current user ----------

def get_current_user():
    user_id = session.get("user_id")
    if not user_id:
        return None
    return query("SELECT * FROM users WHERE id = ?", (user_id,), one=True)


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            flash("Please log in to continue.", "warning")
            return redirect(url_for("auth.login", next=request.path))
        return view(*args, **kwargs)
    return wrapped


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        user = get_current_user()
        if not user:
            flash("Please log in to continue.", "warning")
            return redirect(url_for("auth.login", next=request.path))
        if user["role"] != "admin":
            abort(403)
        return view(*args, **kwargs)
    return wrapped


def student_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        user = get_current_user()
        if not user:
            flash("Please log in to continue.", "warning")
            return redirect(url_for("auth.login", next=request.path))
        if user["role"] != "student":
            abort(403)
        return view(*args, **kwargs)
    return wrapped


# ---------- CSRF protection (lightweight, no extra deps) ----------

def get_csrf_token():
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_hex(32)
    return session["csrf_token"]


def validate_csrf():
    token = session.get("csrf_token")
    form_token = request.form.get("csrf_token")
    if not token or not form_token or not secrets.compare_digest(token, form_token):
        abort(400, description="Invalid or missing CSRF token.")


# ---------- Email verification tokens ----------

def _serializer():
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"])


def generate_verification_token(email):
    return _serializer().dumps(email, salt=VERIFY_SALT)


def verify_token(token, max_age=60 * 60 * 24):  # 24 hours
    try:
        email = _serializer().loads(token, salt=VERIFY_SALT, max_age=max_age)
    except (BadSignature, SignatureExpired):
        return None
    return email


# ---------- Email sending (falls back to demo mode) ----------

def send_verification_email(to_email, link):
    cfg = current_app.config
    if not cfg.get("MAIL_SERVER"):
        # Demo mode: no SMTP configured, just log it.
        current_app.logger.info(f"[DEMO MODE] Verification link for {to_email}: {link}")
        return False  # signals caller to show the link on-screen instead

    msg = MIMEText(
        f"Hello,\n\nPlease verify your {cfg['SCHOOL_NAME']} student portal account "
        f"by clicking the link below:\n\n{link}\n\n"
        f"This link expires in 24 hours.\n"
    )
    msg["Subject"] = f"Verify your {cfg['SCHOOL_NAME']} Student Portal account"
    msg["From"] = cfg["MAIL_SENDER"]
    msg["To"] = to_email

    with smtplib.SMTP(cfg["MAIL_SERVER"], cfg["MAIL_PORT"]) as server:
        server.starttls()
        if cfg["MAIL_USERNAME"]:
            server.login(cfg["MAIL_USERNAME"], cfg["MAIL_PASSWORD"])
        server.sendmail(cfg["MAIL_SENDER"], [to_email], msg.as_string())
    return True


# ---------- File uploads ----------

def allowed_file(filename):
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower() in current_app.config["ALLOWED_EXTENSIONS"]
    )
