import { z } from "zod";

export const createSessionSchema = z.object({
  examType: z.string().min(1),
  metadata: z.record(z.string(), z.any()).optional(),
});

export const submitSubmissionSchema = z.object({
  submissionType: z.enum(["TEXT", "AUDIO"]),
  textData: z.string().min(1).optional(),
  fileId: z.string().uuid().optional(),
}).refine((data) => {
  if (data.submissionType === "TEXT") return !!data.textData;
  if (data.submissionType === "AUDIO") return !!data.fileId;
  return false;
}, { message: "Provide textData for TEXT or fileId for AUDIO" });

export type CreateSessionInput = z.infer<typeof createSessionSchema>;
export type SubmitSubmissionInput = z.infer<typeof submitSubmissionSchema>;
