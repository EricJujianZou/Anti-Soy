# Branch 3: Evaluation Prompt Rewrite

## Context
The current LLM evaluation prompt is tuned for what startup founders find impressive (novelty, unique tech choices). This causes production codebases like Uber's Cadence to be marked as "nothing stands out," which kills credibility with hiring managers. The prompt needs to be rewritten to serve multiple evaluation contexts based on user selected priorities (see Branch 2 for checkbox UI).

## Objective
Replace the single hardcoded evaluation prompt with a modular prompt system that adjusts weights and criteria based on the priorities the user selects.

## Current State
- Single prompt lives in a single file, hardcoded in a function.
- The "standout features" section has a high bar biased toward startup/novelty criteria.
- The comparison baseline is "GPT wrappers, to do apps, CRUD APIs, tutorial clones" which is only relevant for junior/hobby projects, not production code.
- LLM used: Gemini Flash 2.0.

## Architecture

### Prompt Assembly
Instead of one monolithic prompt, build the evaluation prompt from modules:

```
BASE_PROMPT (always included)
+ PRIORITY_MODULE_code_quality (if selected)
+ PRIORITY_MODULE_security (if selected)
+ PRIORITY_MODULE_originality (if selected)
+ PRIORITY_MODULE_production_readiness (if selected)
+ PRIORITY_MODULE_ai_detection (if selected)
+ OUTPUT_FORMAT (always included)
```

The function receives the `priorities` array from the API (see Branch 2) and assembles the prompt accordingly. If Branch 2 is not merged yet, default to all priorities selected.

### Base Prompt
Keep the general structure: analyze the repo, provide assessment, generate interview questions. But remove the founder bias. Replace:

- "Would make a startup founder say 'this person built something real'" → "Would demonstrate competence relevant to the selected evaluation criteria"
- Remove the comparison list of "GPT wrappers, to do apps" etc. Replace with a more neutral baseline appropriate to each priority module.

### Priority Modules

**code_quality:**
Weight these signals HIGH:
- Consistent error handling patterns
- Clear separation of concerns / architecture
- Readable naming conventions
- Appropriate use of language idioms (not writing Java style GO, etc.)
- Reasonable file sizes and module organization
- Meaningful comments (not redundant)
- DRY principles applied without over abstraction

Standout bar: "Code that a senior engineer would approve in code review without major revisions."

**security:**
Weight these signals HIGH:
- Input validation and sanitization
- Auth implementation quality
- SQL injection prevention
- XSS prevention
- Secrets management (no hardcoded keys/tokens)
- Dependency vulnerability awareness
- Safe regex patterns
- Timeout handling on external requests

Standout bar: "Code that would pass a basic security audit."

**originality:**
This is closest to the current prompt but recalibrated:
- Does it solve a real user problem (not a tutorial project)?
- Is the approach novel or differentiated?
- Is there evidence of original thinking vs following a tutorial step by step?
- Comparison baseline: common project types in that language/domain

Standout bar: "A project that shows independent problem solving, not just following instructions."

**production_readiness:**
Weight these signals HIGH:
- Test coverage presence and quality
- CI/CD configuration
- Environment configuration / config management
- Logging and observability
- Dockerfile / deployment config
- Database migration patterns
- Rate limiting / retry logic
- Documentation quality (README, API docs)

Standout bar: "Code that could be deployed to production with minimal additional work."

**ai_detection:**
Keep current AI detection analysis but integrate into the modular system:
- Redundant comments pattern
- Emoji usage in code
- Overly verbose variable names
- Generic boilerplate patterns
- ML classifier confidence score
- Heuristic signals

### Interview Question Generation
CRITICAL FIX: Interview questions must be tailored to the selected priorities.

- If code_quality selected: Questions about design decisions, trade offs, why they structured code a certain way.
- If security selected: Questions about threat models, how they'd handle specific attack vectors in their code.
- If originality selected: Questions about problem discovery, alternative approaches considered, user research.
- If production_readiness selected: Questions about deployment, scaling, monitoring, incident response.
- If ai_detection flagged high: Questions that test deep understanding of the code ("walk me through this function line by line, why did you choose this approach?").

Do NOT generate generic questions about print statements, logging, or unit tests unless directly relevant.

### Standout Features Recalibration
The "nothing stands out" verdict should be RARE for production codebases. New logic:

- If heuristic/ML model says project is senior level and solves real problem, the LLM MUST NOT override with "nothing stands out" unless it has strong specific evidence.
- When all priorities are selected, the bar for "stands out" should be calibrated to the project's apparent scope. A mature OSS project with thousands of stars is evaluated differently than a personal weekend project.
- Add a field: `project_scope_estimate: hobby | coursework | professional | production_oss` and adjust the standout bar accordingly.

## Testing
- Test with Cadence repo (https://github.com/cadence-workflow/cadence): Should surface standout features in code quality and production readiness, NOT return "nothing stands out."
- Test with a known tutorial clone project: Should correctly identify low originality.
- Test with a project containing obvious AI generated code: Should flag appropriately.
- Test same project with different priority selections to verify prompt modules change the output.

## Out of Scope
- UI for checkboxes (Branch 2).
- Language specific heuristic fixes (Branch 1).
- Batch scanning (Carlton).
- Resume parsing (Carlton).

## Definition of Done
- Monolithic prompt replaced with modular prompt assembly.
- All 5 priority modules written and functional.
- Interview questions tailored to selected priorities.
- Cadence repo no longer returns "nothing stands out."
- Output quality is consistent across repeated scans of the same repo with same priorities.
- Backwards compatible: if no priorities passed, defaults to all selected and output quality is equal to or better than current.
