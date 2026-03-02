"""
clone_script.py
Checkout script for git cloning that skips files that are above a certain size.

Uses GitHub API to pre-filter large files before cloning, avoiding unnecessary downloads.
"""

import subprocess
import os
import requests
import tempfile
import logging

from urllib.parse import urlparse

logger = logging.getLogger(__name__)

MAX_FILE_SIZE_BYTES = 3 * 1024 * 1024  # 3MiB
GITHUB_API_URL = "https://api.github.com"

class GitCloneException(Exception):
    pass

def parse_github_url(repo_url: str) -> tuple[str, str]:
    """Extract owner and repo name from GitHub URL."""
    # Handle both https://github.com/owner/repo.git and https://github.com/owner/repo
    parsed = urlparse(repo_url)
    path_parts = parsed.path.strip('/').split('/')
    
    if len(path_parts) < 2:
        raise GitCloneException(f"Invalid GitHub URL: {repo_url}")
    
    owner = path_parts[0]
    repo = path_parts[1].replace('.git', '')
    
    return owner, repo

def get_safe_files(owner: str, repo: str, max_size: int = MAX_FILE_SIZE_BYTES) -> list[str]:
    """
    Get list of files under max_size from GitHub API.
    Returns file paths that are safe to clone.
    """
    github_token = os.getenv("GITHUB_TOKEN")
    headers = {}
    if github_token:
        headers['Authorization'] = f'Bearer {github_token}'
    
    try:
        url = f"{GITHUB_API_URL}/repos/{owner}/{repo}/git/trees/HEAD?recursive=1"
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        
        safe_files = []
        for item in response.json().get('tree', []):
            if item['type'] == 'blob':  # It's a file, not a directory
                size = item.get('size', 0)
                if size <= max_size:
                    safe_files.append(item['path'])
        
        return safe_files
    except requests.exceptions.RequestException as e:
        raise GitCloneException(f"Failed to get file list from GitHub API: {e}")


def clone_repo(repo_url: str, dest_path: str) -> None:
    """
    Clone repository, filtering out large files using GitHub API.
    
    Steps:
    1. Get all files and their sizes from GitHub API
    2. Filter to only files under MAX_FILE_SIZE_BYTES
    3. Clone with --no-checkout (skips file download initially)
    4. Directly checkout only the safe files (avoids downloading large objects)
    """
    # Parse repo URL
    try:
        owner, repo = parse_github_url(repo_url)
    except GitCloneException as e:
        raise GitCloneException(f"Failed to parse repository URL: {e}")
    
    # Get safe files from GitHub API
    logger.info(f"Fetching file list from GitHub API for {owner}/{repo}...")
    safe_files = get_safe_files(owner, repo)
    logger.info(f"Found {len(safe_files)} files under {MAX_FILE_SIZE_BYTES / (1024 * 1024)}MiB")
    
    if not safe_files:
        raise GitCloneException("No files under size limit found in repository")
    
    
    # clone but do NOT checkout because otherwise large files get downloaded and clog bandwith
    logger.info(f"Cloning {repo_url} to {dest_path}...")
    result = subprocess.run(
        ["git", "clone", "--depth", "100", "--no-checkout", "--filter=blob:limit=500k", repo_url, dest_path],
        capture_output=True,
        text=True,
        encoding='utf-8',
        errors='ignore',
        timeout=120
    )
    if result.returncode != 0:
        raise GitCloneException(f"Failed to clone repository: {result.stderr}")
    
    # checkout every file that's good
    logger.info(f"Checking out {len(safe_files)} safe files...")
    for i, file_path in enumerate(safe_files, 1):
        if i % 100 == 0:
            logger.info(f"  Progress: {i}/{len(safe_files)} files checked out...")
        
        result = subprocess.run(
            ["git", "checkout", "HEAD", "--", file_path],
            cwd=dest_path,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='ignore',
            timeout=10
        )
        if result.returncode != 0:
            # Log warning but continue
            logger.warning(f"Warning: Failed to checkout {file_path}: {result.stderr}")
    
    logger.info(f"Successfully cloned {repo} to {dest_path}")

if __name__ == "__main__":
    with tempfile.TemporaryDirectory() as temp_dir:
        logger.info(temp_dir)
        clone_repo("https://github.com/Arihan10/Vibe-Video-Test.git", temp_dir)
