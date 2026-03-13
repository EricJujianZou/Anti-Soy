# Dynamic Scoring & Personalization -- Tech Spec

## Problem Statement

Current scoring is static -- fixed thresholds produce 4 verdict categories (Senior, Junior, Slop Coder, Good AI Coder) with no customization. Recruiters have different priorities: some care deeply about AI usage, others want originality, others focus on security. The current system gives everyone the same score with the same weights. There is also no way to filter by required tech stack or see a per-candidate tech stack breakdown of vibe-coded vs hand-coded projects.

Specifically, the current `compute_verdict()` function in `server/v2/analysis_service.py` (lines 66-94) uses hardcoded threshold logic: `ai_score >= 60` combined with `bad_practices_score >= 50` and `quality_score < 50` to bucket candidates into exactly one of four labels. The `_compute_overall_score()` function in `server/main.py` (lines 194-206) is equally rigid -- it awards 35 points for `solves_real_problem`, 25 for code quality, 20 for standout features, and 20 for low AI score, with no recruiter input.

The 5 priority toggles on the UploadPage (`code_quality`, `security`, `originality`, `production_readiness`, `ai_detection`) are simple on/off checkboxes that get passed to the LLM prompt as weighting instructions but have zero effect on the numeric scoring or verdict computation.

## User Stories

**US-1: Weighted Scoring**
"As a recruiter, I want to adjust how heavily AI usage, security issues, code quality, and originality are weighted in candidate scores, so that the ranking reflects MY hiring priorities, not a one-size-fits-all metric."

**US-2: Tech Stack Filtering**
"As a recruiter evaluating a React+Python role, I want to specify the required tech stack so candidates with hand-coded projects in those technologies score higher."

**US-3: Tech Stack Visibility**
"As a recruiter, I want to see a per-candidate breakdown of which languages they use and which projects are vibe-coded vs hand-coded, so I can quickly assess tech stack fit."

---

## Design

### 1. Slider UI (UploadPage.tsx changes)

**Current state:** 5 checkboxes from `PRIORITY_OPTIONS` in `client/src/services/api.ts` (line 125-131), toggled via `togglePriority()` in `UploadPage.tsx` (lines 32-43). The selected priorities are stored as a `Set<PriorityKey>` and passed to `handleUpload()` as an array.

**New state:** Replace the 5 priority checkboxes with 4 weighted sliders and 1 binary checkbox.

#### Sliders (range 0.0 to 1.0, step 0.1):

| Slider | Default | Penalty Label |
|---|---|---|
| AI Detection | 0.7 | "How harshly to penalize AI-generated code" |
| Security | 0.5 | "How harshly to penalize security issues" |
| Code Quality | 0.5 | "How harshly to penalize poor code quality" |
| Originality | 0.5 | "How harshly to penalize unoriginal projects" |

Each slider must have:
- A left label: "Lenient" (at 0.0)
- A right label: "Strict" (at 1.0)
- The current numeric value displayed (e.g., "0.7")
- A clear label above indicating it controls PENALTY weight. Example: "AI Detection -- How harshly to penalize AI-generated code"

#### Checkbox:
- **"Shipped to Prod" bonus** (binary, default: checked). Replaces the old "Production Readiness" toggle. Label: "Reward candidates who have shipped projects to production"

#### UI Component:
Use a native HTML `<input type="range">` or the shadcn `Slider` component (check if already installed in the project). Style to match the existing card/border theme.

#### State shape:
```typescript
interface ScoringWeights {
  ai_detection: number;   // 0.0 - 1.0
  security: number;       // 0.0 - 1.0
  code_quality: number;   // 0.0 - 1.0
  originality: number;    // 0.0 - 1.0
}

interface ScoringConfig {
  weights: ScoringWeights;
  shipped_to_prod_bonus: boolean;
  required_tech: {
    languages: string[];
    tools: string[];
  };
}
```

#### What to remove:
- Remove the `PRIORITY_OPTIONS` constant usage from UploadPage.
- Remove the `togglePriority()` function.
- Remove the `priorities` Set state.
- The `PRIORITY_OPTIONS` constant in `api.ts` and `VALID_PRIORITIES`/`DEFAULT_PRIORITIES` in `schemas.py` should NOT be deleted (they are still used by the single-repo `/analyze-stream` flow on the Index page). Mark them as legacy in comments.

### 2. Tech Stack Multiselect

Add 2 multiselect dropdown inputs on UploadPage, placed below the sliders and above the file upload area.

#### Required Languages/Frameworks (max 5 selections):
React, Angular, Vue, Svelte, Python, Go, Rust, Java, C#, TypeScript, JavaScript, Node.js, Django, Flask, FastAPI, Spring, .NET, Next.js, Express, Ruby on Rails, Swift, Kotlin

#### Required Tools (max 5 selections):
AWS, GCP, Azure, Docker, Kubernetes, Terraform, CI/CD, PostgreSQL, MongoDB, Redis, GraphQL, REST API, Microsoft 365/Dynamics, Elasticsearch, RabbitMQ, Kafka

#### Implementation:
- Use a combobox/multiselect pattern. If shadcn does not have a built-in multiselect, implement as a dropdown with checkboxes and selected item pills/badges.
- Each selected item appears as a removable badge/pill below the dropdown.
- Enforce max 5 per category. When 5 are selected, disable further selection and show a tooltip: "Maximum 5 selections."
- If no tech is selected, scoring proceeds without tech stack matching (no penalty applied).

### 3. API Changes

#### Endpoint: `POST /batch/upload`

**Current parameters** (in `server/main.py` lines 334-342):
- `resumes: list[UploadFile]` (File)
- `priorities: str` (Form, optional) -- JSON string of priority keys
- `use_generic_questions: str` (Form, optional) -- "true"/"false"

