# Branch 1: Language Compatibility (GO + C#)

## Context
Anti Soy is a GitHub repo scanner that evaluates engineering candidates. The static analysis and security/bad practice detection currently supports multiple languages but has gaps in GO and C# that cause false positives (e.g., GO regex syntax flagged as Python security risk). This is a blocker for a government hiring manager pilot with 500 co op resumes, most in GO and C#.

## Objective
Extend static analysis heuristics so GO and C# repos are evaluated accurately. Eliminate false positives caused by language specific syntax being misinterpreted through Python rules.

## What to Do

### 1. Audit Current Language Detection
- Read the codebase to understand how file extensions / languages are currently detected.
- Identify where language context is (or is not) passed to the heuristic analysis functions.

### 2. Fix Security / Bad Practice Rules per Language
Current rules are partially Python centric. For each rule category, ensure language aware evaluation:

**Security patterns (e.g., regex, request handling):**
- GO: `regexp.Compile` / `regexp.MustCompile` are standard, NOT security risks. HTTP requests via `net/http` without timeout is a valid flag. Identify GO specific security anti patterns (e.g., `sql.Query` with string concatenation for SQL injection).
- C#: `Regex` class usage is standard. Flag `HttpClient` without timeout. Flag raw SQL string concatenation in `SqlCommand`. Flag `Process.Start` with user input.

**Error handling:**
- GO: Ignoring returned `error` values (e.g., `val, _ := someFunc()`) is a real bad practice. Flag this.
- C#: Empty `catch` blocks, catching generic `Exception` without specifics.

**Bare excepts / catch alls:**
- GO: Does not have try/catch. Remove any try/catch based rules from GO analysis.
- C#: `catch (Exception)` without specific handling is a valid flag.

**File / code quality signals:**
- Ensure file name analysis works with GO conventions (e.g., `_test.go` for test files, `main.go` for entry points).
- Ensure C# conventions recognized (e.g., `.csproj`, `Program.cs`, `Startup.cs`, `Controller` suffix for API controllers).

### 3. Update TODO / Comment Detection
- GO: `// TODO` is standard convention. Still flag but lower weight (informational, not negative).
- C#: `// TODO` and `// HACK` and `// FIXME` same treatment.
- Do NOT let high TODO count alone drive a negative verdict.

### 4. Test
- Test against this repo as a known good baseline: `https://github.com/cadence-workflow/cadence` (GO, production codebase, should NOT be flagged as "nothing stands out" or have false security positives).
- Test against at least one C# open source project (e.g., a well known .NET project on GitHub).
- Verify no regressions on Python analysis.

## Out of Scope
- Adding new languages beyond GO and C#.
- Changing the LLM evaluation prompt (separate branch).
- Batch scanning (separate branch).

## Definition of Done
- GO repos scanned without false positive security flags from Python rules.
- C# repos scanned without false positive security flags.
- Cadence repo no longer flagged incorrectly.
- Existing Python analysis unchanged.
