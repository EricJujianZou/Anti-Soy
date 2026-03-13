# File Prioritization Improvement — Tech Spec

## Problem Statement

The current file selection system in `server/v2/data_extractor.py` has a 2MB total content cap (`MAX_TOTAL_CONTENT = 2 * 1024 * 1024`) that effectively limits analysis to ~15 files for larger codebases. This means important files in bigger repos get skipped entirely. The cap — not a hardcoded file count — is the actual constraint. Lifting it to 5MB allows more files to be read and analyzed, giving the scoring engine more data to work with.

Additionally, the file importance heuristics can be improved with better framework-aware entry point detection without requiring full import graph analysis (which would be too expensive).

## User Story

"As a system analyzing a candidate's repo, I want to read more of the codebase (up to 5MB) and prioritize the most important files, so that the AI detection and quality analysis has sufficient code to make accurate assessments."

## Design

### Change 1: Lift Content Cap

- Change `MAX_TOTAL_CONTENT` from `2 * 1024 * 1024` (2MB) to `5 * 1024 * 1024` (5MB).
- This is a single constant change on **line 24** of `server/v2/data_extractor.py`.

**Before:**
```python
MAX_TOTAL_CONTENT = 2 * 1024 * 1024  # 2MB total content
```

**After:**
```python
MAX_TOTAL_CONTENT = 5 * 1024 * 1024  # 5MB total content
```

### Change 2: Adaptive File Count

Instead of a fixed implicit limit of ~15 files (caused by the 2MB cap), make the file selection adaptive. Add three new constants and use them to compute a soft file target.

#### New Constants (add after `MAX_TOTAL_CONTENT` on line 24)

```python
FILE_TARGET_MIN = 15        # Always read at least 15 files
FILE_TARGET_PERCENTAGE = 0.15  # Read up to 15% of total code files
FILE_TARGET_MAX = 50        # Never read more than 50 files
```

#### Formula

```python
file_target = min(FILE_TARGET_MAX, max(FILE_TARGET_MIN, int(total_code_files * FILE_TARGET_PERCENTAGE)))
```

Where `total_code_files` is `len(all_files)` — the count of candidate files collected in Pass 1 (after filtering out skip dirs, skip extensions, blacklisted files, and files exceeding `MAX_FILE_SIZE`).

#### How the Adaptive Count Interacts with Pass 3

The adaptive file count is a **soft target**. The 5MB content cap (`MAX_TOTAL_CONTENT`) is the **hard limit**. In the Pass 3 loop, stop reading files when **either** condition is met:

1. The number of files read reaches `file_target`, OR
2. The total content size reaches `MAX_TOTAL_CONTENT`.

However, if a file would fit within the content cap but we have already reached `file_target`, we **stop** (do not keep trying smaller files). The adaptive count acts as a ceiling on files read, not just a suggestion.

#### Implementation Detail for Pass 3

The current Pass 3 loop (lines 296-316) iterates over all files sorted by importance and uses `continue` to skip files that would exceed the content cap. Modify this loop as follows:

**Before (current code, lines 296-316):**
```python
# PASS 3: Read content in importance order until limit
total_content_size = 0

for file_info in all_files:
    if total_content_size + file_info.size > MAX_TOTAL_CONTENT:
        continue  # Skip this file, but keep trying smaller ones

    try:
        content = file_info.abs_path.read_text(encoding="utf-8", errors="ignore")
        result.files[file_info.rel_path] = content
        result.file_importance[file_info.rel_path] = file_info.importance_score
        total_content_size += len(content)

        # Track language bytes
        suffix = file_info.abs_path.suffix.lower()
        if suffix in CODE_EXTENSIONS:
            lang = EXTENSION_TO_LANGUAGE.get(suffix)
            if lang:
                result.languages[lang] = result.languages.get(lang, 0) + file_info.size

    except (OSError, IOError):
        continue
```

**After:**
```python
# PASS 3: Read content in importance order until limit
total_content_size = 0
files_read = 0
file_target = min(FILE_TARGET_MAX, max(FILE_TARGET_MIN, int(len(all_files) * FILE_TARGET_PERCENTAGE)))

for file_info in all_files:
    # Stop if we've hit the adaptive file count target
    if files_read >= file_target:
        break

    # Skip if this file would exceed the hard content cap
    if total_content_size + file_info.size > MAX_TOTAL_CONTENT:
        continue  # Skip this file, but keep trying smaller ones

    try:
        content = file_info.abs_path.read_text(encoding="utf-8", errors="ignore")
        result.files[file_info.rel_path] = content
        result.file_importance[file_info.rel_path] = file_info.importance_score
        total_content_size += len(content)
        files_read += 1

        # Track language bytes
        suffix = file_info.abs_path.suffix.lower()
        if suffix in CODE_EXTENSIONS:
            lang = EXTENSION_TO_LANGUAGE.get(suffix)
            if lang:
                result.languages[lang] = result.languages.get(lang, 0) + file_info.size

    except (OSError, IOError):
        continue
```

