import { Job as BullJob } from "bullmq";
import { QueueService, QUEUE_NAMES } from "../services/queue.service";
import { prisma } from "../prisma/client";
import { s3Service } from "../services/s3.service";
import { config } from "../config/config";
import { JobStatus, JobType, FileStatus } from "@prisma/client";
import axios from "axios";
import { emailService } from "../services/email.service";
import { usageService } from "../services/usage.service";

/**
 * AI Processing Job Worker
 */
export const createAIProcessingWorker = () => {
  return QueueService.createWorker(
    QUEUE_NAMES.AI_PROCESSING,
    async (job: BullJob) => {
      const { jobId, data } = job.data;
      const { fileId, operation, targetLanguage, text, maxWords, userId, submissionId, sessionId, examType, submissionType, textData } = data;

      console.log(`Delegating AI job ${jobId}: ${operation} to ai-service`);

      // Build envelope expected by ai-service
      let envelope: any;

      if (operation === "transcribe") {
        const file = await prisma.file.findUnique({ where: { id: fileId } });
        if (!file || !file.s3Key) {
          throw new Error("File not found or not uploaded");
        }
        envelope = {
          jobId,
          type: "asr",
          payload: {
            audio_s3_key: file.s3Key,
            language: data?.language,
            user_id: userId,
          },
        };
      } else if (operation === "translate") {
        if (!text && !data?.sourceText) {
          throw new Error("Translate operation requires 'text' in job data");
        }
        envelope = {
          jobId,
          type: "translate",
          payload: {
            text: text || data.sourceText,
            target_language: targetLanguage || "en",
            user_id: userId,
          },
        };
      } else if (operation === "summarize") {
        if (!text && !data?.sourceText) {
          throw new Error("Summarize operation requires 'text' in job data");
        }
        envelope = {
          jobId,
          type: "summarize",
          payload: {
            text: text || data.sourceText,
            max_words: maxWords || 120,
            user_id: userId,
          },
        };
      } else if (operation === "exam_score") {
        // Build assessment envelope
        let source: any = {};
        if (submissionType === "TEXT" && (textData || text)) {
          source = { text: textData || text };
        } else if (submissionType === "AUDIO" && fileId) {
          const file = await prisma.file.findUnique({ where: { id: fileId } });
          if (!file || !file.s3Key) {
            throw new Error("File not found or not uploaded for assessment");
          }
          source = { audio_s3_key: file.s3Key };
        } else {
          throw new Error("Invalid submission for assessment scoring");
        }

        envelope = {
          jobId,
          type: "assessment",
          payload: {
            ...source,
            exam_type: examType,
            session_id: sessionId,
            submission_id: submissionId,
            user_id: userId,
          },
        };
      } else {
        throw new Error(`Unsupported operation: ${operation}`);
      }

      // Push to ai-service Redis list
      await QueueService.publishAIEnvelope(envelope);

      // Update minimal progress to indicate delegation
      await QueueService.updateJobProgress(jobId, 1);

      // Return a lightweight marker; actual completion comes via internal webhook
      return { delegated: true };
    }
  );
};

/**
 * File Processing Job Worker
 */
export const createFileProcessingWorker = () => {
  return QueueService.createWorker(
    QUEUE_NAMES.FILE_PROCESSING,
    async (job: BullJob) => {
      const { jobId, data } = job.data;
      const { fileId, operation, parameters = {} } = data;

      console.log(
        `Processing file job ${jobId}: ${operation} for file ${fileId}`
      );

      try {
        // Get file details
        const file = await prisma.file.findUnique({
          where: { id: fileId },
        });

        if (!file || !file.s3Key) {
          throw new Error("File not found or not uploaded");
        }

        // Download file from S3
        const fileBuffer = await s3Service.downloadFile(file.s3Key);

        let result: any;
        let outputFileId: string | undefined;
        const startTime = Date.now();

        switch (operation) {
          case "convert":
            // Simulate file conversion
            await simulateProgress(job, 15, "Converting file format...");

            // Create converted file (simulate PDF to TXT conversion)
            const convertedContent =
              "This is converted content from the original file.";
            const convertedBuffer = Buffer.from(convertedContent);
            const convertedKey = `conversions/${fileId}-converted-${Date.now()}.txt`;

            await s3Service.uploadFile(
              convertedBuffer,
              convertedKey,
              "text/plain"
            );

            // Create output file record (aligned with Prisma schema)
            const convertedFile = await prisma.file.create({
              data: {
                originalName: `${file.originalName}-converted.txt`,
                fileName: convertedKey,
                mimeType: "text/plain",
                size: BigInt(convertedBuffer.length),
                fileType: file.fileType,
                status: FileStatus.UPLOADED,
                s3Bucket: config.aws.s3Bucket,
                s3Key: convertedKey,
                userId: file.userId,
              },
            });

            outputFileId = convertedFile.id;
            result = {
              originalFormat: file.mimeType,
              convertedFormat: "text/plain",
              outputFileId,
            };
            break;

          case "compress":
            // Simulate file compression
            await simulateProgress(job, 10, "Compressing file...");

            // Create compressed file (simulate smaller size)
            const compressedContent = fileBuffer.slice(
              0,
              Math.floor(fileBuffer.length * 0.7)
            );
            const compressedKey = `compressed/${fileId}-compressed-${Date.now()}.zip`;

            await s3Service.uploadFile(
              compressedContent,
              compressedKey,
              "application/zip"
            );

            // Create output file record (aligned with Prisma schema)
            const compressedFile = await prisma.file.create({
              data: {
                originalName: `${file.originalName}-compressed.zip`,
                fileName: compressedKey,
                mimeType: "application/zip",
                size: BigInt(compressedContent.length),
                fileType: file.fileType,
                status: FileStatus.UPLOADED,
                s3Bucket: config.aws.s3Bucket,
                s3Key: compressedKey,
                userId: file.userId,
              },
            });

            outputFileId = compressedFile.id;
            const originalSizeNum = Number(file.size);
            const compressedSizeNum = compressedContent.length;
            result = {
              originalSize: originalSizeNum,
              compressedSize: compressedSizeNum,
              compressionRatio:
                originalSizeNum > 0
                  ? (originalSizeNum - compressedSizeNum) / originalSizeNum
                  : 0,
              outputFileId,
            };
            break;

          case "extract":
            // Simulate text extraction
            await simulateProgress(job, 12, "Extracting content...");

            result = {
              extractedText: "This is extracted text content from the file.",
              wordCount: 150,
              language: "en",
              confidence: 0.98,
            };
            break;

          default:
            throw new Error(`Unsupported operation: ${operation}`);
        }

        const processingTime = Date.now() - startTime;

        return {
          result,
          processingTime,
          outputFileId,
          metadata: {
            originalFileId: fileId,
            operation,
            parameters,
          },
        };
      } catch (error) {
        throw error;
      }
    }
  );
};

