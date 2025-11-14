import { Request, Response } from "express";
import { usageService } from "../services/usage.service";
import { auditLogger } from "../utils/auditLogger";
import { usageQuotaUpdateSchema } from "../validation/usage.validation";
import { AppError } from "../utils/errors";

export async function getMyUsage(req: Request, res: Response) {
  const userId = (req as any).user?.userId;
  if (!userId) throw new AppError("Unauthorized", 401);
  const usage = await usageService.getUsage(userId);
  await auditLogger({
    action: "usage.view",
    resource: "usage",
    userId,
    ip: req.ip,
    userAgent: req.get("user-agent") || undefined,
    correlationId: (req as any).correlationId,
  });
  res.json({ usage });
}

export async function patchUsageQuota(req: Request, res: Response) {
  const userId = (req as any).user?.userId;
  if (!userId) throw new AppError("Unauthorized", 401);
  const role = (req as any).user?.role;
  if (role !== "ADMIN") throw new AppError("Forbidden", 403);

  const parsed = usageQuotaUpdateSchema.safeParse(req.body);
  if (!parsed.success) throw new AppError(parsed.error.issues.map((issue) => issue.message).join(", "), 400);

  const targetUserId = (req.query.userId as string) || userId; // default to self if not specified
  const updated = await usageService.updateQuota(targetUserId, parsed.data);

  await auditLogger({
    action: "usage.quota.update",
    resource: "usage",
    userId,
    ip: req.ip,
    userAgent: req.get("user-agent") || undefined,
    correlationId: (req as any).correlationId,
    metadata: { targetUserId, fields: Object.keys(parsed.data) },
  });

  res.json({ usage: updated });
}
