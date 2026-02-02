# Anti-Soy Developer Guide

Quick reference for local development, testing, and deployment.

---

## Local Development

### Prerequisites

- **Python 3.10+** (backend)
- **Node.js 18+** and **bun** (frontend)
- **Git** (for cloning repos during analysis)
- **Google Cloud SDK** (optional, for deployment)

---

### Backend (FastAPI)

#### Using uv (Recommended)

[uv](https://github.com/astral-sh/uv) is a fast Python package manager written in Rust.

```bash
cd server

# Install uv (if not installed)
# Windows PowerShell:
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
# macOS/Linux:
curl -LsSf https://astral.sh/uv/install.sh | sh

# Create virtual environment and install dependencies (one command)
uv sync

# Activate virtual environment
# Windows PowerShell:
.venv\Scripts\Activate.ps1
# macOS/Linux:
source .venv/bin/activate

# Run development server
uvicorn main:app --reload --port 8000
```

#### Using pip (Alternative)

```bash
cd server

# Create virtual environment (first time)
python -m venv venv

# Activate virtual environment
# Windows PowerShell:
.\venv\Scripts\Activate.ps1
# Windows CMD:
.\venv\Scripts\activate.bat
# macOS/Linux:
source venv/bin/activate

# Install dependencies in editable mode (-e = editable, changes reflect immediately)
pip install -e .
# Or install manually:
pip install fastapi[standard] google-genai pydantic python-dotenv requests sqlalchemy

# Run development server
uvicorn main:app --reload --port 8000
```

**API will be available at:** `http://localhost:8000`

**API docs (Swagger):** `http://localhost:8000/docs`

---

### Frontend (Vite + React)

```bash
cd client


# Or with npm:
npm install

# Create .env file for local development
# .env.local:
#   VITE_API_BASE_URL=http://localhost:8000

# Or with npm:
npm run dev
```

**Frontend will be available at:** `http://localhost:8080`

---

### Running Both Together

**Terminal 1 (Backend):**

```bash
cd server
.\venv\Scripts\Activate.ps1
uvicorn main:app --reload --port 8000
```

**Terminal 2 (Frontend):**

```bash
cd client
bun dev
```

---

## Testing

### Backend Tests

```bash
cd server

# Run all tests
pytest

# Run specific test file
pytest test_api.py

# Run with verbose output
pytest -v
```

### Frontend Tests

```bash
cd client

# Run tests once
bun test
# Or:
npm run test

# Run tests in watch mode
bun test:watch
# Or:
npm run test:watch
```

### Manual Data Extractor Test

```bash
cd server
python -c "
from v2.data_extractor import extract_repo_data, clone_repository
from pathlib import Path
import tempfile

with tempfile.TemporaryDirectory() as tmp:
    clone_repository('https://github.com/OWNER/REPO', Path(tmp))
    data = extract_repo_data(tmp)
    print(f'Files: {len(data.files)}')
    print(f'Commits: {len(data.commits)}')
    print(f'LOC: {data.total_loc}')
"
```

---

## Deployment

### Architecture

- **Backend:** Google Cloud Run (serverless container)
- **Frontend:** GitHub Pages (static hosting)
- **CI/CD:** Google Cloud Build (triggered on push to master)

### How Cloud Build Works

When you push to `master`, Google Cloud Build automatically:

1. **Builds** the Docker image from `server/Dockerfile`
2. **Pushes** the image to Google Container Registry (`gcr.io/$PROJECT_ID/anti-soy-backend`)
3. **Deploys** to Cloud Run in `us-east4` region

This is configured in `server/cloudbuild.yaml`:

```yaml
steps:
  # Build Docker image
  - name: "gcr.io/cloud-builders/docker"
    args:
      ["build", "-t", "gcr.io/$PROJECT_ID/anti-soy-backend:$COMMIT_SHA", "."]

  # Push to Container Registry
  - name: "gcr.io/cloud-builders/docker"
    args: ["push", "gcr.io/$PROJECT_ID/anti-soy-backend:$COMMIT_SHA"]

  # Deploy to Cloud Run
  - name: "gcr.io/cloud-builders/gcloud"
    args:
      - "run"
      - "deploy"
      - "anti-soy-backend"
      - "--image"
      - "gcr.io/$PROJECT_ID/anti-soy-backend:$COMMIT_SHA"
      - "--region"
      - "us-east4"
      - "--platform"
      - "managed"
      - "--allow-unauthenticated"
```

### Dockerfile Overview

The backend Dockerfile (`server/Dockerfile`):

```dockerfile
FROM python:3.11-slim

# Install git (needed for cloning repos during analysis)
RUN apt-get update && apt-get install -y --no-install-recommends git

# Install Python dependencies
RUN pip install fastapi[standard] google-genai pydantic python-dotenv requests sqlalchemy

# Copy application code
COPY . .

# Run uvicorn on port 8080 (Cloud Run default)
CMD uvicorn main:app --host 0.0.0.0 --port $PORT
```

**Key points:**

- Uses `python:3.11-slim` for smaller image size
- Installs `git` because the analyzer clones repos
- Exposes port 8080 (Cloud Run requirement)
- `$PORT` is set by Cloud Run at runtime

### Manual Deployment (if needed)

```bash
cd server

# Build and push manually
gcloud builds submit --config cloudbuild.yaml

# Or deploy directly
gcloud run deploy anti-soy-backend \
  --source . \
  --region us-east4 \
  --allow-unauthenticated
```

### Deploy Frontend to GitHub Pages

```bash
cd client

# Build and deploy
bun run deploy
# Or:
npm run deploy
```

---

## Environment Variables

### Backend (`server/.env`)

| Variable         | Required | Description                           |
| ---------------- | -------- | ------------------------------------- |
| `GEMINI_API_KEY` | Yes      | Google Gemini API key for LLM calls   |
| `GITHUB_TOKEN`   | Yes      | GitHub PAT for fetching repo metadata |

### Frontend (`client/.env.local`)

| Variable            | Required | Description                                           |
| ------------------- | -------- | ----------------------------------------------------- |
| `VITE_API_BASE_URL` | Yes      | Backend URL (e.g., `http://localhost:8000` for local) |

---

## Useful Commands

| Task                | Command                                 |
| ------------------- | --------------------------------------- |
| Backend dev server  | `uvicorn main:app --reload --port 8000` |
| Frontend dev server | `bun dev`                               |
| Run backend tests   | `pytest`                                |
| Run frontend tests  | `bun test`                              |
| Build frontend      | `bun run build`                         |
| Deploy frontend     | `bun run deploy`                        |
| Trigger Cloud Build | `git push origin master`                |
