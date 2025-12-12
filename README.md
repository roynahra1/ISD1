# ISD-v1.0

Mechanic / Appointment management web application (Flask).

[![codecov](https://codecov.io/gh/roynahra1/ISD1/branch/main/graph/badge.svg)](https://codecov.io/gh/roynahra1/ISD1)

This README now includes a detailed developer guide and a quick-reference layout inspired by an "AI CV Builder" README: clear Requirements, Backend (FastAPI) and Frontend (React) setup, LLM (Ollama) notes, testing and CI pointers, and PDF/template info.

---

## Quick summary

To run locally (developer flow):

1. Install system prerequisites (Node, Python, Git, Ollama if using AI features).
2. Create a Python venv inside `backend/`, install deps, create `.env`.
3. Run `python setup_database.py` (or migrations) to initialize DB.
4. Start backend: `python run.py` (or `uvicorn app.main:app --reload --port 8000`).
5. Install frontend deps from project root and start React dev server: `npm install` then `npm start`.

Detailed sections follow.

---

## 1. Requirements

Make sure these are installed on the machine:

- Node.js  18 and npm
- Python  3.10
- Git
- Ollama (for the AI features; optional but required for LLM analysis)

No external DB server required; SQLite is used by default.

---

## 2. Clone the repository

```bash
git clone https://github.com/your-org/your-repo.git
cd your-repo
```

Project layout (example):

```
backend/        # FastAPI app
src/            # React frontend (Create React App)
package.json    # top-level frontend/npm config
README.md
```

---

## 3. Backend setup (FastAPI)

3.1 Create and activate virtual environment

```powershell
cd backend
python -m venv .venv
# Windows
.\.venv\Scripts\Activate.ps1
# macOS / Linux
# source .venv/bin/activate
```

3.2 Install Python dependencies

```powershell
pip install -r requirements.txt
```

3.3 Environment variables

Create `backend/.env` with values similar to:

```env
# FastAPI
SECRET_KEY=change_me_to_a_random_long_string
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60

# SQLite
DATABASE_URL=sqlite:///./app.db

# CORS / frontend URL
FRONTEND_ORIGIN=http://localhost:3000

# Ollama / LLM (optional)
OLLAMA_URL=http://localhost:11434
OLLAMA_MODEL=llama3

# Google OAuth (optional)
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
```

3.4 Initialize / migrate the database

If the project provides a migration script (e.g. `migrate_db.py`), run it:

```powershell
python migrate_db.py
```

Otherwise, the SQLite file will usually be created on first run or when the app initializes the schema.

3.5 Start the backend server

```powershell
uvicorn app.main:app --reload --port 8000
```

API base URL: `http://localhost:8000`
Swagger UI: `http://localhost:8000/docs`

---

## 4. LLM setup (Ollama)

Ollama provides a local LLM service used by the app for CV analysis/polishing.

1. Install Ollama using official instructions: https://ollama.com
2. Ensure Ollama daemon is running (default API: `http://localhost:11434`).
3. Pull the model used in `.env`:

```bash
ollama pull llama3
```

If Ollama is not running or the model is missing, AI analysis endpoints should gracefully fall back (app should handle 502s or errors and use a non-LLM analysis path).

---

## 5. Frontend setup (React)

From the project root (not inside `backend/`):

```bash
npm install
```

5.1 Frontend environment variables

Create a `.env` in the project root with at least:

```
REACT_APP_API_BASE=http://localhost:8000
```

5.2 Run the React dev server

```bash
npm start
```

Open: `http://localhost:3000`

User flows:
- Fill personal info, education, experience, skills, etc.
- Optionally sign in (email or Google OAuth if configured).
- Use Analyze (AI) to get automatic feedback (requires Ollama).
- Download PDF via the provided templates.

---

## 6. Running tests & coverage

### Frontend

```bash
npm test
```

### Backend

From `backend/` with the venv activated:

```powershell
pytest
# or with coverage
pytest --cov=app
```

CI (GitHub Actions) should run tests and publish coverage to Codecov.

---

## 7. PDF templates & generation

The backend typically contains modules like:

- `pdf_logic.py`  prepares CV data and integrates with the LLM for suggestions
- `pdf_templates.py`  template definitions (e.g. `default`, `modern_blue`, `linkedin`)
- `pdf_generation.py`  endpoint that receives CV JSON and returns a generated PDF

To switch templates, update the template parameter in the frontend or the backend endpoint call (e.g. pass `template: "modern_blue"`).

---

## 8. CI & Codecov

Add a GitHub Actions workflow to run tests on push and PRs. Example responsibilities:
- Install Python and Node
- Run backend and frontend tests
- Upload coverage to Codecov

Badge (example):

```
[![codecov](https://codecov.io/gh/your-org/your-repo/branch/main/graph/badge.svg)](https://codecov.io/gh/your-org/your-repo)
```

---

## 9. Quick troubleshooting

- LLM analysis failing (502): ensure Ollama is running and the model is pulled.
- Tests failing due to DB: reset `app.db` or run migration script and ensure `.env` points to the correct DB.
- OAuth issues: verify redirect URIs in provider console (Google) and matching client secrets in `.env`.

---

## 10. Quick commands

```powershell
# Backend venv creation
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python migrate_db.py   # optional
uvicorn app.main:app --reload --port 8000

# Frontend
cd ..
npm install
npm start

# Tests
# Backend
python -m pytest -q
# Frontend
npm test
```

---

If you want, I will:
- add a `.env.example` file to the repo,
- add a `backend/migrate_db.py` template (if migrations are missing),
- create a GitHub Actions workflow that runs tests and posts coverage to Codecov,
- add sample curl/Postman examples for the main API endpoints.

Please tell me which follow-up tasks you'd like me to do next.
