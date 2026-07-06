import os
import uuid

from flask import (
    Blueprint, render_template, request, redirect, url_for, flash, current_app, send_from_directory, abort
)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

from db import query, execute
from utils import get_current_user, student_required, validate_csrf, get_csrf_token, allowed_file

bp = Blueprint("student", __name__, url_prefix="/student")


@bp.route("/dashboard")
@student_required
def dashboard():
    user = get_current_user()
    grade_count = query("SELECT COUNT(*) c FROM grades WHERE student_id = ?", (user["id"],), one=True)["c"]
    pending_enrollment = query(
        "SELECT * FROM enrollments WHERE student_id = ? ORDER BY date_requested DESC LIMIT 1",
        (user["id"],), one=True
    )
    doc_count = query("SELECT COUNT(*) c FROM documents WHERE student_id = ?", (user["id"],), one=True)["c"]
    announcements = query("SELECT * FROM announcements ORDER BY created_at DESC LIMIT 5")
    return render_template(
        "student/dashboard.html", user=user, grade_count=grade_count,
        pending_enrollment=pending_enrollment, doc_count=doc_count, announcements=announcements
    )


@bp.route("/grades")
@student_required
def grades():
    user = get_current_user()
    rows = query(
        "SELECT * FROM grades WHERE student_id = ? ORDER BY school_year DESC, semester DESC",
        (user["id"],)
    )
    # group by school_year + semester for a clean transcript-style view
    grouped = {}
    for r in rows:
        key = f"{r['school_year']} - {r['semester']}"
        grouped.setdefault(key, []).append(r)
    return render_template("student/grades.html", user=user, grouped=grouped)


@bp.route("/enrollment", methods=["GET", "POST"])
@student_required
def enrollment():
    user = get_current_user()
    if request.method == "POST":
        validate_csrf()
        school_year = request.form.get("school_year", "").strip()
        semester = request.form.get("semester", "").strip()
        year_level = request.form.get("year_level", "").strip()

        if not school_year or not semester or not year_level:
            flash("Please fill out all fields.", "danger")
        else:
            execute(
                """INSERT INTO enrollments (student_id, school_year, semester, year_level, status)
                   VALUES (?, ?, ?, ?, 'pending')""",
                (user["id"], school_year, semester, year_level),
            )
            flash("Enrollment request submitted! You'll be notified once it's processed.", "success")
        return redirect(url_for("student.enrollment"))

    history = query(
        "SELECT * FROM enrollments WHERE student_id = ? ORDER BY date_requested DESC",
        (user["id"],)
    )
    return render_template("student/enrollment.html", user=user, history=history, csrf_token=get_csrf_token())


@bp.route("/documents", methods=["GET", "POST"])
@student_required
def documents():
    user = get_current_user()
    if request.method == "POST":
        validate_csrf()
        doc_type = request.form.get("doc_type", "").strip()
        file = request.files.get("file")

        if not doc_type or not file or file.filename == "":
            flash("Please choose a document type and a file.", "danger")
        elif not allowed_file(file.filename):
            flash("Only PDF, PNG, or JPG files are allowed.", "danger")
        else:
            ext = file.filename.rsplit(".", 1)[1].lower()
            stored_name = f"{uuid.uuid4().hex}.{ext}"
            os.makedirs(current_app.config["UPLOAD_FOLDER"], exist_ok=True)
            file.save(os.path.join(current_app.config["UPLOAD_FOLDER"], stored_name))
            execute(
                """INSERT INTO documents (student_id, doc_type, stored_filename, original_filename, status)
                   VALUES (?, ?, ?, ?, 'pending')""",
                (user["id"], doc_type, stored_name, secure_filename(file.filename)),
            )
            flash("Document uploaded and pending review.", "success")
        return redirect(url_for("student.documents"))

    docs = query(
        "SELECT * FROM documents WHERE student_id = ? ORDER BY uploaded_at DESC",
        (user["id"],)
    )
    return render_template("student/documents.html", user=user, docs=docs, csrf_token=get_csrf_token())


@bp.route("/documents/<int:doc_id>/download")
@student_required
def download_document(doc_id):
    user = get_current_user()
    doc = query("SELECT * FROM documents WHERE id = ? AND student_id = ?", (doc_id, user["id"]), one=True)
    if not doc:
        abort(404)
    return send_from_directory(current_app.config["UPLOAD_FOLDER"], doc["stored_filename"],
                                download_name=doc["original_filename"])


@bp.route("/announcements")
@student_required
def announcements():
    user = get_current_user()
    items = query("SELECT * FROM announcements ORDER BY created_at DESC")
    return render_template("student/announcements.html", user=user, items=items)


@bp.route("/profile", methods=["GET", "POST"])
@student_required
def profile():
    user = get_current_user()
    if request.method == "POST":
        validate_csrf()
        action = request.form.get("action")

        if action == "update_info":
            program = request.form.get("program", "").strip()
            year_level = request.form.get("year_level", "").strip()
            execute("UPDATE users SET program = ?, year_level = ? WHERE id = ?",
                    (program, year_level, user["id"]))
            flash("Profile updated.", "success")

        elif action == "change_password":
            current_pw = request.form.get("current_password", "")
            new_pw = request.form.get("new_password", "")
            confirm_pw = request.form.get("confirm_password", "")

            if not check_password_hash(user["password_hash"], current_pw):
                flash("Current password is incorrect.", "danger")
            elif len(new_pw) < 8:
                flash("New password must be at least 8 characters.", "danger")
            elif new_pw != confirm_pw:
                flash("New passwords do not match.", "danger")
            else:
                execute("UPDATE users SET password_hash = ? WHERE id = ?",
                        (generate_password_hash(new_pw), user["id"]))
                flash("Password changed successfully.", "success")

        return redirect(url_for("student.profile"))

    return render_template("student/profile.html", user=user, csrf_token=get_csrf_token())
