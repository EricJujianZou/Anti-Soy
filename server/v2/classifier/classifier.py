"""
AI Code Classifier for Anti-Soy V2

Loads trained RandomForest model to classify code as human vs AI-generated.
Model must be trained separately using classifier_training_guide.md.
"""

import json
from pathlib import Path
from typing import NamedTuple

# Try to import joblib (for loading sklearn models)
try:
    import joblib
    JOBLIB_AVAILABLE = True
except ImportError:
    JOBLIB_AVAILABLE = False


# =============================================================================
# CONFIGURATION
# =============================================================================

# Model files (relative to this file's directory)
MODEL_DIR = Path(__file__).parent
MODEL_FILE = MODEL_DIR / "ai_code_classifier.joblib"
SCALER_FILE = MODEL_DIR / "feature_scaler.joblib"
FEATURE_NAMES_FILE = MODEL_DIR / "feature_names.json"


# =============================================================================
# DATA CLASSES
# =============================================================================

class ClassifierResult(NamedTuple):
    """Result from the AI code classifier."""
    ai_probability: float  # 0.0 = human, 1.0 = AI
    confidence: str        # "low", "medium", "high"
    is_ai: bool           # True if ai_probability > 0.5


# =============================================================================
# CLASSIFIER CLASS
# =============================================================================

