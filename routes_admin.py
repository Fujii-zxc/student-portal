import os
from flask import (
    Blueprint, render_template, request, redirect, url_for, flash, current_app, send_from_directory, abort
)
from werkzeug.security import generate_password_hash

from db import query, execute
from utils import get_current_user, admin_required, validate_csrf, get_csrf_token

bp = Blueprint("admin", __name__, url_prefix="/admin")


@bp.route("/dashboard")
@admin_required
def dashboard():
    stats = {
        "total_students": query("SELECT COUNT(*) c FROM users WHERE role='student'", one=True)["c"],
        "pending_verification": query("SELECT COUNT(*) c FROM users WHERE role='student' AND is_verified=0", one=True)["c"],
        "pending_enrollments": query("SELECT COUNT(*) c FROM enrollments WHERE status='pending'", one=True)["c"],
        "pending_documents": query("SELECT COUNT(*) c FROM documents WHERE status='pending'", one=True)["c"],
    }
    recent_users = query("SELECT * FROM users WHERE role='student' ORDER BY created_at DESC LIMIT 5")
    return render_template("admin/dashboard.html", stats=stats, recent_users=recent_users)


# ---------- Users ----------

@bp.route("/users")
@admin_required
def users():
    q = request.args.get("q", "").strip()
    if q:
        like = f"%{q}%"
        rows = query(
            """SELECT * FROM users WHERE role='student' AND
               (full_name LIKE ? OR email LIKE ? OR student_number LIKE ?)
               ORDER BY created_at DESC""",
            (like, like, like)
        )
    else:
        rows = query("SELECT * FROM users WHERE role='student' ORDER BY created_at DESC")
    return render_template("admin/users.html", users=rows, q=q)


