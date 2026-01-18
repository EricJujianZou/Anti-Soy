"""
Test script for Anti-Soy API endpoints.
Tests /metadata and /repo endpoints with real GitHub data.
"""

import time
import json
import requests
from typing import Optional

BASE_URL = "http://127.0.0.1:8000"

# Test configuration
GITHUB_USERNAME = "EricJujianZou"
GITHUB_PROFILE_URL = f"https://github.com/{GITHUB_USERNAME}"

COMPANY_DESCRIPTION = """Job Summary:
Slash is building the future of business banking, one industry at a time. We believe businesses deserve financial infrastructure tailored to how they actually operate. That's why we're creating a new category of business banking. We combine the reliability of traditional banking (high yields, competitive rewards, and comprehensive security) with industry-specific features that make businesses more efficient, more competitive, and more profitable.

Started in 2021, Slash is one of the fastest growing fintechs in the world and we power over 6 billion dollars a year in business purchasing across a numerous industries. We're backed by some of the best investors in the world including Goodwater Capital, NEA, Y Combinator, Stanford University, and the founders of Tinder and Plaid. Slash is headquartered in San Francisco, and has a strong in-person culture."""

# Number of repos to analyze
NUM_REPOS_TO_ANALYZE = 5

# Polling configuration
POLL_INTERVAL = 5  # seconds
MAX_POLL_ATTEMPTS = 60  # 5 minutes max wait


def print_separator(title: str = ""):
    """Print a visual separator"""
    print("\n" + "=" * 80)
    if title:
        print(f"  {title}")
        print("=" * 80)
    print()


def print_json(data: dict, indent: int = 2):
    """Pretty print JSON data"""
    print(json.dumps(data, indent=indent, default=str))


def test_health_check():
    """Test the root endpoint"""
    print_separator("Testing Health Check (GET /)")
    
    try:
        response = requests.get(f"{BASE_URL}/")
        print(f"Status: {response.status_code}")
        print_json(response.json())
        return response.status_code == 200
    except Exception as e:
        print(f"ERROR: {e}")
        return False


def test_metadata_endpoint() -> Optional[dict]:
    """
    Test the /metadata endpoint.
    Creates a user and fetches their repos from GitHub.
    Returns the response data including user info.
    """
    print_separator(f"Testing Metadata Endpoint (PUT /metadata)")
    print(f"GitHub User: {GITHUB_USERNAME}")
    print(f"URL: {GITHUB_PROFILE_URL}")
    
    try:
        response = requests.put(
            f"{BASE_URL}/metadata",
            params={"user": GITHUB_PROFILE_URL}
        )
        
        print(f"\nStatus: {response.status_code}")
        data = response.json()
        print_json(data)
        
        if response.status_code == 200:
            print(f"\n✓ User created successfully!")
            print(f"  User ID: {data.get('id')}")
            print(f"  Username: {data.get('username')}")
            return data
        else:
            print(f"\n✗ Failed to create user")
            return None
            
    except Exception as e:
        print(f"ERROR: {e}")
        return None


def get_user_repos_from_db() -> list[str]:
    """
    Get the list of repos for the user from the database.
    Since we don't have a direct endpoint, we'll use GitHub API to get recent repos.
    """
    print_separator("Fetching Recent Repos from GitHub API")
    
    try:
        # Use GitHub REST API to get recent repos
        response = requests.get(
            f"https://api.github.com/users/{GITHUB_USERNAME}/repos",
            params={
                "sort": "updated",
                "direction": "desc",
                "per_page": NUM_REPOS_TO_ANALYZE
            }
        )
        
        if response.status_code == 200:
            repos = response.json()
            repo_urls = [repo["html_url"] for repo in repos]
            
            print(f"Found {len(repo_urls)} most recent repos:")
            for i, url in enumerate(repo_urls, 1):
                print(f"  {i}. {url}")
            
            return repo_urls
        else:
            print(f"Failed to fetch repos: {response.status_code}")
            return []
            
    except Exception as e:
        print(f"ERROR: {e}")
        return []


def start_repo_analysis(repo_url: str) -> Optional[int]:
    """
    Start analysis for a repository.
    Returns the repo_id for polling.
    """
    print(f"\nStarting analysis for: {repo_url}")
    
    try:
        response = requests.put(
            f"{BASE_URL}/repo",
            params={
                "repo": repo_url,
                "company_description": COMPANY_DESCRIPTION
            }
        )
        
        data = response.json()
        
        if response.status_code == 200:
            repo_id = data.get("repo_id")
            print(f"  ✓ Analysis started - repo_id: {repo_id}")
            return repo_id
        else:
            print(f"  ✗ Failed: {data}")
            return None
            
    except Exception as e:
        print(f"  ✗ ERROR: {e}")
        return None