**New parameters:**
- `resumes: list[UploadFile]` (File) -- unchanged
- `scoring_config: str` (Form, optional) -- JSON string of `ScoringConfig` object
- `use_generic_questions: str` (Form, optional) -- unchanged
- `priorities: str` (Form, optional) -- **KEEP for backward compatibility**, but stop reading it in the scoring pipeline. If `scoring_config` is provided, ignore `priorities`.

**Parsing logic in the endpoint:**
```python
# Parse scoring_config if provided
scoring_config_dict = None
if scoring_config:
    try:
        scoring_config_dict = json.loads(scoring_config)
        # Validate with Pydantic model (see Section 10)
        ScoringConfig(**scoring_config_dict)
    except (json.JSONDecodeError, ValidationError):
        scoring_config_dict = None

# Fallback to defaults if not provided or invalid
if scoring_config_dict is None:
    scoring_config_dict = ScoringConfig().model_dump()
```

**Store in BatchJob:**
```python
batch_job = BatchJob(
    id=batch_id,
    total_items=len(resumes),
    status="pending",
    priorities=json.dumps(priority_list),  # keep for backward compat
    scoring_config=json.dumps(scoring_config_dict),  # NEW
    use_generic_questions=generic_questions_flag,
)
```

**Pass to background task:**
```python
background_tasks.add_task(process_batch, batch_id, priority_list, generic_questions_flag)
```
The `process_batch` function will read `scoring_config` from the BatchJob record (not from function args) to avoid serialization issues.

#### Endpoint: `GET /batch/{batch_id}/status`

The `_compute_overall_score()` function currently called at line 441 in `main.py` must be replaced with the new composite score computation. The scoring_config should be read from the BatchJob and passed through.

**Change:** The `BatchStatusResponse` already has `overall_score: int | None` on each item. No schema change needed -- just the computation changes.

#### Endpoint: `GET /batch/{batch_id}/items/{item_id}`

The `CandidateDetailResponse` currently returns `overall_score` as a simple average across repos (line 530 in `main.py`). This must be recomputed using the composite scoring engine with the batch's `scoring_config`.

**New field on `CandidateDetailResponse`:**
```python
tech_stack_breakdown: list[TechStackLanguage] | None = None
```

### 4. Database Schema Changes

**File:** `server/models.py`

Add to `BatchJob` model (after line 125):
```python
scoring_config = Column(Text, nullable=True)  # JSON: ScoringConfig object
```

**Migration strategy:** Since the project uses SQLAlchemy's `create_all()` (line 89 of `main.py`) rather than Alembic migrations, adding a nullable column is safe -- existing rows will have `NULL` for `scoring_config`, and the code must handle this by falling back to defaults.

The `priorities` column is NOT removed. It remains for:
1. Backward compatibility with existing batch jobs
2. The single-repo `/analyze-stream` endpoint still uses priorities
3. Interview question generation still references priorities

### 5. Composite Score Algorithm

**File:** `server/v2/analysis_service.py`

Add a new function `compute_composite_score()`. Do NOT delete `compute_verdict()` -- it is still used by the single-repo `/analyze` and `/analyze-stream` endpoints.

#### Per-repo composite score:

```python
def compute_composite_score(
    ai_slop_score: int,           # 0-100, higher = more AI
    bad_practices_score: int,     # 0-100, higher = worse practices
    code_quality_score: int,      # 0-100, higher = better quality
    originality_score: float,     # 0.0-1.0, higher = more original (from LLM)
    bad_practices_findings: list[dict],  # for severity-aware scaling
    scoring_config: dict,         # ScoringConfig dict
    shipped_to_prod: bool = False,
    tech_match_penalty: float = 0.0,  # 0-100
) -> int:
    """Compute composite 0-100 score for a single repo. Higher = better candidate."""
    weights = scoring_config.get("weights", {})
    w_ai = weights.get("ai_detection", 0.7)
    w_sec = weights.get("security", 0.5)
    w_cq = weights.get("code_quality", 0.5)
    w_orig = weights.get("originality", 0.5)

    # Raw penalty scores (all 0-100, higher = worse)
    ai_penalty = ai_slop_score
    security_penalty = compute_severity_aware_security_penalty(
        bad_practices_score, bad_practices_findings, w_sec
    )
    quality_penalty = 100 - code_quality_score  # invert: higher quality = lower penalty
    originality_penalty = (1.0 - originality_score) * 100  # invert: higher originality = lower penalty

    # Weighted average penalty
    total_weight = w_ai + w_sec + w_cq + w_orig
    if total_weight == 0:
        total_weight = 1.0  # prevent division by zero

    weighted_penalty = (
        ai_penalty * w_ai +
        security_penalty * w_sec +
        quality_penalty * w_cq +
        originality_penalty * w_orig
    ) / total_weight

    # Shipped to prod bonus: 15% penalty reduction
    if scoring_config.get("shipped_to_prod_bonus", True) and shipped_to_prod:
        weighted_penalty *= 0.85

    # Tech stack match scoring
    required_tech = scoring_config.get("required_tech", {})
    has_required = bool(
        required_tech.get("languages") or required_tech.get("tools")
    )
    if has_required and tech_match_penalty > 0:
        weighted_penalty = weighted_penalty * 0.7 + tech_match_penalty * 0.3

    # Final score: 100 - penalty, clamped to [0, 100]
    score = max(0, min(100, round(100 - weighted_penalty)))
    return score
```

#### Per-candidate aggregate score:

```python
def compute_candidate_score(
    repo_scores: list[int],
    repo_tech_relevance: list[float] | None = None,
) -> int:
    """Weighted average of repo scores. Repos matching required tech are weighted higher."""
    if not repo_scores:
        return 0
    if repo_tech_relevance and len(repo_tech_relevance) == len(repo_scores):
        # Weight repos by tech relevance (1.0 = perfect match, 0.5 = default)
        total_weight = sum(repo_tech_relevance)
        if total_weight == 0:
            return round(sum(repo_scores) / len(repo_scores))
        weighted = sum(s * w for s, w in zip(repo_scores, repo_tech_relevance))
        return max(0, min(100, round(weighted / total_weight)))
    else:
        return round(sum(repo_scores) / len(repo_scores))
```

