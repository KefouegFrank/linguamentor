import { Queue, QueueEvents } from "bullmq";
import IORedis from "ioredis";
import { prisma } from "../prisma/client";
import { JobStatus, JobType } from "@prisma/client";
import { config } from "../config/config";

export interface QueueMetrics {
  queueName: string;
  waiting: number;
  active: number;
  completed: number;
  failed: number;
  delayed: number;
  paused: boolean;
}

export interface JobMetrics {
  totalJobs: number;
  completedJobs: number;
  failedJobs: number;
  averageProcessingTime: number;
  successRate: number;
  failureRate: number;
  jobsByType: Record<JobType, number>;
  jobsByStatus: Record<JobStatus, number>;
}

export interface SystemHealth {
  redis: {
    connected: boolean;
    status: string;
    memoryUsage?: number;
    uptime?: number;
  };
  database: {
    connected: boolean;
    queryTime: number;
  };
  queues: {
    healthy: boolean;
    totalQueues: number;
    healthyQueues: number;
  };
}

export class MonitoringService {
  private queues: Map<string, Queue> = new Map();
  private queueEvents: Map<string, QueueEvents> = new Map();
  private metricsInterval?: NodeJS.Timeout;
  private connection: IORedis;

  constructor() {
    this.connection = new IORedis(config.redis.url, {
      maxRetriesPerRequest: null,
      enableReadyCheck: false,
    });
    this.initializeMonitoring();
  }

  /**
   * Initialize monitoring for all queues
   */
  private async initializeMonitoring() {
    const queueNames = [
      "ai-processing",
      "file-processing",
      "email-notifications",
    ];

    for (const queueName of queueNames) {
      const queue = new Queue(queueName, { connection: this.connection });
      const queueEvents = new QueueEvents(queueName, {
        connection: this.connection,
      });

      this.queues.set(queueName, queue);
      this.queueEvents.set(queueName, queueEvents);

      // Set up event listeners for metrics
      this.setupQueueEventListeners(queueName, queueEvents);
    }
  }

  /**
   * Set up event listeners for queue events
   */
  private setupQueueEventListeners(
    queueName: string,
    queueEvents: QueueEvents
  ) {
    queueEvents.on("completed", async ({ jobId, returnvalue }) => {
      await this.logJobEvent(queueName, "completed", jobId);
    });

    queueEvents.on("failed", async ({ jobId, failedReason }) => {
      await this.logJobEvent(queueName, "failed", jobId, failedReason);
    });

    queueEvents.on("progress", async ({ jobId, data }) => {
      await this.updateJobProgress(jobId, data);
    });
  }

  /**
   * Get metrics for all queues
   */
  async getAllQueueMetrics(): Promise<QueueMetrics[]> {
    const metrics: QueueMetrics[] = [];

    for (const [queueName, queue] of this.queues) {
      try {
        const [waiting, active, completed, failed, delayed, paused] =
          await Promise.all([
            queue.getWaitingCount(),
            queue.getActiveCount(),
            queue.getCompletedCount(),
            queue.getFailedCount(),
            queue.getDelayedCount(),
            queue.isPaused(),
          ]);

        metrics.push({
          queueName,
          waiting,
          active,
          completed,
          failed,
          delayed,
          paused,
        });
      } catch (error) {
        console.error(`Error getting metrics for queue ${queueName}:`, error);
        metrics.push({
          queueName,
          waiting: 0,
          active: 0,
          completed: 0,
          failed: 0,
          delayed: 0,
          paused: false,
        });
      }
    }

    return metrics;
  }

