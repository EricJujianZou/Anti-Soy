import os
import requests
from .resume_parser import ResumeParseException

def ResolveRepo(github_profile_url: str, project_names: list[str]) -> str:
    """
    Resolves a GitHub profile URL and a list of project names to the best-matching repository URL.
    """
    if not github_profile_url:
        raise ResumeParseException("GitHub profile URL is empty")

    # 1. Extract username from the profile URL
    # Expected format: https://github.com/username or github.com/username
    parts = [p for p in github_profile_url.split('/') if p]
    if not parts:
        raise ResumeParseException(f"Invalid GitHub profile URL: {github_profile_url}")
    
    username = parts[-1]
    
    # 2. Call GitHub API: GET https://api.github.com/users/{username}/repos?sort=pushed&per_page=100
    github_token = os.getenv("GITHUB_TOKEN")
    headers = {}
    if github_token:
        headers["Authorization"] = f"Bearer {github_token}"
    
    api_url = f"https://api.github.com/users/{username}/repos?sort=pushed&per_page=100"
    
    try:
        response = requests.get(api_url, headers=headers)
    except Exception as e:
        raise ResumeParseException(f"GitHub API request failed: {e}")
    
    # 3. If API call fails or returns non-200: raise ResumeParseException
    if response.status_code != 200:
        raise ResumeParseException(f"GitHub API error: {response.status_code} - {response.text}")
    
    repos = response.json()
    
    # 4. If response returns 0 public repos: raise ResumeParseException
    if not repos:
        raise ResumeParseException("No public repositories found for this user.")
    
    # 5. Matching logic (only if project_names is non-empty)
    best_repo = None
    if project_names:
        for repo in repos:
            repo_name = repo["name"]
            # repo name (hyphens/underscores → spaces, lowercased)
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

    # 6. Fallback (if project_names is empty or all scores = 0)
    if not best_repo:
        best_repo = repos[0] # most recently pushed
        
    # 7. Return "https://github.com/{username}/{repo_name}"
    return f"https://github.com/{username}/{best_repo['name']}"
