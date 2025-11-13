import client from 'prom-client';
import { Request, Response, NextFunction } from 'express';

// Create a Registry and collect default metrics
export const registry = new client.Registry();
client.collectDefaultMetrics({ register: registry });

// HTTP request metrics per route
export const httpRequestDurationMs = new client.Histogram({
  name: 'http_request_duration_ms',
  help: 'Duration of HTTP requests in ms',
  labelNames: ['method', 'route', 'status_code'],
  buckets: [50, 100, 200, 300, 500, 1000, 2000, 5000],
});
export const httpRequestErrorsTotal = new client.Counter({
  name: 'http_request_errors_total',
  help: 'Total number of HTTP errors per route',
  labelNames: ['method', 'route', 'status_code'],
});

// Queue metrics
export const queueLengthGauge = new client.Gauge({
  name: 'queue_length',
  help: 'Current number of jobs in the queue',
  labelNames: ['queue_name', 'state'],
});
export const jobOutcomeCounter = new client.Counter({
  name: 'jobs_outcome_total',
  help: 'Total jobs outcome by status',
  labelNames: ['status'],
});
export const jobProcessingTimeMs = new client.Histogram({
  name: 'job_processing_time_ms',
  help: 'Job processing time histogram',
  labelNames: ['job_type'],
  buckets: [100, 500, 1000, 2000, 5000, 10000, 60000],
});

// System gauges
export const uptimeGauge = new client.Gauge({
  name: 'service_uptime_seconds',
  help: 'Service uptime in seconds',
});
export const workerUptimeGauge = new client.Gauge({
  name: 'worker_uptime_seconds',
  help: 'Worker uptime in seconds',
  labelNames: ['worker_name'],
});

registry.registerMetric(httpRequestDurationMs);
registry.registerMetric(httpRequestErrorsTotal);
registry.registerMetric(queueLengthGauge);
registry.registerMetric(jobOutcomeCounter);
registry.registerMetric(jobProcessingTimeMs);
registry.registerMetric(uptimeGauge);
registry.registerMetric(workerUptimeGauge);

// Middleware to time requests and record errors
export function metricsMiddleware(req: Request, res: Response, next: NextFunction): void {
  const end = httpRequestDurationMs.startTimer({ method: req.method, route: req.route?.path || req.path });
  const originalSend = res.send.bind(res);
  res.send = function (body?: any): Response {
    // Record status code and error if applicable
    const status = res.statusCode;
    end({ status_code: String(status) });
    if (status >= 400) {
      httpRequestErrorsTotal.inc({ method: req.method, route: req.route?.path || req.path, status_code: String(status) });
    }
    return originalSend(body);
  } as any;
  next();
}

export async function metricsHandler(_req: Request, res: Response): Promise<void> {
  res.setHeader('Content-Type', registry.contentType);
  res.send(await registry.metrics());
}

