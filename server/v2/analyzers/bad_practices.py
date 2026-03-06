"""
Bad Practices Analyzer for Anti-Soy V2

Detects security gaps, missing defensive code, and professional discipline issues.
These are things AI doesn't add unless explicitly prompted - a vibe coder doesn't
know to prompt for them.

Categories:
- Security: No input validation, SQL injection, hardcoded secrets, CORS wildcard, no auth
- Robustness: No timeout on HTTP calls, silent error swallowing, no retry logic
- Hygiene: .env committed, lock file issues, print statements in prod code

Output matches schemas.BadPractices exactly.
"""

import re
from dataclasses import dataclass
from pathlib import Path

from ..schemas import BadPractices, Finding, Severity
from ..data_extractor import RepoData, is_code_file, is_test_file


# =============================================================================
# CONFIGURATION
# =============================================================================

# Score weights for different severity levels
SEVERITY_WEIGHTS = {
    Severity.CRITICAL: 60,
    Severity.WARNING: 20,
    Severity.INFO: 5,
}

# Maximum score (100 = very bad practices, capped)
MAX_SCORE = 100


# =============================================================================
# DETECTION PATTERNS
# =============================================================================

@dataclass
class DetectionPattern:
    """A pattern to detect bad practices."""
    name: str
    category: str  # "security", "robustness", "hygiene"
    severity: Severity
    pattern: str  # Regex pattern
    file_pattern: str | None  # Glob pattern for files to check, None = all code files
    explanation: str
    # Optional: negative pattern (if this matches, don't flag)
    negative_pattern: str | None = None


# -----------------------------------------------------------------------------
# SECURITY PATTERNS
# -----------------------------------------------------------------------------

