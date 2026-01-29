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
│  FRONTEND (React Next.js)                           │
│  ├─ username enter                                 │
│  ├─ #OUT OF SCOPE Profile Preloading (Scan 100 profiles)         │
│  ├─ Analysis Progress Tracker                      │
│  └─ Dashboard (Charts, Scores, Insights)            │
│      ├─ Ranked Candidate List                      │
│      ├─ Overall Skill Score (0-100)                │
│      ├─ AI Detection Percentage                     │
│      ├─ Category Breakdowns (Radar Chart)           │
│      ├─ Red Flags & Strengths Lists                │
│      └─ Recommended Interview Questions             │
└─────────────────────────────────────────────────────┘
                        ↓ HTTP POST
┌─────────────────────────────────────────────────────┐
│  BACKEND (FastAPI + Python)                         │
│     
│  ├─ Database (SQLAlchemy + SQLite)                 │
│  ├─ GitHub GraphQL Client                           │
│  └─ Analysis Pipeline:                              │
│      ├─ Behavioral Pattern Analyzer                │
│      │   └─ Refactoring ratio, commit patterns      │
│      ├─ AI Text Detector (OpenAI/Claude API)       │
│      │   └─ Commit messages, PR descriptions        │
│      ├─ Code Quality Analyzer                       │
│      │   ├─ grep for try catch statement
            - simple grep and regex
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

3. For username:
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

- grep + regex + LLM
- TruffleHog (secret/API key detection)
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

### 1. Repository Discovery

```
Input: GitHub username
↓
Fetch user's public repositories via GraphQL
↓
Filter: list of 5 most recent repos

```

**Implementation:**

- Use GitHub GraphQL API to fetch all repos in single query
- Filter client-side to avoid multiple API calls

### 2. Code Extraction

```
Input: Repository list
↓
For each repo:
  - Clone the repository
  - grep to find each metric
  - if not found, will return metric not found.
  - take +- 50 lines above and below 
  - send to chatgpt for evaluation
  - 
  - Fetch file structure
  - Identify entry points (main.py, index.js, etc.)
  - Extract package manifests (package.json, requirements.txt)
↓
Output: Code samples + metadata
```


### 3. Static Analysis

```
Input: Code samples
↓
Run parallel analysis:
  - Dependency counting (parse package.json)
  - Error handling detection (AST parsing)
  - Comment analysis (regex + density calculation)
↓
Output: Numeric metrics per file/repo
```

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

### Phase 1: Setup
1. FastAPI setup with SQLAlchemy
2. GitHub GraphQL client implementation
3. Database models and migrations


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

1. Integrate openai api
2. Commit message analysis
3. Heuristic fallbacks

### Phase 3: Code Quality Metrics

1. grep each of the metrics and decide
2. Dependency parsing
3. pass metric data into frontend

### Phase 4: Frontend Dashboard

1. React setup
2. Chart components (Recharts)
3. Real-time updates
