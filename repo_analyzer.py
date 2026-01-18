import re
import ast
import asyncio
from typing import Any
from collections import Counter


LAYER_PATTERNS = {
    "controllers": r"(controller|handler|endpoint|route)",
    "services": r"(service|usecase|interactor)",
    "repositories": r"(repository|repo|dao|store|adapter)",
    "models": r"(model|entity|domain|schema)",
    "views": r"(view|template|component|page)",
    "utils": r"(util|helper|common|shared|lib)",
}

MVC_DIRS = {"models", "views", "controllers", "templates"}
LAYERED_DIRS = {"domain", "application", "infrastructure", "presentation", "services", "repositories"}

SECRET_PATTERNS = [
    (r"(?i)(api[_-]?key|apikey)\s*[=:]\s*['\"][a-zA-Z0-9]{16,}['\"]", "api_key"),
    (r"(?i)(secret[_-]?key|secretkey)\s*[=:]\s*['\"][a-zA-Z0-9]{16,}['\"]", "secret_key"),
    (r"(?i)(password|passwd|pwd)\s*[=:]\s*['\"][^'\"]{4,}['\"]", "password"),
    (r"(?i)(token|auth[_-]?token)\s*[=:]\s*['\"][a-zA-Z0-9_\-\.]{20,}['\"]", "token"),
    (r"(?i)(aws[_-]?access[_-]?key[_-]?id)\s*[=:]\s*['\"]AKIA[A-Z0-9]{16}['\"]", "aws_key"),
    (r"(?i)(private[_-]?key)\s*[=:]\s*['\"]-----BEGIN", "private_key"),
    (r"ghp_[a-zA-Z0-9]{36}", "github_token"),
    (r"sk-[a-zA-Z0-9]{32,}", "openai_key"),
]

ENV_VAR_PATTERNS = [
    r"os\.environ\.get\s*\(",
    r"os\.environ\[",
    r"os\.getenv\s*\(",
    r"process\.env\.",
    r"Environment\.get",
    r"config\.[a-zA-Z_]+\s*=\s*os\.",
]

AI_COMMENT_PATTERNS = [
    r"(?i)generated\s+by\s+(ai|gpt|claude|copilot|chatgpt)",
    r"(?i)ai[- ]generated",
    r"(?i)this\s+(code|function|class)\s+(was\s+)?generated",
    r"(?i)auto[- ]?generated\s+by",
    r"(?i)created\s+with\s+(ai|gpt|copilot)",
]

LOW_SIGNAL_COMMITS = [
    r"^fix$",
    r"^update$",
    r"^changes?$",
    r"^wip$",
    r"^\.+$",
    r"^asdf+$",
    r"^test$",
    r"^tmp$",
    r"^temp$",
    r"^stuff$",
    r"^commit$",
    r"^save$",
    r"^[a-z]$",
]

TUTORIAL_INDICATORS = [
    "todo-app", "todo-list", "todoapp", "todolist",
    "hello-world", "helloworld",
    "calculator", "counter-app",
    "weather-app", "weatherapp",
    "blog-tutorial", "tutorial-project",
    "sample-app", "sampleapp",
    "demo-project", "demoproj",
    "learning-", "learn-",
    "practice-", "exercise-",
]

BOILERPLATE_FILES = [
    "create-react-app", "vite", "next.js starter",
    "express-generator", "django-admin startproject",
    "rails new", "spring initializr",
]


def _get_dir_structure(tree: list[str]) -> set[str]:
    """
    Extracts all directory paths from a file tree.

    Takes a list of file paths and returns a set of all parent directories
    at every level. For example, 'src/utils/helper.py' yields {'src', 'src/utils'}.
    """
    dirs = set()
    for path in tree:
        parts = path.split("/")
        for i in range(1, len(parts)):
            dirs.add("/".join(parts[:i]))
    return dirs


def _get_top_level_dirs(tree: list[str]) -> set[str]:
    return {path.split("/")[0] for path in tree if "/" in path}


def _count_pattern_matches(files: dict[str, str], pattern: str, extensions: tuple = None) -> int:
    count = 0
    regex = re.compile(pattern, re.IGNORECASE)
    for path, content in files.items():
        if extensions and not path.endswith(extensions):
            continue
        count += len(regex.findall(content))
    return count


def _get_code_files(files: dict[str, str]) -> dict[str, str]:
    code_extensions = (".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".go", ".rb", ".rs", ".cpp", ".c", ".cs")
    return {k: v for k, v in files.items() if k.endswith(code_extensions)}


def _total_loc(files: dict[str, str]) -> int:
    code_files = _get_code_files(files)
    return sum(len(content.splitlines()) for content in code_files.values())


async def analyze_architecture(repo: dict[str, Any]) -> dict[str, Any]:
    tree = repo.get("tree", [])
    files = repo.get("files", {})

    if not tree:
        return {
            "architecture_pattern": "UNKNOWN",
            "separation_of_concerns": "UNKNOWN",
            "justified_abstraction": "UNKNOWN",
            "file_organization_quality": "UNKNOWN",
            "has_tests": "UNKNOWN",
            "readme_quality": "UNKNOWN",
        }

    top_dirs = _get_top_level_dirs(tree)
    all_dirs = _get_dir_structure(tree)
    top_dirs_lower = {d.lower() for d in top_dirs}

    mvc_score = len(top_dirs_lower & MVC_DIRS)
    layered_score = len(top_dirs_lower & LAYERED_DIRS)

    if layered_score >= 3:
        architecture_pattern = "layered"
    elif mvc_score >= 2:
        architecture_pattern = "MVC"
    elif len(tree) <= 5 and all(not "/" in f or f.count("/") <= 1 for f in tree):
        architecture_pattern = "script"
    else:
        architecture_pattern = "unknown"

    layer_counts = {}
    for layer_name, pattern in LAYER_PATTERNS.items():
        regex = re.compile(pattern, re.IGNORECASE)
        count = sum(1 for d in all_dirs if regex.search(d.split("/")[-1]))
        if count > 0:
            layer_counts[layer_name] = count

    distinct_layers = len(layer_counts)
    if distinct_layers >= 3:
        separation_of_concerns = "clear"
    elif distinct_layers >= 2:
        separation_of_concerns = "partial"
    elif distinct_layers >= 1:
        separation_of_concerns = "poor"
    else:
        separation_of_concerns = "UNKNOWN"

    code_files = _get_code_files(files)
    total_files = len(code_files)

    if total_files == 0:
        justified_abstraction = "UNKNOWN"
    else:
        abstraction_indicators = 0

        interface_count = sum(1 for p in tree if re.search(r"(interface|abstract|base|contract)", p, re.I))
        if interface_count > 0 and interface_count <= total_files * 0.3:
            abstraction_indicators += 1

        if distinct_layers >= 2:
            abstraction_indicators += 1

        util_files = sum(1 for p in tree if re.search(r"(util|helper|common)", p, re.I))
        if 0 < util_files <= total_files * 0.2:
            abstraction_indicators += 1

        if abstraction_indicators >= 2:
            justified_abstraction = True
        elif abstraction_indicators == 1:
            justified_abstraction = "UNKNOWN"
        else:
            justified_abstraction = False

    if len(top_dirs) == 0:
        file_organization_quality = "poor"
    elif len(top_dirs) >= 2 and any(d.lower() in {"src", "lib", "app", "pkg"} for d in top_dirs):
        file_organization_quality = "good"
    elif len(top_dirs) >= 1:
        file_organization_quality = "moderate"
    else:
        file_organization_quality = "UNKNOWN"

    test_patterns = [r"test[s]?/", r"spec[s]?/", r"__tests__/", r"_test\.", r"\.test\.", r"\.spec\."]
    test_files = [f for f in tree if any(re.search(p, f, re.I) for p in test_patterns)]

    if len(test_files) >= 3:
        has_tests = True
    elif len(test_files) >= 1:
        has_tests = True
    else:
        has_tests = False

    readme_files = [f for f in tree if f.lower() in {"readme.md", "readme.rst", "readme.txt", "readme"}]

    if not readme_files:
        readme_quality = "missing"
    else:
        readme_content = ""
        for rf in readme_files:
            if rf in files:
                readme_content = files[rf]
                break

        if not readme_content:
            readme_quality = "UNKNOWN"
        else:
            readme_lines = len(readme_content.splitlines())
            has_headers = bool(re.search(r"^#{1,3}\s+\w+", readme_content, re.MULTILINE))
            has_code_blocks = "```" in readme_content
            has_links = bool(re.search(r"\[.+\]\(.+\)", readme_content))

            quality_score = 0
            if readme_lines >= 50:
                quality_score += 2
            elif readme_lines >= 20:
                quality_score += 1

            if has_headers:
                quality_score += 1
            if has_code_blocks:
                quality_score += 1
            if has_links:
                quality_score += 1

            if quality_score >= 4:
                readme_quality = "good"
            elif quality_score >= 2:
                readme_quality = "moderate"
            else:
                readme_quality = "poor"

    return {
        "architecture_pattern": architecture_pattern,
        "separation_of_concerns": separation_of_concerns,
        "justified_abstraction": justified_abstraction,
        "file_organization_quality": file_organization_quality,
        "has_tests": has_tests,
        "readme_quality": readme_quality,
    }


async def analyze_security(repo: dict[str, Any]) -> dict[str, Any]:
    files = repo.get("files", {})

    if not files:
        return {
            "hardcoded_secrets": "UNKNOWN",
            "secrets_found": [],
            "uses_env_variables": "UNKNOWN",
            "unsafe_patterns_detected": "UNKNOWN",
        }

    code_files = _get_code_files(files)

    secrets_found = []
    for path, content in code_files.items():
        for pattern, secret_type in SECRET_PATTERNS:
            matches = re.findall(pattern, content)
            if matches:
                secrets_found.append({
                    "file": path,
                    "type": secret_type,
                    "count": len(matches) if isinstance(matches[0], str) else len(matches),
                })

    hardcoded_secrets = len(secrets_found) > 0

    env_usage_count = 0
    for pattern in ENV_VAR_PATTERNS:
        env_usage_count += _count_pattern_matches(files, pattern)

    uses_env_variables = env_usage_count >= 1

    unsafe_patterns = []

    plaintext_cred_pattern = r"(?i)(password|secret|credential)\s*=\s*['\"][^'\"]+['\"]"
    for path, content in code_files.items():
        if re.search(plaintext_cred_pattern, content):
            if not re.search(r"(?i)(test|spec|mock|fake|dummy|example)", path):
                unsafe_patterns.append({"file": path, "pattern": "plaintext_credentials"})

    unsafe_patterns_detected = len(unsafe_patterns) > 0

    return {
        "hardcoded_secrets": hardcoded_secrets,
        "secrets_found": secrets_found[:10],
        "uses_env_variables": uses_env_variables,
        "unsafe_patterns_detected": unsafe_patterns_detected,
        "unsafe_patterns": unsafe_patterns[:10],
    }


async def analyze_error_handling(repo: dict[str, Any]) -> dict[str, Any]:
    files = repo.get("files", {})

    if not files:
        return {
            "has_error_handling": "UNKNOWN",
            "try_except_usage": "UNKNOWN",
            "has_retries_or_fallbacks": "UNKNOWN",
            "logging_vs_print": "UNKNOWN",
        }

    code_files = _get_code_files(files)

    if not code_files:
        return {
            "has_error_handling": "UNKNOWN",
            "try_except_usage": "UNKNOWN",
            "has_retries_or_fallbacks": "UNKNOWN",
            "logging_vs_print": "UNKNOWN",
        }

    try_patterns = [
        r"\btry\s*:",
        r"\btry\s*\{",
        r"\bcatch\s*\(",
        r"\bexcept\s+",
        r"\bexcept\s*:",
        r"\.catch\s*\(",
        r"\brescue\b",
    ]

    try_count = 0
    for pattern in try_patterns:
        try_count += _count_pattern_matches(code_files, pattern)

    has_error_handling = try_count >= 1

    if try_count >= 10:
        try_except_usage = "extensive"
    elif try_count >= 3:
        try_except_usage = "moderate"
    elif try_count >= 1:
        try_except_usage = "minimal"
    else:
        try_except_usage = "none"

    retry_patterns = [
        r"\bretry\b",
        r"\bbackoff\b",
        r"\bfallback\b",
        r"\bCircuitBreaker\b",
        r"\btenacity\b",
        r"\bretrying\b",
        r"max_retries",
        r"retry_count",
    ]

    retry_count = 0
    for pattern in retry_patterns:
        retry_count += _count_pattern_matches(code_files, pattern)

    has_retries_or_fallbacks = retry_count >= 1

    print_count = _count_pattern_matches(code_files, r"\bprint\s*\(")
    logging_patterns = [
        r"\blogging\.",
        r"\blogger\.",
        r"\.log\s*\(",
        r"\.info\s*\(",
        r"\.warn\s*\(",
        r"\.error\s*\(",
        r"\.debug\s*\(",
        r"console\.log",
        r"console\.error",
    ]

    logging_count = 0
    for pattern in logging_patterns:
        logging_count += _count_pattern_matches(code_files, pattern)

    if logging_count == 0 and print_count == 0:
        logging_vs_print = "UNKNOWN"
    elif logging_count > print_count:
        logging_vs_print = "logging_preferred"
    elif print_count > logging_count:
        logging_vs_print = "print_preferred"
    else:
        logging_vs_print = "mixed"

    return {
        "has_error_handling": has_error_handling,
        "try_except_usage": try_except_usage,
        "has_retries_or_fallbacks": has_retries_or_fallbacks,
        "logging_vs_print": logging_vs_print,
        "print_count": print_count,
        "logging_count": logging_count,
    }


async def analyze_vibe_coding(repo: dict[str, Any]) -> dict[str, Any]:
    files = repo.get("files", {})

    if not files:
        return {
            "emoji_in_code": "UNKNOWN",
            "ai_generated_patterns": "UNKNOWN",
            "print_in_production": "UNKNOWN",
        }

    code_files = _get_code_files(files)

    if not code_files:
        return {
            "emoji_in_code": "UNKNOWN",
            "ai_generated_patterns": "UNKNOWN",
            "print_in_production": "UNKNOWN",
        }

    emoji_pattern = r"[\U0001F300-\U0001F9FF\U00002600-\U000026FF\U00002700-\U000027BF]"
    emoji_count = _count_pattern_matches(code_files, emoji_pattern)
    emoji_in_code = emoji_count >= 1

    ai_pattern_count = 0
    ai_evidence = []
    for pattern in AI_COMMENT_PATTERNS:
        for path, content in code_files.items():
            matches = re.findall(pattern, content)
            if matches:
                ai_pattern_count += len(matches)
                ai_evidence.append(path)

    ai_generated_patterns = ai_pattern_count >= 1

    non_test_files = {k: v for k, v in code_files.items()
                      if not re.search(r"(test|spec|__tests__|_test\.|\.test\.)", k, re.I)}

    print_in_prod_count = _count_pattern_matches(non_test_files, r"\bprint\s*\(")

    loc = _total_loc(non_test_files)
    if loc == 0:
        print_in_production = "UNKNOWN"
    elif print_in_prod_count == 0:
        print_in_production = False
    elif print_in_prod_count / max(loc, 1) > 0.01:
        print_in_production = True
    else:
        print_in_production = "minimal"

    return {
        "emoji_in_code": emoji_in_code,
        "emoji_count": emoji_count,
        "ai_generated_patterns": ai_generated_patterns,
        "ai_evidence_files": list(set(ai_evidence))[:5],
        "print_in_production": print_in_production,
        "print_count_in_production": print_in_prod_count,
    }


async def analyze_dependencies(repo: dict[str, Any]) -> dict[str, Any]:
    dependencies = repo.get("dependencies", [])
    files = repo.get("files", {})

    dep_count = len(dependencies)

    if dep_count == 0:
        return {
            "dependency_count": 0,
            "dependency_density": "UNKNOWN",
            "potential_over_dependence": "UNKNOWN",
        }

    loc = _total_loc(files)

    if loc == 0:
        return {
            "dependency_count": dep_count,
            "dependency_density": "UNKNOWN",
            "potential_over_dependence": "UNKNOWN",
        }

    density = dep_count / (loc / 1000)

    if density > 5:
        potential_over_dependence = True
    elif density > 2:
        potential_over_dependence = "possible"
    else:
        potential_over_dependence = False

    return {
        "dependency_count": dep_count,
        "dependency_density": round(density, 3),
        "potential_over_dependence": potential_over_dependence,
        "loc": loc,
    }


async def analyze_git_history(repo: dict[str, Any]) -> dict[str, Any]:
    commits = repo.get("commits", [])

    if not commits:
        return {
            "commit_count": 0,
            "commit_density": "UNKNOWN",
            "has_large_commits": "UNKNOWN",
            "low_signal_commit_ratio": "UNKNOWN",
        }

    commit_count = len(commits)

    files = repo.get("files", {})
    loc = _total_loc(files)

    if loc > 0:
        commit_density = commit_count / (loc / 1000)
    else:
        commit_density = "UNKNOWN"

    large_commit_threshold = 50
    large_commits = [c for c in commits if c.get("files_changed", 0) > large_commit_threshold]
    has_large_commits = len(large_commits) >= 1
    large_commit_ratio = len(large_commits) / commit_count if commit_count > 0 else 0

    low_signal_count = 0
    for commit in commits:
        msg = commit.get("message", "").strip().lower()
        if len(msg) < 3:
            low_signal_count += 1
            continue
        for pattern in LOW_SIGNAL_COMMITS:
            if re.match(pattern, msg, re.I):
                low_signal_count += 1
                break

    low_signal_ratio = low_signal_count / commit_count if commit_count > 0 else 0

    if low_signal_ratio > 0.3:
        low_signal_assessment = "high"
    elif low_signal_ratio > 0.1:
        low_signal_assessment = "moderate"
    else:
        low_signal_assessment = "low"

    return {
        "commit_count": commit_count,
        "commit_density": round(commit_density, 3) if isinstance(commit_density, float) else commit_density,
        "has_large_commits": has_large_commits,
        "large_commit_ratio": round(large_commit_ratio, 3),
        "low_signal_commit_ratio": round(low_signal_ratio, 3),
        "low_signal_assessment": low_signal_assessment,
    }


async def analyze_comments(repo: dict[str, Any]) -> dict[str, Any]:
    files = repo.get("files", {})

    python_files = {k: v for k, v in files.items() if k.endswith(".py")}

    if not python_files:
        return {
            "functions_analyzed": 0,
            "comment_quality": "UNKNOWN",
            "explains_intent_ratio": "UNKNOWN",
        }

    functions_with_comments = []

    for path, content in python_files.items():
        try:
            tree = ast.parse(content)
        except SyntaxError:
            continue

        lines = content.splitlines()

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if len(node.body) < 3:
                    continue

                func_start = node.lineno - 1
                func_end = node.end_lineno if hasattr(node, 'end_lineno') else func_start + 10

                func_lines = lines[func_start:func_end]

                comments = []
                for line in func_lines:
                    stripped = line.strip()
                    if stripped.startswith("#"):
                        comments.append(stripped[1:].strip())

                docstring = ast.get_docstring(node)

                if comments or docstring:
                    functions_with_comments.append({
                        "name": node.name,
                        "file": path,
                        "comments": comments,
                        "docstring": docstring,
                        "body_size": len(node.body),
                    })

    if not functions_with_comments:
        return {
            "functions_analyzed": 0,
            "comment_quality": "UNKNOWN",
            "explains_intent_ratio": "UNKNOWN",
        }

    sorted_funcs = sorted(functions_with_comments, key=lambda x: x["body_size"], reverse=True)
    sample = sorted_funcs[:3]

    intent_keywords = ["why", "because", "reason", "purpose", "note:", "important:",
                       "todo:", "fixme:", "hack:", "workaround", "ensure", "prevent"]
    behavior_keywords = ["return", "set", "get", "increment", "loop", "iterate",
                         "call", "initialize", "assign"]

    intent_count = 0
    behavior_count = 0

    for func in sample:
        all_comments = " ".join(func["comments"]).lower()
        if func["docstring"]:
            all_comments += " " + func["docstring"].lower()

        has_intent = any(kw in all_comments for kw in intent_keywords)
        has_behavior = any(kw in all_comments for kw in behavior_keywords)

        if has_intent:
            intent_count += 1
        if has_behavior and not has_intent:
            behavior_count += 1

    analyzed_count = len(sample)

    if intent_count >= analyzed_count * 0.5:
        comment_quality = "good"
    elif intent_count >= 1:
        comment_quality = "moderate"
    else:
        comment_quality = "poor"

    explains_intent_ratio = intent_count / analyzed_count if analyzed_count > 0 else 0

    return {
        "functions_analyzed": analyzed_count,
        "comment_quality": comment_quality,
        "explains_intent_ratio": round(explains_intent_ratio, 2),
        "sample_functions": [f["name"] for f in sample],
    }


async def analyze_project_substance(repo: dict[str, Any]) -> dict[str, Any]:
    tree = repo.get("tree", [])
    files = repo.get("files", {})
    commits = repo.get("commits", [])

    if not tree:
        return {
            "is_non_trivial": "UNKNOWN",
            "resembles_tutorial": "UNKNOWN",
            "real_world_evidence": "UNKNOWN",
        }

    code_files = _get_code_files(files)
    loc = _total_loc(files)

    non_trivial_indicators = 0

    if loc >= 500:
        non_trivial_indicators += 1
    if loc >= 2000:
        non_trivial_indicators += 1

    if len(code_files) >= 10:
        non_trivial_indicators += 1

    if len(commits) >= 20:
        non_trivial_indicators += 1

    top_dirs = _get_top_level_dirs(tree)
    if len(top_dirs) >= 3:
        non_trivial_indicators += 1

    if non_trivial_indicators >= 3:
        is_non_trivial = True
    elif non_trivial_indicators >= 1:
        is_non_trivial = "possibly"
    else:
        is_non_trivial = False

    tree_str = " ".join(tree).lower()
    files_str = " ".join(files.keys()).lower()
    combined = tree_str + " " + files_str

    tutorial_matches = sum(1 for indicator in TUTORIAL_INDICATORS if indicator in combined)

    boilerplate_count = 0
    for path, content in files.items():
        content_lower = content.lower()
        for bp in BOILERPLATE_FILES:
            if bp in content_lower:
                boilerplate_count += 1
                break

    if tutorial_matches >= 2 or boilerplate_count >= 2:
        resembles_tutorial = True
    elif tutorial_matches >= 1 or boilerplate_count >= 1:
        resembles_tutorial = "possibly"
    else:
        resembles_tutorial = False

    real_world_indicators = 0

    ci_files = [".github/workflows", ".gitlab-ci", "Jenkinsfile", ".circleci", ".travis.yml"]
    has_ci = any(any(ci in f for ci in ci_files) for f in tree)
    if has_ci:
        real_world_indicators += 1

    docker_files = ["Dockerfile", "docker-compose", ".dockerignore"]
    has_docker = any(any(d.lower() in f.lower() for d in docker_files) for f in tree)
    if has_docker:
        real_world_indicators += 1

    config_patterns = [".env.example", "config/", "settings/"]
    has_config = any(any(c in f for c in config_patterns) for f in tree)
    if has_config:
        real_world_indicators += 1

    api_patterns = ["api/", "routes/", "endpoints/", "swagger", "openapi"]
    has_api = any(any(p in f.lower() for p in api_patterns) for f in tree)
    if has_api:
        real_world_indicators += 1

    db_patterns = ["migrations/", "schema", "models/", "database/"]
    has_db = any(any(p in f.lower() for p in db_patterns) for f in tree)
    if has_db:
        real_world_indicators += 1

    if real_world_indicators >= 3:
        real_world_evidence = "strong"
    elif real_world_indicators >= 2:
        real_world_evidence = "moderate"
    elif real_world_indicators >= 1:
        real_world_evidence = "weak"
    else:
        real_world_evidence = "none"

    return {
        "is_non_trivial": is_non_trivial,
        "loc": loc,
        "file_count": len(code_files),
        "resembles_tutorial": resembles_tutorial,
        "real_world_evidence": real_world_evidence,
        "real_world_indicators": real_world_indicators,
    }


async def analyze_open_source(repo: dict[str, Any]) -> dict[str, Any]:
    prs = repo.get("prs", [])
    stars = repo.get("stars", 0)

    if not prs:
        pr_merge_rate = "UNKNOWN"
        oss_participation = "UNKNOWN"
    else:
        merged_prs = sum(1 for pr in prs if pr.get("merged", False))
        total_prs = len(prs)

        if total_prs > 0:
            pr_merge_rate = round(merged_prs / total_prs, 2)
        else:
            pr_merge_rate = "UNKNOWN"

        if merged_prs >= 5:
            oss_participation = "active"
        elif merged_prs >= 1:
            oss_participation = "some"
        else:
            oss_participation = "none"

    if stars >= 100:
        community_interest = "high"
    elif stars >= 10:
        community_interest = "moderate"
    elif stars >= 1:
        community_interest = "low"
    else:
        community_interest = "none"

    return {
        "pr_count": len(prs),
        "pr_merge_rate": pr_merge_rate,
        "oss_participation": oss_participation,
        "stars": stars,
        "community_interest": community_interest,
    }


async def analyze_tech_agility(repo: dict[str, Any]) -> dict[str, Any]:
    languages = repo.get("languages", {})
    dependencies = repo.get("dependencies", [])

    if not languages:
        return {
            "languages_over_500_loc": 0,
            "language_diversity": "UNKNOWN",
            "non_trivial_tech": "UNKNOWN",
        }

    langs_over_500 = [lang for lang, loc in languages.items() if loc >= 500]
    lang_count = len(langs_over_500)

    if lang_count >= 3:
        language_diversity = "high"
    elif lang_count >= 2:
        language_diversity = "moderate"
    elif lang_count >= 1:
        language_diversity = "low"
    else:
        language_diversity = "minimal"

    non_trivial_langs = {"rust", "go", "scala", "kotlin", "haskell", "elixir",
                         "clojure", "ocaml", "f#", "swift", "c++", "c"}

    non_trivial_frameworks = {"tensorflow", "pytorch", "kubernetes", "kafka",
                              "elasticsearch", "graphql", "grpc", "redis",
                              "celery", "airflow", "spark", "flink"}

    has_non_trivial_lang = any(lang.lower() in non_trivial_langs for lang in langs_over_500)

    deps_lower = [d.lower() for d in dependencies]
    has_non_trivial_framework = any(fw in " ".join(deps_lower) for fw in non_trivial_frameworks)

    if has_non_trivial_lang and has_non_trivial_framework:
        non_trivial_tech = "strong"
    elif has_non_trivial_lang or has_non_trivial_framework:
        non_trivial_tech = "some"
    else:
        non_trivial_tech = "none"

    return {
        "languages_over_500_loc": lang_count,
        "languages": langs_over_500,
        "language_diversity": language_diversity,
        "non_trivial_tech": non_trivial_tech,
        "has_non_trivial_language": has_non_trivial_lang,
        "has_non_trivial_framework": has_non_trivial_framework,
    }


async def analyze_repository(repo: dict[str, Any]) -> dict[str, Any]:
    results = await asyncio.gather(
        analyze_architecture(repo),
        analyze_security(repo),
        analyze_error_handling(repo),
        analyze_vibe_coding(repo),
        analyze_dependencies(repo),
        analyze_git_history(repo),
        analyze_comments(repo),
        analyze_project_substance(repo),
        analyze_open_source(repo),
        analyze_tech_agility(repo),
    )

    return {
        "architecture": results[0],
        "security": results[1],
        "error_handling": results[2],
        "vibe_coding": results[3],
        "dependencies": results[4],
        "git_history": results[5],
        "comments": results[6],
        "project_substance": results[7],
        "open_source": results[8],
        "tech_agility": results[9],
    }
