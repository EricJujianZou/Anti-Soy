"""
Anti-Soy V2 API

Main FastAPI application with endpoints for repository analysis.
"""

import json
import logging
import os
import re
import subprocess
import tempfile
import time
import asyncio
from datetime import datetime
from pathlib import Path

from logging_config import setup_logging
setup_logging()

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request, BackgroundTasks, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

from models import Base, User, Repo, RepoAnalysis, RepoEvaluation, BatchJob, BatchItem

# V2 imports
from v2.data_extractor import extract_repo_data
from v2.feature_extractor import extract_features
from v2.analyzers import analyze_ai_slop, analyze_bad_practices, analyze_code_quality
from v2.schemas import (
    AnalyzeRequest,
    AnalysisResponse,
    RepoInfo,
    Verdict,
    InterviewQuestion,
    EvaluateRequest,
    EvaluateResponse,
    BusinessValue,
    BatchStatusResponse,
    BatchItemStatus,
    BatchUploadResponse,
    CompatibilityRequest,
    CompatibilityResponse,
    CompatibilityCallout,
    VALID_PRIORITIES,
    DEFAULT_PRIORITIES,
)
from prompt_modules import build_evaluation_prompt, build_questions_prompt, build_compatibility_prompt
from v2.compatibility_scorer import compute_compatibility
from v2.batch_processor import process_batch
from v2.analysis_service import (
    compute_verdict, 
    save_analysis_results, 
    save_evaluation_results, 
    run_analysis_pipeline, 
    run_evaluation_pipeline,
    get_or_create_user,
    get_or_create_repo
)


load_dotenv()

# Database setup
DATABASE_URL = os.environ["DATABASE_URL"]
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
)

# Create tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Anti-Soy API",
    description="GitHub profile analyzer for detecting vibe coders vs competent engineers",
    version="2.0.0",
)

# Rate limiting
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content={"detail": "Too many requests. Please try again later."},
    )


# CORS middleware
ALLOWED_ORIGINS = [
    "https://antisoy.com",
    "https://www.antisoy.com",
    "https://ericjujianzou.github.io",
    "https://EricJujianZou.github.io",
    "http://localhost:5173",
    "http://localhost:3000",
    "http://localhost:3001",
    "http://localhost:8080",
    "http://localhost:8001",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type"],
)


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def parse_repo_url(repo_url: str) -> tuple[str, str]:
    """Parse and validate GitHub repo URL. Returns (username, repo_name)."""
    repo_url = repo_url.strip().rstrip("/")
    # Remove .git suffix if present
    if repo_url.endswith(".git"):
        repo_url = repo_url[:-4]

    match = re.match(r"^https://github\.com/([a-zA-Z0-9_.-]+)/([a-zA-Z0-9_.-]+)$", repo_url)
    if not match:
        raise HTTPException(
            status_code=400,
            detail="Invalid GitHub URL. Must be https://github.com/username/repo-name",
        )

    return match.group(1), match.group(2)


def build_analysis_response(repo: Repo, repo_analysis: RepoAnalysis) -> AnalysisResponse:
    """Build AnalysisResponse from database entry."""
    ai_slop_data = json.loads(repo_analysis.ai_slop_data)
    bad_practices_data = json.loads(repo_analysis.bad_practices_data)
    code_quality_data = json.loads(repo_analysis.code_quality_data)
    files_analyzed = json.loads(repo_analysis.files_analyzed)
    languages = json.loads(repo.languages) if repo.languages else {}

    return AnalysisResponse(
        repo=RepoInfo(
            url=repo.github_link,
            name=repo.repo_name,
            owner=repo.user.username,
            languages=languages,
            analyzed_at=repo_analysis.analyzed_at,
        ),
        verdict=Verdict(
            type=repo_analysis.verdict_type,
            confidence=repo_analysis.verdict_confidence,
        ),
        ai_slop=ai_slop_data,
        bad_practices=bad_practices_data,
        code_quality=code_quality_data,
        files_analyzed=files_analyzed,
    )


# =============================================================================
# SSE EVENT SERIALIZATION
# =============================================================================

def build_analysis_event_json(repo: Repo, repo_analysis: RepoAnalysis) -> str:
    """Build JSON string for the 'analysis' SSE event."""
    response = build_analysis_response(repo, repo_analysis)
    return response.model_dump_json()


def build_evaluation_event_json(repo_evaluation: RepoEvaluation) -> str:
    """Build JSON string for the 'evaluation' SSE event."""
    event = {
        "business_value": json.loads(repo_evaluation.business_value),
        "standout_features": json.loads(repo_evaluation.standout_features),
        "is_rejected": bool(repo_evaluation.is_rejected),
        "rejection_reason": repo_evaluation.rejection_reason,
    }
    return json.dumps(event)


