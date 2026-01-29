# Anti-Soy Scoring Algorithms

This document describes all algorithms used in the Anti-Soy platform for analyzing GitHub repositories.

---

# Part 1: Backend Analysis Algorithms

The backend analyzes cloned repositories using a combination of **heuristics-based analysis** (6 metrics) and **LLM-based analysis** (8 metrics via Gemini).

## Data Extraction

### Repository Data Structure
```python
{
    "tree": ["file/paths/..."],      # All file paths in repo
    "files": {"path": "content"},    # File contents (text only)
    "commits": [{...}],              # Git commit history
    "dependencies": ["pkg1", ...]    # Extracted dependencies
}
```

### File Filtering Rules
| Rule | Details |
|------|---------|
| Max file size | 100KB per file |
| Max total content | 500KB for LLM context |
| Skip extensions | `.png`, `.jpg`, `.gif`, `.pdf`, `.exe`, `.lock`, etc. |
| Skip directories | `node_modules/`, `venv/`, `__pycache__/`, `.git/`, `dist/`, `build/` |
| Code extensions | `.py`, `.js`, `.ts`, `.jsx`, `.tsx`, `.java`, `.go`, `.rb`, `.rs`, `.cpp`, `.c`, `.cs`, `.php`, `.swift`, `.kt` |

### Git Commit Extraction
```bash
git log -100 --pretty=format:%H|||%s|||%an|||%ad --date=short --numstat
```
Extracts: hash, message, author, date, files_changed, additions, deletions

### Dependency Extraction
Parses these files:
- `requirements.txt`, `pyproject.toml`, `setup.py`, `Pipfile` (Python)
- `package.json`, `yarn.lock` (JavaScript)
- `go.mod` (Go)
- `Cargo.toml` (Rust)
- `Gemfile` (Ruby)
- `pom.xml`, `build.gradle` (Java)
- `composer.json` (PHP)

---

## Heuristics-Based Metrics (6 metrics, no LLM)

### 1. Test Suites (`test_suites`)

**Purpose:** Evaluate test coverage and testing practices.

**Algorithm:**
```
1. Find test files matching patterns:
   - test[s]/, spec[s]/, __tests__/
   - _test., .test., .spec.

2. Calculate test_ratio = test_files / code_files

3. Score breakdown (0-100):
   - Test ratio (0-40 pts):
     - ≥50%: 40 pts
     - ≥25%: 30 pts
     - ≥10%: 20 pts
     - <10%: 10 pts

   - Test file count (0-30 pts):
     - ≥10 files: 30 pts
     - ≥5 files: 20 pts
     - ≥2 files: 15 pts
     - <2 files: 5 pts

   - Test config present (0-15 pts):
     pytest.ini, jest.config.js, etc.

   - Assertion count in tests (0-15 pts):
     - ≥20 assertions: 15 pts
     - ≥10 assertions: 10 pts
     - ≥5 assertions: 5 pts
```

---

### 2. API Keys Security (`api_keys`)

**Purpose:** Detect hardcoded secrets and evaluate security practices.

**Algorithm:**
```
Base score: 50

Patterns detected (BAD - subtract points):
- api[_-]?key = "..." (-15 each, max -40)
- secret[_-]?key = "..."
- password = "..."
- ghp_[token] (GitHub)
- sk-[key] (OpenAI)
- AKIA[key] (AWS)

Good practices (ADD points):
- No secrets found: +20
- os.environ.get / process.env usage:
  - ≥5 uses: +15
  - ≥1 use: +10
- .env.example exists: +10
- .gitignore includes .env: +5
```

---

### 3. Print vs Logging (`print_or_logging`)

**Purpose:** Evaluate logging practices.

**Algorithm:**
```
1. Count print statements: print(
   (exclude test files)

2. Count logging patterns:
   - logging., logger.
   - .info(), .warn(), .error(), .debug()
   - console.log, console.error

3. Calculate logging_ratio = logging_count / (print + logging)

4. Score based on ratio:
   - ≥80% logging: 90
   - ≥60% logging: 75
   - ≥40% logging: 60
   - ≥20% logging: 40
   - <20% logging: 25

5. Bonus +10 if logging config exists:
   logging.basicConfig, winston, log4j
```

---

### 4. Commit Density (`commit_density`)

