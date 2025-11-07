import { Queue, Worker, Job as BullJob } from 'bullmq';
import IORedis from 'ioredis';
import { config } from '../config/config';
import { prisma } from '../prisma/prisma';
import { AppError } from '../utils/errorHandler';
import { JobStatus, JobType, JobPriority } from '@prisma/client';

// Redis connection
const connection = new IORedis(config.redis.url, {
  maxRetriesPerRequest: null,
  retryDelayOnFailure: 1000,
  enableReadyCheck: false,
});

// Queue names
export const QUEUE_NAMES = {
  AI_PROCESSING: 'ai-processing',
  FILE_PROCESSING: 'file-processing',
  EMAIL_NOTIFICATIONS: 'email-notifications',
} as const;

// Job data types
export interface AIProcessingJobData {
  fileId: string;
  userId: string;
  operation: 'transcribe' | 'translate' | 'summarize';
  targetLanguage?: string;
  webhookUrl?: string;
}

export interface FileProcessingJobData {
  fileId: string;
  operation: 'convert' | 'compress' | 'extract';
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

  constructor() {
    this.initializeQueues();
  }

  private initializeQueues() {
    // Initialize all queues
    Object.values(QUEUE_NAMES).forEach(queueName => {
      const queue = new Queue(queueName, {
        connection,
        defaultJobOptions: {
          removeOnComplete: { count: 1000 },
          removeOnFail: { count: 5000 },
          attempts: 3,
          backoff: {
            type: 'exponential',
            delay: 2000,
          },
        },
      });

      this.queues.set(queueName, queue);
    });
  }

  /**
   * Add a job to the queue
   */
  async addJob<T = any, R = any>(
    queueName: string,
    jobType: JobType,
    data: T,
    priority: JobPriority = JobPriority.MEDIUM,
    delay?: number
  ): Promise<string> {
    const queue = this.queues.get(queueName);
    if (!queue) {
      throw new AppError(`Queue ${queueName} not found`, 404);
    }

    // Create job record in database
    const jobRecord = await prisma.job.create({
      data: {
        type: jobType,
        status: JobStatus.PENDING,
        priority,
        data: JSON.stringify(data),
        queueName,
        attempts: 0,
        maxAttempts: 3,
      },
    });

    // Add job to queue
    const job = await queue.add(jobType, {
      jobId: jobRecord.id,
      data,
      attempts: 0,
    }, {
      priority: this.mapPriorityToNumber(priority),
      delay,
      jobId: jobRecord.id,
    });

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
      throw new AppError('Job not found', 404);
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
      type: job.type,
      status: job.status,
      priority: job.priority,
      data: job.data ? JSON.parse(job.data) : null,
      result: job.result ? JSON.parse(job.result) : null,
      error: job.error,
      attempts: job.attempts,
      maxAttempts: job.maxAttempts,
      startedAt: job.startedAt,
      completedAt: job.completedAt,
      failedAt: job.failedAt,
      createdAt: job.createdAt,
      updatedAt: job.updatedAt,
      file: job.file,
      outputFile: job.outputFile,
      queueJobStatus,
    };
  }

  /**
   * Update job progress
   */
  async updateJobProgress(jobId: string, progress: number, data?: any) {
    await prisma.job.update({
      where: { id: jobId },
      data: {
        progress,
        data: data ? JSON.stringify(data) : undefined,
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
    await prisma.job.update({
      where: { id: jobId },
      data: {
        status: JobStatus.COMPLETED,
        result: JSON.stringify(result),
        completedAt: new Date(),
        progress: 100,
      },
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
      throw new AppError('Job not found', 404);
    }

    if (job.status === JobStatus.COMPLETED || job.status === JobStatus.FAILED) {
      throw new AppError('Cannot cancel completed or failed job', 400);
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
        const [waiting, active, completed, failed, delayed] = await Promise.all([
          queue.getWaitingCount(),
          queue.getActiveCount(),
          queue.getCompletedCount(),
          queue.getFailedCount(),
          queue.getDelayedCount(),
        ]);

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
  async cleanOldJobs(queueName: string, olderThanMs: number = 24 * 60 * 60 * 1000) {
    const queue = this.queues.get(queueName);
    if (!queue) {
      throw new AppError(`Queue ${queueName} not found`, 404);
    }

    const cleaned = await queue.clean(olderThanMs, 1000, 'completed');
    const cleanedFailed = await queue.clean(olderThanMs, 1000, 'failed');

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
      case JobPriority.MEDIUM:
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
      connection,
      concurrency: 10,
      removeOnComplete: { count: 1000 },
      removeOnFail: { count: 5000 },
    });

    // Handle worker events
    worker.on('completed', async (job, result) => {
      console.log(`Job ${job.id} completed`);
      const jobData = job.data;
      if (jobData.jobId) {
        await this.completeJob(jobData.jobId, result);
      }
    });

    worker.on('failed', async (job, error) => {
      console.error(`Job ${job.id} failed:`, error);
      const jobData = job.data;
      if (jobData.jobId) {
        const maxAttemptsReached = await this.failJob(jobData.jobId, error.message);
        if (maxAttemptsReached) {
          console.log(`Job ${jobData.jobId} reached max attempts`);
        }
      }
    });

    worker.on('progress', async (job, progress) => {
      const jobData = job.data;
      if (jobData.jobId) {
        await this.updateJobProgress(jobData.jobId, progress);
      }
    });

    this.workers.set(queueName, worker);
    return worker;
  }

  /**
   * Close all connections
   */
  async close() {
    // Close all workers
    await Promise.all(Array.from(this.workers.values()).map(worker => worker.close()));
    
    // Close all queues
    await Promise.all(Array.from(this.queues.values()).map(queue => queue.close()));
    
    // Close Redis connection
    await connection.quit();
  }
}

// Export singleton instance
export const queueService = new QueueService();

// Export connection for use in other services
export { connection as redisConnection };