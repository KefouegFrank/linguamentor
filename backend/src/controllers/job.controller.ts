import { Request, Response, NextFunction } from "express";
import { prisma } from "../prisma/client";
import { QueueService, QUEUE_NAMES } from "../services/queue.service";
import { AppError } from "../utils/errors";
import { JobStatus, JobType, JobPriority, FileStatus, NotificationType } from "@prisma/client";
import { config } from "../config/config";
import { AccessTokenPayload } from "../types/auth.types";
import { usageService } from "../services/usage.service";
import { auditLogger } from "../utils/auditLogger";
import { notificationService } from "../services/notification.service";

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
    "x-timestamp"?: string;
    "x-idempotency-key"?: string;
    "x-signature"?: string;
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

    // Enforce quotas: block job creation if current usage meets or exceeds quota
    const usage = await usageService.getUsage(userId);
    if (usage.tokensUsed >= usage.dailyQuota || usage.tokensUsed >= usage.monthlyQuota) {
      await auditLogger({
        action: "quota.exceeded",
        resource: "usage",
        userId,
        ip: req.ip,
        userAgent: req.get("user-agent") || undefined,
        correlationId: (req as any).correlationId,
        metadata: { tokensUsed: usage.tokensUsed, dailyQuota: usage.dailyQuota, monthlyQuota: usage.monthlyQuota },
      });
      // Create in-app notification for quota exceeded
      try {
        await notificationService.createNotification({
          userId,
          type: NotificationType.QUOTA_EXCEEDED,
          title: "Usage quota exceeded",
          message: "You have reached your daily or monthly quota. Please wait for reset or contact support.",
          metadata: {
            tokensUsed: usage.tokensUsed,
            dailyQuota: usage.dailyQuota,
            monthlyQuota: usage.monthlyQuota,
          },
        });
      } catch {}
      throw new AppError("Quota exceeded. Please wait for reset or contact support.", 403);
    }

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
    // Audit log
    await auditLogger({
      action: "job.create",
      resource: jobId,
      userId,
      ip: req.ip,
      userAgent: req.get("user-agent") || undefined,
      correlationId: (req as any).correlationId,
      metadata: { type, priority, queueName, fileId },
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
    const timestampHeader = req.headers["x-timestamp"];
    const idempotencyKey = req.headers["x-idempotency-key"];

    // Validate service token
    if (serviceToken !== config.internalService.token) {
      throw new AppError("Invalid service token", 401);
    }

    // Validate timestamp freshness (5 minute window) and idempotency key presence
    if (!timestampHeader || !idempotencyKey) {
      throw new AppError("Missing timestamp or idempotency key", 400);
    }
    const timestamp = Number(timestampHeader);
    if (!Number.isFinite(timestamp)) {
      throw new AppError("Invalid timestamp", 400);
    }
    const now = Date.now();
    const fiveMinutes = 5 * 60 * 1000;
    if (Math.abs(now - timestamp) > fiveMinutes) {
      throw new AppError("Webhook timestamp out of acceptable window", 401);
    }

    // Optional: Validate HMAC signature if configured (include timestamp and idempotency key)
    if (config.internalService.webhookSecret) {
      try {
        const crypto = await import("node:crypto");
        const payloadString = JSON.stringify({ jobId, status, result, error, metadata, timestamp, idempotencyKey });
        const hmac = crypto.createHmac("sha256", config.internalService.webhookSecret);
        hmac.update(payloadString);
        const expected = hmac.digest("hex");
        if (!signature || signature !== expected) {
          throw new AppError("Invalid webhook signature", 401);
        }
      } catch (e) {
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

    // Idempotency: check if this idempotencyKey was already processed
    const existingMetadata: any = (job as any).metadata || {};
    const processedKeys: string[] = Array.isArray(existingMetadata.webhookProcessedKeys)
      ? existingMetadata.webhookProcessedKeys
      : [];
    if (processedKeys.includes(idempotencyKey as string)) {
      return res.status(200).json({ success: true, message: "Webhook already processed" });
    }

    if (status === "completed") {
      await QueueService.completeJob(jobId, result);
      // Increment usage tokens if provided in result
      try {
        const payload: any = (job as any).payload || {};
        const userIdFromJob: string | undefined = payload.userId;
        const tokensCandidate =
          (result && typeof (result as any).tokensUsed === "number" && (result as any).tokensUsed) ||
          (result && (result as any).tokenUsage && typeof (result as any).tokenUsage.total === "number" && (result as any).tokenUsage.total) ||
          (result && (result as any).usage && typeof (result as any).usage.totalTokens === "number" && (result as any).usage.totalTokens) ||
          0;
        if (userIdFromJob && tokensCandidate > 0) {
          await usageService.incrementTokens(userIdFromJob, tokensCandidate);
          await auditLogger({
            action: "usage.tokens.incremented",
            resource: jobId,
            userId: userIdFromJob,
            ip: req.ip,
            userAgent: req.get("user-agent") || undefined,
            correlationId: (req as any).correlationId,
            metadata: { tokensAdded: tokensCandidate },
          });

          // Exam scoring integration: persist result and notify
          try {
            const payload: any = (job as any)?.payload || {};
            const submissionId: string | undefined = payload?.submissionId;
            const sessionId: string | undefined = payload?.sessionId;
            const isExamScore = payload?.operation === "exam_score" && submissionId && sessionId;
            if (isExamScore) {
              const score = Number((result?.score ?? result?.payload?.score ?? 0) || 0);
              const rubric = (result as any)?.rubric ?? (result as any)?.payload?.rubric ?? null;
              const feedback = (result as any)?.feedback ?? (result as any)?.payload?.feedback ?? null;
              const aiModel = (result as any)?.model ?? (result as any)?.payload?.model ?? "unknown";
              const aiUsage = (result as any)?.usage ?? null;

              const examResult = await prisma.examResult.create({
                data: {
                  score,
                  rubric: rubric as any,
                  feedback,
                  metadata: { model: aiModel, usage: aiUsage } as any,
                },
              });

              await prisma.examSubmission.update({
                where: { id: submissionId },
                data: { aiResultId: examResult.id },
              });

              await prisma.examSession.update({
                where: { id: sessionId },
                data: { status: "COMPLETED" },
              });

              await auditLogger({
                action: "exam.scored",
                userId: userIdFromJob,
                resource: submissionId,
                ip: req.ip,
                userAgent: req.get("user-agent") || undefined,
                correlationId: (req as any).correlationId,
                metadata: { sessionId, score },
              });

              const user = await prisma.user.findUnique({ where: { id: userIdFromJob } });
              if (user?.email) {
                await QueueService.addJob(QUEUE_NAMES.EMAIL_NOTIFICATIONS, "CONTENT_GENERATION" as any, {
                  to: user.email,
                  subject: "Exam feedback ready",
                  template: "exam_feedback_ready",
                  data: { score, feedback, sessionId },
                });
              }

              // Create in-app notification for exam feedback ready
              try {
                await notificationService.createNotification({
                  userId: userIdFromJob,
                  type: NotificationType.EXAM_FEEDBACK_READY,
                  title: "Your exam feedback is ready",
                  message: typeof score === "number" ? `Your exam was scored. Score: ${score}.` : "Your exam feedback is now available.",
                  metadata: { sessionId, submissionId, score },
                });
              } catch {}
            }
          } catch {}
        }
      } catch (e) {
        // Swallow usage update errors to avoid blocking webhook processing
      }
    } else if (status === "failed") {
      await QueueService.failJob(jobId, error || "Job failed");
    }

    // Store metadata (merged) and record processed idempotency key
    const newMetadata = {
      ...(existingMetadata || {}),
      ...(metadata || {}),
      webhookProcessedKeys: [...processedKeys, idempotencyKey],
      webhookLastTimestamp: timestamp,
    } as any;
    await prisma.job.update({
      where: { id: jobId },
      data: { metadata: newMetadata },
    });

    await auditLogger({
      action: status === "completed" ? "job.webhook.completed" : "job.webhook.failed",
      resource: jobId,
      ip: req.ip,
      userAgent: req.get("user-agent") || undefined,
      correlationId: (req as any).correlationId,
      metadata: { status, hasResult: !!result, error: error ?? undefined },
    });

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