**Purpose:** Analyze commit frequency and patterns.

**Algorithm:**
```
Base score: 50

Commit count (0-25 pts):
- ≥50 commits: +25
- ≥20 commits: +20
- ≥10 commits: +15
- ≥5 commits: +10
- <5 commits: +5

Large commits penalty (>20 files changed):
- >30% large commits: -15
- >10% large commits: -5

Date diversity (unique dates / total commits):
- ≥50% diversity: +15
- ≥30% diversity: +10

Commit size:
- 50-300 avg lines: +10
- >500 avg lines: -10
```

---

### 5. Concurrency (`concurrency`)

**Purpose:** Detect async/threading patterns.

**Algorithm:**
```
Patterns detected:
- async def, await (Python)
- threading., multiprocessing., asyncio.
- Promise., worker_threads (JS)
- goroutine, channel <- (Go)

Safety patterns:
- Lock(), Semaphore(), Queue()
- Mutex, atomic

No patterns found: score = 50

Patterns found:
- Base: 60
- Pattern count:
  - ≥3 patterns: +15
  - ≥2 patterns: +10
  - 1 pattern: +5
- Safety mechanisms present: +15
- Proper async/await pair: +10
- Mismatched async/await: -10
```

---

### 6. Caching (`caching`)

**Purpose:** Detect caching implementations.

**Algorithm:**
```
Decorator patterns:
- @lru_cache, @cache, @cached, @memoize

External cache:
- redis., memcached
- cache.get(), cache.set()

Browser cache:
- localStorage., sessionStorage.

TTL patterns:
- ttl=, expire, maxage, timeout

No patterns found: score = 50

Patterns found:
- Base: 60
- Decorators present: +10
- External cache: +20
- Browser cache: +5
- TTL configuration: +10
```

---

## LLM-Based Metrics (8 metrics via Gemini)

These metrics use a **single batched API call** to Gemini 2.0 Flash with structured context.

### Prompt Structure

The prompt includes:
1. **File Organization Context:** Top-level dirs, directory structure, sample paths
2. **README Content:** First 4000 chars
3. **Error Handling Samples:** 4 code snippets with try/catch patterns
4. **Comment Samples:** 5 code snippets with comments
5. **Dependencies Context:** Count, density, dep file contents
6. **Commit Messages:** 20 recent messages, low-signal count
7. **Real Problem Indicators:** CI/CD, Docker, config, migrations
8. **Languages Detected:** From file extensions

### 7. Files Organized (`files_organized`)

**Evaluation Criteria:**
- Clear separation of concerns
- Logical grouping of files
- Reasonable nesting depth
- Follows language conventions

---

### 8. README Quality (`readme`)

**Evaluation Criteria:**
- Explains project purpose
- Installation instructions
- Usage examples
- Well-formatted markdown

---

### 9. Error Handling (`error_handling`)

**Evaluation Criteria:**
- Specific exception catches (not bare except)
- Meaningful error handling logic
- Cleanup in finally blocks
- Custom exception classes

---

### 10. Comments Quality (`comments`)

**Evaluation Criteria:**
- Explains WHY not WHAT
- Docstrings present
- Human-written vs AI-generated patterns
- Appropriate density (not over/under commented)

---

### 11. Dependencies (`dependencies`)

**Evaluation Criteria:**
- Pinned versions
- Reasonable count for project size
- Lock file present
- Dev/prod dependencies separated

---

### 12. Commit Lines (`commit_lines`)

**Evaluation Criteria:**
- Descriptive commit messages
- Conventional commit format
- Human vs AI-written messages
- Explains what AND why

---

### 13. Solves Real Problem (`solves_real_problem`)

**Evaluation Criteria:**
- Real problem vs tutorial clone
- Production-ready features (CI/CD, Docker, config)
- Professional quality code
- Meaningful complexity

**Indicators checked:**
- CI/CD pipeline files
- Docker configuration
- Configuration management
- Database migrations
- Tutorial keywords (todo-app, hello-world, etc.)

---

### 14. Aligns Company (`aligns_company`)

**Evaluation Criteria:**
- Tech stack matches company requirements
- Domain relevance
- Skills alignment
- Relevant experience demonstrated

