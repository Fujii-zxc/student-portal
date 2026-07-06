# Student Portal (Demo Build)

A working student-portal prototype: students can view grades, request
enrollment, and upload documents (School ID, copy of grades, etc). Admins
get a control panel to manage students, post grades, approve/reject
enrollment requests, review uploaded documents, and post announcements.

Built with **Flask only** (no other pip packages) — Python's standard library
handles the database (SQLite), password hashing (`werkzeug`), and tokens
(`itsdangerous`, which ships with Flask). This keeps it easy to run anywhere,
including on a school computer with no internet access to install extra
packages.

## 1. Run it

Requires Python 3.9+.

```bash
cd student_portal
pip install -r requirements.txt      # installs Flask only
python app.py
```

Then open **http://localhost:5000** in a browser.

The database (`instance/portal.db`) and an `admin@university.edu` account are
created automatically the first time you run it.

## 2. Demo logins

| Role    | Email                   | Password    |
|---------|-------------------------|-------------|
| Admin   | admin@university.edu    | Admin123!   |

Create a student account from the "Create Student Account" button on the
landing page — you'll need to verify it (see below).

## 3. About email verification (important for your demo)

Real email requires an SMTP account (Gmail, Outlook, a school mail server,
etc). Since you probably don't have one set up yet, this app runs in
**demo mode** by default: instead of emailing the verification link, it shows
the link directly on-screen right after registration, so you can click it
and continue the demo without any email setup.

To wire up real emails later, set these environment variables before running
`app.py` (e.g. in a `.env` file or your terminal):

```bash
export MAIL_SERVER=smtp.gmail.com
export MAIL_PORT=587
export MAIL_USERNAME=your@gmail.com
export MAIL_PASSWORD=your-app-password
export MAIL_SENDER=your@gmail.com
```

## 4. What's included

- **Students:** register, verify email, log in, view grades, submit
  enrollment requests, upload documents (School ID, grade copies, etc, as
  PDF/PNG/JPG), read announcements, edit profile, change password.
- **Admins:** dashboard with live stats, search/manage every student
  account (verify, activate/deactivate, reset password, delete), enter and
  delete grades per student, approve/reject enrollment requests, review and
  download submitted documents, post/delete announcements, create
  additional admin accounts.
- Security basics: hashed passwords, session-based login, CSRF protection
  on every form, role-based access control (a student can't reach admin
  pages and vice versa), file-type/size limits on uploads.

## 5. Before you actually pitch this to a university

This is a **prototype to demonstrate the concept**, not production software.
If the university is interested, flag these to whoever picks it up:

- Change `SECRET_KEY` in `config.py` to a long random value, and don't
  commit it to source control.
- Move from SQLite to a proper database (PostgreSQL/MySQL) for real
  multi-user load.
- Put it behind HTTPS (SSL) — never run a real portal over plain HTTP.
- Set up real email sending (see above) and rate-limit login/registration.
- Have the school's IT/security team review it before handling real student
  data — FERPA-style privacy rules apply to student records in most
  places.

## 6. Project structure

```
student_portal/
├── app.py              # app factory, creates DB + default admin on first run
├── config.py           # settings (secret key, mail, upload limits)
├── db.py                # SQLite schema + query helpers
├── utils.py             # auth/session helpers, CSRF, tokens, email
├── routes_auth.py       # register / login / logout / email verification
├── routes_student.py    # student-facing pages
├── routes_admin.py      # admin control panel
├── templates/           # Jinja2 HTML templates
└── static/css/          # stylesheet
```