  /**
   * Get job metrics from database
   */
  async getJobMetrics(
    timeRange: "1h" | "24h" | "7d" | "30d" = "24h"
  ): Promise<JobMetrics> {
    const timeFilter = this.getTimeFilter(timeRange);

    const [
      totalJobs,
      completedJobs,
      failedJobs,
      jobsByType,
      jobsByStatus,
      completedWithResults,
    ] = await Promise.all([
      prisma.job.count({ where: { createdAt: timeFilter } }),
      prisma.job.count({
        where: { createdAt: timeFilter, status: JobStatus.COMPLETED },
      }),
      prisma.job.count({
        where: { createdAt: timeFilter, status: JobStatus.FAILED },
      }),
      prisma.job.groupBy({
        by: ["jobType"],
        where: { createdAt: timeFilter },
        _count: { jobType: true },
      }),
      prisma.job.groupBy({
        by: ["status"],
        where: { createdAt: timeFilter },
        _count: { status: true },
      }),
      prisma.job.findMany({
        where: { createdAt: timeFilter, status: JobStatus.COMPLETED },
        select: { result: true },
      }),
    ]);

    const successRate = totalJobs > 0 ? (completedJobs / totalJobs) * 100 : 0;
    const failureRate = totalJobs > 0 ? (failedJobs / totalJobs) * 100 : 0;

    // Convert groupBy results to records
    const jobsByTypeRecord = jobsByType.reduce(
      (acc, item) => {
        acc[item.jobType] = item._count.jobType;
        return acc;
      },
      {} as Record<JobType, number>
    );

    const jobsByStatusRecord = jobsByStatus.reduce(
      (acc, item) => {
        acc[item.status] = item._count.status;
        return acc;
      },
      {} as Record<JobStatus, number>
    );

    const processingTimes = completedWithResults
      .map((j) => (j as any).result?.processingTime)
      .filter((t) => typeof t === "number") as number[];

    const averageProcessingTime =
      processingTimes.length > 0
        ? Math.round(
            processingTimes.reduce((a, b) => a + b, 0) / processingTimes.length
          )
        : 0;

    return {
      totalJobs,
      completedJobs,
      failedJobs,
      averageProcessingTime,
      successRate,
      failureRate,
      jobsByType: jobsByTypeRecord,
      jobsByStatus: jobsByStatusRecord,
    };
  }

  /**
   * Get system health status
   */
  async getSystemHealth(): Promise<SystemHealth> {
    const [redisHealth, dbHealth, queueHealth] = await Promise.all([
      this.checkRedisHealth(),
      this.checkDatabaseHealth(),
      this.checkQueueHealth(),
    ]);

    return {
      redis: redisHealth,
      database: dbHealth,
      queues: queueHealth,
    };
  }

  /**
   * Check Redis health
   */
  private async checkRedisHealth() {
    try {
      const startTime = Date.now();
      await this.connection.ping();
      const responseTime = Date.now() - startTime;

      return {
        connected: true,
        status: `Connected (${responseTime}ms)`,
        memoryUsage: await this.getRedisMemoryUsage(),
        uptime: await this.getRedisUptime(),
      };
    } catch (error) {
      return {
        connected: false,
        status: "Connection failed",
        memoryUsage: undefined,
        uptime: undefined,
      };
    }
  }

  /**
   * Check database health
   */
  private async checkDatabaseHealth() {
    try {
      const startTime = Date.now();
      await prisma.$queryRaw`SELECT 1`;
      const queryTime = Date.now() - startTime;

      return {
        connected: true,
        queryTime,
      };
    } catch (error) {
      return {
        connected: false,
        queryTime: -1,
      };
    }
  }

  /**
   * Check queue health
   */
  private async checkQueueHealth() {
    try {
      const metrics = await this.getAllQueueMetrics();
      const healthyQueues = metrics.filter(
        (metric) =>
          metric.failed < 10 && // Less than 10 failed jobs
          metric.waiting < 100 // Less than 100 waiting jobs
      ).length;

      return {
        healthy: healthyQueues === metrics.length,
        totalQueues: metrics.length,
        healthyQueues,
      };
    } catch (error) {
      return {
        healthy: false,
        totalQueues: 0,
        healthyQueues: 0,
      };
    }
  }

  /**
   * Get Redis memory usage
   */
  private async getRedisMemoryUsage(): Promise<number | undefined> {
    try {
      const info = await this.connection.info("memory");
      const usedMemoryMatch = info.match(/used_memory:(\d+)/);
      return usedMemoryMatch ? parseInt(usedMemoryMatch[1]) : undefined;
    } catch {
      return undefined;
    }
  }