class AICodeClassifier:
    """
    Classifier to detect AI-generated code.
    
    Uses a trained RandomForest model on LPcodedec-style features.
    Falls back to heuristic scoring if model not available.
    """
    
    def __init__(self):
        self.model = None
        self.scaler = None
        self.feature_names = None
        self.model_loaded = False
        
        self._load_model()
    
    def _load_model(self):
        """Load trained model files if available."""
        if not JOBLIB_AVAILABLE:
            print("Warning: joblib not installed. Using heuristic fallback.")
            return
        
        if not MODEL_FILE.exists():
            print(f"Warning: Model file not found at {MODEL_FILE}. Using heuristic fallback.")
            return
        
        try:
            self.model = joblib.load(MODEL_FILE)
            
            if SCALER_FILE.exists():
                self.scaler = joblib.load(SCALER_FILE)
            
            if FEATURE_NAMES_FILE.exists():
                with open(FEATURE_NAMES_FILE, 'r') as f:
                    self.feature_names = json.load(f)
            
            self.model_loaded = True
            print(f"AI classifier model loaded successfully.")
            
        except Exception as e:
            print(f"Warning: Failed to load model: {e}. Using heuristic fallback.")
    
    def predict(self, features: dict) -> ClassifierResult:
        """
        Predict if code is AI-generated based on extracted features.
        
        Args:
            features: Dictionary with feature names as keys
                     (output from feature_extractor.features_to_dict)
        
        Returns:
            ClassifierResult with probability, confidence, and binary prediction
        """
        if self.model_loaded:
            return self._predict_with_model(features)
        else:
            return self._predict_heuristic(features)
    
    def _predict_with_model(self, features: dict) -> ClassifierResult:
        """Use trained ML model for prediction."""
        # Map from our feature_extractor names to training names
        # Training used: func_, var_, const_, avg_func_name_length, avg_var_name_length
        # Our extractor uses: function_, variable_, constant_, avg_function_name_length, avg_variable_name_length
        feature_mapping = {
            'func_naming_consistency': 'function_naming_consistency',
            'var_naming_consistency': 'variable_naming_consistency',
            'class_naming_consistency': 'class_naming_consistency',
            'const_naming_consistency': 'constant_naming_consistency',
            'indentation_consistency': 'indentation_consistency',
            'avg_function_length': 'avg_function_length',
            'avg_nesting_depth': 'avg_nesting_depth',
            'comment_ratio': 'comment_ratio',
            'avg_func_name_length': 'avg_function_name_length',
            'avg_var_name_length': 'avg_variable_name_length',
        }
        
        # Use the order from training (self.feature_names from json, or default)
        training_order = self.feature_names or [
            'func_naming_consistency',
            'var_naming_consistency',
            'class_naming_consistency',
            'const_naming_consistency',
            'indentation_consistency',
            'avg_function_length',
            'avg_nesting_depth',
            'comment_ratio',
            'avg_func_name_length',
            'avg_var_name_length',
        ]
        
        feature_vector = []
        for train_name in training_order:
            our_name = feature_mapping.get(train_name, train_name)
            feature_vector.append(features.get(our_name, 0.0))
        
        # Scale if scaler available
        if self.scaler:
            feature_vector = self.scaler.transform([feature_vector])[0]
        
        # Predict
        proba = self.model.predict_proba([feature_vector])[0]
        ai_prob = proba[1]  # Probability of class 1 (AI)
        
        # Determine confidence
        if ai_prob < 0.3 or ai_prob > 0.7:
            confidence = "high"
        elif ai_prob < 0.4 or ai_prob > 0.6:
            confidence = "medium"
        else:
            confidence = "low"
        
        return ClassifierResult(
            ai_probability=round(ai_prob, 3),
            confidence=confidence,
            is_ai=ai_prob > 0.5
        )
    
    def _predict_heuristic(self, features: dict) -> ClassifierResult:
        """
        Fallback heuristic when model not available.
        
        Based on research findings:
        - AI code has MORE consistent naming (uses narrow vocabulary)
        - AI code has MORE comments (especially redundant ones)
        - AI code has LONGER variable names
        """
        score = 0.0
        factors = 0
        
        # High naming consistency suggests AI (uses templates)
        func_consistency = features.get('function_naming_consistency', 0.5)
        var_consistency = features.get('variable_naming_consistency', 0.5)
        
        if func_consistency > 0.9:
            score += 0.15
        if var_consistency > 0.9:
            score += 0.15
        factors += 2
        
        # High comment ratio suggests AI
        comment_ratio = features.get('comment_ratio', 0.1)
        if comment_ratio > 0.25:
            score += 0.2
        elif comment_ratio > 0.15:
            score += 0.1
        factors += 1
        
        # Redundant comments are strong AI signal
        redundant = features.get('redundant_comment_count', 0)
        if redundant > 5:
            score += 0.25
        elif redundant > 2:
            score += 0.15
        elif redundant > 0:
            score += 0.05
        factors += 1
        
        # Longer variable names suggest AI (verbose naming)
        avg_var_len = features.get('avg_variable_name_length', 8)
        if avg_var_len > 15:
            score += 0.15
        elif avg_var_len > 12:
            score += 0.08
        factors += 1
        
        # Very consistent indentation (always 4 spaces) suggests AI
        indent_consistency = features.get('indentation_consistency', 0.8)
        if indent_consistency > 0.95:
            score += 0.1
        factors += 1
        
        # Normalize
        ai_prob = min(score, 1.0)
        
        # Determine confidence (heuristic is always lower confidence)
        if ai_prob < 0.25 or ai_prob > 0.75:
            confidence = "medium"
        else:
            confidence = "low"
        
        return ClassifierResult(
            ai_probability=round(ai_prob, 3),
            confidence=confidence,
            is_ai=ai_prob > 0.5
        )


# =============================================================================
# MODULE-LEVEL INSTANCE
# =============================================================================

# Singleton classifier instance
_classifier: AICodeClassifier | None = None


def get_classifier() -> AICodeClassifier:
    """Get or create the singleton classifier instance."""
    global _classifier
    if _classifier is None:
        _classifier = AICodeClassifier()
    return _classifier


def predict_ai_code(features: dict) -> ClassifierResult:
    """
    Convenience function to predict if code is AI-generated.
    
    Args:
        features: Dictionary from feature_extractor.features_to_dict()
    
    Returns:
        ClassifierResult with ai_probability, confidence, is_ai
    """
    return get_classifier().predict(features)
