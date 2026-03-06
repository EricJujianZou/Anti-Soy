# PRD: Toggle for Same Interview Questions (All Candidates)

## Problem
For batch resume screening, recruiters may want the same generic questions for all candidates to ensure fair comparison. Currently all questions are LLM-generated per-candidate, which also costs time and API credits.

## Design
- Pre-analysis toggle on the resume upload page (same page for single and batch uploads)
- When ON: skip LLM question generation entirely, return hardcoded fully generic questions
- Questions are the same for every candidate — no repo/language context injected
- Business value evaluation still runs (only questions are skipped)

## Hardcoded Questions (5 total, covering all categories)
```json
[
  {
    "question": "Walk me through the architecture of this project. Why did you organize it this way?",
    "based_on": "Project structure and design decisions",
    "probes": "system_design",
    "category": "design_choice"
  },
  {
    "question": "What was the most challenging technical problem you solved in this project?",
    "based_on": "Overall technical complexity",
    "probes": "problem_solving",
    "category": "technical_depth"
  },
  {
    "question": "If this project had to handle 100x the current load, what would break first and how would you fix it?",
    "based_on": "Scalability considerations",
    "probes": "scaling_awareness",
    "category": "technical_depth"
  },
  {
    "question": "What security considerations did you think about when building this?",
    "based_on": "Security awareness",
    "probes": "security_awareness",
    "category": "code_issue"
  },
  {
    "question": "Who is the target user for this project, and how did you validate that this solves their problem?",
    "based_on": "Business value and user research",
    "probes": "product_thinking",
    "category": "business_value"
  }
]
```

## Implementation

### 1. Define hardcoded questions — `server/prompt_modules.py`
- Add `HARDCODED_INTERVIEW_QUESTIONS` list constant with the 5 questions above

### 2. Add toggle to upload page — `client/src/pages/UploadPage.tsx`
- Add `useGenericQuestions` boolean state (default false)
- Add checkbox after priority checkboxes (~line 161), styled consistently with existing checkboxes
- Label: "Use same interview questions for all candidates"

### 3. Pass flag through client stack
- `client/src/pages/UploadPage.tsx` → pass `useGenericQuestions` to `handleUpload()`
- `client/src/hooks/useBatchUpload.ts` → accept flag, pass to `uploadBatch()`
- `client/src/services/batchApi.ts` → append `use_generic_questions` to FormData

### 4. Server-side handling
- `server/main.py` `upload_batch()`: Parse `use_generic_questions` from Form data
- `server/models.py`: Add `use_generic_questions` Integer column to `BatchJob` (default 0)
- `server/v2/batch_processor.py`: Read flag from BatchJob, pass to evaluation pipeline
- `server/v2/analysis_service.py` `run_evaluation_pipeline()`: If flag True, return `HARDCODED_INTERVIEW_QUESTIONS` instead of calling Gemini. Business value evaluation still runs.

## Files to Modify
- `server/prompt_modules.py`
- `client/src/pages/UploadPage.tsx`
- `client/src/hooks/useBatchUpload.ts`
- `client/src/services/batchApi.ts`
- `server/main.py`
- `server/models.py`
- `server/v2/batch_processor.py`
- `server/v2/analysis_service.py`

## Verification
- Toggle ON: Upload resumes, verify all candidates get identical generic questions.
- Toggle OFF: Verify LLM-generated questions still work as before.
- Verify business value evaluation still runs regardless of toggle state.
