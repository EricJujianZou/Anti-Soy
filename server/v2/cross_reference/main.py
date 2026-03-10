"""
cross_reference — entry point.

Given a CandidateInput (name, github URL, full resume text, confidence level),
returns a PersonObject identifying which repos correspond to the candidate's resume
projects so downstream analysis only clones repos that matter.

Pipeline:
  Step 0  — Confidence gate: only "high" confidence candidates are processed.
             Others are flagged for manual review.
  Step 1  — Parse GitHub URL → extract and validate username.
  Step 2  — Fetch all public repos + pinned repos concurrently.
  Step 2b — Fork validation: skip forks with ≤ 1 commit on the parent repo.
  Step 3  — LLM call: extract resume projects + description-based repo matches.
  Step 4  — Algorithmic scoring: name similarity + tech overlap + LLM desc confidence.
  Step 5  — Assemble PersonObject. Pad repos_to_clone to a minimum of 3 using
             pinned repos first, then most recently updated repos as fallback.
"""
import asyncio
import logging

import httpx

from .models import CandidateInput, PersonObject, ResumeProject
from .config import MATCH_CONFIDENCE_THRESHOLD, MAX_CONCURRENT_WORKERS
from .utils import parse_github_url
from .github_client import (
    fetch_user_repos,
    fetch_repo_details,
    fetch_pinned_repos,
    check_fork_contributions,
)
from .resume_parser import extract_and_match_projects
from .matcher import resolve_matches

logger = logging.getLogger(__name__)

# Module-level semaphore — created lazily to avoid issues at import time.
# Caps concurrent GitHub API + LLM calls at MAX_CONCURRENT_WORKERS.
_semaphore: asyncio.Semaphore | None = None


def _get_semaphore() -> asyncio.Semaphore:
    global _semaphore
    if _semaphore is None:
        _semaphore = asyncio.Semaphore(MAX_CONCURRENT_WORKERS)
    return _semaphore


def _err(github_url: str, error: str) -> PersonObject:
    return PersonObject(github_username="", github_url=github_url, error=error)


async def cross_reference(candidate: CandidateInput) -> PersonObject:
    """
    Main entry point. Concurrency is capped by the module-level semaphore so that
    batch processing stays within GitHub API rate limits.
    """
    async with _get_semaphore():
        return await _run(candidate)


async def _run(candidate: CandidateInput) -> PersonObject:
    # Step 0: Confidence gate.
    # Only "high" confidence candidates are processed. Anything else is flagged
    # so a human can review whether the GitHub URL actually belongs to this person.
    if candidate.confidence != "high":
        return PersonObject(
            github_username="",
            github_url=candidate.github,
            flags=[
                f"manual_review_required: candidate confidence is '{candidate.confidence}', "
                "expected 'high'"
            ],
        )

    # Step 1: Parse GitHub URL → extract username.
    try:
        username = parse_github_url(candidate.github)
    except ValueError as exc:
        return _err(candidate.github, f"invalid_github_url: {exc}")

    github_url = f"https://github.com/{username}"

    async with httpx.AsyncClient(timeout=30.0) as http:
        # Step 2: Fetch all public repos and pinned repos concurrently.
        try:
            repos, pinned = await asyncio.gather(
                fetch_user_repos(http, username),
                fetch_pinned_repos(http, username),
            )
        except ValueError as exc:
            return _err(github_url, f"github_user_not_found: {exc}")
        except RuntimeError as exc:
            return _err(github_url, f"github_rate_limit: {exc}")
        except Exception as exc:
            return _err(github_url, f"github_api_error: {exc}")

        if not repos:
            return PersonObject(
                github_username=username,
                github_url=github_url,
                flags=["no_public_repos"],
            )

        # Step 2b: Fork validation — skip forks with ≤ 1 commit on parent.
        valid_repos, flags = await _validate_repos(http, repos, username)

        if not valid_repos:
            return PersonObject(
                github_username=username,
                github_url=github_url,
                flags=flags + ["no_valid_repos_after_fork_filter"],
            )

        # Step 3: LLM — extract resume projects and get description-based match scores.
        try:
            llm_projects = await extract_and_match_projects(
                candidate.resume_text, valid_repos
            )
        except Exception as exc:
            logger.error(f"LLM extraction failed for {username}: {exc}")
            flags.append("resume_parse_failed")
            llm_projects = []

        if not llm_projects:
            # No projects extracted — fall back entirely to pinned/recent repos.
            repos_to_clone = _pad_repos(username, valid_repos, pinned, set(), target=3)
            if len(repos_to_clone) < 3:
                flags.append(
                    f"fewer_than_3_repos_available:{len(repos_to_clone)}_found"
                )
            return PersonObject(
                github_username=username,
                github_url=github_url,
                match_summary="0/0 verified",
                repos_to_clone=repos_to_clone,
                flags=flags + ["no_resume_projects_extracted"],
            )

        # Step 4: Algorithmic scoring and greedy matching.
        matched, unmatched = resolve_matches(
            llm_projects, valid_repos, username, MATCH_CONFIDENCE_THRESHOLD
        )

        # Step 5: Assemble output.
        matched_names = {m.repo_name for m in matched}
        repos_to_clone = [m.repo_url for m in matched]

        # Pad up to minimum 3 repos via pinned/recent fallback.
        needed = max(0, 3 - len(repos_to_clone))
        if needed > 0:
            repos_to_clone.extend(
                _pad_repos(username, valid_repos, pinned, matched_names, target=needed)
            )

        if len(repos_to_clone) < 3:
            flags.append(
                f"fewer_than_3_repos_available:{len(repos_to_clone)}_found"
            )

        resume_projects = [
            ResumeProject(
                name=p.get("name", ""),
                description=p.get("description", ""),
                tech_stack=p.get("tech_stack", []),
            )
            for p in llm_projects
        ]

        total = len(llm_projects)
        verified = len(matched)

        return PersonObject(
            github_username=username,
            github_url=github_url,
            resume_projects=resume_projects,
            matched_projects=matched,
            unmatched_projects=unmatched,
            match_summary=f"{verified}/{total} verified",
            repos_to_clone=repos_to_clone,
            flags=flags,
        )


