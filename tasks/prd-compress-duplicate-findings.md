# PRD: Compress Duplicate Findings in Deep Dive

## Problem
Bad practices findings like `no_timeout`, `no_input_validation`, `silent_error`, etc. can appear 8+ times across files but are listed individually in the Deep Dive output. This is noisy and repetitive. `print_statements` and `todo_comment` already have custom aggregation — the same pattern should apply to ALL finding types with multiple occurrences.

## Reference Pattern
Existing compression in `ai_slop.py` for redundant comments (lines 595-616):
- Groups by type/explanation
- Single Finding per group: `"Multiple files, first occurrence at {file}:{line}"`
- Shows count: `"(found N occurrences)"`

Existing compression in `bad_practices.py` for print_statements (lines 492-565) and todo_comments (lines 567-607):
- Single Finding with count + up to 5 example locations

## Implementation

### 1. Add `_compress_findings()` method — `server/v2/analyzers/bad_practices.py`
- Groups findings by `type`
- For any type with count > 1, compress into single Finding:
  - `file`: first occurrence's file path
  - `line`: first occurrence's line number
  - `snippet`: `"file1:line1, file2:line2, file3:line3, ... and N more"` (max 5 shown)
  - `explanation`: `"{original explanation} (found {count} occurrences)"`
  - `severity`: highest severity in the group
- Types with count == 1 pass through unchanged
- Already-compressed types (print_statements, todo_comment) will be count=1 in their group since their dedicated methods already aggregate — no double-compression

### 2. Call in `analyze()` — line 419
After all findings are collected (line 419), before category counting (line 422):
```python
findings = self._compress_findings(findings)
```

## Files to Modify
- `server/v2/analyzers/bad_practices.py`

## Verification
Run analysis on a repo with many repeated findings (e.g., multiple `no_timeout` or `no_input_validation` across files). Verify Deep Dive shows compressed entries like "found 8 occurrences" instead of 8 individual cards. Verify category counts are still correct.