Key differences:
- Added `files_read` counter initialized to 0.
- Added `file_target` computation using the formula.
- Added `break` when `files_read >= file_target` (stop entirely, do not keep scanning).
- The content cap `continue` remains as-is (skip files too large for remaining budget, try smaller ones).
- Incremented `files_read` after a successful read.

### Change 3: Improved Framework-Aware Heuristics

Add better entry point and important file detection for common frameworks. These are **additions** to the existing scoring system in `_calculate_file_importance()`, NOT replacements.

#### Where to Add

Insert a new scoring block inside `_calculate_file_importance()` **after** the existing "Core application directories" block (after line 369) and **before** the "Backend/server code" block (line 372). This keeps the logical grouping: entry points first, then framework signals, then general directory signals.

#### New Block to Add

Add the following code block. It uses `fnmatch` for glob-style matching against `rel_path`:

```python
# Framework-aware entry points and important files
import fnmatch

framework_patterns = {
    # Next.js pages and app directory
    "pages/**/*.tsx": 20,
    "pages/**/*.ts": 20,
    "pages/**/*.jsx": 20,
    "pages/**/*.js": 20,
    "app/**/*.tsx": 20,
    "app/**/page.tsx": 20,
    "app/**/page.ts": 20,
    "app/**/page.jsx": 20,
    "app/**/page.js": 20,
    # Express routes
    "routes/**/*.js": 20,
    "routes/**/*.ts": 20,
    "router/**/*.js": 20,
    "router/**/*.ts": 20,
    # Django
    "*/views.py": 20,
    "*/urls.py": 20,
    "*/models.py": 20,
    "*/serializers.py": 20,
    # Flask
    # (app.py and routes.py already covered by entry_points; views.py covered by Django block)
    # FastAPI
    "routers/**/*.py": 20,
    "endpoints/**/*.py": 20,
    # Spring
    "*Controller.java": 20,
    "*Service.java": 20,
    "*Repository.java": 20,
    # .NET
    "*Controller.cs": 20,
    # (Startup.cs and Program.cs already covered by entry_points)
    # Go
    "cmd/**/*.go": 15,
    "internal/**/*.go": 15,
    # Rust
    "src/main.rs": 20,
    "src/lib.rs": 20,
    "src/bin/**/*.rs": 20,
    # GraphQL
    "*.graphql": 15,
    "resolvers/**/*": 15,
    # Database
    "schema.sql": 10,
    "models/**/*": 10,
}

for pattern, bonus in framework_patterns.items():
    if fnmatch.fnmatch(path_lower, pattern):
        score += bonus
        break  # Only apply one framework bonus per file to avoid double-counting
```

**Important implementation notes:**

1. The `import fnmatch` statement must go at the **top of the file** (line 4 area, with the other imports), NOT inside the function. The block above shows it inline for illustration only.

2. Use `fnmatch.fnmatch(path_lower, pattern)` — this matches the relative path against glob patterns. The `path_lower` variable is already available in the function (line 350).

3. The `break` after the first match prevents a single file from getting multiple framework bonuses (e.g., `models/user.py` matching both `*/models.py` and `models/**/*`).

4. Some patterns overlap with existing entry points (e.g., `app.py`, `Startup.cs`, `Program.cs`). This is fine — a file can get both the entry point bonus (+40) and a framework bonus (+20). Files like `app.py` are genuinely important enough to warrant both bonuses.

5. For Go `handler*.go` pattern: add a separate filename check since `fnmatch` on the full path would need `**/handler*.go`:

```python
# Go handler files (checked by filename)
if fnmatch.fnmatch(filename, "handler*.go"):
    score += 15
```

Add this immediately after the framework_patterns loop.

6. For Django/Flask patterns like `views.py`, `urls.py`, `models.py`, `serializers.py`: the pattern `*/views.py` matches these files in any subdirectory one level deep. However, `fnmatch` treats `*` as matching everything except `/`. To match at any depth, use the pattern `**/views.py` or check the filename directly. Since `fnmatch` does NOT support `**` in all Python versions the same way, use a **filename-based check** instead:

