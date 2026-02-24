# Branch 2: Evaluation Priority Checkboxes

## Context
Anti Soy currently uses a single evaluation criteria for all scans. Different users care about different things (a government hiring manager cares about security + code quality, a startup founder cares about originality + AI detection). Adding checkboxes lets users customize what the evaluation weights, making results more relevant per use case.

## Objective
Add a checkbox group to the scan input UI that lets users select evaluation priorities. These selections get passed to the backend and influence the LLM evaluation prompt.

## Checkbox Options
Five options, all checked by default:

1. **Code Quality** — Clean architecture, error handling, readability, maintainability
2. **Security** — Vulnerabilities, unsafe patterns, injection risks, auth issues
3. **Originality / Innovation** — Novel approach, solves real problem, not a tutorial clone
4. **Production Readiness** — Testing, CI/CD, logging, deployment config, scalability patterns
5. **AI Detection** — Confidence score on whether code is AI generated or human written

Default state: ALL checked. User can uncheck any. Minimum 1 must remain checked.

## Frontend Changes
- Location: Above or beside the existing GitHub link input field.
- Component: Checkbox group with labels. Clean, minimal UI. No tooltip descriptions needed for MVP.
- When user submits a scan, selected priorities are sent as an array in the API request body (e.g., `priorities: ["code_quality", "security", "ai_detection"]`).
- Read existing UI code to match current styling and component patterns.

## Backend Changes
- API endpoint for scan analysis should accept an optional `priorities` array parameter.
- If not provided, default to all five (backwards compatible).
- Pass the priorities array to the LLM evaluation function.
- The priorities determine WHICH evaluation prompt template is assembled (see Branch 3 for prompt details). This branch only handles passing the selections through. If Branch 3 is not yet merged, use a placeholder that logs the received priorities.

## API Contract
```json
POST /analyze (or whatever the current endpoint is)
{
  "repo_url": "https://github.com/user/repo",
  "priorities": ["code_quality", "security", "originality", "production_readiness", "ai_detection"]
}
```

Keys: `code_quality`, `security`, `originality`, `production_readiness`, `ai_detection`

## Out of Scope
- Writing the actual prompt variants (Branch 3).
- Language compatibility fixes (Branch 1).
- Batch scanning (Carlton).
- Resume parsing (Carlton).

## Definition of Done
- Checkbox group renders on scan page, all checked by default.
- Unchecking/checking works, minimum 1 enforced.
- Selected priorities sent in API request.
- Backend receives and passes priorities to evaluation function.
- UI matches existing design language.
- Works on both desktop and mobile.