def build_questions_event_json(repo_evaluation: RepoEvaluation) -> str:
    """Build JSON string for the 'questions' SSE event."""
    event = {
        "interview_questions": json.loads(repo_evaluation.interview_questions),
    }
    return json.dumps(event)


# =============================================================================
# API ENDPOINTS
# =============================================================================

@app.get("/")
def read_root():
    """Health check endpoint."""
    return {"status": "ok", "version": "2.0.0", "message": "Anti-Soy API"}


@app.post("/analyze", response_model=AnalysisResponse)
@limiter.limit("10/minute")
def analyze_repo(request: Request, body: AnalyzeRequest):
    """
    Analyze a GitHub repository.

    Clones the repo, runs all three analyzers, computes verdict,
    and stores results in database.

    Returns cached results if repo was already analyzed.
    """
    # Parse and validate URL
    username, repo_name = parse_repo_url(body.repo_url)
    repo_url = f"https://github.com/{username}/{repo_name}"
    
    with Session(engine) as session:
        # Get or create user and repo
        user = get_or_create_user(session, username)
        repo = get_or_create_repo(session, user, repo_url, repo_name)
        session.commit()  # Commit early to release write lock before long-running operations
        session.refresh(repo)  # Reload repo with relationships after commit

        # Check if already analyzed
        if repo.repo_analysis:
            return build_analysis_response(repo, repo.repo_analysis)

        # Clone repository
        with tempfile.TemporaryDirectory() as temp_dir:
            try:
                extracted_data, ai_slop_result, bad_practices_result, code_quality_result, verdict = run_analysis_pipeline(repo_url)
                
                repo_analysis = save_analysis_results(
                    session, repo.id, extracted_data, ai_slop_result, bad_practices_result, code_quality_result, verdict
                )
                session.commit()
                session.refresh(repo_analysis)
                session.refresh(repo)

                return build_analysis_response(repo, repo_analysis)
            except Exception as e:
                logger.error(f"Analysis failed for {repo_url}: {e}")
                raise HTTPException(status_code=500, detail=str(e))


@app.get("/repo/{repo_id}")
@limiter.limit("30/minute")
def get_repo_analysis(request: Request, repo_id: int):
    """Get analysis results for a specific repository by ID."""
    with Session(engine) as session:
        repo = session.query(Repo).filter(Repo.id == repo_id).first()

        if not repo:
            raise HTTPException(status_code=404, detail="Repository not found")

        if not repo.repo_analysis:
            raise HTTPException(status_code=400, detail="Repository has not been analyzed yet")

        return build_analysis_response(repo, repo.repo_analysis)


@app.delete("/repo/{repo_id}")
@limiter.limit("5/minute")
def delete_repo_analysis(request: Request, repo_id: int):
    """Delete analysis and evaluation results for a repository (allows re-analysis)."""
    with Session(engine) as session:
        repo = session.query(Repo).filter(Repo.id == repo_id).first()

        if not repo:
            raise HTTPException(status_code=404, detail="Repository not found")

        deleted_count = 0
        if repo.repo_analysis:
            session.delete(repo.repo_analysis)
            deleted_count += 1
        if repo.repo_evaluation:
            session.delete(repo.repo_evaluation)
            deleted_count += 1

        if deleted_count > 0:
            session.commit()

        return {"status": "deleted", "repo_id": repo_id, "deleted_items": deleted_count}


