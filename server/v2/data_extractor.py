"""
Data Extractor for Anti-Soy V2

Handles repository cloning and raw data extraction.
This module extracts data only — no analysis or signal detection.
"""

import json
import logging
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


# =============================================================================
# CONFIGURATION
# =============================================================================

# File size limits
MAX_FILE_SIZE = 200 * 1024  # 200KB per file
MAX_TOTAL_CONTENT = 5 * 1024 * 1024  # 5MB total content
FILE_TARGET_MIN = 15        # Always read at least 15 files
FILE_TARGET_PERCENTAGE = 0.15  # Read up to 15% of total code files
FILE_TARGET_MAX = 50        # Never read more than 50 files

# Code file extensions we care about
CODE_EXTENSIONS = (
    ".py", ".js", ".ts", ".jsx", ".tsx",  # Python, JavaScript, TypeScript
    ".java", ".go", ".rb", ".rs",          # Java, Go, Ruby, Rust
    ".cpp", ".c", ".cs", ".h", ".hpp",     # C/C++/C#
    ".php", ".swift", ".kt", ".scala",     # PHP, Swift, Kotlin, Scala
    ".vue", ".svelte",                      # Frontend frameworks
    ".sql", ".sh", ".bash",                 # SQL, Shell
)

# Test file indicators
TEST_INDICATORS = (
    'test_', '_test.', '.test.', '.spec.',
    '/tests/', '/test/', '/__tests__/',
    'conftest.py', 'pytest', 'unittest',
    # C# test conventions
    'tests.cs', '.tests/', '.test/',
)


# =============================================================================
# SHARED HELPER FUNCTIONS
# =============================================================================

def is_code_file(file_path: str) -> bool:
    """Check if file is a code file based on extension."""
    return file_path.endswith(CODE_EXTENSIONS)


def is_test_file(file_path: str) -> bool:
    """Check if file is a test file based on path patterns."""
    file_lower = file_path.lower()
    return any(indicator in file_lower for indicator in TEST_INDICATORS)


# Config/doc files we also want to read (for analysis)
INCLUDE_FILES = (
    ".gitignore", ".env", ".env.example", ".env.local",
    "README.md", "readme.md", "README.rst", "README.txt", "README",
    "package.json", "package-lock.json", "yarn.lock",
    "requirements.txt", "pyproject.toml", "setup.py", "Pipfile", "Pipfile.lock",
    "go.mod", "go.sum", "Cargo.toml", "Cargo.lock",
    "Gemfile", "Gemfile.lock", "pom.xml", "build.gradle",
    "composer.json", "composer.lock",
    "Dockerfile", "docker-compose.yml", "docker-compose.yaml",
    "Startup.cs", "Program.cs",
    ".cursorrules", "CLAUDE.md", ".github/copilot-instructions.md",
    "tsconfig.json", "jsconfig.json", ".eslintrc", ".eslintrc.js", ".eslintrc.json",
    "pytest.ini", "setup.cfg", "jest.config.js", "jest.config.ts",
)

# Binary/generated extensions to skip entirely
SKIP_EXTENSIONS = (
    ".png", ".jpg", ".jpeg", ".gif", ".ico", ".svg", ".webp",
    ".woff", ".woff2", ".ttf", ".eot", ".otf",
    ".mp3", ".mp4", ".wav", ".avi", ".mov",
    ".zip", ".tar", ".gz", ".rar", ".7z",
    ".pdf", ".doc", ".docx", ".xls", ".xlsx",
    ".exe", ".dll", ".so", ".dylib",
    ".pyc", ".pyo", ".class", ".o", ".obj",
    ".lock", ".min.js", ".min.css", ".map",
)

# Directories to skip reading contents (but still note their existence in tree)
SKIP_DIRS = (
    "node_modules", "venv", ".venv", "env", ".env",
    "__pycache__", ".git", "dist", "build", ".next",
    "coverage", ".nyc_output", ".pytest_cache", ".mypy_cache",
    "vendor", "target", "bin", "obj",
    ".idea", ".vscode", ".vs",
    # Blacklist directories (no value in reading)
    "migrations", "migration",
    "__mocks__", "fixtures", "__fixtures__", "mocks",
)

