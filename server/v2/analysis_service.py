
import json
import logging
import subprocess
import tempfile
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from models import Repo, RepoAnalysis, RepoEvaluation, User
from v2.data_extractor import extract_repo_data, is_test_file
from v2.feature_extractor import extract_features
from v2.analyzers import analyze_ai_slop, analyze_bad_practices, analyze_code_quality
from v2.schemas import Verdict, VALID_PRIORITIES, DEFAULT_PRIORITIES
from v2.clone_script import clone_repo
from prompt_modules import build_evaluation_prompt, build_questions_prompt, build_multi_repo_questions_prompt, HARDCODED_INTERVIEW_QUESTIONS

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
    for finding in bad_practices_result.findings:
        if is_test_file(finding.file):
            continue
        findings_context.append({
            "category": "Bad Practice", "type": finding.type, "severity": finding.severity,
            "file": finding.file, "line": finding.line, "snippet": finding.snippet[:300],
            "explanation": finding.explanation,
        })
        if len(findings_context) >= 5:
            break
    for finding in code_quality_result.findings:
        if is_test_file(finding.file):
            continue
        findings_context.append({
            "category": "Code Quality", "type": finding.type, "severity": finding.severity,
            "file": finding.file, "line": finding.line, "snippet": finding.snippet[:300],
            "explanation": finding.explanation,
        })
        if len(findings_context) >= 10:
            break
    return findings_context