@app.post("/batch/upload", response_model=BatchUploadResponse)
@limiter.limit("5/minute")
async def upload_batch(
    request: Request,
    background_tasks: BackgroundTasks,
    resumes: list[UploadFile] = File(...),
    priorities: str = Form(None), # Passed as comma-separated string or JSON
    use_generic_questions: str = Form(None),
):
    """
    Upload a batch of resumes for background processing.
    """
    # 1. Validation: Max 10 files
    if len(resumes) > 10:
        raise HTTPException(status_code=400, detail="Maximum 10 files allowed per batch.")
    
    # 2. Validation: Extensions
    for resume in resumes:
        ext = Path(resume.filename).suffix.lower()
        if ext not in [".pdf", ".docx"]:
            raise HTTPException(status_code=400, detail=f"Unsupported file type: {ext}. Only .pdf and .docx allowed.")

    # Parse priorities if provided
    priority_list = DEFAULT_PRIORITIES
    if priorities:
        try:
            # Try parsing as JSON list
            parsed = json.loads(priorities)
            if isinstance(parsed, list):
                priority_list = [p for p in parsed if p in VALID_PRIORITIES]
        except json.JSONDecodeError:
            # Try comma-separated
            priority_list = [p.strip() for p in priorities.split(",") if p.strip() in VALID_PRIORITIES]
    
    if not priority_list:
        priority_list = DEFAULT_PRIORITIES

    generic_questions_flag = use_generic_questions and use_generic_questions.lower() == "true"

    import uuid
    batch_id = str(uuid.uuid4())

    with Session(engine) as session:
        # 3. Create BatchJob
        batch_job = BatchJob(
            id=batch_id,
            total_items=len(resumes),
            status="pending",
            priorities=json.dumps(priority_list),
            use_generic_questions=generic_questions_flag,
        )
        session.add(batch_job)
        
        # 4. Create BatchItems
        for i, resume in enumerate(resumes):
            content = await resume.read()
            item = BatchItem(
                batch_job_id=batch_id,
                position=i,
                filename=resume.filename,
                file_bytes=content,
                file_ext=Path(resume.filename).suffix.lower(),
                status="pending"
            )
            session.add(item)
            
        session.commit()
        
        # 5. Kick off background task
        background_tasks.add_task(process_batch, batch_id, priority_list, generic_questions_flag)
        
        return BatchUploadResponse(batch_id=batch_id)


@app.get("/batch/{batch_id}/status", response_model=BatchStatusResponse)
@limiter.limit("60/minute")
def get_batch_status(request: Request, batch_id: str):
    """
    Get the status of a batch job and all its items.
    """
    with Session(engine) as session:
        batch_job = session.query(BatchJob).filter(BatchJob.id == batch_id).first()
        if not batch_job:
            raise HTTPException(status_code=404, detail="Batch job not found")
            
        completed_count = session.query(BatchItem).filter(
            BatchItem.batch_job_id == batch_id, 
            BatchItem.status.in_(["completed", "error"])
        ).count()
        
        item_statuses = []
        for item in batch_job.items:
            verdict = None
            standout_features = []
            overall_score = None

            if item.status == "completed" and item.repo:
                if item.repo.repo_analysis:
                    verdict = Verdict(
                        type=item.repo.repo_analysis.verdict_type,
                        confidence=item.repo.repo_analysis.verdict_confidence
                    )
                if item.repo.repo_evaluation:
                    standout_features = json.loads(item.repo.repo_evaluation.standout_features)

                # Compute overall score (0-100)
                if item.repo.repo_analysis and item.repo.repo_evaluation:
                    score = 0
                    # solves_real_problem: 35 points
                    bv = json.loads(item.repo.repo_evaluation.business_value)
                    if bv.get("solves_real_problem", False):
                        score += 35
                    # code_quality: 0-25 points
                    score += round(item.repo.repo_analysis.code_quality_score / 100 * 25)
                    # standout_features: 20 points if non-empty
                    if standout_features:
                        score += 20
                    # AI bonus: 20 points if ai_slop_score < 50
                    if item.repo.repo_analysis.ai_slop_score < 50:
                        score += 20
                    overall_score = score

            item_statuses.append(BatchItemStatus(
                id=item.id,
                position=item.position,
                filename=item.filename,
                candidate_name=item.candidate_name or "Unknown",
                repo_url=item.repo_url,
                status=item.status,
                error_message=item.error_message,
                repo_id=item.repo_id,
                verdict=verdict,
                standout_features=standout_features,
                overall_score=overall_score,
            ))
            
        return BatchStatusResponse(
            batch_id=batch_job.id,
            created_at=batch_job.created_at,
            total_items=batch_job.total_items,
            completed_items=completed_count,
            status=batch_job.status,
            items=item_statuses
        )


@app.on_event("startup")
async def startup_event():
    """
    Resume any pending or running batch jobs on startup.
    """
    with Session(engine) as session:
        # Find all jobs that aren't completed
        unfinished_jobs = session.query(BatchJob).filter(BatchJob.status.in_(["pending", "running"])).all()
        for job in unfinished_jobs:
            logger.info(f"Resuming batch job {job.id} on startup")
            priorities = json.loads(job.priorities) if job.priorities else DEFAULT_PRIORITIES
            asyncio.create_task(process_batch(job.id, priorities, job.use_generic_questions))


