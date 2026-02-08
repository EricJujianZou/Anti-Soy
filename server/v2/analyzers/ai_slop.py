"""
AI Slop Analyzer for Anti-Soy V2

Detects signs of AI-generated code or over-reliance on AI without understanding.
Combines ML classifier with heuristic signals for scoring.

Signals:
- ML classifier (trained on LPcodedec features) - 40% weight
- Comment ratio thresholds - heuristic
- Redundant comment patterns - heuristic (static checks)
- Long variable/function names - heuristic
- Positive signals (AI instruction files, design docs) - reported only, don't affect score

Output matches schemas.AISlop exactly.
"""

import re
from dataclasses import dataclass
from pathlib import Path

from ..schemas import (
    AISlop,
    StyleFeatures,
    Finding,
    PositiveSignal,
    Severity,
    Confidence,
)
from ..feature_extractor import ExtractedFeatures, features_to_dict
from ..classifier import get_classifier, ClassifierResult
from ..data_extractor import RepoData, is_code_file


# =============================================================================
# CONFIGURATION
# =============================================================================

# ML vs Heuristic weight split
ML_WEIGHT = 0.40
HEURISTIC_WEIGHT = 0.60

# Thresholds for heuristic signals
COMMENT_RATIO_HIGH = 0.30  # Above this is strong AI signal
COMMENT_RATIO_MEDIUM = 0.20  # Above this is weak AI signal
REDUNDANT_COMMENT_HIGH = 5  # Above this is strong AI signal
REDUNDANT_COMMENT_MEDIUM = 2  # Above this is weak AI signal
AVG_VAR_NAME_LENGTH_HIGH = 15  # Above this suggests AI verbose naming
AVG_VAR_NAME_LENGTH_MEDIUM = 12
AVG_FUNC_NAME_LENGTH_HIGH = 20  # Above this suggests AI verbose naming
AVG_FUNC_NAME_LENGTH_MEDIUM = 15

# Emoji detection
# Common emojis found in AI-generated code (Copilot, ChatGPT, etc.)
# These are a strong signal of unvetted AI output - real devs don't put 🔥 in their code
COMMON_EMOJIS = {
    # Popular "vibe" emojis
    '🔥', '💀', '😂', '🚀', '✨', '👍', '👎', '💯', '🙏', '❤️',
    '😊', '😎', '🤔', '🎉', '🎊', '💪', '🤖', '🧠', '💡', '⚡',
    '✅', '❌', '⭐', '🌟', '💥', '🔧', '🛠️', '📝', '📌', '🎯',
    '🚨', '⚠️', '💻', '🖥️', '📊', '📈', '🗂️', '📁', '🔒', '🔑',
    # Commonly used in comments/prints
    '👀', '🤩', '😍', '🥳', '🤯', '😱', '🤣', '😅', '🙄', '🤷',
}

# Regex pattern to match any emoji (Unicode emoji ranges)
# This catches emojis we didn't explicitly list
EMOJI_PATTERN = re.compile(
    "["
    "\U0001F600-\U0001F64F"  # emoticons
    "\U0001F300-\U0001F5FF"  # symbols & pictographs
    "\U0001F680-\U0001F6FF"  # transport & map
    "\U0001F1E0-\U0001F1FF"  # flags
    "\U00002702-\U000027B0"  # dingbats
    "]+",
    flags=re.UNICODE
)

# Bonus points for emoji detection (deterministic, not ML-based)
EMOJI_BONUS = 80  # +80 to AI score if ANY emoji found in code

# AI instruction files (positive signal - indicates disciplined AI use)
AI_INSTRUCTION_FILES = [
    ".cursorrules",
    "CLAUDE.md",
    ".github/copilot-instructions.md",
    "copilot-instructions.md",
    ".aider",
    "aider.conf",
]

