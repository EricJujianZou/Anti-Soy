"""
Feature Extractor for Anti-Soy V2

Extracts the 14 LPcodedec-style features from repository code.
Uses regex-based extraction (no AST) per research methodology.

All features are numeric for ML classifier compatibility.
"""

import re
from dataclasses import dataclass, field
from enum import Enum

from .data_extractor import RepoData, EXTENSION_TO_LANGUAGE


# =============================================================================
# CONFIGURATION
# =============================================================================

# Languages we can extract features from (Python-like, C-like, etc.)
SUPPORTED_LANGUAGES = {
    "Python", "JavaScript", "TypeScript", "Java", "Go", "Ruby", 
    "Rust", "C++", "C", "C#", "PHP", "Swift", "Kotlin", "Scala"
}

# Redundant comment patterns (obvious comments that add no value)
# MVP: Pattern-based detection (LLM verification in deep analysis phase)
REDUNDANT_COMMENT_PATTERNS = [
    # Direct restatement patterns
    r"#\s*(increment|decrement|add|subtract)\s+\w+",
    r"#\s*(loop|iterate)\s+(through|over)",
    r"#\s*(set|assign|initialize)\s+\w+\s+(to|as|=)",
    r"#\s*(return|returns)\s+(the\s+)?\w+",
    r"#\s*(create|make|new)\s+(a\s+)?(new\s+)?\w+",
    r"#\s*(get|fetch|retrieve)\s+(the\s+)?\w+",
    r"#\s*(check|validate)\s+(if|whether)",
    r"#\s*(call|invoke)\s+\w+",
    r"#\s*(import|include)\s+\w+",
    r"#\s*(define|declare)\s+\w+",
    # C-style equivalents
    r"//\s*(increment|decrement|add|subtract)\s+\w+",
    r"//\s*(loop|iterate)\s+(through|over)",
    r"//\s*(set|assign|initialize)\s+\w+\s+(to|as|=)",
    r"//\s*(return|returns)\s+(the\s+)?\w+",
    r"//\s*(create|make|new)\s+(a\s+)?(new\s+)?\w+",
    r"//\s*(get|fetch|retrieve)\s+(the\s+)?\w+",
    r"//\s*(check|validate)\s+(if|whether)",
    r"//\s*(call|invoke)\s+\w+",
    r"//\s*(import|include)\s+\w+",
    r"//\s*(define|declare)\s+\w+",
]


# =============================================================================
# NAMING STYLE DETECTION
# =============================================================================

class NamingStyle(Enum):
    """Naming convention styles"""
    SNAKE_CASE = "snake_case"       # my_function
    CAMEL_CASE = "camelCase"        # myFunction
    PASCAL_CASE = "PascalCase"      # MyFunction
    UPPER_SNAKE = "UPPER_SNAKE"     # MY_CONSTANT
    KEBAB_CASE = "kebab-case"       # my-function (rare in code)
    UNKNOWN = "unknown"


def detect_naming_style(name: str) -> NamingStyle:
    """Detect the naming style of an identifier."""
    if not name or len(name) < 2:
        return NamingStyle.UNKNOWN
    
    # Skip dunder methods (__init__)
    if name.startswith("__") and name.endswith("__"):
        return NamingStyle.UNKNOWN
    
    # Check for UPPER_SNAKE_CASE (constants)
    if re.match(r'^[A-Z][A-Z0-9_]*$', name):
        return NamingStyle.UPPER_SNAKE
    
    # Check for PascalCase
    if re.match(r'^[A-Z][a-zA-Z0-9]*$', name) and not name.isupper():
        return NamingStyle.PASCAL_CASE
    
    # Check for snake_case
    if re.match(r'^[a-z][a-z0-9_]*$', name) and '_' in name:
        return NamingStyle.SNAKE_CASE
    
    # Check for camelCase
    if re.match(r'^[a-z][a-zA-Z0-9]*$', name) and any(c.isupper() for c in name):
        return NamingStyle.CAMEL_CASE
    
    # Check for lowercase (could be snake_case without underscores)
    if re.match(r'^[a-z][a-z0-9]*$', name):
        return NamingStyle.SNAKE_CASE  # Treat as snake_case
    
    # Check for kebab-case (rare)
    if re.match(r'^[a-z][a-z0-9-]*$', name) and '-' in name:
        return NamingStyle.KEBAB_CASE
    
    return NamingStyle.UNKNOWN


