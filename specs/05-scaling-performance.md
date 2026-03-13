# Spec 05: Scaling & Performance — Cloud Tasks Distributed Processing

**Status:** Ready for implementation
**Dependencies:** None (independent of other specs)
**Estimated batch throughput target:** 1,000 resumes processed in ≤ 2 hours
**Budget constraint:** $20 USD/month all-in

---

## Guardrails for the Implementing Agent

> **READ THIS FIRST.**
>
> - **Ask before assuming** on anything not explicitly specified below (Cloud Run region, project ID, queue name, etc.) — these will differ per deployment environment.
> - **Do not modify** `analyze_stream`, `/analyze`, `/evaluate`, or any single-repo endpoint. This spec only touches the batch pipeline.
> - **Do not remove** the existing `BATCH_ITEM_CONCURRENCY` asyncio path. It must remain as a fallback controlled by `TASK_MODE`.
> - **Do not upgrade** Neon tier or Cloud Run tier without confirming with the user — cost decisions are the user's to make.
> - **Confirm** Cloud Run service URL and Google Cloud project ID with the user before writing any Cloud Tasks dispatch code.
> - If a step requires a Cloud Console action the agent cannot perform programmatically, output the exact steps the user needs to take in the Cloud Console as a numbered checklist.

---

## 1. Problem Statement

### Current Architecture

```
[User uploads 10 resumes]
        │
        ▼
POST /batch/upload
        │  BackgroundTask (FastAPI)
        ▼
process_batch()  ←── single Cloud Run instance, 512MB RAM
        │
        ├── asyncio.Semaphore(4)  ←── max 4 concurrent items
        │
        ├── process_single_item(item_1)  ←── clone + analyze + LLM (~90s each)
        ├── process_single_item(item_2)
        ├── process_single_item(item_3)
        └── process_single_item(item_4)
```

**Observed bottlenecks:**
1. **Concurrency ceiling:** `BATCH_ITEM_CONCURRENCY=4` on a single instance. For 1,000 resumes × 3 repos each × 90s per repo = ~75 hours sequential, ~19 hours at 4 concurrent. Completely unacceptable.
2. **Single instance failure domain:** If the Cloud Run instance crashes, the entire in-flight batch is lost. `startup_event` attempts recovery but re-queues everything from scratch.
3. **Memory:** 512MB is tight when cloning multiple repos concurrently (each `git clone --depth 100` can buffer 50–150MB).
4. **Cloud Run request timeout:** Background tasks keep the instance alive, but Cloud Run will scale down idle instances. If the only instance is processing a large batch and a deploy happens, the batch is silently killed.
5. **Neon connection pressure:** `pool_size=3 + max_overflow=5` in `batch_processor.py` and `pool_size=5 + max_overflow=10` in `main.py` = up to 18 simultaneous DB connections from one instance. At 4 concurrency this is fine; at higher concurrency it exhausts Neon free tier limits.

### Target Architecture

```
[User uploads 1,000 resumes]
        │
        ▼
POST /batch/upload
  → Creates BatchJob + BatchItems in DB
  → Enqueues 1,000 Cloud Tasks (one per BatchItem)
  → Returns batch_id immediately
        │
        ▼
Google Cloud Tasks Queue (max 20 concurrent dispatches)
        │
        ├── POST /tasks/process-item {"item_id": 1}  → Cloud Run instance A
        ├── POST /tasks/process-item {"item_id": 2}  → Cloud Run instance B
        ├── POST /tasks/process-item {"item_id": 3}  → Cloud Run instance C
        └── ...20 instances in parallel...

[Frontend polls GET /batch/{id}/status every 5s — no connection kept open]
[User sees progress: "47 / 1000 complete" — can close browser and return]
```

**Estimated throughput:** 8 instances × 1 item per instance × ~90s per item = ~8 items/90s = ~320 items/hour → 1,000 resumes ≈ **3 hours** wall-clock time.

---