```python
# Django/Flask important files (by filename, any directory depth)
django_flask_files = {"views.py", "urls.py", "serializers.py"}
if filename in django_flask_files:
    score += 20
```

Add this as a separate check before or after the framework_patterns loop. Note: `models.py` is intentionally excluded here because it would match too broadly (every ORM-based project has models). Instead, `models.py` files already get a boost from the `models` entry in `core_dirs` (+15).

#### Revised Complete Implementation

Given the `fnmatch` limitations with `**`, here is the exact implementation to use. This replaces the pattern-dict approach with explicit, reliable checks:

```python
    # -----------------------------------------------------------------
    # FRAMEWORK-AWARE HEURISTICS (additive bonuses)
    # -----------------------------------------------------------------

    # Next.js pages and app directory
    if (path_lower.startswith("pages/") or path_lower.startswith("app/")) and \
       filename.endswith((".tsx", ".ts", ".jsx", ".js")):
        score += 20

    # Express/Node routes
    if (path_lower.startswith("routes/") or path_lower.startswith("router/") or
        "/routes/" in path_lower or "/router/" in path_lower) and \
       filename.endswith((".js", ".ts")):
        score += 20

    # Django / Flask important files
    django_flask_files = {"views.py", "urls.py", "serializers.py"}
    if filename in django_flask_files:
        score += 20

    # FastAPI routers and endpoints
    if ("/routers/" in path_lower or path_lower.startswith("routers/") or
        "/endpoints/" in path_lower or path_lower.startswith("endpoints/")) and \
       filename.endswith(".py"):
        score += 20

    # Spring Java
    spring_suffixes = ("controller.java", "service.java", "repository.java")
    if filename.endswith(spring_suffixes):
        score += 20

    # .NET Controllers
    if filename.endswith("controller.cs"):
        score += 20

    # Go entry points and handlers
    if (path_lower.startswith("cmd/") or "/cmd/" in path_lower) and filename.endswith(".go"):
        score += 15
    if (path_lower.startswith("internal/") or "/internal/" in path_lower) and filename.endswith(".go"):
        score += 15
    if filename.startswith("handler") and filename.endswith(".go"):
        score += 15

    # Rust crate entry points
    rust_entry = {"main.rs", "lib.rs"}
    if filename in rust_entry and "src/" in path_lower:
        score += 20
    if path_lower.startswith("src/bin/") and filename.endswith(".rs"):
        score += 20

    # GraphQL
    if filename.endswith(".graphql"):
        score += 15
    if "/resolvers/" in path_lower or path_lower.startswith("resolvers/"):
        score += 15

    # Database schema
    if filename == "schema.sql":
        score += 10
```

This block should be inserted in `_calculate_file_importance()` between the "Core application directories" block and the "Backend/server code" block — specifically, **after line 369** (after the `core_dirs` score adjustment) and **before line 372** (before the `server`/`backend`/`api` check).

No new imports are needed with this approach (no `fnmatch`).

### What NOT to Change

- `MAX_FILE_SIZE` (200KB per file, line 23) — keep as-is.
- The existing importance scoring logic (entry points +40, core dirs +15, etc.) — keep every line as-is, only ADD the new framework block.
- The file skip/blacklist logic (`SKIP_EXTENSIONS`, `SKIP_DIRS`, `BLACKLIST_FILES`) — keep as-is.
- The 3-pass extraction algorithm structure — keep as-is. The only modification to Pass 3 is adding the `files_read` counter and `file_target` soft limit.
- No import graph analysis — too expensive, requires reading all files upfront.
- The `_get_git_commits`, `_extract_dependencies`, `_calculate_total_loc`, `clone_repository` functions — no changes.
- The `RepoData`, `CommitInfo`, `FileInfo` dataclasses — no changes.
- All parser functions (`_parse_requirements_txt`, `_parse_package_json`, etc.) — no changes.

## Implementation Plan

These are the exact steps, in order:

1. **Read** `server/v2/data_extractor.py` to confirm line numbers match this spec.
2. **Line 24**: Change `MAX_TOTAL_CONTENT` from `2 * 1024 * 1024` to `5 * 1024 * 1024`. Update the comment to say `5MB total content`.
3. **After line 24**: Add three new constants:
   ```python
   FILE_TARGET_MIN = 15
   FILE_TARGET_PERCENTAGE = 0.15
   FILE_TARGET_MAX = 50
   ```