@bp.route("/users/<int:user_id>", methods=["GET", "POST"])
@admin_required
def user_detail(user_id):
    student = query("SELECT * FROM users WHERE id = ?", (user_id,), one=True)
    if not student:
        abort(404)

    if request.method == "POST":
        validate_csrf()
        action = request.form.get("action")

        if action == "toggle_verify":
            execute("UPDATE users SET is_verified = ? WHERE id = ?",
                    (0 if student["is_verified"] else 1, user_id))
            flash("Verification status updated.", "success")

        elif action == "toggle_active":
            execute("UPDATE users SET is_active = ? WHERE id = ?",
                    (0 if student["is_active"] else 1, user_id))
            flash("Account status updated.", "success")

        elif action == "reset_password":
            new_pw = request.form.get("new_password", "")
            if len(new_pw) < 8:
                flash("Password must be at least 8 characters.", "danger")
            else:
                execute("UPDATE users SET password_hash = ? WHERE id = ?",
                        (generate_password_hash(new_pw), user_id))
                flash("Password reset successfully.", "success")

        elif action == "delete_user":
            execute("DELETE FROM users WHERE id = ?", (user_id,))
            flash("Student account deleted.", "success")
            return redirect(url_for("admin.users"))

        elif action == "add_grade":
            execute(
                """INSERT INTO grades (student_id, school_year, semester, subject_code,
                                        subject_name, units, grade)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (user_id, request.form.get("school_year"), request.form.get("semester"),
                 request.form.get("subject_code"), request.form.get("subject_name"),
                 request.form.get("units") or 3, request.form.get("grade"))
            )
            flash("Grade added.", "success")

        return redirect(url_for("admin.user_detail", user_id=user_id))

    grades = query("SELECT * FROM grades WHERE student_id = ? ORDER BY school_year DESC, semester DESC", (user_id,))
    enrollments = query("SELECT * FROM enrollments WHERE student_id = ? ORDER BY date_requested DESC", (user_id,))
    documents = query("SELECT * FROM documents WHERE student_id = ? ORDER BY uploaded_at DESC", (user_id,))
    return render_template(
        "admin/user_detail.html", student=student, grades=grades,
        enrollments=enrollments, documents=documents, csrf_token=get_csrf_token()
    )


@bp.route("/grades/<int:grade_id>/delete", methods=["POST"])
@admin_required
def delete_grade(grade_id):
    validate_csrf()
    grade = query("SELECT * FROM grades WHERE id = ?", (grade_id,), one=True)
    if grade:
        execute("DELETE FROM grades WHERE id = ?", (grade_id,))
        flash("Grade deleted.", "success")
        return redirect(url_for("admin.user_detail", user_id=grade["student_id"]))
    abort(404)


# ---------- Enrollment requests ----------

@bp.route("/enrollments")
@admin_required
def enrollments():
    status = request.args.get("status", "pending")
    if status == "all":
        rows = query(
            """SELECT e.*, u.full_name, u.student_number FROM enrollments e
               JOIN users u ON u.id = e.student_id ORDER BY e.date_requested DESC"""
        )
    else:
        rows = query(
            """SELECT e.*, u.full_name, u.student_number FROM enrollments e
               JOIN users u ON u.id = e.student_id WHERE e.status = ?
               ORDER BY e.date_requested DESC""",
            (status,)
        )
    return render_template("admin/enrollments.html", rows=rows, status=status, csrf_token=get_csrf_token())


@bp.route("/enrollments/<int:enr_id>/process", methods=["POST"])
@admin_required
def process_enrollment(enr_id):
    validate_csrf()
    decision = request.form.get("decision")
    remarks = request.form.get("remarks", "")
    if decision not in ("approved", "rejected"):
        abort(400)
    execute(
        "UPDATE enrollments SET status = ?, remarks = ?, date_processed = datetime('now') WHERE id = ?",
        (decision, remarks, enr_id)
    )
    flash(f"Enrollment request {decision}.", "success")
    return redirect(url_for("admin.enrollments"))


# ---------- Documents ----------

@bp.route("/documents")
@admin_required
def documents():
    status = request.args.get("status", "pending")
    if status == "all":
        rows = query(
            """SELECT d.*, u.full_name, u.student_number FROM documents d
               JOIN users u ON u.id = d.student_id ORDER BY d.uploaded_at DESC"""
        )
    else:
        rows = query(
            """SELECT d.*, u.full_name, u.student_number FROM documents d
               JOIN users u ON u.id = d.student_id WHERE d.status = ?
               ORDER BY d.uploaded_at DESC""",
            (status,)
        )
    return render_template("admin/documents.html", rows=rows, status=status, csrf_token=get_csrf_token())


@bp.route("/documents/<int:doc_id>/download")
@admin_required
def download_document(doc_id):
    doc = query("SELECT * FROM documents WHERE id = ?", (doc_id,), one=True)
    if not doc:
        abort(404)
    return send_from_directory(current_app.config["UPLOAD_FOLDER"], doc["stored_filename"],
                                download_name=doc["original_filename"])


@bp.route("/documents/<int:doc_id>/review", methods=["POST"])
@admin_required
def review_document(doc_id):
    validate_csrf()
    decision = request.form.get("decision")
    if decision not in ("verified", "rejected"):
        abort(400)
    execute("UPDATE documents SET status = ? WHERE id = ?", (decision, doc_id))
    flash(f"Document marked as {decision}.", "success")
    return redirect(url_for("admin.documents"))


# ---------- Announcements ----------

@bp.route("/announcements", methods=["GET", "POST"])
@admin_required
def announcements():
    user = get_current_user()
    if request.method == "POST":
        validate_csrf()
        title = request.form.get("title", "").strip()
        content = request.form.get("content", "").strip()
        if not title or not content:
            flash("Title and content are required.", "danger")
        else:
            execute("INSERT INTO announcements (title, content, posted_by) VALUES (?, ?, ?)",
                    (title, content, user["id"]))
            flash("Announcement posted.", "success")
        return redirect(url_for("admin.announcements"))

    items = query("SELECT * FROM announcements ORDER BY created_at DESC")
    return render_template("admin/announcements.html", items=items, csrf_token=get_csrf_token())


@bp.route("/announcements/<int:ann_id>/delete", methods=["POST"])
@admin_required
def delete_announcement(ann_id):
    validate_csrf()
    execute("DELETE FROM announcements WHERE id = ?", (ann_id,))
    flash("Announcement deleted.", "success")
    return redirect(url_for("admin.announcements"))


# ---------- Create new admin (super-admin utility) ----------

@bp.route("/admins", methods=["GET", "POST"])
@admin_required
def manage_admins(u=None):
    if request.method == "POST":
        validate_csrf()
        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not full_name or not email or len(password) < 8:
            flash("Please fill out all fields (password min. 8 characters).", "danger")
        elif query("SELECT id FROM users WHERE email = ?", (email,), one=True):
            flash("An account with that email already exists.", "danger")
        else:
            execute(
                """INSERT INTO users (full_name, email, password_hash, role, is_verified)
                   VALUES (?, ?, ?, 'admin', 1)""",
                (full_name, email, generate_password_hash(password))
            )
            flash("New admin account created.", "success")
        return redirect(url_for("admin.manage_admins"))

    admins = query("SELECT * FROM users WHERE role='admin' ORDER BY created_at")
    return render_template("admin/admins.html", admins=admins, csrf_token=get_csrf_token())
