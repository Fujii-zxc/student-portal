from flask import (
    Blueprint, render_template, request, redirect, url_for, session, flash, current_app
)
from werkzeug.security import generate_password_hash, check_password_hash

from db import query, execute
from utils import (
    get_current_user, validate_csrf, get_csrf_token,
    generate_verification_token, verify_token, send_verification_email
)

bp = Blueprint("auth", __name__)


@bp.route("/")
def index():
    if get_current_user():
        return redirect(url_for("dashboard_redirect"))
    return render_template("auth/landing.html")


@bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        validate_csrf()
        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip().lower()
        student_number = request.form.get("student_number", "").strip()
        program = request.form.get("program", "").strip()
        year_level = request.form.get("year_level", "").strip()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")

        errors = []
        if not full_name or not email or not password:
            errors.append("Full name, email, and password are required.")
        if "@" not in email or "." not in email:
            errors.append("Please enter a valid email address.")
        if len(password) < 8:
            errors.append("Password must be at least 8 characters long.")
        if password != confirm:
            errors.append("Passwords do not match.")
        if query("SELECT id FROM users WHERE email = ?", (email,), one=True):
            errors.append("An account with that email already exists.")

        if errors:
            for e in errors:
                flash(e, "danger")
            return render_template("auth/register.html", form=request.form, csrf_token=get_csrf_token())

        password_hash = generate_password_hash(password)
        user_id = execute(
            """INSERT INTO users (full_name, email, password_hash, role, student_number,
                                   program, year_level, is_verified)
               VALUES (?, ?, ?, 'student', ?, ?, ?, 0)""",
            (full_name, email, password_hash, student_number, program, year_level),
        )

        token = generate_verification_token(email)
        link = url_for("auth.verify_email", token=token, _external=True)
        sent = send_verification_email(email, link)

        if sent:
            flash("Account created! Check your email for a verification link.", "success")
            return redirect(url_for("auth.login"))
        else:
            # Demo mode - no mail server configured, show the link directly.
            flash("Account created! (Demo mode: no email server configured.)", "success")
            return render_template("auth/verify_pending.html", demo_link=link, email=email)

    return render_template("auth/register.html", form={}, csrf_token=get_csrf_token())


@bp.route("/verify/<token>")
def verify_email(token):
    email = verify_token(token)
    if not email:
        flash("That verification link is invalid or has expired.", "danger")
        return redirect(url_for("auth.login"))

    user = query("SELECT * FROM users WHERE email = ?", (email,), one=True)
    if not user:
        flash("Account not found.", "danger")
        return redirect(url_for("auth.register"))

    execute("UPDATE users SET is_verified = 1 WHERE id = ?", (user["id"],))
    flash("Your email has been verified! You can now log in.", "success")
    return redirect(url_for("auth.login"))


@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        validate_csrf()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        user = query("SELECT * FROM users WHERE email = ?", (email,), one=True)

        if not user or not check_password_hash(user["password_hash"], password):
            flash("Incorrect email or password.", "danger")
            return render_template("auth/login.html", csrf_token=get_csrf_token())

        if not user["is_active"]:
            flash("This account has been deactivated. Contact the registrar's office.", "danger")
            return render_template("auth/login.html", csrf_token=get_csrf_token())

        if not user["is_verified"] and user["role"] == "student":
            flash("Please verify your email before logging in.", "warning")
            return render_template("auth/login.html", csrf_token=get_csrf_token())

        session.clear()
        session["user_id"] = user["id"]
        session["role"] = user["role"]
        flash(f"Welcome back, {user['full_name']}!", "success")
        next_url = request.args.get("next")
        return redirect(next_url or url_for("dashboard_redirect"))

    return render_template("auth/login.html", csrf_token=get_csrf_token())


@bp.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("auth.login"))
