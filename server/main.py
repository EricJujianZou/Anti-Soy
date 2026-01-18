import json
import os
import subprocess
import tempfile
import os
import json
import asyncio
import requests
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import requests
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query, BackgroundTasks
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from models import Base, User, Repo, RepoData
from repo_analyzer import extract_repo_data, analyze_repository

load_dotenv()

# Database setup - use absolute path relative to this file
BASE_DIR = Path(__file__).resolve().parent
DATABASE_PATH = BASE_DIR / "database.db"
engine = create_engine(
    f"sqlite:///{DATABASE_PATH}", connect_args={"check_same_thread": False}
)

# Create tables
Base.metadata.create_all(bind=engine)

app = FastAPI()


def fetch_repos(user: User, session: Session):
    """Fetch user's repos from GitHub and store in DB"""
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        raise HTTPException(status_code=500, detail="GITHUB_TOKEN not found in .env")

    headers = {"Authorization": f"Bearer {token}"}

    # 1. Fetch Repositories
    repos_query = """
    query($username: String!, $cursor: String) {
      user(login: $username) {
        repositories(first: 100, after: $cursor, ownerAffiliations: OWNER, privacy: PUBLIC, orderBy: {field: STARGAZERS, direction: DESC}) {
          pageInfo { hasNextPage endCursor }
          nodes {
            name
            url
            stargazerCount
            isPrivate
            languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
              edges { size node { name } }
            }
          }
        }
      }
    }
    """

    # 2. Fetch PR counts (merged by user) - simplified aggregation
    prs_query = """
    query($username: String!, $cursor: String) {
      user(login: $username) {
        pullRequests(first: 100, after: $cursor, states: MERGED, orderBy: {field: CREATED_AT, direction: DESC}) {
          pageInfo { hasNextPage endCursor }
          nodes {
            repository {
              url
            }
          }
        }
      }
    }
    """

    repo_data_map = {}
    has_next = True
    cursor = None

    try:
        # Fetch Repos
        while has_next:
            resp = requests.post(
                "https://api.github.com/graphql",
                json={
                    "query": repos_query,
                    "variables": {"username": user.username, "cursor": cursor},
                },
                headers=headers,
            )
            data = resp.json()
            if "errors" in data:
                print(f"GitHub API Error (Repos): {data['errors']}")
                break

            user_data = data.get("data", {}).get("user")
            if not user_data:
                break

            repos = user_data["repositories"]
            for node in repos["nodes"]:
                langs = {}
                if node["languages"] and node["languages"]["edges"]:
                    for edge in node["languages"]["edges"]:
                        langs[edge["node"]["name"]] = edge["size"]

                repo_data_map[node["url"]] = {
                    "stars": node["stargazerCount"],
                    "is_open_source": not node["isPrivate"],
                    "languages": langs,
                    "prs_merged": 0,
                }

            has_next = repos["pageInfo"]["hasNextPage"]
            cursor = repos["pageInfo"]["endCursor"]

            if len(repo_data_map) > 500:  # Safety limit
                break

        # Fetch PRs and aggregate
        has_next = True
        cursor = None
        total_prs_fetched = 0

        while has_next:
            resp = requests.post(
                "https://api.github.com/graphql",
                json={
                    "query": prs_query,
                    "variables": {"username": user.username, "cursor": cursor},
                },
                headers=headers,
            )
            data = resp.json()
            if "errors" in data:
                print(f"GitHub API Error (PRs): {data['errors']}")
                break

            user_data = data.get("data", {}).get("user")
            if not user_data:
                break

            prs = user_data["pullRequests"]
            for node in prs["nodes"]:
                repo_url = node["repository"]["url"]
                if repo_url in repo_data_map:
                    repo_data_map[repo_url]["prs_merged"] += 1

            has_next = prs["pageInfo"]["hasNextPage"]
            cursor = prs["pageInfo"]["endCursor"]
            total_prs_fetched += len(prs["nodes"])

            if total_prs_fetched > 1000:  # Safety limit for PRs
                break

        # Insert into DB
        for url, r_data in repo_data_map.items():
            db_repo = Repo(
                user_id=user.id,
                github_link=url,
                stars=r_data["stars"],
                is_open_source_project=r_data["is_open_source"],
                prs_merged=r_data["prs_merged"],
                languages=json.dumps(r_data["languages"]),
            )
            session.add(db_repo)

    except Exception as e:
        print(f"Error fetching repos: {e}")
        # We catch exceptions so we don't rollback the user creation entirely if GitHub fails?
        # User requested "fetch repos", if it fails, maybe we should propagate.
        # But 'parse all data...' implies logic.
        raise e