@app.post("/analyze-stream")
@limiter.limit("10/minute")
def analyze_repo_stream(request: Request, body: AnalyzeRequest):
    """
    SSE streaming endpoint for progressive repository analysis.

    Streams 4 event types in order:
    - analysis: Static analysis results (verdict, scores, findings)
    - evaluation: LLM business value + standout features + rejection status
    - questions: LLM interview questions
    - done: Completion signal

    Falls back gracefully if LLM calls fail — frontend appears errorless.
    """

    # Resolve priorities: filter to valid keys, fall back to all five
    if body.priorities:
        priorities = [p for p in body.priorities if p in VALID_PRIORITIES]
        if not priorities:
            priorities = DEFAULT_PRIORITIES
    else:
        priorities = DEFAULT_PRIORITIES
    logger.info(f"Priorities for {body.repo_url}: {priorities}")

    def generate():
        # 1. Parse and validate URL
        try:
            username, repo_name = parse_repo_url(body.repo_url)
        except HTTPException as e:
            yield f"event: error\ndata: {json.dumps({'message': e.detail, 'step': 'validation'})}\n\n"
            return

        repo_url = f"https://github.com/{username}/{repo_name}"

        try:
            with Session(engine) as session:
                # 2. Get or create user + repo
                user = get_or_create_user(session, username)
                repo = get_or_create_repo(session, user, repo_url, repo_name)
                session.commit()
                session.refresh(repo)

                # 3. Full cache — stream everything immediately
                if repo.repo_analysis and repo.repo_evaluation:
                    yield f"event: analysis\ndata: {build_analysis_event_json(repo, repo.repo_analysis)}\n\n"
                    yield f"event: evaluation\ndata: {build_evaluation_event_json(repo.repo_evaluation)}\n\n"
                    yield f"event: questions\ndata: {build_questions_event_json(repo.repo_evaluation)}\n\n"
                    yield f"event: done\ndata: {{}}\n\n"
                    return

                has_cached_analysis = repo.repo_analysis is not None

                # 4. Stream cached analysis immediately if available
                if has_cached_analysis:
                    yield f"event: analysis\ndata: {build_analysis_event_json(repo, repo.repo_analysis)}\n\n"

                # 5. Clone and extract (needed for analysis and/or LLM context)
                try:
                    with tempfile.TemporaryDirectory() as temp_dir:
                        clone_result = subprocess.run(
                            ["git", "clone", "--depth", "100", repo_url, temp_dir],
                            capture_output=True, text=True, encoding="utf-8",
                            errors="ignore", timeout=120,
                        )
                        if clone_result.returncode != 0:
                            logger.error(f"Clone failed for {repo_url}: {clone_result.stderr}")
                            if has_cached_analysis:
                                yield f"event: evaluation\ndata: {json.dumps({'business_value': None, 'standout_features': [], 'is_rejected': False, 'rejection_reason': None})}\n\n"
                                yield f"event: questions\ndata: {json.dumps({'interview_questions': [], 'error': 'No questions generated, an error occurred.'})}\n\n"
                                yield f"event: done\ndata: {{}}\n\n"
                            else:
                                yield f"event: error\ndata: {json.dumps({'message': 'Failed to clone repository. Please check the URL and try again.', 'step': 'clone'})}\n\n"
                            return

                        # Extract data — stores file contents in memory
                        extracted_data = extract_repo_data(temp_dir)
                        features = extract_features(extracted_data)
                    # Temp dir cleaned up here; extracted_data is all in memory

                except subprocess.TimeoutExpired:
                    logger.error(f"Clone timed out for {repo_url}")
                    if has_cached_analysis:
                        yield f"event: evaluation\ndata: {json.dumps({'business_value': None, 'standout_features': [], 'is_rejected': False, 'rejection_reason': None})}\n\n"
                        yield f"event: questions\ndata: {json.dumps({'interview_questions': [], 'error': 'No questions generated, an error occurred.'})}\n\n"
                        yield f"event: done\ndata: {{}}\n\n"
                    else:
                        yield f"event: error\ndata: {json.dumps({'message': 'Repository clone timed out.', 'step': 'clone'})}\n\n"
                    return

                # 6. Run analyzers
                ai_slop_result = analyze_ai_slop(extracted_data, features)
                bad_practices_result = analyze_bad_practices(extracted_data)
                code_quality_result = analyze_code_quality(extracted_data)

                # 7. Save and stream analysis (if not already cached)
                if not has_cached_analysis:
                    if extracted_data.languages:
                        repo.languages = json.dumps(extracted_data.languages)

                    verdict = compute_verdict(
                        ai_slop_result.score,
                        bad_practices_result.score,
                        code_quality_result.score,
                    )

                    files_analyzed = [
                        {
                            "path": path,
                            "importance_score": min(max(score, 0), 100),
                            "loc": len(extracted_data.files.get(path, "").split("\n")),
                        }
                        for path, score in sorted(
                            extracted_data.file_importance.items(),
                            key=lambda x: x[1],
                            reverse=True,
                        )[:15]
                    ]

                    repo_analysis = RepoAnalysis(
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
                    session.add(repo_analysis)
                    session.commit()
                    session.refresh(repo_analysis)
                    session.refresh(repo)

                    yield f"event: analysis\ndata: {build_analysis_event_json(repo, repo_analysis)}\n\n"

                # === LLM PHASE ===

                # 8. LLM Call 1: Business value + standout features
                bv, sf, ir, rr, iq_full = run_evaluation_pipeline(
                    repo_url, repo_name,
                    ai_slop_result, bad_practices_result, code_quality_result,
                    extracted_data,
                    priorities=priorities,
                    skip_questions=body.skip_questions,
                )

                yield f"event: evaluation\ndata: {json.dumps({'business_value': bv, 'standout_features': sf, 'is_rejected': ir, 'rejection_reason': rr})}\n\n"

                # 10. LLM Call 2: Interview questions (already returned from evaluation pipeline in our new service)
                yield f"event: questions\ndata: {json.dumps({'interview_questions': iq_full})}\n\n"

                # 11. Save evaluation to DB
                if bv:
                    try:
                        save_evaluation_results(session, repo.id, bv, sf, ir, rr, iq_full)
                    except Exception as e:
                        logger.error(f"Failed to save evaluation for {repo_url}: {e}")

                yield f"event: done\ndata: {{}}\n\n"

        except Exception as e:
            logger.error(f"Stream error for {body.repo_url}: {e}")
            yield f"event: error\ndata: {json.dumps({'message': 'An unexpected error occurred.', 'step': 'unknown'})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/compatibility", response_model=CompatibilityResponse)