## 2. Cost Analysis

### Cloud Run (compute)

- Free tier: 360,000 vCPU-seconds/month + 180,000 GiB-seconds/month
- 1,000 items × 3 repos × 90s × 1 vCPU = 270,000 vCPU-seconds → **within free tier for 1 batch/month**
- Memory at 1GB: 1,000 × 270s × 1GiB = 270,000 GiB-seconds → **within free tier**
- Upgrade Cloud Run memory from 512MB → **1GB** (no cost change on free tier, needed for stability)
- Paid overage rate if exceeded: $0.000024/vCPU-s + $0.0000025/GiB-s → ~$6.48/extra 1,000-item batch

### Cloud Tasks

- Free tier: 1,000,000 task operations/month
- 1,000 resumes × ~3 task operations each (create + dispatch + delete) = 3,000 ops → **free**

### Neon Postgres

- Free tier: 0.25 compute units, ~20 pooled connections via PgBouncer pooler
- At 8 concurrent Cloud Run instances (concurrency cap), each needing 1–2 connections: 8–16 connections → fits free tier comfortably.
- If connection exhaustion occurs despite this: upgrade to Neon Launch ($19/month).

### Gemini Flash

- Current model: `gemini-2.0-flash` (verify this in `gemini_client.py`)
- Flash pricing: ~$0.075/1M input tokens, ~$0.30/1M output tokens
- Per-repo evaluation: ~2,000 tokens input + ~500 tokens output ≈ $0.000300/call
- 1,000 resumes × 3 repos × $0.000300 = **$0.90 per 1,000-resume batch**

### Total estimated cost per 1,000-resume batch

| Service | Cost |
|---|---|
| Cloud Run | $0 (within free tier) |
| Cloud Tasks | $0 (within free tier) |
| Neon | $0 (if concurrency ≤ 15) or $19/mo |
| Gemini Flash | ~$0.90 |
| **Total** | **~$0.90–$19.90/batch** |

---

## 3. UX Change: Async Processing Model

### Current behavior
User uploads → redirect to `/upload#batch/{id}` → frontend holds open HTTP polling loop → user must keep tab open.

### New behavior
User uploads → redirect to `/upload#batch/{id}` → frontend polls every 5s → **user can close browser and return** — results persist in DB forever.

### Frontend messaging to add

In `BatchDashboard.tsx` (or wherever the status UI lives), add a banner when `batch.status === "running"`:

```
⏳ Processing in background — this may take 1–2 hours for large batches.
   You can close this tab and come back. Bookmark this URL to return:
   [copy URL button]
```

When `batch.status === "completed"`:

```
✅ Batch complete — X of Y candidates analyzed successfully.
```

**Do not add a loading spinner that suggests the user must wait.** Replace any spinner with a progress bar showing `completed_items / total_items`.

---

## 4. Implementation Plan

### Phase 1 — Quick wins, no infrastructure change (implement first)

#### 1A. Lift Cloud Run memory to 1GB

This is a Cloud Console change only. **No code changes.**

**Cloud Console steps (provide these to the user):**
1. Go to Cloud Run → select the `anti-soy` service
2. Click **Edit & Deploy New Revision**
3. Under **Capacity**, set Memory to **1 GiB**
4. Set CPU to **1 CPU** (no change if already 1)
5. Set **Maximum number of instances** to **20**
6. Set **Minimum number of instances** to **0**
7. Set **Request timeout** to **300 seconds** (5 minutes — for task handler endpoint)
8. Click **Deploy**

#### 1B. Tune BATCH_ITEM_CONCURRENCY

In `server/v2/batch_processor.py`, the default is currently `4`. This is only relevant in asyncio mode (fallback when Cloud Tasks is not configured). No code change needed — it's already env-configurable via `BATCH_ITEM_CONCURRENCY`.

#### 1C. Switch to Neon pooler endpoint

**No code changes required.** This is an environment variable change.