def calculate_consistency(names: list[str]) -> float:
    """
    Calculate naming consistency as ratio of dominant style to total.
    
    Returns:
        float: 0.0-1.0 where 1.0 means all names follow same style
    """
    if not names:
        return 1.0  # No names = perfectly consistent (vacuously true)
    
    # Count each style
    style_counts: dict[NamingStyle, int] = {}
    valid_count = 0
    
    for name in names:
        style = detect_naming_style(name)
        if style != NamingStyle.UNKNOWN:
            style_counts[style] = style_counts.get(style, 0) + 1
            valid_count += 1
    
    if valid_count == 0:
        return 1.0  # All unknown = can't measure
    
    # Ratio of dominant style
    max_count = max(style_counts.values())
    return max_count / valid_count


# =============================================================================
# EXTRACTION PATTERNS (Language-specific regex)
# =============================================================================

# Function definition patterns by language family
FUNCTION_PATTERNS = {
    # Python: def function_name(...):
    "Python": r'^\s*(?:async\s+)?def\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\(',
    
    # JavaScript/TypeScript: function name(), const name = () =>, etc.
    "JavaScript": r'(?:function\s+([a-zA-Z_$][a-zA-Z0-9_$]*)\s*\(|(?:const|let|var)\s+([a-zA-Z_$][a-zA-Z0-9_$]*)\s*=\s*(?:async\s*)?\()',
    "TypeScript": r'(?:function\s+([a-zA-Z_$][a-zA-Z0-9_$]*)\s*\(|(?:const|let|var)\s+([a-zA-Z_$][a-zA-Z0-9_$]*)\s*=\s*(?:async\s*)?\()',
    
    # Java/C#: public void methodName()
    "Java": r'(?:public|private|protected)?\s*(?:static\s+)?(?:\w+\s+)+([a-zA-Z_][a-zA-Z0-9_]*)\s*\(',
    "C#": r'(?:public|private|protected|internal)?\s*(?:static\s+)?(?:\w+\s+)+([a-zA-Z_][a-zA-Z0-9_]*)\s*\(',
    
    # Go: func functionName()
    "Go": r'func\s+(?:\([^)]+\)\s+)?([a-zA-Z_][a-zA-Z0-9_]*)\s*\(',
    
    # Ruby: def method_name
    "Ruby": r'def\s+([a-zA-Z_][a-zA-Z0-9_?!]*)',
    
    # Rust: fn function_name()
    "Rust": r'fn\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*[<(]',
    
    # C/C++: returnType functionName()
    "C": r'(?:\w+\s+)+([a-zA-Z_][a-zA-Z0-9_]*)\s*\([^;]*\)\s*\{',
    "C++": r'(?:\w+\s+)+([a-zA-Z_][a-zA-Z0-9_]*)\s*\([^;]*\)\s*\{',
    
    # PHP: function functionName()
    "PHP": r'function\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\(',
    
    # Swift: func functionName()
    "Swift": r'func\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*[<(]',
    
    # Kotlin: fun functionName()
    "Kotlin": r'fun\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*[<(]',
    
    # Scala: def functionName
    "Scala": r'def\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*[(\[]?',
}