# Design documentation patterns (positive signal)
DESIGN_DOC_PATTERNS = [
    r"docs?/.*(?:architecture|design|adr|decision).*\.md$",
    r"ARCHITECTURE\.md$",
    r"DESIGN\.md$",
    r"ADR[-_]?\d+.*\.md$",
]

# Redundant comment patterns for static detection
# Each tuple: (pattern, explanation)
REDUNDANT_COMMENT_PATTERNS = [
    # Loop comments
    (r'#\s*(?:loop|iterate|iterating).*(?:through|over|the).*\n\s*for\s',
     "Comment describes obvious loop"),
    (r'#\s*(?:for each|foreach).*\n\s*for\s',
     "Comment describes obvious loop"),
    
    # Return comments
    (r'#\s*(?:return|returns?)(?:\s+the)?(?:\s+\w+){0,3}\s*\n\s*return\s',
     "Comment describes obvious return statement"),
    
    # Assignment/initialization comments
    (r'#\s*(?:initialize|init|set|create|declare).*(?:variable|var|value).*\n\s*\w+\s*=',
     "Comment describes obvious variable assignment"),
    (r'#\s*(?:set|assign).*to.*\n\s*\w+\s*=',
     "Comment describes obvious assignment"),
    
    # Conditional comments
    (r'#\s*(?:check|if|whether).*\n\s*if\s',
     "Comment describes obvious conditional"),
    
    # Function call comments
    (r'#\s*(?:call|invoke|execute).*(?:function|method|api).*\n\s*\w+\(',
     "Comment describes obvious function call"),
    
    # Increment/decrement comments
    (r'#\s*(?:increment|add one|increase).*\n.*\+\s*=\s*1',
     "Comment describes obvious increment"),
    (r'#\s*(?:decrement|subtract one|decrease).*\n.*-\s*=\s*1',
     "Comment describes obvious decrement"),
    
    # Error handling comments
    (r'#\s*(?:handle|catch).*(?:error|exception).*\n\s*(?:except|catch)',
     "Comment describes obvious error handling"),
    
    # Print/log comments
    (r'#\s*(?:print|log|output).*\n\s*(?:print|console\.log|logging\.)',
     "Comment describes obvious print/log statement"),
    
    # Import comments
    (r'#\s*(?:import|include).*(?:module|library|package).*\n\s*(?:import|from|require)',
     "Comment describes obvious import"),
]

# JavaScript/TypeScript redundant patterns
JS_REDUNDANT_COMMENT_PATTERNS = [
    # Loop comments
    (r'//\s*(?:loop|iterate|iterating).*(?:through|over|the).*\n\s*for\s*\(',
     "Comment describes obvious loop"),
    (r'//\s*(?:for each|foreach).*\n\s*(?:for|forEach)',
     "Comment describes obvious loop"),
    
    # Return comments  
    (r'//\s*(?:return|returns?)(?:\s+the)?(?:\s+\w+){0,3}\s*\n\s*return\s',
     "Comment describes obvious return statement"),
    
    # Assignment comments
    (r'//\s*(?:initialize|init|set|create|declare).*(?:variable|var|value|const|let).*\n\s*(?:const|let|var)\s',
     "Comment describes obvious variable declaration"),
    
    # Conditional comments
    (r'//\s*(?:check|if|whether).*\n\s*if\s*\(',
     "Comment describes obvious conditional"),
    
    # Function call comments
    (r'//\s*(?:call|invoke|execute).*(?:function|method|api).*\n\s*(?:await\s+)?\w+\(',
     "Comment describes obvious function call"),
]


# =============================================================================
# ANALYZER CLASS
# =============================================================================

@dataclass
class RedundantCommentFinding:
    """Internal representation of a redundant comment before converting to Finding."""
    file_path: str
    line_number: int
    snippet: str
    explanation: str


@dataclass
class EmojiFinding:
    """Internal representation of an emoji found in code."""
    file_path: str
    line_number: int
    emoji: str
    context: str  # "comment", "print", or "commit"
    snippet: str


