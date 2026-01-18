# Phase 1: Core Analysis Engine - Development Plan

**Branch:** `github-graphql`
**Focus:** Backend - GitHub data fetching, Real DB Storage, Behavioral Metrics
**Timeline:** Hackathon Mode (Fast Iteration)

---

## Objectives

1. ✅ Set up FastAPI backend in `server/` directory using **uv**
2. ✅ Configure SQLite database connection (`server/database.py`) using existing models
3. ✅ Build GitHub GraphQL client to fetch User, Repo, and Commit metadata
4. ✅ Implement Behavioral Metrics (Commit Density, Commit Size) using metadata only
5. ✅ Create `/analyze/{username}` endpoint to Orchestrate Fetch -> Analyze -> Store
6. ✅ Manual testing with `EricJujianZou`

**Out of Scope for Phase 1:**

- ❌ LLM/OpenAI integration
- ❌ File content analysis (grep, AST, dependency parsing)
- ❌ Frontend integration

---

## Project Structure

```
Anti-Soy/
├── server/                 # Root backend folder
│   ├── main.py             # FastAPI entry point
│   ├── models.py           # Existing SQLAlchemy models
│   ├── database.py         # NEW: DB connection & Session handling
│   ├── .env                # GitHub token
│   ├── requirements.txt    # Managed via uv
│   ├── routers/
│   │   ├── __init__.py
│   │   └── analysis.py     # Main analysis endpoint
│   ├── services/
│   │   ├── __init__.py
│   │   ├── github.py       # GitHub GraphQL Client
│   │   └── metrics.py      # Metric calculations (Behavioral only)
│   └── utils/
│       ├── __init__.py
│       └── helpers.py
├── docs/
│   └── phase1-plan.md
└── README.md
```

---

## Step-by-Step Development Plan

### **Step 1: Environment & Dependencies (15 min)**

**Tasks:**

1. Install **uv**: `pip install uv` (if not installed)
2. Initialize virtualenv: `uv venv`
3. Install dependencies:
   ```bash
   uv pip install "fastapi" "uvicorn[standard]" "httpx" "sqlalchemy" "python-dotenv" "pydantic"
   ```
4. Generate requirements: `uv pip freeze > requirements.txt`
5. Configure `.env`:
   ```env
   GITHUB_TOKEN=ghp_your_token_here
   DATABASE_URL=sqlite:///./antisoy.db
   ```

### **Step 2: Database Layer (30 min)**

Create `server/database.py` to handle the SQLite connection using `server/models.py`.

**Implementation Sketch:**

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Base

# Database URL
SQLALCHEMY_DATABASE_URL = "sqlite:///./antisoy.db"

# Engine
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)

# SessionLocal
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

### **Step 3: GitHub GraphQL Client (2 hours)**

Create `server/services/github.py`. We need a query that fetches:

- **User**: username, link, creation date.
- **Repos (Top 5)**: name, link, stars, is_fork (checking open source), languages, merged PR count (proxy via User query if possible, or omit for now).
- **Commits (Last 50-100)**: committedDate (for timing), additions/deletions (for size).

**GraphQL Strategy:**

- We cannot fetch "PRs merged" easily per repo in one nested query efficiently without complex pagination. We might skip `prs_merged` logic for Phase 1 or use a simpler "total PRs" proxy if available.
- **Languages**: Fetch as nodes, serialize to JSON string `["Python", "Rust"]`.

### **Step 4: Behavioral Metrics (1 hour)**

Create `server/services/metrics.py`. Focus only on what fits into `RepoData` and comes from metadata.

**Metrics to Implement:**

1.  **Commit Density (`RepoData.commit_density`)**
    - **Logic**: Analyze timestamps of commits.
    - **Calc**: Calculate variance of commits per day/hour.
    - **Output**: JSON `{"variance": 12.5, "score": 80, "interpretation": "Consistent"}`

2.  **Commit Lines / Quality (`RepoData.commit_lines`)**
    - **Logic**: Check for "massive commits" (>10k lines).
    - **Calc**: Avg lines per commit, count of massive commits.
    - **Output**: JSON `{"avg_size": 150, "massive_count": 0, "score": 95}`

**Note**: Other `RepoData` fields (`files_organized`, `dependencies`, etc.) will be stored as `null` or empty JSON for now.

### **Step 5: Main Logic & Endpoint (1.5 hours)**

Create `server/routers/analysis.py`.

**Endpoint logic (`POST /analyze/{username}`):**

1.  **Check DB**: existence check for valid recent analysis (Optional for hackathon, maybe always refresh).
2.  **Fetch**: Call `github_client.fetch_user_data(username)`.
3.  **Process User**:
    - Create/Update `User` object.
4.  **Process Repos**:
    - Iterate top 5 repos.
    - Calculate Metrics: `commit_density`, `commit_lines`.
    - Create/Update `Repo` object with `languages` (as string).
    - Create/Update `RepoData` object with calculated metrics.
5.  **Commit**: Save all to SQLite.
6.  **Return**: Full JSON response of stored data.

### **Step 6: Manual Testing (30 min)**

**Test Target**: `EricJujianZou`

**Procedure:**

1.  Run server: `uvicorn main:app --reload`
2.  Use Postman or Curl:
    ```bash
    curl -X POST http://localhost:8000/analyze/EricJujianZou
    ```
3.  Verify:
    - Console logs show GraphQL fetching.
    - `antisoy.db` file is created.
    - Response contains metric JSONs.
    - "languages" is saved as specific text format.

---

## Integration Notes

- **Language Field**: Stored as `Text`. We will format it as a JSON string: `"['Python', 'TypeScript']"`.
- **RepoData Fields**: Only `commit_density` and `commit_lines` will be populated in Phase 1. `files_organized`, `api_keys`, etc. will be `null`.