@limiter.limit("10/minute")
def check_compatibility(request: Request, body: CompatibilityRequest):
    """
    Compute compatibility between two scan results.
    Accepts pre-computed analysis + evaluation dicts from the frontend.
    Returns rule-based score + LLM narrative.
    """
    score, score_label, callouts = compute_compatibility(
        body.analysis_a, body.evaluation_a,
        body.analysis_b, body.evaluation_b,
    )

    # LLM narrative (graceful fallback)
    narrative = ""
    try:
        system_prompt, user_prompt = build_compatibility_prompt(
            body.analysis_a, body.evaluation_a,
            body.analysis_b, body.evaluation_b,
            score, score_label, callouts,
            body.hackathon_context,
        )

        gemini_api_key = os.getenv("GEMINI_API_KEY")
        if gemini_api_key:
            from google import genai
            client = genai.Client(api_key=gemini_api_key)
            response = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=[
                    {"role": "user", "parts": [{"text": f"{system_prompt}\n\n{user_prompt}"}]},
                ],
                config={"http_options": {"timeout": 30_000}, "temperature": 0.3},
            )
            narrative = response.text.strip()
    except Exception as e:
        logger.warning(f"Compatibility narrative LLM call failed: {e}")
        # Fallback to template
        narrative = f"{score_label}. These two developers bring different strengths to the table."

    return CompatibilityResponse(
        score=score,
        score_label=score_label,
        narrative=narrative,
        callouts=[CompatibilityCallout(type=c["type"], message=c["message"]) for c in callouts],
    )


@app.get("/resolve-username")
@limiter.limit("20/minute")
def resolve_username(request: Request, username: str):
    """
    Resolves a GitHub username to their best repository URL.
    Uses pinned repos (GraphQL) first, falls back to most recently pushed repo (REST).
    """
    from v2.github_resolver import _fetch_pinned_repos
    import os

    if not username or "/" in username:
        raise HTTPException(status_code=400, detail="Invalid username")

    github_token = os.getenv("GITHUB_TOKEN")
    headers = {}
    if github_token:
        headers["Authorization"] = f"Bearer {github_token}"

    # Try pinned repos first
    pinned = _fetch_pinned_repos(username, headers)
    if pinned:
        return {"repo_url": pinned[0]["url"]}

    # Fallback to most recently pushed repo
    import requests as http_requests
    try:
        resp = http_requests.get(
            f"https://api.github.com/users/{username}/repos?sort=pushed&per_page=1",
            headers=headers,
        )
        if resp.status_code == 200:
            repos = resp.json()
            if repos:
                return {"repo_url": repos[0]["html_url"]}
    except Exception as e:
        logger.warning(f"GitHub REST fallback failed for {username}: {e}")

    raise HTTPException(status_code=404, detail=f"No repositories found for user '{username}'")
