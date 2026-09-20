# Synapse — Run Guide

This document explains how to set up, configure, run, test, and troubleshoot the Synapse project locally.

## 1. Prerequisites

Install:

- Python 3.11+ (or the version required by the repository)
- Node.js 18+ and npm (or the package manager already used by the project)
- Git
- SQLite 3

Verify:

```bash
python --version
node --version
npm --version
sqlite3 --version
```

Python normally includes SQLite support. Verify it with:

```bash
python -c "import sqlite3; print(sqlite3.sqlite_version)"
```

## 2. Get the Project

Clone the repository:

```bash
git clone <YOUR_REPOSITORY_URL>
cd <PROJECT_DIRECTORY>
```

If the project is already downloaded, open a terminal in the project root.

The root should contain the project's actual files, including `Contracts.md`, `slice/`, `synapse/`, tests, frontend files, and environment/dependency configuration.

## 3. Create the Python Environment

### Windows

```bash
python -m venv .venv
.venv\Scripts\activate
```

### macOS/Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Upgrade pip:

```bash
python -m pip install --upgrade pip
```

If the project uses `requirements.txt`:

```bash
pip install -r requirements.txt
```

Otherwise use the dependency manager already configured by the repository.

## 4. Install Frontend Dependencies

If the frontend is in `frontend/`:

```bash
cd frontend
npm install
cd ..
```

If the frontend is in the repository root:

```bash
npm install
```

Use the package manager already used by the repository if it is not npm.

## 5. Environment Configuration

Create the local environment file:

```bash
cp .env.example .env
```

Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

Never commit `.env`.

Configure the AI provider using the variables documented in `.env.example`.

For OpenAI, the configuration is conceptually:

```text
SLICE_PROVIDER=openai
OPENAI_API_KEY=<your-api-key>
OPENAI_MODEL=<configured-model>
```

Use the exact variable names and model supported by the current project.

Important:

- Never put an API key in frontend code.
- Never commit `.env`.
- Never log API keys.
- Never return API keys from an API.
- Only `slice/config.py` should read environment variables.
- Model calls must go through `slice/llm.py`.

## 6. SQLite Database

Synapse uses SQLite through the project's persistence layer.

The application database must be accessed through:

```text
slice/store.py
```

Do not add direct SQLite access to the frontend, API routes, agents, or runtime modules.

Verify SQLite:

```bash
python -c "import sqlite3; print('SQLite OK:', sqlite3.sqlite_version)"
```

If the repository provides an initialization or migration command, use that existing command.

Do not delete/reset the existing database unless explicitly required.

Do not commit a database containing real credentials or personal data.

## 7. Start the Backend

Use the backend entrypoint already defined by the repository.

For a Uvicorn/FastAPI project, it will commonly look like:

```bash
uvicorn <module>:<app> --reload
```

Replace `<module>:<app>` with the actual entrypoint used by this project. Do not invent a new entrypoint.

Check the terminal output for the actual backend URL and port.

## 8. Start the Frontend

Open a second terminal.

If the frontend is in `frontend/`:

```bash
cd frontend
npm run dev
```

If it is in the project root:

```bash
npm run dev
```

Open the URL printed by the development server.

## 9. Application Flow

The intended flow is:

```text
SYNAPSE
  ↓
Get Started
  ↓
Portal Selection
  ├── Student
  └── Teacher
        ↓
Sign In / Create Account
        ↓
Authenticated Portal
```

Protected Student and Teacher pages require authentication.

## 10. Registration and Login

Create Student or Teacher accounts through the application.

Registration must persist through:

```text
API
 ↓
auth/service
 ↓
slice/store.py
 ↓
SQLite
```

Passwords must be securely hashed and never stored as plaintext.

Login with the registered username/email and password.

Invalid credentials should display:

```text
Invalid username or password.
```

They should not display a 404 page.

The password eye icon toggles the password between hidden and visible states.

## 11. Student ↔ Teacher Connection

Students no longer join using a Classroom ID.

Use the current teacher connection mechanism.

Conceptually:

```text
Teacher
  ↓
Teacher connection mechanism
  ↓
Student connects
  ↓
Persisted teacher ↔ student relationship
  ↓
Teacher sees connected student
```

The relationship is persisted through `slice/store.py`.

## 12. Student Learning and AI Pipeline

The existing Synapse learning flow is:

```text
Student
  ↓
Test / Learning Activity
  ↓
Submit Attempt
  ↓
ATTEMPT_RECEIVED
  ↓
DIAGNOSING
  ↓
AI Diagnosis / Analysis
  ↓
TAILORING
  ↓
AI Note Tailoring
  ↓
REVIEWING
  ↓
NOTE_SAVED
  ↓
ANALYSING
  ↓
AGGREGATING
  ↓
COMPLETE
```

The AI architecture is:

```text
Student submits test
       ↓
Diagnosis Agent
       ↓
slice/llm.py
       ↓
Configured AI Provider
       ↓
Structured Analysis
       ↓
slice/store.py
       ↓
       ├── Teacher performance/analysis
       │
       └── Note Tailoring Agent
                    ↓
               Tailored Notes
                    ↓
                  Student
```

All model requests must go through `slice/llm.py`.

## 13. Teacher Performance

Teachers can view connected students.

Teacher performance information should come from backend/persisted data, including whatever the current analytics system supports, such as:

- test/attempt results
- AI analysis
- mastery
- trends
- learning progress

A teacher must only be able to access students connected to that teacher.

## 14. Run Tests

From the project root:

```bash
pytest
```

Run frontend tests using the command configured in `package.json`, for example:

```bash
npm test
```

Also run the repository's configured:

- type checks
- linting
- architecture/import checks
- provider/LLM tests
- authentication tests
- database/store tests
- runtime tests
- API tests

Do not invent test commands when the repository already defines them.

## 15. Real AI Smoke Test

Only run a real AI request when a valid API key is configured.

Use synthetic/test data.

Verify:

```text
Student submits test
 ↓
Diagnosis Agent
 ↓
slice/llm.py
 ↓
AI Provider
 ↓
Real structured analysis
 ↓
Analysis persisted
 ↓
Teacher can view analysis
 ↓
Note Tailoring Agent
 ↓
Tailored notes
 ↓
Student can view notes
```

Never expose the API key.

## 16. Troubleshooting

### Login says "Invalid username or password" for a known account

Check:

1. Login and registration use the same SQLite database.
2. The account exists in that database.
3. Username/email lookup matches the registered identifier.
4. Password hash verification is compatible with existing accounts.
5. The backend is not accidentally using an empty/new database.
6. Session/token creation succeeds.

Do not delete the database as a first fix.

### Registration returns 404

Check:

1. Frontend registration URL.
2. Backend registration route.
3. Router prefix.
4. HTTP method.
5. Router mounting.
6. Frontend API base URL and backend port.

### AI request fails

Check:

1. Selected provider.
2. Required API key.
3. Configured model name.
4. Backend was restarted after environment changes.
5. API key is valid.
6. Request goes through `slice/llm.py`.
7. Budget has not been exhausted.

### Protected page opens while logged out

Check the frontend authentication guard and backend authorization. Do not rely only on hiding navigation links.

### Student does not appear for teacher

Check:

1. Both accounts exist.
2. The teacher/student relationship was created.
3. The relationship was persisted in SQLite.
4. The correct teacher is authenticated.
5. The teacher API verifies the relationship.
6. The frontend calls the correct API.

## 17. Security

Never commit:

- `.env`
- API keys
- passwords
- real password hashes
- authentication tokens
- real student data
- real teacher data
- sensitive local databases

Use synthetic test accounts for development.

Do not reset the database merely to solve authentication problems.

## 18. Recommended Development Terminals

### Terminal 1 — Backend

```bash
# activate the virtual environment
# Windows:
.venv\Scripts\activate

# macOS/Linux:
source .venv/bin/activate

# start using the repository's actual backend entrypoint
uvicorn <actual-backend-entrypoint> --reload
```

### Terminal 2 — Frontend

```bash
cd frontend
npm run dev
```

Adjust the frontend directory if the repository uses a different location.

### Terminal 3 — Tests

```bash
# activate the virtual environment first
pytest
```

## 19. Shutdown

Stop development servers with:

```text
Ctrl+C
```

Do not delete the SQLite database to stop the application.

## 20. Quick Start

For an already-configured development machine:

```bash
# Terminal 1
# activate .venv, then start the project's backend
uvicorn <actual-backend-entrypoint> --reload

# Terminal 2
cd frontend
npm run dev
```

Then:

1. Open the frontend URL printed by the dev server.
2. Click Get Started.
3. Choose Student or Teacher.
4. Register or sign in.
5. Use the selected portal.
6. Students connect using the current teacher connection mechanism.
7. Teachers can view connected students and available performance analysis.
8. Run a student test to exercise the AI diagnosis and note-tailoring pipeline.

## 21. Source of Truth

If this guide conflicts with the implementation, check the repository's actual:

- `Contracts.md`
- `README.md`
- `.env.example`
- `package.json`
- Python dependency configuration
- backend entrypoint
- frontend configuration
- scripts
- tests

Keep this `run.md` updated whenever the actual setup or run commands change.
