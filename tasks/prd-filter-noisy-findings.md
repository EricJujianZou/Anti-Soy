# PRD: Remove Test Files, Logging & Error Handling from Evaluation

## Problem
Test file findings, logging analysis, and error handling analysis are noise. Recruiters don't care. Remove them completely — don't analyze them, don't score them, don't show them.

## What to Remove

### 1. Code Quality: Drop `error_handling` and `logging_quality` metrics entirely
These two metrics (currently 30% of the code quality score) should be removed from analysis, scoring, and display.

**Server — `server/v2/analyzers/code_quality.py`:**
- Remove `_analyze_error_handling()` method (lines 421-552)
- Remove `_analyze_logging()` method (lines 554-680+)
- Remove calls to both in `analyze()` (lines 109-110) and their findings from `findings.extend()` (lines 117-118)
- Remove `error_handling` and `logging_quality` from weighted score calculation (lines 122-129)
- Redistribute weights across remaining 4 metrics (`files_organized`, `test_coverage`, `readme_quality`, `dependency_health`) — these currently sum to 0.70, scale them to sum to 1.0

**Server — `server/v2/analyzers/code_quality.py` config:**
- Remove `"error_handling": 0.20` and `"logging_quality": 0.10` from `METRIC_WEIGHTS` dict (lines 37-38)
- Recalculate remaining weights to sum to 1.0. Current remaining: `files_organized: 0.15, test_coverage: 0.20, readme_quality: 0.15, dependency_health: 0.20`. Scale proportionally: `0.21, 0.29, 0.21, 0.29` (or round to taste).

**Server — `server/v2/schemas.py`:**
- Remove `error_handling` and `logging_quality` fields from `CodeQuality` model (lines 157-158)

**Client — `client/src/pages/RepoAnalysis.tsx`:**
- Remove the "Error Handling" and "Logging" display blocks (lines 533-544)

**Client — `client/src/services/api.ts`:**
- Remove `error_handling` and `logging_quality` from the TypeScript interface (lines 87-88)

**Client — `client/src/utils/scoring.ts`:**
- Remove all references to `error_handling` (lines 29, 62, 104, 135, 166, 195, 259)
- Remove `logging_quality` weight if present
- Adjust scoring weights to compensate

### 2. Bad Practices: Drop all robustness patterns related to error handling
The entire `ROBUSTNESS_PATTERNS` list in `bad_practices.py` is about error handling patterns (`no_timeout`, `silent_error`, `bare_except`, `unhandled_file_error`, `ignored_error`, `generic_exception`). Remove these.

**Server — `server/v2/analyzers/bad_practices.py`:**
- Remove `ROBUSTNESS_PATTERNS` list entirely (lines 187-309)
- Remove `ROBUSTNESS_PATTERNS` from `self.all_patterns` concatenation (line 396)
- Remove `robustness_issues` counting (line 423) and from the return object

**Server — `server/v2/schemas.py`:**
- Remove `robustness_issues` field from `BadPractices` model (if it exists as a separate field)

**Client:**
- Remove any display of `robustness_issues` count if rendered separately

### 3. Bad Practices: Drop `print_statements` detection
`_check_print_statements()` in `bad_practices.py` (lines 492-565) detects print/console.log usage. This is a logging concern — remove it.

**Server — `server/v2/analyzers/bad_practices.py`:**
- Remove `_check_print_statements()` method (lines 492-565)
- Remove `findings.extend(self._check_print_statements(repo_data))` call (line 418)

### 4. Test file findings: Skip test files entirely in bad_practices analysis
Currently test files are only skipped for hygiene checks. Skip them for ALL pattern matching.

**Server — `server/v2/analyzers/bad_practices.py`:**
- In `_analyze_file()` (line 437-490): If `is_test_file(file_path)`, return empty list immediately (don't run any patterns on test files)
- In `_check_env_committed()`, `_check_gitignore_issues()`, `_check_todo_comments()`: skip test file paths

### 5. LLM context: Filter test/error/logging findings before sending to Gemini
Even if some slip through, don't waste LLM context on them.

**Server — `server/v2/analysis_service.py`:**
- In `_build_findings_context()`: skip any finding where `is_test_file(finding.file)` returns True

## Files to Modify

| File | Change |
|------|--------|
| `server/v2/analyzers/code_quality.py` | Remove `_analyze_error_handling`, `_analyze_logging`, their calls, weights, and score contributions |
| `server/v2/analyzers/bad_practices.py` | Remove `ROBUSTNESS_PATTERNS`, `_check_print_statements()`, skip test files entirely in `_analyze_file()` |
| `server/v2/schemas.py` | Remove `error_handling`, `logging_quality` from `CodeQuality`; remove `robustness_issues` from `BadPractices` |
| `server/v2/analysis_service.py` | Filter test file findings in `_build_findings_context()` |
| `client/src/pages/RepoAnalysis.tsx` | Remove Error Handling and Logging display blocks |
| `client/src/services/api.ts` | Remove fields from TypeScript interfaces |
| `client/src/utils/scoring.ts` | Remove all `error_handling` / `logging_quality` references, adjust weights |

## Verification
- Run analysis on a repo. Verify: no error handling, logging, or robustness findings in Deep Dive. No `error_handling` or `logging_quality` metrics displayed. Code quality score only reflects organization, tests, readme, dependencies.
- Run on a repo with test files. Verify: zero findings from test files anywhere.
- Verify code quality scores are still reasonable (0-100 range, weighted correctly across 4 remaining metrics).