SECURITY_PATTERNS = [
    # SQL Injection - string concatenation/formatting in SQL
    # Note: We specifically look for f-strings, .format(), or + concatenation
    # Parameterized queries like execute("SELECT ... WHERE id = %s", (id,)) are SAFE
    DetectionPattern(
        name="sql_injection_risk",
        category="security",
        severity=Severity.CRITICAL,
        pattern=r'''(?:execute|cursor\.execute|query|raw_query)\s*\(\s*(?:f["\']|["\'][^"\']*\.format\s*\(|["\'][^"\']*\"\s*\+)''',
        file_pattern=None,
        explanation="SQL query built with string concatenation/formatting - vulnerable to SQL injection. Use parameterized queries instead.",
    ),
    DetectionPattern(
        name="sql_injection_risk",
        category="security",
        severity=Severity.CRITICAL,
        pattern=r'''(?:SELECT|INSERT|UPDATE|DELETE|FROM|WHERE)[^"\']*\"\s*\+\s*(?:request|params|user|input|data|body)''',
        file_pattern=None,
        explanation="SQL query concatenated with user input - vulnerable to SQL injection.",
    ),
    
    # Hardcoded secrets
    DetectionPattern(
        name="hardcoded_secret",
        category="security",
        severity=Severity.CRITICAL,
        pattern=r'''(?:api[_-]?key|secret[_-]?key|password|passwd|token|auth[_-]?token|private[_-]?key)\s*[=:]\s*["\'][^"\']{8,}["\']''',
        file_pattern=None,
        explanation="Hardcoded secret/API key detected. Use environment variables instead.",
        negative_pattern=r'''(?:example|placeholder|your[_-]?|xxx|test|dummy|fake|sample)''',
    ),
    DetectionPattern(
        name="hardcoded_secret",
        category="security",
        severity=Severity.CRITICAL,
        pattern=r'''["\'](?:sk-|pk_live_|sk_live_|ghp_|gho_|github_pat_|xox[baprs]-|AKIA)[a-zA-Z0-9]{10,}["\']''',
        file_pattern=None,
        explanation="Hardcoded API key pattern detected (OpenAI, Stripe, GitHub, Slack, AWS). Use environment variables.",
    ),
    
    # CORS wildcard
    DetectionPattern(
        name="cors_wildcard",
        category="security",
        severity=Severity.WARNING,
        pattern=r'''(?:Access-Control-Allow-Origin|cors.*origin|allow_origin)\s*[=:]\s*["\']?\*["\']?''',
        file_pattern=None,
        explanation="CORS wildcard (*) allows any origin - restrict to specific domains in production.",
    ),
    DetectionPattern(
        name="cors_wildcard",
        category="security",
        severity=Severity.WARNING,
        pattern=r'''CORS\s*\(\s*(?:app|application)?\s*(?:,\s*)?(?:origins?\s*=\s*)?["\']?\*["\']?''',
        file_pattern=None,
        explanation="CORS configured to allow all origins - restrict to specific domains.",
    ),
    
    # No input validation on API endpoints
    DetectionPattern(
        name="no_input_validation",
        category="security",
        severity=Severity.WARNING,
        pattern=r'''def\s+(?:post|put|patch|create|update|delete)\w*\s*\([^)]*(?:request|data|body|payload)[^)]*\):\s*\n(?:\s*["\'].*["\'])?(?:\s*#.*)?\s*\n\s*(?:\w+\.(?:save|create|update|insert|execute)|db\.)''',
        file_pattern=None,
        explanation="User input passed directly to database without validation.",
    ),
    
    # Eval/exec with user input (Python-specific)
    DetectionPattern(
        name="dangerous_eval",
        category="security",
        severity=Severity.CRITICAL,
        pattern=r'''\b(?:eval|exec|compile)\s*\(\s*(?:request|params|input|data|user|body|f["'])''',
        file_pattern="*.py",
        explanation="eval/exec with potentially user-controlled input - major security risk.",
    ),
    
    # Disabled SSL verification
    DetectionPattern(
        name="ssl_disabled",
        category="security",
        severity=Severity.WARNING,
        pattern=r'''verify\s*=\s*False|ssl\s*=\s*False|check_hostname\s*=\s*False''',
        file_pattern=None,
        explanation="SSL verification disabled - vulnerable to man-in-the-middle attacks.",
    ),

    # --- GO-SPECIFIC SECURITY ---

    # Go: SQL injection via string concatenation in queries
    DetectionPattern(
        name="sql_injection_risk",
        category="security",
        severity=Severity.CRITICAL,
        pattern=r'''(?:\.Query|\.Exec|\.QueryRow|\.QueryContext|\.ExecContext)\s*\([^)]*(?:fmt\.Sprintf|"\s*\+)''',
        file_pattern="*.go",
        explanation="SQL query built with string concatenation/fmt.Sprintf in Go - use parameterized queries with $1/$2 placeholders.",
    ),

    # --- C#-SPECIFIC SECURITY ---

    # C#: SQL injection via SqlCommand with string concatenation
    DetectionPattern(
        name="sql_injection_risk",
        category="security",
        severity=Severity.CRITICAL,
        pattern=r'''(?:SqlCommand|OleDbCommand|OdbcCommand)\s*\(\s*(?:\$"|["\'][^"\']*\"\s*\+|string\.Format)''',
        file_pattern="*.cs",
        explanation="SQL query built with string concatenation in C# - use parameterized queries with SqlParameter.",
    ),

    # C#: Process.Start with user-controlled input
    DetectionPattern(
        name="command_injection",
        category="security",
        severity=Severity.CRITICAL,
        pattern=r'''Process\.Start\s*\([^)]*(?:request|input|user|param|args|data|Request|Input)''',
        file_pattern="*.cs",
        explanation="Process.Start with potentially user-controlled input - risk of command injection.",
    ),
]

# -----------------------------------------------------------------------------
# ROBUSTNESS PATTERNS
# -----------------------------------------------------------------------------

