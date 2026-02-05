"""
Code Quality Analyzer for Anti-Soy V2

Evaluates overall code quality based on organization, testing, documentation,
error handling, and dependency management.

Unlike AI Slop and Bad Practices (where higher = worse), Code Quality uses
higher = better scoring to match intuition.

Categories:
- files_organized: Project structure, separation of concerns
- test_coverage: Test file presence and ratio
- readme_quality: README completeness and sections
- error_handling: Try/except patterns, proper error handling
- logging_quality: Logging vs print statement usage
- dependency_health: Lock files, pinned versions, dependency count

Output matches schemas.CodeQuality exactly.
"""

import re
from pathlib import Path

from ..schemas import CodeQuality, Finding, Severity
from ..data_extractor import RepoData, is_code_file, is_test_file


# =============================================================================
# CONFIGURATION
# =============================================================================

# Weight for overall score calculation (must sum to 1.0)
METRIC_WEIGHTS = {
    "files_organized": 0.15,
    "test_coverage": 0.20,
    "readme_quality": 0.15,
    "error_handling": 0.20,
    "logging_quality": 0.10,
    "dependency_health": 0.20,
}

# README quality markers
README_REQUIRED_SECTIONS = [
    (r"#.*install|getting started|setup|quick start", "Installation/Setup section"),
    (r"#.*usage|how to use|example", "Usage/Examples section"),
]
README_BONUS_SECTIONS = [
    (r"#.*api|endpoint|reference", "API documentation"),
    (r"#.*contribut", "Contributing guidelines"),
    (r"#.*test", "Testing instructions"),
    (r"#.*licen[sc]e", "License section"),
    (r"#.*requirements|prerequisites|dependencies", "Requirements section"),
]

# Good project structure patterns
GOOD_STRUCTURE_PATTERNS = [
    "src/",
    "lib/",
    "app/",
    "tests/",
    "test/",
    "__tests__/",
    "docs/",
    "scripts/",
    "utils/",
    "helpers/",
    "components/",
    "services/",
    "models/",
    "views/",
    "controllers/",
    "api/",
    "routes/",
    "middleware/",
    "config/",
]


# =============================================================================
# ANALYZER CLASS
# =============================================================================

