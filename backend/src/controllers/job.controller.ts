import { Request, Response, NextFunction } from "express";
import { prisma } from "../prisma/client";
import { QueueService, QUEUE_NAMES } from "../services/queue.service";
import { AppError } from "../utils/errors";
import { JobStatus, JobType, JobPriority, FileStatus } from "@prisma/client";
import { config } from "../config/config";
import { AccessTokenPayload } from "../types/auth.types";

/**
 * Request types
 */
interface AuthenticatedRequest extends Request {
  user?: AccessTokenPayload;
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
    "x-service-token"?: string;
  };
  body: {
    jobId: string;
    status: "completed" | "failed";
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
    const {
      type,
      priority = JobPriority.NORMAL,
      fileId,
      data,
      webhookUrl,
      delay,
    } = req.body;
    const userId = req.user!.userId;

    // Validate file exists if fileId is provided
    if (fileId) {
      const file = await prisma.file.findFirst({
        where: {
          id: fileId,
          userId,
        },
      });

      if (!file) {
        throw new AppError("File not found", 404);
      }

      if (file.status !== FileStatus.UPLOADED) {
        throw new AppError("File not ready for processing", 400);
      }
    }

    // Determine queue based on job type
    let queueName: string;
    switch (type) {
      case JobType.AI_PROCESSING:
        queueName = QUEUE_NAMES.AI_PROCESSING;
        break;
      case JobType.FILE_CONVERSION:
        queueName = QUEUE_NAMES.FILE_PROCESSING;
        break;
      default:
        throw new AppError("Invalid job type", 400);
    }

    // Prepare job data
    const jobData = {
      userId,
      fileId,
      ...data,
      webhookUrl,
    };

    // Add job to queue
    const jobId = await QueueService.addJob(
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
        message: "Job created successfully",
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
    const userId = req.user!.userId;

    // Verify user owns this job
    const job = await prisma.job.findFirst({
      where: {
        id: jobId,
        payload: {
          path: ["userId"],
          equals: userId,
        },
      },
    });

    if (!job) {
      throw new AppError("Job not found", 404);
    }

    const jobStatus = await QueueService.getJobStatus(jobId);

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
    const userId = req.user!.userId;
    const {
      page = 1,
      limit = 10,
      type,
      status,
      queueName,
      sortBy = "createdAt",
      sortOrder = "desc",
    } = req.query;

    const where: any = {
      payload: {
        path: ["userId"],
        equals: userId,
      },
    };

    if (type) {
      where.jobType = type;
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
        orderBy: { [sortBy as string]: sortOrder as "asc" | "desc" },
        include: {
          file: {
            select: {
              id: true,
              fileName: true,
              originalName: true,
              mimeType: true,
              size: true,
              fileType: true,
            },
          },
          outputFile: {
            select: {
              id: true,
              fileName: true,
              originalName: true,
              mimeType: true,
              size: true,
              fileType: true,
            },
          },
        },
      }),
      prisma.job.count({ where }),
    ]);

    res.status(200).json({
      success: true,
      data: {
        jobs: jobs.map((job) => ({
          ...job,
          data: (job as any).payload ?? null,
          result: (job as any).result ?? null,
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
    const userId = req.user!.userId;

    // Verify user owns this job
    const job = await prisma.job.findFirst({
      where: {
        id: jobId,
        payload: {
          path: ["userId"],
          equals: userId,
        },
      },
    });

    if (!job) {
      throw new AppError("Job not found", 404);
    }

    if (job.status === JobStatus.COMPLETED || job.status === JobStatus.FAILED) {
      throw new AppError("Cannot cancel completed or failed job", 400);
    }

    await QueueService.cancelJob(jobId);

    res.status(200).json({
      success: true,
      message: "Job cancelled successfully",
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
    const userId = req.user!.userId;

    // Verify user owns this job
    const job = await prisma.job.findFirst({
      where: {
        id: jobId,
        payload: {
          path: ["userId"],
          equals: userId,
        },
      },
    });

    if (!job) {
      throw new AppError("Job not found", 404);
    }

    if (job.status !== JobStatus.FAILED) {
      throw new AppError("Only failed jobs can be retried", 400);
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
    const jobData = (job as any).payload;
    const newJobId = await QueueService.addJob(
      job.queueName,
      job.jobType,
      jobData,
      job.priority
    );

    res.status(200).json({
      success: true,
      data: {
        jobId: newJobId,
        message: "Job retried successfully",
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
    const serviceToken = req.headers["x-service-token"];
    const signature = (req.headers as any)["x-signature"] as string | undefined;

    // Validate service token
    if (serviceToken !== config.internalService.token) {
      throw new AppError("Invalid service token", 401);
    }

    // Optional: Validate HMAC signature if configured
    if (config.internalService.webhookSecret) {
      try {
        const crypto = await import("node:crypto");
        const payloadString = JSON.stringify({ jobId, status, result, error, metadata });
        const hmac = crypto.createHmac("sha256", config.internalService.webhookSecret);
        hmac.update(payloadString);
        const expected = hmac.digest("hex");
        if (!signature || signature !== expected) {
          throw new AppError("Invalid webhook signature", 401);
        }
      } catch (e) {
        // If signature validation fails, block the request
        if (e instanceof AppError) throw e;
        throw new AppError("Webhook signature validation failed", 401);
      }
    }

    const job = await prisma.job.findUnique({
      where: { id: jobId },
    });

    if (!job) {
      throw new AppError("Job not found", 404);
    }

    if (status === "completed") {
      await QueueService.completeJob(jobId, result);
    } else if (status === "failed") {
      await QueueService.failJob(jobId, error || "Job failed");
    }

    // Store metadata if provided
    if (metadata) {
      await prisma.job.update({
        where: { id: jobId },
        data: {
          metadata: metadata as any,
        },
      });
    }

    res.status(200).json({
      success: true,
      message: "Webhook processed successfully",
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

    const metrics = await QueueService.getQueueMetrics(queueName as string);

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
      throw new AppError("Queue name is required", 400);
    }

    const olderThanMs = olderThanHours * 60 * 60 * 1000;
    const result = await QueueService.cleanOldJobs(queueName, olderThanMs);

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
