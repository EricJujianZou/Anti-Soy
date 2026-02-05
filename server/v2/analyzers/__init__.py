"""
Anti-Soy V2 Analyzers

Three analyzers that consume extracted data and produce analysis results:
- AI Slop Analyzer: Detects AI-generated code patterns
- Bad Practices Analyzer: Finds security/robustness/hygiene issues
- Code Quality Analyzer: Assesses engineering maturity
"""

from .ai_slop import analyze_ai_slop, AISlopAnalyzer
from .bad_practices import analyze_bad_practices, BadPracticesAnalyzer

__all__ = [
    "analyze_ai_slop",
    "AISlopAnalyzer",
    "analyze_bad_practices",
    "BadPracticesAnalyzer",
]
