import { Job as BullJob } from "bullmq";
import { QueueService, QUEUE_NAMES } from "../services/queue.service";
import { prisma } from "../prisma/client";
import { s3Service } from "../services/s3.service";
import { config } from "../config/config";
import { JobStatus, JobType, FileStatus } from "@prisma/client";
import axios from "axios";

/**
 * AI Processing Job Worker
 */
export const createAIProcessingWorker = () => {
  return QueueService.createWorker(
    QUEUE_NAMES.AI_PROCESSING,
    async (job: BullJob) => {
      const { jobId, data } = job.data;
      const { fileId, operation, targetLanguage, webhookUrl, userId } = data;

      console.log(
        `Processing AI job ${jobId}: ${operation} for file ${fileId}`
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

        // Simulate AI processing (replace with actual AI service call)
        let result: any;
        let processingTime = 0;
        const startTime = Date.now();

        switch (operation) {
          case "transcribe":
            // Simulate transcription
            await simulateProgress(job, 30, "Transcribing audio...");
            processingTime = Date.now() - startTime;
            result = {
              text: "This is a simulated transcription result.",
              language: "en",
              confidence: 0.95,
              duration: 120,
            };
            break;

          case "translate":
            // Simulate translation
            await simulateProgress(job, 25, "Translating text...");
            processingTime = Date.now() - startTime;
            result = {
              originalText: "Hello world",
              translatedText: "Hola mundo",
              sourceLanguage: "en",
              targetLanguage: targetLanguage || "es",
              confidence: 0.92,
            };
            break;

          case "summarize":
            // Simulate summarization
            await simulateProgress(job, 20, "Summarizing content...");
            processingTime = Date.now() - startTime;
            result = {
              summary: "This is a simulated summary of the content.",
              originalLength: 1000,
              summaryLength: 150,
              keyPoints: ["Point 1", "Point 2", "Point 3"],
            };
            break;

          default:
            throw new Error(`Unsupported operation: ${operation}`);
        }

        // Create output file if needed
        let outputFileId: string | undefined;
        if (operation === "translate" || operation === "transcribe") {
          const outputContent = JSON.stringify(result, null, 2);
          const outputBuffer = Buffer.from(outputContent);

          const outputKey = `outputs/${fileId}-${operation}-${Date.now()}.json`;
          const outputUrl = await s3Service.uploadFile(
            outputBuffer,
            outputKey,
            "application/json"
          );

          // Create output file record (aligned with Prisma schema)
          const outputFile = await prisma.file.create({
            data: {
              originalName: `${file.originalName}-${operation}.json`,
              fileName: outputKey,
              mimeType: "application/json",
              size: BigInt(outputBuffer.length),
              fileType: file.fileType,
              status: FileStatus.UPLOADED,
              s3Bucket: config.aws.s3Bucket,
              s3Key: outputKey,
              s3Url: outputUrl,
              userId: userId,
            },
          });

          outputFileId = outputFile.id;
        }

        // Call webhook if provided
        if (webhookUrl) {
          try {
            await axios.post(webhookUrl, {
              jobId,
              status: "completed",
              result,
              processingTime,
            });
          } catch (webhookError) {
            console.error("Failed to call webhook:", webhookError);
          }
        }

        return {
          result,
          processingTime,
          outputFileId,
        };
      } catch (error) {
        // Call webhook with error if provided
        if (webhookUrl) {
          try {
            await axios.post(webhookUrl, {
              jobId,
              status: "failed",
              error: error instanceof Error ? error.message : "Unknown error",
            });
          } catch (webhookError) {
            console.error("Failed to call error webhook:", webhookError);
          }
        }

        throw error;
      }
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
        // Simulate email sending
        await simulateProgress(job, 5, "Sending email...");

        // Simulate email service integration
        const messageId = `msg_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;

        // In a real implementation, you would integrate with an email service like:
        // - SendGrid
        // - AWS SES
        // - Nodemailer with SMTP

        console.log(`Email sent successfully: ${messageId}`);

        return {
          sent: true,
          messageId,
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

  console.log("Queue workers initialized successfully");

  return {
    aiWorker,
    fileWorker,
    emailWorker,
  };
};

/**
 * Graceful shutdown
 */
export const shutdownWorkers = async () => {
  console.log("Shutting down queue workers...");
  await QueueService.close();
  console.log("Queue workers shut down successfully");
};
