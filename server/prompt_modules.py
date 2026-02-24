"""
Modular Prompt Assembly for Anti-Soy V2 LLM Evaluation

Builds evaluation and interview prompts dynamically based on user-selected
priorities. Replaces the old monolithic hardcoded prompts.

Priority modules: code_quality, security, originality, production_readiness, ai_detection
"""

import json

ALL_PRIORITIES = [
    "code_quality",
    "security",
    "originality",
    "production_readiness",
    "ai_detection",
]


# =============================================================================
# BASE PROMPT (always included)
# =============================================================================

BASE_EVALUATION_PROMPT = """You are a senior technical interviewer evaluating a GitHub project.

REPOSITORY INFO:
- URL: {repo_url}
- Name: {repo_name}
- AI Slop Score: {ai_score}/100 (higher = more AI-generated)
- Bad Practices Score: {bad_practices_score}/100 (higher = worse)
- Code Quality Score: {quality_score}/100 (higher = better)

FILE STRUCTURE:
{file_tree}

CODE FINDINGS (with file locations and code snippets):
{findings_context}

EVALUATION PRIORITIES:
You are evaluating this project with the following priorities selected by the reviewer: {priority_names}.
Weight your analysis accordingly — focus your attention on the selected criteria.
"""


# =============================================================================
# PRIORITY MODULES — EVALUATION
# =============================================================================

PRIORITY_MODULE_CODE_QUALITY = """
CODE QUALITY CRITERIA (HIGH PRIORITY):
Evaluate these signals with high weight:
- Consistent error handling patterns across the codebase
- Clear separation of concerns and well-defined architecture
- Readable naming conventions that follow language idioms (not writing Java-style Go, etc.)
- Reasonable file sizes and logical module organization
- Meaningful comments where needed (not redundant ones)
- DRY principles applied without over-abstraction
- Appropriate use of the language's type system and idioms

Standout bar for code quality: "Code that a senior engineer would approve in code review without major revisions."
"""

PRIORITY_MODULE_SECURITY = """
SECURITY CRITERIA (HIGH PRIORITY):
Evaluate these signals with high weight:
- Input validation and sanitization at system boundaries
- Authentication and authorization implementation quality
- SQL injection prevention (parameterized queries, ORM usage)
- XSS prevention (output encoding, CSP headers)
- Secrets management (no hardcoded API keys, tokens, or passwords)
- Dependency vulnerability awareness (lock files, pinned versions)
- Safe regex patterns (no ReDoS vulnerabilities)
- Timeout handling on external requests and database calls

Standout bar for security: "Code that would pass a basic security audit."
"""

PRIORITY_MODULE_ORIGINALITY = """
ORIGINALITY CRITERIA (HIGH PRIORITY):
Evaluate these signals with high weight:
- Does this project solve a real user problem (not a tutorial project)?
- Is the approach novel or differentiated from common implementations?
- Is there evidence of original thinking vs following a tutorial step-by-step?
- Compare against common project types in the same language/domain, not a universal baseline.

Standout bar for originality: "A project that shows independent problem-solving, not just following instructions."
"""

PRIORITY_MODULE_PRODUCTION_READINESS = """
PRODUCTION READINESS CRITERIA (HIGH PRIORITY):
Evaluate these signals with high weight:
- Test coverage presence and quality (unit, integration, e2e)
- CI/CD configuration (GitHub Actions, Jenkins, etc.)
- Environment configuration and config management (not hardcoded values)
- Logging and observability (structured logging, metrics, tracing)
- Dockerfile or deployment configuration
- Database migration patterns
- Rate limiting and retry logic for external services
- Documentation quality (README, API docs, setup instructions)

Standout bar for production readiness: "Code that could be deployed to production with minimal additional work."
"""

PRIORITY_MODULE_AI_DETECTION = """
AI DETECTION CRITERIA (HIGH PRIORITY):
Evaluate these signals with high weight:
- Redundant comment patterns (comments that restate the code)
- Emoji usage in code comments or variable names
- Overly verbose or unnaturally descriptive variable names
- Generic boilerplate patterns that look template-generated
- Consistency of coding style (AI-generated code often has uniform style across all files)
- Whether the code shows evidence of iterative development vs one-shot generation

Consider the ML classifier confidence score ({ai_score}/100) alongside your own assessment.
"""


# =============================================================================
# STANDOUT FEATURES CALIBRATION
# =============================================================================