# Variable assignment patterns
VARIABLE_PATTERNS = {
    # Python: var_name = 
    "Python": r'^\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*(?::\s*\w+)?\s*=(?!=)',
    
    # JavaScript/TypeScript: const/let/var name =
    "JavaScript": r'(?:const|let|var)\s+([a-zA-Z_$][a-zA-Z0-9_$]*)\s*(?::\s*\w+)?\s*=',
    "TypeScript": r'(?:const|let|var)\s+([a-zA-Z_$][a-zA-Z0-9_$]*)\s*(?::\s*[^=]+)?\s*=',
    
    # Java/C#: Type varName =
    "Java": r'(?:\w+(?:<[^>]+>)?)\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*=',
    "C#": r'(?:var|\w+(?:<[^>]+>)?)\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*=',
    
    # Go: varName := or var varName
    "Go": r'(?:([a-zA-Z_][a-zA-Z0-9_]*)\s*:=|var\s+([a-zA-Z_][a-zA-Z0-9_]*))',
    
    # Ruby: var_name =
    "Ruby": r'^\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*=(?!=)',
    
    # Rust: let varName
    "Rust": r'let\s+(?:mut\s+)?([a-zA-Z_][a-zA-Z0-9_]*)',
    
    # C/C++: type varName =
    "C": r'(?:\w+\s*\*?\s+)+([a-zA-Z_][a-zA-Z0-9_]*)\s*=',
    "C++": r'(?:\w+\s*[*&]?\s+)+([a-zA-Z_][a-zA-Z0-9_]*)\s*=',
}

# Class definition patterns
CLASS_PATTERNS = {
    "Python": r'^\s*class\s+([A-Za-z_][A-Za-z0-9_]*)',
    "JavaScript": r'class\s+([A-Za-z_$][A-Za-z0-9_$]*)',
    "TypeScript": r'(?:class|interface)\s+([A-Za-z_$][A-Za-z0-9_$]*)',
    "Java": r'(?:public\s+)?(?:class|interface|enum)\s+([A-Za-z_][A-Za-z0-9_]*)',
    "C#": r'(?:public\s+)?(?:class|interface|struct|enum)\s+([A-Za-z_][A-Za-z0-9_]*)',
    "Go": r'type\s+([A-Za-z_][A-Za-z0-9_]*)\s+struct',
    "Ruby": r'class\s+([A-Za-z_][A-Za-z0-9_]*)',
    "Rust": r'(?:struct|enum|trait)\s+([A-Za-z_][A-Za-z0-9_]*)',
    "PHP": r'class\s+([A-Za-z_][A-Za-z0-9_]*)',
    "Swift": r'(?:class|struct|protocol|enum)\s+([A-Za-z_][A-Za-z0-9_]*)',
    "Kotlin": r'(?:class|interface|object|enum class)\s+([A-Za-z_][A-Za-z0-9_]*)',
    "Scala": r'(?:class|trait|object)\s+([A-Za-z_][A-Za-z0-9_]*)',
}

# Docstring/documentation patterns
DOCSTRING_PATTERNS = {
    # Python: """ or '''
    "Python": r'^\s*(?:"""|\'\'\').*?(?:"""|\'\'\')|\s*(?:"""|\'\'\')[\s\S]*?(?:"""|\'\'\')$',
    
    # JSDoc style: /** ... */
    "JavaScript": r'/\*\*[\s\S]*?\*/',
    "TypeScript": r'/\*\*[\s\S]*?\*/',
    
    # Javadoc
    "Java": r'/\*\*[\s\S]*?\*/',
    
    # XML doc comments for C#
    "C#": r'///.*',
    
    # Go doc comments
    "Go": r'//\s*[A-Z][^\n]*',
    
    # Ruby rdoc
    "Ruby": r'#.*',
    
    # Rust doc comments
    "Rust": r'///.*|//!.*',
}


# =============================================================================
# FEATURE EXTRACTION DATACLASS
# =============================================================================

