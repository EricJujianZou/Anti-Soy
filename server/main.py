import subprocess
import tempfile
from pathlib import Path
from urllib.parse import urlparse

from fastapi import FastAPI, HTTPException, Query
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from models import Base, User

# Database setup - use absolute path relative to this file
BASE_DIR = Path(__file__).resolve().parent
DATABASE_PATH = BASE_DIR / "database.db"
engine = create_engine(f"sqlite:///{DATABASE_PATH}", connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create tables
Base.metadata.create_all(bind=engine)

app = FastAPI()


def fetch_repos(user: User):
    """Placeholder - will fetch user's repos from GitHub"""
    pass


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
    
    db = SessionLocal()
    try:
        # Create user row
        db_user = User(username=username, github_link=github_link)
        db.add(db_user)
        db.flush()  # Get the ID before calling fetch_repos
        
        # Call placeholder function
        fetch_repos(db_user)
        
        db.commit()
        db.refresh(db_user)
        
        return {
            "id": db_user.id,
            "username": db_user.username,
            "github_link": db_user.github_link,
            "created_at": db_user.created_at,
            "updated_at": db_user.updated_at
        }
    finally:
        db.close()


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
