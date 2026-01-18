import asyncio
import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import requests
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from models import Base, Repo, RepoData, User
from repo_analyzer import analyze_repository, extract_repo_data

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

# Add CORS middleware to allow frontend requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins in development
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


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
def clone_repo(
    repo: str = Query(..., description="GitHub link to a repository"),
    company_description: Optional[str] = Query(
        None, description="Company mission/job description for alignment analysis"
    ),
):
    """
    Analyze a GitHub repository. Clones it, runs analysis functions concurrently,
    and stores results in repo_data.
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

    with Session(engine) as session:
        # Validate repo exists in database
        db_repo = session.query(Repo).filter(Repo.github_link == repo_link).first()
        if not db_repo:
            raise HTTPException(
                status_code=404,
                detail=f"Repo not found in database. Run PUT /metadata first for user {username}",
            )

        # Return existing repo_data if already analyzed
        if db_repo.repo_data:
            return {
                "status": "already_analyzed",
                "repo_id": db_repo.id,
                "repo_link": repo_link,
                "files_organized": db_repo.repo_data.files_organized,
                "test_suites": db_repo.repo_data.test_suites,
                "readme": db_repo.repo_data.readme,
                "api_keys": db_repo.repo_data.api_keys,
                "error_handling": db_repo.repo_data.error_handling,
                "comments": db_repo.repo_data.comments,
                "print_or_logging": db_repo.repo_data.print_or_logging,
                "dependencies": db_repo.repo_data.dependencies,
                "commit_density": db_repo.repo_data.commit_density,
                "commit_lines": db_repo.repo_data.commit_lines,
                "concurrency": db_repo.repo_data.concurrency,
                "caching": db_repo.repo_data.caching,
                "solves_real_problem": db_repo.repo_data.solves_real_problem,
                "aligns_company": db_repo.repo_data.aligns_company,
            }

        # Clone and analyze
        with tempfile.TemporaryDirectory() as temp_dir:
            result = subprocess.run(
                ["git", "clone", "--depth", "100", repo_link, temp_dir],
                capture_output=True,
                text=True,
                timeout=120,
            )

            if result.returncode != 0:
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to clone repository: {result.stderr}",
                )

            # Extract repo data
            repo_data = extract_repo_data(temp_dir)

            # Run async analyses synchronously
            results = asyncio.run(analyze_repository(repo_data, company_description))

            # Create RepoData and store results
            repo_data_entry = RepoData(
                repo_id=db_repo.id,
                files_organized=results["files_organized"],
                test_suites=results["test_suites"],
                readme=results["readme"],
                api_keys=results["api_keys"],
                error_handling=results["error_handling"],
                comments=results["comments"],
                print_or_logging=results["print_or_logging"],
                dependencies=results["dependencies"],
                commit_density=results["commit_density"],
                commit_lines=results["commit_lines"],
                concurrency=results["concurrency"],
                caching=results["caching"],
                solves_real_problem=results["solves_real_problem"],
                aligns_company=results["aligns_company"],
            )
            session.add(repo_data_entry)
            session.commit()

            return {
                "status": "analyzed",
                "repo_id": db_repo.id,
                "repo_link": repo_link,
                **results,
            }

