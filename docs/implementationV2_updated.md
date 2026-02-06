# Anti-Soy V2: Implementation Updates

> This document tracks changes made to the V2 implementation. Read alongside `implementationV2.md` for full context.

---

## Table of Contents

1. [Session Summary](#session-summary)
2. [Completed Implementation](#completed-implementation)
3. [Current State](#current-state)
4. [Next Steps](#next-steps)

---

## Session Summary

### What Was Built This Session

Starting from a working V2 with three analyzers (AI Slop, Bad Practices, Code Quality), we added:

1. **Emoji Detection** - Static detection of emojis in code comments, print statements, and commit messages
2. **`/evaluate` Endpoint** - LLM-powered project evaluation with business value assessment and interview questions
3. **DB Schema Updates** - Added `project_evaluation` column for caching LLM results

### Key Design Decisions Made

| Decision                  | Choice                          | Rationale                                                 |
| ------------------------- | ------------------------------- | --------------------------------------------------------- |
| Emoji detection approach  | Static regex, not LLM           | Deterministic, fast, no API cost                          |
| Emoji score impact        | +80 to AI score (capped at 100) | Strong signal - real devs don't put 🔥 in production code |
| LLM endpoint architecture | Separate `/evaluate` endpoint   | Keeps `/analyze` fast and cheap; LLM call is optional     |
| LLM provider              | Gemini 2.0 Flash                | Fast, cheap, good at structured JSON output               |
| Interview questions       | Part of `/evaluate` response    | Single LLM call for both business value + questions       |

---

## Completed Implementation

### 1. Emoji Detection (AI Slop Analyzer)

**File:** `server/v2/analyzers/ai_slop.py`

**What was added:**

- `COMMON_EMOJIS` set with 50+ common emojis (🔥💀😂🚀✨👍 etc.)
- `EMOJI_PATTERN` regex for Unicode emoji ranges
- `EmojiFinding` dataclass
- `_detect_emojis()` method that checks:
  - Code comments (`#` and `//` lines)
  - Print/log statements
  - Commit messages (from `repo_data.commits`)
- Score calculation: **+80 to AI score** if any emoji found, capped at 100
- Findings aggregated into single `emoji_in_code` finding showing:
  - First occurrence file/line
  - Distribution (e.g., "17 in code, 7 in print/log")
  - Unique emojis found

**Test result:** FastAPI repo → 24 emoji occurrences detected, AI score = 100

### 2. DB Schema Update

**Files:** `server/models.py`, `server/schema.sql`

**Added column:**

```sql
project_evaluation TEXT  -- JSON: BusinessValue + interview_questions from /evaluate
```

### 3. Pydantic Schemas

**File:** `server/v2/schemas.py`

**New models:**

```python
class BusinessValue(BaseModel):
    solves_real_problem: bool
    project_type: Literal["real_problem", "tutorial", "portfolio_demo", "learning_exercise", "utility_tool"]
    project_description: str
    originality_assessment: str
    project_summary: str

class EvaluateRequest(BaseModel):
    repo_id: int

class EvaluateResponse(BaseModel):
    repo_id: int
    repo_url: str
    business_value: BusinessValue
    interview_questions: list[InterviewQuestion]
```

**Updated model:**

```python
class InterviewQuestion(BaseModel):
    question: str
    based_on: str
    probes: str
    category: str  # NEW: "business_value", "design_choice", "code_issue", "technical_depth"
```

### 4. `/evaluate` Endpoint

**File:** `server/main.py`

**Endpoint:** `POST /evaluate`

**Flow:**

1. Takes `repo_id` (must be analyzed first via `/analyze`)
2. Gathers context: file tree, analyzer scores, top findings
3. Sends to Gemini 2.0 Flash with structured prompt
4. Returns `BusinessValue` + 5-7 `InterviewQuestion` objects with categories
5. Caches result in `repo_data.project_evaluation`

**Test result:** FastAPI repo correctly identified as:

- `solves_real_problem: true`
- `project_type: "real_problem"`
- Generated 7 categorized interview questions

---

## Current State

### Working Endpoints

| Endpoint               | Method | Description                            | Status                        |
| ---------------------- | ------ | -------------------------------------- | ----------------------------- |
| `/`                    | GET    | Health check                           | ✅ Working                    |
| `/analyze`             | POST   | Static analysis (3 analyzers)          | ✅ Working                    |
| `/evaluate`            | POST   | LLM-powered business value + questions | ✅ Working                    |
| `/interview-questions` | POST   | Legacy question generator              | ⚠️ Deprecated (to be removed) |
| `/repo/{id}`           | GET    | Get cached analysis                    | ✅ Working                    |
| `/repo/{id}`           | DELETE | Delete cached analysis                 | ✅ Working                    |

### Verdict Logic

```
| AI Score | Bad Practices | Quality | Verdict |
|----------|---------------|---------|---------|
| ≥60      | ≥50           | <50     | Slop Coder |
| ≥60      | <50           | ≥50     | Good AI Coder |
| <60      | <50           | ≥50     | Senior |
| <60      | ≥50           | <50     | Junior |
```

Edge cases with mixed signals → 50% confidence, lean based on quality score.

### Severity Weights (Bad Practices)

- Critical: 60 points
- Warning: 20 points
- Info: 5 points

### Known Issues

1. **Interview questions too generic** - Current LLM prompt generates questions like "why print instead of logging?" which are textbook answers, not candidate-specific
2. **AI slop findings not used in questions** - Emoji/redundant comment findings are detected but not leveraged for targeted questions
3. **No uniqueness assessment** - We don't highlight what's unique about the project

---

## Next Steps

### 1. Remove `/interview-questions` Endpoint

**Why:** Superseded by `/evaluate` which does everything better (business value + categorized questions in one call).

**Action:** Delete the endpoint from `main.py`.

### 2. Improve `/evaluate` Prompt Quality

**Problem:** Current questions are too generic ("why print instead of logging?").

**Solution:** Update LLM prompt to:

- Send **specific file locations and code snippets** for bad practices/code quality findings
- Focus questions on **design choices and architecture**, not generic best practices
- Questions should require candidate to **explain their own code**, not recite textbook answers
- **Do NOT** generate questions about AI slop signals (emojis, redundant comments)

**Example of good question:**

> "In `user_service.py:45`, you're calling the database without validating the token first. Walk me through the authentication flow - when does token validation happen?"

**Example of bad question:**

> "Why do you have print statements instead of proper logging?"

### 3. Add Uniqueness Field

**New schema:**

```python
class UniqueAspects(BaseModel):
    unique_business_demand: str | None  # What real-world problem this uniquely solves
    unique_tech_choices: str | None     # Unusual/interesting tech stack decisions
    unique_implementation: str | None   # Clever or novel code patterns

class EvaluateResponse(BaseModel):
    repo_id: int
    repo_url: str
    business_value: BusinessValue
    uniqueness: UniqueAspects          # NEW
    interview_questions: list[InterviewQuestion]
```

**LLM prompt addition:**

```
Also identify what's UNIQUE about this project:
- Does it solve a unique business demand (not another to-do app)?
- Are there interesting tech stack choices (why FastAPI instead of Flask)?
- Are there cleverly implemented functions or patterns worth discussing?
```

### 4. Update Question Categories

**Keep:**

- `business_value` - "Why did you build this? Who is the target user?"
- `design_choice` - "Why this architecture/framework/pattern?"
- `code_issue` - Questions about **specific bad practices/quality issues** with file:line references
- `technical_depth` - Deep-dive on their implementation

**Remove from prompts:**

- Questions about print statements (too generic)
- Questions about generic exception handling (textbook answer)
- Questions about AI slop signals (not useful for interview)

---

## File Change Summary

| File                             | Changes                                                                                                 |
| -------------------------------- | ------------------------------------------------------------------------------------------------------- |
| `server/v2/analyzers/ai_slop.py` | Added emoji detection (constants, dataclass, methods, scoring)                                          |
| `server/v2/schemas.py`           | Added `BusinessValue`, `EvaluateRequest`, `EvaluateResponse`, updated `InterviewQuestion` with category |
| `server/models.py`               | Added `project_evaluation` column                                                                       |
| `server/schema.sql`              | Added `project_evaluation` column                                                                       |
| `server/main.py`                 | Added `/evaluate` endpoint, updated imports                                                             |

---

## Testing Commands

```bash
# Start server
cd server && uvicorn main:app --port 8000

# Analyze a repo
curl -X POST "http://localhost:8000/analyze" \
  -H "Content-Type: application/json" \
  -d '{"repo_url": "https://github.com/tiangolo/fastapi"}'

# Evaluate (after analyze)
curl -X POST "http://localhost:8000/evaluate" \
  -H "Content-Type: application/json" \
  -d '{"repo_id": 1}'
```