In Cloud Run environment variables, change `DATABASE_URL` from the **direct** Neon connection string to the **pooler** connection string.

- Direct: `postgresql://user:pass@ep-xxx.us-east-2.aws.neon.tech/neondb`
- Pooler: `postgresql://user:pass@ep-xxx-pooler.us-east-2.aws.neon.tech/neondb?pgbouncer=true`

Find the pooler URL in the Neon dashboard under **Connection Details → Pooler connection**.

**Cloud Console steps (provide these to the user):**
1. Go to Cloud Run → select the service → **Edit & Deploy New Revision**
2. Under **Variables & Secrets**, update `DATABASE_URL` to the pooler URL
3. Deploy

Also add `?pgbouncer=true` to suppress SQLAlchemy prepared statement warnings with PgBouncer. In `batch_processor.py`, update the engine creation:

**File:** `server/v2/batch_processor.py`
**Change:** Add `connect_args` to disable prepared statements for PgBouncer compatibility.

```python
# BEFORE (line 22-28):
engine = create_engine(
    os.environ["DATABASE_URL"],
    pool_pre_ping=True,
    pool_size=3,
    max_overflow=5,
)

# AFTER:
engine = create_engine(
    os.environ["DATABASE_URL"],
    pool_pre_ping=True,
    pool_size=1,          # reduced — Cloud Tasks gives us horizontal scale instead; 8 instances × 2 max = 16 connections (fits Neon free tier)
    max_overflow=1,
    connect_args={"options": "-c statement_timeout=60000"},  # 60s query timeout
)
```

Same change in `server/main.py` (the main engine):

```python
# BEFORE (line 81-86):
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
)

# AFTER:
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_size=3,
    max_overflow=5,
    connect_args={"options": "-c statement_timeout=60000"},
)
```

---

### Phase 2 — Cloud Tasks Integration (the main scaling change)

#### 2A. Add Google Cloud Tasks dependency

**File:** `pyproject.toml` (or `requirements.txt` — check which exists)

Add:
```
google-cloud-tasks>=2.16.0
```

Install with: `uv add google-cloud-tasks`

#### 2B. New environment variables

Add to Cloud Run environment (and local `.env` for testing):

```
# Cloud Tasks configuration
TASK_MODE=cloud_tasks                          # "cloud_tasks" or "asyncio" (default: asyncio)
GOOGLE_CLOUD_PROJECT=your-gcp-project-id      # GCP project ID
CLOUD_TASKS_QUEUE=anti-soy-batch              # Queue name (created in 2C)
CLOUD_TASKS_LOCATION=us-central1              # Queue region — must match Cloud Run region
CLOUD_RUN_SERVICE_URL=https://your-service-xxxx.run.app  # Cloud Run service URL
TASK_AUTH_SECRET=<random-32-char-string>      # Shared secret for task auth (generate with: python -c "import secrets; print(secrets.token_hex(32))")
```

> **Agent:** Ask the user to provide `GOOGLE_CLOUD_PROJECT`, `CLOUD_TASKS_LOCATION`, and `CLOUD_RUN_SERVICE_URL` before writing any dispatch code that references these values. Do not hardcode or guess them.

#### 2C. Create Cloud Tasks queue

**Cloud Console steps (provide these to the user):**
1. Go to **Cloud Tasks** in GCP Console
2. Click **Create Queue**
3. Queue name: `anti-soy-batch`
4. Location: same region as your Cloud Run service (e.g., `us-central1`)
5. **Max concurrent dispatches:** `8` (keeps Neon connections safely within free tier; ~3h for 1,000 resumes)
6. **Max attempts:** `3`
7. **Max retry duration:** `1h`
8. **Min/Max backoff:** 10s min, 5m max
9. Click **Create**

Also grant Cloud Tasks the ability to invoke Cloud Run:

```bash
# Run this in Cloud Shell or local gcloud CLI
gcloud run services add-iam-policy-binding anti-soy \
  --member="serviceAccount:YOUR_PROJECT_NUMBER-compute@developer.gserviceaccount.com" \
  --role="roles/run.invoker" \
  --region=YOUR_REGION
```

> **Agent:** Provide these commands to the user as a checklist — you cannot run them yourself.

#### 2D. New file: `server/v2/task_dispatcher.py`

Create this new file. Do not modify any existing files in this step.

```python
"""
Cloud Tasks dispatcher for batch processing.

Enqueues one Cloud Task per BatchItem. Each task calls POST /tasks/process-item
on this same Cloud Run service, which processes the item independently.

Only used when TASK_MODE=cloud_tasks. Falls back to asyncio path otherwise.
"""

import json
import logging
import os
from google.cloud import tasks_v2

logger = logging.getLogger(__name__)

_client: tasks_v2.CloudTasksClient | None = None


def _get_client() -> tasks_v2.CloudTasksClient:
    global _client
    if _client is None:
        _client = tasks_v2.CloudTasksClient()
    return _client


def get_queue_path() -> str:
    project = os.environ["GOOGLE_CLOUD_PROJECT"]
    location = os.environ["CLOUD_TASKS_LOCATION"]
    queue = os.environ["CLOUD_TASKS_QUEUE"]
    return _get_client().queue_path(project, location, queue)


def enqueue_batch_item(item_id: int, batch_id: str) -> str:
    """
    Enqueues a single Cloud Task to process one BatchItem.
    Returns the task name.

    Raises: google.api_core.exceptions.GoogleAPICallError on failure.
    """
    service_url = os.environ["CLOUD_RUN_SERVICE_URL"].rstrip("/")
    auth_secret = os.environ["TASK_AUTH_SECRET"]

    task = {
        "http_request": {
            "http_method": tasks_v2.HttpMethod.POST,
            "url": f"{service_url}/tasks/process-item",
            "headers": {
                "Content-Type": "application/json",
                "X-Task-Auth": auth_secret,
            },
            "body": json.dumps({"item_id": item_id, "batch_id": batch_id}).encode(),
        }
    }

    response = _get_client().create_task(
        request={"parent": get_queue_path(), "task": task}
    )
    logger.info(f"Enqueued task {response.name} for item {item_id} in batch {batch_id}")
    return response.name


def enqueue_batch(item_ids: list[int], batch_id: str) -> int:
    """
    Enqueues Cloud Tasks for all items in a batch.
    Returns count of successfully enqueued tasks.
    Logs failures individually but does not raise — partial enqueue is acceptable
    because failed items remain "pending" and can be re-enqueued.
    """
    success_count = 0
    for item_id in item_ids:
        try:
            enqueue_batch_item(item_id, batch_id)
            success_count += 1
        except Exception as e:
            logger.error(f"Failed to enqueue task for item {item_id}: {e}")
    return success_count
```

#### 2E. New endpoint in `server/main.py`: `POST /tasks/process-item`

Add this endpoint to `main.py` after the existing batch endpoints (around line 617). Do not modify any existing endpoint.

