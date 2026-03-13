# Emoji False Positives Fix — Tech Spec

## Problem Statement

The current emoji detection in `_detect_emojis()` (in `server/v2/analyzers/ai_slop.py`, lines 356-419) flags ALL emoji occurrences in code files with +15 to the AI score per emoji. This creates false positives when emojis appear in legitimate display contexts — JSX/HTML content, UI strings, template literals. For example, a React component rendering `<h1>🎉 Welcome!</h1>` gets flagged as AI-generated code, when the emoji is simply part of the app's UI content.

The emoji detection is currently the MAIN indicator for AI usage and also the MAIN source of false positives. This fix narrows the scope to high-confidence signals only.

## User Story

"As a recruiter, I want AI detection to accurately flag suspicious emoji usage (in code comments and commit messages) without penalizing apps that legitimately display emojis in their UI."

---

## Design

### What Gets Flagged (AI signal)

1. **Emojis in code comments** — `# 🔥 This function handles auth` or `// 🚀 Fast lookup` is classic AI slop
2. **Emojis in print/log/console statements** — `print("🚀 Server started")` or `console.log("✅ Done")` is suspicious (most professional codebases don't use emoji in logs)
3. **Emojis in commit messages** — Already detected and should be PRESERVED as-is (no changes to commit message detection)

### What Gets Excluded (false positive)

1. **Emojis in JSX/HTML content** — `<span>🎉</span>`, `<h1>🚀 Welcome</h1>`
2. **Emojis in string literals used for display** — UI content strings, i18n translation values
3. **Emojis in template literals for UI** — `` `${emoji} Welcome` `` when used in rendering context
4. **Emojis in test data/fixtures** — Test strings containing emojis for testing emoji handling

### Classification Contexts

Each line containing an emoji is classified into one of four contexts:

| Context      | Flagged? | Description |
|-------------|----------|-------------|
| `"comment"` | YES      | Emoji appears inside a code comment |
| `"print_log"` | YES    | Emoji appears inside a print/log/console statement |
| `"display"` | NO       | Emoji appears in JSX/HTML content or a string literal not in comment/print context |
| `"code"`    | NO       | Emoji appears in code in a context that doesn't match the above (default fallback — conservative, don't flag) |

**Key change:** The current code flags `"code"` context emojis. The new behavior does NOT flag them. Only `"comment"` and `"print_log"` are flagged.

---

## Implementation Approach

### Step 1: Add `classify_emoji_context()` Helper Function

Add a new standalone helper function **above** the `AISlopAnalyzer` class definition (after the config section, before line 220). This function classifies what context an emoji appears in on a given line.

**Function signature:**

```python
def classify_emoji_context(line: str, file_path: str, in_block_comment: bool) -> str:
    """
    Classify the context of an emoji on a given line.

    Args:
        line: The full line of source code containing the emoji.
        file_path: The file path (used to determine language from extension).
        in_block_comment: Whether this line is inside a multi-line block comment (/* ... */).

    Returns:
        One of: "comment", "print_log", "display", "code"
    """
```

**Why `file_path` instead of `language`:** The existing codebase already uses `file_path.endswith(...)` patterns for language detection (see `_detect_redundant_comments` at lines 319-329). Reuse the same pattern for consistency. The function internally determines language from the file extension.

**Why `in_block_comment` as a parameter:** Block comment state (`/* ... */`) must be tracked across lines by the caller (the main scanning loop). The helper function is stateless and receives this as input.

### Step 2: Classification Logic Inside `classify_emoji_context()`

The function applies checks in priority order. The FIRST match wins.

#### Priority 1: Block Comment (all languages except Python)

```python
if in_block_comment:
    return "comment"
```

#### Priority 2: Line Comment

Detect if the emoji is in a line comment. The logic depends on language:

**Python files** (`.py`):
```python
stripped = line.lstrip()
if stripped.startswith('#'):
    return "comment"
```

Also check for inline comments: if `#` appears in the line before the emoji position AND the `#` is not inside a string literal. Use a simple heuristic: find the first `#` that is not enclosed in quotes.