async def _validate_repos(
    http: httpx.AsyncClient,
    repos: list[dict],
    username: str,
) -> tuple[list[dict], list[str]]:
    """
    Validate each repo. Non-forks pass through unconditionally.
    Forks are checked for user contributions on the parent:
      - > 1 commits on parent → treat as owned (legit contributor)
      - ≤ 1 commits → skip and flag (profile padding)

    The /users/{username}/repos endpoint does NOT include parent info, so we
    fetch full repo details for each fork individually (done concurrently).
    """
    flags: list[str] = []
    non_forks = [r for r in repos if not r.get("fork")]
    forks = [r for r in repos if r.get("fork")]

    if not forks:
        return non_forks, flags

    # Fetch full details for each fork concurrently to get parent info.
    fork_details = await asyncio.gather(
        *[fetch_repo_details(http, username, r["name"]) for r in forks],
        return_exceptions=True,
    )

    # Split into forks with resolvable parent info and those without.
    check_list: list[tuple[dict, str, str]] = []  # (fork_dict, parent_owner, parent_repo)
    no_parent: list[dict] = []

    for fork, detail in zip(forks, fork_details):
        if isinstance(detail, Exception) or not isinstance(detail, dict):
            no_parent.append(fork)
            continue
        parent = detail.get("parent") or {}
        full_name = parent.get("full_name", "")
        if "/" not in full_name:
            no_parent.append(fork)
            continue
        p_owner, p_repo = full_name.split("/", 1)
        check_list.append((fork, p_owner, p_repo))

    for fork in no_parent:
        flags.append(f"forked_repo_skipped:{fork['name']} (parent info unavailable)")

    if not check_list:
        return non_forks, flags

    # Check contributions for all qualifying forks concurrently.
    counts = await asyncio.gather(
        *[
            check_fork_contributions(http, username, p_owner, p_repo)
            for _, p_owner, p_repo in check_list
        ],
        return_exceptions=True,
    )

    valid_forks: list[dict] = []
    for (fork, _, _), count in zip(check_list, counts):
        n = int(count) if isinstance(count, int) else 0
        if n > 1:
            valid_forks.append(fork)
        else:
            flags.append(
                f"forked_repo_skipped:{fork['name']} ({n} commit(s) on parent)"
            )

    return non_forks + valid_forks, flags


def _pad_repos(
    username: str,
    valid_repos: list[dict],
    pinned_repos: list[dict],
    exclude_names: set[str],
    target: int,
) -> list[str]:
    """
    Build a list of fallback repo URLs up to `target` length.
    Tries pinned repos first, then most recently updated repos.
    Skips repos whose names are in exclude_names.
    """
    result: list[str] = []
    seen = set(exclude_names)

    # 1. Pinned repos first (already surfaced by the candidate as notable work).
    for repo in pinned_repos:
        if len(result) >= target:
            break
        name = repo.get("name")
        if name and name not in seen:
            seen.add(name)
            result.append(f"https://github.com/{username}/{name}")

    # 2. Most recently updated repos from valid_repos.
    if len(result) < target:
        sorted_repos = sorted(
            valid_repos,
            key=lambda r: r.get("updated_at", ""),
            reverse=True,
        )
        for repo in sorted_repos:
            if len(result) >= target:
                break
            name = repo.get("name")
            if name and name not in seen:
                seen.add(name)
                result.append(f"https://github.com/{username}/{name}")

    return result
