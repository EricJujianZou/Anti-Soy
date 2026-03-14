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
from sqlalchemy.orm import Session, joinedload

logger = logging.getLogger(__name__)

from models import Base, User, Repo, RepoAnalysis, RepoEvaluation, BatchJob, BatchItem, BatchItemRepo

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
    CandidateRepoDetail,
    CandidateDetailResponse,
    TechStackLanguage,
    CompatibilityRequest,
    CompatibilityResponse,
    CompatibilityCallout,
    ScoringConfig,
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
    get_or_create_repo,
    run_questions_from_db,
    run_multi_repo_questions,
    compute_composite_score,
    compute_candidate_score,
    compute_tech_match_penalty,
    aggregate_tech_stack,
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
    expose_headers=["X-Resume-Count"],
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


def build_evaluate_response(repo: Repo, repo_evaluation: RepoEvaluation) -> EvaluateResponse:
    """Build EvaluateResponse from database entry."""
    return EvaluateResponse(
        repo_id=repo.id,
        repo_url=repo.github_link,
        is_rejected=bool(repo_evaluation.is_rejected),
        rejection_reason=repo_evaluation.rejection_reason,
        business_value=json.loads(repo_evaluation.business_value),
        standout_features=json.loads(repo_evaluation.standout_features),
        interview_questions=json.loads(repo_evaluation.interview_questions),
    )


def _load_scoring_config(batch_job: BatchJob) -> dict:
    """Load ScoringConfig dict from BatchJob, falling back to defaults for old batches."""
    if batch_job and batch_job.scoring_config:
        try:
            return json.loads(batch_job.scoring_config)
        except Exception:
            pass
    return ScoringConfig().model_dump()


def _compute_overall_score(repo_analysis: RepoAnalysis, repo_evaluation: RepoEvaluation) -> int:
    """
    Legacy score used by /analyze and /analyze-stream (single-repo flow).
    DO NOT DELETE — still used by the non-batch pipeline.
    """
    score = 0
    bv = json.loads(repo_evaluation.business_value)
    if bv.get("solves_real_problem", False):
        score += 35
    score += round(repo_analysis.code_quality_score / 100 * 25)
    sf = json.loads(repo_evaluation.standout_features)
    if sf:
        score += 20
    if repo_analysis.ai_slop_score < 50:
        score += 20
    return score