# Files to NEVER read (blacklist) - appear in tree but never in files
# These are either too large, auto-generated, or have zero analytical value
BLACKLIST_FILES = (
    # Lock files (huge, auto-generated)
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml",
    "pipfile.lock", "gemfile.lock", "cargo.lock",
    "composer.lock", "go.sum", "poetry.lock",
    # Config boilerplate (low signal, often copied)
    "tsconfig.json", "jsconfig.json",
    ".eslintrc", ".eslintrc.js", ".eslintrc.json", ".eslintrc.yaml", ".eslintrc.yml",
    "vite.config.js", "vite.config.ts",
    "webpack.config.js", "webpack.config.ts",
    "babel.config.js", "babel.config.json", ".babelrc",
    "tailwind.config.js", "tailwind.config.ts",
    "postcss.config.js", "postcss.config.cjs", "postcss.config.mjs",
    "jest.config.js", "jest.config.ts", "jest.config.json",
    "prettier.config.js", ".prettierrc", ".prettierrc.js", ".prettierrc.json",
    "rollup.config.js", "rollup.config.ts",
    "vitest.config.ts", "vitest.config.js",
    ".editorconfig", ".gitattributes",
    "next.config.js", "next.config.mjs", "next.config.ts",
    "nuxt.config.js", "nuxt.config.ts",
)

# Dependency file patterns for extraction
DEPENDENCY_FILES = {
    "requirements.txt": "python",
    "pyproject.toml": "python",
    "setup.py": "python",
    "Pipfile": "python",
    "package.json": "javascript",
    "go.mod": "go",
    "Cargo.toml": "rust",
    "Gemfile": "ruby",
    "pom.xml": "java",
    "build.gradle": "java",
    "composer.json": "php",
    ".csproj": "csharp",
}

# Language detection by extension
EXTENSION_TO_LANGUAGE = {
    ".py": "Python",
    ".js": "JavaScript",
    ".ts": "TypeScript",
    ".jsx": "JavaScript",
    ".tsx": "TypeScript",
    ".java": "Java",
    ".go": "Go",
    ".rb": "Ruby",
    ".rs": "Rust",
    ".cpp": "C++",
    ".c": "C",
    ".cs": "C#",
    ".h": "C",
    ".hpp": "C++",
    ".php": "PHP",
    ".swift": "Swift",
    ".kt": "Kotlin",
    ".scala": "Scala",
    ".vue": "Vue",
    ".svelte": "Svelte",
    ".sql": "SQL",
    ".sh": "Shell",
    ".bash": "Shell",
}


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class CommitInfo:
    """Information about a single git commit"""
    hash: str
    message: str
    author: str
    date: str  # ISO format date string
    files_changed: int = 0
    additions: int = 0
    deletions: int = 0


@dataclass
class FileInfo:
    """Information about a file for importance scoring"""
    rel_path: str
    abs_path: Path
    size: int
    importance_score: int = 0


@dataclass
class RepoData:
    """
    Raw extracted data from a repository.
    This is the output of the data extractor, fed into analyzers.
    """
    repo_path: Path
    tree: list[str] = field(default_factory=list)  # All file paths
    files: dict[str, str] = field(default_factory=dict)  # path -> content
    file_importance: dict[str, int] = field(default_factory=dict)  # path -> importance score (for files read)
    commits: list[CommitInfo] = field(default_factory=list)
    languages: dict[str, int] = field(default_factory=dict)  # language -> bytes
    dependencies: list[str] = field(default_factory=list)
    total_loc: int = 0


# =============================================================================
# DEPLOYMENT SIGNAL DETECTION
# =============================================================================

DEPLOY_URL_PATTERN = re.compile(
    r'https?://[\w.-]+\.(?:vercel\.app|netlify\.app|herokuapp\.com|fly\.dev|'
    r'onrender\.com|railway\.app|azurewebsites\.net|web\.app|pages\.dev)',
    re.IGNORECASE,
)

DEPLOY_HEADER_PATTERN = re.compile(
    r'#+\s*(?:demo|live|deployed|production|website)\b',
    re.IGNORECASE,
)


def detect_deployment_signals(repo_data: "RepoData") -> dict:
    """
    Detect signals that a project has been deployed to production.
    Uses already-extracted RepoData — does NOT re-clone.

    Returns:
        {"shipped_to_prod": bool, "signals": ["Dockerfile found", ...]}
    """
    signals: list[str] = []
    tree_lower = {p.lower() for p in repo_data.tree}
    tree_set = set(repo_data.tree)

    # --- File presence checks ---
    if any(p == "dockerfile" or p.endswith("/dockerfile") for p in tree_lower):
        signals.append("Dockerfile found")

    if any("docker-compose.yml" in p or "docker-compose.yaml" in p for p in tree_lower):
        signals.append("Docker Compose configuration found")

    if any("k8s/" in p or "kubernetes/" in p or ".k8s/" in p for p in tree_lower):
        signals.append("Kubernetes manifests found")

    if "vercel.json" in tree_lower:
        signals.append("Vercel deployment config found")

    if "netlify.toml" in tree_lower:
        signals.append("Netlify deployment config found")

    if "fly.toml" in tree_lower:
        signals.append("Fly.io deployment config found")

    if "procfile" in tree_lower:
        signals.append("Heroku Procfile found")

    if any("appspec.yml" in p for p in tree_lower):
        signals.append("AWS CodeDeploy config found")

    if any("cloudbuild.yaml" in p or "/app.yaml" in p or p == "app.yaml" for p in tree_lower):
        signals.append("GCP deployment config found")

    if "render.yaml" in tree_lower:
        signals.append("Render deployment config found")

    if any("railway.json" in p or "railway.toml" in p for p in tree_lower):
        signals.append("Railway deployment config found")

    if any("terraform/" in p or "cdk/" in p or "pulumi/" in p for p in tree_lower):
        signals.append("Infrastructure-as-code directory found")

    # --- GitHub Actions with deploy keywords ---
    for path in repo_data.tree:
        path_lower = path.lower()
        if ".github/workflows/" in path_lower and (path_lower.endswith(".yml") or path_lower.endswith(".yaml")):
            content = repo_data.files.get(path, "")
            if not content:
                # Try case-insensitive lookup
                for k, v in repo_data.files.items():
                    if k.lower() == path_lower:
                        content = v
                        break
            if any(kw in content.lower() for kw in ("deploy", "release", "publish", "production")):
                signals.append("GitHub Actions workflow found")
                break

    # --- README URL / section checks ---
    readme_content = ""
    for path, content in repo_data.files.items():
        if path.lower().startswith("readme"):
            readme_content = content
            break

    if readme_content:
        if DEPLOY_URL_PATTERN.search(readme_content):
            signals.append("Live deployment URL found in README")
        if DEPLOY_HEADER_PATTERN.search(readme_content):
            # Make sure there's an actual URL near the header
            if "http" in readme_content.lower():
                signals.append("Live demo section found in README")

    return {"shipped_to_prod": len(signals) > 0, "signals": signals}


# =============================================================================
# MAIN EXTRACTION FUNCTION
# =============================================================================

def extract_repo_data(repo_path: str | Path) -> RepoData:
    """
    Extract all necessary data from a cloned repository.
    
    Uses importance scoring to prioritize reading important files first,
    ensuring we don't hit size limits reading unimportant files.
    
    Args:
        repo_path: Path to the cloned repository
        
    Returns:
        RepoData object containing all extracted information
    """
    repo_path = Path(repo_path)
    
    # Initialize result
    result = RepoData(repo_path=repo_path)
    
    # ==========================================================================
    # PASS 1: Walk repo, collect all file paths + sizes (no content yet)
    # ==========================================================================
    all_files: list[FileInfo] = []
    
    for file_path in repo_path.rglob("*"):
        if not file_path.is_file():
            continue
            
        # Get relative path (normalized with forward slashes)
        rel_path = str(file_path.relative_to(repo_path)).replace("\\", "/")
        
        # Always add to tree (so we can detect node_modules, etc.)
        result.tree.append(rel_path)
        
        # Check if in a skip directory (skip reading content, not tree listing)
        path_parts = rel_path.split("/")
        if any(skip_dir in path_parts for skip_dir in SKIP_DIRS):
            continue
        
        # Skip binary/generated files
        if file_path.suffix.lower() in SKIP_EXTENSIONS:
            continue
        
        # Skip blacklisted files (never read, zero value)
        filename = file_path.name
        if filename.lower() in BLACKLIST_FILES:
            continue
        
        # Check if we should consider reading this file
        is_code_file = file_path.suffix.lower() in CODE_EXTENSIONS
        is_include_file = filename in INCLUDE_FILES or rel_path in INCLUDE_FILES
        # Also include C# project files and Go module files by extension
        is_project_file = file_path.suffix.lower() in (".csproj", ".sln")

        if not (is_code_file or is_include_file or is_project_file):
            continue
        
        # Get file size
        try:
            file_size = file_path.stat().st_size
            if file_size > MAX_FILE_SIZE:
                continue
                
            all_files.append(FileInfo(
                rel_path=rel_path,
                abs_path=file_path,
                size=file_size,
            ))
        except (OSError, IOError):
            continue
    
    # ==========================================================================
    # PASS 2: Score files by importance
    # ==========================================================================
    for file_info in all_files:
        file_info.importance_score = _calculate_file_importance(file_info.rel_path, file_info.size)
    
    # Sort by importance (highest first)
    all_files.sort(key=lambda f: f.importance_score, reverse=True)
    
    # ==========================================================================
    # PASS 3: Read content in importance order until limit
    # ==========================================================================
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
    
    # Extract git commits
    result.commits = _get_git_commits(repo_path)
    
    # Extract dependencies
    result.dependencies = _extract_dependencies(result.files)
    
    # Calculate total LOC
    result.total_loc = _calculate_total_loc(result.files)
    
    return result


# =============================================================================
# FILE IMPORTANCE SCORING
# =============================================================================

def _calculate_file_importance(rel_path: str, file_size: int) -> int:
    """
    Calculate importance score for a file based on path patterns and size.
    
    Higher score = more important = read first.
    
    Args:
        rel_path: Relative path of the file
        file_size: Size of file in bytes
        
    Returns:
        Importance score (can be negative)
    """
    score = 50  # Base score
    
    filename = rel_path.split("/")[-1].lower()
    path_lower = rel_path.lower()
    path_parts = rel_path.lower().split("/")
    
    # -------------------------------------------------------------------------
    # POSITIVE SIGNALS (important files)
    # -------------------------------------------------------------------------
    
    # Entry points - highest priority
    entry_points = ["main.py", "app.py", "server.py", "index.py", "run.py",
                    "index.js", "index.ts", "app.js", "app.ts", "server.js", "server.ts",
                    "main.go", "main.rs", "main.java",
                    "program.cs", "startup.cs"]
    if filename in entry_points:
        score += 40
    
    # Core application directories
    core_dirs = ["src", "api", "services", "core", "lib", "models", "controllers", 
                 "routes", "handlers", "middleware", "domain", "application"]
    if any(d in path_parts for d in core_dirs):
        score += 15
    
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

    # Backend/server code (often more complex logic)
    if "server" in path_parts or "backend" in path_parts or "api" in path_parts:
        score += 10
    
    # Config files (important for understanding project)
    config_files = ["package.json", "pyproject.toml", "requirements.txt", 
                    "dockerfile", "docker-compose.yml", "docker-compose.yaml",
                    ".env.example", "config.py", "settings.py", "config.js", "config.ts"]
    if filename in config_files:
        score += 0 #no boost for now, maybe later
        
    
    # AI instruction files (very important for our analysis)
    ai_files = [".cursorrules", "claude.md", ".github/copilot-instructions.md"]
    if filename in ai_files or path_lower in ai_files:
        score += 35
    
    # README (important context)
    if filename.startswith("readme"):
        score += 15
    
    # Meaningful size bonus (50-500 lines estimated, assuming ~40 bytes/line)
    estimated_lines = file_size / 40
    if 50 <= estimated_lines <= 500:
        score += 20
    elif 20 <= estimated_lines < 50:
        score += 10
    elif estimated_lines > 500:
        score += 5  # Still valuable, but might be bloated
    
    # -------------------------------------------------------------------------
    # NEGATIVE SIGNALS (less important files)
    # -------------------------------------------------------------------------
    
    # Test files - lower priority (still read, but after core code)
    test_patterns = ["test_", "_test.", ".test.", ".spec.", "__tests__", "tests/", "spec/"]
    if any(p in path_lower for p in test_patterns):
        score -= 25
    
    # UI component libraries (often boilerplate)
    ui_patterns = ["components/ui/", "ui/components/", "/ui/", "shadcn"]
    if any(p in path_lower for p in ui_patterns):
        score -= 35
    
    # Hooks, utils, helpers (often small utility code)
    util_patterns = ["/hooks/", "/utils/", "/helpers/", "/constants/", "/types/"]
    if any(p in path_lower for p in util_patterns):
        score -= 20
    
    # Low signal config (already in blacklist, but catch patterns)
    low_signal_patterns = ["config.js", "config.ts", ".config."]
    if any(p in filename for p in low_signal_patterns):
        score -= 15
    
    # Migration files (directory already blacklisted, but catch stragglers)
    if "migration" in path_lower:
        score -= 30
    
    # Fixture/mock data (directory already blacklisted, but catch stragglers)
    if "fixture" in path_lower or "mock" in path_lower:
        score -= 30
    
    return score


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def _get_git_commits(repo_path: Path, max_commits: int = 500) -> list[CommitInfo]:
    """
    Extract git commit history.
    
    Args:
        repo_path: Path to the repository
        max_commits: Maximum number of commits to extract
        
    Returns:
        List of CommitInfo objects
    """
    commits = []
    
    try:
        # Get commit log with stats (--no-pager prevents blocking on less/pager)
        result = subprocess.run(
            [
                "git", "--no-pager", "log",
                f"-{max_commits}",
                "--pretty=format:%H|||%s|||%an|||%ad",
                "--date=short",
                "--numstat",
                "--no-pager"
            ],
            cwd=repo_path,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='ignore',  # Ignore Unicode decode errors (emoji, special chars)
            timeout=60
        )
        
        if result.returncode != 0 or not result.stdout:
            return commits

        current_commit: CommitInfo | None = None

        for line in result.stdout.split("\n"):
            if "|||" in line:
                # Save previous commit
                if current_commit:
                    commits.append(current_commit)
                
                # Parse new commit line
                parts = line.split("|||")
                current_commit = CommitInfo(
                    hash=parts[0],
                    message=parts[1] if len(parts) > 1 else "",
                    author=parts[2] if len(parts) > 2 else "",
                    date=parts[3] if len(parts) > 3 else "",
                )
            elif line.strip() and current_commit:
                # Parse numstat line: additions\tdeletions\tfilename
                parts = line.split("\t")
                if len(parts) >= 2:
                    try:
                        additions = int(parts[0]) if parts[0] != "-" else 0
                        deletions = int(parts[1]) if parts[1] != "-" else 0
                        current_commit.files_changed += 1
                        current_commit.additions += additions
                        current_commit.deletions += deletions
                    except ValueError:
                        pass
        
        # Don't forget the last commit
        if current_commit:
            commits.append(current_commit)
            
    except subprocess.TimeoutExpired:
        logger.warning("Git log timed out for %s", repo_path)
    except Exception as e:
        logger.error("Error getting git commits: %s", e, exc_info=True)
    
    return commits


def _extract_dependencies(files: dict[str, str]) -> list[str]:
    """
    Extract dependency names from various package files.
    
    Args:
        files: Dictionary of file path -> content
        
    Returns:
        Deduplicated list of dependency names
    """
    dependencies = []
    
    for filepath, content in files.items():
        filename = filepath.split("/")[-1]
        
        if filename == "requirements.txt":
            dependencies.extend(_parse_requirements_txt(content))
        elif filename == "package.json":
            dependencies.extend(_parse_package_json(content))
        elif filename == "pyproject.toml":
            dependencies.extend(_parse_pyproject_toml(content))
        elif filename == "go.mod":
            dependencies.extend(_parse_go_mod(content))
        elif filename == "Cargo.toml":
            dependencies.extend(_parse_cargo_toml(content))
        elif filename == "Gemfile":
            dependencies.extend(_parse_gemfile(content))
        elif filename.endswith(".csproj"):
            dependencies.extend(_parse_csproj(content))
    
    # Deduplicate while preserving order
    seen = set()
    unique_deps = []
    for dep in dependencies:
        if dep not in seen:
            seen.add(dep)
            unique_deps.append(dep)
    
    return unique_deps


def _parse_requirements_txt(content: str) -> list[str]:
    """Parse Python requirements.txt"""
    deps = []
    for line in content.splitlines():
        line = line.strip()
        if line and not line.startswith("#") and not line.startswith("-"):
            # Extract package name (before ==, >=, etc.)
            pkg = re.split(r"[=<>!~\[\];]", line)[0].strip()
            if pkg:
                deps.append(pkg)
    return deps


def _parse_package_json(content: str) -> list[str]:
    """Parse JavaScript package.json"""
    deps = []
    try:
        data = json.loads(content)
        for key in ["dependencies", "devDependencies", "peerDependencies"]:
            if key in data and isinstance(data[key], dict):
                deps.extend(data[key].keys())
    except json.JSONDecodeError:
        pass
    return deps


def _parse_pyproject_toml(content: str) -> list[str]:
    """Parse Python pyproject.toml (simple parsing, not full TOML)"""
    deps = []
    in_deps = False
    
    for line in content.splitlines():
        line_stripped = line.strip()
        
        # Check for dependencies section
        if "dependencies" in line_stripped and "=" in line_stripped:
            in_deps = True
            # Handle inline list: dependencies = ["pkg1", "pkg2"]
            if "[" in line_stripped:
                matches = re.findall(r'"([a-zA-Z0-9_-]+)', line_stripped)
                deps.extend(matches)
        elif in_deps:
            if line_stripped.startswith("[") and "dependencies" not in line_stripped:
                in_deps = False
            else:
                # Parse dependency line
                match = re.match(r'^\s*"?([a-zA-Z0-9_-]+)', line_stripped)
                if match:
                    deps.append(match.group(1))
    
    return deps


def _parse_go_mod(content: str) -> list[str]:
    """Parse Go go.mod"""
    deps = []
    for line in content.splitlines():
        line = line.strip()
        if line.startswith("require"):
            continue
        match = re.match(r"^\s*([a-zA-Z0-9._/-]+)\s+v", line)
        if match and "/" in match.group(1):
            deps.append(match.group(1))
    return deps


def _parse_cargo_toml(content: str) -> list[str]:
    """Parse Rust Cargo.toml"""
    deps = []
    in_deps = False
    
    for line in content.splitlines():
        line_stripped = line.strip()
        
        if "[dependencies]" in line_stripped or "[dev-dependencies]" in line_stripped:
            in_deps = True
        elif line_stripped.startswith("[") and in_deps:
            in_deps = False
        elif in_deps and "=" in line_stripped:
            pkg = line_stripped.split("=")[0].strip()
            if pkg:
                deps.append(pkg)
    
    return deps


def _parse_gemfile(content: str) -> list[str]:
    """Parse Ruby Gemfile"""
    deps = []
    for line in content.splitlines():
        match = re.match(r"^\s*gem\s+['\"]([^'\"]+)['\"]", line)
        if match:
            deps.append(match.group(1))
    return deps


def _parse_csproj(content: str) -> list[str]:
    """Parse C# .csproj for NuGet PackageReference dependencies."""
    deps = []
    for match in re.finditer(r'<PackageReference\s+Include="([^"]+)"', content):
        deps.append(match.group(1))
    return deps


def _calculate_total_loc(files: dict[str, str]) -> int:
    """
    Calculate total lines of code across all code files.
    
    Args:
        files: Dictionary of file path -> content
        
    Returns:
        Total line count
    """
    total = 0
    for filepath, content in files.items():
        # Only count code files
        if any(filepath.endswith(ext) for ext in CODE_EXTENSIONS):
            total += len(content.splitlines())
    return total


# =============================================================================
# CLONE FUNCTION
# =============================================================================

def clone_repository(repo_url: str, target_path: Path, timeout: int = 300) -> bool:
    """
    Clone a git repository.
    
    Args:
        repo_url: GitHub repository URL
        target_path: Where to clone to
        timeout: Timeout in seconds
        
    Returns:
        True if successful, False otherwise
    """
    try:
        result = subprocess.run(
            ["git", "clone", repo_url, str(target_path)],
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='ignore',  # Ignore Unicode decode errors
            timeout=timeout
        )
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        logger.warning("Clone timed out for %s", repo_url)
        return False
    except Exception as e:
        logger.error("Clone failed for %s: %s", repo_url, e, exc_info=True)
        return False
