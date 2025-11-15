import httpx
from typing import Tuple
from app.config import settings
from app.logging import log


async def download_presigned(url: str) -> bytes:
    """Download object from S3 via presigned GET URL."""
    timeout = httpx.Timeout(settings.HTTP_TIMEOUT_SECONDS)
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        return resp.content


async def upload_presigned(url: str, data: bytes, content_type: str = "application/octet-stream") -> Tuple[str, int]:
    """Upload object to S3 via presigned PUT URL. Returns (url, status_code)."""
    timeout = httpx.Timeout(settings.HTTP_TIMEOUT_SECONDS)
    headers = {"Content-Type": content_type}
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.put(url, headers=headers, content=data)
        resp.raise_for_status()
        return url, resp.status_code

