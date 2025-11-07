import { Request, Response, NextFunction } from 'express';
import { monitoringService } from '../services/monitoring.service';
import { AppError } from '../utils/AppError';
import { catchAsync } from '../utils/catchAsync';

/**
 * Get queue metrics
 */
export const getQueueMetrics = catchAsync(async (req: Request, res: Response) => {
  const metrics = await monitoringService.getAllQueueMetrics();
  
  res.json({
    success: true,
    data: {
      metrics,
      timestamp: new Date().toISOString(),
    },
  });
});

/**
 * Get job metrics
 */
export const getJobMetrics = catchAsync(async (req: Request, res: Response) => {
  const { timeRange = '24h' } = req.query;
  
  if (!['1h', '24h', '7d', '30d'].includes(timeRange as string)) {
    throw new AppError('Invalid time range. Must be one of: 1h, 24h, 7d, 30d', 400);
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
export const getSystemHealth = catchAsync(async (req: Request, res: Response) => {
  const health = await monitoringService.getSystemHealth();
  
  const overallHealthy = health.redis.connected && 
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
});

/**
 * Get cached metrics (faster, but might be slightly stale)
 */
export const getCachedMetrics = catchAsync(async (req: Request, res: Response) => {
  const cached = await monitoringService.getCachedMetrics();
  
  if (!cached) {
    // If no cached metrics, get fresh ones
    const [queues, jobs] = await Promise.all([
      monitoringService.getAllQueueMetrics(),
      monitoringService.getJobMetrics('1h'),
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
});

/**
 * Start metrics collection
 * Admin only endpoint
 */
export const startMetricsCollection = catchAsync(async (req: Request, res: Response) => {
  const { interval = 60000 } = req.body; // Default 1 minute
  
  if (typeof interval !== 'number' || interval < 10000) {
    throw new AppError('Interval must be a number and at least 10000ms (10 seconds)', 400);
  }
  
  monitoringService.startMetricsCollection(interval);
  
  res.json({
    success: true,
    message: `Metrics collection started with ${interval}ms interval`,
  });
});

/**
 * Stop metrics collection
 * Admin only endpoint
 */
export const stopMetricsCollection = catchAsync(async (req: Request, res: Response) => {
  monitoringService.stopMetricsCollection();
  
  res.json({
    success: true,
    message: 'Metrics collection stopped',
  });
});

/**
 * Get failed jobs with details
 */
export const getFailedJobs = catchAsync(async (req: Request, res: Response) => {
  const { limit = 50, offset = 0, queueName, jobType } = req.query;
  
  const where: any = {
    status: 'FAILED',
  };
  
  if (queueName) {
    where.queueName = queueName;
  }
  
  if (jobType) {
    where.jobType = jobType;
  }
  
  const [jobs, total] = await Promise.all([
    monitoringService['prisma'].job.findMany({
      where,
      orderBy: { failedAt: 'desc' },
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
    monitoringService['prisma'].job.count({ where }),
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
export const getJobProcessingStats = catchAsync(async (req: Request, res: Response) => {
  const { timeRange = '24h' } = req.query;
  
  if (!['1h', '24h', '7d', '30d'].includes(timeRange as string)) {
    throw new AppError('Invalid time range. Must be one of: 1h, 24h, 7d, 30d', 400);
  }
  
  const timeFilter = monitoringService['getTimeFilter'](timeRange as any);
  
  const [
    avgProcessingTimeByType,
    processingTimeDistribution,
    peakProcessingTimes,
    throughputByHour,
  ] = await Promise.all([
    // Average processing time by job type
    monitoringService['prisma'].job.groupBy({
      by: ['jobType'],
      where: {
        createdAt: timeFilter,
        processingTime: { not: null },
        status: 'COMPLETED',
      },
      _avg: {
        processingTime: true,
      },
      _count: {
        jobType: true,
      },
    }),
    
    // Processing time distribution
    monitoringService['prisma'].$queryRaw`
      SELECT 
        CASE 
          WHEN "processing_time" < 60000 THEN '0-1min'
          WHEN "processing_time" < 300000 THEN '1-5min'
          WHEN "processing_time" < 600000 THEN '5-10min'
          WHEN "processing_time" < 1800000 THEN '10-30min'
          ELSE '30min+'
        END as time_range,
        COUNT(*) as count
      FROM jobs
      WHERE "created_at" >= ${timeFilter.gte}
        AND "processing_time" IS NOT NULL
        AND "status" = 'COMPLETED'
      GROUP BY time_range
      ORDER BY time_range
    `,
    
    // Peak processing times (top 10 busiest hours)
    monitoringService['prisma'].$queryRaw`
      SELECT 
        DATE_TRUNC('hour', "created_at") as hour,
        COUNT(*) as job_count,
        AVG("processing_time") as avg_processing_time
      FROM jobs
      WHERE "created_at" >= ${timeFilter.gte}
      GROUP BY hour
      ORDER BY job_count DESC
      LIMIT 10
    `,
    
    // Throughput by hour for the last 24 hours
    monitoringService['prisma'].$queryRaw`
      SELECT 
        DATE_TRUNC('hour', "created_at") as hour,
        COUNT(*) as job_count,
        COUNT(CASE WHEN "status" = 'COMPLETED' THEN 1 END) as completed_count,
        COUNT(CASE WHEN "status" = 'FAILED' THEN 1 END) as failed_count
      FROM jobs
      WHERE "created_at" >= ${timeFilter.gte}
      GROUP BY hour
      ORDER BY hour DESC
      LIMIT 24
    `,
  ]);
  
  res.json({
    success: true,
    data: {
      avgProcessingTimeByType,
      processingTimeDistribution,
      peakProcessingTimes,
      throughputByHour,
      timeRange,
    },
  });
});

/**
 * Retry failed job
 */
export const retryFailedJob = catchAsync(async (req: Request, res: Response) => {
  const { jobId } = req.params;
  
  const job = await monitoringService['prisma'].job.findUnique({
    where: { id: jobId },
  });
  
  if (!job) {
    throw new AppError('Job not found', 404);
  }
  
  if (job.status !== 'FAILED') {
    throw new AppError('Only failed jobs can be retried', 400);
  }
  
  // Reset job status and clear error information
  const updatedJob = await monitoringService['prisma'].job.update({
    where: { id: jobId },
    data: {
      status: 'PENDING',
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
      message: 'Job has been queued for retry',
    },
  });
});

/**
 * Bulk retry failed jobs
 */
export const bulkRetryFailedJobs = catchAsync(async (req: Request, res: Response) => {
  const { jobIds, queueName, jobType } = req.body;
  
  let where: any = {
    status: 'FAILED',
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
  
  const result = await monitoringService['prisma'].job.updateMany({
    where,
    data: {
      status: 'PENDING',
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
});