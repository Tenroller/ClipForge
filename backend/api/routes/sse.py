"""
Server-Sent Events (SSE) endpoint for real-time job progress streaming.

Provides an efficient alternative to REST polling for job status updates.
Falls back gracefully -- clients can still use REST polling if SSE is unavailable.
"""

import asyncio
import json
import time
from typing import Optional, Dict, Any

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse

from ...logging_config import get_logger
from ...database import get_job_store

router = APIRouter()
logger = get_logger("sse")

# Terminal statuses that signal the stream should close for a single-job subscription
TERMINAL_STATUSES = {"done", "error", "cancelled", "completed", "failed"}

# How often (seconds) to poll the database for changes
POLL_INTERVAL = 2

# How often (seconds) to send a heartbeat to keep the connection alive
HEARTBEAT_INTERVAL = 15


def _format_sse(event: str, data: str, event_id: Optional[str] = None) -> str:
    """Format a message in SSE wire format."""
    lines = []
    if event_id:
        lines.append(f"id: {event_id}")
    lines.append(f"event: {event}")
    # SSE data lines: each line of the JSON must be prefixed with "data: "
    for line in data.split("\n"):
        lines.append(f"data: {line}")
    lines.append("")  # blank line terminates the event
    lines.append("")
    return "\n".join(lines)


def _job_to_sse_payload(job: Dict[str, Any]) -> Dict[str, Any]:
    """Extract the fields the frontend cares about from a job dict."""
    # Map 'step' to 'current_step' for frontend compatibility (same as REST endpoint)
    payload = {
        "id": job.get("id"),
        "status": job.get("status"),
        "step": job.get("step"),
        "current_step": job.get("step"),
        "workflow": job.get("workflow"),
        "result": job.get("result"),
        "error": job.get("error"),
        "error_message": job.get("error"),
        "created_at": job.get("created_at"),
        "updated_at": job.get("updated_at"),
        "started_at": job.get("started_at"),
        "ended_at": job.get("ended_at"),
        "duration_seconds": job.get("duration_seconds"),
        "progress": job.get("progress"),
    }
    return payload


async def _stream_single_job(job_id: str):
    """Generator that streams SSE events for a single job until it reaches a terminal state."""
    job_store = get_job_store()
    last_updated_at: Optional[str] = None
    last_status: Optional[str] = None
    last_heartbeat = time.monotonic()
    event_counter = 0

    try:
        while True:
            job = job_store.get_job(job_id)

            if job is None:
                # Job was deleted or never existed -- send an error event and close
                event_counter += 1
                yield _format_sse(
                    "error",
                    json.dumps({"error": "job_not_found", "job_id": job_id}),
                    event_id=str(event_counter),
                )
                return

            current_updated = job.get("updated_at")
            current_status = job.get("status")

            # Only emit when something has changed (status or updated_at)
            if current_updated != last_updated_at or current_status != last_status:
                last_updated_at = current_updated
                last_status = current_status
                event_counter += 1

                payload = _job_to_sse_payload(job)
                yield _format_sse(
                    "job_update",
                    json.dumps(payload, default=str),
                    event_id=str(event_counter),
                )

                # If terminal, close the stream
                if current_status in TERMINAL_STATUSES:
                    return

            # Heartbeat to keep connection alive
            now = time.monotonic()
            if now - last_heartbeat >= HEARTBEAT_INTERVAL:
                last_heartbeat = now
                yield _format_sse("heartbeat", json.dumps({"ts": int(time.time())}))

            await asyncio.sleep(POLL_INTERVAL)

    except asyncio.CancelledError:
        # Client disconnected
        logger.debug(f"SSE stream cancelled for job {job_id}")
        return
    except Exception as exc:
        logger.error(f"SSE stream error for job {job_id}: {exc}")
        yield _format_sse("error", json.dumps({"error": str(exc)}))
        return


async def _stream_all_jobs():
    """Generator that streams SSE events for all jobs. Never auto-closes."""
    job_store = get_job_store()
    # Track last known updated_at per job to detect changes
    known_states: Dict[str, Optional[str]] = {}
    last_heartbeat = time.monotonic()
    event_counter = 0

    try:
        while True:
            jobs = job_store.list_jobs(limit=100)

            for job in jobs:
                job_id = job.get("id")
                if not job_id:
                    continue

                current_updated = job.get("updated_at")
                prev_updated = known_states.get(job_id)

                if current_updated != prev_updated:
                    known_states[job_id] = current_updated
                    event_counter += 1

                    payload = _job_to_sse_payload(job)
                    yield _format_sse(
                        "job_update",
                        json.dumps(payload, default=str),
                        event_id=str(event_counter),
                    )

            # Heartbeat
            now = time.monotonic()
            if now - last_heartbeat >= HEARTBEAT_INTERVAL:
                last_heartbeat = now
                yield _format_sse("heartbeat", json.dumps({"ts": int(time.time())}))

            await asyncio.sleep(POLL_INTERVAL)

    except asyncio.CancelledError:
        logger.debug("SSE all-jobs stream cancelled")
        return
    except Exception as exc:
        logger.error(f"SSE all-jobs stream error: {exc}")
        yield _format_sse("error", json.dumps({"error": str(exc)}))
        return


@router.get("/jobs/stream", summary="SSE stream for job progress updates")
async def stream_job_updates(
    job_id: Optional[str] = Query(None, description="Optional job ID to stream. If omitted, streams all job updates."),
):
    """Server-Sent Events endpoint for real-time job progress.

    - If `job_id` is provided, streams updates for that single job and auto-closes
      when the job reaches a terminal state (done/error/cancelled).
    - If `job_id` is omitted, streams updates for all jobs (never auto-closes).

    Events emitted:
    - `job_update`: JSON payload with job status fields.
    - `heartbeat`: Periodic keep-alive with a timestamp.
    - `error`: Sent when an unrecoverable error occurs.
    """
    if job_id:
        generator = _stream_single_job(job_id)
    else:
        generator = _stream_all_jobs()

    return StreamingResponse(
        generator,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )
