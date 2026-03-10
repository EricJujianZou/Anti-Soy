"""URL parsing, string normalization, and similarity utilities."""
import re

import Levenshtein

# Valid GitHub username pattern
_USERNAME_RE = re.compile(r"^[a-zA-Z0-9\-]+$")

# Canonical tech name aliases — maps various spellings to a single normalized form.
# Used so that "JavaScript" and "JS", "Node.js" and "node", etc. are treated as equal.
_TECH_ALIASES: dict[str, str] = {
    "javascript": "js",
    "typescript": "ts",
    "node": "node",
    "nodejs": "node",
    "node.js": "node",
    "node js": "node",
    "reactjs": "react",
    "react.js": "react",
    "vuejs": "vue",
    "vue.js": "vue",
    "angularjs": "angular",
    "postgresql": "postgres",
    "postgres": "postgres",
    "mongodb": "mongo",
    "mongo": "mongo",
    "c++": "cpp",
    "c#": "csharp",
    "golang": "go",
    "python3": "python",
    "scss": "css",
    "sass": "css",
    "html5": "html",
    "css3": "css",
    "expressjs": "express",
    "express.js": "express",
    "nextjs": "next",
    "next.js": "next",
    "nuxtjs": "nuxt",
    "nuxt.js": "nuxt",
    "sveltejs": "svelte",
    "svelte.js": "svelte",
    "shell": "bash",
    "sh": "bash",
}


def parse_github_url(url: str) -> str:
    """
    Extract and validate a GitHub username from any of these formats:
      https://github.com/username
      github.com/username
      https://github.com/username/  (trailing slash)

    Returns the username string.
    Raises ValueError on any invalid input.
    """
    if not url or not url.strip():
        raise ValueError("GitHub URL is empty")

    cleaned = url.strip().rstrip("/")
    cleaned = re.sub(r"^https?://", "", cleaned)
    parts = [p for p in cleaned.split("/") if p]

    try:
        gh_idx = next(i for i, p in enumerate(parts) if p.lower() == "github.com")
    except StopIteration:
        raise ValueError(f"Not a GitHub URL: {url!r}")

    if gh_idx + 1 >= len(parts):
        raise ValueError(f"No username found in GitHub URL: {url!r}")

    username = parts[gh_idx + 1]
    if not _USERNAME_RE.match(username):
        raise ValueError(f"Invalid GitHub username {username!r} in URL: {url!r}")

    return username


def normalize_tech(tech: str) -> str:
    """Normalize a technology name to its canonical form for comparison."""
    key = tech.lower().strip()
    return _TECH_ALIASES.get(key, key)


def tokenize(s: str) -> set[str]:
    """
    Split a string into lowercase tokens.
    Handles camelCase (ChatApp → chat, app), hyphens, underscores, and spaces.
    """
    # Insert a space before uppercase letters that follow a lowercase letter (camelCase)
    s = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", s)
    return {t.lower() for t in re.split(r"[^a-zA-Z0-9]", s) if t}


def name_similarity(resume_name: str, repo_name: str) -> float:
    """
    Compute similarity between a resume project name and a repo name.

    Strategy:
      - Tokenize both strings (splits on spaces, hyphens, underscores, etc.)
      - Jaccard similarity on token sets (primary signal, handles "ChatApp" vs "chat-app-v2")
      - Levenshtein ratio on concatenated sorted tokens (fallback signal)

    Returns a float in [0, 1].
    """
    tokens_a = tokenize(resume_name)
    tokens_b = tokenize(repo_name)

    if tokens_a and tokens_b:
        intersection = tokens_a & tokens_b
        union = tokens_a | tokens_b
        jaccard = len(intersection) / len(union) if union else 0.0
    else:
        jaccard = 0.0

    str_a = "".join(sorted(tokens_a))
    str_b = "".join(sorted(tokens_b))
    lev = Levenshtein.ratio(str_a, str_b) if str_a and str_b else 0.0

    # Jaccard weighted more heavily — it handles abbreviated/hyphenated names well
    return round(0.7 * jaccard + 0.3 * lev, 4)


def compute_tech_overlap(
    resume_stack: list[str],
    repo_primary_language: str | None,
    repo_topics: list[str],
) -> float:
    """
    Compute tech stack overlap: |intersection| / |resume_stack|.

    Uses the repo's primary language field and topic tags. Full language
    breakdown from languages_url is not fetched here to avoid excess API calls.

    Returns 0.0 if resume_stack is empty.
    """
    if not resume_stack:
        return 0.0

    normalized_resume = {normalize_tech(t) for t in resume_stack}
    normalized_repo: set[str] = set()

    if repo_primary_language:
        normalized_repo.add(normalize_tech(repo_primary_language))
    for topic in repo_topics:
        normalized_repo.add(normalize_tech(topic))

    intersection = normalized_resume & normalized_repo
    return round(len(intersection) / len(normalized_resume), 4)