```python
@app.post("/tasks/process-item")
async def handle_task_process_item(request: Request):
    """
    Cloud Tasks callback endpoint. Processes a single BatchItem.

    Authentication: shared secret in X-Task-Auth header.
    Cloud Tasks will retry this endpoint (up to 3 times with backoff) if it
    returns a non-2xx status. Idempotent: if item is already completed, returns 200.

    This endpoint must respond within Cloud Run's request timeout (set to 300s).
    """
    import os

    # Authenticate the task
    auth_secret = os.getenv("TASK_AUTH_SECRET", "")
    task_auth = request.headers.get("X-Task-Auth", "")
    if not auth_secret or task_auth != auth_secret:
        # Return 200 to prevent Cloud Tasks from retrying unauthenticated requests
        # (retrying won't help — the secret won't magically appear)
        logger.warning("Rejected task request with invalid auth header")
        return JSONResponse(status_code=200, content={"status": "rejected", "reason": "invalid_auth"})

    try:
        body = await request.json()
    except Exception:
        return JSONResponse(status_code=400, content={"error": "Invalid JSON body"})

    item_id = body.get("item_id")
    batch_id = body.get("batch_id")

    if not item_id or not batch_id:
        return JSONResponse(status_code=400, content={"error": "item_id and batch_id required"})

    # Check idempotency — if already completed, return 200 immediately
    with Session(engine) as session:
        from models import BatchItem as _BatchItem
        item = session.query(_BatchItem).filter(_BatchItem.id == item_id).first()
        if not item:
            logger.warning(f"Task received for unknown item_id={item_id}")
            return JSONResponse(status_code=200, content={"status": "not_found"})
        if item.status == "completed":
            logger.info(f"Item {item_id} already completed, skipping")
            return JSONResponse(status_code=200, content={"status": "already_complete"})

    # Process the item
    from v2.batch_processor import process_single_item
    from v2.schemas import DEFAULT_PRIORITIES
    import json as _json

    with Session(engine) as session:
        from models import BatchJob as _BatchJob
        batch_job = session.query(_BatchJob).filter(_BatchJob.id == batch_id).first()
        priorities = _json.loads(batch_job.priorities) if batch_job and batch_job.priorities else DEFAULT_PRIORITIES
        use_generic_questions = bool(batch_job.use_generic_questions) if batch_job else False

    await process_single_item(item_id, priorities, use_generic_questions)

    # Check if all items are done — update BatchJob status
    with Session(engine) as session:
        from models import BatchJob as _BatchJob, BatchItem as _BatchItem
        batch_job = session.query(_BatchJob).filter(_BatchJob.id == batch_id).first()
        if batch_job and batch_job.status != "completed":
            pending_count = session.query(_BatchItem).filter(
                _BatchItem.batch_job_id == batch_id,
                _BatchItem.status.in_(["pending", "running"]),
            ).count()
            if pending_count == 0:
                batch_job.status = "completed"
                session.commit()
                logger.info(f"Batch {batch_id} marked completed by task worker")

    return JSONResponse(status_code=200, content={"status": "ok", "item_id": item_id})
```

#### 2F. Modify `POST /batch/upload` in `server/main.py`

**Current behavior (lines 402–404):**
```python
background_tasks.add_task(process_batch, batch_id, priority_list, generic_questions_flag)
return BatchUploadResponse(batch_id=batch_id)
```

**New behavior:**

```python
    task_mode = os.getenv("TASK_MODE", "asyncio")

    if task_mode == "cloud_tasks":
        # Enqueue one Cloud Task per item — distributed processing
        from v2.task_dispatcher import enqueue_batch
        with Session(engine) as session:
            from models import BatchItem as _BatchItem
            item_ids = [
                item.id for item in session.query(_BatchItem)
                .filter(_BatchItem.batch_job_id == batch_id)
                .order_by(_BatchItem.position)
                .all()
            ]
        enqueued = enqueue_batch(item_ids, batch_id)
        logger.info(f"Enqueued {enqueued}/{len(item_ids)} Cloud Tasks for batch {batch_id}")
        # Mark batch as running immediately (Cloud Tasks will drive progress)
        with Session(engine) as session:
            batch_job = session.query(BatchJob).filter(BatchJob.id == batch_id).first()
            if batch_job:
                batch_job.status = "running"
                session.commit()
    else:
        # Fallback: asyncio background task (current behavior)
        background_tasks.add_task(process_batch, batch_id, priority_list, generic_questions_flag)

    return BatchUploadResponse(batch_id=batch_id)
```

#### 2G. Update `startup_event` in `server/main.py`

The startup event currently resumes all unfinished jobs via `asyncio`. In Cloud Tasks mode, this would cause double-processing. Update it:

**Current (lines 656–664):**
```python
@app.on_event("startup")
async def startup_event():
    with Session(engine) as session:
        unfinished_jobs = session.query(BatchJob).filter(BatchJob.status.in_(["pending", "running"])).all()
        for job in unfinished_jobs:
            logger.info(f"Resuming batch job {job.id} on startup")
            priorities = json.loads(job.priorities) if job.priorities else DEFAULT_PRIORITIES
            asyncio.create_task(process_batch(job.id, priorities, job.use_generic_questions))
```

**New:**
```python
@app.on_event("startup")
async def startup_event():
    task_mode = os.getenv("TASK_MODE", "asyncio")

    if task_mode == "cloud_tasks":
        # In Cloud Tasks mode, the queue is durable — tasks survive instance restarts.
        # Re-enqueue only items that were stuck "running" (orphaned mid-process).
        from v2.task_dispatcher import enqueue_batch_item
        with Session(engine) as session:
            stuck_items = session.query(BatchItem).filter(BatchItem.status == "running").all()
            for item in stuck_items:
                logger.info(f"Re-enqueuing stuck item {item.id} in batch {item.batch_job_id}")
                item.status = "pending"  # Reset so process_single_item picks it up
                session.commit()
                try:
                    enqueue_batch_item(item.id, item.batch_job_id)
                except Exception as e:
                    logger.error(f"Failed to re-enqueue item {item.id}: {e}")
    else:
        # asyncio mode: resume as before
        with Session(engine) as session:
            unfinished_jobs = session.query(BatchJob).filter(BatchJob.status.in_(["pending", "running"])).all()
            for job in unfinished_jobs:
                logger.info(f"Resuming batch job {job.id} on startup")
                priorities = json.loads(job.priorities) if job.priorities else DEFAULT_PRIORITIES
                asyncio.create_task(process_batch(job.id, priorities, job.use_generic_questions))
```

---

### Phase 3 — Repo Result Caching (already partially implemented)

The caching check at `server/v2/batch_processor.py` line 183:
```python
if repo.repo_analysis and repo.repo_evaluation:
    continue
```
...already skips re-analysis of known repos. **This is the existing cache and it works correctly.** No changes needed.

**What "big win" means in practice:** If 1,000 resumes include 200 candidates who all forked the same bootcamp starter repo, that repo is analyzed once and the other 199 candidates get instant results from DB. This reduces actual Cloud Task compute time significantly for batches with template repos.

**Verify** the cache is working by checking logs for `"Skipping already-analyzed repo"` messages. Add a log line if not present:

In `server/v2/batch_processor.py`, line 183, add a log statement:
```python
if repo.repo_analysis and repo.repo_evaluation:
    logger.info(f"Cache hit for repo {repo_url} — skipping clone and analysis")
    continue
```

---

## 5. Files Modified Summary

| File | Change | Phase |
|---|---|---|
| `server/v2/batch_processor.py` | Reduce pool_size, add connect_args, add cache log | 1C + 3 |
| `server/main.py` | Reduce pool_size, add connect_args, add `/tasks/process-item` endpoint, modify `/batch/upload`, update `startup_event` | 1C + 2E + 2F + 2G |
| `server/v2/task_dispatcher.py` | **New file** — Cloud Tasks dispatch logic | 2D |
| `pyproject.toml` | Add `google-cloud-tasks` dependency | 2A |

---

## 6. Deployment Checklist for User

The implementing agent should output this checklist at the end as instructions for the user:

**One-time Cloud Console setup (do these before deploying code):**

- [ ] 1. Go to Cloud Run → Edit & Deploy New Revision:
  - Memory: 1 GiB
  - Request timeout: 300 seconds
  - Max instances: 20
  - Min instances: 0