ROBUSTNESS_PATTERNS = [
    # HTTP calls without timeout
    DetectionPattern(
        name="no_timeout",
        category="robustness",
        severity=Severity.WARNING,
        pattern=r'''requests\.(?:get|post|put|patch|delete|head)\s*\([^)]*\)(?!.*timeout)''',
        file_pattern="*.py",
        explanation="HTTP request without timeout - can hang indefinitely if server doesn't respond.",
        negative_pattern=r'''timeout\s*=''',
    ),
    DetectionPattern(
        name="no_timeout",
        category="robustness",
        severity=Severity.WARNING,
        pattern=r'''fetch\s*\([^)]+\)(?!.*signal|.*timeout|.*AbortController)''',
        file_pattern="*.{js,ts,jsx,tsx}",
        explanation="Fetch request without timeout/abort signal - can hang indefinitely.",
    ),
    DetectionPattern(
        name="no_timeout",
        category="robustness",
        severity=Severity.WARNING,
        pattern=r'''axios\.(?:get|post|put|patch|delete)\s*\([^)]*\)(?!.*timeout)''',
        file_pattern="*.{js,ts,jsx,tsx}",
        explanation="Axios request without timeout - can hang indefinitely.",
        negative_pattern=r'''timeout\s*[:=]''',
    ),
    
    # Silent error swallowing - empty except/catch blocks
    DetectionPattern(
        name="silent_error",
        category="robustness",
        severity=Severity.WARNING,
        pattern=r'''except(?:\s+\w+)?:\s*\n\s*(?:pass|\.\.\.)\s*(?:\n|$)''',
        file_pattern="*.py",
        explanation="Empty except block silently swallows errors - at minimum, log the error.",
    ),
    DetectionPattern(
        name="silent_error",
        category="robustness",
        severity=Severity.WARNING,
        pattern=r'''catch\s*\([^)]*\)\s*\{\s*\}''',
        file_pattern="*.{js,ts,jsx,tsx}",
        explanation="Empty catch block silently swallows errors - at minimum, log the error.",
    ),
    
    # Bare except (catches everything including KeyboardInterrupt)
    DetectionPattern(
        name="bare_except",
        category="robustness",
        severity=Severity.INFO,
        pattern=r'''except\s*:\s*\n''',
        file_pattern="*.py",
        explanation="Bare 'except:' catches all exceptions including KeyboardInterrupt. Use 'except Exception:' instead.",
    ),
    
    # No error handling on file operations - simplified pattern
    # We just detect open() calls and flag them; false positives are acceptable
    DetectionPattern(
        name="unhandled_file_error",
        category="robustness",
        severity=Severity.INFO,
        pattern=r'''^\s*(?:data|content|text|file_content)\s*=\s*open\s*\([^)]+\)\.read\(\)''',
        file_pattern="*.py",
        explanation="File read without 'with' context manager - use 'with open(...) as f:' for proper cleanup.",
    ),

    # --- GO-SPECIFIC ROBUSTNESS ---

    # Go: HTTP requests using DefaultClient (no timeout)
    DetectionPattern(
        name="no_timeout",
        category="robustness",
        severity=Severity.WARNING,
        pattern=r'''(?:http\.Get|http\.Post|http\.PostForm|http\.Head|http\.DefaultClient\.)''',
        file_pattern="*.go",
        explanation="Using default HTTP client without timeout in Go - create a custom http.Client with Timeout set.",
    ),

    # Go: Ignoring returned error values
    DetectionPattern(
        name="ignored_error",
        category="robustness",
        severity=Severity.WARNING,
        pattern=r'''[a-zA-Z_]\w*\s*,\s*_\s*:?=\s*\w+''',
        file_pattern="*.go",
        explanation="Returned error value ignored in Go (val, _ := ...). Always check error return values.",
    ),

    # --- C#-SPECIFIC ROBUSTNESS ---

    # C#: HttpClient without timeout
    DetectionPattern(
        name="no_timeout",
        category="robustness",
        severity=Severity.WARNING,
        pattern=r'''new\s+HttpClient\s*\(\s*\)''',
        file_pattern="*.cs",
        explanation="HttpClient created without timeout configuration in C# - set HttpClient.Timeout or use IHttpClientFactory.",
        negative_pattern=r'''Timeout\s*=''',
    ),

    # C#: Empty catch blocks
    DetectionPattern(
        name="silent_error",
        category="robustness",
        severity=Severity.WARNING,
        pattern=r'''catch\s*(?:\([^)]*\))?\s*\{\s*\}''',
        file_pattern="*.cs",
        explanation="Empty catch block in C# silently swallows errors - at minimum, log the error.",
    ),

    # C#: Catching generic Exception without specifics
    DetectionPattern(
        name="generic_exception",
        category="robustness",
        severity=Severity.INFO,
        pattern=r'''catch\s*\(\s*Exception\s+\w+\s*\)''',
        file_pattern="*.cs",
        explanation="Catching generic Exception in C# - catch specific exception types for better error handling.",
    ),
]

