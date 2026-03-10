import os
import requests
from .resume_parser import ResumeParseException

def _fetch_pinned_repos(username: str, headers: dict) -> list[dict]:
    """Fetches pinned repos via GitHub GraphQL API. Returns list of {name, url} or empty list on any failure."""
    token = headers.get("Authorization")
    if not token:
        return []

    query = """
    query($username: String!) {
      user(login: $username) {
        pinnedItems(first: 6, types: REPOSITORY) {
          nodes { ... on Repository { name url } }
        }
      }
    }
    """
    try:
        response = requests.post(
            "https://api.github.com/graphql",
            json={"query": query, "variables": {"username": username}},
            headers=headers,
        )
        if response.status_code != 200:
            return []
        data = response.json()
        nodes = data.get("data", {}).get("user", {}).get("pinnedItems", {}).get("nodes", [])
        return [{"name": n["name"], "url": n["url"]} for n in nodes if n]
    except Exception:
        return []

def ResolveRepo(github_profile_url: str, project_names: list[str]) -> str:
    """
    DEPRECATED: Use v2.cross_reference.cross_reference() instead.

    This function resolved a GitHub profile URL to a single best-matching repo URL.
    It has been superseded by the cross_reference module which:
      - Matches all resume projects to repos (not just the first hit)
      - Returns multiple repos_to_clone per candidate
      - Uses LLM + algorithmic scoring for confident matching
      - Handles fork validation and fallback logic

    Kept here only for the /resolve-username endpoint in main.py which imports
    _fetch_pinned_repos directly from this module.
    """
    if not github_profile_url:
        raise ResumeParseException("GitHub profile URL is empty")

    # 1. Extract username from the profile URL
    # Expected format: https://github.com/username or github.com/username
    parts = [p for p in github_profile_url.split('/') if p]
    if not parts:
        raise ResumeParseException(f"Invalid GitHub profile URL: {github_profile_url}")
    
    username = parts[-1]
    
    # 2. Build headers and fetch pinned repos
    github_token = os.getenv("GITHUB_TOKEN")
    headers = {}
    if github_token:
        headers["Authorization"] = f"Bearer {github_token}"

    pinned_repos = _fetch_pinned_repos(username, headers)

    # 3. If pinned repos exist and project_names provided, try matching pinned repos first
    if pinned_repos and project_names:
        for repo in pinned_repos:
            repo_name = repo["name"]
            processed_repo_name = repo_name.replace('-', ' ').replace('_', ' ').lower()
            for proj in project_names:
                proj_lower = proj.lower()
                if processed_repo_name and proj_lower and (processed_repo_name in proj_lower or proj_lower in processed_repo_name):
                    return f"https://github.com/{username}/{repo_name}"

    # 4. If pinned repos exist and no project_names, return first pinned repo
    if pinned_repos and not project_names:
        return f"https://github.com/{username}/{pinned_repos[0]['name']}"

    # 5. Fall through to REST API logic (existing behavior)
    api_url = f"https://api.github.com/users/{username}/repos?sort=pushed&per_page=100"

    try:
        response = requests.get(api_url, headers=headers)
    except Exception as e:
        raise ResumeParseException(f"GitHub API request failed: {e}")

    if response.status_code != 200:
        raise ResumeParseException(f"GitHub API error: {response.status_code} - {response.text}")

    repos = response.json()

    if not repos:
        raise ResumeParseException("No public repositories found for this user.")

    best_repo = None
    if project_names:
        for repo in repos:
            repo_name = repo["name"]
            processed_repo_name = repo_name.replace('-', ' ').replace('_', ' ').lower()

            match_found = False
            for proj in project_names:
                proj_lower = proj.lower()
                if processed_repo_name and proj_lower and (processed_repo_name in proj_lower or proj_lower in processed_repo_name):
                    match_found = True
                    break

            if match_found:
                best_repo = repo
                break

    if not best_repo:
        best_repo = repos[0]  # most recently pushed

    return f"https://github.com/{username}/{best_repo['name']}"