def run_analysis_pipeline(repo_url: str):
    """
    Core analysis logic: Clone -> Extract -> Analyze.
    Returns (extracted_data, ai_slop, bad_practices, code_quality, verdict)
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        clone_repo(repo_url, temp_dir)
        
        extracted_data = extract_repo_data(temp_dir)
        features = extract_features(extracted_data)
        
        ai_slop = analyze_ai_slop(extracted_data, features)
        bad_practices = analyze_bad_practices(extracted_data)
        code_quality = analyze_code_quality(extracted_data)
        
        verdict = compute_verdict(ai_slop.score, bad_practices.score, code_quality.score)
        
        return extracted_data, ai_slop, bad_practices, code_quality, verdict

def save_analysis_results(session: Session, repo_id: int, extracted_data, ai_slop, bad_practices, code_quality, verdict):
    """
    Saves analysis results to the database. Updates existing record if one already exists.
    """
    files_analyzed = [
        {"path": path, "importance_score": min(max(score, 0), 100), "loc": len(extracted_data.files.get(path, "").split("\n"))}
        for path, score in sorted(extracted_data.file_importance.items(), key=lambda x: x[1], reverse=True)[:15]
    ]

    repo_analysis = session.query(RepoAnalysis).filter(RepoAnalysis.repo_id == repo_id).first()
    if repo_analysis:
        repo_analysis.analyzed_at = datetime.utcnow()
        repo_analysis.verdict_type = verdict.type
        repo_analysis.verdict_confidence = verdict.confidence
        repo_analysis.ai_slop_score = ai_slop.score
        repo_analysis.ai_slop_confidence = ai_slop.confidence.value
        repo_analysis.ai_slop_data = ai_slop.model_dump_json()
        repo_analysis.bad_practices_score = bad_practices.score
        repo_analysis.bad_practices_data = bad_practices.model_dump_json()
        repo_analysis.code_quality_score = code_quality.score
        repo_analysis.code_quality_data = code_quality.model_dump_json()
        repo_analysis.files_analyzed = json.dumps(files_analyzed)
    else:
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
    priorities: list[str] = None,
    use_generic_questions: bool = False,
    skip_questions: bool = False,
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

    # Extract and clamp originality_score; store it in business_value for later composite scoring
    try:
        originality_score = max(0.0, min(1.0, float(eval_result.get("originality_score", 0.5))))
    except (TypeError, ValueError):
        originality_score = 0.5
    if business_value and isinstance(business_value, dict):
        business_value["originality_score"] = originality_score
    
    # Rejection logic
    is_rejected = False
    rejection_reason = None
    if not standout_features and ai_slop.score == 100:
        is_rejected = True
        rejection_reason = "AI-generated code and nothing stands out"
        
    # 2. Interview Questions
    if skip_questions:
        return business_value, standout_features, is_rejected, rejection_reason, []

    if use_generic_questions:
        return business_value, standout_features, is_rejected, rejection_reason, HARDCODED_INTERVIEW_QUESTIONS

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
    repo_evaluation = session.query(RepoEvaluation).filter(RepoEvaluation.repo_id == repo_id).first()
    if repo_evaluation:
        repo_evaluation.evaluated_at = datetime.utcnow()
        repo_evaluation.is_rejected = bool(is_rejected)
        repo_evaluation.rejection_reason = rejection_reason
        repo_evaluation.business_value = json.dumps(business_value) if business_value else json.dumps({})
        repo_evaluation.standout_features = json.dumps(standout_features)
        repo_evaluation.interview_questions = json.dumps(interview_questions)
    else:
        repo_evaluation = RepoEvaluation(
            repo_id=repo_id,
            evaluated_at=datetime.utcnow(),
            is_rejected=bool(is_rejected),
            rejection_reason=rejection_reason,
            business_value=json.dumps(business_value) if business_value else json.dumps({}),
            standout_features=json.dumps(standout_features),
            interview_questions=json.dumps(interview_questions),
        )
        session.add(repo_evaluation)
    session.flush()
    return repo_evaluation


# =============================================================================
# DYNAMIC COMPOSITE SCORING ENGINE
# =============================================================================

def compute_severity_aware_security_penalty(
    raw_bad_practices_score: int,
    findings: list[dict],
    security_weight: float,
) -> int:
    """
    Recompute bad practices penalty with severity-aware scaling.

    CRITICAL findings (hardcoded secrets, .env committed) always apply at full weight.
    WARNING findings scale linearly with the slider weight.
    INFO findings are heavily discounted at low slider values.
    """
    if not findings:
        return raw_bad_practices_score

    SEVERITY_WEIGHTS = {"critical": 60, "warning": 20, "info": 5}
    severity_multipliers = {
        "critical": 1.0,               # Always full weight — hardcoded secrets etc.
        "warning": security_weight,     # Scales linearly with slider
        "info": security_weight * 0.3,  # Heavily discounted at low slider values
    }

    total_weight = 0
    for finding in findings:
        severity = finding.get("severity", "info").lower()
        base_weight = SEVERITY_WEIGHTS.get(severity, 5)
        multiplier = severity_multipliers.get(severity, security_weight)
        total_weight += base_weight * multiplier

    return min(100, round(total_weight))


def compute_tech_match_penalty(
    repo_languages: dict[str, int],
    repo_dependencies: list[str],
    ai_slop_score: int,
    required_tech: dict,
) -> float:
    """
    Compute penalty (0-100) based on how well a repo matches the required tech stack.
    Higher = worse match. 0 = perfect match or no requirements.
    """
    required_langs = required_tech.get("languages", [])
    required_tools = required_tech.get("tools", [])

    if not required_langs and not required_tools:
        return 0.0

    total_required = len(required_langs) + len(required_tools)
    matched = 0

    repo_lang_lower = {lang.lower() for lang in repo_languages.keys()}

    FRAMEWORK_TO_LANG = {
        "react": {"javascript", "typescript"},
        "angular": {"typescript"},
        "vue": {"javascript", "typescript"},
        "svelte": {"javascript", "typescript"},
        "next.js": {"javascript", "typescript"},
        "express": {"javascript", "typescript"},
        "node.js": {"javascript", "typescript"},
        "django": {"python"},
        "flask": {"python"},
        "fastapi": {"python"},
        "spring": {"java"},
        ".net": {"c#"},
        "ruby on rails": {"ruby"},
    }

    dep_lower = [d.lower() for d in repo_dependencies]

    for req_lang in required_langs:
        req_lower = req_lang.lower()
        if req_lower in repo_lang_lower:
            matched += 1
            continue
        expected_langs = FRAMEWORK_TO_LANG.get(req_lower, set())
        if expected_langs and expected_langs & repo_lang_lower:
            if any(req_lower.replace(".", "").replace(" ", "") in d for d in dep_lower):
                matched += 1
                continue
        if any(req_lower.replace(" ", "-") in d or req_lower.replace(" ", "") in d for d in dep_lower):
            matched += 1

    TOOL_INDICATORS = {
        "aws": ["aws", "boto3", "aws-cdk", "aws-sdk", "serverless"],
        "gcp": ["google-cloud", "gcloud", "@google-cloud"],
        "azure": ["azure", "@azure"],
        "docker": ["docker"],
        "kubernetes": ["kubernetes", "k8s", "kubectl"],
        "terraform": ["terraform"],
        "ci/cd": [],
        "postgresql": ["pg", "postgres", "psycopg", "sequelize", "prisma"],
        "mongodb": ["mongo", "mongoose", "pymongo"],
        "redis": ["redis", "ioredis"],
        "graphql": ["graphql", "apollo", "@apollo"],
        "rest api": [],
        "microsoft 365/dynamics": ["microsoft365", "dynamics", "@microsoft"],
        "elasticsearch": ["elasticsearch", "elastic"],
        "rabbitmq": ["rabbitmq", "amqp", "pika"],
        "kafka": ["kafka", "confluent"],
    }

    for req_tool in required_tools:
        req_lower = req_tool.lower()
        indicators = TOOL_INDICATORS.get(req_lower, [req_lower])
        if any(ind in d for d in dep_lower for ind in indicators):
            matched += 1

    match_ratio = matched / total_required if total_required > 0 else 1.0
    missing_penalty = (1.0 - match_ratio) * 100

    # Extra penalty for vibe-coded tech matches
    if matched > 0 and ai_slop_score >= 60:
        missing_penalty += 15

    return min(100.0, missing_penalty)


def compute_composite_score(
    ai_slop_score: int,
    bad_practices_score: int,
    code_quality_score: int,
    originality_score: float,
    bad_practices_findings: list[dict],
    scoring_config: dict,
    shipped_to_prod: bool = False,
    tech_match_penalty: float = 0.0,
) -> int:
    """Compute composite 0-100 score for a single repo. Higher = better candidate."""
    weights = scoring_config.get("weights", {})
    w_ai = weights.get("ai_detection", 0.7)
    w_sec = weights.get("security", 0.5)
    w_cq = weights.get("code_quality", 0.5)
    w_orig = weights.get("originality", 0.5)

    ai_penalty = ai_slop_score
    security_penalty = compute_severity_aware_security_penalty(bad_practices_score, bad_practices_findings, w_sec)
    quality_penalty = 100 - code_quality_score
    originality_penalty = (1.0 - originality_score) * 100

    total_weight = w_ai + w_sec + w_cq + w_orig
    if total_weight == 0:
        total_weight = 1.0

    weighted_penalty = (
        ai_penalty * w_ai +
        security_penalty * w_sec +
        quality_penalty * w_cq +
        originality_penalty * w_orig
    ) / total_weight

    if scoring_config.get("shipped_to_prod_bonus", True) and shipped_to_prod:
        weighted_penalty *= 0.85

    required_tech = scoring_config.get("required_tech", {})
    has_required = bool(required_tech.get("languages") or required_tech.get("tools"))
    if has_required and tech_match_penalty > 0:
        weighted_penalty = weighted_penalty * 0.7 + tech_match_penalty * 0.3

    return max(0, min(100, round(100 - weighted_penalty)))


def compute_candidate_score(
    repo_scores: list[int],
    repo_tech_relevance: list[float] | None = None,
) -> int:
    """
    Weighted average of repo scores.
    repo_tech_relevance[i] = (1 - tech_match_penalty/100) * max(0, 1 - (ai_slop/100) * w_ai)
    Repos matching required tech AND hand-coded are weighted higher.
    """
    if not repo_scores:
        return 0
    if repo_tech_relevance and len(repo_tech_relevance) == len(repo_scores):
        total_weight = sum(repo_tech_relevance)
        if total_weight == 0:
            return round(sum(repo_scores) / len(repo_scores))
        weighted = sum(s * w for s, w in zip(repo_scores, repo_tech_relevance))
        return max(0, min(100, round(weighted / total_weight)))
    return round(sum(repo_scores) / len(repo_scores))


def aggregate_tech_stack(repos: list[dict]) -> list[dict]:
    """
    Aggregate language/tech usage across all candidate repos.

    Args:
        repos: List of dicts with keys:
            - "repo_name": str
            - "languages": dict[str, int]  (language -> bytes)
            - "ai_slop_score": int

    Returns:
        List of TechStackLanguage-compatible dicts, sorted by total_projects descending.
    """
    from collections import defaultdict
    lang_data: dict[str, dict] = defaultdict(lambda: {
        "total_projects": 0,
        "hand_coded": 0,
        "vibe_coded": 0,
        "project_names": [],
    })

    for repo in repos:
        repo_name = repo.get("repo_name", "")
        languages = repo.get("languages", {}) or {}
        ai_slop_score = repo.get("ai_slop_score", 0)
        is_vibe_coded = ai_slop_score >= 60

        for language in languages.keys():
            entry = lang_data[language]
            entry["total_projects"] += 1
            if is_vibe_coded:
                entry["vibe_coded"] += 1
            else:
                entry["hand_coded"] += 1
            entry["project_names"].append(repo_name)

    result = [
        {
            "language": lang,
            "total_projects": data["total_projects"],
            "hand_coded": data["hand_coded"],
            "vibe_coded": data["vibe_coded"],
            "project_names": data["project_names"],
        }
        for lang, data in lang_data.items()
    ]
    result.sort(key=lambda x: x["total_projects"], reverse=True)
    return result


def run_questions_from_db(
    repo: Repo,
    repo_analysis: RepoAnalysis,
    priorities: list[str] = None,
) -> list:
    """
    Generate single-repo interview questions from stored analysis data — no re-cloning.
    Reconstructs findings context from the persisted JSON blobs.
    """
    import os
    from google import genai

    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    if not GEMINI_API_KEY:
        return []

    client = genai.Client(api_key=GEMINI_API_KEY)

    bad_practices_data = json.loads(repo_analysis.bad_practices_data)
    code_quality_data = json.loads(repo_analysis.code_quality_data)
    files_analyzed = json.loads(repo_analysis.files_analyzed)

    # Reconstruct findings_context from stored data (same logic as _build_findings_context)
    findings_context = []
    for finding in bad_practices_data.get("findings", []):
        if is_test_file(finding.get("file", "")):
            continue
        findings_context.append({
            "category": "Bad Practice",
            "type": finding["type"],
            "severity": finding["severity"],
            "file": finding["file"],
            "line": finding["line"],
            "snippet": finding.get("snippet", "")[:300],
            "explanation": finding["explanation"],
        })
        if len(findings_context) >= 5:
            break
    for finding in code_quality_data.get("findings", []):
        if is_test_file(finding.get("file", "")):
            continue
        findings_context.append({
            "category": "Code Quality",
            "type": finding["type"],
            "severity": finding["severity"],
            "file": finding["file"],
            "line": finding["line"],
            "snippet": finding.get("snippet", "")[:300],
            "explanation": finding["explanation"],
        })
        if len(findings_context) >= 10:
            break

    file_tree = [f["path"] for f in files_analyzed[:10]]

    class _ScoreStub:
        def __init__(self, score):
            self.score = score
            self.confidence = "medium"

    questions_prompt = build_questions_prompt(
        repo_url=repo.github_link,
        repo_name=repo.repo_name,
        ai_slop_result=_ScoreStub(repo_analysis.ai_slop_score),
        bad_practices_result=_ScoreStub(repo_analysis.bad_practices_score),
        code_quality_result=_ScoreStub(repo_analysis.code_quality_score),
        file_tree=file_tree,
        findings_context=findings_context,
        priorities=priorities,
    )

    for attempt in range(2):
        try:
            response = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=questions_prompt,
                config={"http_options": {"timeout": 30_000}},
            )
            data = json.loads(response.text.strip().replace("```json", "").replace("```", ""))
            return data.get("interview_questions", [])[:7]
        except Exception as e:
            logger.warning(f"Gemini questions error (attempt {attempt + 1}/2): {e}")

    return []


def run_multi_repo_questions(
    repos_data: list[dict],
    priorities: list[str] = None,
) -> list:
    """
    Generate 3-5 interview questions aggregated across multiple repos in a single LLM call.
    repos_data: list of {repo_url, repo_name, ai_score, bad_practices_score, quality_score,
                          bad_practices_findings, code_quality_findings}
    """
    import os
    from google import genai

    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    if not GEMINI_API_KEY:
        return []

    client = genai.Client(api_key=GEMINI_API_KEY)
    prompt = build_multi_repo_questions_prompt(repos_data, priorities)

    for attempt in range(2):
        try:
            response = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=prompt,
                config={"http_options": {"timeout": 45_000}},
            )
            data = json.loads(response.text.strip().replace("```json", "").replace("```", ""))
            return data.get("interview_questions", [])[:5]
        except Exception as e:
            logger.warning(f"Gemini multi-repo questions error (attempt {attempt + 1}/2): {e}")

    return []