  /**
   * Get Redis uptime
   */
  private async getRedisUptime(): Promise<number | undefined> {
    try {
      const info = await this.connection.info("server");
      const uptimeMatch = info.match(/uptime_in_seconds:(\d+)/);
      return uptimeMatch ? parseInt(uptimeMatch[1]) : undefined;
    } catch {
      return undefined;
    }
  }

  /**
   * Get time filter for database queries
   */
  public getTimeFilter(timeRange: string): { gte: Date } {
    const now = new Date();
    let hours = 24; // default 24h

    switch (timeRange) {
      case "1h":
        hours = 1;
        break;
      case "24h":
        hours = 24;
        break;
      case "7d":
        hours = 24 * 7;
        break;
      case "30d":
        hours = 24 * 30;
        break;
    }

    return {
      gte: new Date(now.getTime() - hours * 60 * 60 * 1000),
    };
  }

  /**
   * Log job events to database
   */
  private async logJobEvent(
    queueName: string,
    event: string,
    jobId: string,
    error?: string
  ) {
    try {
      await prisma.adminLog.create({
        data: {
          logLevel: event === "failed" ? "ERROR" : "INFO",
          message: `Job ${jobId} ${event} in queue ${queueName}`,
          category: "job_queue",
          metadata: {
            queueName,
            event,
            jobId,
            error,
          },
        },
      });
    } catch (error) {
      console.error("Failed to log job event:", error);
    }
  }

  /**
   * Update job progress in database
   */
  private async updateJobProgress(jobId: string, progress: any) {
    try {
      await prisma.job.update({
        where: { id: jobId },
        data: {
          progress:
            typeof progress === "number" ? progress : progress.progress || 0,
          progressMessage:
            typeof progress === "object" ? progress.message : undefined,
        },
      });
    } catch (error) {
      console.error("Failed to update job progress:", error);
    }
  }

  /**
   * Start collecting metrics periodically
   */
  startMetricsCollection(intervalMs: number = 60000) {
    // 1 minute default
    this.stopMetricsCollection();

    this.metricsInterval = setInterval(async () => {
      try {
        const metrics = await this.getAllQueueMetrics();
        const jobMetrics = await this.getJobMetrics("1h");

        // Store metrics in Redis for quick access
        await this.connection.setex(
          "queue:metrics",
          300,
          JSON.stringify(metrics)
        ); // 5 minute TTL
        await this.connection.setex(
          "job:metrics:1h",
          300,
          JSON.stringify(jobMetrics)
        ); // 5 minute TTL

        console.log(
          `[Monitoring] Collected metrics for ${metrics.length} queues`
        );
      } catch (error) {
        console.error("[Monitoring] Error collecting metrics:", error);
      }
    }, intervalMs);
  }

  /**
   * Stop collecting metrics
   */
  stopMetricsCollection() {
    if (this.metricsInterval) {
      clearInterval(this.metricsInterval);
      this.metricsInterval = undefined;
    }
  }

  /**
   * Get cached metrics from Redis
   */
  async getCachedMetrics(): Promise<{
    queues: QueueMetrics[];
    jobs: JobMetrics;
  } | null> {
    try {
      const [queueMetrics, jobMetrics] = await Promise.all([
        this.connection.get("queue:metrics"),
        this.connection.get("job:metrics:1h"),
      ]);

      if (queueMetrics && jobMetrics) {
        return {
          queues: JSON.parse(queueMetrics),
          jobs: JSON.parse(jobMetrics),
        };
      }

      return null;
    } catch {
      return null;
    }
  }

  /**
   * Clean up resources
   */
  async cleanup() {
    this.stopMetricsCollection();

    // Close all queue events
    for (const [_, queueEvents] of this.queueEvents) {
      await queueEvents.close();
    }

    // Close all queues
    for (const [_, queue] of this.queues) {
      await queue.close();
    }

    this.queues.clear();
    this.queueEvents.clear();
  }
}

// Export singleton instance
export const monitoringService = new MonitoringService();
