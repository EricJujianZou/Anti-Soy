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
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

from models import Base, User, Repo, RepoAnalysis, RepoEvaluation

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
)

load_dotenv()

# Database setup
BASE_DIR = Path(__file__).resolve().parent
DATABASE_PATH = BASE_DIR / "database.db"
engine = create_engine(
    f"sqlite:///{DATABASE_PATH}",
    connect_args={
        "check_same_thread": False,
        "timeout": 30,  # Wait up to 30 seconds for lock to be released
    },
    pool_pre_ping=True,  # Verify connections before using
    pool_size=5,  # Connection pool size
    max_overflow=10,  # Allow up to 10 additional connections
)

# Enable WAL mode for better concurrency
with engine.connect() as conn:
    conn.execute(text("PRAGMA journal_mode=WAL"))
    conn.execute(text("PRAGMA busy_timeout=30000"))  # 30 second timeout
    conn.commit()

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
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type"],
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


def get_or_create_user(session: Session, username: str) -> User:
    """Get existing user or create new one. Handles concurrent inserts."""
    user = session.query(User).filter(User.username == username).first()

    if not user:
        try:
            user = User(
                username=username,
                github_link=f"https://github.com/{username}",
            )
            session.add(user)
            session.flush()
        except IntegrityError:
            # Another concurrent request created it - rollback and query again
            session.rollback()
            user = session.query(User).filter(User.username == username).first()
            if not user:
                raise  # Re-raise if still not found (shouldn't happen)

    return user


def get_or_create_repo(session: Session, user: User, repo_url: str, repo_name: str) -> Repo:
    """Get existing repo or create new one. Handles concurrent inserts."""
    repo = session.query(Repo).filter(Repo.github_link == repo_url).first()

    if not repo:
        try:
            repo = Repo(
                user_id=user.id,
                github_link=repo_url,
                repo_name=repo_name,
                stars=0,
                languages="{}",
            )
            session.add(repo)
            session.flush()
        except IntegrityError:
            # Another concurrent request created it - rollback and query again
            session.rollback()
            repo = session.query(Repo).filter(Repo.github_link == repo_url).first()
            if not repo:
                raise  # Re-raise if still not found (shouldn't happen)

    return repo


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
# LLM HELPER FUNCTIONS (split for SSE streaming)
# =============================================================================

def _build_findings_context(bad_practices_result, code_quality_result):
    """Build findings context list for LLM prompts."""
    findings_context = []
    for finding in bad_practices_result.findings[:5]:
        findings_context.append({
            "category": "Bad Practice", "type": finding.type, "severity": finding.severity,
            "file": finding.file, "line": finding.line, "snippet": finding.snippet[:300],
            "explanation": finding.explanation,
        })
    for finding in code_quality_result.findings[:5]:
        findings_context.append({
            "category": "Code Quality", "type": finding.type, "severity": finding.severity,
            "file": finding.file, "line": finding.line, "snippet": finding.snippet[:300],
            "explanation": finding.explanation,
        })
    return findings_context


def call_gemini_evaluation(
    repo_url: str,
    repo_name: str,
    ai_slop_result,
    bad_practices_result,
    code_quality_result,
    extracted_data,
) -> dict | None:
    """
    LLM Call 1: Business value + standout features.
    Returns dict with keys: business_value, standout_features.
    """
    from google import genai

    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    if not GEMINI_API_KEY:
        return None

    findings_context = _build_findings_context(bad_practices_result, code_quality_result)
    file_tree = [path for path, score in sorted(
        extracted_data.file_importance.items(), key=lambda x: x[1], reverse=True
    )[:10]]

    prompt = f"""You are a senior technical interviewer evaluating a GitHub project.

REPOSITORY INFO:
- URL: {repo_url}
- Name: {repo_name}
- AI Slop Score: {ai_slop_result.score}/100 (higher = more AI-generated)
- Bad Practices Score: {bad_practices_result.score}/100 (higher = worse)
- Code Quality Score: {code_quality_result.score}/100 (higher = better)

FILE STRUCTURE:
{json.dumps(file_tree, indent=2)}

CODE FINDINGS (with file locations and code snippets):
{json.dumps(findings_context, indent=2)}

Respond with a JSON object containing TWO parts:

{{
  "business_value": {{
    "solves_real_problem": true/false,
    "project_type": "real_problem" | "tutorial" | "portfolio_demo" | "learning_exercise" | "utility_tool",
    "project_description": "One sentence describing what this project does",
    "originality_assessment": "Is this novel or just another to-do app? What makes it unique or generic?",
    "project_summary": "2-3 sentence executive summary for a hiring manager"
  }},
  "standout_features": [
    "Short punchy headline about something genuinely impressive"
  ]
}}

STANDOUT FEATURES INSTRUCTIONS:
- Return 0-3 short headlines. Most projects will have ZERO — return [] if nothing genuinely stands out.
- The bar is VERY HIGH. Compare against what's common: GPT wrappers, to-do apps, CRUD APIs, tutorial clones, portfolio demos, summary tools, productivity dashboards, chat apps, weather apps, e-commerce templates.
- Only include things that would make a startup founder say "this person built something real."
- Categories to consider (in order of importance):
  1. SOLVES A REAL USER PROBLEM (most weight): The project addresses a genuine need that isn't already solved by 100 other tools. Evidence of actual users or deployment is a strong signal.
  2. UNUSUAL TECH CHOICES: Not "uses React" — more like "built custom consensus protocol" or "implemented their own query optimizer."
  3. BEYOND-MVP ENGINEERING: Not basic error handling or rate limiting — advanced patterns like custom caching strategies, observability pipelines, zero-downtime deployment, sophisticated auth systems.
- Each headline: 1 short punchy sentence max. Written for a busy founder scanning resumes.

Return ONLY the JSON object, no other text or markdown formatting."""

    client = genai.Client(api_key=GEMINI_API_KEY)
    for attempt in range(2):
        try:
            response = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=prompt,
                config={"http_options": {"timeout": 30_000}},
            )
            response_text = response.text.strip().replace("```json", "").replace("```", "")
            return json.loads(response_text)
        except (json.JSONDecodeError, IndexError, Exception) as e:
            logger.warning(f"Gemini evaluation error (attempt {attempt + 1}/2): {e}")
            time.sleep(1)

    return None


