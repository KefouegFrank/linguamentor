import { Request, Response, NextFunction } from "express";
import { AppError } from "../utils/errors";
import { auditLogger } from "../utils/auditLogger";
import { notificationService } from "../services/notification.service";
import { AccessTokenPayload } from "../types/auth.types";

interface AuthenticatedRequest extends Request {
  user?: AccessTokenPayload;
}

export const getMyNotifications = async (req: AuthenticatedRequest, res: Response, next: NextFunction) => {
  try {
    const userId = req.user?.userId;
    if (!userId) throw new AppError("Unauthorized", 401);
    const notifications = await notificationService.getMyNotifications(userId);
    await auditLogger({
      action: "notifications.list",
      resource: userId,
      userId,
      ip: req.ip,
      userAgent: req.get("user-agent") || undefined,
      correlationId: (req as any).correlationId,
    });
    res.json({ success: true, data: { notifications } });
  } catch (error) {
    next(error);
  }
};

export const markNotificationRead = async (req: AuthenticatedRequest, res: Response, next: NextFunction) => {
  try {
    const userId = req.user?.userId;
    if (!userId) throw new AppError("Unauthorized", 401);
    const { id } = req.params as { id: string };
    const updated = await notificationService.markRead(id, userId);
    await auditLogger({
      action: "notifications.read",
      resource: id,
      userId,
      ip: req.ip,
      userAgent: req.get("user-agent") || undefined,
      correlationId: (req as any).correlationId,
    });
    res.json({ success: true, data: { notification: updated } });
  } catch (error) {
    next(error);
  }
};