### 6. "Shipped to Prod" Detection

**File:** `server/v2/data_extractor.py`

Add a new function after the `extract_repo_data()` function:

```python
def detect_deployment_signals(repo_data: RepoData) -> dict:
    """
    Detect signals that a project has been deployed to production.

    Returns:
        {"shipped_to_prod": bool, "signals": ["Dockerfile found", ...]}
    """
```

#### Files to detect (check `repo_data.tree`):

| Pattern | Signal label |
|---|---|
| `Dockerfile` | "Dockerfile found" |
| `docker-compose.yml` or `docker-compose.yaml` | "Docker Compose configuration found" |
| Any file path containing `k8s/`, `kubernetes/`, `.k8s/` | "Kubernetes manifests found" |
| `vercel.json` | "Vercel deployment config found" |
| `netlify.toml` | "Netlify deployment config found" |
| `fly.toml` | "Fly.io deployment config found" |
| `.github/workflows/*.yml` or `.github/workflows/*.yaml` | "GitHub Actions workflow found" (only if file content contains `deploy`, `release`, `publish`, or `production` -- check `repo_data.files` if available) |
| `Procfile` | "Heroku Procfile found" |
| Any path containing `terraform/`, `cdk/`, `pulumi/` | "Infrastructure-as-code directory found" |
| `appspec.yml` | "AWS CodeDeploy config found" |
| `cloudbuild.yaml` or `app.yaml` | "GCP deployment config found" |
| `render.yaml` | "Render deployment config found" |
| `railway.json` or `railway.toml` | "Railway deployment config found" |

#### URLs to detect (check `repo_data.files` for README content):

Search the README file content (any file matching `readme*` case-insensitive) for:
- `*.vercel.app`
- `*.netlify.app`
- `*.herokuapp.com`
- `*.fly.dev`
- `*.onrender.com`
- `*.railway.app`
- `*.azurewebsites.net`
- `*.web.app` (Firebase)

Use a regex like:
```python
DEPLOY_URL_PATTERN = re.compile(
    r'https?://[\w.-]+\.(?:vercel\.app|netlify\.app|herokuapp\.com|fly\.dev|'
    r'onrender\.com|railway\.app|azurewebsites\.net|web\.app|pages\.dev)',
    re.IGNORECASE
)
```

Also look for sections in README with headers containing "Demo", "Live", "Deployed", "Production", "Website" followed by a URL.

#### Return type:
```python
{"shipped_to_prod": bool, "signals": list[str]}
```

`shipped_to_prod` is `True` if at least 1 signal is found.

### 7. LLM Prompt Refactoring for Originality

**File:** `server/prompt_modules.py`

#### Changes to the evaluation prompt output format:

The current `OUTPUT_FORMAT_EVALUATION` (lines 171-188) instructs the LLM to return a JSON object with `business_value` and `standout_features`. Modify it to ALSO return `originality_score`.

**New output format:**
```python
OUTPUT_FORMAT_EVALUATION = """
Respond with a JSON object containing THREE parts:

{
  "business_value": {
    "solves_real_problem": true/false,
    "project_type": "real_problem" | "tutorial" | "portfolio_demo" | "learning_exercise" | "utility_tool",
    "project_description": "One sentence describing what this project does",
    "originality_assessment": "What makes this unique or generic, calibrated to the project's domain",
    "project_summary": "2-3 sentence executive summary for a hiring manager",
    "project_scope_estimate": "hobby" | "coursework" | "professional" | "production_oss"
  },
  "standout_features": [
    "Short punchy headline about something genuinely impressive"
  ],
  "originality_score": 0.0-1.0
}

Return ONLY the JSON object, no other text or markdown formatting."""
```

#### New originality calibration module:

Add a new prompt section after `STANDOUT_CALIBRATION`:

```python
ORIGINALITY_SCORING_CALIBRATION = """
ORIGINALITY SCORE INSTRUCTIONS (0.0 to 1.0):

You MUST return a numeric originality_score between 0.0 and 1.0.

IDEA ORIGINALITY (primary factor, ~60% of score):
- 0.0-0.2: Common tutorial/portfolio projects: to-do app, weather app, calculator,
  portfolio website, CRUD blog, chat app, e-commerce store, note-taking app,
  URL shortener, expense tracker, social media clone.
- 0.2-0.4: Standard utility projects with slight customization but fundamentally
  the same as thousands of others.
- 0.4-0.6: Projects that solve a real problem but in a well-trodden domain with
  a standard approach.
- 0.6-0.8: Projects in a niche domain, addressing a genuine gap, or combining
  technologies in an unusual way.
- 0.8-1.0: Truly novel projects: unique domain-specific tools, creative
  applications of technology, research implementations, tools that don't
  have obvious equivalents.

IMPLEMENTATION ORIGINALITY (secondary factor, ~40% of score):
- Generic boilerplate/template code implementing a generic idea = 0.0-0.1.
- Standard implementation of a generic idea with minor customizations = 0.1-0.3.
- Generic idea but with genuinely novel architecture, unique features, or
  creative problem-solving in the implementation = 0.3-0.5.
- Novel idea with standard implementation = 0.5-0.7.
- Novel idea with creative implementation = 0.7-1.0.

CRITICAL RULES:
1. DO NOT say "while the idea isn't novel, the implementation shows..." unless
   the implementation genuinely demonstrates something a senior engineer would
   find impressive. Generic implementations of generic ideas = low originality.
2. A to-do app with React + Node.js + MongoDB is NOT original regardless of how
   clean the code is. Score: 0.05-0.15.
3. A portfolio site with standard sections (about, projects, contact) is NOT
   original. Score: 0.05-0.15.
4. Using popular frameworks/libraries exactly as their tutorials teach is NOT
   implementation originality.

CALIBRATION EXAMPLES:
- To-do app with CRUD and auth: originality_score = 0.05
- Weather dashboard pulling from public API: originality_score = 0.10
- E-commerce store following MERN tutorial: originality_score = 0.08
- CLI tool that analyzes git commit patterns for team productivity: originality_score = 0.65
- Custom browser extension that helps colorblind users: originality_score = 0.75
- ML model for detecting plant diseases from photos, deployed as mobile app: originality_score = 0.80
"""
```

