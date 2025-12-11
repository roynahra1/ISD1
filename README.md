# ISD-v1.0

Mechanic / Appointment management web application (Flask). This repository contains a Flask backend, HTML templates, a lightweight plate-detection OCR pipeline, and tests.

This README explains how to set up the development environment on Windows (PowerShell), run the app, run tests, and where to look for the most important pieces of the codebase.

## Contents
- Project overview
- Requirements & dependencies
- Environment variables
- Database setup
- Run locally (development)
- Testing
- Plate detection notes
- Key project files & routes
- Developer guidance
- Contributing
- License

---

## Project overview

This project implements a small service center application. Core features include:
- User authentication (client + mechanic)
- Owner / Car / Appointment management
- Mechanic dashboard with statistics and recent activity
- License plate detection / OCR utilities
- Tests (pytest)

The backend is a Flask app with blueprint-based routes under `routes/`. Templates live in `templates/`. Utilities are under `utils/`.

## Requirements & dependencies

- Python 3.10+ recommended
- System dependencies: MySQL server (or compatible), and optionally Tesseract OCR for the plate detector.
- Python dependencies: listed in `requirements.txt` and `requirements-full.txt` (development extras in `requirements-dev.txt`).

Install Python packages in a virtual environment (PowerShell example):

```powershell
python -m venv .venv
.\\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

## Environment variables

Create a `.env` file in the project root or set environment variables in your shell. Typical variables the app expects (defaults are shown in `app.create_app`):

- `APP_SECRET_KEY`  Flask secret key (default in dev: `dev-secret-key-for-testing`)
- `DB_HOST`  MySQL host (default `127.0.0.1`)
- `DB_PORT`  MySQL port (default `3306`)
- `DB_USER`  MySQL user
- `DB_PASSWORD`  MySQL password
- `DB_NAME`  MySQL database name (e.g., `isd`)

Example `.env` (do not commit `.env` to git):

```env
APP_SECRET_KEY=change-me-for-prod
DB_HOST=127.0.0.1
DB_PORT=3306
DB_USER=root
DB_PASSWORD=secret
DB_NAME=isd
```

On PowerShell you can set one-off vars before launching the app:

```powershell
$env:DB_HOST = '127.0.0.1'; $env:DB_USER = 'root'; $env:DB_PASSWORD = 'secret'; $env:DB_NAME = 'isd'; python run.py
```

## Database setup

The repo includes `setup_database.py` which contains database initialization logic. Review it and run it against a test MySQL instance to initialize schema and sample data. Typical flow:

```powershell
python setup_database.py
```

If you already have a DB migration process, adapt the schema or run migrations accordingly. The tests expect the DB schema to be present.

## Run locally (development)

There are multiple entry points. The app factory lives in `app.py`. To run in development mode:

```powershell
python run.py
```

The server will listen on the port configured in `run.py` or default Flask port 5000.

## Testing

Tests use `pytest`. Run tests from the repo root with the venv active:

```powershell
python -m pytest -q
# or to run a single test file
python -m pytest tests/test_auth_routes.py::test_signup_success -q
```

If tests rely on a test database, ensure environment variables point to a disposable database or use mocking in tests. See `tests/conftest.py` for fixtures.

## Plate detection notes (OCR + detector)

The project contains a simple plate detector utility at `plate_detector.py`. Important notes:
- It uses OpenCV + pytesseract. Install system Tesseract (Windows: install Tesseract-OCR and ensure it's on PATH or install at `C:\Program Files\Tesseract-OCR\tesseract.exe`).
- The detector includes preprocessing (CLAHE, thresholding) and multiple OCR configurations. You can tune `min_confidence` near the top of `WorkingPlateDetector`.
- Model weights: some repos include a `models/` folder (e.g., `yolov8_lp.pt`) for YOLO-based detectors. This project also contains an OCR fallback in `plate_detector.py` and uses Tesseract.

If you rely on the plate detector in production, consider:
- running the model on a GPU-enabled environment
- collecting sample plates to tune regex/whitelist
- enabling debug mode to save candidate crops for offline analysis

## Key project files & routes (quick reference)

- `app.py`  app factory and Flask configuration
- `run.py`  app entry point used to start the server
- `routes/auth_routes.py`  signup, login, logout, owner linking
- `routes/appointment_routes.py`  appointment booking, search, update
- `routes/mechanic_routes.py`  mechanic dashboard APIs and admin features
- `templates/`  HTML templates (client and mechanic pages)
- `plate_detector.py`  OCR-based plate detector
- `utils/database.py`  DB helper functions
- `tests/`  pytest test suite

### Example endpoints you may call (non-exhaustive)

- `POST /signup`  create account + owner
- `POST /login`  login
- `GET /mechanic/dashboard`  mechanic dashboard (template)
- `GET /mechanic/api/dashboard-stats`  dashboard statistics (JSON, mechanic only)
- `GET /mechanic/api/recent-activity`  recent activities (supports `?limit=8&offset=0`)
- `POST /mechanic/api/complete-service`  complete a service (requires JSON body)
- `POST /book`  book appointment (client)

See the `routes/` folder for full endpoints and parameters.

## Developer guidance & style

- **Logging**: use the module `logger` (already used across code). Avoid `print()` in server code.
- **Database**: use parameterized queries (already present). Prefer `cursor(dictionary=True)` for readability when selecting named columns.
- **Sessions**: Flask `session` stores `logged_in`, `mechanic_logged_in`, and related user data. Clear session on logout.
- **Tests**: add fixtures in `tests/conftest.py` to mock DB connections or provide a test DB instance.

## Contributing

1. Fork the repo
2. Create a feature branch
3. Run tests locally and add tests for new behavior
4. Submit a PR with a clear description and CI passing

## Security & production notes

- Do not use the dev `APP_SECRET_KEY` in production. Use a strong secret and store it securely.
- Set `SESSION_COOKIE_SECURE=True` when deploying over HTTPS.
- Lock down DB credentials and consider read-only accounts for certain endpoints.
- Sanitize and validate all user inputs on both client and server sides.

## License

Add a license file if you plan to open-source this repository. No license is included by default.