**Default company description:**
> "A technology company building software products. Looking for developers with strong coding skills, clean code practices, and experience with modern development workflows."

---

## LLM Response Format

```json
{
  "files_organized": {"score": 0-100, "comment": "<150 chars>"},
  "readme": {"score": 0-100, "comment": "<150 chars>"},
  "error_handling": {"score": 0-100, "comment": "<150 chars>"},
  "comments": {"score": 0-100, "comment": "<150 chars>"},
  "dependencies": {"score": 0-100, "comment": "<150 chars>"},
  "commit_lines": {"score": 0-100, "comment": "<150 chars>"},
  "solves_real_problem": {"score": 0-100, "comment": "<150 chars>"},
  "aligns_company": {"score": 0-100, "comment": "<150 chars>"}
}
```

**Score Guidelines:**
- 0-20: Very poor
- 21-40: Poor
- 41-60: Average
- 61-80: Good
- 81-100: Excellent

---

# Part 2: Frontend Derived Statistics

The frontend computes additional statistics from the 14 backend metrics.

## Backend Response Structure

Each metric returns:
```json
{
  "score": 0-100,
  "comment": "Explanation of the score"
}
```

---

## 1. Overall Repository Score

**Purpose:** Single score representing overall code quality.

**Algorithm:** Weighted average of all metrics.

```typescript
weights = {
  files_organized: 0.08,
  test_suites: 0.10,
  readme: 0.05,
  api_keys: 0.12,      // Security weighted higher
  error_handling: 0.10,
  comments: 0.05,
  print_or_logging: 0.08,
  dependencies: 0.07,
  commit_density: 0.08,
  commit_lines: 0.07,
  concurrency: 0.05,
  caching: 0.05,
  solves_real_problem: 0.05,
  aligns_company: 0.05,
}

overall_score = Σ (metric.score × weight)
```

**Output:** 0-100 (rounded)

---

## 2. Radar Chart Data

**Purpose:** Visual breakdown into 6 high-level categories.

**Algorithm:** Average scores within each category.

| Category | Formula |
|----------|---------|
| Code Quality | `(files_organized + comments) / 2` |
| Documentation | `readme` |
| Testing | `test_suites` |
| Architecture | `(files_organized + concurrency + caching) / 3` |
| Security | `(api_keys + error_handling) / 2` |
| Performance | `(caching + concurrency + dependencies) / 3` |

**Output:** Array of 6 `{label, value}` objects

---

## 3. AI Footprint

**Purpose:** Estimate likelihood of AI-generated code.

**Algorithm:** Inverse of `print_or_logging` score.

```typescript
ai_footprint = max(0, 100 - print_or_logging.score)
```

**Rationale:** AI-generated code often lacks proper logging practices, using print statements instead.

**Output:** 0-100 (higher = more AI-like patterns)

---

## 4. Strengths

**Purpose:** Highlight the repository's best qualities.

**Algorithm:**
1. Collect all 14 metrics with their scores
2. Sort by score descending
3. Take top 3
4. Return their comments

```typescript
strengths = metrics
  .sort((a, b) => b.score - a.score)
  .slice(0, 3)
  .map(m => m.comment)
```

**Output:** Array of 3 insight objects

---

## 5. Red Flags

**Purpose:** Highlight areas needing improvement.

**Algorithm:**
1. Collect all 14 metrics with their scores
2. Sort by score ascending
3. Take bottom 3
4. Return their comments

```typescript
red_flags = metrics
  .sort((a, b) => a.score - b.score)
  .slice(0, 3)
  .map(m => m.comment)
```

**Output:** Array of 3 insight objects

---

## 6. Suggestions

**Purpose:** Actionable improvement recommendations.

**Algorithm:** Threshold-based rules on specific metrics.

| Condition | Suggestion |
|-----------|------------|
| `test_suites < 70` | "Add more unit tests to improve coverage" |
| `print_or_logging < 50` | "Replace print statements with proper logging" |
| `caching < 50` | "Consider adding caching for frequently accessed data" |
| `concurrency < 50` | "Consider async patterns for I/O operations" |
| `error_handling < 60` | "Add more error handling and edge case coverage" |
| `comments < 60` | "Document complex functions with clear comments" |

**Output:** Up to 5 suggestions (capped)

---

## 7. Production Readiness Score

