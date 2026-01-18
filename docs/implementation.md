# Anti-Soy: Technical Implementation Guide

Technical reference for implementing the Anti-Soy candidate analysis platform.

---

## Table of Contents

1. [System Architecture](#system-architecture)
2. [Technical Stack](#technical-stack)
3. [Analysis Pipeline](#analysis-pipeline)
4. [Detection Implementation](#detection-implementation)
5. [API Design](#api-design)
6. [Data Models](#data-models)

---

## System Architecture

### System Overview

```
┌─────────────────────────────────────────────────────┐
│  FRONTEND (React)                                   │
│  ├─ Bulk Upload Interface                          │
│  │   └─ Upload CSV with GitHub usernames           │
│  ├─ Profile Preloading (Scan 100 profiles)         │
│  ├─ Analysis Progress Tracker                      │
│  └─ Dashboard (Charts, Scores, Insights)            │
│      ├─ Ranked Candidate List                      │
│      ├─ Overall Skill Score (0-100)                │
│      ├─ AI Detection Percentage                     │
│      ├─ Category Breakdowns (Radar Chart)           │
│      ├─ Red Flags & Strengths Lists                │
│      └─ Recommended Interview Questions             │
└─────────────────────────────────────────────────────┘
                        ↓ HTTP POST /analyze/batch
┌─────────────────────────────────────────────────────┐
│  BACKEND (FastAPI + Python)                         │
│  ├─ /analyze/batch endpoint                        │
│  ├─ Database (SQLAlchemy + SQLite)                 │
│  ├─ GitHub GraphQL Client                           │
│  └─ Analysis Pipeline:                              │
│      ├─ Behavioral Pattern Analyzer                │
│      │   └─ Refactoring ratio, commit patterns      │
│      ├─ AI Text Detector (OpenAI/Claude API)       │
│      │   └─ Commit messages, PR descriptions        │
│      ├─ Code Quality Analyzer                       │
│      │   ├─ Radon (Python complexity)               │
│      │   ├─ ESLint (JS/TS complexity)               │
│      │   └─ AST parsing (error handling)            │
│      ├─ Security Analyzer                           │
│      │   └─ TruffleHog (API key detection)          │
│      ├─ Dependency Analyzer                         │
│      │   └─ package.json/requirements.txt parsing   │
│      ├─ Project Authenticity Checker                │
│      │   └─ LLM-based tutorial project detection    │
│      └─ Composite Scoring Algorithm                 │
│          └─ Weighted metrics → final score          │
└─────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────┐
│  EXTERNAL APIS                                      │
│  ├─ GitHub GraphQL API                              │
│  │   └─ Fetch repos, commits, code, metadata        │
│  └─ OpenAI/Claude API                               │
│      ├─ AI text detection (commit messages)         │
│      ├─ Project authenticity assessment             │
│      └─ Company alignment evaluation                │
└─────────────────────────────────────────────────────┘
```

### Data Flow

1. User uploads CSV with 100 GitHub usernames (or scans profiles)
2. Backend creates batch job, stores in database
3. For each username:
   - Check database for existing analysis
   - If not analyzed, fetch user data via GitHub GraphQL
   - Run parallel analysis across all metrics
   - Store results in database via SQLAlchemy
4. Frontend polls for progress, displays real-time updates
5. Once complete, frontend renders ranked dashboard with all candidates

---

## Technical Stack

### Backend

**Core Framework:**

- Python 3.11+
- FastAPI (async API server)
- SQLAlchemy (ORM)
- SQLite (database - local development)

**AI/ML:**

- OpenAI API (GPT-4o-mini for AI text detection & project analysis)
- Anthropic Claude API (alternative/fallback)
- Custom heuristics (behavioral pattern analysis)

**Code Analysis Tools:**

- Radon (Python complexity analysis)
- ESLint (JavaScript/TypeScript analysis via subprocess)
- TruffleHog (secret/API key detection)
- AST parsing: Python `ast` module
- Dependency analysis: Direct JSON parsing (package.json, requirements.txt)

**Data Collection:**

- GitHub GraphQL API (fetch repos, commits, code, PRs)
- GitHub REST API (fallback for specific endpoints)
- Rate limiting: 5000 req/hr with GraphQL

### Frontend

**Core Framework:**

- React 18+ (JavaScript)
- Standard CSS or TailwindCSS (styling)
- Chart.js or Recharts (data visualization)

**State Management:**

- React hooks (useState, useEffect)
- Context API (optional for global state)

### Infrastructure

**Local Development Only:**

- No deployment required (hackathon project)
- No CI/CD pipeline
- No monitoring/logging infrastructure
- Run locally: `uvicorn main:app --reload`

---

## Analysis Pipeline

### 1. Bulk Input Processing

```
Input: CSV file with GitHub usernames or list of 100 profiles
↓
Parse CSV, extract usernames
↓
Create batch analysis job in database
↓
For each username:
  - Check if already analyzed (query database)
  - If not, add to analysis queue
↓
Output: Batch job ID, queue of usernames to analyze
```

**Implementation:**

- Accept CSV upload via React frontend
- FastAPI endpoint: POST /analyze/batch
- Store job in SQLite via SQLAlchemy
- Return job ID for progress tracking

### 2. Repository Discovery

```
Input: GitHub username
↓
Fetch user's public repositories via GraphQL
↓
Filter: >500 LOC, updated in last 2 years
↓
Identify primary languages per repo
↓
Output: List of significant repositories
```

**Implementation:**

- Use GitHub GraphQL API to fetch all repos in single query
- Filter client-side to avoid multiple API calls
- Prioritize repos with: stars, forks, recent commits

### 2. Code Extraction

```
Input: Repository list
↓
For each repo:
  - Fetch file structure
  - Identify entry points (main.py, index.js, etc.)
  - Extract package manifests (package.json, requirements.txt)
  - Sample key files (avoid fetching entire codebase)
↓
Output: Code samples + metadata
```

**Optimization:**

- Don't clone repos - use GitHub API to fetch specific files
- Sample 5-10 key files per repo (main logic, API routes, models)
- Cache file contents to avoid re-fetching

### 3. Static Analysis

```
Input: Code samples
↓
Run parallel analysis:
  - Complexity metrics (Radon, ESLint)
  - Dependency counting (parse package.json)
  - Error handling detection (AST parsing)
  - Comment analysis (regex + density calculation)
↓
Output: Numeric metrics per file/repo
```

**Tools:**

- Radon: `pip install radon` → `radon cc <file>` for complexity
- ESLint: Use programmatically via Node.js API
- AST parsing: Python `ast` module, Esprima for JS

### 4. AI Analysis

```
Input: Commit messages, code comments, PR descriptions
↓
For each text sample:
  - Run through AI detector (roberta-base-openai-detector)
  - Calculate formal language score (heuristics)
  - Check for personal voice indicators
↓
Aggregate scores
↓
Output: AI percentage (0-100%)
```

**AI Detector:**

- Model: `roberta-base-openai-detector` from Hugging Face
- Input: Text string (max 512 tokens)
- Output: Probability (0-1) that text is AI-generated

**Heuristics:**

- Formal words: "utilized", "implemented", "comprehensive"
- Personal words: "whoops", "forgot", "my bad"
- Length consistency: High variance = human

### 5. Scoring Algorithm

```
Input: All metrics from previous stages
↓
Calculate category scores:
  - Behavioral patterns (0-100)
  - Code quality (0-100)
  - AI dependency (0-100, inverted)
  - Documentation (0-100)
  - Community (0-100)
↓
Weighted composite:
  vibe_score = (
    behavioral * 0.4 +
    ai_dependency * 0.3 +
    code_quality * 0.15 +
    documentation * 0.1 +
    community * 0.05
  )
↓
Output: Overall score + category breakdowns
```

**Weighting Rationale:**

- Behavioral patterns (40%): Hardest to fake, strongest signal
- AI dependency (30%): Core differentiation
- Code quality (15%): Important but can be AI-generated
- Documentation (10%): Nice-to-have
- Community (5%): Bonus points

### 6. Insight Generation

```
Input: Scores + raw data
↓
Identify top 3 strengths (highest scoring areas)
Identify top 3 red flags (lowest scoring areas)
↓
Generate interview questions:
  - If low error handling: "Walk me through how you handle errors in your projects"
  - If high AI dependency: "Explain the architecture decisions in [specific project]"
  - If dependency bloat: "Why did you choose these specific libraries?"
  - If tutorial clone: "What unique challenges did you solve in [project]?"
  - If security issues: "How do you manage API keys and secrets?"
  - If print statements: "Tell me about your logging strategy"
↓
Output: Actionable insights for recruiters
```

**Additional Checks:**

**Open Source Contributions:**

- Query GitHub API for user's PRs across all repos
- Calculate PR merge rate (merged / total submitted)
- Identify communities: Organizations user contributes to
- Contribution quality: Bug fixes vs features vs docs

**Technological Agility:**

- Count languages with >500 LOC projects
- Identify nuanced/advanced languages: Rust, Go, Scala, Elixir (vs just JS/Python)
- Framework diversity: React, Vue, Django, FastAPI, etc.
- Bonus for systems programming, low-level languages

---

## Detection Implementation

### Behavioral Pattern Analysis

**Refactoring Ratio:**

```
For each repository:
  commitsQuality Analysis:**

```

For each commit:

# Check for massive commits (red flag)

if commit.additions + commit.deletions > 10000:
massive_commit_count += 1

# Calculate commit density

total_lines_changed += commit.additions + commit.deletions

commit_density = total_lines_changed / total_commits

# Score interpretation

if massive_commit_count > total_commits \* 0.1:

# More than 10% massive commits = red flag

score = 30
elif commit_density < 100:

# Small, focused commits = good

score = 90
else:
score = 60

```

**Commit Timing Clustering:**

```

commit_timestamps = [extract timestamps from all commits]

# Group by day

commits_by_day = group_by_day(commit_timestamps)

# Calculate variance

time_variance = variance(commits_by_day)

Score:
High variance (sInfrastructure

1. FastAPI setup with SQLAlchemy
2. GitHub GraphQL client implementation
3. Database models and migrations
4. CSV upload endpoint

### Phase 2: Basic Metrics

1. Behavioral pattern detection (refactoring ratio, commit timing)
2. Dependency counting
3. File organization check
4. Basic scoring algorithm

### Phase 3: Advanced Analysis

1. OpenAI API integration for AI text detection
2. TruffleHog for security scanning
3. Project authenticity checking
4. Vibe coding indicators (emojis, print statements)

### Phase 4: Comprehensive Metrics

1. Error handling analysis
2. Scalability detection
3. Comment quality assessment
4. Open source contribution analysis
5. Technological agility scoring

### Phase 5: Frontend Dashboard

1. React UI for CSV upload
2. Progress tracking display
3. Results dashboard with rankings
4. Charts and visualizations (Chart.js)

### Phase 6: Polish

1. Batch processing optimization
2. Error handling and retry logic
3. Database query optimization
4. Final scoring algorithm tun Error Handling:\*\*

```python
import ast

def analyze_error_handling(python_code):
    tree = ast.parse(python_code)

    # Count try/except blocks
    try_blocks = [n for n in ast.walk(tree) if isinstance(n, ast.Try)]

    # Check for retry logic
    has_retry = any("retry" in ast.get_source_segment(python_code, n)
                    for n in ast.walk(tree) if isinstance(n, ast.FunctionDef))

    # Count logging calls vs print statements
    logging_calls = sum(1 for n in ast.walk(tree)
                       if isinstance(n, ast.Call) and
                       hasattr(n.func, 'attr') and
                       'log' in n.func.attr.lower())

    print_calls = sum(1 for n in ast.walk(tree)
                     if isinstance(n, ast.Call) and
                     hasattr(n.func, 'id') and
                     n.func.id == 'print')

    return {
        "try_catch_count": len(try_blocks),
        "has_retry_logic": has_retry,
        "logging_calls": logging_calls,
        "print_calls": print_calls,
        "vibe_coder_indicator": print_calls > logging_calls  # Red flag
    }
```

### Vibe Coding Indicators

**AI Comment Detection:**

```python
import re

def detect_vibe_coding(code):
    # Check for emojis in code/comments
    emoji_pattern = re.compile("[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF\U0001F1E0-\U0001F1FF]")
    emoji_count = len(emoji_pattern.findall(code))

    # Check for AI-style comments
    ai_comment_patterns = [
        r"# .*function to.*",
        r"# .*This (class|method|function).*",
        r"// .*Returns.*when.*",
    ]
    ai_comment_count = sum(len(re.findall(p, code, re.IGNORECASE)) for p in ai_comment_patterns)

    # Print vs logging
    print_count = len(re.findall(r'\bprint\s*\(', code))
    logging_count = len(re.findall(r'logging\.(debug|info|warning|error)', code))

    return {
        "emoji_count": emoji_count,
        "ai_comment_count": ai_comment_count,
        "print_vs_logging_ratio": print_count / max(logging_count, 1),
        "vibe_coder_score": min(100, emoji_count * 10 + ai_comment_count * 5 + (print_count / max(logging_count, 1)) * 20)
    }
```

### Project Authenticity Check

**Top 10 Tutorial Projects:**

```python
TUTORIAL_PROJECTS = [
    "todo app", "todo list", "todolist",
    "weather app", "weather api",
    "blog", "personal blog",
    "calculator",
    "portfolio", "portfolio website",
    "chat app", "real-time chat",
    "e-commerce", "shopping cart",
    "url shortener",
    "note taking app",
    "expense tracker"
]

def check_tutorial_project(repo_name, description, readme):
    repo_text = f"{repo_name} {description} {readme}".lower()

    for tutorial in TUTORIAL_PROJECTS:
        if tutorial in repo_text:
            return {
                "is_tutorial": True,
                "tutorial_type": tutorial,
                "authenticity_score": 20  # Low score for tutorials
            }

    return {
        "is_tutorial": False,
        "tutorial_type": None,
        "authenticity_score": 80  # Higher base score for non-tutorials
    }
```

### Comment Quality Analysis

```python
import random

def analyze_comment_quality(functions, code):
    # Sample 3 random functions
    sampled = random.sample(functions, min(3, len(functions)))

    scores = []
    for func in sampled:
        func_code = extract_function_code(func, code)
        comments = extract_comments(func_code)

        # Check if comments explain "why" not "what"
        why_indicators = ["because", "to handle", "for performance", "due to"]
        has_why = any(ind in comment.lower() for comment in comments for ind in why_indicators)

        # Calculate comment quality
        if len(comments) == 0:
            score = 0  # No comments
        elif has_why:
            score = 100  # Explains reasoning
        else:
            score = 50  # Just describes what

        scores.append(score)

    return sum(scores) / len(scores) if scores else 0
```

### Scalability Detection

```python
def analyze_scalability(code, repo_files):
    # Check for concurrency patterns
    concurrency_keywords = ["async", "await", "threading", "multiprocessing", "concurrent"]
    has_concurrency = any(keyword in code for keyword in concurrency_keywords)

    # Check for caching
    caching_keywords = ["@cache", "@lru_cache", "redis", "memcached", "cache.set"]
    has_caching = any(keyword in code for keyword in caching_keywords)

    # Check for database pooling
    pooling_keywords = ["create_engine(.*pool", "connection pool", "pool_size"]
    has_pooling = any(re.search(keyword, code) for keyword in pooling_keywords)

    scalability_score = (
        (50 if has_concurrency else 0) +
        (30 if has_caching else 0) +
        (20 if has_pooling else 0)
    )

    return {
        "has_concurrency": has_concurrency,
        "has_caching": has_caching,
        "has_pooling": has_pooling,
        "scalability_score": scalability_score
    }
```

### Open Source Contribution Analysis

```python
def analyze_open_source(username, github_client):
    # Query GitHub for user's PRs
    query = """
    {
      user(login: "%s") {
        pullRequests(first: 100, states: [MERGED, OPEN]) {
          nodes {
            state
            repository {
              owner {
                login
              }
              name
            }
          }
        }
        repositoriesContributedTo(first: 50) {
          nodes {
            owner {
              login
            }
            name
          }
        }
      }
    }
    """ % username

    result = github_client.execute(query)

    prs = result['user']['pullRequests']['nodes']
    merged_prs = [pr for pr in prs if pr['state'] == 'MERGED']

    # Get unique organizations/communities
    communities = set(pr['repository']['owner']['login'] for pr in prs)

    return {
        "total_prs": len(prs),
        "merged_prs": len(merged_prs),
        "merge_rate": len(merged_prs) / len(prs) if prs else 0,
        "communities": list(communities),
        "community_score": min(100, len(communities) * 10 + len(merged_prs) * 2)
    }
```

### Technological Agility

```python
NUANCED_LANGUAGES = ["Rust", "Go", "Scala", "Elixir", "Haskell", "OCaml", "Kotlin", "Swift"]
BASIC_LANGUAGES = ["JavaScript", "Python", "Java"]

def analyze_tech_agility(repos):
    language_stats = {}

    for repo in repos:
        lang = repo['primaryLanguage']
        loc = repo['linesOfCode']

        if loc > 500:
            if lang not in language_stats:
                language_stats[lang] = 0
            language_stats[lang] += loc

    # Count competent languages (>500 LOC)
    competent_languages = len(language_stats)

    # Bonus for nuanced languages
    nuanced_count = sum(1 for lang in language_stats if lang in NUANCED_LANGUAGES)

    agility_score = (
        competent_languages * 10 +
        nuanced_count * 15
    )

    return {
        "competent_languages": competent_languages,
        "nuanced_languages": nuanced_count,
        "language_breakdown": language_stats,
        "agility_score": min(100, agility_score)
    }
    < 0.15: Low (vibe coder red flag)
```

**Commit Timing Clustering:**

```
commit_timestamps = [extract timestamps from all commits]

# Group by day
commits_by_day = group_by_day(commit_timestamps)

# Calculate variance
time_variance = variance(commits_by_day)

Score:
  High variance (spread out): Skilled
  Low variance (clustered): Vibe coder (AI sprint)
```

---

## Implementation Phases

### Phase 1: Core Analysis Engine

1. GitHub GraphQL integration
2. Behavioral pattern detection
3. Basic scoring algorithm
4. SQLite caching

### Phase 2: AI Detection

1. Integrate `roberta-base-openai-detector`
2. Commit message analysis
3. Heuristic fallbacks

### Phase 3: Code Quality Metrics

1. Radon integration (Python)
2. ESLint integration (JavaScript)
3. Dependency parsing

### Phase 4: Frontend Dashboard

1. React + Vite setup
2. Chart components (Recharts)
3. Real-time updates

### Phase 5: Production Ready

1. PostgreSQL migration
2. Redis caching
3. Rate limiting
4. Error handling
5. Monitoring