STANDOUT_CALIBRATION = """
STANDOUT FEATURES INSTRUCTIONS:
- Return 0-3 short headlines about genuinely impressive aspects.
- Calibrate the bar to the project's apparent scope and the selected priorities.
- The "nothing stands out" verdict should be RARE for mature, production-grade codebases.
- When evaluating, consider: if the heuristic scores indicate senior-level work (low AI score, low bad practices, high quality) and the project solves a real problem, you MUST identify specific standout features unless you have strong evidence to the contrary.
- Each headline: 1 short punchy sentence max. Written for a busy hiring manager scanning candidates.
"""


# =============================================================================
# OUTPUT FORMAT (always included)
# =============================================================================

OUTPUT_FORMAT_EVALUATION = """
Respond with a JSON object containing TWO parts:

{
  "business_value": {
    "solves_real_problem": true/false,
    "project_type": "real_problem" | "tutorial" | "portfolio_demo" | "learning_exercise" | "utility_tool",
    "project_description": "One sentence describing what this project does",
    "originality_assessment": "What makes this unique or generic, calibrated to the project's domain",
    "project_summary": "2-3 sentence executive summary for a hiring manager",
    "project_scope_estimate": "hobby" | "coursework" | "professional" | "production_oss"
  },
  "standout_features": [
    "Short punchy headline about something genuinely impressive"
  ]
}

Return ONLY the JSON object, no other text or markdown formatting."""


# =============================================================================
# INTERVIEW QUESTION MODULES
# =============================================================================

BASE_QUESTIONS_PROMPT = """You are a senior technical interviewer. Generate interview questions for a candidate about their GitHub project.

REPOSITORY INFO:
- URL: {repo_url}
- Name: {repo_name}
- AI Slop Score: {ai_score}/100 (higher = more AI-generated)
- Bad Practices Score: {bad_practices_score}/100 (higher = worse)
- Code Quality Score: {quality_score}/100 (higher = better)

FILE STRUCTURE:
{file_tree}

CODE FINDINGS (with file locations and code snippets):
{findings_context}

EVALUATION PRIORITIES: {priority_names}
Tailor your questions to probe the candidate's understanding in the areas that matter most for this evaluation.

GENERAL INSTRUCTIONS:
1. Questions must require the candidate to EXPLAIN THEIR OWN CODE — not recite textbook answers.
2. Do NOT reference specific file paths or line numbers in the question text.
3. Do NOT ask about AI-generated code signals, emojis, or redundant comments directly.
4. Do NOT generate generic questions about print statements, logging, or unit tests unless directly relevant to a selected priority and a specific finding.
"""

QUESTIONS_MODULE_CODE_QUALITY = """
CODE QUALITY QUESTIONS:
Generate at least 1 question probing:
- Design decisions and trade-offs ("Why did you structure it this way?")
- Architecture choices ("Walk me through how X module interacts with Y")
- Refactoring rationale ("If you had to simplify this, what would you change?")
"""

QUESTIONS_MODULE_SECURITY = """
SECURITY QUESTIONS:
Generate at least 1 question probing:
- Threat model awareness ("What attack vectors did you consider for this endpoint?")
- Specific security implementation ("How does your auth system prevent X?")
- Vulnerability response ("If someone reported a SQL injection here, how would you fix it?")
"""

QUESTIONS_MODULE_ORIGINALITY = """
ORIGINALITY QUESTIONS:
Generate at least 1 question probing:
- Problem discovery ("How did you identify this as a problem worth solving?")
- Alternative approaches ("What other solutions did you consider before building this?")
- User research ("Who uses this and how did you validate the approach?")
"""

QUESTIONS_MODULE_PRODUCTION_READINESS = """
PRODUCTION READINESS QUESTIONS:
Generate at least 1 question probing:
- Deployment process ("Walk me through how this gets deployed")
- Scaling considerations ("What happens when traffic 10x's?")
- Monitoring and incidents ("How would you know if this broke in production?")
"""

QUESTIONS_MODULE_AI_DETECTION = """
AI DETECTION QUESTIONS (the AI score is {ai_score}/100):
If AI score is high (≥60), generate at least 1 deep-understanding question:
- "Walk me through this function line by line — why did you choose this approach?"
- "What was the hardest bug you encountered while building this?"
- "If I asked you to rewrite this module from scratch right now, what would you do differently?"
These questions test whether the candidate truly wrote and understands the code.
"""

