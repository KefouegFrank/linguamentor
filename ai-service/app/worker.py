import asyncio
import json
import time
from typing import Optional

import backoff
from redis.asyncio import from_url as redis_from_url

from app.config import settings
from app.logging import log
from app.metrics import record_job_result, queue_depth, worker_concurrency
from app.models import JobEnvelope
from app.handlers.base import handle_job
from app.backend_client import report_success, report_failure


class Worker:
    def __init__(self) -> None:
        self.redis = redis_from_url(settings.REDIS_URL)
        self._stop = asyncio.Event()
        self._sem = asyncio.Semaphore(settings.WORKER_CONCURRENCY)

    async def start(self) -> None:
        log.info("worker.start", queue=settings.REDIS_QUEUE_NAME)
        worker_concurrency.set(settings.WORKER_CONCURRENCY)
        await asyncio.gather(self._run_queue_loop(), self._run_metrics_loop())

    async def stop(self) -> None:
        log.info("worker.stop")
        self._stop.set()
        await self.redis.close()

    async def _run_metrics_loop(self) -> None:
        # Periodically update queue depth gauge
        while not self._stop.is_set():
            try:
                depth = await self.redis.llen(settings.REDIS_QUEUE_NAME)
                queue_depth.set(depth or 0)
            except Exception as e:
                log.error("metrics.queue_depth.error", error=str(e))
            await asyncio.sleep(5)

    async def _run_queue_loop(self) -> None:
        # Blocking pop loop to consume jobs from Redis list.
        while not self._stop.is_set():
            try:
                item = await self.redis.blpop(settings.REDIS_QUEUE_NAME, timeout=5)
                if not item:
                    continue
                _, raw = item
                await self._sem.acquire()
                asyncio.create_task(self._process_raw(raw))
            except Exception as e:
                log.error("worker.loop.error", error=str(e))
                await asyncio.sleep(1)

    async def _process_raw(self, raw: bytes) -> None:
        try:
            envelope = JobEnvelope.model_validate_json(raw)
        except Exception as e:
            log.error("job.decode.error", error=str(e))
            self._sem.release()
            return

        start = time.perf_counter()
        try:
            result = await self._handle_with_backoff(envelope)
            duration = time.perf_counter() - start
            record_job_result(envelope.type, "completed", duration)
            await report_success(envelope.jobId, result, {"duration": duration})
        except Exception as e:
            duration = time.perf_counter() - start
            record_job_result(envelope.type, "failed", duration)
            await report_failure(envelope.jobId, str(e), {"duration": duration})
        finally:
            self._sem.release()

    @backoff.on_exception(backoff.expo, Exception, max_tries=lambda: settings.MAX_RETRIES)
    async def _handle_with_backoff(self, envelope: JobEnvelope):
        return await handle_job(envelope)


worker = Worker()

