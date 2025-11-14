import { Queue, Worker, Job as BullJob, JobProgress } from "bullmq";
import IORedis from "ioredis";
import { prisma } from "../prisma/client";
import { AppError } from "../utils/errors";
import { JobStatus, JobType, JobPriority } from "@prisma/client";
import { config } from "../config/config";

// Queue names
export const QUEUE_NAMES = {
  AI_PROCESSING: "ai-processing",
  FILE_PROCESSING: "file-processing",
  EMAIL_NOTIFICATIONS: "email-notifications",
  SYSTEM_TASKS: "system-tasks",
} as const;

// Job data types
export interface AIProcessingJobData {
  fileId: string;
  userId: string;
  operation: "transcribe" | "translate" | "summarize";
  targetLanguage?: string;
  webhookUrl?: string;
}

export interface FileProcessingJobData {
  fileId: string;
  operation: "convert" | "compress" | "extract";
  parameters?: Record<string, any>;
}

export interface EmailNotificationJobData {
  to: string;
  subject: string;
  template: string;
  data: Record<string, any>;
}

// Job result types
export interface AIProcessingJobResult {
  result: any;
  processingTime: number;
  cost?: number;
}

export interface FileProcessingJobResult {
  outputFileId?: string;
  metadata: any;
}

export interface EmailNotificationJobResult {
  sent: boolean;
  messageId?: string;
}

// Queue service
export class QueueService {
  private queues: Map<string, Queue> = new Map();
  private workers: Map<string, Worker> = new Map();
  private connection: IORedis;

  constructor(redisUrl: string) {
    this.connection = new IORedis(redisUrl, {
      maxRetriesPerRequest: null,
      enableReadyCheck: false,
    });
    this.initializeQueues();
  }

  private initializeQueues() {
    // Initialize all queues
    Object.values(QUEUE_NAMES).forEach((queueName) => {
      const queue = new Queue(queueName, {
        connection: this.connection,
        defaultJobOptions: {
          removeOnComplete: 1000,
          removeOnFail: 5000,
          attempts: 3,
          backoff: {
            type: "exponential",
            delay: 2000,
          },
        },
      });

      this.queues.set(queueName, queue);
    });
  }

  /**
   * Schedule a recurring task in a queue (no DB job record).
   * Intended for internal system tasks like usage resets.
   */
  async scheduleRecurringTask(
    queueName: string,
    name: string,
    data: Record<string, any>,
    cronPattern: string
  ) {
    const queue = this.queues.get(queueName);
    if (!queue) {
      throw new AppError(`Queue ${queueName} not found`, 404);
    }
    await queue.add(name, data, {
      jobId: name, // ensure single repeatable job per name
      repeat: { pattern: cronPattern },
      removeOnComplete: true,
      removeOnFail: 100,
    });
  }

  /**
   * Add a job to the queue
   */
  async addJob<T = any, R = any>(
    queueName: string,
    jobType: JobType,
    data: T,
    priority: JobPriority = JobPriority.NORMAL,
    delay?: number
  ): Promise<string> {
    const queue = this.queues.get(queueName);
    if (!queue) {
      throw new AppError(`Queue ${queueName} not found`, 404);
    }

    // Create job record in database
    const jobRecord = await prisma.job.create({
      data: {
        jobType,
        status: JobStatus.PENDING,
        priority,
        payload: data as any,
        queueName,
        attempts: 0,
        maxAttempts: 3,
        user: { connect: { id: (data as any).userId } },
        file: (data as any).fileId
          ? { connect: { id: (data as any).fileId as string } }
          : undefined,
      },
    });

    // Add job to queue
    const job = await queue.add(
      jobType,
      {
        jobId: jobRecord.id,
        data,
        attempts: 0,
      },
      {
        priority: this.mapPriorityToNumber(priority),
        delay,
        jobId: jobRecord.id,
      }
    );

    // Update job with queue job ID
    await prisma.job.update({
      where: { id: jobRecord.id },
      data: { queueJobId: job.id },
    });

    return jobRecord.id;
  }

  /**
   * Get job status
   */
  async getJobStatus(jobId: string) {
    const job = await prisma.job.findUnique({
      where: { id: jobId },
      include: {
        file: true,
        outputFile: true,
      },
    });

    if (!job) {
      throw new AppError("Job not found", 404);
    }

    // Get queue job status if it exists
    let queueJobStatus = null;
    if (job.queueJobId && job.queueName) {
      const queue = this.queues.get(job.queueName);
      if (queue) {
        try {
          const queueJob = await queue.getJob(job.queueJobId);
          if (queueJob) {
            queueJobStatus = {
              state: await queueJob.getState(),
              progress: queueJob.progress,
              returnvalue: queueJob.returnvalue,
              failedReason: queueJob.failedReason,
              attempts: queueJob.attemptsMade,
            };
          }
        } catch (error) {
          // Queue job might be removed due to retention policy
        }
      }
    }

    return {
      id: job.id,
      type: job.jobType,
      status: job.status,
      priority: job.priority,
      data: job.payload,
      result: job.result,
      error: job.error ?? job.errorMessage,
      attempts: job.attempts,
      maxAttempts: job.maxAttempts,
      startedAt: job.startedAt,
      completedAt: job.completedAt,
      failedAt: job.failedAt,
      cancelledAt: job.cancelledAt,
      createdAt: job.createdAt,
      updatedAt: job.updatedAt,
      file: job.file,
      outputFile: job.outputFile,
      queueJobStatus,
    };
  }

