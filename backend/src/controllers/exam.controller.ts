import { Request, Response, NextFunction } from "express";
import { prisma } from "../prisma/client";
import { AppError } from "../utils/errors";
import { auditLogger } from "../utils/auditLogger";
import { QueueService, QUEUE_NAMES } from "../services/queue.service";
import { JobType, ExamStatus } from "@prisma/client";
import { createSessionSchema, submitSubmissionSchema } from "../validation/exam.validation";
import { AccessTokenPayload } from "../types/auth.types";

interface AuthenticatedRequest extends Request {
  user?: AccessTokenPayload;
}

export const createSession = async (req: AuthenticatedRequest, res: Response, next: NextFunction) => {
  try {
    const userId = req.user?.userId;
    if (!userId) throw new AppError("Unauthorized", 401);
    const parsed = createSessionSchema.safeParse(req.body);
    if (!parsed.success) throw new AppError(parsed.error.issues.map((issue) => issue.message).join(", "), 400);
    const { examType, metadata } = parsed.data;

    const session = await prisma.examSession.create({
      data: { userId, examType, status: ExamStatus.IN_PROGRESS, metadata: metadata as any },
    });

    await auditLogger({
      action: "exam.session.created",
      resource: session.id,
      userId,
      ip: req.ip,
      userAgent: req.get("user-agent") || undefined,
      correlationId: (req as any).correlationId,
      metadata: { examType },
    });

    res.status(201).json({ success: true, data: { session } });
  } catch (error) {
    next(error);
  }
};

export const submitToSession = async (req: AuthenticatedRequest, res: Response, next: NextFunction) => {
  try {
    const userId = req.user?.userId;
    if (!userId) throw new AppError("Unauthorized", 401);
    const { sessionId } = req.params as { sessionId: string };

    const session = await prisma.examSession.findFirst({ where: { id: sessionId, userId } });
    if (!session) throw new AppError("Session not found", 404);
    if (session.status !== ExamStatus.IN_PROGRESS) throw new AppError("Session not in progress", 400);

    const parsed = submitSubmissionSchema.safeParse(req.body);
    if (!parsed.success) throw new AppError(parsed.error.issues.map((issue) => issue.message).join(", "), 400);
    const { submissionType, textData, fileId } = parsed.data;

    const submission = await prisma.examSubmission.create({
      data: {
        sessionId: session.id,
        submissionType,
        textData: textData,
        fileId: fileId,
      },
    });

    // Queue assessment scoring job via AI_PROCESSING
    const jobData = {
      userId,
      operation: "exam_score",
      submissionType,
      textData,
      fileId,
      sessionId: session.id,
      submissionId: submission.id,
      examType: session.examType,
    };

    const jobId = await QueueService.addJob(
      QUEUE_NAMES.AI_PROCESSING,
      JobType.CONTENT_GENERATION,
      jobData
    );

    await auditLogger({
      action: "exam.submission.queued",
      resource: submission.id,
      userId,
      ip: req.ip,
      userAgent: req.get("user-agent") || undefined,
      correlationId: (req as any).correlationId,
      metadata: { jobId, submissionType },
    });

    res.status(202).json({ success: true, data: { submission, jobId } });
  } catch (error) {
    next(error);
  }
};

export const getSession = async (req: AuthenticatedRequest, res: Response, next: NextFunction) => {
  try {
    const userId = req.user?.userId;
    if (!userId) throw new AppError("Unauthorized", 401);
    const { sessionId } = req.params as { sessionId: string };

    const session = await prisma.examSession.findFirst({
      where: { id: sessionId, userId },
      include: {
        submissions: {
          include: {
            aiResult: true,
            file: true,
          },
        },
      },
    });

    if (!session) throw new AppError("Session not found", 404);

    await auditLogger({
      action: "exam.session.viewed",
      resource: session.id,
      userId,
      ip: req.ip,
      userAgent: req.get("user-agent") || undefined,
      correlationId: (req as any).correlationId,
    });

    res.json({ success: true, data: { session } });
  } catch (error) {
    next(error);
  }
};