@dataclass
class ExtractedFeatures:
    """
    All 14 features extracted from a repository.
    Ready to be converted to StyleFeatures schema.
    """
    # Core LPcodedec features (10)
    function_naming_consistency: float = 0.0
    variable_naming_consistency: float = 0.0
    class_naming_consistency: float = 0.0
    constant_naming_consistency: float = 0.0
    indentation_consistency: float = 0.0
    avg_function_length: float = 0.0
    avg_nesting_depth: float = 0.0
    comment_ratio: float = 0.0
    avg_function_name_length: float = 0.0
    avg_variable_name_length: float = 0.0
    
    # Our custom additions (4)
    max_function_length: int = 0
    max_nesting_depth: int = 0
    docstring_coverage: float = 0.0
    redundant_comment_count: int = 0
    
    # Metadata (not features, but useful)
    files_processed: int = 0
    total_functions: int = 0
    total_variables: int = 0
    total_classes: int = 0


@dataclass
class FileFeatures:
    """Features extracted from a single file."""
    language: str
    
    # Names extracted
    function_names: list[str] = field(default_factory=list)
    variable_names: list[str] = field(default_factory=list)
    class_names: list[str] = field(default_factory=list)
    constant_names: list[str] = field(default_factory=list)
    
    # Metrics
    function_lengths: list[int] = field(default_factory=list)
    nesting_depths: list[int] = field(default_factory=list)
    indent_sizes: list[int] = field(default_factory=list)
    
    # Counts
    total_lines: int = 0
    comment_lines: int = 0
    functions_with_docstrings: int = 0
    total_functions: int = 0
    redundant_comments: int = 0


# =============================================================================
# FILE-LEVEL EXTRACTION
# =============================================================================

def get_language_from_path(file_path: str) -> str | None:
    """Get language from file extension."""
    for ext, lang in EXTENSION_TO_LANGUAGE.items():
        if file_path.endswith(ext):
            return lang
    return None


