
import json
import logging
import subprocess
import tempfile
import os
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
import requests

from models import Repo, RepoAnalysis, RepoEvaluation, User
from v2.data_extractor import extract_repo_data
from v2.feature_extractor import extract_features
from v2.analyzers import analyze_ai_slop, analyze_bad_practices, analyze_code_quality
from v2.schemas import Verdict, VALID_PRIORITIES, DEFAULT_PRIORITIES
from v2.clone_script import clone_repo
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

def compute_general_score(ai_score: int, bad_practices_score: int, code_quality_score: int) -> int:
    """
    Compute a general repository health score (0-100) by aggregating the three analyzer scores.
    
    - Lower AI slop is better (inverted): 100 - ai_score
    - Lower bad practices is better (inverted): 100 - bad_practices_score
    - Higher code quality is better: code_quality_score
    
    Returns weighted average: (inverted_ai + inverted_bad_practices + quality) / 3
    """
    inverted_ai = 100 - ai_score
    inverted_bad_practices = 100 - bad_practices_score
    general_score = (inverted_ai + inverted_bad_practices + code_quality_score) // 3
    return max(0, min(100, general_score))  # Clamp to [0, 100]

def generate_analysis_summary(repo_name: str, verdict: Verdict, ai_slop, bad_practices, code_quality, extracted_data) -> str:
    """
    Generate a human-readable summary of the repository analysis.
    
    Returns a formatted text summary covering verdict, key metrics, and recommendations.
    """
    summary_lines = []
    summary_lines.append(f"=== Analysis Summary for {repo_name} ===\n")
    
    # Verdict Section
    summary_lines.append(f"VERDICT: {verdict.type} (Confidence: {verdict.confidence}%)\n")
    
    # AI Slop Analysis
    summary_lines.append(f"AI Slop Detection: {ai_slop.score}/100")
    summary_lines.append(f"  Confidence: {ai_slop.confidence.value.upper()}")
    if ai_slop.score >= 70:
        summary_lines.append("  → Significant indicators of AI-generated or AI-assisted code detected")
    elif ai_slop.score >= 40:
        summary_lines.append("  → Some patterns suggest AI assistance in code generation")
    else:
        summary_lines.append("  → Code appears to be primarily hand-written")
    summary_lines.append("")
    
    # Bad Practices Analysis
    summary_lines.append(f"Bad Practices Score: {bad_practices.score}/100")
    critical_count = len([f for f in bad_practices.findings if f.severity.value == "critical"])
    warning_count = len([f for f in bad_practices.findings if f.severity.value == "warning"])
    summary_lines.append(f"  Findings: {critical_count} critical, {warning_count} warnings")
    if critical_count > 0:
        summary_lines.append("  → Code has critical security or design issues that need immediate attention")
    elif bad_practices.score >= 50:
        summary_lines.append("  → Several code quality and maintainability concerns found")
    else:
        summary_lines.append("  → Code follows good practices and standards")
    summary_lines.append("")
    
    # Code Quality Analysis
    summary_lines.append(f"Code Quality Score: {code_quality.score}/100")
    if code_quality.score >= 70:
        summary_lines.append("  → Strong code organization, testing, and documentation")
    elif code_quality.score >= 50:
        summary_lines.append("  → Moderate code quality with room for improvement")
    else:
        summary_lines.append("  → Code quality needs significant improvement")
    summary_lines.append("")
    
    # Key Strengths and Concerns
    summary_lines.append("KEY OBSERVATIONS:")
    
    # Positive signals
    positive_signals_found = False
    if hasattr(code_quality, 'positive_signals') and code_quality.positive_signals:
        positive_signals_found = True
        summary_lines.append("  Strengths:")
        for signal in code_quality.positive_signals[:3]:
            summary_lines.append(f"    • {signal.explanation}")
    
    # Top findings
    all_findings = []
    if hasattr(bad_practices, 'findings') and bad_practices.findings:
        all_findings.extend(bad_practices.findings)
    if hasattr(code_quality, 'findings') and code_quality.findings:
        all_findings.extend(code_quality.findings)
    
    if all_findings:
        if positive_signals_found:
            summary_lines.append("  Concerns:")
        else:
            summary_lines.append("  Key Issues:")
        for finding in sorted(all_findings, key=lambda f: {"critical": 0, "warning": 1, "info": 2}.get(f.severity.value, 3))[:3]:
            summary_lines.append(f"    • [{finding.severity.value.upper()}] {finding.type} in {finding.file}")
    summary_lines.append("")
    
    # Languages & File Breakdown
    if extracted_data.languages:
        summary_lines.append("LANGUAGES USED:")
        for lang, bytes_count in sorted(extracted_data.languages.items(), key=lambda x: x[1], reverse=True)[:5]:
            summary_lines.append(f"  • {lang}")
    summary_lines.append("")
    
    # Recommendation
    summary_lines.append("RECOMMENDATION FOR INTERVIEWS:")
    if verdict.type == "Slop Coder":
        summary_lines.append("  Focus on understanding candidate's grasp of fundamentals. Ask them to explain")
        summary_lines.append("  complex sections from their code and trace through logic manually.")
    elif verdict.type == "Junior":
        summary_lines.append("  Strong foundation but needs mentoring. Discuss their approach to learning and")
        summary_lines.append("  how they handle code review feedback and best practices.")
    elif verdict.type == "Senior":
        summary_lines.append("  Demonstrates solid engineering practices. Dig deeper into architectural")
        summary_lines.append("  decisions and how they approach complex problems.")
    else:  # Good AI Coder
        summary_lines.append("  Shows effective AI tool usage with good judgment. Discuss their workflow and")
        summary_lines.append("  how they verify and test AI-generated code before merging.")
    summary_lines.append("")
    
    return "\n".join(summary_lines)

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
        clone_repo(repo_url, temp_dir)
        
        extracted_data = extract_repo_data(temp_dir)
        features = extract_features(extracted_data)
        
        ai_slop = analyze_ai_slop(extracted_data, features)
        bad_practices = analyze_bad_practices(extracted_data)
        code_quality = analyze_code_quality(extracted_data)
        
        verdict = compute_verdict(ai_slop.score, bad_practices.score, code_quality.score)
        
        return extracted_data, ai_slop, bad_practices, code_quality, verdict

