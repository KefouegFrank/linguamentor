import { Request, Response, NextFunction } from 'express';
import { prisma } from '../prisma/prisma';
import { queueService, QUEUE_NAMES } from '../services/queue.service';
import { AppError } from '../utils/errorHandler';
import { JobStatus, JobType, JobPriority } from '@prisma/client';
import { config } from '../config/config';

/**
 * Request types
 */
interface AuthenticatedRequest extends Request {
  user?: {
    id: string;
    email: string;
    role: string;
  };
}

interface CreateJobRequest extends AuthenticatedRequest {
  body: {
    type: JobType;
    priority?: JobPriority;
    fileId?: string;
    data: Record<string, any>;
    webhookUrl?: string;
    delay?: number;
  };
}

interface JobWebhookRequest extends Request {
  headers: {
    'x-service-token'?: string;
  };
  body: {
    jobId: string;
    status: 'completed' | 'failed';
    result?: any;
    error?: string;
    metadata?: Record<string, any>;
  };
}

/**
 * Create a new job
 */
export const createJob = async (
  req: CreateJobRequest,
  res: Response,
  next: NextFunction
) => {
  try {
    const { type, priority = JobPriority.MEDIUM, fileId, data, webhookUrl, delay } = req.body;
    const userId = req.user!.id;

    // Validate file exists if fileId is provided
    if (fileId) {
      const file = await prisma.file.findFirst({
        where: {
          id: fileId,
          uploadedById: userId,
        },
      });

      if (!file) {
        throw new AppError('File not found', 404);
      }

      if (file.status !== 'UPLOADED') {
        throw new AppError('File not ready for processing', 400);
      }
    }

    // Determine queue based on job type
    let queueName: string;
    switch (type) {
      case JobType.AI_PROCESSING:
        queueName = QUEUE_NAMES.AI_PROCESSING;
        break;
      case JobType.FILE_PROCESSING:
        queueName = QUEUE_NAMES.FILE_PROCESSING;
        break;
      case JobType.EMAIL_NOTIFICATION:
        queueName = QUEUE_NAMES.EMAIL_NOTIFICATIONS;
        break;
      default:
        throw new AppError('Invalid job type', 400);
    }

    // Prepare job data
    const jobData = {
      userId,
      fileId,
      ...data,
      webhookUrl,
    };

    // Add job to queue
    const jobId = await queueService.addJob(
      queueName,
      type,
      jobData,
      priority,
      delay
    );

    res.status(201).json({
      success: true,
      data: {
        jobId,
        message: 'Job created successfully',
      },
    });
  } catch (error) {
    next(error);
  }
};

/**
 * Get job status
 */
export const getJobStatus = async (
  req: AuthenticatedRequest,
  res: Response,
  next: NextFunction
) => {
  try {
    const { jobId } = req.params;
    const userId = req.user!.id;

    // Verify user owns this job
    const job = await prisma.job.findFirst({
      where: {
        id: jobId,
        data: {
          path: ['userId'],
          equals: userId,
        },
      },
    });

    if (!job) {
      throw new AppError('Job not found', 404);
    }

    const jobStatus = await queueService.getJobStatus(jobId);

    res.status(200).json({
      success: true,
      data: {
        job: jobStatus,
      },
    });
  } catch (error) {
    next(error);
  }
};

/**
 * List user jobs
 */
export const listJobs = async (
  req: AuthenticatedRequest,
  res: Response,
  next: NextFunction
) => {
  try {
    const userId = req.user!.id;
    const {
      page = 1,
      limit = 10,
      type,
      status,
      queueName,
      sortBy = 'createdAt',
      sortOrder = 'desc',
    } = req.query;

    const where: any = {
      data: {
        path: ['userId'],
        equals: userId,
      },
    };

    if (type) {
      where.type = type;
    }

    if (status) {
      where.status = status;
    }

    if (queueName) {
      where.queueName = queueName;
    }

    const skip = (Number(page) - 1) * Number(limit);

    const [jobs, total] = await Promise.all([
      prisma.job.findMany({
        where,
        skip,
        take: Number(limit),
        orderBy: { [sortBy as string]: sortOrder as 'asc' | 'desc' },
        include: {
          file: {
            select: {
              id: true,
              filename: true,
              originalName: true,
              contentType: true,
              size: true,
              type: true,
            },
          },
          outputFile: {
            select: {
              id: true,
              filename: true,
              originalName: true,
              contentType: true,
              size: true,
              type: true,
            },
          },
        },
      }),
      prisma.job.count({ where }),
    ]);

    res.status(200).json({
      success: true,
      data: {
        jobs: jobs.map(job => ({
          ...job,
          data: job.data ? JSON.parse(job.data) : null,
          result: job.result ? JSON.parse(job.result) : null,
        })),
        pagination: {
          page: Number(page),
          limit: Number(limit),
          total,
          pages: Math.ceil(total / Number(limit)),
        },
      },
    });
  } catch (error) {
    next(error);
  }
};