# -----------------------------------------------------------------------------
# HYGIENE PATTERNS
# -----------------------------------------------------------------------------

HYGIENE_PATTERNS = [
    # .env file committed (check tree, not content)
    # This is handled specially, not via regex
    
    # NOTE: Print statements are handled separately via _check_print_statements()
    # to aggregate them instead of creating individual findings
    
    # Commented-out code blocks
    DetectionPattern(
        name="commented_code",
        category="hygiene",
        severity=Severity.INFO,
        pattern=r'''#\s*(?:def |class |if |for |while |return |import ).*\n(?:#.*\n){2,}''',
        file_pattern="*.py",
        explanation="Large block of commented-out code - remove dead code to improve maintainability.",
    ),
    DetectionPattern(
        name="commented_code",
        category="hygiene",
        severity=Severity.INFO,
        pattern=r'''//\s*(?:function |const |let |var |if |for |while |return |import ).*\n(?://.*\n){2,}''',
        file_pattern="*.{js,ts,jsx,tsx}",
        explanation="Large block of commented-out code - remove dead code to improve maintainability.",
    ),

    # Go: Commented-out code blocks
    DetectionPattern(
        name="commented_code",
        category="hygiene",
        severity=Severity.INFO,
        pattern=r'''//\s*(?:func |if |for |return |var |type |import ).*\n(?://.*\n){2,}''',
        file_pattern="*.go",
        explanation="Large block of commented-out Go code - remove dead code to improve maintainability.",
    ),

    # C#: Commented-out code blocks
    DetectionPattern(
        name="commented_code",
        category="hygiene",
        severity=Severity.INFO,
        pattern=r'''//\s*(?:public |private |protected |internal |static |class |if |for |foreach |while |return |using |var ).*\n(?://.*\n){2,}''',
        file_pattern="*.cs",
        explanation="Large block of commented-out C# code - remove dead code to improve maintainability.",
    ),
    
    # NOTE: TODO/FIXME/HACK comments are handled separately via _check_todo_comments()
    # to aggregate them and cap their score impact (they shouldn't drive a negative verdict alone).
    
    # Debug flags left on
    DetectionPattern(
        name="debug_enabled",
        category="hygiene",
        severity=Severity.WARNING,
        pattern=r'''(?:DEBUG|TESTING)\s*=\s*True''',
        file_pattern="*.py",
        explanation="Debug flag enabled in code - should be False or controlled via environment.",
    ),
    DetectionPattern(
        name="debug_enabled",
        category="hygiene",
        severity=Severity.WARNING,
        pattern=r'''(?:debug|testing)\s*[=:]\s*true''',
        file_pattern="*.{js,ts,jsx,tsx,json}",
        explanation="Debug flag enabled in code - should be controlled via environment.",
    ),
]


# =============================================================================
# ANALYZER CLASS
# =============================================================================