#### Integrate into `build_evaluation_prompt()`:

In the `build_evaluation_prompt()` function (line 415), add the `ORIGINALITY_SCORING_CALIBRATION` after `STANDOUT_CALIBRATION`:

```python
# Standout calibration + originality scoring + output format
prompt_parts.append(STANDOUT_CALIBRATION)
prompt_parts.append(ORIGINALITY_SCORING_CALIBRATION)
prompt_parts.append(OUTPUT_FORMAT_EVALUATION)
```

#### Parsing the originality_score in analysis_service.py:

In `run_evaluation_pipeline()` (line 233), after parsing `eval_result`, extract the originality score:

```python
originality_score = eval_result.get("originality_score", 0.5)
# Clamp to valid range
originality_score = max(0.0, min(1.0, float(originality_score)))
```

This value needs to be stored and passed to the composite score engine. See Section 9 for storage approach.

### 8. Security Severity Scaling

**File:** `server/v2/analyzers/bad_practices.py`

Add a new function (does NOT modify the existing `BadPracticesAnalyzer._calculate_score()` -- that remains for the single-repo flow):

**File:** `server/v2/analysis_service.py`

```python
def compute_severity_aware_security_penalty(
    raw_bad_practices_score: int,
    findings: list[dict],
    security_weight: float,
) -> int:
    """
    Recompute the bad practices penalty with severity-aware scaling.

    CRITICAL findings (hardcoded secrets, .env committed) always apply at full weight.
    WARNING findings scale linearly with the slider weight.
    INFO findings are heavily discounted at low slider values.

    Args:
        raw_bad_practices_score: Original 0-100 score from bad_practices analyzer
        findings: List of finding dicts from bad_practices_data["findings"]
        security_weight: The security slider value (0.0 to 1.0)

    Returns:
        Adjusted penalty score (0-100)
    """
    if not findings:
        return raw_bad_practices_score

    SEVERITY_WEIGHTS = {"critical": 60, "warning": 20, "info": 5}
    severity_multipliers = {
        "critical": 1.0,                    # Always full weight
        "warning": security_weight,          # Scales linearly with slider
        "info": security_weight * 0.3,       # Heavily discounted
    }

    total_weight = 0
    for finding in findings:
        severity = finding.get("severity", "info").lower()
        base_weight = SEVERITY_WEIGHTS.get(severity, 5)
        multiplier = severity_multipliers.get(severity, security_weight)
        total_weight += base_weight * multiplier

    return min(100, round(total_weight))
```

This means: even at Security slider = 0.2, CRITICAL issues like hardcoded secrets still penalize fully (multiplier = 1.0), but INFO issues like bare `except` or missing rate limiting are nearly ignored (multiplier = 0.06).

### 9. Per-Candidate Tech Stack Aggregation

#### Backend

**File:** `server/v2/analysis_service.py`

Add a new function:

```python
def aggregate_tech_stack(
    repos: list[dict],
) -> list[dict]:
    """
    Aggregate language/tech usage across all candidate repos.

    Args:
        repos: List of dicts with keys:
            - "repo_name": str
            - "languages": dict[str, int]  (language -> bytes)
            - "ai_slop_score": int

    Returns:
        List of dicts:
        [
            {
                "language": "Python",
                "total_projects": 3,
                "hand_coded": 2,   # ai_slop_score < 60
                "vibe_coded": 1,   # ai_slop_score >= 60
                "project_names": ["repo-a", "repo-b", "repo-c"]
            },
            ...
        ]
        Sorted by total_projects descending.
    """
```

Logic:
1. For each repo, get its `languages` dict (from `Repo.languages` JSON column) and its `ai_slop_score` (from `RepoAnalysis.ai_slop_score`).
2. For each language in that repo, record it as "hand_coded" if `ai_slop_score < 60`, else "vibe_coded".
3. Aggregate across all repos. A repo with multiple languages counts once per language.
4. Sort by `total_projects` descending.

#### API Response

**File:** `server/v2/schemas.py`

Add new Pydantic models:

```python
class TechStackLanguage(BaseModel):
    """Per-language aggregation across a candidate's repos."""
    language: str
    total_projects: int
    hand_coded: int  # repos where ai_slop_score < 60
    vibe_coded: int  # repos where ai_slop_score >= 60
    project_names: list[str]
```

Add to `CandidateDetailResponse`:
```python
tech_stack_breakdown: list[TechStackLanguage] | None = None
```

#### Frontend

**File:** `client/src/pages/CandidateAssessment.tsx`

Add a new section between the candidate header and the "Project Assessments" section.

**Component: `TechStackBreakdown`**

Displays a list of languages with visual indicators:

```
TECH STACK BREAKDOWN
-------------------------------------------------
Python      3 projects  [=====|==]  2 hand-coded, 1 vibe-coded
React       2 projects  [|=====]    0 hand-coded, 2 vibe-coded
Go          1 project   [=====]     1 hand-coded, 0 vibe-coded
```

For each language row:
- Language name (bold, monospace)
- Total project count
- A stacked horizontal bar: green portion for hand-coded, red/amber portion for vibe-coded
- Text breakdown: "X hand-coded, Y vibe-coded"