/**
 * Email Notification Job Worker
 */
export const createEmailNotificationWorker = () => {
  return QueueService.createWorker(
    QUEUE_NAMES.EMAIL_NOTIFICATIONS,
    async (job: BullJob) => {
      const { jobId, data } = job.data;
      const { to, subject, template, data: emailData } = data;

      console.log(`Processing email job ${jobId}: ${subject} to ${to}`);

      try {
        await simulateProgress(job, 5, "Sending email...");

        if (template === "exam_feedback_ready") {
          const details = {
            score: emailData?.score,
            feedback: emailData?.feedback,
            sessionId: emailData?.sessionId,
            examType: emailData?.examType,
            dashboardUrl: emailData?.dashboardUrl,
          };
          await emailService.sendExamFeedbackEmail(
            to,
            emailData?.userName || to,
            details
          );
        } else if (template === "generic") {
          await emailService.sendEmailWithRetry(to, {
            subject: subject || "Notification",
            html: `<p>${emailData?.html || emailData?.message || "You have a new notification."}</p>`,
            text: emailData?.text || emailData?.message || "You have a new notification.",
          });
        } else {
          // Default fallback
          await emailService.sendEmailWithRetry(to, {
            subject: subject || "Notification",
            html: `<p>${emailData?.message || "You have a new notification."}</p>`,
            text: emailData?.message || "You have a new notification.",
          });
        }

        return {
          sent: true,
          recipient: to,
          subject,
          template,
        };
      } catch (error) {
        throw error;
      }
    }
  );
};

/**
 * System Tasks Worker (recurring cron jobs)
 */
export const createSystemTasksWorker = () => {
  return QueueService.createWorker(
    QUEUE_NAMES.SYSTEM_TASKS,
    async (job: BullJob) => {
      const { data } = job;
      const task = data?.task as string;
      if (task === "usage.reset.daily") {
        await usageService.resetDaily();
        return { ok: true, task };
      }
      if (task === "usage.reset.monthly") {
        await usageService.resetMonthly();
        return { ok: true, task };
      }
      throw new Error(`Unknown system task: ${task}`);
    }
  );
};

/**
 * Simulate job progress (for demonstration)
 */
async function simulateProgress(job: BullJob, steps: number, message: string) {
  for (let i = 1; i <= steps; i++) {
    await new Promise((resolve) => setTimeout(resolve, 100));
    await job.updateProgress((i / steps) * 100);
    if (message) {
      console.log(`${message} ${Math.round((i / steps) * 100)}%`);
    }
  }
}

/**
 * Initialize all workers
 */
export const initializeWorkers = () => {
  console.log("Initializing queue workers...");

  const aiWorker = createAIProcessingWorker();
  const fileWorker = createFileProcessingWorker();
  const emailWorker = createEmailNotificationWorker();
  const systemWorker = createSystemTasksWorker();

  console.log("Queue workers initialized successfully");

  return {
    aiWorker,
    fileWorker,
    emailWorker,
    systemWorker,
  };
};

export const scheduleRecurringUsageTasks = async () => {
  // Daily at midnight
  await QueueService.scheduleRecurringTask(
    QUEUE_NAMES.SYSTEM_TASKS,
    "usage.reset.daily",
    { task: "usage.reset.daily" },
    "0 0 * * *"
  );
  // Monthly at midnight on the 1st
  await QueueService.scheduleRecurringTask(
    QUEUE_NAMES.SYSTEM_TASKS,
    "usage.reset.monthly",
    { task: "usage.reset.monthly" },
    "0 0 1 * *"
  );
};

/**
 * Graceful shutdown
 */
export const shutdownWorkers = async () => {
  console.log("Shutting down queue workers...");
  await QueueService.close();
  console.log("Queue workers shut down successfully");
};
