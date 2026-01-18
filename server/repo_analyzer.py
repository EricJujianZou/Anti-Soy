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

async def call_gemini(prompt: str, max_retries: int = 3) -> dict[str, Any]:
    """
    Call Gemini API with a prompt.
    Returns: {"score": 0-100, "comment": "explanation"}
    """
    if not gemini_client:
        return {"score": 50, "comment": "GEMINI_API_KEY not configured"}
    
    try:
        system_prompt = """You are a code quality analyzer. Analyze the provided code/data and respond ONLY with valid JSON in this exact format:
{"score": <integer 0-100>, "comment": "<brief explanation under 200 chars>"}

Score guidelines:
- 0-20: Very poor / Missing entirely
- 21-40: Poor / Major issues
- 41-60: Average / Some issues
- 61-80: Good / Minor issues
- 81-100: Excellent / Best practices

Be concise and specific in your comment."""

        full_prompt = f"{system_prompt}\n\n{prompt}"
        
        # Use async client for Gemini API
        response = await gemini_client.models.generate_content(
            model="gemini-2.0-flash",
            contents=full_prompt,
        )
        
        # Parse response
        text = response.text.strip()
        # Extract JSON from response (handle markdown code blocks)
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()
        
        result = json.loads(text)
        
        # Validate structure
        if "score" not in result or "comment" not in result:
            return {"score": 50, "comment": "Invalid LLM response structure"}
        
        result["score"] = max(0, min(100, int(result["score"])))
        result["comment"] = str(result["comment"])[:500]
        
        return result
        
    except json.JSONDecodeError as e:
        return {"score": 50, "comment": f"Failed to parse LLM response: {str(e)[:100]}"}
    except Exception as e:
        return {"score": 50, "comment": f"LLM error: {str(e)[:100]}"}


# ============================================================================
# METRIC ANALYSIS FUNCTIONS (14 metrics matching RepoData columns)
# ============================================================================

async def analyze_files_organized(repo: dict[str, Any]) -> dict[str, Any]:
    """Analyze file and folder organization quality"""
    tree = repo.get("tree", [])
    files = repo.get("files", {})
    
    if not tree:
        return {"score": 0, "comment": "No files found in repository"}
    
    # Build context for LLM
    top_level = set()
    all_dirs = set()
    for path in tree[:200]:  # Limit for prompt size
        parts = path.split("/")
        if len(parts) > 1:
            top_level.add(parts[0])
            for i in range(1, len(parts)):
                all_dirs.add("/".join(parts[:i]))
    
    prompt = f"""Analyze the file organization of this repository.

Top-level directories: {sorted(top_level)}
Sample of directory structure: {sorted(list(all_dirs)[:30])}
Total files: {len(tree)}
Sample file paths: {tree[:50]}

Evaluate:
1. Is there clear separation (src/, tests/, docs/, etc.)?
2. Are related files grouped logically?
3. Is the nesting depth reasonable?
4. Does it follow common conventions for the project type?"""

    return await call_gemini(prompt)


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


async def analyze_readme(repo: dict[str, Any]) -> dict[str, Any]:
    """Analyze README quality"""
    files = repo.get("files", {})
    
    readme_content = None
    for name in ["README.md", "readme.md", "README.rst", "README.txt", "README"]:
        if name in files:
            readme_content = files[name]
            break
    
    if not readme_content:
        return {"score": 0, "comment": "No README file found"}
    
    prompt = f"""Analyze this README file quality:

{readme_content[:5000]}

Evaluate:
1. Does it explain what the project does?
2. Are there installation/setup instructions?
3. Are there usage examples?
4. Is it well-formatted with headers and code blocks?
5. Does it describe a real-world use case (not just a tutorial)?"""

    return await call_gemini(prompt)


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


async def analyze_error_handling(repo: dict[str, Any]) -> dict[str, Any]:
    """Analyze error handling practices"""
    files = repo.get("files", {})
    code_files = _get_code_files(files)
    
    if not code_files:
        return {"score": 50, "comment": "No code files to analyze"}
    
    # Extract try/catch patterns with context
    error_patterns = [
        r"\btry\s*[:{]",
        r"\bcatch\s*\(",
        r"\bexcept\s+\w+",
        r"\.catch\s*\(",
    ]
    
    error_snippets = []
    for path, content in list(code_files.items())[:20]:
        for pattern in error_patterns:
            snippets = _extract_pattern_context(content, pattern, 30)
            for snippet in snippets[:2]:
                error_snippets.append(f"=== {path} ===\n{snippet}")
    
    prompt = f"""Analyze the error handling quality in this codebase.

Sample error handling code:
{chr(10).join(error_snippets[:5])}

Evaluate:
1. Are exceptions caught specifically (not bare except)?
2. Are errors logged or handled meaningfully?
3. Is there proper cleanup in finally blocks?
4. Are custom exceptions used where appropriate?
5. Is there retry logic for transient failures?"""

    return await call_gemini(prompt)