Use existing color tokens: green-500 for hand-coded, destructive/amber-500 for vibe-coded.

#### Frontend types

**File:** `client/src/services/batchApi.ts`

Add to `CandidateDetailResponse`:
```typescript
tech_stack_breakdown?: {
  language: string;
  total_projects: number;
  hand_coded: number;
  vibe_coded: number;
  project_names: string[];
}[] | null;
```

### 10. Pydantic Schema Models

**File:** `server/v2/schemas.py`

Add the following models:

```python
class ScoringWeights(BaseModel):
    """Slider weights for the 4 scoring dimensions."""
    ai_detection: float = Field(default=0.7, ge=0.0, le=1.0)
    security: float = Field(default=0.5, ge=0.0, le=1.0)
    code_quality: float = Field(default=0.5, ge=0.0, le=1.0)
    originality: float = Field(default=0.5, ge=0.0, le=1.0)


class RequiredTech(BaseModel):
    """Required tech stack for matching."""
    languages: list[str] = Field(default_factory=list, max_length=5)
    tools: list[str] = Field(default_factory=list, max_length=5)


class ScoringConfig(BaseModel):
    """Full scoring configuration from the recruiter."""
    weights: ScoringWeights = Field(default_factory=ScoringWeights)
    shipped_to_prod_bonus: bool = Field(default=True)
    required_tech: RequiredTech = Field(default_factory=RequiredTech)


class TechStackLanguage(BaseModel):
    """Per-language aggregation across a candidate's repos."""
    language: str
    total_projects: int
    hand_coded: int = Field(description="Repos where ai_slop_score < 60")
    vibe_coded: int = Field(description="Repos where ai_slop_score >= 60")
    project_names: list[str]
```

### 11. Tech Stack Match Penalty Computation

**File:** `server/v2/analysis_service.py`

Add a new function:

```python
def compute_tech_match_penalty(
    repo_languages: dict[str, int],
    repo_dependencies: list[str],
    ai_slop_score: int,
    required_tech: dict,
) -> float:
    """
    Compute penalty based on how well a repo matches the required tech stack.

    Args:
        repo_languages: {"Python": 50000, "JavaScript": 20000, ...}
        repo_dependencies: ["flask", "react", "aws-cdk", ...]
        ai_slop_score: 0-100
        required_tech: {"languages": ["Python", "React"], "tools": ["AWS", "Docker"]}

    Returns:
        Penalty score 0-100. Higher = worse match.
    """
    required_langs = required_tech.get("languages", [])
    required_tools = required_tech.get("tools", [])

    if not required_langs and not required_tools:
        return 0.0

    total_required = len(required_langs) + len(required_tools)
    matched = 0

    # Check language matches (case-insensitive)
    repo_lang_lower = {lang.lower() for lang in repo_languages.keys()}
    # Also map framework names to their base languages
    FRAMEWORK_TO_LANG = {
        "react": {"javascript", "typescript"},
        "angular": {"typescript"},
        "vue": {"javascript", "typescript"},
        "svelte": {"javascript", "typescript"},
        "next.js": {"javascript", "typescript"},
        "express": {"javascript", "typescript"},
        "node.js": {"javascript", "typescript"},
        "django": {"python"},
        "flask": {"python"},
        "fastapi": {"python"},
        "spring": {"java"},
        ".net": {"c#"},
        "ruby on rails": {"ruby"},
    }

    for req_lang in required_langs:
        req_lower = req_lang.lower()
        # Direct language match
        if req_lower in repo_lang_lower:
            matched += 1
            continue
        # Framework match: check dependencies
        expected_langs = FRAMEWORK_TO_LANG.get(req_lower, set())
        if expected_langs and expected_langs & repo_lang_lower:
            # Check if the framework name appears in dependencies
            dep_lower = [d.lower() for d in repo_dependencies]
            if any(req_lower.replace(".", "").replace(" ", "") in d for d in dep_lower):
                matched += 1
                continue
        # Also check if the required item appears directly in dependencies
        dep_lower = [d.lower() for d in repo_dependencies]
        if any(req_lower.replace(" ", "-") in d or req_lower.replace(" ", "") in d for d in dep_lower):
            matched += 1

    # Check tool matches (search in dependencies, file tree)
    TOOL_INDICATORS = {
        "aws": ["aws", "boto3", "aws-cdk", "aws-sdk", "serverless"],
        "gcp": ["google-cloud", "gcloud", "@google-cloud"],
        "azure": ["azure", "@azure"],
        "docker": ["docker"],  # also checked via Dockerfile in tree
        "kubernetes": ["kubernetes", "k8s", "kubectl"],
        "terraform": ["terraform"],
        "ci/cd": [],  # checked via .github/workflows presence
        "postgresql": ["pg", "postgres", "psycopg", "sequelize", "prisma"],
        "mongodb": ["mongo", "mongoose", "pymongo"],
        "redis": ["redis", "ioredis"],
        "graphql": ["graphql", "apollo", "@apollo"],
        "rest api": [],  # most APIs are REST by default
        "elasticsearch": ["elasticsearch", "elastic"],
        "rabbitmq": ["rabbitmq", "amqp", "pika"],
        "kafka": ["kafka", "confluent"],
    }

    dep_lower = [d.lower() for d in repo_dependencies]
    for req_tool in required_tools:
        req_lower = req_tool.lower()
        indicators = TOOL_INDICATORS.get(req_lower, [req_lower])
        if any(ind in d for d in dep_lower for ind in indicators):
            matched += 1

    # Compute match ratio
    match_ratio = matched / total_required if total_required > 0 else 1.0
    missing_penalty = (1.0 - match_ratio) * 100

    # Extra penalty if matched tech is vibe-coded
    if matched > 0 and ai_slop_score >= 60:
        missing_penalty += 15  # extra penalty for vibe-coded matches

    return min(100.0, missing_penalty)
```

