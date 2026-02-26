
import os
import requests
from v2.resume_parser import ResumeParseException

def ResolveRepo(github_profile_url: str, project_names: list[str]) -> str:
    """
    Resolves a GitHub profile + project name list → a single best-matching repo URL
    """
    # 1. Extract username from the profile URL
    # https://github.com/username
    username = github_profile_url.rstrip("/").split("/")[-1]
    
    # 2. Call GitHub API
    github_token = os.getenv("GITHUB_TOKEN")
    headers = {}
    if github_token:
        headers["Authorization"] = f"Bearer {github_token}"
    
    api_url = f"https://api.github.com/users/{username}/repos?sort=pushed&per_page=100"
    try:
        response = requests.get(api_url, headers=headers, timeout=10)
    except Exception as e:
        raise ResumeParseException(f"GitHub API error: {str(e)}")
        
    # 3. If API call fails or returns non-200
    if response.status_code != 200:
        raise ResumeParseException(f"GitHub API error: {response.status_code} {response.text}")
        
    # 4. If response returns 0 public repos
    repos = response.json()
    if not repos:
        raise ResumeParseException("No public repositories found for this user.")
        
    # 5. Matching logic
    best_repo = None
    if project_names:
        max_score = 0
        for repo in repos:
            repo_name = repo["name"].replace("-", " ").replace("_", " ").lower()
            score = 0
            for proj in project_names:
                proj_lower = proj.lower()
                if repo_name in proj_lower or proj_lower in repo_name:
                    score = 1
                    break
            
            if score > max_score:
                max_score = score
                best_repo = repo
                
    # 6. Fallback
    if best_repo is None:
        best_repo = repos[0] # most recently pushed
        
    # 7. Return URL
    return f"https://github.com/{username}/{best_repo['name']}"