def extract_file_features(content: str, language: str) -> FileFeatures:
    """
    Extract features from a single file's content.
    
    Args:
        content: File content as string
        language: Programming language
        
    Returns:
        FileFeatures with all extracted data
    """
    features = FileFeatures(language=language)
    lines = content.split('\n')
    features.total_lines = len(lines)
    
    # Get patterns for this language
    func_pattern = FUNCTION_PATTERNS.get(language)
    var_pattern = VARIABLE_PATTERNS.get(language)
    class_pattern = CLASS_PATTERNS.get(language)
    
    # ==========================================================================
    # Extract function names and track positions for length calculation
    # ==========================================================================
    function_start_lines: list[int] = []
    
    if func_pattern:
        for i, line in enumerate(lines):
            match = re.search(func_pattern, line, re.MULTILINE)
            if match:
                # Get first non-None group (different patterns capture in different groups)
                name = next((g for g in match.groups() if g), None)
                if name and not name.startswith('_'):  # Skip private/dunder
                    features.function_names.append(name)
                    function_start_lines.append(i)
    
    features.total_functions = len(features.function_names)
    
    # ==========================================================================
    # Calculate function lengths (lines until next function or end of file)
    # ==========================================================================
    for idx, start_line in enumerate(function_start_lines):
        if idx + 1 < len(function_start_lines):
            end_line = function_start_lines[idx + 1]
        else:
            end_line = len(lines)
        
        # Count non-empty, non-comment lines in function
        func_lines = 0
        for line_num in range(start_line, end_line):
            stripped = lines[line_num].strip()
            if stripped and not stripped.startswith(('#', '//', '/*', '*', "'''", '"""')):
                func_lines += 1
        
        features.function_lengths.append(func_lines)
    
    # ==========================================================================
    # Extract variable names
    # ==========================================================================
    if var_pattern:
        for line in lines:
            match = re.search(var_pattern, line)
            if match:
                name = next((g for g in match.groups() if g), None)
                if name and not name.startswith('_') and len(name) > 1:
                    # Check if it looks like a constant (UPPER_CASE)
                    if re.match(r'^[A-Z][A-Z0-9_]*$', name):
                        features.constant_names.append(name)
                    else:
                        features.variable_names.append(name)
    
    # ==========================================================================
    # Extract class names
    # ==========================================================================
    if class_pattern:
        for line in lines:
            match = re.search(class_pattern, line)
            if match:
                name = next((g for g in match.groups() if g), None)
                if name:
                    features.class_names.append(name)
    
    # ==========================================================================
    # Count comments and detect redundant ones
    # ==========================================================================
    in_multiline_comment = False
    
    for line in lines:
        stripped = line.strip()
        
        # Track multiline comments
        if '"""' in stripped or "'''" in stripped:
            if stripped.count('"""') == 1 or stripped.count("'''") == 1:
                in_multiline_comment = not in_multiline_comment
            features.comment_lines += 1
            continue
        
        if in_multiline_comment:
            features.comment_lines += 1
            continue
        
        # Single line comments
        if stripped.startswith(('#', '//', '/*', '*')):
            features.comment_lines += 1
            
            # Check for redundant patterns
            for pattern in REDUNDANT_COMMENT_PATTERNS:
                if re.search(pattern, stripped, re.IGNORECASE):
                    features.redundant_comments += 1
                    break
    
    # ==========================================================================
    # Calculate nesting depth
    # ==========================================================================
    current_depth = 0
    max_depth = 0
    
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        
        # Count indent
        indent = len(line) - len(line.lstrip())
        if indent > 0:
            features.indent_sizes.append(indent)
        
        # Track nesting (simplified - based on indent changes)
        if language == "Python":
            # Python uses indentation
            spaces_per_indent = 4  # Assume 4 spaces
            depth = indent // spaces_per_indent
            features.nesting_depths.append(depth)
            max_depth = max(max_depth, depth)
        else:
            # Brace-based languages
            current_depth += stripped.count('{') - stripped.count('}')
            current_depth = max(0, current_depth)
            features.nesting_depths.append(current_depth)
            max_depth = max(max_depth, current_depth)
    
    # ==========================================================================
    # Docstring coverage (check if functions have docstrings)
    # ==========================================================================
    docstring_pattern = DOCSTRING_PATTERNS.get(language)
    if docstring_pattern and function_start_lines:
        for start_line in function_start_lines:
            # Look at lines immediately after function definition
            for offset in range(1, min(4, len(lines) - start_line)):
                check_line = lines[start_line + offset].strip()
                if check_line and re.match(docstring_pattern, check_line):
                    features.functions_with_docstrings += 1
                    break
                elif check_line and not check_line.startswith(('#', '//')):
                    break  # Non-comment, non-docstring code found
    
    return features


# =============================================================================
# AGGREGATION (Repo-level)
# =============================================================================

