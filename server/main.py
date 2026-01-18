import subprocess
import tempfile
import os
import json
import requests
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from models import Base, User, Repo

load_dotenv()

# Database setup - use absolute path relative to this file
BASE_DIR = Path(__file__).resolve().parent
DATABASE_PATH = BASE_DIR / "database.db"
engine = create_engine(f"sqlite:///{DATABASE_PATH}", connect_args={"check_same_thread": False})

# Create tables
Base.metadata.create_all(bind=engine)

app = FastAPI()


def fetch_repos(user: User, session: Session):
    """Fetch user's repos from GitHub and store in DB"""
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        print("Warning: GITHUB_TOKEN not found in .env")
        return

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
                json={"query": repos_query, "variables": {"username": user.username, "cursor": cursor}},
                headers=headers
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
                    "prs_merged": 0 
                }
            
            has_next = repos["pageInfo"]["hasNextPage"]
            cursor = repos["pageInfo"]["endCursor"]
            
            if len(repo_data_map) > 500: # Safety limit
                break

        # Fetch PRs and aggregate
        has_next = True
        cursor = None
        total_prs_fetched = 0
        
        while has_next:
            resp = requests.post(
                "https://api.github.com/graphql",
                json={"query": prs_query, "variables": {"username": user.username, "cursor": cursor}},
                headers=headers
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
            
            if total_prs_fetched > 1000: # Safety limit for PRs
                break
                
        # Insert into DB
        for url, r_data in repo_data_map.items():
            db_repo = Repo(
                user_id=user.id,
                github_link=url,
                stars=r_data["stars"],
                is_open_source_project=r_data["is_open_source"],
                prs_merged=r_data["prs_merged"],
                languages=json.dumps(r_data["languages"])
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
def create_user_metadata(user: str = Query(..., description="GitHub link to user profile or repo")):
    """
    Create a user from a GitHub link.
    Accepts both user profile links (https://github.com/username) 
    and repo links (https://github.com/username/repo-name).
    """
    try:
        username = parse_github_username(user)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    github_link = f"https://github.com/{username}"
    
    with Session(engine) as session:
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
            "updated_at": db_user.updated_at
        }


@app.put("/repo")
def clone_repo(repo: str = Query(..., description="GitHub link to a repository")):
    """
    Clone a GitHub repository into a temporary directory.
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
            detail="Invalid repo link. Must be https://github.com/username/repo-name"
        )
    
    username = path_parts[0]
    repo_name = path_parts[1]
    repo_link = f"https://github.com/{username}/{repo_name}"
    
    # Create temp directory and clone repo
    with tempfile.TemporaryDirectory() as temp_dir:
        result = subprocess.run(
            ["git", "clone", repo_link, temp_dir],
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to clone repository: {result.stderr}"
            )
        
        cloned_path = temp_dir
        
        # TODO: Future implementation will process the cloned repo here
        
        return {
            "status": "cloned",
            "repo_link": repo_link,
            "username": username,
            "repo_name": repo_name,
            "temp_path": cloned_path
        }
