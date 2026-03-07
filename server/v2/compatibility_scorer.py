"""
Compatibility Scorer for Duo Scan

Rule-based scoring algorithm that evaluates how complementary two developers are
based on their analysis results. No LLM calls — purely deterministic.
"""

FRONTEND_LANGS = {"JavaScript", "TypeScript", "CSS", "HTML", "SCSS", "Sass", "Less", "Vue", "Svelte"}
BACKEND_LANGS = {"Python", "Go", "Rust", "Java", "C++", "C", "C#", "Ruby", "PHP", "Kotlin", "Scala", "Elixir", "Haskell"}

SCORE_LABELS = [
    (80, "Strong Pair"),
    (60, "Good Match"),
    (40, "Workable"),
    (20, "Risky Pair"),
    (0, "Avoid"),
]


def _top_languages(languages: dict[str, int], n: int = 3) -> list[str]:
    """Return top N languages by byte count."""
    return [lang for lang, _ in sorted(languages.items(), key=lambda x: x[1], reverse=True)[:n]]


def _language_category(languages: dict[str, int]) -> str:
    """Classify a language dict as 'frontend', 'backend', or 'mixed'."""
    total = sum(languages.values()) or 1
    frontend_bytes = sum(v for k, v in languages.items() if k in FRONTEND_LANGS)
    backend_bytes = sum(v for k, v in languages.items() if k in BACKEND_LANGS)

    frontend_ratio = frontend_bytes / total
    backend_ratio = backend_bytes / total

    if frontend_ratio > 0.6:
        return "frontend"
    elif backend_ratio > 0.6:
        return "backend"
    return "mixed"


def _score_role_coverage(langs_a: dict[str, int], langs_b: dict[str, int]) -> int:
    """0-40 points based on how complementary the language stacks are."""
    cat_a = _language_category(langs_a)
    cat_b = _language_category(langs_b)

    if {cat_a, cat_b} == {"frontend", "backend"}:
        return 40
    elif cat_a == "mixed" or cat_b == "mixed":
        if cat_a != cat_b:
            return 30
        return 20
    elif cat_a == cat_b:
        return 5
    return 15


def _score_skill_diversity(langs_a: dict[str, int], langs_b: dict[str, int]) -> int:
    """0-20 points based on unique language count across both."""
    top_a = set(_top_languages(langs_a))
    top_b = set(_top_languages(langs_b))
    unique = len(top_a | top_b)

    if unique >= 5:
        return 20
    elif unique == 4:
        return 15
    elif unique == 3:
        return 10
    elif unique == 2:
        return 5
    return 0


def _score_code_quality(quality_a: int, quality_b: int) -> int:
    """0-20 points based on average code quality."""
    avg = (quality_a + quality_b) / 2
    if avg >= 80:
        return 20
    elif avg >= 50:
        return 10
    return 0


def _score_completeness(eval_a: dict | None, eval_b: dict | None) -> int:
    """0-20 points. Each person with standout_features + solves_real_problem = 10pts."""
    score = 0
    for ev in [eval_a, eval_b]:
        if ev and ev.get("standout_features") and ev.get("business_value", {}).get("solves_real_problem"):
            score += 10
    return score


def _get_score_label(score: int) -> str:
    """Map score to label."""
    for threshold, label in SCORE_LABELS:
        if score >= threshold:
            return label
    return "Avoid"


def _generate_callouts(
    langs_a: dict[str, int],
    langs_b: dict[str, int],
    eval_a: dict | None,
    eval_b: dict | None,
) -> list[dict]:
    """Generate deterministic callouts (strengths and flags)."""
    callouts = []

    cat_a = _language_category(langs_a)
    cat_b = _language_category(langs_b)
    top_a = _top_languages(langs_a)
    top_b = _top_languages(langs_b)

    # Role split
    if {cat_a, cat_b} == {"frontend", "backend"}:
        fe_langs = top_a if cat_a == "frontend" else top_b
        be_langs = top_a if cat_a == "backend" else top_b
        callouts.append({
            "type": "strength",
            "message": f"Strong frontend/backend split — {', '.join(fe_langs)} meets {', '.join(be_langs)}",
        })
    elif cat_a == cat_b and cat_a != "mixed":
        callouts.append({
            "type": "flag",
            "message": f"Both lean {cat_a}-heavy ({', '.join(set(top_a) | set(top_b))}) — consider who covers the other side",
        })

    # Skill diversity
    unique_langs = set(top_a) | set(top_b)
    if len(unique_langs) >= 5:
        callouts.append({
            "type": "strength",
            "message": f"Wide tech coverage across {len(unique_langs)} languages",
        })

    # Completeness
    both_have_standout = (
        eval_a and eval_a.get("standout_features") and
        eval_b and eval_b.get("standout_features")
    )
    if both_have_standout:
        callouts.append({
            "type": "strength",
            "message": "Both projects show standout qualities",
        })

    neither_has_standout = (
        (not eval_a or not eval_a.get("standout_features")) and
        (not eval_b or not eval_b.get("standout_features"))
    )
    if neither_has_standout:
        callouts.append({
            "type": "flag",
            "message": "Neither project shows standout features — may need to dig deeper",
        })

    return callouts


def compute_compatibility(
    analysis_a: dict,
    eval_a: dict | None,
    analysis_b: dict,
    eval_b: dict | None,
) -> tuple[int, str, list[dict]]:
    """
    Compute compatibility score, label, and callouts.

    Args:
        analysis_a: AnalysisResponse dict for person A
        eval_a: {business_value, standout_features, is_rejected} or None
        analysis_b: AnalysisResponse dict for person B
        eval_b: same as eval_a for person B

    Returns:
        (score, score_label, callouts)
    """
    langs_a = analysis_a.get("repo", {}).get("languages", {})
    langs_b = analysis_b.get("repo", {}).get("languages", {})
    quality_a = analysis_a.get("code_quality", {}).get("score", 0)
    quality_b = analysis_b.get("code_quality", {}).get("score", 0)

    score = 0
    score += _score_role_coverage(langs_a, langs_b)
    score += _score_skill_diversity(langs_a, langs_b)
    score += _score_code_quality(quality_a, quality_b)
    score += _score_completeness(eval_a, eval_b)

    score = max(0, min(100, score))
    label = _get_score_label(score)
    callouts = _generate_callouts(langs_a, langs_b, eval_a, eval_b)

    return score, label, callouts
