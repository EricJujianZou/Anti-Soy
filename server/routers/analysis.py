from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import json
import sys
import os

# Add parent directory to path to allow imports from root of server
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import get_db
from models import User, Repo, RepoData
from services.github import GitHubGraphQLClient
from services.metrics import MetricsCalculator

router = APIRouter(prefix="/analyze", tags=["analysis"])
github_client = GitHubGraphQLClient()

@router.post("/{username}")
async def analyze_user(username: str, db: Session = Depends(get_db)):
    try:
        # 1. Fetch data from GitHub
        user_data = await github_client.fetch_user_data(username)
        if not user_data:
            raise HTTPException(status_code=404, detail="GitHub user not found")
            
        # 2. Update or Create User
        # Check if user exists
        user = db.query(User).filter(User.username == user_data['login']).first()
        if not user:
            user = User(
                username=user_data['login'],
                github_link=user_data['url']
                # created_at handled by default
            )
            db.add(user)
            db.commit()
            db.refresh(user)
        
        # 3. Process Repositories
        nodes = user_data.get('repositories', {}).get('nodes', [])
        analyzed_repos = []
        
        for repo_node in nodes:
            name = repo_node['name']
            link = repo_node['url']
            stars = repo_node['stargazerCount']
            
            # Languages to string
            langs = [l['name'] for l in repo_node.get('languages', {}).get('nodes', [])]
            langs_str = json.dumps(langs)
            
            # Find or Create Repo
            repo = db.query(Repo).filter(Repo.github_link == link).first()
            if not repo:
                repo = Repo(
                    user_id=user.id,
                    github_link=link,
                    stars=stars,
                    languages=langs_str,
                    is_open_source_project=not repo_node.get('isFork', False)
                )
                db.add(repo)
                db.commit()
                db.refresh(repo)
            else:
                # Update existing repo
                repo.stars = stars
                repo.languages = langs_str
                # Update user_id just in case? Usually logic ensures it's same user
                db.commit()
            
            # Metrics Calculation
            commits = repo_node.get('defaultBranchRef', {}).get('target', {}).get('history', {}).get('nodes', []) if repo_node.get('defaultBranchRef') else []
            
            commit_density = MetricsCalculator.calculate_commit_density(commits)
            commit_lines = MetricsCalculator.calculate_commit_lines(commits)
            
            # Update RepoData
            repo_data = db.query(RepoData).filter(RepoData.repo_id == repo.id).first()
            if not repo_data:
                repo_data = RepoData(
                    repo_id=repo.id,
                    commit_density=commit_density,
                    commit_lines=commit_lines
                )
                db.add(repo_data)
            else:
                repo_data.commit_density = commit_density
                repo_data.commit_lines = commit_lines
            
            db.commit()
            
            analyzed_repos.append({
                "name": name,
                "metrics": {
                    "density": commit_density,
                    "lines": commit_lines
                }
            })
            
        return {
            "status": "success",
            "username": username,
            "repos_analyzed": len(analyzed_repos),
            "details": analyzed_repos
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