def poll_for_results(repo_id: int, repo_url: str) -> Optional[dict]:
    """
    Poll the /repo/{repo_id} endpoint until analysis is complete.
    Returns the full analysis results.
    """
    print(f"\nPolling for results (repo_id: {repo_id})...")
    
    for attempt in range(MAX_POLL_ATTEMPTS):
        try:
            response = requests.get(f"{BASE_URL}/repo/{repo_id}")
            data = response.json()
            
            status = data.get("status")
            
            if status == "complete":
                print(f"  ✓ Analysis complete after {(attempt + 1) * POLL_INTERVAL} seconds")
                return data
            elif status == "pending":
                print(f"  ... waiting ({(attempt + 1) * POLL_INTERVAL}s)")
                time.sleep(POLL_INTERVAL)
            else:
                print(f"  ✗ Unexpected status: {status}")
                return data
                
        except Exception as e:
            print(f"  ✗ Poll error: {e}")
            time.sleep(POLL_INTERVAL)
    
    print(f"  ✗ Timeout after {MAX_POLL_ATTEMPTS * POLL_INTERVAL} seconds")
    return None


def print_analysis_results(repo_url: str, results: dict):
    """Print the full analysis results in a formatted way"""
    print_separator(f"Analysis Results: {repo_url.split('/')[-1]}")
    
    print(f"Repository: {results.get('github_link')}")
    print(f"Repo ID: {results.get('repo_id')}")
    print(f"Status: {results.get('status')}")
    
    metrics = results.get("metrics", {})
    
    if not metrics:
        print("\nNo metrics available.")
        return
    
    print("\n" + "-" * 60)
    print("METRICS (will be stored in RepoData table):")
    print("-" * 60)
    
    # Calculate total score
    total_score = 0
    valid_metrics = 0
    
    for metric_name, metric_data in metrics.items():
        if metric_data:
            score = metric_data.get("score", "N/A")
            comment = metric_data.get("comment", "No comment")
            
            if isinstance(score, int):
                total_score += score
                valid_metrics += 1
            
            print(f"\n{metric_name.upper()}:")
            print(f"  Score: {score}/100")
            print(f"  Comment: {comment}")
    
    # Print summary
    if valid_metrics > 0:
        avg_score = total_score / valid_metrics
        print("\n" + "-" * 60)
        print(f"SUMMARY:")
        print(f"  Average Score: {avg_score:.1f}/100")
        print(f"  Metrics Analyzed: {valid_metrics}/14")
        print("-" * 60)
    
    # Print raw JSON for DB storage reference
    print("\n" + "-" * 60)
    print("RAW JSON (as stored in database):")
    print("-" * 60)
    print_json(metrics)


def test_repo_analysis_endpoint(repo_urls: list[str]):
    """
    Test the /repo endpoint for multiple repositories.
    Starts all analyses, then polls for results.
    """
    print_separator("Testing Repo Analysis Endpoint (PUT /repo)")
    print(f"Company Description: {COMPANY_DESCRIPTION[:100]}...")
    print(f"\nWill analyze {len(repo_urls)} repositories")
    
    # Start all analyses
    analysis_tasks = []  # List of (repo_url, repo_id)
    
    for repo_url in repo_urls:
        repo_id = start_repo_analysis(repo_url)
        if repo_id:
            analysis_tasks.append((repo_url, repo_id))
    
    if not analysis_tasks:
        print("\n✗ No analyses started successfully")
        return
    
    print(f"\n{len(analysis_tasks)} analyses started. Waiting for results...")
    
    # Poll for each result
    all_results = []
    
    for repo_url, repo_id in analysis_tasks:
        result = poll_for_results(repo_id, repo_url)
        if result:
            all_results.append((repo_url, result))
    
    # Print all results
    for repo_url, result in all_results:
        print_analysis_results(repo_url, result)
    
    # Final summary
    print_separator("FINAL SUMMARY")
    print(f"Total repositories analyzed: {len(all_results)}/{len(repo_urls)}")
    
    if all_results:
        # Calculate overall stats
        all_scores = []
        for repo_url, result in all_results:
            metrics = result.get("metrics", {})
            for metric_data in metrics.values():
                if metric_data and isinstance(metric_data.get("score"), int):
                    all_scores.append(metric_data["score"])
        
        if all_scores:
            print(f"Overall average score: {sum(all_scores) / len(all_scores):.1f}/100")
            print(f"Highest score: {max(all_scores)}/100")
            print(f"Lowest score: {min(all_scores)}/100")


def main():
    """Main test function"""
    print_separator("ANTI-SOY API TEST SCRIPT")
    print(f"Base URL: {BASE_URL}")
    print(f"GitHub User: {GITHUB_USERNAME}")
    print(f"Repos to analyze: {NUM_REPOS_TO_ANALYZE}")
    
    # Test 1: Health check
    if not test_health_check():
        print("\n✗ Server not responding. Make sure the server is running:")
        print("  cd server && uv run uvicorn main:app --reload")
        return
    
    # Test 2: Create user and fetch metadata
    user_data = test_metadata_endpoint()
    
    # Test 3: Get recent repos to analyze
    repo_urls = get_user_repos_from_db()
    
    if not repo_urls:
        print("\n✗ No repos found to analyze")
        return
    
    # Test 4: Analyze repos
    test_repo_analysis_endpoint(repo_urls)
    
    print_separator("TEST COMPLETE")


if __name__ == "__main__":
    main()