def aggregate_features(file_features_list: list[FileFeatures]) -> ExtractedFeatures:
    """
    Aggregate features from all files into repo-level metrics.
    
    No weighting by file importance - consistency should be measured
    uniformly across the entire codebase.
    """
    result = ExtractedFeatures()
    
    if not file_features_list:
        return result
    
    # Collect all names across files
    all_function_names: list[str] = []
    all_variable_names: list[str] = []
    all_class_names: list[str] = []
    all_constant_names: list[str] = []
    
    # Collect all metrics
    all_function_lengths: list[int] = []
    all_nesting_depths: list[int] = []
    all_indent_sizes: list[int] = []
    
    # Totals
    total_lines = 0
    total_comment_lines = 0
    total_functions = 0
    total_functions_with_docs = 0
    total_redundant_comments = 0
    
    for ff in file_features_list:
        all_function_names.extend(ff.function_names)
        all_variable_names.extend(ff.variable_names)
        all_class_names.extend(ff.class_names)
        all_constant_names.extend(ff.constant_names)
        
        all_function_lengths.extend(ff.function_lengths)
        all_nesting_depths.extend(ff.nesting_depths)
        all_indent_sizes.extend(ff.indent_sizes)
        
        total_lines += ff.total_lines
        total_comment_lines += ff.comment_lines
        total_functions += ff.total_functions
        total_functions_with_docs += ff.functions_with_docstrings
        total_redundant_comments += ff.redundant_comments
    
    result.files_processed = len(file_features_list)
    result.total_functions = len(all_function_names)
    result.total_variables = len(all_variable_names)
    result.total_classes = len(all_class_names)
    
    # ==========================================================================
    # Calculate consistency metrics (0-1 scale)
    # ==========================================================================
    result.function_naming_consistency = calculate_consistency(all_function_names)
    result.variable_naming_consistency = calculate_consistency(all_variable_names)
    result.class_naming_consistency = calculate_consistency(all_class_names)
    result.constant_naming_consistency = calculate_consistency(all_constant_names)
    
    # Indentation consistency: ratio of most common indent to total
    if all_indent_sizes:
        indent_counts: dict[int, int] = {}
        for size in all_indent_sizes:
            indent_counts[size] = indent_counts.get(size, 0) + 1
        max_indent_count = max(indent_counts.values())
        result.indentation_consistency = max_indent_count / len(all_indent_sizes)
    else:
        result.indentation_consistency = 1.0
    
    # ==========================================================================
    # Calculate averages
    # ==========================================================================
    if all_function_lengths:
        result.avg_function_length = sum(all_function_lengths) / len(all_function_lengths)
        result.max_function_length = max(all_function_lengths)
    
    if all_nesting_depths:
        result.avg_nesting_depth = sum(all_nesting_depths) / len(all_nesting_depths)
        result.max_nesting_depth = max(all_nesting_depths)
    
    if all_function_names:
        result.avg_function_name_length = sum(len(n) for n in all_function_names) / len(all_function_names)
    
    if all_variable_names:
        result.avg_variable_name_length = sum(len(n) for n in all_variable_names) / len(all_variable_names)
    
    # ==========================================================================
    # Calculate ratios
    # ==========================================================================
    if total_lines > 0:
        result.comment_ratio = total_comment_lines / total_lines
    
    if total_functions > 0:
        result.docstring_coverage = total_functions_with_docs / total_functions
    
    result.redundant_comment_count = total_redundant_comments
    
    return result


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

def extract_features(repo_data: RepoData) -> ExtractedFeatures:
    """
    Extract all 14 LPcodedec-style features from repository data.
    
    Args:
        repo_data: RepoData from data_extractor
        
    Returns:
        ExtractedFeatures with all metrics
    """
    file_features_list: list[FileFeatures] = []
    
    for file_path, content in repo_data.files.items():
        # Determine language
        language = get_language_from_path(file_path)
        if not language or language not in SUPPORTED_LANGUAGES:
            continue
        
        # Extract features from this file
        try:
            features = extract_file_features(content, language)
            file_features_list.append(features)
        except Exception as e:
            # Skip files that fail to parse
            print(f"Warning: Failed to extract features from {file_path}: {e}")
            continue
    
    # Aggregate all file features
    return aggregate_features(file_features_list)


def features_to_dict(features: ExtractedFeatures) -> dict:
    """Convert ExtractedFeatures to a dictionary for API response."""
    return {
        "function_naming_consistency": round(features.function_naming_consistency, 3),
        "variable_naming_consistency": round(features.variable_naming_consistency, 3),
        "class_naming_consistency": round(features.class_naming_consistency, 3),
        "constant_naming_consistency": round(features.constant_naming_consistency, 3),
        "indentation_consistency": round(features.indentation_consistency, 3),
        "avg_function_length": round(features.avg_function_length, 2),
        "avg_nesting_depth": round(features.avg_nesting_depth, 2),
        "comment_ratio": round(features.comment_ratio, 3),
        "avg_function_name_length": round(features.avg_function_name_length, 2),
        "avg_variable_name_length": round(features.avg_variable_name_length, 2),
        "max_function_length": features.max_function_length,
        "max_nesting_depth": features.max_nesting_depth,
        "docstring_coverage": round(features.docstring_coverage, 3),
        "redundant_comment_count": features.redundant_comment_count,
    }