def save_analysis_results(session: Session, repo_id: int, repo_name: str, extracted_data, ai_slop, bad_practices, code_quality, verdict):
    """
    Saves analysis results to the database. Updates existing record if one already exists.
    """
    files_analyzed = [
        {"path": path, "importance_score": min(max(score, 0), 100), "loc": len(extracted_data.files.get(path, "").split("\n"))}
        for path, score in sorted(extracted_data.file_importance.items(), key=lambda x: x[1], reverse=True)[:15]
    ]
    general_score = compute_general_score(ai_slop.score, bad_practices.score, code_quality.score)
    analysis_summary = generate_analysis_summary(repo_name, verdict, ai_slop, bad_practices, code_quality, extracted_data)

    repo_analysis = session.query(RepoAnalysis).filter(RepoAnalysis.repo_id == repo_id).first()
    if repo_analysis:
        repo_analysis.analyzed_at = datetime.utcnow()
        repo_analysis.verdict_type = verdict.type
        repo_analysis.verdict_confidence = verdict.confidence
        repo_analysis.general_score = general_score
        repo_analysis.analysis_summary = analysis_summary
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
            general_score=general_score,
            analysis_summary=analysis_summary,
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
    repo_evaluation = session.query(RepoEvaluation).filter(RepoEvaluation.repo_id == repo_id).first()
    if repo_evaluation:
        repo_evaluation.evaluated_at = datetime.utcnow()
        repo_evaluation.is_rejected = 1 if is_rejected else 0
        repo_evaluation.rejection_reason = rejection_reason
        repo_evaluation.business_value = json.dumps(business_value) if business_value else json.dumps({})
        repo_evaluation.standout_features = json.dumps(standout_features)
        repo_evaluation.interview_questions = json.dumps(interview_questions)
    else:
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