### 12. Storing Originality Score

The `originality_score` from the LLM needs to be persisted so it can be used in composite scoring without re-calling the LLM.

**Option chosen: Store in the `business_value` JSON blob.**

The `RepoEvaluation.business_value` column already stores a JSON dict. Add `originality_score` as a new key:

```json
{
  "solves_real_problem": true,
  "project_type": "real_problem",
  "project_description": "...",
  "originality_assessment": "...",
  "project_summary": "...",
  "project_scope_estimate": "professional",
  "originality_score": 0.65
}
```

This avoids any schema migration. The `save_evaluation_results()` function in `analysis_service.py` already stores `business_value` as a JSON dict. The `run_evaluation_pipeline()` function needs to inject `originality_score` into the `business_value` dict before saving:

```python
originality_score = eval_result.get("originality_score", 0.5)
originality_score = max(0.0, min(1.0, float(originality_score)))
if business_value:
    business_value["originality_score"] = originality_score
```

When reading it back for composite scoring:
```python
bv = json.loads(repo_evaluation.business_value)
originality_score = bv.get("originality_score", 0.5)  # default 0.5 for old data
```

---

## Data Flow

```
UploadPage (sliders + multiselect + files)
  |
  v
useBatchUpload.handleUpload()
  |  Constructs ScoringConfig from slider state + multiselect state
  |  Appends as JSON string to FormData under key "scoring_config"
  v
POST /batch/upload
  |  Parses scoring_config JSON, validates with ScoringConfig Pydantic model
  |  Creates BatchJob with scoring_config JSON column
  |  Kicks off background task: process_batch(batch_id, ...)
  v
process_batch (server/v2/batch_processor.py)
  |  Reads scoring_config from BatchJob record
  |  For each resume item → process_single_item()
  v
process_single_item
  |  Resume parse → cross-reference → get repo URLs
  |  For each repo:
  |    ├── run_analysis_pipeline() → ai_slop, bad_practices, code_quality, verdict
  |    ├── detect_deployment_signals() → shipped_to_prod, signals
  |    ├── run_evaluation_pipeline() → business_value (includes originality_score),
  |    |                                standout_features, etc.
  |    ├── compute_tech_match_penalty() → tech_match_penalty
  |    └── compute_composite_score(
  |            ai_slop.score, bad_practices.score, code_quality.score,
  |            originality_score, bad_practices.findings,
  |            scoring_config, shipped_to_prod, tech_match_penalty
  |        ) → repo_composite_score (0-100)
  |
  |  Aggregate across repos:
  |    ├── compute_candidate_score(repo_scores, repo_tech_relevance)
  |    └── aggregate_tech_stack(repos)
  v
GET /batch/{batch_id}/status
  |  For each completed item:
  |    Read scoring_config from BatchJob
  |    Recompute composite score (or read cached from a new column if added)
  |    Return in BatchItemStatus.overall_score
  v
BatchDashboard displays composite_score (numeric 0-100)
  |  Optionally shows a derived label (Strong/Moderate/Weak/Concerning)
  v
GET /batch/{batch_id}/items/{item_id}
  |  Returns CandidateDetailResponse with:
  |    - overall_score (composite, weighted average across repos)
  |    - repos[] each with per-repo overall_score (composite)
  |    - tech_stack_breakdown[]
  v
CandidateAssessment shows:
  - Composite score in header
  - Tech stack breakdown section (new)
  - Per-repo cards with composite per-repo scores
  - Interview questions (unchanged)
```

---

## Implementation Plan (ordered steps)

Each step should be a separate commit/PR. Steps within the same phase can be parallelized.

### Phase 1: Backend Foundation

1. **Database:** Add `scoring_config` TEXT column to `BatchJob` model in `server/models.py`. Just the column -- no logic changes.

2. **Schemas:** Add `ScoringConfig`, `ScoringWeights`, `RequiredTech`, `TechStackLanguage` Pydantic models to `server/v2/schemas.py`.

3. **Backend API:** Modify `POST /batch/upload` in `server/main.py` to accept and store `scoring_config` form field. Fallback to defaults if not provided. Keep `priorities` for backward compat.

### Phase 2: Backend Scoring Engine

4. **Shipped to Prod Detection:** Add `detect_deployment_signals()` function in `server/v2/data_extractor.py`.

5. **LLM Prompt Refactor:** In `server/prompt_modules.py`:
   - Add `ORIGINALITY_SCORING_CALIBRATION` prompt section
   - Update `OUTPUT_FORMAT_EVALUATION` to include `originality_score`
   - Include the new section in `build_evaluation_prompt()`

6. **Security Severity Scaling:** Add `compute_severity_aware_security_penalty()` in `server/v2/analysis_service.py`.

7. **Tech Stack Match:** Add `compute_tech_match_penalty()` in `server/v2/analysis_service.py`.

8. **Composite Score Engine:** Add `compute_composite_score()` and `compute_candidate_score()` in `server/v2/analysis_service.py`.

9. **Tech Stack Aggregation:** Add `aggregate_tech_stack()` in `server/v2/analysis_service.py`.

### Phase 3: Backend Integration

10. **Batch Processor Integration:** Modify `process_single_item()` in `server/v2/batch_processor.py` to:
    - Read `scoring_config` from the BatchJob
    - Call `detect_deployment_signals()` for each repo
    - Extract `originality_score` from LLM response and store in `business_value`
    - Call `compute_composite_score()` per repo
    - Call `aggregate_tech_stack()` and `compute_candidate_score()` per candidate
    - Note: composite scores are recomputed on read (in the status/detail endpoints) since they depend on the batch's scoring_config. No new DB columns needed for scores.

11. **Status Endpoint Update:** Modify `GET /batch/{batch_id}/status` in `server/main.py` to use `compute_composite_score()` instead of `_compute_overall_score()` when `scoring_config` is present on the BatchJob. Fall back to old logic for batches without `scoring_config`.

