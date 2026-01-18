"""
Repository Analyzer for Anti-Soy Candidate Analysis Platform

Analyzes cloned repositories and generates metrics using pattern detection + Gemini LLM.
Each metric returns: {"score": 0-100, "comment": "LLM explanation"}
"""

import re
import os
import ast
import json
import asyncio
import subprocess
from pathlib import Path
from typing import Any, Optional

from google import genai
from dotenv import load_dotenv

load_dotenv()

# Configure Gemini client
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
gemini_client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None

# File size limits
MAX_FILE_SIZE = 100 * 1024  # 100KB
MAX_TOTAL_CONTENT = 500 * 1024  # 500KB total content to send to LLM
CONTEXT_LINES = 50  # Lines before/after pattern match

# Code file extensions
CODE_EXTENSIONS = (".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".go", ".rb", ".rs", ".cpp", ".c", ".cs", ".php", ".swift", ".kt")

# Binary/skip extensions
SKIP_EXTENSIONS = (".png", ".jpg", ".jpeg", ".gif", ".ico", ".svg", ".woff", ".woff2", ".ttf", ".eot", ".mp3", ".mp4", ".zip", ".tar", ".gz", ".pdf", ".exe", ".dll", ".so", ".pyc", ".class", ".o", ".lock")

# Dependency file patterns
DEPENDENCY_FILES = {
    "requirements.txt": "python",
    "pyproject.toml": "python",
    "setup.py": "python",
    "Pipfile": "python",
    "package.json": "javascript",
    "yarn.lock": "javascript",
    "go.mod": "go",
    "Cargo.toml": "rust",
    "Gemfile": "ruby",
    "pom.xml": "java",
    "build.gradle": "java",
    "composer.json": "php",
}


# ============================================================================
# DATA EXTRACTION UTILITIES
# ============================================================================

def extract_repo_data(repo_path: str) -> dict[str, Any]:
    """
    Extract all necessary data from a cloned repository.
    Returns dict with: tree, files, commits, dependencies
    """
    repo_path_obj = Path(repo_path)
    
    # Get file tree
    tree = []
    files = {}
    total_content_size = 0
    
    for file_path in repo_path_obj.rglob("*"):
        if file_path.is_file():
            # Get relative path
            rel_path = str(file_path.relative_to(repo_path_obj)).replace("\\", "/")
            
            # Skip hidden files, node_modules, venv, etc.
            if any(part.startswith(".") for part in rel_path.split("/")):
                if not rel_path.startswith(".github"):  # Keep .github workflows
                    continue
            if any(skip in rel_path for skip in ["node_modules/", "venv/", "__pycache__/", ".git/", "dist/", "build/"]):
                continue
            
            tree.append(rel_path)
            
            # Skip binary files
            if file_path.suffix.lower() in SKIP_EXTENSIONS:
                continue
            
            # Skip large files
            try:
                file_size = file_path.stat().st_size
                if file_size > MAX_FILE_SIZE:
                    continue
                if total_content_size + file_size > MAX_TOTAL_CONTENT * 2:  # Allow 2x for raw storage
                    continue
                
                # Try to read as text
                content = file_path.read_text(encoding="utf-8", errors="ignore")
                files[rel_path] = content
                total_content_size += len(content)
            except Exception:
                continue
    
    # Get git commits
    commits = _get_git_commits(repo_path_obj)
    
    # Extract dependencies
    dependencies = _extract_dependencies(files)
    
    return {
        "tree": tree,
        "files": files,
        "commits": commits,
        "dependencies": dependencies,
    }


def _get_git_commits(repo_path: Path, max_commits: int = 100) -> list[dict]:
    """Extract git commit history"""
    commits = []
    try:
        # Get commit log with stats
        result = subprocess.run(
            ["git", "log", f"-{max_commits}", "--pretty=format:%H|||%s|||%an|||%ad", "--date=short", "--numstat"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode != 0:
            return commits
        
        current_commit = None
        for line in result.stdout.split("\n"):
            if "|||" in line:
                if current_commit:
                    commits.append(current_commit)
                parts = line.split("|||")
                current_commit = {
                    "hash": parts[0],
                    "message": parts[1] if len(parts) > 1 else "",
                    "author": parts[2] if len(parts) > 2 else "",
                    "date": parts[3] if len(parts) > 3 else "",
                    "files_changed": 0,
                    "additions": 0,
                    "deletions": 0,
                }
            elif line.strip() and current_commit:
                # Parse numstat line: additions\tdeletions\tfilename
                parts = line.split("\t")
                if len(parts) >= 2:
                    try:
                        additions = int(parts[0]) if parts[0] != "-" else 0
                        deletions = int(parts[1]) if parts[1] != "-" else 0
                        current_commit["files_changed"] += 1
                        current_commit["additions"] += additions
                        current_commit["deletions"] += deletions
                    except ValueError:
                        pass
        
        if current_commit:
            commits.append(current_commit)
            
    except Exception as e:
        print(f"Error getting git commits: {e}")
    
    return commits


def _extract_dependencies(files: dict[str, str]) -> list[str]:
    """Extract dependency names from various package files"""
    dependencies = []
    
    for filename, content in files.items():
        basename = filename.split("/")[-1]
        
        if basename == "requirements.txt":
            for line in content.splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    # Extract package name (before ==, >=, etc.)
                    pkg = re.split(r"[=<>!~\[]", line)[0].strip()
                    if pkg:
                        dependencies.append(pkg)
        
        elif basename == "package.json":
            try:
                data = json.loads(content)
                for key in ["dependencies", "devDependencies"]:
                    if key in data and isinstance(data[key], dict):
                        dependencies.extend(data[key].keys())
            except json.JSONDecodeError:
                pass
        
        elif basename == "pyproject.toml":
            # Simple TOML parsing for dependencies
            in_deps = False
            for line in content.splitlines():
                if "dependencies" in line and "=" in line:
                    in_deps = True
                elif in_deps:
                    if line.startswith("["):
                        in_deps = False
                    else:
                        match = re.match(r'^\s*"?([a-zA-Z0-9_-]+)', line)
                        if match:
                            dependencies.append(match.group(1))
        
        elif basename == "go.mod":
            for line in content.splitlines():
                if line.strip().startswith("require"):
                    continue
                match = re.match(r"^\s*([a-zA-Z0-9._/-]+)", line)
                if match and "/" in match.group(1):
                    dependencies.append(match.group(1))
        
        elif basename == "Cargo.toml":
            in_deps = False
            for line in content.splitlines():
                if "[dependencies]" in line:
                    in_deps = True
                elif line.startswith("[") and in_deps:
                    in_deps = False
                elif in_deps and "=" in line:
                    pkg = line.split("=")[0].strip()
                    if pkg:
                        dependencies.append(pkg)
    
    return list(set(dependencies))


def _get_code_files(files: dict[str, str]) -> dict[str, str]:
    """Filter to only code files"""
    return {k: v for k, v in files.items() if k.endswith(CODE_EXTENSIONS)}


def _extract_pattern_context(content: str, pattern: str, context_lines: int = CONTEXT_LINES) -> list[str]:
    """
    Extract code snippets around pattern matches.
    Returns list of code snippets with context.
    """
    snippets = []
    lines = content.splitlines()
    regex = re.compile(pattern, re.IGNORECASE)
    
    matched_ranges = set()
    
    for i, line in enumerate(lines):
        if regex.search(line):
            start = max(0, i - context_lines)
            end = min(len(lines), i + context_lines + 1)
            
            # Avoid overlapping snippets
            range_key = (start // context_lines, end // context_lines)
            if range_key not in matched_ranges:
                matched_ranges.add(range_key)
                snippet = "\n".join(lines[start:end])
                snippets.append(snippet)
    
    return snippets[:5]  # Limit to 5 snippets per file


def _total_loc(files: dict[str, str]) -> int:
    """Count total lines of code"""
    code_files = _get_code_files(files)
    return sum(len(content.splitlines()) for content in code_files.values())


# ============================================================================
# GEMINI LLM INTEGRATION
# ============================================================================

async def call_gemini_batched(prompt: str, retries: int = 1) -> dict[str, Any]:
    """
    Call Gemini API with a batched prompt for all 8 LLM metrics.
    Returns dict with all 8 metrics, each containing {"score": 0-100, "comment": "..."}
    Retries once on failure, then raises exception.
    """
    if not gemini_client:
        raise RuntimeError("GEMINI_API_KEY not configured")
    
    expected_keys = [
        "files_organized", "readme", "error_handling", "comments",
        "dependencies", "commit_lines", "solves_real_problem", "aligns_company"
    ]
    
    last_error = None
    
    def _sync_generate():
        """Sync wrapper for Gemini API call"""
        return gemini_client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt,
        )
    
    for attempt in range(retries + 1):
        try:
            # Run sync API in thread pool to not block event loop
            response = await asyncio.to_thread(_sync_generate)
            
            # Parse response
            text = response.text.strip()
            
            # Extract JSON from response (handle markdown code blocks)
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0].strip()
            elif "```" in text:
                text = text.split("```")[1].split("```")[0].strip()
            
            result = json.loads(text)
            
            # Validate all expected keys exist
            validated_result = {}
            for key in expected_keys:
                if key in result and isinstance(result[key], dict):
                    score = result[key].get("score", 50)
                    comment = result[key].get("comment", "No comment provided")
                    validated_result[key] = {
                        "score": max(0, min(100, int(score))),
                        "comment": str(comment)[:500]
                    }
                else:
                    raise ValueError(f"Missing or invalid key: {key}")
            
            return validated_result
            
        except (json.JSONDecodeError, ValueError, KeyError, TypeError) as e:
            last_error = f"Parse error: {str(e)[:100]}"
            if attempt < retries:
                await asyncio.sleep(1)  # Brief delay before retry
                continue
        except Exception as e:
            last_error = f"API error: {str(e)[:150]}"
            if attempt < retries:
                await asyncio.sleep(1)
                continue
    
    # Both attempts failed
    raise RuntimeError(f"Gemini API failed after {retries + 1} attempts: {last_error}")


# ============================================================================
# METRIC ANALYSIS FUNCTIONS - HEURISTICS-BASED (6 metrics)
# ============================================================================

async def analyze_test_suites(repo: dict[str, Any]) -> dict[str, Any]:
    """Analyze test coverage and quality (heuristics-based)"""
    tree = repo.get("tree", [])
    files = repo.get("files", {})
    
    # Find test files
    test_patterns = [r"test[s]?/", r"spec[s]?/", r"__tests__/", r"_test\.", r"\.test\.", r"\.spec\."]
    test_files = [f for f in tree if any(re.search(p, f, re.I) for p in test_patterns)]
    
    if not test_files:
        return {"score": 0, "comment": "No test files found in repository"}
    
    # Count code files
    code_files = [f for f in tree if f.endswith(CODE_EXTENSIONS)]
    code_file_count = len(code_files)
    test_file_count = len(test_files)
    
    # Calculate test ratio
    test_ratio = test_file_count / code_file_count if code_file_count > 0 else 0
    
    # Check for test frameworks (pytest, jest, mocha, etc.)
    has_test_config = any(
        f in files for f in ["pytest.ini", "setup.cfg", "jest.config.js", "jest.config.ts", ".mocharc.json", "karma.conf.js"]
    )
    
    # Count assertion patterns in test files
    assertion_count = 0
    for tf in test_files[:10]:
        if tf in files:
            content = files[tf]
            assertion_count += len(re.findall(r"\b(assert|expect|should|toBe|toEqual|assertEqual)\b", content, re.I))
    
    # Calculate score based on heuristics
    score = 0
    comments = []
    
    # Test ratio scoring (0-40 points)
    if test_ratio >= 0.5:
        score += 40
        comments.append(f"Good test ratio ({test_ratio:.1%})")
    elif test_ratio >= 0.25:
        score += 30
        comments.append(f"Moderate test ratio ({test_ratio:.1%})")
    elif test_ratio >= 0.1:
        score += 20
        comments.append(f"Low test ratio ({test_ratio:.1%})")
    else:
        score += 10
        comments.append(f"Very low test ratio ({test_ratio:.1%})")
    
    # Test file count scoring (0-30 points)
    if test_file_count >= 10:
        score += 30
    elif test_file_count >= 5:
        score += 20
    elif test_file_count >= 2:
        score += 15
    else:
        score += 5
    
    # Test config bonus (0-15 points)
    if has_test_config:
        score += 15
        comments.append("Has test config")
    
    # Assertions bonus (0-15 points)
    if assertion_count >= 20:
        score += 15
    elif assertion_count >= 10:
        score += 10
    elif assertion_count >= 5:
        score += 5
    
    return {"score": min(100, score), "comment": f"{test_file_count} test files. {'; '.join(comments)}"}


async def analyze_api_keys(repo: dict[str, Any]) -> dict[str, Any]:
    """Analyze security - hardcoded secrets and API key handling (heuristics-based)"""
    files = repo.get("files", {})
    tree = repo.get("tree", [])
    code_files = _get_code_files(files)
    
    if not code_files:
        return {"score": 50, "comment": "No code files to analyze"}
    
    # Patterns for secrets (bad)
    secret_patterns = [
        (r"(?i)(api[_-]?key|apikey)\s*[=:]\s*['\"][a-zA-Z0-9]{16,}['\"]", "API key"),
        (r"(?i)(secret[_-]?key|secretkey)\s*[=:]\s*['\"][a-zA-Z0-9]{16,}['\"]", "Secret key"),
        (r"(?i)(password|passwd|pwd)\s*[=:]\s*['\"][^'\"]{4,}['\"]", "Password"),
        (r"ghp_[a-zA-Z0-9]{36}", "GitHub token"),
        (r"sk-[a-zA-Z0-9]{32,}", "OpenAI key"),
        (r"AKIA[0-9A-Z]{16}", "AWS key"),
    ]
    
    # Patterns for good practices
    env_patterns = [
        r"os\.environ\.get\s*\(",
        r"os\.getenv\s*\(",
        r"process\.env\.",
        r"dotenv",
        r"load_dotenv",
    ]
    
    secrets_found = 0
    env_usage_count = 0
    
    for path, content in code_files.items():
        for pattern, _ in secret_patterns:
            secrets_found += len(re.findall(pattern, content))
        
        for pattern in env_patterns:
            env_usage_count += len(re.findall(pattern, content))
    
    # Check for good practices
    has_env_example = any(".env.example" in f or ".env.sample" in f for f in tree)
    has_gitignore = ".gitignore" in files
    gitignore_has_env = False
    if has_gitignore and ".gitignore" in files:
        gitignore_content = files[".gitignore"]
        gitignore_has_env = ".env" in gitignore_content
    
    # Calculate score
    score = 50  # Start at neutral
    comments = []
    
    # Penalize hardcoded secrets heavily
    if secrets_found > 0:
        score -= min(40, secrets_found * 15)
        comments.append(f"{secrets_found} potential hardcoded secrets")
    else:
        score += 20
        comments.append("No hardcoded secrets detected")
    
    # Reward env usage
    if env_usage_count >= 5:
        score += 15
        comments.append("Good env var usage")
    elif env_usage_count >= 1:
        score += 10
    
    # Reward .env.example
    if has_env_example:
        score += 10
        comments.append("Has .env.example")
    
    # Reward .gitignore with .env
    if gitignore_has_env:
        score += 5
    
    return {"score": max(0, min(100, score)), "comment": "; ".join(comments)}


async def analyze_print_or_logging(repo: dict[str, Any]) -> dict[str, Any]:
    """Analyze logging vs print usage (heuristics-based)"""
    files = repo.get("files", {})
    code_files = _get_code_files(files)
    
    if not code_files:
        return {"score": 50, "comment": "No code files to analyze"}
    
    # Count patterns
    print_pattern = r"\bprint\s*\("
    logging_patterns = [
        r"\blogging\.",
        r"\blogger\.",
        r"\.info\s*\(",
        r"\.warn\s*\(",
        r"\.error\s*\(",
        r"\.debug\s*\(",
        r"console\.log",
        r"console\.error",
        r"console\.warn",
    ]
    
    print_count = 0
    logging_count = 0
    
    for path, content in code_files.items():
        # Skip test files for print counting
        is_test = bool(re.search(r"(test|spec)", path, re.I))
        
        if not is_test:
            print_count += len(re.findall(print_pattern, content))
        
        for pattern in logging_patterns:
            logging_count += len(re.findall(pattern, content))
    
    # Check for logging config
    has_logging_config = any(
        "logging.basicConfig" in files.get(f, "") or 
        "logging.config" in files.get(f, "") or
        "winston" in files.get(f, "") or
        "log4j" in files.get(f, "")
        for f in code_files
    )
    
    # Calculate score
    total_output = print_count + logging_count
    
    if total_output == 0:
        return {"score": 50, "comment": "No print or logging statements found"}
    
    logging_ratio = logging_count / total_output if total_output > 0 else 0
    
    # Score based on ratio
    if logging_ratio >= 0.8:
        score = 90
        comment = f"Excellent: {logging_count} logging vs {print_count} print"
    elif logging_ratio >= 0.6:
        score = 75
        comment = f"Good: {logging_count} logging vs {print_count} print"
    elif logging_ratio >= 0.4:
        score = 60
        comment = f"Mixed: {logging_count} logging vs {print_count} print"
    elif logging_ratio >= 0.2:
        score = 40
        comment = f"Print-heavy: {logging_count} logging vs {print_count} print"
    else:
        score = 25
        comment = f"Mostly print: {logging_count} logging vs {print_count} print"
    
    # Bonus for logging config
    if has_logging_config:
        score = min(100, score + 10)
        comment += "; Has logging config"
    
    return {"score": score, "comment": comment}


async def analyze_commit_density(repo: dict[str, Any]) -> dict[str, Any]:
    """Analyze commit frequency and patterns (heuristics-based)"""
    commits = repo.get("commits", [])
    files = repo.get("files", {})
    
    if not commits:
        return {"score": 50, "comment": "No git history available"}
    
    loc = _total_loc(files)
    
    # Calculate metrics
    commit_count = len(commits)
    density = commit_count / (loc / 1000) if loc > 0 else 0
    
    # Large commits (>20 files changed)
    large_commits = [c for c in commits if c.get("files_changed", 0) > 20]
    large_commit_ratio = len(large_commits) / commit_count if commit_count > 0 else 0
    
    # Commit frequency by date
    dates = [c.get("date", "") for c in commits if c.get("date")]
    unique_dates = len(set(dates))
    date_diversity = unique_dates / commit_count if commit_count > 0 else 0
    
    # Average lines per commit
    total_changes = sum(c.get("additions", 0) + c.get("deletions", 0) for c in commits)
    avg_lines_per_commit = total_changes / commit_count if commit_count > 0 else 0
    
    # Calculate score
    score = 50
    comments = []
    
    # Commit count scoring (0-25 points)
    if commit_count >= 50:
        score += 25
        comments.append(f"{commit_count} commits")
    elif commit_count >= 20:
        score += 20
        comments.append(f"{commit_count} commits")
    elif commit_count >= 10:
        score += 15
        comments.append(f"{commit_count} commits")
    elif commit_count >= 5:
        score += 10
        comments.append(f"{commit_count} commits")
    else:
        score += 5
        comments.append(f"Only {commit_count} commits")
    
    # Penalize too many large commits
    if large_commit_ratio > 0.3:
        score -= 15
        comments.append(f"{len(large_commits)} large commits")
    elif large_commit_ratio > 0.1:
        score -= 5
    
    # Date diversity bonus (spread across multiple days)
    if date_diversity >= 0.5:
        score += 15
        comments.append("Regular commit frequency")
    elif date_diversity >= 0.3:
        score += 10
    
    # Reasonable commit size bonus
    if 50 <= avg_lines_per_commit <= 300:
        score += 10
        comments.append("Good commit sizes")
    elif avg_lines_per_commit > 500:
        score -= 10
        comments.append("Large commit sizes")
    
    return {"score": max(0, min(100, score)), "comment": "; ".join(comments)}


async def analyze_concurrency(repo: dict[str, Any]) -> dict[str, Any]:
    """Analyze concurrency and parallelism patterns (heuristics-based)"""
    files = repo.get("files", {})
    code_files = _get_code_files(files)
    
    if not code_files:
        return {"score": 50, "comment": "No code files to analyze"}
    
    # Concurrency patterns
    concurrency_patterns = [
        (r"\basync\s+def\b", "async def"),
        (r"\bawait\s+", "await"),
        (r"\bthreading\.", "threading"),
        (r"\bmultiprocessing\.", "multiprocessing"),
        (r"\basyncio\.", "asyncio"),
        (r"\bPromise\.", "Promise"),
        (r"\bworker_threads", "worker_threads"),
        (r"\bgoroutine", "goroutine"),
        (r"\bchannel\s*<-", "channel"),
    ]
    
    # Safety patterns (good practice)
    safety_patterns = [
        (r"\bLock\s*\(", "Lock"),
        (r"\bSemaphore\s*\(", "Semaphore"),
        (r"\bQueue\s*\(", "Queue"),
        (r"\bMutex", "Mutex"),
        (r"\batomic", "atomic"),
    ]
    
    patterns_found = set()
    safety_found = set()
    
    for path, content in code_files.items():
        for pattern, name in concurrency_patterns:
            if re.search(pattern, content):
                patterns_found.add(name)
        for pattern, name in safety_patterns:
            if re.search(pattern, content):
                safety_found.add(name)
    
    if not patterns_found:
        return {"score": 50, "comment": "No concurrency patterns detected - may not be needed"}
    
    # Calculate score based on usage
    score = 60  # Base score for having concurrency
    comments = []
    
    # More patterns = more sophisticated (up to a point)
    pattern_count = len(patterns_found)
    if pattern_count >= 3:
        score += 15
        comments.append(f"Uses {pattern_count} concurrency patterns")
    elif pattern_count >= 2:
        score += 10
        comments.append(f"Uses {pattern_count} concurrency patterns")
    else:
        score += 5
        comments.append(f"Uses {list(patterns_found)[0]}")
    
    # Reward safety mechanisms
    if safety_found:
        score += 15
        comments.append(f"Has safety: {', '.join(safety_found)}")
    
    # Check for async/await consistency
    has_async = "async def" in patterns_found
    has_await = "await" in patterns_found
    if has_async and has_await:
        score += 10
        comments.append("Proper async/await usage")
    elif has_async != has_await:
        score -= 10
        comments.append("Inconsistent async/await")
    
    return {"score": min(100, score), "comment": "; ".join(comments)}


async def analyze_caching(repo: dict[str, Any]) -> dict[str, Any]:
    """Analyze caching implementation (heuristics-based)"""
    files = repo.get("files", {})
    code_files = _get_code_files(files)
    
    if not code_files:
        return {"score": 50, "comment": "No code files to analyze"}
    
    # Caching patterns by category
    decorator_patterns = [
        (r"@lru_cache", "lru_cache"),
        (r"@cache\b", "@cache"),
        (r"@cached", "@cached"),
        (r"@memoize", "memoize"),
    ]
    
    external_cache_patterns = [
        (r"\bredis\.", "Redis"),
        (r"\bmemcached", "Memcached"),
        (r"\bcache\.get\(", "cache.get"),
        (r"\bcache\.set\(", "cache.set"),
    ]
    
    browser_cache_patterns = [
        (r"localStorage\.", "localStorage"),
        (r"sessionStorage\.", "sessionStorage"),
    ]
    
    # TTL/expiry patterns (good practice)
    ttl_patterns = [
        r"ttl\s*=",
        r"expire",
        r"maxage",
        r"max_age",
        r"timeout",
    ]
    
    decorators_found = set()
    external_found = set()
    browser_found = set()
    has_ttl = False
    
    for path, content in code_files.items():
        for pattern, name in decorator_patterns:
            if re.search(pattern, content, re.I):
                decorators_found.add(name)
        for pattern, name in external_cache_patterns:
            if re.search(pattern, content, re.I):
                external_found.add(name)
        for pattern, name in browser_cache_patterns:
            if re.search(pattern, content, re.I):
                browser_found.add(name)
        for pattern in ttl_patterns:
            if re.search(pattern, content, re.I):
                has_ttl = True
    
    all_patterns = decorators_found | external_found | browser_found
    
    if not all_patterns:
        return {"score": 50, "comment": "No caching patterns detected - may not be needed"}
    
    # Calculate score
    score = 60  # Base for having caching
    comments = []
    
    # Decorator caching (simple but effective)
    if decorators_found:
        score += 10
        comments.append(f"Decorators: {', '.join(decorators_found)}")
    
    # External cache (production-ready)
    if external_found:
        score += 20
        comments.append(f"External: {', '.join(external_found)}")
    
    # Browser cache
    if browser_found:
        score += 5
        comments.append(f"Browser: {', '.join(browser_found)}")
    
    # TTL configuration (good practice)
    if has_ttl:
        score += 10
        comments.append("Has TTL config")
    
    return {"score": min(100, score), "comment": "; ".join(comments)}


# ============================================================================
# BATCHED LLM ANALYSIS (8 metrics in 1 API call)
# ============================================================================

def _build_batched_prompt(repo: dict[str, Any], company_description: str) -> str:
    """
    Build a single comprehensive prompt for all 8 LLM-based metrics.
    """
    tree = repo.get("tree", [])
    files = repo.get("files", {})
    commits = repo.get("commits", [])
    dependencies = repo.get("dependencies", [])
    code_files = _get_code_files(files)
    
    # === FILE ORGANIZATION CONTEXT ===
    top_level = set()
    all_dirs = set()
    for path in tree[:200]:
        parts = path.split("/")
        if len(parts) > 1:
            top_level.add(parts[0])
            for i in range(1, len(parts)):
                all_dirs.add("/".join(parts[:i]))
    
    # === README CONTEXT ===
    readme_content = ""
    for name in ["README.md", "readme.md", "README.rst", "README.txt", "README"]:
        if name in files:
            readme_content = files[name][:4000]
            break
    
    # === ERROR HANDLING CONTEXT ===
    error_patterns = [r"\btry\s*[:{]", r"\bcatch\s*\(", r"\bexcept\s+\w+", r"\.catch\s*\("]
    error_snippets = []
    for path, content in list(code_files.items())[:15]:
        for pattern in error_patterns:
            snippets = _extract_pattern_context(content, pattern, 20)
            for snippet in snippets[:1]:
                error_snippets.append(f"=== {path} ===\n{snippet}")
                if len(error_snippets) >= 4:
                    break
        if len(error_snippets) >= 4:
            break
    
    # === COMMENTS CONTEXT ===
    comment_samples = []
    for path, content in list(code_files.items())[:10]:
        lines = content.splitlines()
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith("#") or stripped.startswith("//") or '"""' in stripped:
                start = max(0, i - 3)
                end = min(len(lines), i + 8)
                snippet = "\n".join(lines[start:end])
                comment_samples.append(f"=== {path}:{i} ===\n{snippet}")
                if len(comment_samples) >= 5:
                    break
        if len(comment_samples) >= 5:
            break
    
    # === DEPENDENCIES CONTEXT ===
    dep_file_content = {}
    for filename in DEPENDENCY_FILES.keys():
        for path, content in files.items():
            if path.endswith(filename):
                dep_file_content[filename] = content[:2000]
                break
    
    loc = _total_loc(files)
    dep_density = len(dependencies) / (loc / 1000) if loc > 0 else 0
    
    # === COMMIT MESSAGES CONTEXT ===
    messages = [c.get("message", "") for c in commits[:30]]
    low_signal = [r"^fix$", r"^update$", r"^changes?$", r"^wip$", r"^\.+$", r"^test$", r"^commit$"]
    low_signal_count = sum(
        1 for msg in messages 
        if any(re.match(p, msg.strip(), re.I) for p in low_signal) or len(msg.strip()) < 3
    )
    
    # === REAL PROBLEM INDICATORS ===
    real_indicators = []
    ci_files = [".github/workflows", ".gitlab-ci", "Jenkinsfile", ".circleci"]
    if any(any(ci in f for ci in ci_files) for f in tree):
        real_indicators.append("CI/CD pipeline")
    if any("Dockerfile" in f or "docker-compose" in f for f in tree):
        real_indicators.append("Docker configuration")
    if any(".env.example" in f or "config/" in f for f in tree):
        real_indicators.append("Configuration management")
    if any("migrations/" in f or "schema" in f.lower() for f in tree):
        real_indicators.append("Database migrations")
    
    tutorial_indicators = ["todo-app", "hello-world", "calculator", "counter", "weather-app", "tutorial", "sample-app", "demo", "learning", "practice", "exercise"]
    tree_lower = " ".join(tree).lower()
    tutorial_matches = [t for t in tutorial_indicators if t in tree_lower]
    
    # === LANGUAGES DETECTED ===
    lang_extensions = {
        ".py": "Python", ".js": "JavaScript", ".ts": "TypeScript",
        ".java": "Java", ".go": "Go", ".rs": "Rust", ".rb": "Ruby",
        ".cpp": "C++", ".c": "C", ".cs": "C#", ".php": "PHP",
    }
    languages = set()
    for path in tree:
        for ext, lang in lang_extensions.items():
            if path.endswith(ext):
                languages.add(lang)
    
    # === BUILD THE MEGA PROMPT ===
    prompt = f"""You are a code quality analyzer. Analyze this repository and return scores for 8 metrics.

RESPOND ONLY WITH VALID JSON in this exact format (no other text):
{{
  "files_organized": {{"score": <0-100>, "comment": "<brief reason>"}},
  "readme": {{"score": <0-100>, "comment": "<brief reason>"}},
  "error_handling": {{"score": <0-100>, "comment": "<brief reason>"}},
  "comments": {{"score": <0-100>, "comment": "<brief reason>"}},
  "dependencies": {{"score": <0-100>, "comment": "<brief reason>"}},
  "commit_lines": {{"score": <0-100>, "comment": "<brief reason>"}},
  "solves_real_problem": {{"score": <0-100>, "comment": "<brief reason>"}},
  "aligns_company": {{"score": <0-100>, "comment": "<brief reason>"}}
}}

Score guidelines: 0-20=Very poor, 21-40=Poor, 41-60=Average, 61-80=Good, 81-100=Excellent
Keep each comment under 150 chars.

================================================================================
REPOSITORY CONTEXT
================================================================================

### FILE ORGANIZATION
Top-level directories: {sorted(top_level)}
Directory structure sample: {sorted(list(all_dirs)[:25])}
Total files: {len(tree)}
Sample paths: {tree[:40]}

### README
{readme_content if readme_content else "No README found"}

### ERROR HANDLING SAMPLES
{chr(10).join(error_snippets[:4]) if error_snippets else "No try/catch patterns found"}

### COMMENT SAMPLES
{chr(10).join(comment_samples[:5]) if comment_samples else "No comments found"}

### DEPENDENCIES
Count: {len(dependencies)}, Density: {dep_density:.2f} per 1000 LOC
List: {dependencies[:40]}
Dep files: {list(dep_file_content.keys())}
{chr(10).join(f'=== {k} ===\n{v[:1500]}' for k, v in list(dep_file_content.items())[:2])}

### COMMIT MESSAGES
Total: {len(messages)}, Low-signal: {low_signal_count}
{chr(10).join(f"- {msg[:80]}" for msg in messages[:20])}

### REAL PROBLEM INDICATORS
Real-world signs: {real_indicators if real_indicators else "None"}
Tutorial signs: {tutorial_matches if tutorial_matches else "None"}
Commit count: {len(commits)}, File count: {len(tree)}, LOC: {loc}

### COMPANY ALIGNMENT
Company: {company_description}
Languages: {sorted(languages)}
Dependencies: {dependencies[:25]}

================================================================================
EVALUATE THESE 8 METRICS:
1. files_organized: Clear separation? Logical grouping? Reasonable nesting? Follows conventions?
2. readme: Explains purpose? Install instructions? Usage examples? Well-formatted?
3. error_handling: Specific catches? Meaningful handling? Cleanup in finally? Custom exceptions?
4. comments: Explain WHY not WHAT? Docstrings present? Human-written or AI-generated? Appropriate density?
5. dependencies: Pinned versions? Reasonable count? Lock file? Dev/prod separated?
6. commit_lines: Descriptive messages? Conventional format? Human or AI-written? Explains what/why?
7. solves_real_problem: Real problem or tutorial clone? Production-ready features? Professional quality?
8. aligns_company: Tech stack match? Domain relevance? Skills alignment? Relevant experience?
"""
    
    return prompt


# ============================================================================
# MAIN ANALYSIS FUNCTION
# ============================================================================

async def analyze_repository(repo: dict[str, Any], company_description: Optional[str] = None) -> dict[str, Any]:
    """
    Run all 14 metric analyses.
    - 6 metrics use heuristics (no LLM)
    - 8 metrics use a single batched LLM call
    
    Returns dict with all metrics, each containing {"score": 0-100, "comment": "..."}
    Raises RuntimeError if LLM call fails after retry.
    """
    
    # Default company description if not provided
    if not company_description:
        company_description = "A technology company building software products. Looking for developers with strong coding skills, clean code practices, and experience with modern development workflows."
    
    # Run heuristics-based analyses in parallel
    heuristic_results = await asyncio.gather(
        analyze_test_suites(repo),
        analyze_api_keys(repo),
        analyze_print_or_logging(repo),
        analyze_commit_density(repo),
        analyze_concurrency(repo),
        analyze_caching(repo),
        return_exceptions=True
    )
    
    heuristic_names = ["test_suites", "api_keys", "print_or_logging", "commit_density", "concurrency", "caching"]
    
    # Build final results with heuristics
    final_results = {}
    for name, result in zip(heuristic_names, heuristic_results):
        if isinstance(result, Exception):
            final_results[name] = {"score": 50, "comment": f"Analysis error: {str(result)[:100]}"}
        else:
            final_results[name] = result
    
    # Build and execute batched LLM call for remaining 8 metrics
    prompt = _build_batched_prompt(repo, company_description)
    
    # This will raise RuntimeError if both attempts fail
    llm_results = await call_gemini_batched(prompt, retries=1)
    
    # Merge LLM results
    final_results.update(llm_results)
    
    return final_results