**Purpose:** Assess deployment readiness.

**Algorithm:** Weighted average of production-critical metrics.

```typescript
production_readiness = (
  error_handling.score × 0.35 +
  concurrency.score × 0.25 +
  caching.score × 0.20 +
  dependencies.score × 0.20
)
```

**Output:** 0-100 (rounded)

---

## 8. Scalability Score

**Purpose:** Assess ability to handle growth.

**Algorithm:** Weighted average of scalability-related metrics.

```typescript
scalability = (
  concurrency.score × 0.40 +
  caching.score × 0.35 +
  files_organized.score × 0.25
)
```

**Output:** 0-100 (rounded)

---

## 9. Production Readiness Signals

**Purpose:** Quick visual indicators for production concerns.

**Algorithm:** Threshold-based categorization.

| Metric | Score ≥ 70 | Score 40-69 | Score < 40 |
|--------|------------|-------------|------------|
| `concurrency` | "Present" (good) | "Partial" (warn) | "Missing" (bad) |
| `error_handling` | "Strong" (good) | "Partial" (warn) | "Weak" (bad) |
| `caching` | "Present" (good) | "Basic" (warn) | "Missing" (bad) |

**Output:** Array of 3 signal objects with tone indicators

---

## 10. AI Usage Signals

**Purpose:** Indicators of AI-assisted development patterns.

**Algorithm:** Threshold-based categorization.

| Metric | Score ≥ 70 | Score 40-69 | Score < 40 |
|--------|------------|-------------|------------|
| `comments` | "Natural" (good) | "Mixed" (warn) | "Sparse" (neutral) |
| `commit_lines` | "Organic" (good) | "Mixed" (warn) | "Bulk Changes" (neutral) |

Plus AI Footprint indicator:
| AI Footprint | Label |
|--------------|-------|
| ≤ 20 | "Low" (good) |
| 21-50 | "Moderate" (neutral) |
| > 50 | "High" (warn) |

**Output:** Array of 3 signal objects with tone indicators

---

## 11. AI Suggestions

**Purpose:** AI-style improvement recommendations.

**Algorithm:** Threshold-based rules.

| Condition | Suggestion |
|-----------|------------|
| `error_handling < 60` | "Add structured logging to improve incident triage" |
| `concurrency < 50` | "Introduce async patterns for better scalability" |
| `caching < 50` | "Add caching layer for frequently accessed data" |
| `test_suites < 60` | "Expand test coverage for critical paths" |

**Output:** Up to 3 suggestions (capped)

---

# Summary Tables

## Backend Metrics Overview

| Metric | Type | Key Factors |
|--------|------|-------------|
| `test_suites` | Heuristic | Test file ratio, config, assertions |
| `api_keys` | Heuristic | Secrets detection, env var usage |
| `print_or_logging` | Heuristic | Logging ratio, config presence |
| `commit_density` | Heuristic | Commit count, size, frequency |
| `concurrency` | Heuristic | Async patterns, safety mechanisms |
| `caching` | Heuristic | Cache decorators, external cache, TTL |
| `files_organized` | LLM | Structure, conventions, separation |
| `readme` | LLM | Purpose, install, usage, formatting |
| `error_handling` | LLM | Specificity, handling logic, cleanup |
| `comments` | LLM | Quality, density, human vs AI |
| `dependencies` | LLM | Versions, count, lock file |
| `commit_lines` | LLM | Message quality, format, clarity |
| `solves_real_problem` | LLM | Real vs tutorial, production features |
| `aligns_company` | LLM | Tech stack, domain, skills match |

## Frontend Computed Statistics

| Statistic | Input Metrics | Method |
|-----------|---------------|--------|
| Overall Score | All 14 | Weighted average |
| Radar Chart | Grouped subsets | Category averages |
| AI Footprint | print_or_logging | Inverse |
| Strengths | All 14 | Top 3 by score |
| Red Flags | All 14 | Bottom 3 by score |
| Suggestions | 6 specific metrics | Threshold rules |
| Production Readiness | 4 metrics | Weighted average |
| Scalability | 3 metrics | Weighted average |
| Production Signals | 3 metrics | Threshold categories |
| AI Usage Signals | 3 metrics + derived | Threshold categories |
| AI Suggestions | 4 metrics | Threshold rules |
