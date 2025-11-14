import { z } from "zod";

export const usageQuotaUpdateSchema = z.object({
  dailyQuota: z.number().int().positive().optional(),
  monthlyQuota: z.number().int().positive().optional(),
}).refine((data) => data.dailyQuota !== undefined || data.monthlyQuota !== undefined, {
  message: "At least one quota field must be provided",
});

export type UsageQuotaUpdateInput = z.infer<typeof usageQuotaUpdateSchema>;
