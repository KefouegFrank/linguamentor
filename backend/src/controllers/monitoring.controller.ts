import { Request, Response, NextFunction } from "express";
import { z } from "zod";
import { monitoringService } from "../services/monitoring.service";
import { prisma } from "../prisma/client";
import { AppError } from "../utils/errors";
import { catchAsync } from "../utils/catchAsync";

/**
 * Get queue metrics
 */
export const getQueueMetrics = catchAsync(
  async (req: Request, res: Response) => {
    const metrics = await monitoringService.getAllQueueMetrics();

    res.json({
      success: true,
      data: {
        metrics,
        timestamp: new Date().toISOString(),
      },
    });
  }
);

/**
 * Get job metrics
 */
export const getJobMetrics = catchAsync(async (req: Request, res: Response) => {
  const { timeRange = "24h" } = req.query;

  if (!["1h", "24h", "7d", "30d"].includes(timeRange as string)) {
    throw new AppError(
      "Invalid time range. Must be one of: 1h, 24h, 7d, 30d",
      400
    );
  }

  const metrics = await monitoringService.getJobMetrics(timeRange as any);

  res.json({
    success: true,
    data: {
      metrics,
      timeRange,
      timestamp: new Date().toISOString(),
    },
  });
});

/**
 * Get system health
 */
export const getSystemHealth = catchAsync(
  async (req: Request, res: Response) => {
    const health = await monitoringService.getSystemHealth();

    const overallHealthy =
      health.redis.connected &&
      health.database.connected &&
      health.queues.healthy;

    res.json({
      success: true,
      data: {
        health,
        overallHealthy,
        timestamp: new Date().toISOString(),
      },
    });
  }
);

/**
 * Get cached metrics (faster, but might be slightly stale)
 */
export const getCachedMetrics = catchAsync(
  async (req: Request, res: Response) => {
    const cached = await monitoringService.getCachedMetrics();

    if (!cached) {
      // If no cached metrics, get fresh ones
      const [queues, jobs] = await Promise.all([
        monitoringService.getAllQueueMetrics(),
        monitoringService.getJobMetrics("1h"),
      ]);

      return res.json({
        success: true,
        data: {
          queues,
          jobs,
          cached: false,
          timestamp: new Date().toISOString(),
        },
      });
    }

    res.json({
      success: true,
      data: {
        ...cached,
        cached: true,
        timestamp: new Date().toISOString(),
      },
    });
  }
);

/**
 * Start metrics collection
 * Admin only endpoint
 */
export const startMetricsCollection = catchAsync(
  async (req: Request, res: Response) => {
    const { interval = 60000 } = req.body; // Default 1 minute

    if (typeof interval !== "number" || interval < 10000) {
      throw new AppError(
        "Interval must be a number and at least 10000ms (10 seconds)",
        400
      );
    }

    monitoringService.startMetricsCollection(interval);

    res.json({
      success: true,
      message: `Metrics collection started with ${interval}ms interval`,
    });
  }
);

/**
 * Stop metrics collection
 * Admin only endpoint
 */
export const stopMetricsCollection = catchAsync(
  async (req: Request, res: Response) => {
    monitoringService.stopMetricsCollection();

    res.json({
      success: true,
      message: "Metrics collection stopped",
    });
  }
);

/**
 * Get failed jobs with details
 */
export const getFailedJobs = catchAsync(async (req: Request, res: Response) => {
  const { limit = 50, offset = 0, queueName, jobType } = req.query;

  const where: any = {
    status: "FAILED",
  };

  if (queueName) {
    where.queueName = queueName;
  }

  if (jobType) {
    where.jobType = jobType;
  }

  const [jobs, total] = await Promise.all([
    prisma.job.findMany({
      where,
      orderBy: { failedAt: "desc" },
      take: parseInt(limit as string),
      skip: parseInt(offset as string),
      include: {
        user: {
          select: {
            id: true,
            email: true,
            firstName: true,
            lastName: true,
          },
        },
        file: {
          select: {
            id: true,
            originalName: true,
            fileType: true,
          },
        },
      },
    }),
    prisma.job.count({ where }),
  ]);

  res.json({
    success: true,
    data: {
      jobs,
      pagination: {
        total,
        limit: parseInt(limit as string),
        offset: parseInt(offset as string),
        hasMore: parseInt(offset as string) + parseInt(limit as string) < total,
      },
    },
  });
});

/**
 * Get job processing statistics
 */