4. **In `_calculate_file_importance()`** (currently lines 334-433): Insert the framework-aware heuristics block from the "Revised Complete Implementation" section above. Insert it after the `core_dirs` block (after line 369) and before the "Backend/server code" block (line 372).
5. **In `extract_repo_data()`, Pass 3** (currently lines 296-316): Add the `files_read` counter, compute `file_target`, add the `break` condition. See the exact "After" code in Change 2 above.
6. **Verify**: Read the modified file to confirm:
   - `MAX_TOTAL_CONTENT` is `5 * 1024 * 1024`
   - `MAX_FILE_SIZE` is still `200 * 1024` (unchanged)
   - The three new constants exist
   - The framework heuristics block is present inside `_calculate_file_importance()`
   - Pass 3 has the `files_read` counter and `file_target` logic
   - No other functions were modified

## Files to Modify

- `server/v2/data_extractor.py` — constants (lines 23-24), scoring function (lines 334-433), selection loop (lines 296-316)

No other files need to be modified. No new files need to be created.

## Risks & Tradeoffs

### Risk: Increased memory usage
5MB of code content per repo (up from 2MB) increases memory pressure during analysis. With 4 concurrent batch items, worst case is 20MB of code in memory (up from 8MB). This is manageable even on Cloud Run's 512MB instances, but worth noting.

### Risk: Increased processing time
More files = more code to analyze through the AI slop, bad practices, and code quality analyzers. Expected increase: ~2.5x per repo (proportional to content increase). Mitigation: the 50-file cap bounds the worst case.

### Risk: Framework detection false positives
A file matching `pages/*.tsx` might not actually be a Next.js page (could be a different framework). Mitigation: the bonus is only +20 (not dominant), and it's additive — a bad file still gets penalized by other signals.

### Risk: Adaptive count `break` vs `continue` semantics
The current Pass 3 uses `continue` when a file exceeds the content cap, meaning it keeps scanning for smaller files that fit. The new `file_target` check uses `break`, which stops scanning entirely. This is intentional: once we have enough files, we stop. However, this means if the top 50 files by importance include a few large files that are skipped (via `continue`), we might read fewer than 50 files total because the `files_read` counter only increments on successful reads. This is acceptable behavior — the content cap is the hard limit, and the adaptive count is a soft target.

### Rejected Alternatives

- **Import graph analysis:** Would provide the best file ranking but requires reading all files first, defeating the purpose of selective reading. Too expensive for the marginal benefit.
- **Raise cap to 10MB:** Diminishing returns. Most repos' important files are well within 5MB. Higher caps increase memory and processing time without proportional quality improvement.
- **No file cap at all:** Unbounded memory and processing time. Some repos have thousands of files. A cap is necessary.
- **Using `fnmatch` for pattern matching:** While cleaner syntactically, `fnmatch` has inconsistent `**` support across Python versions and adds an import dependency for marginal benefit. Direct string checks are more reliable and easier to debug.

## Testing & Verification

1. **Small repo (<15 files):** Should read all files (same as before). `file_target = max(15, int(10 * 0.15)) = 15`, but only 10 files exist, so all are read.
2. **Medium repo (50-100 files):** Should read ~15 files. `file_target = max(15, int(75 * 0.15)) = 15` for 75 files; `max(15, int(100 * 0.15)) = 15` for 100 files.
3. **Large repo (200 files):** Should read ~30 files. `file_target = max(15, int(200 * 0.15)) = 30`.
4. **Very large repo (500+ files):** Should read up to 50 files or 5MB, whichever hits first. `file_target = min(50, int(500 * 0.15)) = 50`.
5. **Framework-specific files:** Verify that `pages/index.tsx`, `views.py`, `UserController.java`, `src/main.rs` etc. get higher importance scores than generic utility files.
6. **Regression check:** Compare analysis quality before/after for a known repo. More findings expected due to more files being read.

## Guardrails for Implementing Agent

- **ASK before assuming** if any requirement is ambiguous. Do not guess.
- Do NOT modify `MAX_FILE_SIZE` (the per-file limit, line 23).
- Do NOT remove or modify existing importance scoring — only ADD new patterns.
- Do NOT implement import graph analysis.
- The 5MB cap is a HARD limit. The adaptive file count is a SOFT target. Content cap always wins.
- Keep the 3-pass algorithm structure intact — modify within it, do not restructure it.
- Do NOT modify any functions other than `extract_repo_data()` and `_calculate_file_importance()`.
- Do NOT add any new imports.
- Do NOT modify any dataclasses (`RepoData`, `CommitInfo`, `FileInfo`).
- Do NOT modify the blacklist, skip, or include file lists.
- The `break` in Pass 3 for `file_target` is intentional — do NOT change it to `continue`.
