"""
Anti-Soy V2 API

Main FastAPI application with endpoints for repository analysis.
"""

import json
import os
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from models import Base, User, Repo, RepoData

# V2 imports
from v2.data_extractor import extract_repo_data
from v2.feature_extractor import extract_features
from v2.analyzers import analyze_ai_slop, analyze_bad_practices, analyze_code_quality
from v2.schemas import (
    AnalyzeRequest,
    AnalysisResponse,
    RepoInfo,
    Verdict,
    InterviewQuestionsRequest,
    InterviewQuestionsResponse,
    InterviewQuestion,
)

load_dotenv()

# Database setup
BASE_DIR = Path(__file__).resolve().parent
DATABASE_PATH = BASE_DIR / "database.db"
engine = create_engine(
    f"sqlite:///{DATABASE_PATH}", connect_args={"check_same_thread": False}
)

# Create tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Anti-Soy API",
    description="GitHub profile analyzer for detecting vibe coders vs competent engineers",
    version="2.0.0",
)

# CORS middleware
ALLOWED_ORIGINS = [
    "https://ericjujianzou.github.io",
    "https://EricJujianZou.github.io",
    "http://localhost:5173",
    "http://localhost:3000",
    "http://localhost:8080",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =============================================================================
# VERDICT LOGIC
# =============================================================================

def compute_verdict(ai_score: int, bad_practices_score: int, quality_score: int) -> Verdict:
    """
    Compute verdict based on analyzer scores.
    
    All cases are explicitly covered (no default fallback):
    
    | AI Score | Bad Practices | Quality | Verdict |
    |----------|---------------|---------|---------|
    | ≥60      | ≥50           | <50     | Slop Coder |
    | ≥60      | <50           | ≥50     | Good AI Coder |
    | <60      | <50           | ≥50     | Senior |
    | <60      | ≥50           | <50     | Junior |
    
    Edge cases (mixed signals) → closest match based on primary signal (AI score)
    """
    # High AI usage (≥60)
    if ai_score >= 60:
        if bad_practices_score >= 50 and quality_score < 50:
            # Slop Coder: High AI + sloppy code + low quality
            confidence = min(100, 60 + (ai_score - 60) // 2 + (bad_practices_score - 50) // 2 + (50 - quality_score) // 2)
            return Verdict(type="Slop Coder", confidence=confidence)
        elif bad_practices_score < 50 and quality_score >= 50:
            # Good AI Coder: High AI + clean code + good quality
            confidence = min(100, 60 + (ai_score - 60) // 3 + (50 - bad_practices_score) // 3 + (quality_score - 50) // 3)
            return Verdict(type="Good AI Coder", confidence=confidence)
        else:
            # Edge case: High AI but mixed signals
            # If quality is high, lean toward Good AI Coder; otherwise Slop Coder
            if quality_score >= 50:
                confidence = 50  # Low confidence due to mixed signals
                return Verdict(type="Good AI Coder", confidence=confidence)
            else:
                confidence = 50
                return Verdict(type="Slop Coder", confidence=confidence)
    
    # Low AI usage (<60)
    else:
        if bad_practices_score < 50 and quality_score >= 50:
            # Senior: Low AI + clean code + good quality
            confidence = min(100, 60 + (60 - ai_score) // 3 + (50 - bad_practices_score) // 3 + (quality_score - 50) // 3)
            return Verdict(type="Senior", confidence=confidence)
        elif bad_practices_score >= 50 and quality_score < 50:
            # Junior: Low AI + sloppy code + low quality
            confidence = min(100, 60 + (bad_practices_score - 50) // 2 + (50 - quality_score) // 2)
            return Verdict(type="Junior", confidence=confidence)
        else:
            # Edge case: Low AI but mixed signals
            # If quality is high, lean toward Senior; otherwise Junior
            if quality_score >= 50:
                confidence = 50
                return Verdict(type="Senior", confidence=confidence)
            else:
                confidence = 50
                return Verdict(type="Junior", confidence=confidence)


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def parse_repo_url(repo_url: str) -> tuple[str, str]:
    """Parse GitHub repo URL and return (username, repo_name)."""
    parsed = urlparse(repo_url)
    
    if parsed.netloc != "github.com":
        raise HTTPException(status_code=400, detail="Invalid GitHub URL. Must be github.com")
    
    path_parts = [p for p in parsed.path.split("/") if p]
    
    if len(path_parts) < 2:
        raise HTTPException(
            status_code=400,
            detail="Invalid repo URL. Must be https://github.com/username/repo-name"
        )
    
    return path_parts[0], path_parts[1]


def get_or_create_user(session: Session, username: str) -> User:
    """Get existing user or create new one."""
    user = session.query(User).filter(User.username == username).first()
    
    if not user:
        user = User(
            username=username,
            github_link=f"https://github.com/{username}",
        )
        session.add(user)
        session.flush()
    
    return user


def get_or_create_repo(session: Session, user: User, repo_url: str, repo_name: str) -> Repo:
    """Get existing repo or create new one."""
    repo = session.query(Repo).filter(Repo.github_link == repo_url).first()
    
    if not repo:
        repo = Repo(
            user_id=user.id,
            github_link=repo_url,
            repo_name=repo_name,
            stars=0,
            languages="{}",
        )
        session.add(repo)
        session.flush()
    
    return repo


def build_analysis_response(repo: Repo, repo_data_entry: RepoData) -> AnalysisResponse:
    """Build AnalysisResponse from database entry."""
    ai_slop_data = json.loads(repo_data_entry.ai_slop_data) if repo_data_entry.ai_slop_data else {}
    bad_practices_data = json.loads(repo_data_entry.bad_practices_data) if repo_data_entry.bad_practices_data else {}
    code_quality_data = json.loads(repo_data_entry.code_quality_data) if repo_data_entry.code_quality_data else {}
    files_analyzed = json.loads(repo_data_entry.files_analyzed) if repo_data_entry.files_analyzed else []
    languages = json.loads(repo.languages) if repo.languages else {}
    
    return AnalysisResponse(
        repo=RepoInfo(
            url=repo.github_link,
            name=repo.repo_name,
            owner=repo.user.username,
            languages=languages,
            analyzed_at=repo_data_entry.analyzed_at,
        ),
        verdict=Verdict(
            type=repo_data_entry.verdict_type,
            confidence=repo_data_entry.verdict_confidence,
        ),
        ai_slop=ai_slop_data,
        bad_practices=bad_practices_data,
        code_quality=code_quality_data,
        files_analyzed=files_analyzed,
    )


# =============================================================================
# API ENDPOINTS
# =============================================================================

@app.get("/")
def read_root():
    """Health check endpoint."""
    return {"status": "ok", "version": "2.0.0", "message": "Anti-Soy API"}


@app.post("/analyze", response_model=AnalysisResponse)
def analyze_repo(request: AnalyzeRequest):
    """
    Analyze a GitHub repository.
    
    Clones the repo, runs all three analyzers, computes verdict,
    and stores results in database.
    
    Returns cached results if repo was already analyzed.
    """
    # Parse and validate URL
    username, repo_name = parse_repo_url(request.repo_url)
    repo_url = f"https://github.com/{username}/{repo_name}"
    
    with Session(engine) as session:
        # Get or create user and repo
        user = get_or_create_user(session, username)
        repo = get_or_create_repo(session, user, repo_url, repo_name)
        
        # Check if already analyzed
        if repo.repo_data:
            return build_analysis_response(repo, repo.repo_data)
        
        # Clone repository
        with tempfile.TemporaryDirectory() as temp_dir:
            result = subprocess.run(
                ["git", "clone", "--depth", "100", repo_url, temp_dir],
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
            extracted_data = extract_repo_data(temp_dir)
            
            # Extract features for ML classifier
            features = extract_features(extracted_data)
            
            # Update repo with languages from extraction
            if extracted_data.languages:
                repo.languages = json.dumps(extracted_data.languages)
            
            # Run all three analyzers
            ai_slop_result = analyze_ai_slop(extracted_data, features)
            bad_practices_result = analyze_bad_practices(extracted_data)
            code_quality_result = analyze_code_quality(extracted_data)
            
            # Compute verdict
            verdict = compute_verdict(
                ai_slop_result.score,
                bad_practices_result.score,
                code_quality_result.score,
            )
            
            # Build files_analyzed list from importance scores (clamp to 0-100 for API schema)
            files_analyzed = [
                {"path": path, "importance_score": min(max(score, 0), 100), "loc": len(extracted_data.files.get(path, "").split("\n"))}
                for path, score in sorted(
                    extracted_data.file_importance.items(),
                    key=lambda x: x[1],
                    reverse=True
                )[:15]
            ]
            
            # Store in database
            repo_data_entry = RepoData(
                repo_id=repo.id,
                analyzed_at=datetime.utcnow(),
                verdict_type=verdict.type,
                verdict_confidence=verdict.confidence,
                ai_slop_score=ai_slop_result.score,
                ai_slop_confidence=ai_slop_result.confidence.value,
                ai_slop_data=ai_slop_result.model_dump_json(),
                bad_practices_score=bad_practices_result.score,
                bad_practices_data=bad_practices_result.model_dump_json(),
                code_quality_score=code_quality_result.score,
                code_quality_data=code_quality_result.model_dump_json(),
                files_analyzed=json.dumps(files_analyzed),
            )
            session.add(repo_data_entry)
            session.commit()
            session.refresh(repo_data_entry)
            session.refresh(repo)
            
            return build_analysis_response(repo, repo_data_entry)


@app.post("/interview-questions", response_model=InterviewQuestionsResponse)
def generate_interview_questions(request: InterviewQuestionsRequest):
    """
    Generate interview questions based on analysis findings.
    Uses Gemini LLM to create targeted questions.
    """
    from google import genai
    
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    if not GEMINI_API_KEY:
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY not configured")
    
    with Session(engine) as session:
        repo = session.query(Repo).filter(Repo.id == request.repo_id).first()
        
        if not repo:
            raise HTTPException(status_code=404, detail="Repository not found")
        
        if not repo.repo_data:
            raise HTTPException(status_code=400, detail="Repository has not been analyzed yet")
        
        # Check if questions already generated
        if repo.repo_data.interview_questions:
            questions = json.loads(repo.repo_data.interview_questions)
            return InterviewQuestionsResponse(
                repo_id=repo.id,
                repo_url=repo.github_link,
                questions=[InterviewQuestion(**q) for q in questions],
            )
        
        # Gather findings for prompt
        ai_slop_data = json.loads(repo.repo_data.ai_slop_data) if repo.repo_data.ai_slop_data else {}
        bad_practices_data = json.loads(repo.repo_data.bad_practices_data) if repo.repo_data.bad_practices_data else {}
        code_quality_data = json.loads(repo.repo_data.code_quality_data) if repo.repo_data.code_quality_data else {}
        
        findings_summary = []
        
        for finding in ai_slop_data.get("negative_ai_signals", [])[:5]:
            findings_summary.append({
                "category": "AI Slop",
                "type": finding.get("type"),
                "file": finding.get("file"),
                "line": finding.get("line"),
                "snippet": finding.get("snippet", "")[:200],
                "explanation": finding.get("explanation"),
            })
        
        for finding in bad_practices_data.get("findings", [])[:5]:
            findings_summary.append({
                "category": "Bad Practices",
                "type": finding.get("type"),
                "file": finding.get("file"),
                "line": finding.get("line"),
                "snippet": finding.get("snippet", "")[:200],
                "explanation": finding.get("explanation"),
            })
        
        for finding in code_quality_data.get("findings", [])[:5]:
            findings_summary.append({
                "category": "Code Quality",
                "type": finding.get("type"),
                "file": finding.get("file"),
                "line": finding.get("line"),
                "snippet": finding.get("snippet", "")[:200],
                "explanation": finding.get("explanation"),
            })
        
        if not findings_summary:
            return InterviewQuestionsResponse(
                repo_id=repo.id,
                repo_url=repo.github_link,
                questions=[],
            )
        
        prompt = f"""You are a technical interviewer reviewing a candidate's GitHub repository.
Based on the following code analysis findings, generate 3-5 interview questions that:
1. Reference the specific code snippet or pattern found
2. Probe whether the candidate understands WHY this is a problem
3. Test if they know the correct approach

Repository: {repo.github_link}
Verdict: {repo.repo_data.verdict_type}

Findings:
{json.dumps(findings_summary, indent=2)}

Generate questions in this JSON format:
[
  {{
    "question": "The specific question to ask",
    "based_on": "Brief reference to the finding (e.g., 'SQL injection in auth.py:45')",
    "probes": "What skill/knowledge this tests (e.g., 'sql_injection_prevention')"
  }}
]

Return ONLY the JSON array, no other text."""

        client = genai.Client(api_key=GEMINI_API_KEY)
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt,
        )
        
        try:
            response_text = response.text.strip()
            if response_text.startswith("```"):
                response_text = response_text.split("```")[1]
                if response_text.startswith("json"):
                    response_text = response_text[4:]
            questions_data = json.loads(response_text)
        except (json.JSONDecodeError, IndexError) as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to parse LLM response: {str(e)}"
            )
        
        questions = []
        for q in questions_data[:5]:
            questions.append(InterviewQuestion(
                question=q.get("question", ""),
                based_on=q.get("based_on", ""),
                probes=q.get("probes", ""),
            ))
        
        repo.repo_data.interview_questions = json.dumps([q.model_dump() for q in questions])
        session.commit()
        
        return InterviewQuestionsResponse(
            repo_id=repo.id,
            repo_url=repo.github_link,
            questions=questions,
        )


@app.get("/repo/{repo_id}")
def get_repo_analysis(repo_id: int):
    """Get analysis results for a specific repository by ID."""
    with Session(engine) as session:
        repo = session.query(Repo).filter(Repo.id == repo_id).first()
        
        if not repo:
            raise HTTPException(status_code=404, detail="Repository not found")
        
        if not repo.repo_data:
            raise HTTPException(status_code=400, detail="Repository has not been analyzed yet")
        
        return build_analysis_response(repo, repo.repo_data)


@app.delete("/repo/{repo_id}")
def delete_repo_analysis(repo_id: int):
    """Delete analysis results for a repository (allows re-analysis)."""
    with Session(engine) as session:
        repo = session.query(Repo).filter(Repo.id == repo_id).first()
        
        if not repo:
            raise HTTPException(status_code=404, detail="Repository not found")
        
        if repo.repo_data:
            session.delete(repo.repo_data)
            session.commit()
        
        return {"status": "deleted", "repo_id": repo_id}