def fetch_github_pinned_repos(username: str) -> list[dict]:
    """
    Fetch a GitHub user's pinned repositories using GraphQL API.
    Pinned repos are prioritized as they're explicitly showcased by the user.
    
    Returns: List of dicts with keys: 'name', 'url', 'stars', 'language'
    """
    try:
        query = """
        query($userName:String!) {
          user(login: $userName) {
            pinnedItems(first: 6, types: REPOSITORY) {
              edges {
                node {
                  ... on Repository {
                    name
                    url
                    stargazerCount
                    primaryLanguage {
                      name
                    }
                    isArchived
                    isFork
                  }
                }
              }
            }
          }
        }
        """
        
        headers = {"Content-Type": "application/json"}
        
        # Try with GitHub token if available
        github_token = os.getenv("GITHUB_TOKEN")
        if github_token:
            headers["Authorization"] = f"Bearer {github_token}"
        
        response = requests.post(
            "https://api.github.com/graphql",
            json={"query": query, "variables": {"userName": username}},
            headers=headers,
            timeout=10
        )
        response.raise_for_status()
        data = response.json()
        
        if "errors" in data:
            logger.warning(f"GraphQL error fetching pinned repos for {username}: {data['errors']}")
            return []
        
        pinned = []
        for edge in data.get("data", {}).get("user", {}).get("pinnedItems", {}).get("edges", []):
            repo = edge.get("node", {})
            if not repo:
                continue
            
            if repo.get("isArchived") or repo.get("isFork"):
                continue
            
            pinned.append({
                "name": repo.get("name"),
                "url": repo.get("url"),
                "stars": repo.get("stargazerCount", 0),
                "language": repo.get("primaryLanguage", {}).get("name"),
                "is_pinned": True,
            })
        
        return pinned
    except Exception as e:
        logger.debug(f"Failed to fetch pinned repos for {username}: {e}")
        return []


def fetch_github_user_repos(username: str, limit: int = 3) -> list[dict]:
    """
    Fetch a GitHub user's top repositories, prioritizing pinned repos.
    Falls back to starred repos if not enough pinned repos available.
    
    Returns: List of dicts with keys: 'name', 'url', 'stars', 'language', 'is_pinned'
    """
    try:
        # First, try to get pinned repos
        pinned_repos = fetch_github_pinned_repos(username)
        
        # If we have enough pinned repos, return those
        if len(pinned_repos) >= limit:
            return pinned_repos[:limit]
        
        # Otherwise, fetch starred repos to fill the gap
        url = f"https://api.github.com/users/{username}/repos"
        
        params = {
            "sort": "stars",
            "direction": "desc",
            "per_page": 100,
            "type": "owner"
        }
        
        headers = {}
        github_token = os.getenv("GITHUB_TOKEN")
        if github_token:
            headers["Authorization"] = f"Bearer {github_token}"
        
        response = requests.get(url, params=params, headers=headers, timeout=10)
        response.raise_for_status()
        
        repos = response.json()
        
        # Build list of starred repos (excluding those already pinned)
        pinned_names = {repo["name"] for repo in pinned_repos}
        starred_repos = []
        
        for repo in repos:
            if repo.get("fork"):
                continue
            if repo.get("archived"):
                continue
            if repo["name"] in pinned_names:  # Skip if already in pinned list
                continue
            
            starred_repos.append({
                "name": repo["name"],
                "url": repo["html_url"],
                "stars": repo["stargazers_count"],
                "language": repo.get("language"),
                "is_pinned": False,
            })
            
            if len(pinned_repos) + len(starred_repos) >= limit:
                break
        
        # Combine pinned (first) and starred repos
        return pinned_repos + starred_repos[:limit - len(pinned_repos)]
    except Exception as e:
        logger.error(f"Failed to fetch repos for {username}: {e}")
        return []


def find_top_repositories(session: Session, username: str, limit: int = 3) -> list[tuple[Repo, bool]]:
    """
    Find the top N repositories for a user.
    Fetches from GitHub API to get fresh repo data, then ensures they're in the database.
    Returns tuples of (Repo, is_pinned) where is_pinned indicates if the repo was pinned.
    """
    # Get or create user
    user = session.query(User).filter(User.username == username).first()
    if not user:
        user = User(
            username=username,
            github_link=f"https://github.com/{username}",
        )
        session.add(user)
        session.flush()
    
    # Fetch repos from GitHub API
    github_repos = fetch_github_user_repos(username, limit=limit)
    
    if not github_repos:
        return []
    
    # Get or create Repo records for each GitHub repo
    repos = []
    for github_repo in github_repos:
        repo = get_or_create_repo(
            session,
            user,
            github_repo["url"],
            github_repo["name"]
        )
        # Update stars if they've changed
        if repo.stars != github_repo["stars"]:
            repo.stars = github_repo["stars"]
        
        is_pinned = github_repo.get("is_pinned", False)
        repos.append((repo, is_pinned))
    
    session.flush()
    return repos


def generate_profile_assessment(repos_analyses: list[tuple[Repo, RepoAnalysis]]) -> tuple[str, str]:
    """
    Generate a tier score and profile summary using LLM based on repository analyses.
    The average general_score is passed as a calibration anchor to keep the tier
    grounded while still allowing the LLM to reason about qualitative patterns.

    Returns: (tier, profile_summary)
    tier: One of ["F", "E", "D", "C", "B", "A", "S"]
    """
    import os
    from google import genai
    
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    if not GEMINI_API_KEY:
        return _compute_fallback_tier_and_summary(repos_analyses)
    
    client = genai.Client(api_key=GEMINI_API_KEY)
    
    # Compute average general score as calibration anchor
    valid_scores = [a.general_score for _, a in repos_analyses if a.general_score is not None]
    avg_general_score = round(sum(valid_scores) / len(valid_scores)) if valid_scores else None

    # Map score to the tier range the LLM should stay close to
    SCORE_TO_TIER_RANGE = [
        (85, "S"),
        (70, "A"),
        (55, "B"),
        (40, "C"),
        (20, "D"),
        (0,  "F"),
    ]
    anchored_tier = "C"
    if avg_general_score is not None:
        for threshold, tier_label in SCORE_TO_TIER_RANGE:
            if avg_general_score >= threshold:
                anchored_tier = tier_label
                break

    # Prepare context from analyses
    repos_context = []
    for repo, analysis in repos_analyses:
        repos_context.append({
            "name": repo.repo_name,
            "url": repo.github_link,
            "verdict": analysis.verdict_type,
            "verdict_confidence": analysis.verdict_confidence,
            "ai_slop_score": analysis.ai_slop_score,
            "bad_practices_score": analysis.bad_practices_score,
            "code_quality_score": analysis.code_quality_score,
            "general_score": analysis.general_score,
            "summary": analysis.analysis_summary,
        })
    
    score_anchor_block = (
        f"\nCALIBRATION ANCHOR:\n"
        f"  Average general_score across repos: {avg_general_score}/100\n"
        f"  Score-implied tier: {anchored_tier}\n"
        f"  Your assigned tier SHOULD match this anchor unless the qualitative patterns below "
        f"provide compelling evidence for a deviation. If you deviate, you MUST explain why in the summary.\n"
    ) if avg_general_score is not None else ""

    prompt = f"""Based on the following GitHub repository analyses, evaluate this developer's profile.

Repository Analyses:
{json.dumps(repos_context, indent=2)}
{score_anchor_block}
Your task:
1. Assign a tier: F (worst) > D > C > B > A > S (best)
2. Write exactly 3-4 bullet points summarizing the assessment. Each bullet must be one concise sentence.
   Cover: overall pattern, notable strengths or red flags, and one concrete recommendation for interviewers.
   If your tier differs from the calibration anchor, one bullet must explain the deviation.

Tier definitions:
- S (score ~85+): Consistently strong, excellent engineering, minimal AI signs or excellent AI usage
- A (score ~70-84): Strong performance, high code quality, few issues
- B (score ~55-69): Good overall, some areas for improvement
- C (score ~40-54): Mixed signals, average quality, room for improvement
- D (score ~20-39): Below average, notable issues, poor practices, or heavy AI dependency
- F (score <20): Critical red flags, appears to be pure AI-generated code

Return ONLY valid JSON (no markdown):
{{
  "tier": "{anchored_tier}",
  "bullets": ["First bullet.", "Second bullet.", "Third bullet."]
}}"""
    
    try:
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt,
            config={"http_options": {"timeout": 30_000}, "temperature": 0.1, "top_p": 0.0, "top_k": 1}
        )
        result = json.loads(response.text.strip().replace("```json", "").replace("```", ""))
        tier = result.get("tier", anchored_tier).upper()
        bullets = result.get("bullets", [])
        
        # Validate tier
        if tier not in ["F", "D", "C", "B", "A", "S"]:
            tier = anchored_tier
        
        # Format bullets as a simple bullet list for the profile_summary field
        profile_summary = "\n".join(f"• {b}" for b in bullets if b)
        
        return tier, profile_summary
    except Exception as e:
        logger.error(f"Gemini profile assessment error: {e}")
        return _compute_fallback_tier_and_summary(repos_analyses)

