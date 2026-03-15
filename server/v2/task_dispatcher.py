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

    NOTE: If TASK_AUTH_SECRET is rotated while tasks are in-flight, those tasks
    will fail auth and return 200 (to avoid retry loops). Affected items will be
    stuck as "pending" and require manual re-enqueue.

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