class AISlopAnalyzer:
    """
    Analyzes code for AI-generated patterns.
    
    Combines ML classifier probability with heuristic signals to produce
    a final AI slop score and supporting evidence.
    """
    
    def __init__(self):
        self.classifier = get_classifier()
    
    def analyze(
        self,
        repo_data: RepoData,
        features: ExtractedFeatures,
    ) -> AISlop:
        """
        Run full AI slop analysis on a repository.
        
        Args:
            repo_data: Raw repository data (files, tree structure)
            features: Pre-extracted style features
            
        Returns:
            AISlop schema object ready for API response
        """
        # 1. Get ML classifier prediction
        features_dict = features_to_dict(features)
        classifier_result = self.classifier.predict(features_dict)
        
        # 2. Detect redundant comments (static patterns)
        redundant_findings = self._detect_redundant_comments(repo_data)
        
        # 3. Detect emojis in code (comments, prints, commit messages)
        emoji_findings = self._detect_emojis(repo_data)
        
        # 4. Detect positive signals
        positive_signals = self._detect_positive_signals(repo_data)
        
        # 5. Calculate final score (0-100)
        score, confidence = self._calculate_score(
            classifier_result,
            features,
            len(redundant_findings),
            has_emojis=len(emoji_findings) > 0,
        )
        
        # 6. Build StyleFeatures from extracted features
        style_features = self._build_style_features(features, len(redundant_findings))
        
        # 7. Convert findings to Finding objects
        negative_signals = self._convert_to_findings(redundant_findings, emoji_findings)
        
        return AISlop(
            score=score,
            confidence=confidence,
            style_features=style_features,
            negative_ai_signals=negative_signals,
            positive_ai_signals=positive_signals,
        )
    
    def _detect_redundant_comments(self, repo_data: RepoData) -> list[RedundantCommentFinding]:
        """
        Detect redundant comments using static pattern matching.
        
        Scans all code files for comment patterns that obviously describe
        what the next line of code does (classic AI-generated pattern).
        
        Returns:
            List of RedundantCommentFinding with file, line, snippet, explanation
        """
        findings: list[RedundantCommentFinding] = []
        
        for file_path, content in repo_data.files.items():
            # Skip non-code files
            if not is_code_file(file_path):
                continue
            
            # Choose patterns based on file type
            if file_path.endswith('.py'):
                patterns = REDUNDANT_COMMENT_PATTERNS
            elif file_path.endswith(('.js', '.ts', '.jsx', '.tsx')):
                patterns = JS_REDUNDANT_COMMENT_PATTERNS
            else:
                # Use Python patterns as fallback (# comments work in many languages)
                patterns = REDUNDANT_COMMENT_PATTERNS
            
            # Search for each pattern
            for pattern, explanation in patterns:
                for match in re.finditer(pattern, content, re.MULTILINE | re.IGNORECASE):
                    # Find line number
                    line_start = content[:match.start()].count('\n') + 1
                    
                    # Extract snippet (current line + 3 full lines after)
                    lines = content.split('\n')
                    snippet_start = max(0, line_start - 1)
                    snippet_end = min(len(lines), line_start + 4)  # +4 = current line + 3 after
                    snippet = '\n'.join(lines[snippet_start:snippet_end])
                    
                    # Limit snippet length but preserve full lines
                    if len(snippet) > 500:
                        snippet = snippet[:500] + "..."
                    
                    findings.append(RedundantCommentFinding(
                        file_path=file_path,
                        line_number=line_start,
                        snippet=snippet,
                        explanation=explanation,
                    ))
        
        return findings
    
    def _detect_emojis(self, repo_data: RepoData) -> list[EmojiFinding]:
        """
        Detect emojis in code comments, print statements, and commit messages.
        
        Emojis in code are a strong signal of unvetted AI-generated content.
        Real developers don't put 🔥 and 🚀 in their comments.
        
        Returns:
            List of EmojiFinding with file, line, emoji, context, snippet
        """
        findings: list[EmojiFinding] = []
        
        # 1. Check code files for emojis in comments and print statements
        for file_path, content in repo_data.files.items():
            if not is_code_file(file_path):
                continue
            
            lines = content.split('\n')
            for line_num, line in enumerate(lines, 1):
                # Check for emojis using our pattern
                emojis_found = EMOJI_PATTERN.findall(line)
                if not emojis_found:
                    # Also check for common emojis in our set (some might not match regex)
                    emojis_found = [e for e in COMMON_EMOJIS if e in line]
                
                if emojis_found:
                    # Determine context (comment or print)
                    stripped = line.strip()
                    if stripped.startswith('#') or stripped.startswith('//') or stripped.startswith('/*'):
                        context = "comment"
                    elif 'print' in line.lower() or 'console.log' in line.lower() or 'logger' in line.lower():
                        context = "print/log"
                    else:
                        context = "code"
                    
                    # Build snippet (current line + 2 lines after for context)
                    snippet_start = line_num - 1
                    snippet_end = min(len(lines), line_num + 2)
                    snippet = '\n'.join(lines[snippet_start:snippet_end])
                    
                    findings.append(EmojiFinding(
                        file_path=file_path,
                        line_number=line_num,
                        emoji=emojis_found[0],  # Store first emoji found
                        context=context,
                        snippet=snippet[:300] if len(snippet) > 300 else snippet,
                    ))
        
        # 2. Check commit messages for emojis
        for commit in repo_data.commits:
            emojis_found = EMOJI_PATTERN.findall(commit.message)
            if not emojis_found:
                emojis_found = [e for e in COMMON_EMOJIS if e in commit.message]
            
            if emojis_found:
                findings.append(EmojiFinding(
                    file_path="[commit]",
                    line_number=0,
                    emoji=emojis_found[0],
                    context="commit",
                    snippet=f"{commit.hash[:7]}: {commit.message[:100]}",
                ))
        
        return findings
    
    def _detect_positive_signals(self, repo_data: RepoData) -> list[PositiveSignal]:
        """
        Detect positive signals that indicate disciplined AI usage or manual coding.
        
        Positive signals:
        - AI instruction files (.cursorrules, CLAUDE.md, etc.)
        - Design documentation (architecture docs, ADRs)
        
        These DON'T reduce the AI score, but are reported to give context.
        """
        signals: list[PositiveSignal] = []
        
        # Check for AI instruction files
        for ai_file in AI_INSTRUCTION_FILES:
            # Check both in tree (all paths) and files (content was read)
            if ai_file in repo_data.files or any(ai_file in path for path in repo_data.tree):
                signals.append(PositiveSignal(
                    type="ai_instruction_file",
                    file=ai_file,
                    explanation=f"Has {ai_file} - indicates disciplined AI usage with custom instructions",
                ))
        
        # Check for design docs
        for path in repo_data.tree:
            for pattern in DESIGN_DOC_PATTERNS:
                if re.search(pattern, path, re.IGNORECASE):
                    signals.append(PositiveSignal(
                        type="design_docs",
                        file=path,
                        explanation="Has architecture/design documentation - indicates thoughtful planning",
                    ))
                    break  # Don't report same file multiple times
        
        return signals
    
    def _calculate_score(
        self,
        classifier_result: ClassifierResult,
        features: ExtractedFeatures,
        redundant_count: int,
        has_emojis: bool = False,
    ) -> tuple[int, Confidence]:
        """
        Calculate final AI slop score (0-100) and confidence.
        
        Formula:
        - 40% from ML classifier probability
        - 60% from heuristic signals (comment_ratio, name lengths, redundant count)
        - +80 bonus if ANY emoji found (deterministic, capped at 100)
        
        Positive signals are reported but don't affect score (per user requirement).
        
        Returns:
            Tuple of (score 0-100, confidence enum)
        """
        # ML component (0-1 probability -> 0-40 points)
        ml_score = classifier_result.ai_probability * 100 * ML_WEIGHT
        
        # Heuristic component (max 60 points)
        heuristic_score = 0.0
        heuristic_signals = 0
        
        # Comment ratio signal (max 15 points)
        if features.comment_ratio >= COMMENT_RATIO_HIGH:
            heuristic_score += 15
            heuristic_signals += 1
        elif features.comment_ratio >= COMMENT_RATIO_MEDIUM:
            heuristic_score += 8
            heuristic_signals += 1
        
        # Redundant comments signal (max 20 points)
        if redundant_count >= REDUNDANT_COMMENT_HIGH:
            heuristic_score += 20
            heuristic_signals += 1
        elif redundant_count >= REDUNDANT_COMMENT_MEDIUM:
            heuristic_score += 10
            heuristic_signals += 1
        elif redundant_count > 0:
            heuristic_score += 5
            heuristic_signals += 1
        
        # Variable name length signal (max 10 points)
        if features.avg_variable_name_length >= AVG_VAR_NAME_LENGTH_HIGH:
            heuristic_score += 10
            heuristic_signals += 1
        elif features.avg_variable_name_length >= AVG_VAR_NAME_LENGTH_MEDIUM:
            heuristic_score += 5
            heuristic_signals += 1
        
        # Function name length signal (max 10 points)
        if features.avg_function_name_length >= AVG_FUNC_NAME_LENGTH_HIGH:
            heuristic_score += 10
            heuristic_signals += 1
        elif features.avg_function_name_length >= AVG_FUNC_NAME_LENGTH_MEDIUM:
            heuristic_score += 5
            heuristic_signals += 1
        
        # High naming consistency can be AI signal (max 5 points)
        # AI tends to use very consistent naming (all snake_case or all camelCase)
        avg_consistency = (
            features.function_naming_consistency +
            features.variable_naming_consistency
        ) / 2
        if avg_consistency > 0.95:
            heuristic_score += 5
            heuristic_signals += 1
        
        # Combine scores
        total_score = ml_score + heuristic_score
        
        # Emoji bonus: +80 if ANY emoji found (deterministic signal)
        # This is applied AFTER combining ML + heuristics to ensure it dominates
        if has_emojis:
            total_score += EMOJI_BONUS
            heuristic_signals += 1  # Count as a signal for confidence
        
        # Clamp to 0-100
        final_score = max(0, min(100, int(round(total_score))))
        
        # Determine confidence based on signal agreement
        # High confidence if ML and heuristics agree
        ml_says_ai = classifier_result.ai_probability > 0.5
        heuristics_say_ai = heuristic_score > 30  # More than half of heuristic max
        
        if ml_says_ai == heuristics_say_ai:
            if heuristic_signals >= 3:
                confidence = Confidence.HIGH
            else:
                confidence = Confidence.MEDIUM
        else:
            # Disagreement between ML and heuristics
            confidence = Confidence.LOW
        
        return final_score, confidence
    
    def _build_style_features(
        self,
        features: ExtractedFeatures,
        redundant_count: int,
    ) -> StyleFeatures:
        """Convert ExtractedFeatures to StyleFeatures schema."""
        return StyleFeatures(
            function_naming_consistency=round(features.function_naming_consistency, 3),
            variable_naming_consistency=round(features.variable_naming_consistency, 3),
            class_naming_consistency=round(features.class_naming_consistency, 3),
            constant_naming_consistency=round(features.constant_naming_consistency, 3),
            indentation_consistency=round(features.indentation_consistency, 3),
            avg_function_length=round(features.avg_function_length, 2),
            avg_nesting_depth=round(features.avg_nesting_depth, 2),
            comment_ratio=round(features.comment_ratio, 3),
            avg_function_name_length=round(features.avg_function_name_length, 2),
            avg_variable_name_length=round(features.avg_variable_name_length, 2),
            max_function_length=features.max_function_length,
            max_nesting_depth=features.max_nesting_depth,
            docstring_coverage=round(features.docstring_coverage, 3),
            redundant_comment_count=redundant_count,  # Use our detected count
        )
    
    def _convert_to_findings(
        self,
        redundant_findings: list[RedundantCommentFinding],
        emoji_findings: list[EmojiFinding],
    ) -> list[Finding]:
        """
        Convert internal findings to schema Finding objects.
        
        Aggregates findings:
        - Redundant comments grouped by explanation type
        - Emojis grouped into single finding with all occurrences
        """
        findings: list[Finding] = []
        
        # 1. Handle redundant comments (group by explanation type)
        if redundant_findings:
            grouped: dict[str, list[RedundantCommentFinding]] = {}
            for f in redundant_findings:
                if f.explanation not in grouped:
                    grouped[f.explanation] = []
                grouped[f.explanation].append(f)
            
            for explanation, group in grouped.items():
                first = group[0]
                occurrences = [f"{f.file_path}:{f.line_number}" for f in group]
                snippet_parts = occurrences[:5]
                snippet = ', '.join(snippet_parts)
                if len(occurrences) > 5:
                    snippet += f" ... and {len(occurrences) - 5} more"
                
                findings.append(Finding(
                    type="redundant_comment",
                    severity=Severity.WARNING,
                    file=f"Multiple files, first occurrence at {first.file_path}",
                    line=first.line_number,
                    snippet=snippet,
                    explanation=f"{explanation} (found {len(group)} occurrences)",
                ))
        
        # 2. Handle emojis (aggregate all into single finding)
        if emoji_findings:
            first = emoji_findings[0]
            
            # Group by context for the explanation
            contexts: dict[str, int] = {}
            unique_emojis: set[str] = set()
            for f in emoji_findings:
                contexts[f.context] = contexts.get(f.context, 0) + 1
                unique_emojis.add(f.emoji)
            
            # Build snippet showing occurrences (max 5)
            occurrences = [
                f"{f.file_path}:{f.line_number} ({f.emoji})" 
                if f.context != "commit" 
                else f"commit {f.snippet[:40]}... ({f.emoji})"
                for f in emoji_findings[:5]
            ]
            snippet = '\n'.join(occurrences)
            if len(emoji_findings) > 5:
                snippet += f"\n... and {len(emoji_findings) - 5} more"
            
            # Build context summary
            context_parts = [f"{count} in {ctx}" for ctx, count in contexts.items()]
            context_summary = ', '.join(context_parts)
            
            # Show unique emojis found
            emoji_display = ' '.join(sorted(unique_emojis)[:10])
            if len(unique_emojis) > 10:
                emoji_display += f" ... and {len(unique_emojis) - 10} more"
            
            findings.append(Finding(
                type="emoji_in_code",
                severity=Severity.CRITICAL,  # Strong AI signal
                file=f"Multiple locations, first at {first.file_path}" if first.context != "commit" else "[commit messages]",
                line=first.line_number if first.context != "commit" else 0,
                snippet=snippet,
                explanation=f"Emojis found in code: {emoji_display}. Distribution: {context_summary}. Total: {len(emoji_findings)} occurrences. Real developers don't put 🔥 and 🚀 in production code.",
            ))
        
        return findings


# =============================================================================
# CONVENIENCE FUNCTION
# =============================================================================

# Singleton analyzer instance
_analyzer: AISlopAnalyzer | None = None


def get_analyzer() -> AISlopAnalyzer:
    """Get or create the singleton analyzer instance."""
    global _analyzer
    if _analyzer is None:
        _analyzer = AISlopAnalyzer()
    return _analyzer


def analyze_ai_slop(repo_data: RepoData, features: ExtractedFeatures) -> AISlop:
    """
    Convenience function to analyze AI slop in a repository.
    
    Args:
        repo_data: Raw repository data from data_extractor
        features: Extracted features from feature_extractor
        
    Returns:
        AISlop schema object
    """
    return get_analyzer().analyze(repo_data, features)