def _compute_fallback_tier_and_summary(repos_analyses: list[tuple[Repo, RepoAnalysis]]) -> tuple[str, str]:
    """
    Fallback tier computation if LLM fails.
    Computes an aggregate score from the analyzed repositories.
    """
    if not repos_analyses:
        return "F", "No repositories analyzed."
    
    verdicts = [analysis.verdict_type for _, analysis in repos_analyses]
    general_scores = [analysis.general_score for _, analysis in repos_analyses if analysis.general_score is not None]
    
    # Count verdict types
    verdict_counts = {}
    for v in verdicts:
        verdict_counts[v] = verdict_counts.get(v, 0) + 1
    
    avg_score = sum(general_scores) / len(general_scores) if general_scores else 50
    
    # Determine tier based on verdict patterns and average score
    if "Slop Coder" in verdict_counts and verdict_counts["Slop Coder"] >= len(verdicts) * 0.7:
        tier = "F"
    elif verdict_counts.get("Slop Coder", 0) >= len(verdicts) * 0.5:
        tier = "D"
    elif verdict_counts.get("Junior", 0) >= len(verdicts) * 0.5:
        tier = "C" if avg_score < 60 else "B"
    elif verdict_counts.get("Senior", 0) >= len(verdicts) * 0.7:
        tier = "A" if avg_score >= 75 else "B"
    elif verdict_counts.get("Good AI Coder", 0) >= len(verdicts) * 0.7:
        tier = "B" if avg_score >= 70 else "C"
    else:
        # Mixed verdicts - use average score
        if avg_score >= 85: tier = "S"
        elif avg_score >= 70: tier = "A"
        elif avg_score >= 55: tier = "B"
        elif avg_score >= 40: tier = "C"
        elif avg_score >= 20: tier = "D"
        else: tier = "F"
    
    summary_lines = [
        f"Profile Analysis Summary ({len(repos_analyses)} repos analyzed):",
        f"Average General Score: {avg_score:.1f}/100",
        f"Verdict Distribution: {', '.join([f'{k}: {v}' for k, v in sorted(verdict_counts.items())])}",
        "",
        f"Tier: {tier}",
        f"The developer demonstrates the following patterns across their repositories: {', '.join(set(verdicts))}.",
    ]
    
    profile_summary = "\n".join(summary_lines)
    return tier, profile_summary


def save_profile_evaluation(
    session: Session,
    user_id: int,
    tier: str,
    profile_summary: str,
    repos_analyzed: list[Repo],
    repos_analyses: list[RepoAnalysis],
):
    """
    Saves profile evaluation results to the database.
    """
    from models import ProfileEvaluation
    
    # Build repo analyses context
    repo_analyses_context = []
    for repo, analysis in zip(repos_analyzed, repos_analyses):
        repo_analyses_context.append({
            "url": repo.github_link,
            "name": repo.repo_name,
            "verdict": analysis.verdict_type,
            "verdict_confidence": analysis.verdict_confidence,
            "ai_slop_score": analysis.ai_slop_score,
            "bad_practices_score": analysis.bad_practices_score,
            "code_quality_score": analysis.code_quality_score,
            "general_score": analysis.general_score,
        })
    
    profile_evaluation = ProfileEvaluation(
        user_id=user_id,
        tier=tier,
        profile_summary=profile_summary,
        top_repos_analyzed=json.dumps([repo.github_link for repo in repos_analyzed]),
        repo_analyses_context=json.dumps(repo_analyses_context),
    )
    session.add(profile_evaluation)
    session.flush()
    return profile_evaluation