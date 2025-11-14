import os
import time
import uuid
import httpx
import backoff
from typing import Any, Dict, Optional
from app.config import settings
from app.logging import log


def _headers() -> Dict[str, str]:
    ts = str(int(time.time() * 1000))
    idem = uuid.uuid4().hex
    base = {
        "x-service-token": settings.INTERNAL_SERVICE_TOKEN or "",
        "x-timestamp": ts,
        "x-idempotency-key": idem,
    }
    # Compatibility header for different backend variants
    base["X-INTERNAL-TOKEN"] = settings.INTERNAL_SERVICE_TOKEN or ""
    return base


@backoff.on_exception(backoff.expo, Exception, max_tries=lambda: settings.MAX_RETRIES)
async def _post(path: str, payload: Dict[str, Any]) -> None:
    url = settings.BACKEND_URL.rstrip("/") + path
    timeout = httpx.Timeout(settings.HTTP_TIMEOUT_SECONDS)
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(url, headers=_headers(), json=payload)
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
    await _post("/jobs/webhook", body)


async def report_failure(job_id: str, error: str, metadata: Optional[Dict[str, Any]] = None) -> None:
    """Report failure to backend internal webhook."""
    log.error("callback.failure", job_id=job_id, error=error)
    body = {
        "jobId": job_id,
        "status": "failed",
        "error": error,
        "metadata": metadata or {},
    }
    await _post("/jobs/webhook", body)