class CodeQualityAnalyzer:
    """
    Analyzes code for quality signals.
    
    Higher scores = better quality (opposite of other analyzers).
    """
    
    def __init__(self):
        pass
    
    def analyze(self, repo_data: RepoData) -> CodeQuality:
        """
        Run code quality analysis on a repository.
        
        Args:
            repo_data: Raw repository data (files, tree structure)
            
        Returns:
            CodeQuality schema object ready for API response
        """
        findings: list[Finding] = []
        
        # Calculate each metric (0-100, higher = better)
        files_organized, org_findings = self._analyze_organization(repo_data)
        test_coverage, test_findings = self._analyze_test_coverage(repo_data)
        readme_quality, readme_findings = self._analyze_readme(repo_data)
        error_handling, error_findings = self._analyze_error_handling(repo_data)
        logging_quality, logging_findings = self._analyze_logging(repo_data)
        dependency_health, dep_findings = self._analyze_dependencies(repo_data)
        
        # Collect all findings
        findings.extend(org_findings)
        findings.extend(test_findings)
        findings.extend(readme_findings)
        findings.extend(error_findings)
        findings.extend(logging_findings)
        findings.extend(dep_findings)
        
        # Calculate overall score (weighted average)
        overall_score = int(
            files_organized * METRIC_WEIGHTS["files_organized"] +
            test_coverage * METRIC_WEIGHTS["test_coverage"] +
            readme_quality * METRIC_WEIGHTS["readme_quality"] +
            error_handling * METRIC_WEIGHTS["error_handling"] +
            logging_quality * METRIC_WEIGHTS["logging_quality"] +
            dependency_health * METRIC_WEIGHTS["dependency_health"]
        )
        
        return CodeQuality(
            score=overall_score,
            files_organized=files_organized,
            test_coverage=test_coverage,
            readme_quality=readme_quality,
            error_handling=error_handling,
            logging_quality=logging_quality,
            dependency_health=dependency_health,
            findings=findings,
        )
    
    # =========================================================================
    # FILES ORGANIZED (0-100)
    # =========================================================================
    
    def _analyze_organization(self, repo_data: RepoData) -> tuple[int, list[Finding]]:
        """
        Analyze project structure and file organization.
        
        Checks for:
        - Proper directory structure (src/, tests/, etc.)
        - Not too many files in root
        - No god files (> 500 LOC)
        """
        findings: list[Finding] = []
        score = 100
        
        tree = repo_data.tree
        
        # Count code files in root vs subdirectories
        root_code_files = []
        organized_files = []
        
        for path in tree:
            if not is_code_file(path):
                continue
            
            if "/" not in path:
                # File is in root
                root_code_files.append(path)
            else:
                organized_files.append(path)
        
        total_code_files = len(root_code_files) + len(organized_files)
        
        if total_code_files == 0:
            return 50, findings  # No code files, neutral score
        
        # Check for flat structure (too many code files in root)
        root_ratio = len(root_code_files) / total_code_files if total_code_files > 0 else 0
        
        if root_ratio > 0.5 and total_code_files > 3:
            score -= 25
            findings.append(Finding(
                type="flat_structure",
                severity=Severity.WARNING,
                file="(project root)",
                line=1,
                snippet=f"Root files: {', '.join(root_code_files[:5])}{'...' if len(root_code_files) > 5 else ''}",
                explanation=f"{len(root_code_files)}/{total_code_files} code files are in the root directory. Consider organizing into src/, lib/, or feature-based folders.",
            ))
        
        # Check for good directory structure
        has_structure_dirs = []
        for pattern in GOOD_STRUCTURE_PATTERNS:
            if any(pattern in path for path in tree):
                has_structure_dirs.append(pattern.rstrip("/"))
        
        if len(has_structure_dirs) >= 3:
            score = min(100, score + 10)  # Bonus for good structure
        elif len(has_structure_dirs) == 0 and total_code_files > 5:
            score -= 15
            findings.append(Finding(
                type="no_structure",
                severity=Severity.INFO,
                file="(project root)",
                line=1,
                snippet="No standard directories found",
                explanation="No common project structure patterns detected (src/, tests/, lib/, etc.). Consider organizing code into logical directories.",
            ))
        
        # Check for god files (> 500 LOC)
        for file_path, content in repo_data.files.items():
            if not is_code_file(file_path):
                continue
            
            loc = len(content.split("\n"))
            if loc > 500:
                score -= 10
                findings.append(Finding(
                    type="god_file",
                    severity=Severity.WARNING,
                    file=file_path,
                    line=1,
                    snippet=f"File has {loc} lines of code",
                    explanation=f"Large file with {loc} LOC. Consider breaking into smaller, focused modules.",
                ))
        
        return max(0, min(100, score)), findings
    
    # =========================================================================
    # TEST COVERAGE (0-100)
    # =========================================================================
    
    def _analyze_test_coverage(self, repo_data: RepoData) -> tuple[int, list[Finding]]:
        """
        Analyze test presence and coverage.
        
        Checks for:
        - Presence of test files
        - Test to code ratio
        - Test configuration files
        """
        findings: list[Finding] = []
        
        tree = repo_data.tree
        
        # Count test files vs source files
        test_files = []
        source_files = []
        
        for path in tree:
            if not is_code_file(path):
                continue
            
            if is_test_file(path):
                test_files.append(path)
            else:
                source_files.append(path)
        
        total_source = len(source_files)
        total_tests = len(test_files)
        
        if total_source == 0:
            return 50, findings  # No source files
        
        # Calculate test ratio
        test_ratio = total_tests / total_source if total_source > 0 else 0
        
        # Score based on test ratio
        if total_tests == 0:
            score = 0
            findings.append(Finding(
                type="no_tests",
                severity=Severity.WARNING,
                file="(project)",
                line=1,
                snippet="No test files found",
                explanation="No test files detected. Tests are essential for code reliability and maintainability.",
            ))
        elif test_ratio < 0.1:
            score = 20
            findings.append(Finding(
                type="low_test_coverage",
                severity=Severity.INFO,
                file="(project)",
                line=1,
                snippet=f"{total_tests} test files for {total_source} source files",
                explanation=f"Low test coverage: {test_ratio:.0%} test-to-source ratio. Aim for at least 30%.",
            ))
        elif test_ratio < 0.3:
            score = 50
        elif test_ratio < 0.5:
            score = 70
        elif test_ratio < 0.8:
            score = 85
        else:
            score = 100
        
        # Check for test config files (pytest.ini, jest.config.js, etc.)
        test_configs = [
            "pytest.ini", "setup.cfg", "pyproject.toml",
            "jest.config.js", "jest.config.ts", "jest.config.json",
            "vitest.config.ts", "vitest.config.js",
            "karma.conf.js", ".mocharc.js", ".mocharc.json",
        ]
        
        has_test_config = any(
            any(cfg in path for cfg in test_configs)
            for path in tree
        )
        
        if has_test_config and total_tests > 0:
            score = min(100, score + 10)  # Bonus for proper test config
        
        return max(0, min(100, score)), findings
    
    # =========================================================================
    # README QUALITY (0-100)
    # =========================================================================
    
    def _analyze_readme(self, repo_data: RepoData) -> tuple[int, list[Finding]]:
        """
        Analyze README completeness and quality.
        
        Checks for:
        - README existence
        - Required sections (install, usage)
        - Bonus sections (API, contributing, license)
        - Minimum length
        """
        findings: list[Finding] = []
        
        # Find README file
        readme_content = None
        readme_path = None
        
        for path, content in repo_data.files.items():
            lower_path = path.lower()
            if "readme" in lower_path and lower_path.endswith((".md", ".rst", ".txt", "")):
                readme_content = content
                readme_path = path
                break
        
        # Also check tree for README if not in files
        if readme_content is None:
            for path in repo_data.tree:
                lower_path = path.lower()
                if "readme" in lower_path:
                    readme_path = path
                    break
        
        if readme_content is None and readme_path is None:
            findings.append(Finding(
                type="no_readme",
                severity=Severity.WARNING,
                file="README.md",
                line=1,
                snippet="(missing file)",
                explanation="No README file found. A README is essential for project documentation.",
            ))
            return 0, findings
        
        if readme_content is None:
            # README exists in tree but wasn't read (shouldn't happen)
            return 30, findings
        
        score = 30  # Base score for having a README
        readme_lower = readme_content.lower()
        
        # Check minimum length
        word_count = len(readme_content.split())
        if word_count < 50:
            findings.append(Finding(
                type="sparse_readme",
                severity=Severity.INFO,
                file=readme_path or "README.md",
                line=1,
                snippet=f"README has {word_count} words",
                explanation="README is very short. Consider adding more documentation.",
            ))
        elif word_count >= 100:
            score += 10  # Good length bonus
        
        # Check required sections
        missing_required = []
        for pattern, name in README_REQUIRED_SECTIONS:
            if re.search(pattern, readme_lower, re.IGNORECASE):
                score += 15
            else:
                missing_required.append(name)
        
        if missing_required:
            findings.append(Finding(
                type="readme_missing_sections",
                severity=Severity.INFO,
                file=readme_path or "README.md",
                line=1,
                snippet=f"Missing: {', '.join(missing_required)}",
                explanation=f"README is missing important sections: {', '.join(missing_required)}",
            ))
        
        # Check bonus sections
        bonus_found = 0
        for pattern, _ in README_BONUS_SECTIONS:
            if re.search(pattern, readme_lower, re.IGNORECASE):
                bonus_found += 1
        
        score += min(20, bonus_found * 5)  # Up to 20 bonus points
        
        return max(0, min(100, score)), findings
    
    # =========================================================================
    # ERROR HANDLING (0-100)
    # =========================================================================
    
    def _analyze_error_handling(self, repo_data: RepoData) -> tuple[int, list[Finding]]:
        """
        Analyze error handling patterns.
        
        Checks for:
        - Presence of try/except or try/catch blocks
        - Specific exception types (not bare except)
        - Error logging in catch blocks
        """
        findings: list[Finding] = []
        
        total_files = 0
        files_with_error_handling = 0
        good_error_handling = 0
        
        # Collect bare except occurrences with evidence
        bare_except_occurrences: list[tuple[str, int, str]] = []  # (file, line, snippet)
        
        for file_path, content in repo_data.files.items():
            if not is_code_file(file_path):
                continue
            
            # Skip test files for error handling analysis
            if is_test_file(file_path):
                continue
            
            total_files += 1
            lines = content.split("\n")
            
            # Python error handling
            if file_path.endswith(".py"):
                has_try = "try:" in content
                if has_try:
                    files_with_error_handling += 1
                    
                    # Check for specific exceptions (good)
                    specific_except = re.search(
                        r"except\s+(?:[\w.]+(?:\s*,\s*[\w.]+)*|\([\w.\s,]+\))\s*(?:as\s+\w+)?:",
                        content
                    )
                    if specific_except:
                        good_error_handling += 1
                    
                    # Find bare excepts with line numbers and snippets
                    for match in re.finditer(r"except\s*:", content):
                        line_num = content[:match.start()].count("\n") + 1
                        # Get snippet (2 lines before, the line, 2 lines after)
                        start_line = max(0, line_num - 2)
                        end_line = min(len(lines), line_num + 3)
                        snippet = "\n".join(lines[start_line:end_line])
                        if len(snippet) > 200:
                            snippet = snippet[:200] + "..."
                        bare_except_occurrences.append((file_path, line_num, snippet))
            
            # JavaScript/TypeScript error handling
            elif file_path.endswith((".js", ".ts", ".jsx", ".tsx")):
                has_try = "try {" in content or "try{" in content
                if has_try:
                    files_with_error_handling += 1
                    
                    # Check for non-empty catch
                    catch_with_body = re.search(r"catch\s*\([^)]+\)\s*\{[^}]+\}", content)
                    if catch_with_body:
                        good_error_handling += 1
        
        if total_files == 0:
            return 50, findings  # No files to analyze
        
        # Calculate score
        handling_ratio = files_with_error_handling / total_files if total_files > 0 else 0
        
        if files_with_error_handling == 0:
            score = 30  # Base score, error handling not always needed
        else:
            # Score based on error handling presence and quality
            score = 40 + int(handling_ratio * 30)  # 40-70 based on coverage
            
            # Bonus for good error handling (specific exceptions)
            if good_error_handling > 0:
                quality_ratio = good_error_handling / files_with_error_handling
                score += int(quality_ratio * 30)  # Up to 30 bonus
        
        # Penalty for bare excepts - create finding with evidence
        bare_except_count = len(bare_except_occurrences)
        if bare_except_count > 0:
            if bare_except_count > 3:
                score -= 15
            
            # Get first occurrence as example snippet
            example_file, example_line, example_snippet = bare_except_occurrences[0]
            
            # Collect all line numbers for the explanation
            locations = [f"{f}:{l}" for f, l, _ in bare_except_occurrences[:5]]  # Max 5 locations
            if bare_except_count > 5:
                locations.append(f"... and {bare_except_count - 5} more")
            
            findings.append(Finding(
                type="bare_except",
                severity=Severity.WARNING if bare_except_count > 3 else Severity.INFO,
                file=example_file,
                line=example_line,
                snippet=example_snippet,
                explanation=f"Found {bare_except_count} bare 'except:' statement(s). Locations: {', '.join(locations)}. Use specific exception types for better error handling.",
            ))
        
        return max(0, min(100, score)), findings
    
    # =========================================================================
    # LOGGING QUALITY (0-100)
    # =========================================================================
    
    def _analyze_logging(self, repo_data: RepoData) -> tuple[int, list[Finding]]:
        """
        Analyze logging practices.
        
        Checks for:
        - Proper logging module usage
        - Print statement usage (should be minimal in prod code)
        """
        findings: list[Finding] = []
        
        has_logging_import = False
        uses_logging = False
        print_count = 0
        console_log_count = 0
        total_code_files = 0
        
        for file_path, content in repo_data.files.items():
            if not is_code_file(file_path):
                continue
            
            # Skip test files
            if is_test_file(file_path):
                continue
            
            total_code_files += 1
            
            # Python
            if file_path.endswith(".py"):
                if "import logging" in content or "from logging" in content:
                    has_logging_import = True
                
                if re.search(r"logging\.(debug|info|warning|error|critical|exception)\(", content):
                    uses_logging = True
                
                # Count print statements (excluding commented lines)
                for line in content.split("\n"):
                    stripped = line.strip()
                    if stripped.startswith("#"):
                        continue
                    if re.search(r"^\s*print\s*\(", line):
                        print_count += 1
            
            # JavaScript/TypeScript
            elif file_path.endswith((".js", ".ts", ".jsx", ".tsx")):
                # Check for logger imports
                if re.search(r"import.*(?:winston|pino|bunyan|log4js|logger)", content, re.IGNORECASE):
                    has_logging_import = True
                    uses_logging = True
                
                # Count console.log (excluding commented)
                for line in content.split("\n"):
                    stripped = line.strip()
                    if stripped.startswith("//"):
                        continue
                    if "console.log(" in line:
                        console_log_count += 1
        
        if total_code_files == 0:
            return 50, findings
        
        # Calculate score
        total_prints = print_count + console_log_count
        
        if uses_logging:
            score = 80
            if total_prints < 5:
                score = 100
            elif total_prints < 15:
                score = 90
        elif has_logging_import:
            score = 60
        else:
            # No logging at all
            if total_prints == 0:
                score = 50  # Could be a small project
            elif total_prints < 10:
                score = 40
            else:
                score = 20
                findings.append(Finding(
                    type="print_over_logging",
                    severity=Severity.INFO,
                    file="(multiple files)",
                    line=1,
                    snippet=f"Found {total_prints} print/console.log statements",
                    explanation="Using print statements instead of proper logging. Consider using logging module for production code.",
                ))
        
        return max(0, min(100, score)), findings
    
    # =========================================================================
    # DEPENDENCY HEALTH (0-100)
    # =========================================================================
    
    def _analyze_dependencies(self, repo_data: RepoData) -> tuple[int, list[Finding]]:
        """
        Analyze dependency management.
        
        Checks for:
        - Presence of dependency files
        - Lock files
        - Reasonable dependency count
        - Version pinning
        """
        findings: list[Finding] = []
        
        tree = repo_data.tree
        files = repo_data.files
        
        # Check for dependency definition files
        dep_files = {
            "requirements.txt": False,
            "pyproject.toml": False,
            "setup.py": False,
            "package.json": False,
            "go.mod": False,
            "Cargo.toml": False,
            "Gemfile": False,
            "pom.xml": False,
            "build.gradle": False,
            "composer.json": False,
        }
        
        # Check for lock files
        lock_files = {
            "requirements.txt": ["requirements.lock", "requirements-lock.txt"],
            "pyproject.toml": ["poetry.lock", "pdm.lock", "uv.lock"],
            "setup.py": [],
            "package.json": ["package-lock.json", "yarn.lock", "pnpm-lock.yaml"],
            "go.mod": ["go.sum"],
            "Cargo.toml": ["Cargo.lock"],
            "Gemfile": ["Gemfile.lock"],
            "pom.xml": [],
            "build.gradle": ["gradle.lockfile"],
            "composer.json": ["composer.lock"],
        }
        
        found_dep_files = []
        found_lock_files = []
        
        for path in tree:
            filename = Path(path).name
            
            for dep_file in dep_files:
                if filename == dep_file:
                    dep_files[dep_file] = True
                    found_dep_files.append(dep_file)
            
            for dep_file, locks in lock_files.items():
                if filename in locks:
                    found_lock_files.append(filename)
        
        if not found_dep_files:
            # No dependency files - might be a small project or use different system
            # Check if there are any code files that would need dependencies
            code_files = [p for p in tree if is_code_file(p)]
            if len(code_files) > 5:
                findings.append(Finding(
                    type="no_dependency_file",
                    severity=Severity.INFO,
                    file="(project root)",
                    line=1,
                    snippet="No dependency management file found",
                    explanation="No requirements.txt, package.json, or similar dependency file found.",
                ))
                return 40, findings
            else:
                return 70, findings  # Small project, acceptable
        
        score = 60  # Base score for having dependency file
        
        # Check for lock files
        has_lock = len(found_lock_files) > 0
        
        if has_lock:
            score += 20
        else:
            # Check if project type typically uses lock files
            needs_lock = any(
                dep_file in found_dep_files and lock_files.get(dep_file)
                for dep_file in ["package.json", "pyproject.toml", "Gemfile", "Cargo.toml"]
            )
            if needs_lock:
                findings.append(Finding(
                    type="no_lock_file",
                    severity=Severity.INFO,
                    file=found_dep_files[0],
                    line=1,
                    snippet="No lock file found",
                    explanation="No dependency lock file found. Lock files ensure reproducible builds.",
                ))
        
        # Check version pinning in requirements.txt
        if "requirements.txt" in found_dep_files:
            req_content = files.get("requirements.txt", "")
            if req_content:
                all_lines = req_content.split("\n")
                dep_lines = [(i + 1, l.strip()) for i, l in enumerate(all_lines) if l.strip() and not l.strip().startswith("#")]
                
                pinned_lines = [(ln, l) for ln, l in dep_lines if "==" in l or ">=" in l or "~=" in l]
                unpinned_lines = [(ln, l) for ln, l in dep_lines if "==" not in l and ">=" not in l and "~=" not in l]
                
                unpinned_count = len(unpinned_lines)
                
                if unpinned_count > 3:
                    # Show actual unpinned dependencies as snippet
                    unpinned_examples = [l for _, l in unpinned_lines[:5]]
                    snippet = "\n".join(unpinned_examples)
                    if unpinned_count > 5:
                        snippet += f"\n... and {unpinned_count - 5} more"
                    
                    findings.append(Finding(
                        type="unpinned_dependencies",
                        severity=Severity.INFO,
                        file="requirements.txt",
                        line=unpinned_lines[0][0] if unpinned_lines else 1,
                        snippet=snippet,
                        explanation=f"{unpinned_count} dependencies without version constraints. This can cause reproducibility issues.",
                    ))
                    score -= 10
                elif unpinned_count == 0 and dep_lines:
                    score += 10  # All pinned bonus
        
        # Check dependency count (too many = complexity)
        dep_count = len(repo_data.dependencies)
        if dep_count > 50:
            findings.append(Finding(
                type="many_dependencies",
                severity=Severity.INFO,
                file=found_dep_files[0],
                line=1,
                snippet=f"{dep_count} dependencies",
                explanation=f"Large number of dependencies ({dep_count}). Consider if all are necessary.",
            ))
            score -= 10
        
        return max(0, min(100, score)), findings


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

_analyzer: CodeQualityAnalyzer | None = None


def get_analyzer() -> CodeQualityAnalyzer:
    """Get or create singleton analyzer instance."""
    global _analyzer
    if _analyzer is None:
        _analyzer = CodeQualityAnalyzer()
    return _analyzer


def analyze_code_quality(repo_data: RepoData) -> CodeQuality:
    """
    Convenience function to analyze code quality in a repository.
    
    Args:
        repo_data: Raw repository data from data_extractor
        
    Returns:
        CodeQuality schema object
    """
    return get_analyzer().analyze(repo_data)
