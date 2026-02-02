"""
Anti-Soy V2 API Schema Definitions

Pydantic models defining the API contract for all V2 endpoints.
These models are the source of truth for what the backend returns.
"""

from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


# =============================================================================
# ENUMS
# =============================================================================

class Severity(str, Enum):
    """Severity level for findings"""
    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"


class Confidence(str, Enum):
    """Confidence level for AI detection"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


# =============================================================================
# SHARED MODELS
# =============================================================================

class Finding(BaseModel):
    """A single finding/issue detected in the code"""
    type: str = Field(..., description="Type of finding (e.g., 'no_input_validation', 'redundant_comment')")
    severity: Severity = Field(..., description="How serious this finding is")
    file: str = Field(..., description="Relative path to the file")
    line: int = Field(..., description="Line number where the issue was found")
    snippet: str = Field(..., description="Code snippet showing the issue")
    explanation: str = Field(..., description="Plain-English explanation of why this is a problem")


class PositiveSignal(BaseModel):
    """A positive signal found in the code (good practice indicator)"""
    type: str = Field(..., description="Type of positive signal (e.g., 'ai_instruction_file', 'design_docs')")
    file: str | None = Field(None, description="File path if applicable")
    explanation: str = Field(..., description="Why this is a positive signal")


class FileAnalyzed(BaseModel):
    """Info about a file that was analyzed"""
    path: str = Field(..., description="Relative path to the file")
    importance_score: int = Field(..., ge=0, le=100, description="How important this file is (0-100)")
    loc: int = Field(..., ge=0, description="Lines of code in the file")


# =============================================================================
# REPO INFO
# =============================================================================

class RepoInfo(BaseModel):
    """Basic repository metadata"""
    url: str = Field(..., description="Full GitHub URL")
    name: str = Field(..., description="Repository name")
    owner: str = Field(..., description="Repository owner/organization")
    languages: dict[str, int] = Field(default_factory=dict, description="Language -> bytes mapping")
    analyzed_at: datetime = Field(..., description="When the analysis was performed")


# =============================================================================
# VERDICT
# =============================================================================

class Verdict(BaseModel):
    """
    Overall verdict about the candidate based on all signals.
    
    Possible types:
    - "Slop Coder": High AI slop, high bad practices, low quality
    - "Junior": Medium-high AI usage, low bad practices, low-mid quality
    - "Senior": Low-mid AI, low bad practices, high quality
    - "Good Use of AI": High AI, low bad practices, mid-high quality
    """
    type: str = Field(..., description="Verdict category (e.g., 'Slop Coder', 'Senior', 'Good Use of AI')")
    confidence: int = Field(..., ge=0, le=100, description="Confidence score 0-100")


# =============================================================================
# AI SLOP ANALYZER
# =============================================================================

class StyleFeatures(BaseModel):
    """
    LPcodedec-style features for AI detection.
    10 core features from research + 4 custom additions.
    """
    # Core LPcodedec features (10)
    function_naming_consistency: float = Field(..., ge=0, le=1, description="Ratio of dominant naming style for functions")
    variable_naming_consistency: float = Field(..., ge=0, le=1, description="Ratio of dominant naming style for variables")
    class_naming_consistency: float = Field(..., ge=0, le=1, description="Ratio of dominant naming style for classes")
    constant_naming_consistency: float = Field(..., ge=0, le=1, description="Ratio of dominant naming style for constants")
    indentation_consistency: float = Field(..., ge=0, le=1, description="Ratio of most common indent vs total indented lines")
    avg_function_length: float = Field(..., ge=0, description="Average lines of code per function")
    avg_nesting_depth: float = Field(..., ge=0, description="Average nesting level")
    comment_ratio: float = Field(..., ge=0, le=1, description="Comment lines / total lines")
    avg_function_name_length: float = Field(..., ge=0, description="Average character length of function names")
    avg_variable_name_length: float = Field(..., ge=0, description="Average character length of variable names")
    
    # Our custom additions (4)
    max_function_length: int = Field(..., ge=0, description="Longest function in LOC (god function detection)")
    max_nesting_depth: int = Field(..., ge=0, description="Deepest nesting level (complexity red flag)")
    docstring_coverage: float = Field(..., ge=0, le=1, description="Percentage of functions with docstrings")
    redundant_comment_count: int = Field(..., ge=0, description="Number of redundant/obvious comments")


class AISlop(BaseModel):
    """AI Slop Detector results"""
    score: int = Field(..., ge=0, le=100, description="AI slop score (higher = more AI-like)")
    confidence: Confidence = Field(..., description="Confidence in the detection")
    style_features: StyleFeatures = Field(..., description="All 14 style features extracted")
    negative_ai_signals: list[Finding] = Field(default_factory=list, description="Signs of AI-generated code without understanding")
    positive_ai_signals: list[PositiveSignal] = Field(default_factory=list, description="Signs of disciplined AI usage or manual code")


# =============================================================================
# BAD PRACTICES ANALYZER
# =============================================================================

class BadPractices(BaseModel):
    """Bad Practices Detector results"""
    score: int = Field(..., ge=0, le=100, description="Bad practices score (higher = worse)")
    
    # Category breakdowns (counts of issues found)
    security_issues: int = Field(..., ge=0, description="Count of security issues (SQL injection, hardcoded secrets, CORS, etc.)")
    robustness_issues: int = Field(..., ge=0, description="Count of robustness issues (no timeouts, silent errors, no retry, etc.)")
    hygiene_issues: int = Field(..., ge=0, description="Count of hygiene issues (.env committed, print statements, etc.)")
    
    # All findings with evidence
    findings: list[Finding] = Field(default_factory=list, description="All bad practice findings with code snippets")


# =============================================================================
# CODE QUALITY ANALYZER
# =============================================================================

class CodeQuality(BaseModel):
    """Code Quality Analyzer results"""
    score: int = Field(..., ge=0, le=100, description="Code quality score (higher = better)")
    
    # Individual metric scores (0-100 each)
    files_organized: int = Field(..., ge=0, le=100, description="How well organized the file structure is")
    test_coverage: int = Field(..., ge=0, le=100, description="Test presence and quality score")
    readme_quality: int = Field(..., ge=0, le=100, description="README completeness and clarity")
    error_handling: int = Field(..., ge=0, le=100, description="Quality of error handling patterns")
    logging_quality: int = Field(..., ge=0, le=100, description="Logging vs print usage quality")
    dependency_health: int = Field(..., ge=0, le=100, description="Dependency management quality")
    
    # All findings with evidence
    findings: list[Finding] = Field(default_factory=list, description="Quality issues and areas for improvement")


# =============================================================================
# FULL ANALYSIS RESPONSE
# =============================================================================

class AnalysisResponse(BaseModel):
    """
    Complete analysis response for POST /analyze endpoint.
    This is the main output of the V2 analysis pipeline.
    """
    repo: RepoInfo = Field(..., description="Repository metadata")
    verdict: Verdict = Field(..., description="Overall verdict with confidence")
    ai_slop: AISlop = Field(..., description="AI Slop Detector results")
    bad_practices: BadPractices = Field(..., description="Bad Practices Detector results")
    code_quality: CodeQuality = Field(..., description="Code Quality Analyzer results")
    files_analyzed: list[FileAnalyzed] = Field(default_factory=list, description="Top 10-15 files that were analyzed")


# =============================================================================
# INTERVIEW QUESTIONS ENDPOINT
# =============================================================================

class InterviewQuestion(BaseModel):
    """A generated interview question based on analysis findings"""
    question: str = Field(..., description="The interview question to ask")
    based_on: str = Field(..., description="Reference to the finding that prompted this question")
    probes: str = Field(..., description="What skill/knowledge this question probes (e.g., 'input_validation', 'defensive_coding')")


class InterviewQuestionsRequest(BaseModel):
    """Request body for POST /interview-questions endpoint"""
    repo_id: int = Field(..., description="ID of the repo to generate questions for")


class InterviewQuestionsResponse(BaseModel):
    """Response for POST /interview-questions endpoint"""
    repo_id: int = Field(..., description="ID of the repo")
    repo_url: str = Field(..., description="URL of the repo")
    questions: list[InterviewQuestion] = Field(default_factory=list, description="Generated interview questions")


# =============================================================================
# REQUEST MODELS
# =============================================================================

class AnalyzeRequest(BaseModel):
    """Request body for POST /analyze endpoint"""
    repo_url: str = Field(..., description="Full GitHub URL to analyze (e.g., https://github.com/user/repo)")
