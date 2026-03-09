"""
Algorithmic scoring and greedy bipartite matching of resume projects to GitHub repos.

Adaptive scoring formula:

  Name match mode  (name_similarity >= NAME_MATCH_THRESHOLD = 0.5):
    confidence = 0.9 * name_score + 0.1 * desc_score
    Fallback (no description): confidence = name_score

  Description match mode  (name_similarity < NAME_MATCH_THRESHOLD):
    confidence = 0.2 * name_score + 0.8 * desc_score
    Fallback (no description): confidence = 0.2 * name_score  (penalised — no signal)

  Tech/language overlap: excluded (weight = 0). GitHub only exposes the primary
  language and candidates frequently omit languages, making this signal too noisy.

Greedy matching: sort all (project, repo) candidate pairs by descending confidence,
then assign greedily so each project and each repo is matched at most once.
"""
import logging

from .models import MatchedProject, UnmatchedProject, MatchSignals
from .utils import name_similarity
from .config import (
    NAME_MATCH_THRESHOLD,
    NAME_HIGH_NAME_W, NAME_HIGH_DESC_W,
    NAME_LOW_NAME_W, NAME_LOW_DESC_W,
    MATCH_CONFIDENCE_THRESHOLD,
)

logger = logging.getLogger(__name__)


def _score(
    project_name: str,
    repo: dict,
    desc_confidence: float | None,
) -> tuple[float, MatchSignals]:
    """
    Compute the combined confidence score for one (project, repo) pair.
    Uses adaptive weighting: name-dominant when names clearly match,
    description-dominant when they don't.
    Returns (confidence, MatchSignals).
    """
    n_score = name_similarity(project_name, repo.get("name", ""))
    name_match_mode = n_score >= NAME_MATCH_THRESHOLD

    if bool(repo.get("description")) and desc_confidence is not None:
        d_score: float = desc_confidence
        if name_match_mode:
            confidence = NAME_HIGH_NAME_W * n_score + NAME_HIGH_DESC_W * d_score
        else:
            confidence = NAME_LOW_NAME_W * n_score + NAME_LOW_DESC_W * d_score
    else:
        d_score = 0.0
        if name_match_mode:
            # Name clearly matches — description unavailable, trust the name
            confidence = n_score
        else:
            # No name match, no description — minimal signal
            confidence = NAME_LOW_NAME_W * n_score

    return round(confidence, 4), MatchSignals(
        name_similarity=round(n_score, 4),
        description_similarity=round(d_score, 4),
        tech_stack_overlap=0.0,
    )


def resolve_matches(
    llm_projects: list[dict],
    repos: list[dict],
    username: str,
    threshold: float = MATCH_CONFIDENCE_THRESHOLD,
) -> tuple[list[MatchedProject], list[UnmatchedProject]]:
    """
    Greedy bipartite matching: each project matches at most one repo, each repo
    matches at most one project.

    Algorithm:
      1. Build desc_confidence lookup from LLM output (project_idx, repo_name) -> float.
      2. Score every (project, repo) pair using algorithmic signals + LLM desc score.
      3. Sort all pairs descending by confidence.
      4. Greedily assign highest-confidence pairs, skipping already-used slots.
      5. Classify remaining projects as unmatched with a reason.

    Returns (matched_projects, unmatched_projects).
    """
    # Build LLM description confidence lookup keyed by (project_idx, repo_name)
    desc_conf_lookup: dict[tuple[int, str], float] = {}
    for proj_idx, proj in enumerate(llm_projects):
        llm_match = proj.get("matched_repo")
        if llm_match and llm_match.get("repo_name"):
            desc_conf_lookup[(proj_idx, llm_match["repo_name"])] = float(
                llm_match.get("description_confidence", 0.0)
            )

    # Score all (project, repo) pairs
    candidates: list[tuple[float, int, str, MatchSignals]] = []
    for proj_idx, proj in enumerate(llm_projects):
        for repo in repos:
            repo_name = repo.get("name", "")
            desc_conf = desc_conf_lookup.get((proj_idx, repo_name))
            confidence, signals = _score(
                proj.get("name", ""),
                repo,
                desc_conf,
            )
            candidates.append((confidence, proj_idx, repo_name, signals))

    # Sort descending by confidence
    candidates.sort(key=lambda x: x[0], reverse=True)

    matched: list[MatchedProject] = []
    used_repos: set[str] = set()
    used_projects: set[int] = set()

    for confidence, proj_idx, repo_name, signals in candidates:
        if confidence < threshold:
            break  # Early exit — list is sorted descending
        if proj_idx in used_projects or repo_name in used_repos:
            continue

        proj = llm_projects[proj_idx]
        matched.append(
            MatchedProject(
                resume_project_name=proj.get("name", ""),
                repo_name=repo_name,
                repo_url=f"https://github.com/{username}/{repo_name}",
                confidence=confidence,
                match_signals=signals,
            )
        )
        used_repos.add(repo_name)
        used_projects.add(proj_idx)

    # Classify unmatched projects
    # Pre-build a lookup: project_idx -> (best_confidence, best_repo_name)
    best_scores: dict[int, tuple[float, str]] = {}
    for confidence, proj_idx, repo_name, _ in candidates:
        if proj_idx not in best_scores or confidence > best_scores[proj_idx][0]:
            best_scores[proj_idx] = (confidence, repo_name)

    unmatched: list[UnmatchedProject] = []
    for proj_idx, proj in enumerate(llm_projects):
        if proj_idx in used_projects:
            continue

        # "Outbid" means: this project had a high-confidence pair, but that repo
        # was already claimed by a higher-confidence project.
        reason = "no_matching_repo_found"
        for _, pi, rn, _ in candidates:
            if pi == proj_idx and rn in used_repos:
                reason = "outbid_by_higher_confidence_match"
                break

        best_conf, best_repo = best_scores.get(proj_idx, (0.0, ""))
        unmatched.append(
            UnmatchedProject(
                name=proj.get("name", ""),
                description=proj.get("description", ""),
                reason=reason,
                best_confidence=round(best_conf, 4),
                best_repo_name=best_repo or None,
            )
        )

    return matched, unmatched