export const getJobProcessingStats = catchAsync(
  async (req: Request, res: Response) => {
    const schema = z.object({
      timeRange: z.enum(["1h", "24h", "7d", "30d"]).default("24h"),
      topN: z.coerce.number().int().min(1).max(100).default(10),
    });
    const { timeRange, topN } = schema.parse({
      timeRange: req.query.timeRange,
      topN: req.query.topN,
    });

    const timeFilter = monitoringService.getTimeFilter(timeRange as any);

    const completedJobs = await prisma.job.findMany({
      where: { createdAt: timeFilter, status: "COMPLETED" },
      select: { jobType: true, createdAt: true, completedAt: true, result: true },
      orderBy: { createdAt: "asc" },
    });

    const typeBuckets: Record<string, { sum: number; count: number }> = {};
    const processingTimes: number[] = [];
    const processingTimeDistribution: Record<string, number> = {
      "0-1min": 0,
      "1-5min": 0,
      "5-10min": 0,
      "10-30min": 0,
      "30min+": 0,
    };
    const throughputByHour: Record<string, number> = {};

    for (const j of completedJobs) {
      const pt: number | undefined = (j as any).result?.processingTime;
      if (typeof pt === "number") {
        const key = j.jobType;
        if (!typeBuckets[key]) typeBuckets[key] = { sum: 0, count: 0 };
        typeBuckets[key].sum += pt;
        typeBuckets[key].count += 1;

        processingTimes.push(pt);

        if (pt < 60000) processingTimeDistribution["0-1min"]++;
        else if (pt < 300000) processingTimeDistribution["1-5min"]++;
        else if (pt < 600000) processingTimeDistribution["5-10min"]++;
        else if (pt < 1800000) processingTimeDistribution["10-30min"]++;
        else processingTimeDistribution["30min+"]++;
      }

      const hourKey = (j.completedAt || j.createdAt).toISOString().slice(0, 13);
      throughputByHour[hourKey] = (throughputByHour[hourKey] || 0) + 1;
    }

    const avgProcessingTimeByType = Object.entries(typeBuckets).map(
      ([jobType, { sum, count }]) => ({ jobType, avgProcessingTime: Math.round(sum / count), count })
    );

    // Percentiles
    const sorted = processingTimes.sort((a, b) => a - b);
    const percentile = (p: number) => {
      if (sorted.length === 0) return null;
      const idx = Math.min(sorted.length - 1, Math.floor((p / 100) * sorted.length));
      return sorted[idx];
    };
    const p50 = percentile(50);
    const p90 = percentile(90);
    const p99 = percentile(99);
    const averageAll =
      sorted.length > 0
        ? Math.round(sorted.reduce((acc, v) => acc + v, 0) / sorted.length)
        : null;

    const peakProcessingTimes = completedJobs
      .map((j) => ({ jobType: j.jobType, processingTime: (j as any).result?.processingTime }))
      .filter((x) => typeof x.processingTime === "number")
      .sort((a, b) => (b.processingTime as number) - (a.processingTime as number))
      .slice(0, topN);

    res.json({
      success: true,
      data: {
        avgProcessingTimeByType,
        processingTimeDistribution,
        peakProcessingTimes,
        throughputByHour,
        percentiles: { p50, p90, p99, average: averageAll },
        timeRange,
        topN,
      },
    });
  }
);

/**
 * Retry failed job
 */
export const retryFailedJob = catchAsync(
  async (req: Request, res: Response) => {
    const { jobId } = req.params;

    const job = await prisma.job.findUnique({
      where: { id: jobId },
    });

    if (!job) {
      throw new AppError("Job not found", 404);
    }

    if (job.status !== "FAILED") {
      throw new AppError("Only failed jobs can be retried", 400);
    }

    // Reset job status and clear error information
    const updatedJob = await prisma.job.update({
      where: { id: jobId },
      data: {
        status: "PENDING",
        attempts: 0,
        errorMessage: null,
        errorStack: null,
        failedAt: null,
        startedAt: null,
        completedAt: null,
        progress: 0,
        progressMessage: null,
      },
    });

    res.json({
      success: true,
      data: {
        job: updatedJob,
        message: "Job has been queued for retry",
      },
    });
  }
);

/**
 * Bulk retry failed jobs
 */
export const bulkRetryFailedJobs = catchAsync(
  async (req: Request, res: Response) => {
    const { jobIds, queueName, jobType } = req.body;

    let where: any = {
      status: "FAILED",
    };

    if (jobIds && Array.isArray(jobIds) && jobIds.length > 0) {
      where.id = { in: jobIds };
    }

    if (queueName) {
      where.queueName = queueName;
    }

    if (jobType) {
      where.jobType = jobType;
    }

    const result = await prisma.job.updateMany({
      where,
      data: {
        status: "PENDING",
        attempts: 0,
        errorMessage: null,
        errorStack: null,
        failedAt: null,
        startedAt: null,
        completedAt: null,
        progress: 0,
        progressMessage: null,
      },
    });

    res.json({
      success: true,
      data: {
        count: result.count,
        message: `${result.count} jobs have been queued for retry`,
      },
    });
  }
);
