/**
 * File Input Validation (Backend)
 * Zod schemas for file-related endpoints
 */

import { z } from "zod";
import { config } from "../config/config";

// Mirror Prisma enum values to avoid direct dependency
const FileTypeValues = [
  "AUDIO",
  "VIDEO",
  "IMAGE",
  "DOCUMENT",
  "OTHER",
] as const;

export const createUploadSchema = z.object({
  filename: z.string().min(1, "Filename is required").max(255),
  contentType: z
    .string()
    .min(1, "Content type is required")
    .refine((val) => config.upload.allowedMimeTypes.includes(val), {
      message: "File type not allowed",
    }),
  fileType: z.enum(FileTypeValues),
  size: z
    .number()
    .int("File size must be an integer")
    .positive("File size must be positive")
    .refine((val) => val <= config.upload.maxFileSize, {
      message: "File size exceeds maximum allowed size",
    }),
  metadata: z.record(z.string(), z.any()).optional(),
});

export const processFileSchema = z.object({
  operation: z.enum([
    "transcribe",
    "translate",
    "summarize",
    "convert",
    "compress",
    "extract",
  ]),
  targetLanguage: z.string().min(2).max(50).optional(),
  parameters: z.record(z.string(), z.any()).optional(),
  priority: z.enum(["LOW", "NORMAL", "HIGH"]).optional(),
  webhookUrl: z.string().url("Invalid webhook URL").optional(),
});

export type CreateUploadInput = z.infer<typeof createUploadSchema>;
export type ProcessFileInput = z.infer<typeof processFileSchema>;