def _compute_repo_composite(repo_analysis: RepoAnalysis, repo_evaluation: RepoEvaluation, scoring_config_dict: dict) -> int:
    """
    Compute composite score for a single repo using the batch's scoring config.
    Falls back to legacy scoring for old batches (no scoring_config on BatchJob).
    """
    bv = {}
    if repo_evaluation and repo_evaluation.business_value:
        try:
            bv = json.loads(repo_evaluation.business_value)
        except Exception:
            pass

    originality_score = bv.get("originality_score", 0.5)

    bad_practices_findings = []
    if repo_analysis and repo_analysis.bad_practices_data:
        try:
            bp_data = json.loads(repo_analysis.bad_practices_data)
            bad_practices_findings = bp_data.get("findings", [])
        except Exception:
            pass

    # Tech match penalty: not recomputed at read time (no stored dependencies here),
    # so we pass 0.0 — penalty was already factored into the per-repo score during processing.
    return compute_composite_score(
        ai_slop_score=repo_analysis.ai_slop_score,
        bad_practices_score=repo_analysis.bad_practices_score,
        code_quality_score=repo_analysis.code_quality_score,
        originality_score=originality_score,
        bad_practices_findings=bad_practices_findings,
        scoring_config=scoring_config_dict,
        shipped_to_prod=False,  # Not re-detected at read time; safe default
        tech_match_penalty=0.0,
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


def build_questions_event_json(repo_evaluation: RepoEvaluation, repo_id: int) -> str:
    """Build JSON string for the 'questions' SSE event."""
    iq = json.loads(repo_evaluation.interview_questions) if repo_evaluation.interview_questions else []
    event = {
        "interview_questions": iq,
        "repo_id": repo_id,
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
    priorities: str = Form(None),       # Legacy: comma-separated or JSON. Kept for backward compat.
    scoring_config: str = Form(None),   # New: JSON-encoded ScoringConfig object.
    use_generic_questions: str = Form(None),
):
    """
    Upload a batch of resumes for background processing.
    If scoring_config is provided it takes precedence over priorities.
    priorities is kept for backward compatibility with old clients.
    """
    # 1. Validation: Max 10 files
    if len(resumes) > 10:
        raise HTTPException(status_code=400, detail="Maximum 10 files allowed per batch.")

    # 2. Validation: Extensions
    for resume in resumes:
        ext = Path(resume.filename).suffix.lower()
        if ext not in [".pdf", ".docx"]:
            raise HTTPException(status_code=400, detail=f"Unsupported file type: {ext}. Only .pdf and .docx allowed.")

    # Parse legacy priorities (still used by the single-repo /analyze-stream flow)
    priority_list = DEFAULT_PRIORITIES
    if priorities:
        try:
            parsed = json.loads(priorities)
            if isinstance(parsed, list):
                priority_list = [p for p in parsed if p in VALID_PRIORITIES]
        except json.JSONDecodeError:
            priority_list = [p.strip() for p in priorities.split(",") if p.strip() in VALID_PRIORITIES]
    if not priority_list:
        priority_list = DEFAULT_PRIORITIES

    # Parse scoring_config — takes precedence over priorities if valid
    scoring_config_dict = None
    if scoring_config:
        try:
            from pydantic import ValidationError
            parsed_sc = json.loads(scoring_config)
            ScoringConfig(**parsed_sc)  # validate
            scoring_config_dict = parsed_sc
        except Exception:
            scoring_config_dict = None
    if scoring_config_dict is None:
        scoring_config_dict = ScoringConfig().model_dump()

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
            scoring_config=json.dumps(scoring_config_dict),
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

        # 5. Kick off background task (scoring_config is read from BatchJob inside the task)
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

        scoring_config_dict = _load_scoring_config(batch_job)
        use_composite = bool(batch_job.scoring_config)  # Only use composite for new batches

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

                # Compute overall score — composite for new batches, legacy for old ones
                if item.repo.repo_analysis and item.repo.repo_evaluation:
                    if use_composite:
                        # For the list view, compute composite across all repos for this candidate
                        batch_repos = (
                            session.query(BatchItemRepo)
                            .filter(BatchItemRepo.batch_item_id == item.id)
                            .all()
                        )
                        repo_ids = [br.repo_id for br in batch_repos] if batch_repos else ([item.repo_id] if item.repo_id else [])
                        all_repos = (
                            session.query(Repo)
                            .options(joinedload(Repo.repo_analysis), joinedload(Repo.repo_evaluation))
                            .filter(Repo.id.in_(repo_ids))
                            .all()
                        ) if len(repo_ids) > 1 else [item.repo]

                        repo_scores = []
                        for r in all_repos:
                            if r.repo_analysis and r.repo_evaluation:
                                repo_scores.append(_compute_repo_composite(r.repo_analysis, r.repo_evaluation, scoring_config_dict))
                        overall_score = compute_candidate_score(repo_scores) if repo_scores else None
                    else:
                        overall_score = _compute_overall_score(item.repo.repo_analysis, item.repo.repo_evaluation)

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


@app.get("/batch/{batch_id}/items/{item_id}", response_model=CandidateDetailResponse)
@limiter.limit("30/minute")
def get_candidate_detail(request: Request, batch_id: str, item_id: int):
    """
    Get full analysis + evaluation for every repo analyzed for a batch candidate.
    Falls back to item.repo_id for old items that pre-date the BatchItemRepo join table.
    """
    with Session(engine) as session:
        item = session.query(BatchItem).filter(
            BatchItem.id == item_id,
            BatchItem.batch_job_id == batch_id,
        ).first()
        if not item:
            raise HTTPException(status_code=404, detail="Candidate not found in this batch")
        if item.status != "completed":
            raise HTTPException(status_code=400, detail=f"Candidate analysis not yet complete (status: {item.status})")

        # Collect repo IDs — join table preferred; fall back to primary repo for legacy items.
        batch_repos = (
            session.query(BatchItemRepo)
            .filter(BatchItemRepo.batch_item_id == item.id)
            .order_by(BatchItemRepo.position)
            .all()
        )
        repo_ids = [br.repo_id for br in batch_repos] if batch_repos else ([item.repo_id] if item.repo_id else [])

        if not repo_ids:
            raise HTTPException(status_code=404, detail="No analyzed repositories found for this candidate")

        # Single query with eager-loaded relationships — eliminates N+1 lazy-load round trips
        repos_map = {
            r.id: r
            for r in session.query(Repo)
            .options(
                joinedload(Repo.repo_analysis),
                joinedload(Repo.repo_evaluation),
                joinedload(Repo.user),
            )
            .filter(Repo.id.in_(repo_ids))
            .all()
        }

        # Load scoring config for this batch
        batch_job_for_detail = session.query(BatchJob).filter(BatchJob.id == batch_id).first()
        scoring_config_dict = _load_scoring_config(batch_job_for_detail)
        use_composite = bool(batch_job_for_detail and batch_job_for_detail.scoring_config)

        repo_details: list[CandidateRepoDetail] = []
        scores: list[int] = []
        repo_tech_relevance: list[float] = []
        tech_repos_for_aggregation: list[dict] = []

        w_ai = scoring_config_dict.get("weights", {}).get("ai_detection", 0.7)

        for repo_id in repo_ids:
            repo = repos_map.get(repo_id)
            if not repo or not repo.repo_analysis or not repo.repo_evaluation:
                continue

            if use_composite:
                score = _compute_repo_composite(repo.repo_analysis, repo.repo_evaluation, scoring_config_dict)
                # Compute tech relevance for weighted candidate average
                # tech_match_penalty not re-derived at read time (no deps stored), default to 0 for relevance
                tech_penalty = 0.0
                ai_slop = repo.repo_analysis.ai_slop_score
                base_relevance = 1.0 - (tech_penalty / 100)
                ai_discount = max(0.0, 1.0 - (ai_slop / 100) * w_ai)
                repo_tech_relevance.append(base_relevance * ai_discount)
            else:
                score = _compute_overall_score(repo.repo_analysis, repo.repo_evaluation)

            scores.append(score)
            repo_details.append(CandidateRepoDetail(
                repo_id=repo.id,
                repo_url=repo.github_link,
                repo_name=repo.repo_name,
                overall_score=score,
                analysis=build_analysis_response(repo, repo.repo_analysis),
                evaluation=build_evaluate_response(repo, repo.repo_evaluation),
            ))

            # Collect data for tech stack aggregation
            languages = {}
            if repo.languages:
                try:
                    languages = json.loads(repo.languages)
                except Exception:
                    pass
            tech_repos_for_aggregation.append({
                "repo_name": repo.repo_name,
                "languages": languages,
                "ai_slop_score": repo.repo_analysis.ai_slop_score,
            })

        if not repo_details:
            raise HTTPException(status_code=404, detail="No completed repo analyses found for this candidate")

        if use_composite and scores:
            overall_score = compute_candidate_score(scores, repo_tech_relevance if repo_tech_relevance else None)
        else:
            overall_score = round(sum(scores) / len(scores))

        # Build tech stack breakdown
        tech_stack_breakdown = None
        if tech_repos_for_aggregation:
            raw_breakdown = aggregate_tech_stack(tech_repos_for_aggregation)
            tech_stack_breakdown = [TechStackLanguage(**entry) for entry in raw_breakdown]

        # Questions cached on the primary User — candidate-scoped, persists across batch runs
        interview_questions = None
        primary_repo = repos_map.get(repo_ids[0]) if repo_ids else None
        if primary_repo and primary_repo.user and primary_repo.user.interview_questions:
            interview_questions = json.loads(primary_repo.user.interview_questions)

        return CandidateDetailResponse(
            item_id=item.id,
            candidate_name=item.candidate_name or "Unknown",
            github_profile_url=item.github_profile_url,
            overall_score=overall_score,
            repos=repo_details,
            interview_questions=interview_questions,
            tech_stack_breakdown=tech_stack_breakdown,
        )


@app.post("/batch/{batch_id}/items/{item_id}/interview-questions")
@limiter.limit("10/minute")
def generate_batch_interview_questions(request: Request, batch_id: str, item_id: int):
    """
    Generate (or return cached) aggregated interview questions for all repos of a batch candidate.
    One LLM call across all repos — saves result to User.interview_questions (candidate-scoped cache).
    """
    with Session(engine) as session:
        item = session.query(BatchItem).filter(
            BatchItem.id == item_id,
            BatchItem.batch_job_id == batch_id,
        ).first()
        if not item:
            raise HTTPException(status_code=404, detail="Candidate not found in this batch")
        if item.status != "completed":
            raise HTTPException(status_code=400, detail="Candidate analysis not yet complete")

        batch_job = session.query(BatchJob).filter(BatchJob.id == batch_id).first()
        priorities = json.loads(batch_job.priorities) if batch_job and batch_job.priorities else DEFAULT_PRIORITIES

        batch_repos = (
            session.query(BatchItemRepo)
            .filter(BatchItemRepo.batch_item_id == item.id)
            .order_by(BatchItemRepo.position)
            .all()
        )
        repo_ids = [br.repo_id for br in batch_repos] if batch_repos else ([item.repo_id] if item.repo_id else [])
        if not repo_ids:
            raise HTTPException(status_code=404, detail="No repos found for this candidate")

        repos = (
            session.query(Repo)
            .options(joinedload(Repo.repo_analysis), joinedload(Repo.user))
            .filter(Repo.id.in_(repo_ids))
            .all()
        )
        repos_map = {r.id: r for r in repos}

        # Questions are cached on the primary User (position=0 repo owner) — candidate-scoped
        primary_repo = repos_map.get(repo_ids[0]) if repos_map.get(repo_ids[0]) else None
        primary_user = primary_repo.user if primary_repo else None
        if primary_user and primary_user.interview_questions:
            return {"interview_questions": json.loads(primary_user.interview_questions)}

        repos_data = []
        for repo_id in repo_ids:
            repo = repos_map.get(repo_id)
            if not repo or not repo.repo_analysis:
                continue
            bp_data = json.loads(repo.repo_analysis.bad_practices_data)
            cq_data = json.loads(repo.repo_analysis.code_quality_data)
            repos_data.append({
                "repo_url": repo.github_link,
                "repo_name": repo.repo_name,
                "ai_score": repo.repo_analysis.ai_slop_score,
                "bad_practices_score": repo.repo_analysis.bad_practices_score,
                "quality_score": repo.repo_analysis.code_quality_score,
                "bad_practices_findings": bp_data.get("findings", []),
                "code_quality_findings": cq_data.get("findings", []),
            })

        if not repos_data:
            raise HTTPException(status_code=404, detail="No analyzed repos found for this candidate")

        questions = run_multi_repo_questions(repos_data, priorities)
        if primary_user:
            primary_user.interview_questions = json.dumps(questions)
            session.commit()

        return {"interview_questions": questions}


@app.post("/repo/{repo_id}/interview-questions")
@limiter.limit("10/minute")
def generate_repo_interview_questions(request: Request, repo_id: int):
    """
    Generate (or return cached) interview questions for a single repository.
    Saves result to RepoEvaluation.interview_questions.
    """
    with Session(engine) as session:
        repo = (
            session.query(Repo)
            .options(
                joinedload(Repo.repo_analysis),
                joinedload(Repo.repo_evaluation),
                joinedload(Repo.user),
            )
            .filter(Repo.id == repo_id)
            .first()
        )
        if not repo or not repo.repo_analysis:
            raise HTTPException(status_code=404, detail="Repository not found or not yet analyzed")

        # Return cached if already generated (non-empty list)
        if repo.repo_evaluation and repo.repo_evaluation.interview_questions:
            existing = json.loads(repo.repo_evaluation.interview_questions)
            if existing:
                return {"interview_questions": existing, "repo_id": repo_id}

        questions = run_questions_from_db(repo, repo.repo_analysis)

        if repo.repo_evaluation:
            repo.repo_evaluation.interview_questions = json.dumps(questions)
            session.commit()

        return {"interview_questions": questions, "repo_id": repo_id}


@app.on_event("startup")
async def startup_event():
    with Session(engine) as session:
        # Find all jobs that aren't completed
        unfinished_jobs = session.query(BatchJob).filter(BatchJob.status.in_(["pending", "running"])).all()
        for job in unfinished_jobs:
            logger.info(f"Resuming batch job {job.id} on startup (scoring_config present: {bool(job.scoring_config)})")
            priorities = json.loads(job.priorities) if job.priorities else DEFAULT_PRIORITIES
            # scoring_config is read inside process_batch from the BatchJob record — no arg needed
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
                    yield f"event: questions\ndata: {build_questions_event_json(repo.repo_evaluation, repo.id)}\n\n"
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

                # 8. LLM Call 1: Business value + standout features (questions always skipped — generated on demand)
                bv, sf, ir, rr, iq_full = run_evaluation_pipeline(
                    repo_url, repo_name,
                    ai_slop_result, bad_practices_result, code_quality_result,
                    extracted_data,
                    priorities=priorities,
                    skip_questions=True,
                )

                yield f"event: evaluation\ndata: {json.dumps({'business_value': bv, 'standout_features': sf, 'is_rejected': ir, 'rejection_reason': rr})}\n\n"

                # Send questions event with empty list + repo_id so frontend can show Generate button
                yield f"event: questions\ndata: {json.dumps({'interview_questions': [], 'repo_id': repo.id})}\n\n"

                # 11. Save evaluation to DB (no interview questions — generated on demand)
                if bv:
                    try:
                        save_evaluation_results(session, repo.id, bv, sf, ir, rr, [])
                        session.commit()
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


@app.post("/amalgam/test")
async def test_amalgam_parser(pdf: UploadFile = File(...)):
    """
    Test endpoint for the amalgam PDF parser.
    Upload a multi-resume PDF; returns a zip of the extracted individual resumes.
    """
    import zipfile
    import io
    from v2.amalgam_parser import crack_amalgam_pdf

    if not pdf.filename or not pdf.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")

    contents = await pdf.read()

    with tempfile.TemporaryDirectory() as input_dir, tempfile.TemporaryDirectory() as output_dir:
        input_path = Path(input_dir) / "amalgam.pdf"
        output_path = Path(output_dir)

        input_path.write_bytes(contents)

        try:
            await crack_amalgam_pdf(input_path, output_path)
        except Exception as e:
            logger.exception("Amalgam parser failed")
            raise HTTPException(status_code=500, detail=f"Parser error: {e}")

        output_files = list(output_path.glob("*.pdf"))

        if not output_files:
            raise HTTPException(status_code=422, detail="No resumes were extracted from the PDF.")

        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            for f in sorted(output_files):
                zf.write(f, arcname=f.name)
        zip_buffer.seek(0)

        from fastapi.responses import Response
        return Response(
            content=zip_buffer.read(),
            media_type="application/zip",
            headers={"Content-Disposition": f"attachment; filename=extracted_resumes.zip", "X-Resume-Count": str(len(output_files))},
        )
