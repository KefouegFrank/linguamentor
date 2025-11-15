from prometheus_client import Counter, Gauge, Histogram

# Metrics: Counters
jobs_processed_total = Counter(
    "jobs_processed_total", "Total processed jobs", ["status", "type"]
)
jobs_failures_total = Counter(
    "jobs_failures_total", "Total failed jobs", ["type"]
)

# Caching metrics
cache_hits_total = Counter(
    "cache_hits_total", "Total cache hits", ["type"]
)
cache_misses_total = Counter(
    "cache_misses_total", "Total cache misses", ["type"]
)

# Metrics: Gauges
queue_depth = Gauge("queue_depth", "Current queue depth")
worker_concurrency = Gauge("worker_concurrency", "Configured worker concurrency")

# Metrics: Histograms
job_duration_seconds = Histogram(
    "job_duration_seconds",
    "Job processing duration",
    buckets=(0.1, 0.5, 1, 2, 5, 10, 20, 60, 120, 300),
)

provider_call_duration_seconds = Histogram(
    "provider_call_duration_seconds",
    "External provider API call duration",
    buckets=(0.05, 0.1, 0.2, 0.5, 1, 2, 5, 10, 20),
)


def record_job_result(job_type: str, status: str, duration_seconds: float):
    jobs_processed_total.labels(status=status, type=job_type).inc()
    if status.lower() == "failed":
        jobs_failures_total.labels(type=job_type).inc()
    job_duration_seconds.observe(duration_seconds)


def record_cache_hit(job_type: str):
    cache_hits_total.labels(type=job_type).inc()


def record_cache_miss(job_type: str):
    cache_misses_total.labels(type=job_type).inc()
