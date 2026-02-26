
import json
import logging
import subprocess
import tempfile
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from models import Repo, RepoAnalysis, RepoEvaluation, User
from v2.data_extractor import extract_repo_data
from v2.feature_extractor import extract_features
from v2.analyzers import analyze_ai_slop, analyze_bad_practices, analyze_code_quality
from v2.schemas import Verdict, VALID_PRIORITIES, DEFAULT_PRIORITIES
from prompt_modules import build_evaluation_prompt, build_questions_prompt

logger = logging.getLogger(__name__)

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

def compute_verdict(ai_score: int, bad_practices_score: int, quality_score: int) -> Verdict:
    """
    Compute verdict based on analyzer scores.
    """
    # High AI usage (≥60)
    if ai_score >= 60:
        if bad_practices_score >= 50 and quality_score < 50:
            confidence = min(100, 60 + (ai_score - 60) // 2 + (bad_practices_score - 50) // 2 + (50 - quality_score) // 2)
            return Verdict(type="Slop Coder", confidence=confidence)
        elif bad_practices_score < 50 and quality_score >= 50:
            confidence = min(100, 60 + (ai_score - 60) // 3 + (50 - bad_practices_score) // 3 + (quality_score - 50) // 3)
            return Verdict(type="Good AI Coder", confidence=confidence)
        else:
            if quality_score >= 50:
                return Verdict(type="Good AI Coder", confidence=50)
            else:
                return Verdict(type="Slop Coder", confidence=50)
    else:
        if bad_practices_score < 50 and quality_score >= 50:
            confidence = min(100, 60 + (60 - ai_score) // 3 + (50 - bad_practices_score) // 3 + (quality_score - 50) // 3)
            return Verdict(type="Senior", confidence=confidence)
        elif bad_practices_score >= 50 and quality_score < 50:
            confidence = min(100, 60 + (bad_practices_score - 50) // 2 + (50 - quality_score) // 2)
            return Verdict(type="Junior", confidence=confidence)
        else:
            if quality_score >= 50:
                return Verdict(type="Senior", confidence=50)
            else:
                return Verdict(type="Junior", confidence=50)

def _build_findings_context(bad_practices_result, code_quality_result):
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

def run_analysis_pipeline(repo_url: str):
    """
    Core analysis logic: Clone -> Extract -> Analyze.
    Returns (extracted_data, ai_slop, bad_practices, code_quality, verdict)
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        result = subprocess.run(
            ["git", "clone", "--depth", "100", repo_url, temp_dir],
            capture_output=True, text=True, encoding='utf-8', errors='ignore', timeout=120,
        )
        if result.returncode != 0:
            raise Exception(f"Failed to clone repository: {result.stderr}")
        
        extracted_data = extract_repo_data(temp_dir)
        features = extract_features(extracted_data)
        
        ai_slop = analyze_ai_slop(extracted_data, features)
        bad_practices = analyze_bad_practices(extracted_data)
        code_quality = analyze_code_quality(extracted_data)
        
        verdict = compute_verdict(ai_slop.score, bad_practices.score, code_quality.score)
        
        return extracted_data, ai_slop, bad_practices, code_quality, verdict

def save_analysis_results(session: Session, repo_id: int, extracted_data, ai_slop, bad_practices, code_quality, verdict):
    """
    Saves analysis results to the database.
    """
    files_analyzed = [
        {"path": path, "importance_score": min(max(score, 0), 100), "loc": len(extracted_data.files.get(path, "").split("\n"))}
        for path, score in sorted(extracted_data.file_importance.items(), key=lambda x: x[1], reverse=True)[:15]
    ]
    
    repo_analysis = RepoAnalysis(
        repo_id=repo_id,
        analyzed_at=datetime.utcnow(),
        verdict_type=verdict.type,
        verdict_confidence=verdict.confidence,
        ai_slop_score=ai_slop.score,
        ai_slop_confidence=ai_slop.confidence.value,
        ai_slop_data=ai_slop.model_dump_json(),
        bad_practices_score=bad_practices.score,
        bad_practices_data=bad_practices.model_dump_json(),
        code_quality_score=code_quality.score,
        code_quality_data=code_quality.model_dump_json(),
        files_analyzed=json.dumps(files_analyzed),
    )
    session.add(repo_analysis)
    
    # Update repo languages
    repo = session.query(Repo).filter(Repo.id == repo_id).first()
    if repo and extracted_data.languages:
        repo.languages = json.dumps(extracted_data.languages)
    
    session.flush()
    return repo_analysis

def run_evaluation_pipeline(
    repo_url: str,
    repo_name: str,
    ai_slop,
    bad_practices,
    code_quality,
    extracted_data,
    priorities: list[str] = None
):
    """
    Runs Gemini evaluation and returns (business_value, standout_features, is_rejected, rejection_reason, interview_questions)
    """
    import os
    from google import genai
    
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    if not GEMINI_API_KEY:
        return None, [], False, None, []
    
    client = genai.Client(api_key=GEMINI_API_KEY)
    findings_context = _build_findings_context(bad_practices, code_quality)
    file_tree = [path for path, score in sorted(extracted_data.file_importance.items(), key=lambda x: x[1], reverse=True)[:10]]
    
    # 1. Business Value & Standout Features
    eval_prompt = build_evaluation_prompt(
        repo_url=repo_url, repo_name=repo_name,
        ai_slop_result=ai_slop, bad_practices_result=bad_practices, code_quality_result=code_quality,
        file_tree=file_tree, findings_context=findings_context, priorities=priorities
    )
    
    eval_result = None
    for attempt in range(2):
        try:
            response = client.models.generate_content(
                model="gemini-2.0-flash", contents=eval_prompt,
                config={"http_options": {"timeout": 30_000}, "temperature": 0.0, "top_p": 0.0, "top_k": 1}
            )
            eval_result = json.loads(response.text.strip().replace("```json", "").replace("```", ""))
            break
        except Exception as e:
            logger.warning(f"Gemini evaluation error (attempt {attempt + 1}/2): {e}")
            
    if not eval_result:
        return None, [], False, None, []
        
    business_value = eval_result.get("business_value")
    standout_features = [str(f) for f in eval_result.get("standout_features", [])[:3]]
    
    # Rejection logic
    is_rejected = False
    rejection_reason = None
    if not standout_features and ai_slop.score == 100:
        is_rejected = True
        rejection_reason = "AI-generated code and nothing stands out"
        
    # 2. Interview Questions
    questions_prompt = build_questions_prompt(
        repo_url=repo_url, repo_name=repo_name,
        ai_slop_result=ai_slop, bad_practices_result=bad_practices, code_quality_result=code_quality,
        file_tree=file_tree, findings_context=findings_context, priorities=priorities
    )
    
    questions_list = []
    for attempt in range(2):
        try:
            response = client.models.generate_content(
                model="gemini-2.0-flash", contents=questions_prompt,
                config={"http_options": {"timeout": 30_000}}
            )
            questions_data = json.loads(response.text.strip().replace("```json", "").replace("```", ""))
            questions_list = questions_data.get("interview_questions", [])[:7]
            break
        except Exception as e:
            logger.warning(f"Gemini questions error (attempt {attempt + 1}/2): {e}")
            
    return business_value, standout_features, is_rejected, rejection_reason, questions_list

def save_evaluation_results(
    session: Session,
    repo_id: int,
    business_value,
    standout_features,
    is_rejected,
    rejection_reason,
    interview_questions
):
    """
    Saves evaluation results to the database.
    """
    repo_evaluation = RepoEvaluation(
        repo_id=repo_id,
        evaluated_at=datetime.utcnow(),
        is_rejected=1 if is_rejected else 0,
        rejection_reason=rejection_reason,
        business_value=json.dumps(business_value) if business_value else json.dumps({}),
        standout_features=json.dumps(standout_features),
        interview_questions=json.dumps(interview_questions),
    )
    session.add(repo_evaluation)
    session.flush()
    return repo_evaluation
