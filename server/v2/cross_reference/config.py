"""Configuration and environment variable bindings for the cross_reference module."""
import os

# Required: reuses the same env var used throughout the server
GITHUB_PAT: str | None = os.getenv("GITHUB_TOKEN")

# Required: Gemini API key for project extraction
GEMINI_API_KEY: str | None = os.getenv("GEMINI_API_KEY")

# --- Matching ---
# Threshold lowered to 0.55: with 15/70/15 weights, a zero-name-match repo still needs
# desc_conf >= 0.786 to pass — a high bar that prevents false positives.
# The 0.6 wall was cutting off clearly correct matches where the LLM returned 0.59-0.61.
MATCH_CONFIDENCE_THRESHOLD: float = float(os.getenv("MATCH_CONFIDENCE_THRESHOLD", "0.55"))
MAX_CONCURRENT_WORKERS: int = int(os.getenv("MAX_CONCURRENT_WORKERS", "15"))

# --- LLM ---
LLM_MODEL: str = os.getenv("LLM_MODEL", "gemini-2.0-flash")

# --- Adaptive signal weights ---
# Strategy: name similarity determines which regime we're in.
#
# NAME MATCH (name_sim >= 0.5): name is the primary signal.
#   confidence = 0.9 * name_sim + 0.1 * desc_sim
#   Rationale: if the repo name clearly matches the resume project, it almost
#   certainly IS that project — description is a sanity check only.
#
# DESCRIPTION MATCH (name_sim < 0.5): LLM semantic match drives the decision.
#   confidence = 0.2 * name_sim + 0.8 * desc_sim
#   Rationale: project may have a different repo name (e.g. "Expandr" → "promptassist");
#   the LLM's description comparison is the only reliable signal.
#
# Tech/language overlap: weight = 0. GitHub exposes only the primary language,
# and candidates frequently omit languages from project descriptions — too noisy.
NAME_MATCH_THRESHOLD: float = 0.5
NAME_HIGH_NAME_W: float = 0.9
NAME_HIGH_DESC_W: float = 0.1
NAME_LOW_NAME_W: float = 0.2
NAME_LOW_DESC_W: float = 0.8