class BadPracticesAnalyzer:
    """
    Analyzes code for security, robustness, and hygiene issues.
    
    These are things AI typically doesn't add unless explicitly prompted,
    making them good indicators of engineering maturity.
    """
    
    def __init__(self):
        self.all_patterns = SECURITY_PATTERNS + ROBUSTNESS_PATTERNS + HYGIENE_PATTERNS
    
    def analyze(self, repo_data: RepoData) -> BadPractices:
        """
        Run bad practices analysis on a repository.
        
        Args:
            repo_data: Raw repository data (files, tree structure)
            
        Returns:
            BadPractices schema object ready for API response
        """
        findings: list[Finding] = []
        
        # Run pattern detection on all files
        for file_path, content in repo_data.files.items():
            file_findings = self._analyze_file(file_path, content)
            findings.extend(file_findings)
        
        # Check for special cases (not regex-based)
        findings.extend(self._check_env_committed(repo_data))
        findings.extend(self._check_gitignore_issues(repo_data))
        findings.extend(self._check_print_statements(repo_data))
        findings.extend(self._check_todo_comments(repo_data))

        findings = self._compress_findings(findings)

        # Count by category
        security_count = sum(1 for f in findings if self._get_category(f.type) == "security")
        robustness_count = sum(1 for f in findings if self._get_category(f.type) == "robustness")
        hygiene_count = sum(1 for f in findings if self._get_category(f.type) == "hygiene")
        
        # Calculate score (higher = worse)
        score = self._calculate_score(findings)
        
        return BadPractices(
            score=score,
            security_issues=security_count,
            robustness_issues=robustness_count,
            hygiene_issues=hygiene_count,
            findings=findings,
        )
    
    def _analyze_file(self, file_path: str, content: str) -> list[Finding]:
        """Analyze a single file for bad practices."""
        findings: list[Finding] = []
        
        # Skip test files for some checks
        file_is_test = is_test_file(file_path)
        
        for pattern in self.all_patterns:
            # Check if pattern applies to this file type
            if not self._file_matches_pattern(file_path, pattern.file_pattern):
                continue
            
            # Skip hygiene checks in test files (print statements OK in tests)
            if file_is_test and pattern.category == "hygiene":
                continue
            
            # Search for matches
            for match in re.finditer(pattern.pattern, content, re.MULTILINE | re.IGNORECASE):
                # Check negative pattern (things that make this OK)
                if pattern.negative_pattern:
                    # Check if the negative pattern matches in the same region
                    match_text = match.group(0)
                    if re.search(pattern.negative_pattern, match_text, re.IGNORECASE):
                        continue
                    # Also check surrounding context (5 lines before and after)
                    start_pos = max(0, match.start() - 500)
                    end_pos = min(len(content), match.end() + 500)
                    context = content[start_pos:end_pos]
                    if re.search(pattern.negative_pattern, context, re.IGNORECASE):
                        continue
                
                # Get line number
                line_number = content[:match.start()].count('\n') + 1
                
                # Get snippet (the line plus 3 full lines after for context)
                lines = content.split('\n')
                snippet_start = max(0, line_number - 1)
                snippet_end = min(len(lines), line_number + 4)  # +4 = current line + 3 after
                snippet = '\n'.join(lines[snippet_start:snippet_end])
                
                # Truncate very long snippets but preserve full lines
                if len(snippet) > 500:
                    snippet = snippet[:500] + "..."
                
                findings.append(Finding(
                    type=pattern.name,
                    severity=pattern.severity,
                    file=file_path,
                    line=line_number,
                    snippet=snippet,
                    explanation=pattern.explanation,
                ))
        
        return findings
    
    def _check_print_statements(self, repo_data: RepoData) -> list[Finding]:
        """
        Check for print/console.log statements and aggregate them.
        
        Instead of individual findings per print statement, creates one
        aggregated finding with count and examples.
        """
        findings: list[Finding] = []
        print_occurrences: list[str] = []  # "file:line" format
        
        for file_path, content in repo_data.files.items():
            # Skip test files
            if is_test_file(file_path):
                continue
            
            lines = content.split('\n')
            
            # Python print statements
            if file_path.endswith('.py'):
                for i, line in enumerate(lines):
                    stripped = line.strip()
                    if stripped.startswith('#'):
                        continue
                    if re.match(r'^\s*print\s*\(', line):
                        print_occurrences.append(f"{file_path}:{i+1}")
            
            # JavaScript/TypeScript console.log
            elif file_path.endswith(('.js', '.ts', '.jsx', '.tsx')):
                for i, line in enumerate(lines):
                    stripped = line.strip()
                    if stripped.startswith('//'):
                        continue
                    if 'console.log(' in line:
                        print_occurrences.append(f"{file_path}:{i+1}")

            # Go: fmt.Println/fmt.Printf (debug print statements)
            elif file_path.endswith('.go'):
                for i, line in enumerate(lines):
                    stripped = line.strip()
                    if stripped.startswith('//'):
                        continue
                    if re.search(r'fmt\.Print(?:ln|f)?\s*\(', line):
                        print_occurrences.append(f"{file_path}:{i+1}")

            # C#: Console.WriteLine (debug print statements)
            elif file_path.endswith('.cs'):
                for i, line in enumerate(lines):
                    stripped = line.strip()
                    if stripped.startswith('//'):
                        continue
                    if 'Console.Write' in line:
                        print_occurrences.append(f"{file_path}:{i+1}")
        
        # Only create finding if there are print statements
        if len(print_occurrences) >= 3:  # Threshold: 3+ to flag
            # Parse first occurrence for file and line
            first_file, first_line = print_occurrences[0].rsplit(':', 1)
            
            # Take first 3 examples for snippet
            examples = print_occurrences[:3]
            examples_str = ', '.join(examples)
            if len(print_occurrences) > 3:
                examples_str += f" ... and {len(print_occurrences) - 3} more"
            
            findings.append(Finding(
                type="print_statements",
                severity=Severity.INFO,
                file=f"Multiple files, first occurrence at {first_file}",
                line=int(first_line),
                snippet=examples_str,
                explanation=f"Found {len(print_occurrences)} print/console.log statements across the codebase. Consider using proper logging for production.",
            ))
        
        return findings
    
    def _check_todo_comments(self, repo_data: RepoData) -> list[Finding]:
        """
        Check for TODO/FIXME/HACK comments and aggregate them.

        TODOs are standard convention in Go and C# (and most languages).
        We aggregate them into a single informational finding and cap
        their score impact so high TODO count alone cannot drive a
        negative verdict.
        """
        findings: list[Finding] = []
        todo_occurrences: list[str] = []  # "file:line" format
        todo_pattern = re.compile(r'(?:#|//)\s*(?:TODO|FIXME|HACK|XXX|BUG)\s*[:\s]', re.IGNORECASE)

        for file_path, content in repo_data.files.items():
            if is_test_file(file_path):
                continue
            if not is_code_file(file_path):
                continue

            lines = content.split('\n')
            for i, line in enumerate(lines):
                if todo_pattern.search(line):
                    todo_occurrences.append(f"{file_path}:{i+1}")

        if todo_occurrences:
            first_file, first_line = todo_occurrences[0].rsplit(':', 1)
            examples = todo_occurrences[:5]
            examples_str = ', '.join(examples)
            if len(todo_occurrences) > 5:
                examples_str += f" ... and {len(todo_occurrences) - 5} more"

            findings.append(Finding(
                type="todo_comment",
                severity=Severity.INFO,
                file=f"Multiple files, first occurrence at {first_file}" if len(todo_occurrences) > 1 else first_file,
                line=int(first_line),
                snippet=examples_str,
                explanation=f"Found {len(todo_occurrences)} TODO/FIXME/HACK comment(s). This is informational - TODOs are standard convention and don't indicate poor quality on their own.",
            ))

        return findings

    def _compress_findings(self, findings: list[Finding]) -> list[Finding]:
        """
        Compress findings of the same type into a single aggregated Finding.

        Types with count == 1 pass through unchanged.
        Already-aggregated types (print_statements, todo_comment) will be
        count=1 in their group since their dedicated methods already aggregate,
        so they pass through without double-compression.
        """
        severity_rank = {Severity.CRITICAL: 2, Severity.WARNING: 1, Severity.INFO: 0}

        grouped: dict[str, list[Finding]] = {}
        for f in findings:
            grouped.setdefault(f.type, []).append(f)

        result: list[Finding] = []
        for ftype, group in grouped.items():
            if len(group) == 1:
                result.append(group[0])
                continue

            count = len(group)
            first = group[0]
            highest_severity = max(group, key=lambda f: severity_rank[f.severity]).severity

            locations = [f"{f.file}:{f.line}" for f in group]
            shown = locations[:5]
            snippet = ', '.join(shown)
            if count > 5:
                snippet += f" ... and {count - 5} more"

            result.append(Finding(
                type=ftype,
                severity=highest_severity,
                file=f"Multiple files, first occurrence at {first.file}",
                line=first.line,
                snippet=snippet,
                explanation=f"{first.explanation} (found {count} occurrences)",
            ))

        return result

    def _check_env_committed(self, repo_data: RepoData) -> list[Finding]:
        """Check if .env file is committed (appears in tree)."""
        findings: list[Finding] = []
        
        env_files = ['.env', '.env.local', '.env.production', '.env.development']
        
        for path in repo_data.tree:
            filename = Path(path).name
            if filename in env_files and filename != '.env.example':
                # Check if there's a .gitignore that should have caught this
                findings.append(Finding(
                    type="env_committed",
                    severity=Severity.CRITICAL,
                    file=path,
                    line=1,
                    snippet=f"File: {path}",
                    explanation=f"{filename} appears to be committed to the repository. This may expose secrets. Add to .gitignore.",
                ))
        
        return findings
    
    def _check_gitignore_issues(self, repo_data: RepoData) -> list[Finding]:
        """Check for .gitignore issues."""
        findings: list[Finding] = []
        
        # Check if .gitignore exists
        has_gitignore = any('.gitignore' in path for path in repo_data.tree)
        
        if not has_gitignore and len(repo_data.tree) > 5:
            findings.append(Finding(
                type="no_gitignore",
                severity=Severity.WARNING,
                file=".gitignore",
                line=1,
                snippet="(missing file)",
                explanation="No .gitignore file found - sensitive files may accidentally be committed.",
            ))
        
        return findings
    
    def _calculate_score(self, findings: list[Finding]) -> int:
        """
        Calculate bad practices score (0-100, higher = worse).
        
        Uses severity weights to compute score.
        """
        total_weight = 0
        
        for finding in findings:
            total_weight += SEVERITY_WEIGHTS.get(finding.severity, 5)
        
        # Cap at MAX_SCORE
        score = min(total_weight, MAX_SCORE)
        
        return score
    
    def _file_matches_pattern(self, file_path: str, file_pattern: str | None) -> bool:
        """Check if file matches the glob pattern."""
        if file_pattern is None:
            # Check if it's a code file
            return is_code_file(file_path)
        
        # Handle glob patterns like "*.py" or "*.{js,ts}"
        if file_pattern.startswith("*."):
            extensions = file_pattern[2:]
            if extensions.startswith("{") and extensions.endswith("}"):
                # Multiple extensions: *.{js,ts,jsx,tsx}
                ext_list = extensions[1:-1].split(",")
                return any(file_path.endswith(f".{ext.strip()}") for ext in ext_list)
            else:
                # Single extension: *.py
                return file_path.endswith(f".{extensions}")
        
        return True
    
    def _get_category(self, finding_type: str) -> str:
        """Get category for a finding type."""
        for pattern in SECURITY_PATTERNS:
            if pattern.name == finding_type:
                return "security"
        for pattern in ROBUSTNESS_PATTERNS:
            if pattern.name == finding_type:
                return "robustness"
        for pattern in HYGIENE_PATTERNS:
            if pattern.name == finding_type:
                return "hygiene"
        # Special cases
        if finding_type in ("env_committed", "no_gitignore", "print_statements", "todo_comment"):
            return "hygiene"
        if finding_type in ("ignored_error", "generic_exception"):
            return "robustness"
        if finding_type == "command_injection":
            return "security"
        return "hygiene"  # Default


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

_analyzer: BadPracticesAnalyzer | None = None


def get_analyzer() -> BadPracticesAnalyzer:
    """Get or create singleton analyzer instance."""
    global _analyzer
    if _analyzer is None:
        _analyzer = BadPracticesAnalyzer()
    return _analyzer


def analyze_bad_practices(repo_data: RepoData) -> BadPractices:
    """
    Convenience function to analyze bad practices in a repository.
    
    Args:
        repo_data: Raw repository data from data_extractor
        
    Returns:
        BadPractices schema object
    """
    return get_analyzer().analyze(repo_data)
