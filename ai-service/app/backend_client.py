import os
import time
import uuid
import hmac
import hashlib
import json
import httpx
import backoff
from typing import Any, Dict, Optional
from app.config import settings
from app.logging import log


def _make_headers(body: Dict[str, Any], ts: str, idem: str) -> Dict[str, str]:
    base = {
        "x-service-token": settings.INTERNAL_SERVICE_TOKEN or "",
        "x-timestamp": ts,
        "x-idempotency-key": idem,
    }
    # Compatibility header for different backend variants
    base["X-INTERNAL-TOKEN"] = settings.INTERNAL_SERVICE_TOKEN or ""

    # Optional HMAC signature when WEBHOOK_SECRET is set
    if settings.WEBHOOK_SECRET:
        payload_string = json.dumps({
            "jobId": body.get("jobId"),
            "status": body.get("status"),
            "result": body.get("result"),
            "error": body.get("error"),
            "metadata": body.get("metadata"),
            "timestamp": int(ts),
            "idempotencyKey": idem,
        })
        # Compute HMAC-SHA256 hex digest to match backend validation
        digest = hmac.new(
            settings.WEBHOOK_SECRET.encode("utf-8"),
            payload_string.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        base["x-signature"] = digest

    return base


@backoff.on_exception(backoff.expo, Exception, max_tries=lambda: settings.MAX_RETRIES)
async def _post(path: str, payload: Dict[str, Any]) -> None:
    url = settings.BACKEND_URL.rstrip("/") + path
    timeout = httpx.Timeout(settings.HTTP_TIMEOUT_SECONDS)
    ts = str(int(time.time() * 1000))
    idem = uuid.uuid4().hex
    headers = _make_headers(payload, ts, idem)
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(url, headers=headers, json=payload)
        resp.raise_for_status()


async def report_success(job_id: str, result: Dict[str, Any], metadata: Optional[Dict[str, Any]] = None) -> None:
    """Report successful completion to backend internal webhook."""
    log.info("callback.success", job_id=job_id)
    body = {
        "jobId": job_id,
        "status": "completed",
        "result": result,
        "metadata": metadata or {},
    }
    await _post("/api/jobs/webhook", body)


async def report_failure(job_id: str, error: str, metadata: Optional[Dict[str, Any]] = None) -> None:
    """Report failure to backend internal webhook."""
    log.error("callback.failure", job_id=job_id, error=error)
    body = {
        "jobId": job_id,
        "status": "failed",
        "error": error,
        "metadata": metadata or {},
    }
    await _post("/api/jobs/webhook", body)
