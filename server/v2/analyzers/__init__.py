"""
Anti-Soy V2 Analyzers

Three analyzers that consume extracted data and produce analysis results:
- AI Slop Analyzer: Detects AI-generated code patterns
- Bad Practices Analyzer: Finds security/robustness/hygiene issues
- Code Quality Analyzer: Assesses engineering maturity
"""

from .ai_slop import analyze_ai_slop, AISlopAnalyzer

__all__ = [
    "analyze_ai_slop",
    "AISlopAnalyzer",
]