def call_gemini_questions(
    repo_url: str,
    repo_name: str,
    ai_slop_result,
    bad_practices_result,
    code_quality_result,
    extracted_data,
) -> dict | None:
    """
    LLM Call 2: Interview questions.
    Returns dict with key: interview_questions.
    """
    from google import genai

    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    if not GEMINI_API_KEY:
        return None

    findings_context = _build_findings_context(bad_practices_result, code_quality_result)
    file_tree = [path for path, score in sorted(
        extracted_data.file_importance.items(), key=lambda x: x[1], reverse=True
    )[:10]]

    prompt = f"""You are a senior technical interviewer. Generate interview questions for a candidate about their GitHub project.

REPOSITORY INFO:
- URL: {repo_url}
- Name: {repo_name}
- AI Slop Score: {ai_slop_result.score}/100 (higher = more AI-generated)
- Bad Practices Score: {bad_practices_result.score}/100 (higher = worse)
- Code Quality Score: {code_quality_result.score}/100 (higher = better)

FILE STRUCTURE:
{json.dumps(file_tree, indent=2)}

CODE FINDINGS (with file locations and code snippets):
{json.dumps(findings_context, indent=2)}

INSTRUCTIONS FOR GENERATING QUESTIONS:

1. Focus only on what is UNIQUE, IMPRESSIVE, or UNUSUAL about this project and its issues. Ignore generic findings.
2. Questions must require the candidate to EXPLAIN THEIR OWN CODE — not recite textbook answers. The candidate should need to have actually written and understood the code to answer well.
3. Focus on DESIGN CHOICES and ARCHITECTURE — "why did you build it this way?" not "do you know the right way?"
4. Do NOT reference specific file paths or line numbers in the question text. Ask naturally, like a human interviewer who has reviewed their code.
5. Do NOT ask about AI-generated code signals, emojis, or redundant comments.

GOOD QUESTION EXAMPLE:
"Walk me through how authentication works in your API — specifically, how do you make sure a user is authorized before they can modify data?"
(This is grounded in a real finding — no auth check before DB writes — but asked naturally.)

BAD QUESTION EXAMPLE:
"Why do you have print statements instead of proper logging?"
(This is generic and can be answered by anyone who has read a Python best practices blog.)

Respond with a JSON object:

{{
  "interview_questions": [
    {{
      "question": "Natural interview question (no file:line references)",
      "based_on": "Which finding this is grounded in",
      "probes": "What skill this tests (e.g., 'security_awareness', 'system_design')",
      "category": "business_value" | "design_choice" | "code_issue" | "technical_depth"
    }}
  ]
}}

Generate 3-5 interview questions with a mix of categories. At least 1 business_value, 1 design_choice, and 1 code_issue questions.

Return ONLY the JSON object, no other text or markdown formatting."""

    client = genai.Client(api_key=GEMINI_API_KEY)
    for attempt in range(2):
        try:
            response = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=prompt,
                config={"http_options": {"timeout": 30_000}},
            )
            response_text = response.text.strip().replace("```json", "").replace("```", "")
            return json.loads(response_text)
        except (json.JSONDecodeError, IndexError, Exception) as e:
            logger.warning(f"Gemini questions error (attempt {attempt + 1}/2): {e}")
            time.sleep(1)

    return None


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
            result = subprocess.run(
                ["git", "clone", "--depth", "100", repo_url, temp_dir],
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='ignore',  # Ignore Unicode decode errors
                timeout=120,
            )
            
            if result.returncode != 0:
                logger.error(f"Clone failed for {repo_url}: {result.stderr}")
                raise HTTPException(
                    status_code=500,
                    detail="Failed to clone repository. Please check the URL and try again.",
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

            return build_analysis_response(repo, repo_analysis)


@app.post("/evaluate", response_model=EvaluateResponse)
@limiter.limit("20/minute")
def evaluate_repo(request: Request, body: EvaluateRequest):
    """
    Evaluate a repository's business value and generate comprehensive interview questions.
    This is a self-contained endpoint that clones, analyzes, and evaluates.

    This endpoint uses an LLM to:
    1. Assess if the project solves a real problem
    2. Classify the project type
    3. Generate a summary for hiring managers
    4. Create interview questions covering business value, design choices, and code issues

    Results are cached in the database.
    """
    from google import genai

    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    if not GEMINI_API_KEY:
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY not configured")

    # 1. Parse URL and set up database session
    username, repo_name = parse_repo_url(body.repo_url)
    repo_url = f"https://github.com/{username}/{repo_name}"

    with Session(engine) as session:
        user = get_or_create_user(session, username)
        repo = get_or_create_repo(session, user, repo_url, repo_name)
        session.commit()  # Commit early to release write lock before long-running operations
        session.refresh(repo)  # Reload repo with relationships after commit

        # 2. Check for cached evaluation
        if repo.repo_evaluation:
            return EvaluateResponse(
                repo_id=repo.id,
                repo_url=repo.github_link,
                is_rejected=bool(repo.repo_evaluation.is_rejected),
                rejection_reason=repo.repo_evaluation.rejection_reason,
                business_value=BusinessValue(**json.loads(repo.repo_evaluation.business_value)),
                standout_features=json.loads(repo.repo_evaluation.standout_features),
                interview_questions=[InterviewQuestion(**q) for q in json.loads(repo.repo_evaluation.interview_questions)],
            )

        # 3. Clone and Analyze (if no cached result)
        with tempfile.TemporaryDirectory() as temp_dir:
            result = subprocess.run(
                ["git", "clone", "--depth", "100", repo_url, temp_dir],
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='ignore',  # Ignore Unicode decode errors
                timeout=120,
            )
            if result.returncode != 0:
                logger.error(f"Clone failed for {repo_url}: {result.stderr}")
                raise HTTPException(status_code=500, detail="Failed to clone repository.")

            extracted_data = extract_repo_data(temp_dir)
            features = extract_features(extracted_data)
            
            # Run analyzers
            ai_slop_result = analyze_ai_slop(extracted_data, features)
            bad_practices_result = analyze_bad_practices(extracted_data)
            code_quality_result = analyze_code_quality(extracted_data)

        # 4. Rejection status determined after LLM call (based on standout features + AI slop only)
        
        # 5. Gather context for LLM
        findings_context = []
        for finding in bad_practices_result.findings[:5]:
            findings_context.append({
                "category": "Bad Practice", "type": finding.type, "severity": finding.severity,
                "file": finding.file, "line": finding.line, "snippet": finding.snippet[:300],
                "explanation": finding.explanation,
            })
        for finding in code_quality_result.findings[:5]:
             findings_context.append({
                "category": "Code Quality", "type": finding.type, "severity": finding.severity,
                "file": finding.file, "line": finding.line, "snippet": finding.snippet[:300],
                "explanation": finding.explanation,
            })

        file_tree = [path for path, score in sorted(extracted_data.file_importance.items(), key=lambda x: x[1], reverse=True)[:10]]

        prompt = f"""You are a senior technical interviewer. You're about to interview a candidate about a GitHub project they built. Your job is to generate interview questions that sound natural — like a real person across the table — while being specifically grounded in what you see in their code.

REPOSITORY INFO:
- URL: {repo_url}
- Name: {repo_name}
- AI Slop Score: {ai_slop_result.score}/100 (higher = more AI-generated)
- Bad Practices Score: {bad_practices_result.score}/100 (higher = worse)
- Code Quality Score: {code_quality_result.score}/100 (higher = better)

FILE STRUCTURE:
{json.dumps(file_tree, indent=2)}

CODE FINDINGS (with file locations and code snippets):
{json.dumps(findings_context, indent=2)}

INSTRUCTIONS FOR GENERATING QUESTIONS:

1. Focus only on what is UNIQUE, IMPRESSIVE, or UNUSUAL about this project and its issues. Ignore generic findings.
2. Questions must require the candidate to EXPLAIN THEIR OWN CODE — not recite textbook answers. The candidate should need to have actually written and understood the code to answer well.
3. Focus on DESIGN CHOICES and ARCHITECTURE — "why did you build it this way?" not "do you know the right way?"
4. Do NOT reference specific file paths or line numbers in the question text. Ask naturally, like a human interviewer who has reviewed their code.
5. Do NOT ask about AI-generated code signals, emojis, or redundant comments.

GOOD QUESTION EXAMPLE:
"Walk me through how authentication works in your API — specifically, how do you make sure a user is authorized before they can modify data?"
(This is grounded in a real finding — no auth check before DB writes — but asked naturally.)

BAD QUESTION EXAMPLE:
"Why do you have print statements instead of proper logging?"
(This is generic and can be answered by anyone who has read a Python best practices blog.)

Respond with a JSON object containing THREE parts:

{{
  "business_value": {{
    "solves_real_problem": true/false,
    "project_type": "real_problem" | "tutorial" | "portfolio_demo" | "learning_exercise" | "utility_tool",
    "project_description": "One sentence describing what this project does",
    "originality_assessment": "Is this novel or just another to-do app? What makes it unique or generic?",
    "project_summary": "2-3 sentence executive summary for a hiring manager"
  }},
  "standout_features": [
    "Short punchy headline about something genuinely impressive"
  ],
  "interview_questions": [
    {{
      "question": "Natural interview question (no file:line references)",
      "based_on": "Which finding this is grounded in",
      "probes": "What skill this tests (e.g., 'security_awareness', 'system_design')",
      "category": "business_value" | "design_choice" | "code_issue" | "technical_depth"
    }}
  ]
}}

STANDOUT FEATURES INSTRUCTIONS:
- Return 0-3 short headlines. Most projects will have ZERO — return [] if nothing genuinely stands out.
- The bar is VERY HIGH. Compare against what's common: GPT wrappers, to-do apps, CRUD APIs, tutorial clones, portfolio demos, summary tools, productivity dashboards, chat apps, weather apps, e-commerce templates.
- Only include things that would make a startup founder say "this person built something real."
- Categories to consider (in order of importance):
  1. SOLVES A REAL USER PROBLEM (most weight): The project addresses a genuine need that isn't already solved by 100 other tools. Evidence of actual users or deployment is a strong signal.
  2. UNUSUAL TECH CHOICES: Not "uses React" — more like "built custom consensus protocol" or "implemented their own query optimizer."
  3. BEYOND-MVP ENGINEERING: Not basic error handling or rate limiting — advanced patterns like custom caching strategies, observability pipelines, zero-downtime deployment, sophisticated auth systems.
- Each headline: 1 short punchy sentence max. Written for a busy founder scanning resumes.

Generate 3-5 interview questions with a mix of categories. At least 1 business_value, 1 design_choice, and 1 code_issue questions.

Return ONLY the JSON object, no other text or markdown formatting."""
        
        # 6. Call LLM
        client = genai.Client(api_key=GEMINI_API_KEY)
        evaluation_data = None
        last_error = None
        for attempt in range(2):
            try:
                response = client.models.generate_content(
                    model="gemini-2.0-flash",
                    contents=prompt,
                    config={"http_options": {"timeout": 30_000}},
                )
                response_text = response.text.strip().replace("```json", "").replace("```", "")
                evaluation_data = json.loads(response_text)
                break
            except (json.JSONDecodeError, IndexError, Exception) as e:
                last_error = e
                logger.warning(f"Gemini error (attempt {attempt + 1}/2): {e}")
                time.sleep(1)

        if evaluation_data is None:
            logger.error(f"Gemini failed after 2 attempts for repo {repo.id}: {last_error}")
            raise HTTPException(status_code=503, detail="Evaluation service temporarily unavailable.")

        # 7. Validate and build response
        try:
            business_value = BusinessValue(**evaluation_data["business_value"])
            standout_features = [str(f) for f in evaluation_data.get("standout_features", [])[:3]]
            questions = [InterviewQuestion(**q) for q in evaluation_data.get("interview_questions", [])[:7]]
        except (KeyError, ValueError) as e:
            logger.error(f"LLM response missing required fields for repo {repo.id}: {e}")
            raise HTTPException(status_code=500, detail="Evaluation returned incomplete results.")

        # 8. Finalize rejection logic
        is_rejected = False
        rejection_reason = None

        if standout_features:
            # If something stands out, never reject (even if AI slop)
            is_rejected = False
            rejection_reason = None
        else:
            # Nothing stands out - only reject for pure AI slop
            if ai_slop_result.score == 100:
                is_rejected = True
                rejection_reason = "AI-generated code and nothing stands out"

        # 9. Store in database and return
        repo_evaluation = RepoEvaluation(
            repo_id=repo.id,
            evaluated_at=datetime.utcnow(),
            is_rejected=1 if is_rejected else 0,
            rejection_reason=rejection_reason,
            business_value=json.dumps(business_value.model_dump()),
            standout_features=json.dumps(standout_features),
            interview_questions=json.dumps([q.model_dump() for q in questions]),
        )
        session.add(repo_evaluation)
        session.commit()

        return EvaluateResponse(
            repo_id=repo.id,
            repo_url=repo_url,
            is_rejected=is_rejected,
            rejection_reason=rejection_reason,
            business_value=business_value,
            standout_features=standout_features,
            interview_questions=questions,
        )


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
                eval_result = call_gemini_evaluation(
                    repo_url, repo_name,
                    ai_slop_result, bad_practices_result, code_quality_result,
                    extracted_data,
                )

                # 9. Determine rejection status
                business_value = None
                standout_features = []
                is_rejected = False
                rejection_reason = None

                if eval_result:
                    business_value = eval_result.get("business_value")
                    standout_features = [str(f) for f in eval_result.get("standout_features", [])[:3]]

                if standout_features:
                    is_rejected = False
                    rejection_reason = None
                else:
                    if ai_slop_result.score == 100:
                        is_rejected = True
                        rejection_reason = "AI-generated code and nothing stands out"

                if not eval_result:
                    logger.error(f"LLM evaluation failed after retries for {repo_url}")

                yield f"event: evaluation\ndata: {json.dumps({'business_value': business_value, 'standout_features': standout_features, 'is_rejected': is_rejected, 'rejection_reason': rejection_reason})}\n\n"

                # 10. LLM Call 2: Interview questions
                questions_result = call_gemini_questions(
                    repo_url, repo_name,
                    ai_slop_result, bad_practices_result, code_quality_result,
                    extracted_data,
                )

                questions_list = []
                questions_error = None
                if questions_result:
                    questions_list = questions_result.get("interview_questions", [])[:7]
                else:
                    logger.error(f"LLM questions failed after retries for {repo_url}")
                    questions_error = "No questions generated, an error occurred."

                questions_event: dict = {"interview_questions": questions_list}
                if questions_error:
                    questions_event["error"] = questions_error

                yield f"event: questions\ndata: {json.dumps(questions_event)}\n\n"

                # 11. Save evaluation to DB (only if eval LLM succeeded)
                if eval_result:
                    try:
                        repo_evaluation = RepoEvaluation(
                            repo_id=repo.id,
                            evaluated_at=datetime.utcnow(),
                            is_rejected=1 if is_rejected else 0,
                            rejection_reason=rejection_reason,
                            business_value=json.dumps(business_value) if business_value else json.dumps({}),
                            standout_features=json.dumps(standout_features),
                            interview_questions=json.dumps(questions_list),
                        )
                        session.add(repo_evaluation)
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


