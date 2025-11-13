/**
 * Job Input Validation
 * Zod schemas for job-related endpoints
 */

import { z } from "zod";

// Mirror Prisma enum values
const JobTypeValues = ["AI_PROCESSING", "FILE_CONVERSION"] as const;
const JobPriorityValues = ["LOW", "NORMAL", "HIGH"] as const;

export const createJobSchema = z.object({
  type: z.enum(JobTypeValues),
  priority: z.enum(JobPriorityValues).optional(),
  fileId: z.string().uuid("Invalid file ID").optional(),
  data: z.record(z.string(), z.any()).default({}),
  webhookUrl: z.string().url("Invalid webhook URL").optional(),
  delay: z.number().int().min(0).optional(),
});

export const webhookSchema = z.object({
  jobId: z.string().uuid("Invalid job ID"),
  status: z.enum(["completed", "failed"]),
  result: z.any().optional(),
  error: z.string().optional(),
  metadata: z.record(z.string(), z.any()).optional(),
});

export type CreateJobInput = z.infer<typeof createJobSchema>;
export type JobWebhookInput = z.infer<typeof webhookSchema>;
