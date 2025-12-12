# ISD-v1.0

Mechanic / Appointment management web application (Flask).

[![codecov](https://codecov.io/gh/roynahra1/ISD1/branch/main/graph/badge.svg)](https://codecov.io/gh/roynahra1/ISD1)

This repository contains a Flask backend, Jinja2 templates, a plate-detection OCR helper, and tests.

---

## Quickstart (Windows PowerShell)

1. Clone the repository:

```powershell
git clone https://github.com/roynahra1/ISD1.git
cd ISD1
```

2. Create and activate a Python virtual environment (from repo root):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

3. Install Python dependencies:

```powershell
pip install -r requirements.txt
```

4. Create environment variables (see `Environment variables` section) and initialize the database:

```powershell
python setup_database.py
```

5. Run the app (development):

```powershell
python run.py
# or
uvicorn app.main:app --reload --port 5000
```

Open `http://127.0.0.1:5000` in your browser.

---

## Requirements

- Python 3.10+
- MySQL server (optional)  SQLite is supported by default
- Tesseract OCR (optional) for plate detection features

Install Python packages from `requirements.txt`.

---

## Environment variables

Create a `.env` (or set environment variables) with the values your deployment requires. Typical variables used by the app:

```
APP_SECRET_KEY=change-me
DB_HOST=127.0.0.1
DB_PORT=3306
DB_USER=root
DB_PASSWORD=secret
DB_NAME=isd
```

The app will use SQLite if `DATABASE_URL` or DB settings are not configured.

---

## Database setup

Run the provided `setup_database.py` to create tables and optional seed data:

```powershell
python setup_database.py
```

Inspect the script before running on production data.

---

## Testing

Run the pytest test suite from the repository root:

```powershell
python -m pytest -q
```

Coverage is supported in CI; locally you can run:

```powershell
pytest --cov=.
```

---

## Plate detection (OCR)

The project includes `plate_detector.py` which uses OpenCV and `pytesseract` for OCR-based plate recognition. Notes:

- Install Tesseract-OCR on Windows and ensure the binary is on PATH (`C:\Program Files\Tesseract-OCR\tesseract.exe`).
- The detector supports multiple preprocessing steps; tune thresholds and OCR configs for your dataset.

---

## Key files and folders

- `app.py`  Flask app factory and configuration
- `run.py`  app entry point
- `routes/`  Flask blueprints for authentication, appointments, mechanics, detection, etc.
- `templates/`  Jinja2 HTML templates
- `utils/`  helper modules (database connection, utilities)
- `plate_detector.py`  OCR-based plate detection helper
- `models/`  optional model weights (if used)
- `tests/`  pytest test suite

---

## Troubleshooting

- App pages accessible after logout: ensure session handling and template-level auth checks are in place.
- Tests failing due to DB state: recreate or reset the DB and re-run `setup_database.py`.
- Plate detection poor results: provide sample images and tune preprocessing or try expanding OCR whitelists.

---

## Contributing

1. Fork the repo
2. Create a feature branch
3. Add tests for new behavior
4. Open a pull request describing the change

---

If you want, I can also:
- add a `.env.example` file,
- add a `backend/migrate_db.py` helper script,
- create a GitHub Actions workflow to run tests and upload coverage to Codecov,
- add a short developer setup script (`scripts/setup.ps1`).

Please tell me which follow-up you'd like.
