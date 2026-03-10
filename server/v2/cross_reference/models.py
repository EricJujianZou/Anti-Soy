"""
Pydantic models for the cross_reference module.
"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class CandidateInput(BaseModel):
    """
    Input for a single candidate to be cross-referenced.

    NOTE: resume_text must be populated by an upstream PDF intake / parsing layer.
    As of this implementation it is a required placeholder that must be wired in
    before the LLM-based project extraction (Step 3) can function correctly.
    """

    name: str = Field(..., description="Candidate's full name")
    github: str = Field(..., description="GitHub profile URL — any supported format")
    pages: list[int] = Field(
        default_factory=list,
        description="PDF pages where this candidate appears (pass-through, not used by this module)",
    )
    confidence: str = Field(
        ...,
        description=(
            "How confident the upstream layer is that this GitHub URL belongs to the candidate. "
            "Only 'high' confidence candidates are processed; others are flagged for manual review."
        ),
    )
    resume_text: str = Field(
        ...,
        description="Full raw resume text. Must be supplied by the upstream PDF parsing layer.",
    )


class MatchSignals(BaseModel):
    name_similarity: float = Field(..., ge=0.0, le=1.0)
    description_similarity: float = Field(..., ge=0.0, le=1.0)
    tech_stack_overlap: float = Field(..., ge=0.0, le=1.0)


class ResumeProject(BaseModel):
    name: str
    description: str
    tech_stack: list[str] = Field(default_factory=list)


class MatchedProject(BaseModel):
    resume_project_name: str
    repo_name: str
    repo_url: str = Field(..., description="Full URL: https://github.com/{username}/{repo}")
    confidence: float = Field(..., ge=0.0, le=1.0)
    match_signals: MatchSignals


class UnmatchedProject(BaseModel):
    name: str
    description: str
    reason: str  # "no_matching_repo_found" | "outbid_by_higher_confidence_match"
    best_confidence: float = Field(
        default=0.0,
        description="Highest confidence score this project achieved against any repo (below threshold)",
    )
    best_repo_name: Optional[str] = Field(
        default=None,
        description="Repo that produced best_confidence — useful for diagnosing near-misses",
    )


class PersonObject(BaseModel):
    github_username: str
    github_url: str
    resume_projects: list[ResumeProject] = Field(default_factory=list)
    matched_projects: list[MatchedProject] = Field(default_factory=list)
    unmatched_projects: list[UnmatchedProject] = Field(default_factory=list)
    match_summary: str = Field(default="0/0 verified")
    repos_to_clone: list[str] = Field(
        default_factory=list,
        description="Full repo URLs to pass to downstream cloning and analysis",
    )
    flags: list[str] = Field(default_factory=list)
    error: Optional[str] = None