12. **Detail Endpoint Update:** Modify `GET /batch/{batch_id}/items/{item_id}` in `server/main.py` to:
    - Use composite scoring
    - Include `tech_stack_breakdown` in response

13. **Startup Resilience:** Update the `@app.on_event("startup")` handler (line 656) to handle batches with `scoring_config`.

### Phase 4: Frontend

14. **Slider UI:** In `client/src/pages/UploadPage.tsx`:
    - Replace the priority checkboxes section (lines 137-175) with slider components
    - Add "Shipped to Prod" checkbox
    - Manage state as `ScoringConfig` object

15. **Multiselect:** In `client/src/pages/UploadPage.tsx`:
    - Add two multiselect components for languages/frameworks and tools
    - Enforce max 5 per category
    - Store selections in `ScoringConfig.required_tech`

16. **useBatchUpload:** In `client/src/hooks/useBatchUpload.ts`:
    - Change `handleUpload()` signature to accept `ScoringConfig` instead of `PriorityKey[]`
    - Serialize `scoring_config` as JSON string in FormData
    - Update localStorage storage

17. **Frontend types:** In `client/src/services/batchApi.ts`:
    - Add `TechStackLanguage` type
    - Add `tech_stack_breakdown` to `CandidateDetailResponse`

18. **BatchDashboard:** In `client/src/pages/BatchDashboard.tsx`:
    - The composite score already displays as a number. No major changes needed.
    - Optionally: add a derived label badge based on score ranges:
      - 80-100: "Strong" (green)
      - 60-79: "Moderate" (blue)
      - 40-59: "Developing" (amber)
      - 0-39: "Concerning" (red)
    - Keep the existing `VerdictBadge` component for backward compat with old batches that have verdicts but no composite scores.