- [ ] 2. Add environment variables in Cloud Run:
  - `TASK_MODE=cloud_tasks`
  - `GOOGLE_CLOUD_PROJECT=<your GCP project ID>`
  - `CLOUD_TASKS_QUEUE=anti-soy-batch`
  - `CLOUD_TASKS_LOCATION=<your Cloud Run region, e.g. us-central1>`
  - `CLOUD_RUN_SERVICE_URL=<your Cloud Run service URL>`
  - `TASK_AUTH_SECRET=<generate with: python -c "import secrets; print(secrets.token_hex(32))">`
  - `DATABASE_URL=<switch to Neon pooler URL>`
- [ ] 3. Create Cloud Tasks queue named `anti-soy-batch` in same region as Cloud Run, max concurrent dispatches = 15
- [ ] 4. Grant Cloud Run service account the `Cloud Tasks Enqueuer` role in IAM
- [ ] 5. Deploy the new code revision
- [ ] 6. Test with a small batch (2-3 resumes) and verify tasks appear in the Cloud Tasks queue in GCP Console
- [ ] 7. Monitor Cloud Run logs for `"Enqueued task"` and `"Cache hit"` messages

**To roll back to asyncio mode:** Set `TASK_MODE=asyncio` in Cloud Run environment variables and redeploy.

---

## 7. Risks and Tradeoffs

### Risk 1: Cloud Tasks idempotency
Cloud Tasks may deliver the same task more than once (at-least-once delivery). The idempotency check at the start of `/tasks/process-item` (checking `item.status == "completed"`) handles this. **Make sure this check exists in the implementation.**

### Risk 2: Partial batch failure
If 50 out of 1,000 tasks fail all 3 retry attempts, those 50 items will be in `error` status. The batch will eventually reach `status=completed` but with some items errored. The frontend already handles this in the status display.

### Risk 3: Neon connection exhaustion
At 8 concurrent Cloud Run instances (the chosen cap), each keeping a SQLAlchemy pool of `pool_size=2, max_overflow=3`, worst case = 8 × 5 = 40 connections. Neon free tier pooler supports ~20 via PgBouncer.
**Decided mitigation:** Cap Cloud Tasks max concurrent dispatches to **8** AND set `pool_size=1, max_overflow=1` in the batch engine → 8 × 2 = 16 connections → fits free tier.

### Risk 4: TASK_AUTH_SECRET rotation
If `TASK_AUTH_SECRET` is rotated while tasks are in-flight, in-flight tasks will fail auth and return 200 (by design, to avoid retry loops). Those items will be stuck as "pending". Manual re-enqueue needed. Document this in comments.

### Rejected Alternatives

| Alternative | Why Rejected |
|---|---|
| **Celery + Redis** | Adds Redis cost ($15–$30/month on Upstash free tier is insufficient for 1K items), more ops complexity, no benefit over Cloud Tasks given existing GCP infrastructure |
| **Cloud Run Jobs** | Designed for one-off batch jobs, not request-driven processing. Harder to integrate with existing FastAPI app. |
| **Increase asyncio concurrency to 40** | Single instance still hits memory ceiling (512MB → 1GB helps but 40 concurrent clones = OOM). Single point of failure remains. |
| **Pub/Sub instead of Cloud Tasks** | More complex (need to manage subscription, acknowledgement, pull vs push). Cloud Tasks push model maps directly to existing HTTP endpoint pattern. |
| **Vertical scale only (32GB Cloud Run)** | Very expensive ($0.36/GB-hour × 32GB × 24h = $276/day). Not realistic on $20 budget. |

---

## 8. Future Improvements (Not Implementing Now)

- **Dead letter queue:** Configure Cloud Tasks to send permanently-failed tasks to a DLQ for manual inspection.
- **Batch progress webhooks:** Instead of frontend polling, push progress notifications via WebSocket or SSE to the dashboard.
- **Priority queues:** High-priority batches (VIP customers) get a separate queue with higher concurrency.
- **Caching layer:** Redis cache for repo analysis results (skip DB round-trip for repeated lookups). Only worth it at >10K resumes/month.
- **Gemini batch API:** Instead of per-repo LLM calls, accumulate and send in a batch request for ~50% cost reduction.