  /**
   * Publish an AI job envelope to the AI service Redis list
   */
  async publishAIEnvelope(envelope: Record<string, any>): Promise<void> {
    const listName = config.internalService.aiQueueName;
    await this.connection.rpush(listName, JSON.stringify(envelope));
  }

  /**
   * Update job progress
   */
  async updateJobProgress(jobId: string, progress: number, data?: any) {
    await prisma.job.update({
      where: { id: jobId },
      data: {
        progress,
      },
    });

    // Update queue job progress if it exists
    const job = await prisma.job.findUnique({
      where: { id: jobId },
      select: { queueJobId: true, queueName: true },
    });

    if (job?.queueJobId && job?.queueName) {
      const queue = this.queues.get(job.queueName);
      if (queue) {
        try {
          const queueJob = await queue.getJob(job.queueJobId);
          if (queueJob) {
            await queueJob.updateProgress(progress);
          }
        } catch (error) {
          // Queue job might be removed
        }
      }
    }
  }

  /**
   * Complete job
   */
  async completeJob(jobId: string, result: any) {
    const updateData: any = {
      status: JobStatus.COMPLETED,
      result: result as any,
      completedAt: new Date(),
      progress: 100,
    };
    if (result && typeof result === "object" && (result as any).outputFileId) {
      updateData.outputFileId = (result as any).outputFileId as string;
    }
    await prisma.job.update({
      where: { id: jobId },
      data: updateData,
    });
  }

  /**
   * Fail job
   */
  async failJob(jobId: string, error: string) {
    const job = await prisma.job.update({
      where: { id: jobId },
      data: {
        status: JobStatus.FAILED,
        error,
        failedAt: new Date(),
        attempts: { increment: 1 },
      },
    });

    return job.attempts >= job.maxAttempts;
  }

  /**
   * Cancel job
   */
  async cancelJob(jobId: string) {
    const job = await prisma.job.findUnique({
      where: { id: jobId },
      select: { queueJobId: true, queueName: true, status: true },
    });

    if (!job) {
      throw new AppError("Job not found", 404);
    }

    if (job.status === JobStatus.COMPLETED || job.status === JobStatus.FAILED) {
      throw new AppError("Cannot cancel completed or failed job", 400);
    }

    // Remove from queue if it's pending
    if (job.queueJobId && job.queueName) {
      const queue = this.queues.get(job.queueName);
      if (queue) {
        try {
          const queueJob = await queue.getJob(job.queueJobId);
          if (queueJob) {
            await queueJob.remove();
          }
        } catch (error) {
          // Queue job might be removed
        }
      }
    }

    // Update database
    await prisma.job.update({
      where: { id: jobId },
      data: {
        status: JobStatus.CANCELLED,
        cancelledAt: new Date(),
      },
    });
  }

  /**
   * Get queue metrics
   */
  async getQueueMetrics(queueName?: string) {
    if (queueName) {
      const queue = this.queues.get(queueName);
      if (!queue) {
        throw new AppError(`Queue ${queueName} not found`, 404);
      }

      const [waiting, active, completed, failed, delayed] = await Promise.all([
        queue.getWaitingCount(),
        queue.getActiveCount(),
        queue.getCompletedCount(),
        queue.getFailedCount(),
        queue.getDelayedCount(),
      ]);

      return {
        queueName,
        waiting,
        active,
        completed,
        failed,
        delayed,
      };
    }

    // Get metrics for all queues
    const metrics = await Promise.all(
      Object.values(QUEUE_NAMES).map(async (name) => {
        const queue = this.queues.get(name)!;
        const [waiting, active, completed, failed, delayed] = await Promise.all(
          [
            queue.getWaitingCount(),
            queue.getActiveCount(),
            queue.getCompletedCount(),
            queue.getFailedCount(),
            queue.getDelayedCount(),
          ]
        );

        return {
          queueName: name,
          waiting,
          active,
          completed,
          failed,
          delayed,
        };
      })
    );

    return metrics;
  }

  /**
   * Clean old jobs
   */
  async cleanOldJobs(
    queueName: string,
    olderThanMs: number = 24 * 60 * 60 * 1000
  ) {
    const queue = this.queues.get(queueName);
    if (!queue) {
      throw new AppError(`Queue ${queueName} not found`, 404);
    }

    const cleaned = await queue.clean(olderThanMs, 1000, "completed");
    const cleanedFailed = await queue.clean(olderThanMs, 1000, "failed");

    return {
      completed: cleaned.length,
      failed: cleanedFailed.length,
      total: cleaned.length + cleanedFailed.length,
    };
  }