19. **CandidateAssessment:** In `client/src/pages/CandidateAssessment.tsx`:
    - Add `TechStackBreakdown` component between candidate header and project assessments
    - Display the `tech_stack_breakdown` array from the API response
    - Handle null/undefined gracefully (old batches won't have it)

---

## Files to Modify

| File (relative to project root) | Changes |
|---|---|
| `server/models.py` | Add `scoring_config` column to `BatchJob` |
| `server/v2/schemas.py` | Add `ScoringConfig`, `ScoringWeights`, `RequiredTech`, `TechStackLanguage` models; add `tech_stack_breakdown` to `CandidateDetailResponse` |
| `server/main.py` | Update `/batch/upload` to accept `scoring_config`; update `/batch/{id}/status` and `/batch/{id}/items/{item_id}` to use composite scoring; update startup handler |
| `server/v2/analysis_service.py` | Add `compute_composite_score()`, `compute_candidate_score()`, `compute_severity_aware_security_penalty()`, `compute_tech_match_penalty()`, `aggregate_tech_stack()`; inject `originality_score` into business_value in `run_evaluation_pipeline()` |
| `server/v2/data_extractor.py` | Add `detect_deployment_signals()` |
| `server/v2/batch_processor.py` | Read `scoring_config` from BatchJob; call new detection/scoring functions |
| `server/v2/analyzers/bad_practices.py` | No changes (severity-aware scaling is in `analysis_service.py`) |
| `server/prompt_modules.py` | Add `ORIGINALITY_SCORING_CALIBRATION`; update `OUTPUT_FORMAT_EVALUATION`; include in `build_evaluation_prompt()` |
| `client/src/pages/UploadPage.tsx` | Replace priority checkboxes with sliders + shipped-to-prod checkbox + tech stack multiselects |
| `client/src/hooks/useBatchUpload.ts` | Accept `ScoringConfig` instead of `PriorityKey[]`; serialize as JSON in FormData |
| `client/src/services/api.ts` | Add comment marking `PRIORITY_OPTIONS` as legacy (still used by single-repo flow) |
| `client/src/services/batchApi.ts` | Add `TechStackLanguage` type; add `tech_stack_breakdown` to `CandidateDetailResponse` |
| `client/src/pages/BatchDashboard.tsx` | Add optional score-range label badge alongside existing verdict badge |
| `client/src/pages/CandidateAssessment.tsx` | Add `TechStackBreakdown` component |

---

## Risks & Tradeoffs

### Risk: LLM originality scoring inconsistency
LLMs may not produce consistent 0.0-1.0 scores across different repos. The same to-do app might get 0.1 from one call and 0.3 from another.

**Mitigation:**
- Include few-shot calibration examples directly in the prompt (done in `ORIGINALITY_SCORING_CALIBRATION`).
- Clamp output to [0.0, 1.0] and default to 0.5 if parsing fails.
- Use `temperature=0.0, top_p=0.0, top_k=1` (already set in `run_evaluation_pipeline()`) for maximum determinism.

### Risk: Composite score loses nuance of 4-category verdict
Users lose the quick "Senior/Junior/Slop Coder" label.

**Mitigation:**
- Keep the old verdict in the DB (do NOT delete `compute_verdict()` or the `verdict_type`/`verdict_confidence` columns).
- Optionally derive a label from score ranges for the new batches (Strong/Moderate/Developing/Concerning).
- Old batches created before this feature will continue to show the old verdict badge.

### Risk: Tech stack multiselect is unbounded
Users could select 20 languages and 15 tools, making every candidate score poorly.

**Mitigation:**
- Hard cap at 5 languages + 5 tools, enforced both in frontend and backend (`max_length=5` on the Pydantic model).

### Risk: Composite score computation on every status poll
`GET /batch/{batch_id}/status` is polled every few seconds during processing. Recomputing composite scores on every poll adds CPU overhead.

**Mitigation:**
- The composite score computation is pure arithmetic (no LLM, no I/O) -- it takes microseconds per repo.
- Only compute for completed items.
- If performance becomes an issue later, cache the composite score in a new DB column on `BatchItemRepo` or `BatchItem`.

### Risk: Shipped-to-prod detection false positives
A repo with a `Dockerfile` used only for local development would trigger a false positive.

**Mitigation:**
- Return the list of signals so the recruiter can see WHY it was flagged.
- The bonus is modest (15% penalty reduction), not a game-changer.
- A single Dockerfile alone is a weak signal; multiple signals (Dockerfile + CI/CD + deploy URLs) are much stronger.

### Rejected Alternatives

- **5 sliders including Production Readiness:** Rejected because "Production Readiness" doesn't map to a clean numeric penalty score from static analysis. Replaced with binary "Shipped to Prod" detection which is more concrete and verifiable.

- **Preset profiles (saved slider configs):** Deferred to backlog. Per-batch config is sufficient for MVP. Adding presets requires a user accounts system or localStorage persistence, which is out of scope.

- **LLM-derived scores for all 4 dimensions:** Rejected because LLM scoring is slow (~3s per call) and expensive. Only Originality uses LLM; AI Detection, Security, and Code Quality all use static analysis which is deterministic and fast.

- **Storing composite scores in the DB at processing time:** Considered but rejected for MVP. Composite scores depend on the batch's `scoring_config`, which is set at upload time and doesn't change. Computing on read is simpler and avoids a migration. Can be added later if performance requires it.

---

## Testing & Verification

### Unit Tests
1. `compute_composite_score()` with various weight combinations:
   - All weights at 0.0 (should return ~100 since no penalties apply)
   - All weights at 1.0
   - Single dimension at 1.0, rest at 0.0
   - Verify score is always clamped to [0, 100]
2. `compute_severity_aware_security_penalty()` with:
   - Only CRITICAL findings at weight 0.2 (should still penalize fully)
   - Only INFO findings at weight 0.2 (should penalize minimally)
   - Mixed findings at weight 1.0 (should match raw score)
3. `detect_deployment_signals()` against a mock RepoData with:
   - Known deployment files (Dockerfile, vercel.json)
   - No deployment files
   - GitHub Actions workflow with/without deploy keywords
4. `compute_tech_match_penalty()` with:
   - Perfect match (all required tech present)
   - No match (nothing present)
   - Partial match
   - Vibe-coded repo with matching tech (should get extra penalty)
5. `aggregate_tech_stack()` with multi-repo, multi-language data

### Integration Tests
6. End-to-end batch upload with custom `scoring_config`:
   - Verify scoring_config is stored in BatchJob
   - Verify composite scores differ from default weights
7. Backward compatibility:
   - Create a batch WITHOUT `scoring_config` (old client)
   - Verify it still works with default scoring
   - Old batches with `priorities` but no `scoring_config` should use defaults

### Manual Tests
8. Upload a batch with extreme slider values (all 0.0, all 1.0)
9. Upload with tech stack multiselect and verify matching/non-matching repos score differently
10. Verify "Shipped to Prod" detection against a repo with known Dockerfile + vercel.json
11. Test LLM originality scoring with a to-do app repo (should score < 0.2) vs a unique project (should score > 0.6)
12. Verify the CandidateAssessment page shows tech stack breakdown correctly

---

## Guardrails for Implementing Agent

1. **ASK before assuming** if any requirement is ambiguous. Do not guess.

2. **Do NOT modify the single-repo analysis flow.** The Index page -> `/analyze-stream` flow must continue working exactly as before. This spec ONLY affects the batch/resume pipeline (`/batch/upload`, `/batch/{id}/status`, `/batch/{id}/items/{item_id}`).

3. **Do NOT delete the old verdict logic.** `compute_verdict()` in `analysis_service.py` and the `verdict_type`/`verdict_confidence` columns in `RepoAnalysis` must remain. They are still used by:
   - `POST /analyze` endpoint
   - `POST /analyze-stream` endpoint
   - `GET /repo/{repo_id}` endpoint
   - Old batch items that pre-date this feature

4. **The composite score must ALWAYS be between 0 and 100.** Clamp aggressively with `max(0, min(100, ...))`.

5. **When refactoring LLM prompts**, keep ALL existing evaluation fields (`business_value`, `standout_features`, etc.). ADD `originality_score` alongside them -- do not replace or remove any existing fields.

6. **Default `originality_score` to 0.5** for repos analyzed before this feature (i.e., repos that don't have `originality_score` in their `business_value` JSON).

7. **Default `scoring_config` to the `ScoringConfig()` defaults** (all default weights) for batch jobs that don't have a `scoring_config` column value (old batches).

8. **Do NOT add new required DB columns.** The `scoring_config` column must be `nullable=True` so existing rows don't break.

9. **Test with the existing test suite** after changes to ensure no regressions.

10. **Frontend slider values** must be serialized as floats (0.0, 0.1, ..., 1.0), not integers.

11. **The `priorities` form field** in the upload endpoint must continue to work for backward compatibility. If both `scoring_config` and `priorities` are provided, `scoring_config` takes precedence.

12. **Do not install new frontend dependencies** for the multiselect unless absolutely necessary. Prefer building from existing shadcn primitives (Popover + Command pattern, or simple checkbox list in a dropdown).

---

## Future / Backlog

- **Preset profiles:** Save and reuse slider configurations (e.g., "Frontend React Role", "Senior Backend Engineer"). Requires localStorage or user accounts.
- **Job description paste:** Free-text JD input -> LLM extracts requirements -> auto-configures sliders and tech stack selections.
- **A/B scoring:** Run the same batch with two different scoring configs to compare how candidates rank under different priorities.
- **Score caching:** If status polling performance becomes an issue, cache composite scores in a new `composite_score` column on `BatchItem` or `BatchItemRepo`.
- **Per-repo shipped-to-prod display:** Show the deployment signals on each repo card in CandidateAssessment, not just use them for scoring.
