"""
AI Code Classifier module.

Exports:
    - AICodeClassifier: Main classifier class
    - predict_ai_code: Convenience function for prediction
    - ClassifierResult: Named tuple with prediction results
"""

from .classifier import AICodeClassifier, predict_ai_code, ClassifierResult, get_classifier

__all__ = [
    "AICodeClassifier",
    "predict_ai_code", 
    "ClassifierResult",
    "get_classifier",
]
