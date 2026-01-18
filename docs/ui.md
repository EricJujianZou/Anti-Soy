# Anti-Soy Frontend UI Flow

This document describes the user flow and frontend UI from a flow perspective,
grounded in `README.md` and `docs/implementation.md`, with an ASCII aesthetic
inspired by SkillSync but distinct in execution.

---

## Flow Overview

1. Landing: user sees a focused hero with a single GitHub username input.
2. Submit: frontend POSTs to backend; backend checks cache, otherwise analyzes.
3. Progress: frontend polls and renders real-time pipeline steps.
4. Results: dashboard with scores, charts, insights, and interview prompts.

---

## Screen-by-Screen UI Flow

### 1) Landing / Input

- Purpose: fast, founder-friendly entry point.
- UI elements:
  - Hero copy: "Analyze a GitHub profile in ~3 minutes."
  - Input: `> analyze <github_handle>`
  - Primary action: ASCII-styled button/prompt (e.g., `[ run scan ]`)
- ASCII aesthetic:
  - Monospace typography for all primary UI.
  - Box-drawn layout frames (custom, not default +---+).
  - Subtle scanline/grid background for texture.

### 2) Analysis / Progress

- Purpose: show live pipeline state to build trust and reduce perceived wait.
- UI elements:
  - Vertical pipeline tracker:
    - repo discovery
    - code extraction
    - static analysis
    - AI analysis
    - scoring
    - insight generation
  - Status markers (spinner/ellipsis/check).
  - Optional sidebar showing what each step evaluates.
- ASCII aesthetic:
  - "Streaming" data rows in a terminal-style panel.
  - Step list aligned like a CLI task runner.

### 3) Results / Dashboard

- Purpose: give a fast, recruiter-ready summary of candidate quality.
- UI elements (from docs):
  - Ranked candidate list (batch mode) or single summary.
  - Overall Skill Score (0-100).
  - AI Detection Percentage.
  - Category breakdowns (radar chart or bar chart).
  - Red Flags list.
  - Strengths list.
  - Recommended Interview Questions.
- ASCII aesthetic:
  - Panels framed in box-drawing characters.
  - Charts embedded in framed "console windows."
  - Bold headers using ASCII dividers, not standard UI cards.

---

## Signature Look (SkillSync-inspired, but unique)

- Theme: "Founders' terminal," not "hacker terminal."
- Colors: warm amber + slate + muted off-white (avoid neon green).
- Motion:
  - One page-load reveal.
  - Staggered checkmarks for pipeline steps.
  - Subtle "data tape" animation tied to progress.
- Visual motifs:
  - Custom ASCII borders for each panel.
  - Blueprint-like grid or scanline texture background.

---

## Key UI Modules

- `UsernameInput` with terminal prompt styling.
- `ProgressTracker` with step states and live status.
- `ScoreSummary` (overall + AI %).
- `CategoryBreakdownChart` (radar or bar).
- `RedFlagsAndStrengths` (paired lists).
- `InterviewHints` (contextual prompts).

---

## Notes

- The UI should feel fast, lightweight, and opinionated.
- ASCII flavor is a brand signature, not a gimmick.
- The primary CTA is always the username input.