def parse_github_username(github_link: str) -> str:
    """Extract username from GitHub link (user profile or repo link)"""
    parsed = urlparse(github_link)

    if parsed.netloc != "github.com":
        raise ValueError("Invalid GitHub link")

    # Path format: /username or /username/repo-name
    path_parts = [p for p in parsed.path.split("/") if p]

    if len(path_parts) < 1:
        raise ValueError("Could not extract username from GitHub link")

    return path_parts[0]


@app.get("/")
def read_root():
    return {"Hello": "World"}


@app.put("/metadata")
def create_user_metadata(
    user: str = Query(..., description="GitHub link to user profile or repo"),
):
    """
    Create a user from a GitHub link, or return existing user if already exists.
    Accepts both user profile links (https://github.com/username)
    and repo links (https://github.com/username/repo-name).
    """
    try:
        username = parse_github_username(user)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    github_link = f"https://github.com/{username}"

    with Session(engine) as session:
        db_user = session.query(User).filter(User.username == username).first()

        if not db_user:
            db_user = User(username=username, github_link=github_link)
            session.add(db_user)
            session.flush()
            fetch_repos(db_user, session)
            session.commit()
            session.refresh(db_user)

        return {
            "id": db_user.id,
            "username": db_user.username,
            "github_link": db_user.github_link,
            "created_at": db_user.created_at,
            "updated_at": db_user.updated_at,
            "repos": [
                {
                    "id": repo.id,
                    "github_link": repo.github_link,
                    "stars": repo.stars,
                    "is_open_source_project": repo.is_open_source_project,
                    "prs_merged": repo.prs_merged,
                    "languages": repo.languages,
                }
                for repo in db_user.repos
            ],
        }


@app.put("/repo")
async def analyze_repo(
    repo: str = Query(..., description="GitHub link to a repository"),
    company_description: Optional[str] = Query(None, description="Company mission/job description for alignment analysis"),
    background_tasks: BackgroundTasks = None
):
    """
    Clone and analyze a GitHub repository.
    Returns immediately with task status, analysis runs in background.
    Link must be in format: https://github.com/username/repo-name
    """
    parsed = urlparse(repo)

    if parsed.netloc != "github.com":
        raise HTTPException(status_code=400, detail="Invalid GitHub link")

    # Path format must be: /username/repo-name
    path_parts = [p for p in parsed.path.split("/") if p]

    if len(path_parts) < 2:
        raise HTTPException(
            status_code=400,
            detail="Invalid repo link. Must be https://github.com/username/repo-name",
        )

    username = path_parts[0]
    repo_name = path_parts[1]
    repo_link = f"https://github.com/{username}/{repo_name}"
    
    # Find or create repo entry in DB
    with Session(engine) as session:
        db_repo = session.query(Repo).filter(Repo.github_link == repo_link).first()
        
        if not db_repo:
            # Create a repo without user association for independent analysis
            db_repo = Repo(
                user_id=1,  # Default user ID - should be updated based on your needs
                github_link=repo_link,
                stars=0,
                is_open_source_project=True,
                prs_merged=0,
                languages="{}"
            )
            session.add(db_repo)
            session.commit()
            session.refresh(db_repo)
        
        repo_id = db_repo.id
    
    # Add background task for analysis
    background_tasks.add_task(
        run_repo_analysis,
        repo_link=repo_link,
        repo_id=repo_id,
        company_description=company_description
    )
    
    return {
        "status": "analysis_started",
        "repo_link": repo_link,
        "repo_id": repo_id,
        "message": "Analysis running in background. Query /repo/{repo_id} for results."
    }