/**
 * Cancel job
 */
export const cancelJob = async (
  req: AuthenticatedRequest,
  res: Response,
  next: NextFunction
) => {
  try {
    const { jobId } = req.params;
    const userId = req.user!.id;

    // Verify user owns this job
    const job = await prisma.job.findFirst({
      where: {
        id: jobId,
        data: {
          path: ['userId'],
          equals: userId,
        },
      },
    });

    if (!job) {
      throw new AppError('Job not found', 404);
    }

    if (job.status === JobStatus.COMPLETED || job.status === JobStatus.FAILED) {
      throw new AppError('Cannot cancel completed or failed job', 400);
    }

    await queueService.cancelJob(jobId);

    res.status(200).json({
      success: true,
      message: 'Job cancelled successfully',
    });
  } catch (error) {
    next(error);
  }
};

/**
 * Retry job
 */
export const retryJob = async (
  req: AuthenticatedRequest,
  res: Response,
  next: NextFunction
) => {
  try {
    const { jobId } = req.params;
    const userId = req.user!.id;

    // Verify user owns this job
    const job = await prisma.job.findFirst({
      where: {
        id: jobId,
        data: {
          path: ['userId'],
          equals: userId,
        },
      },
    });

    if (!job) {
      throw new AppError('Job not found', 404);
    }

    if (job.status !== JobStatus.FAILED) {
      throw new AppError('Only failed jobs can be retried', 400);
    }

    // Reset job status and attempts
    await prisma.job.update({
      where: { id: jobId },
      data: {
        status: JobStatus.PENDING,
        attempts: 0,
        error: null,
        failedAt: null,
        startedAt: null,
        completedAt: null,
      },
    });

    // Re-add to queue
    const jobData = JSON.parse(job.data);
    const newJobId = await queueService.addJob(
      job.queueName,
      job.type,
      jobData,
      job.priority
    );

    res.status(200).json({
      success: true,
      data: {
        jobId: newJobId,
        message: 'Job retried successfully',
      },
    });
  } catch (error) {
    next(error);
  }
};

/**
 * Handle job webhook from AI service
 */
export const handleJobWebhook = async (
  req: JobWebhookRequest,
  res: Response,
  next: NextFunction
) => {
  try {
    const { jobId, status, result, error, metadata } = req.body;
    const serviceToken = req.headers['x-service-token'];

    // Validate service token
    if (serviceToken !== config.internalService.token) {
      throw new AppError('Invalid service token', 401);
    }

    const job = await prisma.job.findUnique({
      where: { id: jobId },
    });

    if (!job) {
      throw new AppError('Job not found', 404);
    }

    if (status === 'completed') {
      await queueService.completeJob(jobId, result);
    } else if (status === 'failed') {
      await queueService.failJob(jobId, error || 'Job failed');
    }

    // Store metadata if provided
    if (metadata) {
      await prisma.job.update({
        where: { id: jobId },
        data: {
          metadata: JSON.stringify(metadata),
        },
      });
    }

    res.status(200).json({
      success: true,
      message: 'Webhook processed successfully',
    });
  } catch (error) {
    next(error);
  }
};

/**
 * Get queue metrics
 */
export const getQueueMetrics = async (
  req: AuthenticatedRequest,
  res: Response,
  next: NextFunction
) => {
  try {
    const { queueName } = req.query;

    const metrics = await queueService.getQueueMetrics(queueName as string);

    res.status(200).json({
      success: true,
      data: {
        metrics,
      },
    });
  } catch (error) {
    next(error);
  }
};

/**
 * Clean old jobs
 */
export const cleanOldJobs = async (
  req: AuthenticatedRequest,
  res: Response,
  next: NextFunction
) => {
  try {
    const { queueName, olderThanHours = 24 } = req.body;

    if (!queueName) {
      throw new AppError('Queue name is required', 400);
    }

    const olderThanMs = olderThanHours * 60 * 60 * 1000;
    const result = await queueService.cleanOldJobs(queueName, olderThanMs);

    res.status(200).json({
      success: true,
      data: {
        cleaned: result,
      },
    });
  } catch (error) {
    next(error);
  }
};