async def analyze_comments(repo: dict[str, Any]) -> dict[str, Any]:
    """Analyze comment quality - human vs AI written, explains intent"""
    files = repo.get("files", {})
    code_files = _get_code_files(files)
    
    if not code_files:
        return {"score": 50, "comment": "No code files to analyze"}
    
    # Extract comments and docstrings
    comment_samples = []
    
    for path, content in list(code_files.items())[:15]:
        # Find comment blocks
        lines = content.splitlines()
        in_docstring = False
        current_block = []
        
        for i, line in enumerate(lines):
            stripped = line.strip()
            
            # Python docstrings
            if '"""' in stripped or "'''" in stripped:
                if in_docstring:
                    current_block.append(line)
                    comment_samples.append(f"=== {path}:{i} ===\n" + "\n".join(current_block))
                    current_block = []
                    in_docstring = False
                else:
                    in_docstring = True
                    current_block = [line]
            elif in_docstring:
                current_block.append(line)
            # Single line comments
            elif stripped.startswith("#") or stripped.startswith("//"):
                # Get context around comment
                start = max(0, i - 5)
                end = min(len(lines), i + 10)
                snippet = "\n".join(lines[start:end])
                comment_samples.append(f"=== {path}:{i} ===\n{snippet}")
    
    prompt = f"""Analyze the comment quality in this codebase.

Sample comments and docstrings:
{chr(10).join(comment_samples[:8])}

Evaluate:
1. Do comments explain WHY (intent) rather than just WHAT (behavior)?
2. Are docstrings present for functions/classes?
3. Do comments appear human-written (specific, contextual) or AI-generated (generic, obvious)?
4. Is the comment density appropriate (not too few, not excessive)?
5. Are complex algorithms or business logic explained?"""

    return await call_gemini(prompt)


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


async def analyze_dependencies(repo: dict[str, Any]) -> dict[str, Any]:
    """Analyze dependency management"""
    dependencies = repo.get("dependencies", [])
    files = repo.get("files", {})
    
    # Find dependency files
    dep_file_content = {}
    for filename in DEPENDENCY_FILES.keys():
        for path, content in files.items():
            if path.endswith(filename):
                dep_file_content[filename] = content[:3000]
    
    loc = _total_loc(files)
    density = len(dependencies) / (loc / 1000) if loc > 0 else 0
    
    prompt = f"""Analyze the dependency management of this project.

Dependencies found: {len(dependencies)}
Dependency list: {dependencies[:50]}
Lines of code: {loc}
Dependency density: {density:.2f} deps per 1000 LOC

Dependency files:
{chr(10).join(f'=== {k} ===\n{v}' for k, v in list(dep_file_content.items())[:3])}

Evaluate:
1. Are dependencies pinned to specific versions?
2. Is the number of dependencies reasonable for the project size?
3. Are there obvious unnecessary dependencies?
4. Is there a lock file (package-lock.json, poetry.lock, etc.)?
5. Are dev dependencies separated from production?"""

    return await call_gemini(prompt)


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


async def analyze_commit_lines(repo: dict[str, Any]) -> dict[str, Any]:
    """Analyze commit message quality - detect AI-generated messages"""
    commits = repo.get("commits", [])
    
    if not commits:
        return {"score": 50, "comment": "No git history available"}
    
    # Get commit messages
    messages = [c.get("message", "") for c in commits[:50]]
    
    # Low signal patterns
    low_signal = [
        r"^fix$", r"^update$", r"^changes?$", r"^wip$",
        r"^\.+$", r"^asdf+$", r"^test$", r"^commit$",
    ]
    
    low_signal_count = sum(
        1 for msg in messages 
        if any(re.match(p, msg.strip(), re.I) for p in low_signal) or len(msg.strip()) < 3
    )
    
    prompt = f"""Analyze the commit message quality in this repository.

Total commits analyzed: {len(messages)}
Low-signal commits (wip, fix, update, etc.): {low_signal_count}

Sample commit messages:
{chr(10).join(f"- {msg[:100]}" for msg in messages[:25])}

Evaluate:
1. Are commit messages descriptive and meaningful?
2. Do they follow conventional commit format (feat:, fix:, etc.)?
3. Do messages appear human-written or AI-generated (too perfect, generic)?
4. Is there a pattern of lazy commit messages (wip, fix, update)?
5. Do messages explain WHAT changed and WHY?"""

    return await call_gemini(prompt)


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


