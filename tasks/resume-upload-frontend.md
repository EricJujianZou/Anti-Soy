 REQ-004: Frontend — Resume Upload Page & Routing

  Branch: feat/frontend-upload
  Can start: Immediately (can mock backend with hardcoded batch_id during development)
  Files owned: client/src/App.tsx, client/src/pages/Index.tsx, client/src/pages/UploadPage.tsx (new), client/src/services/batchApi.ts (new),    
  client/src/hooks/useBatchUpload.ts (new)

  ---
  Overview

  Adds the resume upload flow: a new CTA on the landing page, a dedicated upload page with drag-and-drop, and the API service layer used by both
   this ticket and REQ-005.

  ---
  Landing Page (Index.tsx)

  Add a rectangular button between the GitHub URL input and the Run Scan button:

  [ Upload Candidate Resumes ]

  - Clicking navigates to /upload
  - Styled as a secondary/outlined action (not as prominent as Run Scan)
  - Label: "Upload Candidate Resumes"

  ---
  Routing (App.tsx)

  Add two new routes:
  <Route path="/upload" element={<UploadPage />} />
  <Route path="/dashboard/:batchId" element={<BatchDashboard />} />

  BatchDashboard is created by REQ-005. Add it as a lazy import with a simple loading fallback so the app compiles while REQ-005 is in
  development:
  const BatchDashboard = React.lazy(() => import("./pages/BatchDashboard"));

  ---
  Upload Page (UploadPage.tsx)

  Route: /upload

  Layout:
  - Reuse existing <Header /> component
  - Page title: "Upload Candidate Resumes"
  - Subtitle: "Upload up to 10 resumes to analyze candidates in batch"

  Dropzone area:
  - Drag-and-drop zone accepting .pdf and .docx only
  - Click-to-browse also works
  - Visual states: idle, drag-over (highlighted border), files-loaded
  - File list below dropzone: each row shows filename, file size, and a remove (×) button
  - File counter: "{n} / 10 resumes selected" — counter turns red at 10
  - If user attempts to add files beyond 10: show toast error "Maximum 10 resumes allowed"
  - If user drops an unsupported file type: show toast error "Only .pdf and .docx files are supported"

  Run Analysis button:
  - Disabled and greyed out when 0 files selected
  - Label: "Run Analysis"
  - On click:
    a. Button becomes loading state (spinner, disabled)
    b. Call uploadBatch(files) from batchApi.ts
    c. On success: save batch_id to localStorage key antisoy_batch_id, navigate to /dashboard/{batch_id}
    d. On error: show toast "Upload failed. Please try again.", re-enable button
  - No back-navigation: once navigated to dashboard, this page is not reachable via browser back (use navigate(..., { replace: true }))

  ---
  API Service (batchApi.ts)

  const API_BASE = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

  export async function uploadBatch(files: File[]): Promise<{ batch_id: string }> {
    // Build FormData with field name "resumes", POST to /batch/upload
  }

  export async function getBatchStatus(batchId: string): Promise<BatchStatusResponse> {
    // GET /batch/{batchId}/status
  }

  Both functions defined here. REQ-005 imports getBatchStatus from this file.

  Also define the TypeScript types here:
  export interface BatchItemStatus { ... }   // mirrors REQ-001 schema
  export interface BatchStatusResponse { ... }

  ---
  Acceptance Criteria

  - User can drag-and-drop or click to select PDF/DOCX files
  - Adding more than 10 files shows an error and does not add the extras
  - Run Analysis button is disabled with 0 files
  - Successful upload stores batch_id in localStorage and navigates to /dashboard/{batch_id}
  - Back button after navigation does not return to the upload page
  - /dashboard/:batchId route is registered in App.tsx

  REQ-005: Frontend — Batch Dashboard Page

  Branch: feat/frontend-dashboard
  Depends on: REQ-004 (for batchApi.ts types and the route registration in App.tsx)
  Files owned: client/src/pages/BatchDashboard.tsx (new), client/src/hooks/useBatchStatus.ts (new)

  ---
  Overview

  The dashboard page that recruiters land on after submitting a batch. Shows a live-updating grid of candidate cards, each reflecting the       
  current processing state. Cards become clickable and navigate to the existing results page when complete.

  ---
  Route & Mounting

  Route: /dashboard/:batchId (registered by REQ-004)

  On mount:
  - Extract batchId from URL params (source of truth)
  - Begin polling immediately

  ---
  Page Layout

  - Reuse <Header />
  - Title: "Candidate Batch Analysis"
  - Subtitle: "{completed_items} of {total_items} complete" — updates as polling returns new data
  - Responsive grid of candidate cards: 3 columns on desktop, 2 on tablet, 1 on mobile

  ---
  Candidate Card States

  Pending / Running:
  ┌─────────────────────────────────┐
  │  ◌  [spinning]                  │
  │  John Doe                       │
  │  University of Michigan         │
  │  Analyzing...                   │
  │  —                              │
  └─────────────────────────────────┘
  - Not clickable (cursor: default, no hover)

  Completed:
  ┌─────────────────────────────────┐
  │  ✓  [verdict badge]  SENIOR     │
  │  John Doe                       │
  │  University of Michigan         │
  │  "Uses proper abstraction..."   │
  └─────────────────────────────────┘
  - Clickable → navigate("/repo/{repo_id}")
  - Hover: border highlight, cursor pointer, subtle lift/shadow
  - Verdict badge colors: Slop Coder = red, Junior = yellow/amber, Senior = green, Good AI Coder = blue
  - 1-liner: standout_features[0] if non-empty, else "Nothing stands out about this project"

  Error:
  ┌─────────────────────────────────┐
  │  ✕  UNRESOLVABLE                │
  │  john_doe_resume.pdf            │
  │  —                              │
  │  "Could not resolve GitHub..."  │
  └─────────────────────────────────┘
  - Not clickable
  - Red/muted error styling
  - Name field falls back to filename if candidate_name is unavailable
  - 1-liner shows error_message

  ---
  Polling Hook (useBatchStatus.ts)

  function useBatchStatus(batchId: string): {
    data: BatchStatusResponse | null;
    isLoading: boolean;
    error: string | null;
  }

  - Poll getBatchStatus(batchId) every 3 seconds
  - Stop polling when data.status === "completed"
  - Pause polling when document.visibilityState === "hidden" (tab not visible), resume on "visible" — avoids unnecessary requests when user tabs
   away
  - On 404 response: set error = "Batch not found.", stop polling
  - On other errors: log and continue polling (transient network errors shouldn't kill the dashboard)

  ---
  Persistence / Return Navigation

  - Since batchId is in the URL, navigating back to /dashboard/{batchId} (browser back, sharing the link, waking from sleep) automatically      
  resumes polling
  - No additional localStorage reads needed on this page

  ---
  Acceptance Criteria

  - Cards render in the correct state (pending, completed, error) based on API response
  - Dashboard updates automatically as items complete (without page refresh)
  - Completed cards navigate to /repo/{repo_id} on click
  - Pending/error cards are not clickable
  - Polling stops when all items are complete
  - Polling pauses when tab is hidden and resumes when tab is focused again
  - Dashboard loads correctly when navigating back after closing the browser (URL-based recovery)
  - candidate_name falls back to filename on error cards if name extraction failed

  ---
  Summary

  ┌─────────┬─────────────────────────┬───────────────────────┬────────────────────────────────────────────────────────────────────┐
  │   REQ   │         Branch          │      Depends On       │                            Files Owned                             │
  ├─────────┼─────────────────────────┼───────────────────────┼────────────────────────────────────────────────────────────────────┤
  │ REQ-001 │ feat/batch-data-models  │ None                  │ models.py, v2/schemas.py                                           │
  ├─────────┼─────────────────────────┼───────────────────────┼────────────────────────────────────────────────────────────────────┤
  │ REQ-002 │ feat/resume-enhancement │ None                  │ v2/resume_parser.py, v2/github_resolver.py                         │
  ├─────────┼─────────────────────────┼───────────────────────┼────────────────────────────────────────────────────────────────────┤
  │ REQ-003 │ feat/batch-api          │ REQ-001, REQ-002      │ main.py (additions), v2/batch_processor.py                         │
  ├─────────┼─────────────────────────┼───────────────────────┼────────────────────────────────────────────────────────────────────┤
  │ REQ-004 │ feat/frontend-upload    │ None (can mock)       │ App.tsx, Index.tsx, UploadPage.tsx, batchApi.ts, useBatchUpload.ts │
  ├─────────┼─────────────────────────┼───────────────────────┼────────────────────────────────────────────────────────────────────┤
  │ REQ-005 │ feat/frontend-dashboard │ REQ-004 (batchApi.ts) │ BatchDashboard.tsx, useBatchStatus.ts                              │
  └─────────┴─────────────────────────┴───────────────────────┴────────────────────────────────────────────────────────────────────┘