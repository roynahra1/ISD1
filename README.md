# ISD-v1.0  Appointment & Mechanic Management

A Flask-based service-center application for booking appointments, tracking cars/owners, and supporting mechanics with a dashboard. This repository contains the Flask backend, Jinja2 templates, a plate-detection OCR helper, tests, and developer tooling.

> Quick: This README targets developers. For running locally, use PowerShell on Windows (examples included).

---

## Table of contents
- Project overview
- Quickstart (Windows)
- Prerequisites
- Installation
- Configuration (`.env`)
- Database setup
- Running the app (dev)
- Testing
- Plate detection (Tesseract + notes)
- API reference (common endpoints)
- Developer notes & coding conventions
- Troubleshooting
- Contributing
- License

---

## Project overview

The app supports two primary roles:
- Owners / Clients: sign up, manage cars, book appointments
- Mechanics: manage appointments, mark services complete, view dashboard

Key components:
- `routes/`  Flask Blueprints for `auth`, `appointment`, `mechanic`, `detection`, etc.
- `templates/`  Jinja2 HTML templates (client and mechanic views)
- `utils/`  helpers (database connection, helpers)
- `plate_detector.py`  OCR + image processing helper (OpenCV + pytesseract)
- `tests/`  pytest-based test suite

---

## Quickstart (Windows PowerShell)

1. Open PowerShell in the project root.
2. Create and activate a virtual environment:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

3. Install dependencies:

```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
```

4. Copy environment example (create `.env`) and set DB creds (see next section).
5. Run database setup (or apply migrations):

```powershell
python setup_database.py
```

6. Start the development server:

```powershell
python run.py
```

Open `http://127.0.0.1:5000` in your browser.

---

## Prerequisites

- Python 3.10+
- MySQL server (or compatible) for production/test DB
- Optional but recommended: Tesseract OCR (Windows installer) for `plate_detector.py` functionality

Tesseract recommendation (Windows):
- Download and install from https://github.com/tesseract-ocr/tesseract/releases
- Add `C:\Program Files\Tesseract-OCR\` to your PATH, or set `pytesseract.pytesseract.tesseract_cmd` in code.

---

## Installation & Dependencies

- `requirements.txt` contains runtime deps.
- `requirements-dev.txt` contains dev/test extras.

Install them as shown in Quickstart. If you need the full optional packages (CV, YOLO weights), use `requirements-full.txt`.

---

## Configuration (`.env`)

Create a `.env` in the repo root (DO NOT commit it). Example values:

```env
APP_SECRET_KEY=change-me-for-prod
DB_HOST=127.0.0.1
DB_PORT=3306
DB_USER=root
DB_PASSWORD=secret
DB_NAME=isd
```

Environment variables are read by the app factory (`app.create_app`). Use PowerShell to export temporarily:

```powershell
$env:DB_HOST='127.0.0.1'; $env:DB_USER='root'; $env:DB_PASSWORD='secret'; $env:DB_NAME='isd'
python run.py
```

---

## Database setup

This repo includes `setup_database.py` to create tables and optional seed data. Inspect the script before running on a production DB.

```powershell
python setup_database.py
```

If you use migrations, adapt `setup_database.py` or switch to your migration tool (Alembic, Flask-Migrate, etc.).

---

## Run (development)

Start the app with:

```powershell
python run.py
```

For debugging/reloading you can set Flask debug mode in `run.py` or environment variables. Avoid debug mode in production.

---

## Testing

Run the full test suite with pytest (venv active):

```powershell
python -m pytest -q
```

Run a single test:

```powershell
python -m pytest tests/test_auth_routes.py::test_signup_success -q
```

Notes:
- Tests may require a test database or use fixtures from `tests/conftest.py`.
- If tests fail due to DB state, reset schema with `setup_database.py` or use a disposable DB.

---

## Plate detection (OCR + plate_detector.py)

`plate_detector.py` provides a lightweight OCR-based fallback to detect license plates. It uses OpenCV preprocessing and `pytesseract`.

Key tips:
- Install Tesseract and ensure it's reachable (PATH) or set `pytesseract.pytesseract.tesseract_cmd` to the binary.
- If detection quality is low, collect example images and tune:
  - contrast/CLAHE settings
  - Tesseract PSM/OEM and whitelist
  - cropping / rotation retry thresholds
- The repo contains `models/` for optional detector weights (YOLO). If you enable that path, ensure correct model version and hardware support.

---

## API reference (common endpoints)

Below are the most-used endpoints and example requests (JSON or form data). Adjust `Host`/port as appropriate (default `http://127.0.0.1:5000`).

- POST `/signup`  register owner + account
  - form fields: `username`, `email`, `password`, `owner_name`, `phone`
  - curl example (form):

```bash
curl -X POST http://127.0.0.1:5000/signup -F "username=joe" -F "password=secret" -F "owner_name=Joe Smith"
```

- POST `/login`  login (creates session)
  - form: `username`, `password`

- POST `/book`  book an appointment
  - form fields: `owner_id` (or session user), `car_plate`, `car_model`, `car_year`, `service_id`, `date`, `time`

- GET `/mechanic/api/recent-activity`  recent activities (mechanic-only)
  - supports `?limit=8&offset=0`

- POST `/mechanic/api/complete-service`  mark service complete (JSON)
  - Example payload: `{ "appointment_id": 42, "notes": "Done", "status": "completed" }`

See `routes/` for full parameter lists and behavior.

---

## Developer notes & conventions

- Logging: prefer the `logger` module (configured in app). Avoid `print()` in server code.
- Database: use parameterized queries to avoid SQL injection. Prefer `cursor(dictionary=True)` when reading rows.
- Sessions: `session['logged_in']`, `session['owner_id']`, and `session['mechanic_logged_in']` are used. Ensure session is cleared on logout.
- Frontend templates: use Jinja includes (`templates/topbar.html`) for common UI elements.
- Tests: add pytest fixtures to `tests/conftest.py` for DB or app context.

Security:
- Never commit `.env` or DB credentials.
- Use a strong `APP_SECRET_KEY` for production and secure session cookies.

---

## Troubleshooting

- Tests failing due to DB: ensure `.env` points to a test database and re-run `setup_database.py`.
- Tesseract not found: set `pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"` before calling OCR.
- Pages accessible after logout: ensure protected templates include JS auth-check or server-side `login_required` checks.

---

## Contributing

1. Fork the repo
2. Create a feature branch
3. Add tests for new behavior
4. Run test suite and ensure green
5. Submit PR with description and code review

---

## Quick commands

```powershell
# activate venv
.\.venv\Scripts\Activate.ps1
# run tests
python -m pytest -q
# start dev server
python run.py
```

---

If you'd like, I can:
- add a `.env.example` file to the repo,
- add more API examples (full request + expected response),
- add a `Make.ps1` or `scripts/` folder with helpers for dev tasks,
- add CI configuration snippets (GitHub Actions) to run tests and report code coverage.

Please tell me which of these you'd like next.
