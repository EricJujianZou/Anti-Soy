"""
LLM-based resume project extraction and description-level repo matching.

Calls Gemini Flash with both the resume text and the candidate's GitHub repo list.
Returns extracted projects with description-based confidence scores for repo matches.
These scores feed into Step 4 (algorithmic scoring in matcher.py) as the
description_similarity signal — they are NOT the final match confidence.
"""
import json
import logging

from v2.gemini_client import get_gemini_client
from .config import LLM_MODEL

logger = logging.getLogger(__name__)

# Note: double-braces {{ }} are escaped braces in the format string.
_PROMPT_TEMPLATE = """\
You are given a candidate's resume text and a list of their public GitHub repositories.

Your job is to:
1. Extract all software projects from the resume. For each project return:
   - name: the project name exactly as written in the resume
   - description: one sentence summary based on the resume text

2. For each extracted project, review the GitHub repos and decide whether any repo
   is likely the same project based on DESCRIPTION SIMILARITY ONLY (not name or tech).
   If a repo matches, provide a description_confidence score from 0.0 to 1.0.
   If no repo matches on description, set matched_repo to null.

   Scoring calibration — use these anchors:
   - 0.9+  = Almost certainly the same project. Core concept matches even if phrased very
             differently. e.g. repo "garbage-robot" for resume "autonomous obstacle detection
             vehicle" — both describe the same robotic system.
   - 0.75  = Very likely the same project. Key themes clearly overlap.
   - 0.55  = Probably the same project. Partial overlap, some uncertainty.
   - 0.3   = Possibly related but likely different projects.
   - 0.0   = Unrelated.

   IMPORTANT: Repo descriptions are often short and informal. Score by conceptual
   equivalence, not literal word overlap. A terse repo description like "autonomous
   garbage collector" CAN be a 0.9 match for a resume entry describing a full autonomous
   robotics navigation system — if they describe the same core project.

   Each repo should match at most one project. When two projects could match the same
   repo by description, assign it to the stronger match only.

Return ONLY valid JSON. No preamble. No markdown fences. Use this exact format:

{{
  "projects": [
    {{
      "name": "...",
      "description": "...",
      "matched_repo": {{
        "repo_name": "...",
        "description_confidence": 0.0
      }}
    }}
  ]
}}

Set matched_repo to null if there is no description-based match.
If no projects are found in the resume, return: {{"projects": []}}

Resume:
{resume_text}

GitHub Repos:
{repo_list_json}
"""


async def extract_and_match_projects(resume_text: str, repos: list[dict]) -> list[dict]:
    """
    Call Gemini Flash to extract resume projects and score description-based repo matches.

    Returns a list of project dicts, each containing:
      - name: str
      - description: str
      - tech_stack: list[str]
      - matched_repo: {repo_name: str, description_confidence: float} | None

    Returns [] and logs a warning if the Gemini client is unavailable.
    Raises RuntimeError if both JSON parse attempts fail.
    """
    try:
        client = get_gemini_client()
    except RuntimeError:
        logger.warning("Gemini client unavailable — skipping LLM project extraction")
        return []

    repo_summaries = [
        {
            "name": r.get("name"),
            "description": r.get("description") or "",
            "language": r.get("language") or "",
            "topics": r.get("topics", []),
        }
        for r in repos
    ]

    prompt = _PROMPT_TEMPLATE.format(
        resume_text=resume_text,
        repo_list_json=json.dumps(repo_summaries, indent=2),
    )

    last_error: Exception | None = None
    for attempt in range(2):
        try:
            response = await client.aio.models.generate_content(
                model=LLM_MODEL,
                contents=prompt,
            )
            raw = response.text.strip()

            # Strip markdown code fences in case the model wraps the output
            if raw.startswith("```"):
                parts = raw.split("```")
                raw = parts[1] if len(parts) > 1 else raw
                if raw.startswith("json"):
                    raw = raw[4:]
                raw = raw.strip()

            data = json.loads(raw)
            return data.get("projects", [])

        except json.JSONDecodeError as exc:
            logger.warning(f"LLM JSON parse failed (attempt {attempt + 1}/2): {exc}")
            last_error = exc
        except Exception as exc:
            logger.error(f"LLM call failed (attempt {attempt + 1}/2): {exc}")
            last_error = exc
            break  # Non-parse errors are unlikely to succeed on retry

    raise RuntimeError(f"LLM extraction failed after retries: {last_error}")
