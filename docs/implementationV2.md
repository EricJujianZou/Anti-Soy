# Anti-Soy V2: Implementation Specification

> A technical specification for engineers. Describes WHAT to build and WHY, not HOW to implement.

---

## Table of Contents

1. [Context](#context)
2. [Research Findings](#research-findings)
3. [Architecture Overview](#architecture-overview)
4. [Analyzer Specifications](#analyzer-specifications)
5. [File Importance & Aggregation](#file-importance--aggregation)
6. [Output Specification](#output-specification)
7. [Decision Log](#decision-log)

---

## Context

### What V1 Had

V1 runs 14 metrics through a single pipeline, producing individual scores that get weighted into an overall score. Metrics are detected via simple regex/pattern matching.

### What V2 Changes

V2 introduces a **three-analyzer architecture** where each analyzer:

- Uses multiple signals (triangulation) for higher confidence
- Produces **evidence with code snippets**, not just scores
- Generates **interview questions** based on findings

### Core Philosophy Change

| V1                       | V2                                      |
| ------------------------ | --------------------------------------- |
| "Score good practices"   | "Detect absences of defensive thinking" |
| Single signal per metric | Multiple signals per finding            |
| Numbers for interviewers | Evidence + questions for interviewers   |
| Surface-level regex      | Deep style analysis + LLM verification  |

---

## Research Findings

### Academic Research on AI Code Detection

**LPcodedec** (Park et al., 2025)

- Paper: "Detection of LLM-Paraphrased Code Using Coding Style Features"
- Dataset: 21k code snippets (C, C++, Java, Python)
- Approach: **Style-based feature extraction** — naming conventions, indentation patterns, comment ratios
- Accuracy: 87-93% F1 score
- Key insight: **Not a neural network** — extracts exactly **10 numerical features**, feeds to MLPClassifier or RandomForest
- Uses **regex-based extraction** (not AST) — simpler, faster, portable across languages
- Fully explainable; can show which features triggered detection

**H-AIRosettaMP** (Gurioli et al., 2025)

- Paper: "Recognizing AI-written Programs with Multilingual Code Stylometry"
- Dataset: 121k code snippets, 10 languages, MIT license
- Approach: Transformer-based encoder classifier
- Accuracy: 84.1% ± 3.8% across all languages
- Less explainable (black box), requires GPU

### Key Takeaway for Our Implementation

Feature-based detection (LPcodedec style) is:

- More explainable (we can show WHY)
- More accurate for single languages
- Faster (CPU-only, milliseconds per file)
- Doesn't require GPU infrastructure

We adopt the **feature-based approach** for V2.

### LPcodedec's Exact Feature Vector (10 features)

From analysis of their source code, here are the exact features they extract:

| #   | Feature                       | Type  | Description                                                                    |
| --- | ----------------------------- | ----- | ------------------------------------------------------------------------------ |
| 1   | `function_naming_consistency` | 0-1   | Ratio of dominant naming style (camelCase/snake_case/PascalCase) for functions |
| 2   | `variable_naming_consistency` | 0-1   | Same, for variables                                                            |
| 3   | `class_naming_consistency`    | 0-1   | Same, for classes                                                              |
| 4   | `constant_naming_consistency` | 0-1   | Same, for constants (UPPER_SNAKE_CASE)                                         |
| 5   | `indentation_consistency`     | 0-1   | Ratio of most common indent level vs total indented lines                      |
| 6   | `avg_function_length`         | float | Average lines of code per function                                             |
| 7   | `avg_nesting_depth`           | float | Average nesting level (indent-based for Python, brace-based for C/Java)        |
| 8   | `comment_ratio`               | 0-1   | Comment lines / (comment + code lines)                                         |
| 9   | `avg_function_name_length`    | float | Average character length of function names                                     |
| 10  | `avg_variable_name_length`    | float | Average character length of variable names                                     |

**Key insight:** AI tends toward verbose names (`processUserDataAndReturnResult`) while humans use shorter names (`process_data`).

### Forum/Community Findings

From developer forums (Reddit, HN, Blind):

- Engineers spot AI code primarily through **redundant comments** ("iterate through the loop" before a for loop)
- GitHub stars/forks are **not reliable** — can be artificially inflated
- Commit history patterns matter less than code quality
- The things AI misses: input validation, rate limiting, security considerations, edge case handling

---

## Architecture Overview

```
Input: GitHub repo URL
        │
        ▼
┌───────────────────────┐
│   Data Extraction     │
│   - Clone repo        │
│   - Parse files       │
│   - Extract git history│
└───────────────────────┘
        │
        ├─────────────────────────────────────────┐
        │                                         │
        ▼                                         ▼
┌─────────────────────┐  ┌─────────────────────┐  ┌─────────────────────┐
│  AI Slop Detector   │  │  Bad Practices      │  │  Code Quality       │
│                     │  │  Detector           │  │  Analyzer           │
│  - Style features   │  │  - Security gaps    │  │  - Complexity       │
│  - Comment analysis │  │  - Missing checks   │  │  - Test coverage    │
│  - Instruction files│  │  - Hygiene issues   │  │  - Documentation    │
└─────────────────────┘  └─────────────────────┘  └─────────────────────┘
        │                         │                         │
        └─────────────────────────┴─────────────────────────┘
                                  │
                                  ▼
                    ┌───────────────────────────┐
                    │   Evidence Collector       │
                    │   - Gather all findings    │
                    │   - Attach code snippets   │
                    │   - Add file:line refs     │
                    └───────────────────────────┘
                                  │
                                  ▼
                    ┌───────────────────────────┐
                    │   Question Generator       │
                    │   - LLM generates questions│
                    │   - Based on evidence      │
                    └───────────────────────────┘
                                  │
                                  ▼
                    ┌───────────────────────────┐
                    │   Final Report             │
                    │   - Per-analyzer scores    │
                    │   - Evidence + snippets    │
                    │   - Interview questions    │
                    └───────────────────────────┘
```

---

## Analyzer Specifications

### Analyzer 1: AI Slop Detector

**Purpose:** Detect signs of AI-generated code or over-reliance on AI without understanding.

**Signals:**

| Signal                           | What It Detects                                                                  | Explainability                   |
| -------------------------------- | -------------------------------------------------------------------------------- | -------------------------------- |
| Style features (LPcodedec-style) | Naming patterns, structure, comment ratios that differ from human norms          | High — show each feature value   |
| Redundant comments               | "# iterate through loop" before `for` statements                                 | High — show the comment + code   |
| AI instruction files             | .cursorrules, CLAUDE.md present (indicates disciplined AI use — positive signal) | High — file exists/doesn't exist |
| Comment-to-complexity mismatch   | Over-explained simple code, under-explained complex code                         | Medium — requires judgment       |

**Style Features to Extract:**

```
Core LPcodedec Features (10 — proven in research):
1.  function_naming_consistency     # 0-1, dominant style ratio
2.  variable_naming_consistency     # 0-1, dominant style ratio
3.  class_naming_consistency        # 0-1, dominant style ratio
4.  constant_naming_consistency     # 0-1, dominant style ratio
5.  indentation_consistency         # 0-1, most common indent / total
6.  avg_function_length             # float, LOC per function
7.  avg_nesting_depth               # float, indent/brace depth
8.  comment_ratio                   # 0-1, comment lines / total
9.  avg_function_name_length        # float, chars
10. avg_variable_name_length        # float, chars

Our Additions (4 — for richer signal):
11. max_function_length             # int, god function detection
12. max_nesting_depth               # int, complexity red flag
13. docstring_coverage              # 0-1, % functions with docstrings
14. redundant_comment_count         # int, LLM-verified (our differentiator)

Binary Signals (not in classifier, separate checks):
- has_ai_instruction_files          # .cursorrules, CLAUDE.md, .github/copilot-instructions.md
- has_design_docs                   # /docs with architecture/design content (not AI summaries)
```

**Naming Style Classification (from LPcodedec):**

| Pattern                         | Style            | Example       |
| ------------------------------- | ---------------- | ------------- |
| `^[a-z]+(?:[A-Z][a-z]*)*$`      | camelCase        | `getUserId`   |
| `^[a-z]+(?:_[a-z]+)+$`          | snake_case       | `get_user_id` |
| `^[A-Z][a-z]+(?:[A-Z][a-z]*)*$` | PascalCase       | `GetUserId`   |
| `^[A-Z]+(?:_[A-Z]+)+$`          | UPPER_SNAKE_CASE | `GET_USER_ID` |
| (else)                          | Other            | `getuser_Id`  |

**Consistency Score Formula:**

```
consistency = count(dominant_style) / total_identifiers
```

A score of 1.0 means all identifiers follow the same convention. Mixed conventions (common in AI code) produce lower scores.

**Implementation Notes (from LPcodedec source analysis):**

1. **Regex over AST** — LPcodedec uses pure regex to extract identifiers. This is faster and works across languages without language-specific parsers:

   ```python
   # Function names
   r'(?:def|function|fn|func)\s+([a-zA-Z_]\w*)'

   # Variable names
   r'(?:let|var|const|int|float|string|bool)?\s*([a-zA-Z_]\w*)\s*[:=]'

   # Class names
   r'(?:class|struct|interface)\s+([a-zA-Z_]\w*)'
   ```

2. **Indentation consistency** — Count leading whitespace per line, bucket into multiples (2, 4, 8, etc.), compute ratio of most common bucket vs total indented lines.

3. **Nesting depth** — For Python, use indent level. For C/Java/JS, count brace depth.

4. **MLPClassifier vs RandomForest** — LPcodedec defaults to MLPClassifier with StandardScaler. We'll use RandomForest for better explainability (feature importances).

5. **Training time** — 21k samples trains in seconds on CPU. No GPU needed.

**Redundant Comment Detection:**

Pre-filter with cheap pattern matching:

- "# loop/iterate" followed by `for`
- "# call api" followed by HTTP call
- "# handle error" followed by `except`
- "# return result" followed by `return`

Only send suspicious comments to LLM for verification (cost control).

**Output:**

- AI Slop Score (0-100)
- Confidence (Low/Medium/High based on signal agreement)
- Evidence list with code snippets
- Verdict: "Professional AI User" / "Possible Vibe Coder" / "Likely Manual Code"

---

### Analyzer 2: Bad Practices Detector

**Purpose:** Find security gaps, missing defensive code, and professional discipline issues.

**Key Insight:** These are things AI doesn't add unless explicitly prompted. A vibe coder doesn't know to prompt for them.

**Signals:**

| Category       | Signal                   | What It Catches                                  |
| -------------- | ------------------------ | ------------------------------------------------ |
| **Security**   | No input validation      | Functions using params without sanitization      |
| **Security**   | SQL injection risk       | String concatenation in queries                  |
| **Security**   | Hardcoded secrets        | API keys, passwords in code                      |
| **Security**   | CORS wildcard            | `Access-Control-Allow-Origin: *`                 |
| **Security**   | No auth middleware       | Unprotected API endpoints                        |
| **Robustness** | No timeout on HTTP calls | Requests without timeout parameter               |
| **Robustness** | Silent error swallowing  | Empty except blocks                              |
| **Robustness** | No retry logic           | External calls without retry patterns            |
| **Hygiene**    | .env committed           | Sensitive files in repo                          |
| **Hygiene**    | Lock file mismatch       | package-lock.json inconsistent with package.json |

**Output:**

- List of findings, each with:
  - Severity (Critical / Warning / Info)
  - Code snippet with file:line
  - Plain-English explanation
  - Generated interview question

---

### Analyzer 3: Code Quality Analyzer

**Purpose:** Assess engineering maturity and maintainability.

**Signals:**

| Signal              | What It Measures                                      |
| ------------------- | ----------------------------------------------------- |
| Function complexity | God functions (>100 LOC), deep nesting (>4 levels)    |
| Test presence       | Test files exist, assertion count, edge case coverage |
| Documentation       | README quality, docstring coverage                    |
| Project structure   | Logical directory organization                        |
| Dependency health   | Outdated or excessive dependencies                    |

**Output:**

- Quality Score (0-100)
- Strengths list
- Areas for improvement

---

## File Importance & Aggregation

### Problem

Repos contain hundreds of files. Analyzing everything is:

- Slow
- Noisy (utility files dilute signal)
- Expensive (LLM calls)

### Solution: File Importance Scoring

**Prioritize files that show real engineering decisions:**

| Signal                                              | Weight Adjustment              |
| --------------------------------------------------- | ------------------------------ |
| Entry points (main.py, app.py, index.js, server.py) | +30                            |
| Highly imported (many other files depend on it)     | +5 per import (max +30)        |
| Meaningful size (50-500 LOC)                        | +20                            |
| Very large (>500 LOC)                               | +10 (slight penalty for bloat) |
| Test/spec files                                     | -40                            |
| Utils/helpers/constants                             | -40                            |
| UI component library (components/ui/)               | -30                            |

**Files to analyze:** Top 10-15 by importance score.

### Aggregation Strategy

1. Analyze each important file independently
2. Collect per-file scores and evidence
3. Aggregate to repo level using importance-weighted average
4. Display: Repo-level score with drill-down to per-file details

---

## Output Specification

### Per-Repo Report Structure

```
Repository: {owner}/{repo}
Overall Assessment: {verdict}

┌─────────────────────────────────────────────────────┐
│ AI Slop Score: 65/100 (Medium Confidence)           │
│ Bad Practices: 3 Critical, 2 Warning                │
│ Code Quality: 72/100                                │
└─────────────────────────────────────────────────────┘

Evidence (5 findings):

1. [CRITICAL] No input validation on user endpoint
   File: api/users.py:47
   ┌──────────────────────────────────────────────────┐
   │ def update_user(user_id, data):                  │
   │     db.users.update(user_id, data)               │
   └──────────────────────────────────────────────────┘
   Ask: "What happens if someone passes {"role": "admin"}
        in this payload? How would you prevent that?"

2. [WARNING] Redundant AI-style comment
   File: services/auth.py:23
   ┌──────────────────────────────────────────────────┐
   │ # Iterate through the list of users              │
   │ for user in users:                               │
   └──────────────────────────────────────────────────┘
   Ask: "Walk me through why you structured the auth
        service this way."

... (more findings)

Interview Questions (Generated):
1. "What happens if the database connection times out in your
    API handler? Show me how you'd handle that."
2. "I see you're using {library} here. What made you choose
    that over alternatives?"
3. "If this endpoint gets 1000 requests/second, what breaks first?"
```

---

## Decision Log

### Metric Changes from V1

| V1 Metric             | V2 Status                           | Rationale                                                       |
| --------------------- | ----------------------------------- | --------------------------------------------------------------- |
| `files_organized`     | **Moved** to Code Quality Analyzer  | Still relevant, now part of larger quality assessment           |
| `test_suites`         | **Moved** to Code Quality Analyzer  | Enhanced with edge case detection                               |
| `readme`              | **Moved** to Code Quality Analyzer  | Unchanged                                                       |
| `api_keys`            | **Moved** to Bad Practices Detector | Enhanced with more secret patterns                              |
| `error_handling`      | **Moved** to Bad Practices Detector | Now checks for silent swallowing, not just presence             |
| `comments`            | **Replaced** by AI Slop Detector    | Now distinguishes helpful vs redundant comments                 |
| `print_or_logging`    | **Moved** to Bad Practices Detector | Part of hygiene signals                                         |
| `dependencies`        | **Moved** to Code Quality Analyzer  | Unchanged                                                       |
| `commit_density`      | **Deprioritized**                   | Research showed commit patterns less reliable than code quality |
| `commit_lines`        | **Deprioritized**                   | Same as above                                                   |
| `concurrency`         | **Moved** to Code Quality Analyzer  | Part of scalability assessment                                  |
| `caching`             | **Moved** to Code Quality Analyzer  | Part of scalability assessment                                  |
| `solves_real_problem` | **Removed**                         | Too subjective, LLM-dependent, low signal                       |
| `aligns_company`      | **Removed**                         | Requires company context we don't have                          |

### Architecture Decisions

- **Three separate analyzers instead of 14 flat metrics**
  - Why: Allows independent development, clearer ownership, better organization of signals
  - Alternative considered: Enhanced single pipeline — rejected because it doesn't solve the "scattered output" problem

- **Feature-based ML over transformer model**
  - Why: Explainability is our product; transformer can't show evidence
  - Why: Higher accuracy for single languages (87-93% vs 84%)
  - Why: No GPU required, runs on CPU in milliseconds
  - Alternative considered: H-AIRosettaMP transformer — rejected for now, may add as secondary signal later

- **LPcodedec's exact 10 features as baseline**
  - Why: Proven in peer-reviewed research (Park et al., 2025)
  - Why: Simple regex extraction, no complex AST parsing required
  - Why: Trains in seconds on 21k samples
  - Addition: +4 features (docstring*coverage, max*\*, redundant_comment_count) for richer signal
  - Alternative considered: Custom feature set — rejected because we shouldn't reinvent the wheel

- **Regex-based identifier extraction over AST**
  - Why: LPcodedec achieves 87-93% F1 with pure regex
  - Why: Portable across languages without language-specific parsers
  - Why: Simpler implementation, easier to maintain
  - When to use AST: Only for language-specific checks (Python indentation, JS brace counting)

- **RandomForest classifier over MLP**
  - Why: LPcodedec uses MLP, but RandomForest provides feature importances
  - Why: Feature importances = explainable evidence ("naming consistency was the strongest signal")
  - Why: Trains in minutes on laptop, no infrastructure
  - Alternative considered: Fine-tuned CodeBERT — rejected due to explainability requirements

- **LLM for question generation, not detection**
  - Why: Detection needs consistency; questions benefit from creativity
  - Why: LLM calls are expensive; limit to high-value output
  - Alternative considered: Full LLM analysis — rejected due to cost and consistency issues

- **Pre-filter then LLM for redundant comments**
  - Why: 500 comments × $0.01/call = $5/repo is too expensive
  - Solution: Regex pre-filter catches 80% of candidates, LLM verifies only suspicious ones
  - Expected: 10-50 LLM calls per repo max

### Language Support Decisions

- **Python + JavaScript/TypeScript first**
  - Why: Covers majority of startup codebases
  - Why: Good AST libraries available (Python `ast`, `esprima`/Babel for JS)
  - Expansion: Add Go, Rust later based on demand

- **Abstract parser interface**
  - Why: ~60% of feature extraction logic is language-agnostic
  - Implementation: Language-specific parsers implement shared interface
  - Benefit: Adding new language = ~2-3 days work

### File Selection Decisions

- **Importance scoring over random sampling**
  - Why: Main files show engineering decisions; utils show boilerplate
  - Why: Random sampling might miss all the interesting code

- **10-15 files per repo**
  - Why: Diminishing returns beyond this
  - Why: Keeps analysis time reasonable (<60 seconds)

- **Skip test files for AI detection, include for quality**
  - Why: Test code has different style norms
  - Why: Test presence/quality is a quality signal, not AI signal

---

## Open Questions for Implementation

1. **Classifier training data:** Use LPcode dataset (21k samples) or H-AIRosettaMP (121k samples)?
   - Recommendation: Start with LPcode (smaller, 4 languages including Python)

2. **LLM choice for question generation:** Google Gemini
   - Consider: Cost, quality, latency

3. **Caching strategy:** How long to cache analysis results?
   - Consider: Repos change; stale results vs compute costs

4. **Confidence thresholds:** What score ranges map to verdicts?
   - Needs: Testing against known-good and known-bad repos to calibrate

---

## References

- LPcode: https://github.com/Shinwoo-Park/LPcode
- H-AIRosettaMP: https://huggingface.co/datasets/isThisYouLLM/H-AIRosettaMP
- DetectCodeGPT: https://github.com/YerbaPage/DetectCodeGPT
- Paper: "Detection of LLM-Paraphrased Code" (Park et al., 2025)
- Paper: "Is This You, LLM?" (Gurioli et al., 2025)
