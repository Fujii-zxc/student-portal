from flask import Flask, redirect, url_for
from werkzeug.security import generate_password_hash

from config import Config
from db import init_db, close_db, query, execute
from utils import get_current_user

import routes_auth
import routes_student
import routes_admin


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    app.teardown_appcontext(close_db)

    app.register_blueprint(routes_auth.bp)
    app.register_blueprint(routes_student.bp)
    app.register_blueprint(routes_admin.bp)

    @app.context_processor
    def inject_globals():
        return {
            "current_user": get_current_user(),
            "school_name": app.config["SCHOOL_NAME"],
        }

    @app.route("/dashboard")
    def dashboard_redirect():
        user = get_current_user()
        if not user:
            return redirect(url_for("auth.login"))
        if user["role"] == "admin":
            return redirect(url_for("admin.dashboard"))
        return redirect(url_for("student.dashboard"))

    @app.errorhandler(403)
    def forbidden(e):
        return "403 - You don't have permission to view this page.", 403

    @app.errorhandler(404)
    def not_found(e):
        return "404 - Page not found.", 404

    with app.app_context():
        init_db(app)
        seed_default_admin(app)

    return app


def seed_default_admin(app):
    """Create a default admin account on first run, for demo purposes."""
    existing = query("SELECT id FROM users WHERE role = 'admin' LIMIT 1")
    if existing:
        return
    execute(
        """INSERT INTO users (full_name, email, password_hash, role, is_verified)
           VALUES (?, ?, ?, 'admin', 1)""",
        ("Portal Administrator", "admin@university.edu", generate_password_hash("Admin123!"))
    )
    app.logger.info("Seeded default admin -> admin@university.edu / Admin123!")


app = create_app()

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