  /**
   * Map priority enum to number
   */
  private mapPriorityToNumber(priority: JobPriority): number {
    switch (priority) {
      case JobPriority.LOW:
        return 10;
      case JobPriority.NORMAL:
        return 5;
      case JobPriority.HIGH:
        return 1;
      case JobPriority.URGENT:
        return 0;
      default:
        return 5;
    }
  }

  /**
   * Create a worker for a queue
   */
  createWorker(queueName: string, processor: (job: BullJob) => Promise<any>) {
    const worker = new Worker(queueName, processor, {
      connection: this.connection,
      concurrency: 10,
    });

    // Handle worker events
    worker.on("completed", (job, result, _prev) => {
      void (async () => {
        const jobData = job?.data;
        // For AI queue, completion is reported via webhook; skip auto-complete
        if (queueName === QUEUE_NAMES.AI_PROCESSING) {
          console.log(`Job ${job?.id} delegated to ai-service; awaiting webhook.`);
          return;
        }
        console.log(`Job ${job?.id} completed`);
        if (jobData?.jobId) {
          await this.completeJob(jobData.jobId, result);
        }
      })();
    });

    worker.on("failed", (job, error, _prev) => {
      void (async () => {
        console.error(`Job ${job?.id} failed:`, error);
        const jobData = job?.data;
        if (jobData?.jobId) {
          const maxAttemptsReached = await this.failJob(
            jobData.jobId,
            error.message
          );
          if (maxAttemptsReached) {
            console.log(`Job ${jobData.jobId} reached max attempts`);
          }
        }
      })();
    });

    // Mark job as processing when picked up by worker
    worker.on("active", (job: BullJob) => {
      void (async () => {
        const jobData = job?.data;
        if (jobData?.jobId) {
          await prisma.job.update({
            where: { id: jobData.jobId },
            data: { status: JobStatus.PROCESSING, startedAt: new Date() },
          });
        }
      })();
    });

    worker.on("progress", (job: BullJob, progress: JobProgress) => {
      void (async () => {
        const jobData = job.data;
        if (jobData?.jobId) {
          const value = typeof progress === "number" ? progress : 0;
          await this.updateJobProgress(jobData.jobId, value);
        }
      })();
    });

    this.workers.set(queueName, worker);
    return worker;
  }

  /**
   * Close all connections
   */
  async close() {
    // Close all workers
    await Promise.all(
      Array.from(this.workers.values()).map((worker) => worker.close())
    );

    // Close all queues
    await Promise.all(
      Array.from(this.queues.values()).map((queue) => queue.close())
    );

    // Close Redis connection
    await this.connection.quit();
  }

  // Singleton instance management and static proxies for controllers/workers
  private static _instance: QueueService | null = null;

  static init(redisUrl: string): QueueService {
    const instance = new QueueService(redisUrl);
    QueueService._instance = instance;
    return instance;
  }

  private static get instance(): QueueService {
    if (!QueueService._instance) {
      throw new AppError("QueueService not initialized", 500);
    }
    return QueueService._instance;
  }

  // Static proxy methods
  static addJob<T = any, R = any>(
    queueName: string,
    jobType: JobType,
    data: T,
    priority: JobPriority = JobPriority.NORMAL,
    delay?: number
  ): Promise<string> {
    return QueueService.instance.addJob<T, R>(queueName, jobType, data, priority, delay);
  }

  static getJobStatus(jobId: string) {
    return QueueService.instance.getJobStatus(jobId);
  }

  static updateJobProgress(jobId: string, progress: number, data?: any) {
    return QueueService.instance.updateJobProgress(jobId, progress, data);
  }

  static completeJob(jobId: string, result: any) {
    return QueueService.instance.completeJob(jobId, result);
  }

  static failJob(jobId: string, error: string) {
    return QueueService.instance.failJob(jobId, error);
  }

  static cancelJob(jobId: string) {
    return QueueService.instance.cancelJob(jobId);
  }

  static getQueueMetrics(queueName?: string) {
    return QueueService.instance.getQueueMetrics(queueName);
  }

  static cleanOldJobs(queueName: string, olderThanMs: number = 24 * 60 * 60 * 1000) {
    return QueueService.instance.cleanOldJobs(queueName, olderThanMs);
  }

  static createWorker(queueName: string, processor: (job: BullJob) => Promise<any>) {
    return QueueService.instance.createWorker(queueName, processor);
  }

  static publishAIEnvelope(envelope: Record<string, any>) {
    return QueueService.instance.publishAIEnvelope(envelope);
  }

  static close() {
    return QueueService.instance.close();
  }

  static scheduleRecurringTask(
    queueName: string,
    name: string,
    data: Record<string, any>,
    cronPattern: string
  ) {
    return QueueService.instance.scheduleRecurringTask(queueName, name, data, cronPattern);
  }
}

// Export a function to create and set the singleton service
export const createQueueService = (redisUrl: string) => {
  return QueueService.init(redisUrl);
};
