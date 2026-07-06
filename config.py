import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

class Config:
    # Change this to a long random string before deploying for real.
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-me")

    DATABASE_PATH = os.path.join(BASE_DIR, "instance", "portal.db")

    UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "uploads")
    ALLOWED_EXTENSIONS = {"pdf", "png", "jpg", "jpeg"}
    MAX_CONTENT_LENGTH = 8 * 1024 * 1024  # 8 MB max upload

    SCHOOL_NAME = os.environ.get("SCHOOL_NAME", "Your University")

    # ---- Email (optional) ----
    # If MAIL_SERVER is left blank, the app runs in "demo mode": instead of
    # sending a real email, it prints the verification link to the console
    # and shows it on-screen after registration, so you can demo the whole
    # flow without setting up an email account.
    MAIL_SERVER = os.environ.get("MAIL_SERVER", "")
    MAIL_PORT = int(os.environ.get("MAIL_PORT", 587))
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME", "")
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD", "")
    MAIL_SENDER = os.environ.get("MAIL_SENDER", "no-reply@example.com")
