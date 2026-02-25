REQ-003: Backend — Batch API Endpoints & Background Processing

  Branch: feat/batch-api
  Depends on: REQ-001 merged (models/schemas), REQ-002 merged (resume pipeline) — can stub during development
  Files owned: server/main.py (additions only), server/v2/batch_processor.py (new file)

  ---
  Overview

  Two new API endpoints and a background task orchestrator that processes up to 10 resumes concurrently: resume → GitHub profile → repo
  resolution → full analysis pipeline per candidate.

  ---
  POST /batch/upload

  - Content-Type: multipart/form-data, field name: resumes
  - Validation:
    - Max 10 files — return HTTP 400 if exceeded
    - Only .pdf and .docx extensions — return HTTP 400 for others
  - On success:
    a. Generate batch_id = str(uuid.uuid4())
    b. Read all file bytes into memory (do not write to disk in this thread)
    c. Create BatchJob in DB (status = "pending")
    d. Create one BatchItem per file (status = "pending", filename set, all other fields null)
    e. Kick off background task: BackgroundTasks.add_task(process_batch, batch_id, file_bytes_map)
    f. Return {"batch_id": batch_id} immediately
  - Rate limit: 5/minute

  ---
  GET /batch/{batch_id}/status

  - Return 404 if batch_id not found
  - Query all BatchItem rows for this batch
  - For each item with status == "completed": join to Repo and RepoAnalysis to populate verdict (type + confidence). Join to RepoEvaluation (if 
  exists) to populate standout_features (parse JSON, may be empty list [])
  - Return BatchStatusResponse (see REQ-001)
  - Rate limit: 60/minute

  ---
  batch_processor.py

  async def process_batch(batch_id: str, file_bytes_map: dict[str, bytes])
  - Update BatchJob.status → "running"
  - Use asyncio.gather() to run all items concurrently
  - After all complete: update BatchJob.status → "completed"

  async def process_single_item(batch_item_id: int, filename: str, file_bytes: bytes)

  ┌──────┬──────────────────────────────────────────────────────────────────────────────────────────────────┬───────────────────────────────┐   
  │ Step │                                              Action                                              │          On failure           │   
  ├──────┼──────────────────────────────────────────────────────────────────────────────────────────────────┼───────────────────────────────┤   
  │ 1    │ Set item status → "running"                                                                      │ —                             │   
  ├──────┼──────────────────────────────────────────────────────────────────────────────────────────────────┼───────────────────────────────┤   
  │ 2    │ Write file_bytes to tempfile.NamedTemporaryFile                                                  │ Set error, return             │   
  ├──────┼──────────────────────────────────────────────────────────────────────────────────────────────────┼───────────────────────────────┤   
  │ 3    │ Call GeneralExtractor(temp_path) → resume_dump                                                   │ Set error: "Failed to read    │   
  │      │                                                                                                  │ resume file."                 │   
  ├──────┼──────────────────────────────────────────────────────────────────────────────────────────────────┼───────────────────────────────┤   
  │ 4    │ Call ExtractCandidateInfo(resume_dump) → CandidateInfo                                           │ Set error: "Failed to extract │   
  │      │                                                                                                  │  resume data."                │   
  ├──────┼──────────────────────────────────────────────────────────────────────────────────────────────────┼───────────────────────────────┤   
  │ 5    │ Update item: candidate_name, candidate_university, github_profile_url                            │ —                             │   
  ├──────┼──────────────────────────────────────────────────────────────────────────────────────────────────┼───────────────────────────────┤   
  │      │                                                                                                  │ Set error: "Could not resolve │   
  │ 6    │ If github_profile_url is None:                                                                   │  GitHub profile. Check        │   
  │      │                                                                                                  │ resume."                      │   
  ├──────┼──────────────────────────────────────────────────────────────────────────────────────────────────┼───────────────────────────────┤   
  │ 7    │ Call ResolveRepo(github_profile_url, project_names) → repo_url                                   │ Set error: exception message  │   
  ├──────┼──────────────────────────────────────────────────────────────────────────────────────────────────┼───────────────────────────────┤   
  │ 8    │ Update item: repo_url                                                                            │ —                             │   
  ├──────┼──────────────────────────────────────────────────────────────────────────────────────────────────┼───────────────────────────────┤   
  │      │ Run full analysis pipeline (reuse logic from /analyze-stream): clone repo, extract data, run all │ Set error on any              │   
  │ 9    │  3 analyzers, compute verdict, save RepoAnalysis to DB. Then run LLM evaluation (Gemini calls),  │ unrecoverable failure         │   
  │      │ save RepoEvaluation to DB                                                                        │                               │   
  ├──────┼──────────────────────────────────────────────────────────────────────────────────────────────────┼───────────────────────────────┤   
  │ 10   │ Update item: repo_id, status → "completed", completed_at = now()                                 │ —                             │   
  └──────┴──────────────────────────────────────────────────────────────────────────────────────────────────┴───────────────────────────────┘   

  Error state: on any failure in steps 2-9, set status → "error", error_message = <message>, completed_at = now(), then return (do not crash the
   whole batch).

  ---
  Acceptance Criteria

  - Uploading 3 resumes returns batch_id immediately (< 500ms)
  - GET status returns correct status for each item as they complete
  - If one item fails (e.g., no GitHub found), the rest continue processing
  - Batch continues processing even if the client disconnects
  - No modifications to existing /analyze, /analyze-stream, or /repo/:id endpoints