def run_repo_analysis(repo_link: str, repo_id: int, company_description: Optional[str] = None):
    """
    Background task to clone, analyze, and store repository metrics.
    """
    temp_dir = None
    try:
        # Create temp directory for cloning
        temp_dir = tempfile.mkdtemp()
        
        # Clone the repository
        result = subprocess.run(
            ["git", "clone", "--depth", "100", repo_link, temp_dir],
            capture_output=True,
            text=True,
            timeout=120
        )

        if result.returncode != 0:
            raise HTTPException(
                status_code=500, detail=f"Failed to clone repository: {result.stderr}"
            )
            
        
        # Extract repository data
        repo_data = extract_repo_data(temp_dir)
        
        # Run analysis (async function, need to run in event loop)
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            analysis_results = loop.run_until_complete(
                analyze_repository(repo_data, company_description)
            )
        finally:
            loop.close()
        
        # Store results in database
        with Session(engine) as session:
            # Check if RepoData already exists
            existing_data = session.query(RepoData).filter(RepoData.repo_id == repo_id).first()
            
            if existing_data:
                # Update existing
                existing_data.files_organized = analysis_results.get("files_organized")
                existing_data.test_suites = analysis_results.get("test_suites")
                existing_data.readme = analysis_results.get("readme")
                existing_data.api_keys = analysis_results.get("api_keys")
                existing_data.error_handling = analysis_results.get("error_handling")
                existing_data.comments = analysis_results.get("comments")
                existing_data.print_or_logging = analysis_results.get("print_or_logging")
                existing_data.dependencies = analysis_results.get("dependencies")
                existing_data.commit_density = analysis_results.get("commit_density")
                existing_data.commit_lines = analysis_results.get("commit_lines")
                existing_data.concurrency = analysis_results.get("concurrency")
                existing_data.caching = analysis_results.get("caching")
                existing_data.solves_real_problem = analysis_results.get("solves_real_problem")
                existing_data.aligns_company = analysis_results.get("aligns_company")
            else:
                # Create new
                repo_data_entry = RepoData(
                    repo_id=repo_id,
                    files_organized=analysis_results.get("files_organized"),
                    test_suites=analysis_results.get("test_suites"),
                    readme=analysis_results.get("readme"),
                    api_keys=analysis_results.get("api_keys"),
                    error_handling=analysis_results.get("error_handling"),
                    comments=analysis_results.get("comments"),
                    print_or_logging=analysis_results.get("print_or_logging"),
                    dependencies=analysis_results.get("dependencies"),
                    commit_density=analysis_results.get("commit_density"),
                    commit_lines=analysis_results.get("commit_lines"),
                    concurrency=analysis_results.get("concurrency"),
                    caching=analysis_results.get("caching"),
                    solves_real_problem=analysis_results.get("solves_real_problem"),
                    aligns_company=analysis_results.get("aligns_company"),
                )
                session.add(repo_data_entry)
            
            session.commit()
        
        print(f"Analysis complete for {repo_link}")
        
    except Exception as e:
        print(f"Error analyzing {repo_link}: {e}")
        _store_error_result(repo_id, str(e)[:200])
    
    finally:
        # Cleanup temp directory
        if temp_dir:
            import shutil
            try:
                shutil.rmtree(temp_dir)
            except Exception:
                pass


def _store_error_result(repo_id: int, error_message: str):
    """Store error result in database"""
    error_result = {"score": 0, "comment": f"Analysis failed: {error_message}"}
    
    with Session(engine) as session:
        existing_data = session.query(RepoData).filter(RepoData.repo_id == repo_id).first()
        
        if existing_data:
            existing_data.files_organized = error_result
        else:
            repo_data_entry = RepoData(
                repo_id=repo_id,
                files_organized=error_result,
            )
            session.add(repo_data_entry)
        
        session.commit()


@app.get("/repo/{repo_id}")
def get_repo_analysis(repo_id: int):
    """
    Get analysis results for a repository.
    """
    with Session(engine) as session:
        db_repo = session.query(Repo).filter(Repo.id == repo_id).first()
        
        if not db_repo:
            raise HTTPException(status_code=404, detail="Repository not found")
        
        repo_data = session.query(RepoData).filter(RepoData.repo_id == repo_id).first()
        
        if not repo_data:
            return {
                "repo_id": repo_id,
                "github_link": db_repo.github_link,
                "status": "pending",
                "message": "Analysis not yet complete or not started"
            }
        
        return {
            "repo_id": repo_id,
            "github_link": db_repo.github_link,
            "status": "complete",
            "metrics": {
                "files_organized": repo_data.files_organized,
                "test_suites": repo_data.test_suites,
                "readme": repo_data.readme,
                "api_keys": repo_data.api_keys,
                "error_handling": repo_data.error_handling,
                "comments": repo_data.comments,
                "print_or_logging": repo_data.print_or_logging,
                "dependencies": repo_data.dependencies,
                "commit_density": repo_data.commit_density,
                "commit_lines": repo_data.commit_lines,
                "concurrency": repo_data.concurrency,
                "caching": repo_data.caching,
                "solves_real_problem": repo_data.solves_real_problem,
                "aligns_company": repo_data.aligns_company,
            }
        }