async def analyze_solves_real_problem(repo: dict[str, Any]) -> dict[str, Any]:
    """Analyze if project solves a real problem vs tutorial/toy project"""
    tree = repo.get("tree", [])
    files = repo.get("files", {})
    commits = repo.get("commits", [])
    
    if not tree:
        return {"score": 0, "comment": "No files found"}
    
    # Get README
    readme_content = ""
    for name in ["README.md", "readme.md", "README.rst", "README"]:
        if name in files:
            readme_content = files[name][:4000]
            break
    
    # Indicators of real project
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
    
    # Tutorial indicators
    tutorial_indicators = [
        "todo-app", "hello-world", "calculator", "counter",
        "weather-app", "tutorial", "sample-app", "demo",
        "learning", "practice", "exercise",
    ]
    
    tree_lower = " ".join(tree).lower()
    tutorial_matches = [t for t in tutorial_indicators if t in tree_lower]
    
    prompt = f"""Analyze if this project solves a real-world problem or is a tutorial/toy project.

README content:
{readme_content if readme_content else "No README found"}

Real-world indicators found: {real_indicators if real_indicators else "None"}
Tutorial/toy indicators found: {tutorial_matches if tutorial_matches else "None"}

Commit count: {len(commits)}
File count: {len(tree)}
Lines of code: {_total_loc(files)}

Evaluate:
1. Does the README describe solving a real problem?
2. Is this a tutorial clone (todo app, calculator, etc.)?
3. Does the project complexity suggest real usage?
4. Are there production-ready features (CI, Docker, configs)?
5. Is this something that could be used in a professional context?"""

    return await call_gemini(prompt)


async def analyze_aligns_company(repo: dict[str, Any], company_description: Optional[str] = None) -> dict[str, Any]:
    """Analyze if project aligns with company mission/tech stack"""
    tree = repo.get("tree", [])
    files = repo.get("files", {})
    dependencies = repo.get("dependencies", [])
    
    if not company_description:
        return {"score": 50, "comment": "No company description provided for alignment analysis"}
    
    # Get README
    readme_content = ""
    for name in ["README.md", "readme.md", "README.rst", "README"]:
        if name in files:
            readme_content = files[name][:3000]
            break
    
    # Detect languages
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
    
    prompt = f"""Analyze if this project aligns with the company's needs.

COMPANY DESCRIPTION:
{company_description}

PROJECT DETAILS:
README: {readme_content if readme_content else "No README"}
Languages used: {sorted(languages)}
Dependencies: {dependencies[:30]}
File structure sample: {tree[:30]}

Evaluate:
1. Does the tech stack match what the company uses?
2. Does the project domain relate to the company's industry?
3. Do the skills demonstrated align with the job requirements?
4. Would this project experience be relevant to the role?"""

    return await call_gemini(prompt)


# ============================================================================
# MAIN ANALYSIS FUNCTION
# ============================================================================

async def analyze_repository(repo: dict[str, Any], company_description: Optional[str] = None) -> dict[str, Any]:
    """
    Run all 14 metric analyses in parallel.
    Returns dict with all metrics, each containing {"score": 0-100, "comment": "..."}
    """
    
    # Run all analyses in parallel
    results = await asyncio.gather(
        analyze_files_organized(repo),
        analyze_test_suites(repo),
        analyze_readme(repo),
        analyze_api_keys(repo),
        analyze_error_handling(repo),
        analyze_comments(repo),
        analyze_print_or_logging(repo),
        analyze_dependencies(repo),
        analyze_commit_density(repo),
        analyze_commit_lines(repo),
        analyze_concurrency(repo),
        analyze_caching(repo),
        analyze_solves_real_problem(repo),
        analyze_aligns_company(repo, company_description),
        return_exceptions=True
    )
    
    # Handle any exceptions
    metric_names = [
        "files_organized", "test_suites", "readme", "api_keys",
        "error_handling", "comments", "print_or_logging", "dependencies",
        "commit_density", "commit_lines", "concurrency", "caching",
        "solves_real_problem", "aligns_company"
    ]
    
    final_results = {}
    for name, result in zip(metric_names, results):
        if isinstance(result, Exception):
            final_results[name] = {"score": 50, "comment": f"Analysis error: {str(result)[:100]}"}
        else:
            final_results[name] = result
    
    return final_results