**JS/TS/Go/C#/Java/C/C++/Rust/Swift/Kotlin/Scala/PHP files** (all files ending with `.js`, `.ts`, `.jsx`, `.tsx`, `.go`, `.cs`, `.java`, `.c`, `.cpp`, `.h`, `.hpp`, `.rs`, `.swift`, `.kt`, `.scala`, `.php`):
```python
stripped = line.lstrip()
if stripped.startswith('//'):
    return "comment"
if stripped.startswith('/*'):
    return "comment"
```

Also check for inline `//` comments the same way as Python's `#` check.

**Shell files** (`.sh`, `.bash`):
```python
stripped = line.lstrip()
if stripped.startswith('#'):
    return "comment"
```

**Python docstrings** (`"""..."""` or `'''...'''`): Treat as comment context. Detect by checking if the stripped line starts with `"""` or `'''`. This is a simplification — it won't catch all docstring lines, but it catches the common case.

#### Priority 3: Print/Log Statement

Check if the line contains a print or logging call. This check is language-aware:

**Python:**
- Patterns: `print(`, `logging.`, `logger.`, `log.`

**JavaScript/TypeScript:**
- Patterns: `console.log(`, `console.warn(`, `console.error(`, `console.info(`, `console.debug(`

**Go:**
- Patterns: `fmt.Print`, `fmt.Println`, `fmt.Printf`, `fmt.Sprint`, `fmt.Sprintf`, `log.Print`, `log.Println`, `log.Printf`, `log.Fatal`, `log.Fatalf`

**C#:**
- Patterns: `Console.Write`, `Console.WriteLine`, `Debug.Log`, `Trace.Write`

**Java:**
- Patterns: `System.out.print`, `System.err.print`, `logger.`, `log.`

**All languages (generic fallback):**
- Patterns: `print(`, `log(`, `warn(`, `error(`

Use case-sensitive matching for these patterns (e.g., `Console.Write` not `console.write`). Check using simple `in` operator on the line string.

```python
# Example for Python
if file_path.endswith('.py'):
    if any(pat in line for pat in ['print(', 'logging.', 'logger.', 'log.']):
        return "print_log"
```

If the line matches a print/log pattern, return `"print_log"`.

#### Priority 4: Display Context (JSX/HTML)

Check if the emoji is in a display/UI context. This is the main false-positive filter.

**JSX/HTML indicators** (for `.jsx`, `.tsx`, `.vue`, `.svelte` files, AND any file where the line contains HTML-like patterns):

A line is considered "display context" if ANY of these are true:
- Line contains a JSX/HTML tag pattern: regex `<\w+[>\s/]` or `</\w+>` (opening or closing tags)
- Line contains JSX attribute patterns: `className=`, `style=`, `dangerouslySetInnerHTML`
- Line contains HTML entities or `&nbsp;`, `&amp;`, etc.

```python
import re
JSX_HTML_PATTERN = re.compile(r'<\w+[\s>/]|</\w+>')
```

```python
if file_path.endswith(('.jsx', '.tsx', '.vue', '.svelte')):
    if JSX_HTML_PATTERN.search(line):
        return "display"
```

For non-JSX files: do NOT apply this check (a `<` in Python is a comparison operator, not an HTML tag).

#### Priority 5: String-Only Context (Generic Display)

If the emoji is inside a string literal and not in a comment or print/log context, classify as `"display"`.

**Heuristic:** Check if the line (stripped) is primarily a string assignment or return of a string. Use a simple approach:
- If the emoji appears between matching quotes (`"..."`, `'...'`, `` `...` ``), and the line does NOT match comment or print/log patterns, return `"display"`.

**Implementation approach for string detection:**
```python
# Find all string regions in the line (simplified: find quoted regions)
# Check if the emoji position falls inside a quoted region
# This is a best-effort heuristic, not a full parser
```

A simpler alternative (recommended for MVP): for non-JSX files, if the line is NOT a comment and NOT a print/log, check whether the emoji appears inside quotes. Use a regex to find all quoted string regions and check if the emoji falls within one:

```python
STRING_PATTERN = re.compile(r'''("(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*'|`(?:[^`\\]|\\.)*`)''')
```

Find all string spans in the line. For each emoji match position, check if it falls inside a string span. If ALL emojis on the line are inside string spans and the line is not a print/log line, return `"display"`.

#### Priority 6: Default Fallback

If none of the above matched, return `"code"`.

**IMPORTANT:** The old behavior classified these as `"code"` and still flagged them. The NEW behavior returns `"code"` and does NOT flag them. This is a deliberate decision — when we can't confidently classify, we err on the side of not flagging (reducing false positives at the cost of some false negatives).

---

### Step 3: Add Block Comment State Tracking

Add a helper function to track block comment state across lines:

```python
def _update_block_comment_state(line: str, in_block_comment: bool) -> bool:
    """
    Update block comment tracking state for /* ... */ style comments.

    Args:
        line: Current line of source code.
        in_block_comment: Whether we were inside a block comment before this line.

    Returns:
        Whether we are inside a block comment after processing this line.
    """
```

Logic:
- If `in_block_comment` is True, check if `*/` appears in the line. If so, return False. Otherwise, return True.
- If `in_block_comment` is False, check if `/*` appears in the line. If so, check if `*/` also appears (single-line block comment). If only `/*`, return True. Otherwise return False.

This is a simplified state machine. It does NOT handle nested block comments or `/*` inside strings. This is acceptable for a scoring heuristic.

**This function should NOT be applied to Python files** (Python doesn't have `/* */` comments). The caller should skip block comment tracking for `.py`, `.sh`, `.bash` files.

---

### Step 4: Modify `_detect_emojis()` Method

Modify the existing `_detect_emojis()` method in `AISlopAnalyzer` (lines 356-419). The changes are:

#### 4a: Add block comment state tracking to the per-file loop

```python
for file_path, content in repo_data.files.items():
    if not is_code_file(file_path):
        continue

    lines = content.split('\n')
    in_block_comment = False  # NEW: track block comment state
    uses_block_comments = not file_path.endswith(('.py', '.sh', '.bash'))  # NEW

    for line_num, line in enumerate(lines, 1):
        # NEW: update block comment state
        if uses_block_comments:
            in_block_comment = _update_block_comment_state(line, in_block_comment)

        # ... existing emoji detection ...
```

#### 4b: Classify context using the new helper

Replace the existing context classification block (lines 382-389):

```python
# OLD:
stripped = line.strip()
if stripped.startswith('#') or stripped.startswith('//') or stripped.startswith('/*'):
    context = "comment"
elif 'print' in line.lower() or 'console.log' in line.lower() or 'logger' in line.lower():
    context = "print/log"
else:
    context = "code"
```

With:

```python
# NEW: Use context classifier
context = classify_emoji_context(line, file_path, in_block_comment)
```

#### 4c: Only append to findings if context is flaggable

Change the findings append logic. Currently, ALL emoji occurrences are appended to findings. Change to:

```python
if context in ("comment", "print_log"):
    # Flagged: add to findings (affects score)
    findings.append(EmojiFinding(
        file_path=file_path,
        line_number=line_num,
        emoji=emojis_found[0],
        context=context,
        snippet=snippet[:300] if len(snippet) > 300 else snippet,
    ))
else:
    # Not flagged: track as display emoji (informational only)
    display_findings.append(EmojiFinding(
        file_path=file_path,
        line_number=line_num,
        emoji=emojis_found[0],
        context=context,
        snippet=snippet[:300] if len(snippet) > 300 else snippet,
    ))
```

#### 4d: Return both lists

Change the return type and signature of `_detect_emojis()`:

**Old signature:**
```python
def _detect_emojis(self, repo_data: RepoData) -> list[EmojiFinding]:
```

**New signature:**
```python
def _detect_emojis(self, repo_data: RepoData) -> tuple[list[EmojiFinding], list[EmojiFinding]]:
    """
    Detect emojis in code comments, print statements, and commit messages.

    Returns:
        Tuple of (flagged_findings, display_findings).
        - flagged_findings: emojis in comments/print/logs/commits (affect score)
        - display_findings: emojis in display/UI context (informational, don't affect score)
    """
```

#### 4e: Commit message detection — NO CHANGES

The commit message emoji detection block (lines 404-417) remains exactly as-is. Commit message emojis are always added to `findings` (the flagged list), never to `display_findings`.

---

### Step 5: Update `analyze()` Method Call Site

In the `analyze()` method (line 274), update the call to `_detect_emojis()`:

**Old:**
```python
emoji_findings = self._detect_emojis(repo_data)
```

**New:**
```python
emoji_findings, display_emoji_findings = self._detect_emojis(repo_data)
```

The `emoji_findings` list (flagged only) continues to be passed to `_calculate_score()` and `_convert_to_findings()` exactly as before. The `display_emoji_findings` list is passed to `_convert_to_findings()` for informational reporting.

Update the call to `_convert_to_findings()`:

**Old:**
```python
negative_signals = self._convert_to_findings(redundant_findings, emoji_findings)
```

**New:**
```python
negative_signals = self._convert_to_findings(redundant_findings, emoji_findings, display_emoji_findings)
```

---

### Step 6: Update `_convert_to_findings()` for Display Emoji Reporting

Update the method signature:

**Old:**
```python
def _convert_to_findings(
    self,
    redundant_findings: list[RedundantCommentFinding],
    emoji_findings: list[EmojiFinding],
) -> list[Finding]:
```

**New:**
```python
def _convert_to_findings(
    self,
    redundant_findings: list[RedundantCommentFinding],
    emoji_findings: list[EmojiFinding],
    display_emoji_findings: list[EmojiFinding] | None = None,
) -> list[Finding]:
```

After the existing emoji findings block (which produces the `"emoji_in_code"` finding for flagged emojis), add an informational finding for display emojis:

```python
# 3. Handle display emojis (informational, not scored)
if display_emoji_findings:
    count = len(display_emoji_findings)
    unique_display_emojis = set(f.emoji for f in display_emoji_findings)
    emoji_display = ' '.join(sorted(unique_display_emojis)[:10])

    findings.append(Finding(
        type="emoji_in_display",
        severity=Severity.INFO,
        file="Multiple locations" if count > 1 else display_emoji_findings[0].file_path,
        line=display_emoji_findings[0].line_number,
        snippet=f"{count} emoji(s) found in display/UI context (not flagged)",
        explanation=f"Emojis found in UI/display context: {emoji_display}. These appear in JSX/HTML content or string literals and are not counted as AI signals.",
    ))
```

**Note:** This requires `Severity.INFO` to exist. Check the `Severity` enum in `schemas.py`. If `INFO` does not exist, add it. Here is what to check:

```python
# In server/v2/schemas.py, the Severity enum:
class Severity(str, Enum):
    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"        # <-- Make sure this exists. If not, add it.
```

---

### Step 7: Update `EmojiFinding.context` Type Hint

The existing `EmojiFinding` dataclass (line 231-237) has:

```python
context: str  # "comment", "print", or "commit"
```

Update the comment to reflect the new context values:

```python
context: str  # "comment", "print_log", "display", "code", or "commit"
```

Also update the existing code that checks `f.context != "commit"` in `_convert_to_findings()` — this check still works correctly since the only non-file context is `"commit"`.

---

## Compile-Time Constants to Add

Add these regex patterns near the top of the file, in the CONFIGURATION section after `EMOJI_BONUS` (after line 79):

```python
# Context classification patterns for emoji false-positive filtering
# JSX/HTML tag pattern - matches opening or closing tags
JSX_HTML_PATTERN = re.compile(r'<\w+[\s>/]|</\w+>')

# String literal pattern - matches quoted strings (double, single, backtick)
# Used to check if an emoji falls inside a string region
STRING_REGION_PATTERN = re.compile(r'''("(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*'|`(?:[^`\\]|\\.)*`)''')

# Print/log patterns by language group
PYTHON_PRINT_PATTERNS = ('print(', 'logging.', 'logger.', 'log.')
JS_PRINT_PATTERNS = ('console.log(', 'console.warn(', 'console.error(', 'console.info(', 'console.debug(')
GO_PRINT_PATTERNS = ('fmt.Print', 'fmt.Println', 'fmt.Printf', 'fmt.Sprint', 'fmt.Sprintf',
                     'log.Print', 'log.Println', 'log.Printf', 'log.Fatal', 'log.Fatalf')
CSHARP_PRINT_PATTERNS = ('Console.Write', 'Console.WriteLine', 'Debug.Log', 'Trace.Write')
JAVA_PRINT_PATTERNS = ('System.out.print', 'System.err.print', 'logger.', 'log.')
GENERIC_PRINT_PATTERNS = ('print(', 'log(', 'warn(', 'error(')
```

---

## Files to Modify

| File | What Changes |
|------|-------------|
| `server/v2/analyzers/ai_slop.py` | Add `classify_emoji_context()` and `_update_block_comment_state()` helper functions; modify `_detect_emojis()` to use context classification and split findings; update `analyze()` call site; update `_convert_to_findings()` signature and add display emoji reporting; add new regex constants; update `EmojiFinding` docstring |
| `server/v2/schemas.py` | Add `Severity.INFO` if it doesn't already exist |

---

## What NOT to Change

- The `COMMON_EMOJIS` set (the 40+ tracked emojis) — keep exactly as-is
- The `EMOJI_PATTERN` regex — keep exactly as-is
- The `EMOJI_BONUS` value of `+15` — keep exactly as-is
- The overall scoring formula in `_calculate_score()` — keep exactly as-is (it receives `emoji_count` which now only counts flagged emojis)
- Commit message emoji detection — keep exactly as-is
- The `_detect_redundant_comments()` method — no changes
- The `_detect_positive_signals()` method — no changes

---

## Edge Cases

| Scenario | Expected Behavior | Reason |
|----------|-------------------|--------|
| Multi-line block comment `/* ... */` spanning 5 lines with emoji on line 3 | Flagged as `"comment"` | Block comment state tracking handles this |
| Python docstring `"""🚀 Fast module"""` | Flagged as `"comment"` | Line starting with `"""` detected as docstring |
| `f"🚀 {message}"` inside a `print()` call | Flagged as `"print_log"` | Print/log check has higher priority than string check |
| `<h1>🎉 Welcome!</h1>` in a `.tsx` file | Excluded as `"display"` | JSX/HTML pattern detected |
| `title = "🎉 Welcome"` in a `.py` file (not in print/comment) | Excluded as `"display"` | Emoji inside string, not in comment/print context |
| `ERROR_MSG = "❌ Failed to connect"` in a `.py` file | Excluded as `"display"` | Emoji inside string — accepted as a precision tradeoff (see Risks) |
| Emoji in variable name `fire🔥count = 0` | Classified as `"code"`, NOT flagged | Falls through to default; conservative approach |
| `# 🔥 TODO: fix this` | Flagged as `"comment"` | Line starts with `#` |
| `x = 5  # 🚀 fast` (inline comment) | Flagged as `"comment"` | Inline `#` detected before emoji position |
| `url = "http://example.com#🔥fragment"` | Excluded as `"display"` | `#` is inside a string, emoji is inside a string — string detection takes precedence |
| `console.log("✅ Done")` in `.js` file | Flagged as `"print_log"` | Console.log pattern matched |
| Emoji in a `.sql` file comment `-- 🎉 migration` | Classified as `"code"`, NOT flagged | SQL `--` comments are not handled (acceptable gap — SQL files rarely have AI emoji slop) |
| `<Component emoji="🎉" />` in `.tsx` | Excluded as `"display"` | JSX pattern detected |

---

## Risks & Tradeoffs

### Risk: Over-filtering (Reduced Recall)

Some AI-generated code puts emojis in string literals that are not truly "display" content (e.g., `ERROR_MSG = "❌ Failed to connect"`). These would be excluded as string-context. **Accept this** as a small loss in recall for a large gain in precision. The emoji-in-comments signal is much stronger and more reliable.

### Risk: Parsing Complexity

Properly detecting comment vs string context requires basic parsing. A regex-based approach will not handle all edge cases (e.g., `#` inside a Python string on the same line as a real comment). **Mitigation:** Use a conservative approach — only classify as `"comment"` or `"print_log"` when there is strong evidence. When in doubt, classify as `"display"` or `"code"` (don't flag).

### Risk: Block Comment State Bugs

The simplified block comment tracker does not handle `/*` inside strings or nested comments. **Mitigation:** This is rare in practice. The worst case is a few emojis incorrectly classified as "comment" when they are inside a string that happens to follow a `/*` — this would be a false positive for flagging, not a false negative. Since we are trying to REDUCE false positives, this edge case works against us slightly, but the occurrence rate is negligible.

### Rejected Alternatives

| Alternative | Why Rejected |
|------------|--------------|
| AST-based parsing | Too heavy for a scoring heuristic. Would require language-specific parsers for Python, JS, Go, C#, etc. Regex + heuristics is sufficient for this use case. |
| Remove emoji detection entirely | Emojis in comments remain a strong AI signal. The fix should narrow scope, not eliminate the feature. |
| Reduce `EMOJI_BONUS` instead of filtering | Doesn't solve the problem — even at +5, a React app with 10 UI emojis would get +50 incorrectly. |
| Whitelist specific file extensions (only scan `.py`) | Too restrictive. AI slop appears in all languages. |

---

## Testing & Verification

### Manual Test Cases

Create test inputs (as string content passed to `_detect_emojis()` via a mock `RepoData`) for each case:

1. **React component with emojis in JSX** (file: `App.tsx`)
   ```tsx
   export function App() {
     return <h1>🎉 Welcome!</h1>;
   }
   ```
   Expected: 0 flagged findings, 1 display finding

2. **Python file with emojis in comments** (file: `app.py`)
   ```python
   # 🔥 This function handles auth
   def authenticate(user):
       pass
   ```
   Expected: 1 flagged finding (context: "comment")

3. **Python file with emojis in print** (file: `server.py`)
   ```python
   print("🚀 Server started on port 8080")
   ```
   Expected: 1 flagged finding (context: "print_log")

4. **Mixed file — emojis in both comments and strings** (file: `mixed.py`)
   ```python
   # ✨ Magic function
   title = "🎉 Celebration"
   print("🚀 Starting...")
   ```
   Expected: 2 flagged findings (comment + print_log), 1 display finding (string)

5. **Commit messages with emojis**
   Expected: Flagged as before (no change)

6. **Block comment with emoji** (file: `app.js`)
   ```javascript
   /* 🔥 This module handles
      all the authentication
      logic for the app */
   ```
   Expected: 1 flagged finding (context: "comment")

7. **JSX with emoji in attribute** (file: `Button.tsx`)
   ```tsx
   <Button label="🎉 Click me" onClick={handleClick} />
   ```
   Expected: 0 flagged findings, 1 display finding

8. **Go file with emoji in fmt.Println** (file: `main.go`)
   ```go
   fmt.Println("🚀 Server starting...")
   ```
   Expected: 1 flagged finding (context: "print_log")

### Regression Testing

Run the full analyzer against existing test repos (if available) and compare before/after:
- Total AI scores should decrease for repos with UI emoji usage (React, Vue apps)
- Total AI scores should remain the same for repos where emojis only appear in comments/prints
- Commit message emoji detection should be completely unchanged

---

## Guardrails for Implementing Agent

- **ASK before assuming** if any requirement is ambiguous. Do not guess.
- Do NOT change the `COMMON_EMOJIS` set (the 40+ tracked emojis)
- Do NOT change the `EMOJI_PATTERN` regex
- Do NOT change the `EMOJI_BONUS` value (+15)
- Do NOT modify commit message emoji detection (lines 404-417 of current code)
- Do NOT change `_calculate_score()` — it already receives `emoji_count` and the count will now naturally be lower (only flagged emojis)
- Keep the function signature of `_detect_emojis()` compatible — it now returns a tuple instead of a single list, so update ALL call sites
- The `classify_emoji_context()` function MUST be a separate helper function defined at module level, NOT a method on `AISlopAnalyzer` and NOT inlined into the loop
- The `_update_block_comment_state()` function MUST also be a separate helper at module level
- Add comments explaining the classification logic for maintainability
- The new compile-time constants (regex patterns, print pattern tuples) MUST be defined in the CONFIGURATION section at the top of the file, not inside functions
- If `Severity.INFO` does not exist in `schemas.py`, add it as the last enum value
- Run `python -c "from server.v2.analyzers.ai_slop import AISlopAnalyzer"` after changes to verify no import errors
