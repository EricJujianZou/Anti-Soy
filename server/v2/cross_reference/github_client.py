"""Async GitHub API interactions for the cross_reference module."""
import logging
import re

import httpx

from .config import GITHUB_PAT

logger = logging.getLogger(__name__)

_BASE = "https://api.github.com"
_GRAPHQL_URL = "https://api.github.com/graphql"


def _headers() -> dict[str, str]:
    h = {"Accept": "application/vnd.github+json"}
    if GITHUB_PAT:
        h["Authorization"] = f"Bearer {GITHUB_PAT}"
    return h


async def fetch_user_repos(client: httpx.AsyncClient, username: str) -> list[dict]:
    """
    Fetch all public repos owned by the user using the REST API.
    Paginates via Link header (handles > 100 repos).

    Raises ValueError on 404 (user not found).
    Raises RuntimeError on 403/429 (rate limit).
    """
    repos: list[dict] = []
    url: str | None = f"{_BASE}/users/{username}/repos?per_page=100&type=owner"

    while url:
        resp = await client.get(url, headers=_headers())
        if resp.status_code == 404:
            raise ValueError(f"GitHub user not found: {username}")
        if resp.status_code in (403, 429):
            raise RuntimeError(f"GitHub API rate limit hit for user: {username}")
        resp.raise_for_status()
        repos.extend(resp.json())
        url = _parse_link(resp.headers.get("Link", ""), rel="next")

    return repos


async def fetch_repo_details(
    client: httpx.AsyncClient, owner: str, repo_name: str
) -> dict | None:
    """
    Fetch full details for a single repo (includes 'parent' field for forks).
    Returns None on any failure.
    """
    try:
        resp = await client.get(f"{_BASE}/repos/{owner}/{repo_name}", headers=_headers())
        if resp.status_code == 200:
            return resp.json()
    except Exception as exc:
        logger.warning(f"Failed to fetch repo details for {owner}/{repo_name}: {exc}")
    return None


async def fetch_pinned_repos(client: httpx.AsyncClient, username: str) -> list[dict]:
    """
    Fetch up to 6 pinned repos via GitHub GraphQL.
    Returns a list of simplified repo dicts, or [] if PAT is missing or request fails.
    """
    if not GITHUB_PAT:
        return []

    query = """
    query($username: String!) {
      user(login: $username) {
        pinnedItems(first: 6, types: REPOSITORY) {
          nodes {
            ... on Repository {
              name
              url
              description
              primaryLanguage { name }
              repositoryTopics(first: 10) { nodes { topic { name } } }
            }
          }
        }
      }
    }
    """
    try:
        resp = await client.post(
            _GRAPHQL_URL,
            json={"query": query, "variables": {"username": username}},
            headers=_headers(),
        )
        if resp.status_code != 200:
            return []
        nodes = (
            resp.json()
            .get("data", {})
            .get("user", {})
            .get("pinnedItems", {})
            .get("nodes", [])
        )
        return [n for n in nodes if n]
    except Exception as exc:
        logger.warning(f"Failed to fetch pinned repos for {username}: {exc}")
        return []


async def check_fork_contributions(
    client: httpx.AsyncClient,
    username: str,
    parent_owner: str,
    parent_repo: str,
) -> int:
    """
    Count contributions by `username` on the parent repo via the contributors endpoint.
    This correctly counts commits where the user is either author OR committer —
    the commits `?author=` filter only matches the git 'author' field and misses
    commits where the user is listed as 'committer' (e.g. merge commits, cherry-picks).
    Returns 0 on failure or if the user is not found in the contributors list.
    """
    try:
        # Contributors endpoint returns up to 100 contributors per page, sorted by
        # contribution count descending. For the fork-validation use case (small
        # university / personal projects), the user will almost always be in the
        # first page. Pagination is skipped intentionally to keep latency low.
        resp = await client.get(
            f"{_BASE}/repos/{parent_owner}/{parent_repo}/contributors?per_page=100",
            headers=_headers(),
        )
        if resp.status_code != 200:
            return 0
        for contributor in resp.json():
            if contributor.get("login", "").lower() == username.lower():
                return int(contributor.get("contributions", 0))
        return 0
    except Exception as exc:
        logger.warning(
            f"Could not check fork contributions for {username} "
            f"on {parent_owner}/{parent_repo}: {exc}"
        )
        return 0


def _parse_link(link_header: str, rel: str) -> str | None:
    """Parse a specific rel URL from a GitHub Link header."""
    if not link_header:
        return None
    for part in link_header.split(","):
        if f'rel="{rel}"' in part:
            url_part = part.strip().split(";")[0].strip()
            return url_part.lstrip("<").rstrip(">")
    return None