QUESTIONS_OUTPUT_FORMAT = """
Respond with a JSON object:

{
  "interview_questions": [
    {
      "question": "Natural interview question (no file:line references)",
      "based_on": "Which finding or aspect this is grounded in",
      "probes": "What skill this tests (e.g., 'security_awareness', 'system_design')",
      "category": "business_value" | "design_choice" | "code_issue" | "technical_depth"
    }
  ]
}

Generate 3-7 interview questions. Prioritize quality over quantity. Ensure a mix of categories relevant to the selected priorities.

Return ONLY the JSON object, no other text or markdown formatting."""


# =============================================================================
# ASSEMBLY FUNCTIONS
# =============================================================================

EVAL_MODULES = {
    "code_quality": PRIORITY_MODULE_CODE_QUALITY,
    "security": PRIORITY_MODULE_SECURITY,
    "originality": PRIORITY_MODULE_ORIGINALITY,
    "production_readiness": PRIORITY_MODULE_PRODUCTION_READINESS,
    "ai_detection": PRIORITY_MODULE_AI_DETECTION,
}

QUESTION_MODULES = {
    "code_quality": QUESTIONS_MODULE_CODE_QUALITY,
    "security": QUESTIONS_MODULE_SECURITY,
    "originality": QUESTIONS_MODULE_ORIGINALITY,
    "production_readiness": QUESTIONS_MODULE_PRODUCTION_READINESS,
    "ai_detection": QUESTIONS_MODULE_AI_DETECTION,
}


def _normalize_priorities(priorities: list[str] | None) -> list[str]:
    """Validate and normalize priorities. Defaults to all if None or empty."""
    if not priorities:
        return ALL_PRIORITIES
    valid = [p for p in priorities if p in ALL_PRIORITIES]
    return valid if valid else ALL_PRIORITIES


def _format_priority_names(priorities: list[str]) -> str:
    """Human-readable priority list for prompt injection."""
    names = {
        "code_quality": "Code Quality",
        "security": "Security",
        "originality": "Originality",
        "production_readiness": "Production Readiness",
        "ai_detection": "AI Detection",
    }
    return ", ".join(names.get(p, p) for p in priorities)


def build_evaluation_prompt(
    repo_url: str,
    repo_name: str,
    ai_slop_result,
    bad_practices_result,
    code_quality_result,
    file_tree: list[str],
    findings_context: list[dict],
    priorities: list[str] | None = None,
) -> str:
    """
    Assemble the evaluation prompt from base + selected priority modules + output format.
    """
    priorities = _normalize_priorities(priorities)
    priority_names = _format_priority_names(priorities)

    prompt_parts = []

    # Base prompt with repo context
    prompt_parts.append(BASE_EVALUATION_PROMPT.format(
        repo_url=repo_url,
        repo_name=repo_name,
        ai_score=ai_slop_result.score,
        bad_practices_score=bad_practices_result.score,
        quality_score=code_quality_result.score,
        file_tree=json.dumps(file_tree, indent=2),
        findings_context=json.dumps(findings_context, indent=2),
        priority_names=priority_names,
    ))

    # Selected priority modules
    for priority in priorities:
        module = EVAL_MODULES.get(priority, "")
        if priority == "ai_detection":
            module = module.format(ai_score=ai_slop_result.score)
        prompt_parts.append(module)

    # Standout calibration + output format
    prompt_parts.append(STANDOUT_CALIBRATION)
    prompt_parts.append(OUTPUT_FORMAT_EVALUATION)

    return "\n".join(prompt_parts)


def build_questions_prompt(
    repo_url: str,
    repo_name: str,
    ai_slop_result,
    bad_practices_result,
    code_quality_result,
    file_tree: list[str],
    findings_context: list[dict],
    priorities: list[str] | None = None,
) -> str:
    """
    Assemble the interview questions prompt from base + selected priority modules + output format.
    """
    priorities = _normalize_priorities(priorities)
    priority_names = _format_priority_names(priorities)

    prompt_parts = []

    # Base prompt with repo context
    prompt_parts.append(BASE_QUESTIONS_PROMPT.format(
        repo_url=repo_url,
        repo_name=repo_name,
        ai_score=ai_slop_result.score,
        bad_practices_score=bad_practices_result.score,
        quality_score=code_quality_result.score,
        file_tree=json.dumps(file_tree, indent=2),
        findings_context=json.dumps(findings_context, indent=2),
        priority_names=priority_names,
    ))

    # Selected question modules
    for priority in priorities:
        module = QUESTION_MODULES.get(priority, "")
        if priority == "ai_detection":
            module = module.format(ai_score=ai_slop_result.score)
        prompt_parts.append(module)

    # Output format
    prompt_parts.append(QUESTIONS_OUTPUT_FORMAT)

    return "\n".join(prompt_parts)
