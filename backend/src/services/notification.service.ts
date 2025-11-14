import { prisma } from "../prisma/client";
import { QueueService, QUEUE_NAMES } from "./queue.service";
import { JobType, NotificationType } from "@prisma/client";

class NotificationService {
  async createNotification(params: {
    userId: string;
    type: NotificationType;
    title: string;
    message: string;
    metadata?: Record<string, any>;
  }) {
    const { userId, type, title, message, metadata } = params;
    const notification = await prisma.notification.create({
      data: { userId, type, title, message, metadata: metadata as any },
    });
    return notification;
  }

  async sendEmail(params: { to: string; subject: string; template: string; data?: Record<string, any> }) {
    const jobData = { to: params.to, subject: params.subject, template: params.template, data: params.data };
    return QueueService.addJob(QUEUE_NAMES.EMAIL_NOTIFICATIONS, JobType.CONTENT_GENERATION, jobData);
  }

  async markRead(notificationId: string, userId: string) {
    return prisma.notification.update({
      where: { id: notificationId },
      data: { readAt: new Date() },
    });
  }

  async getMyNotifications(userId: string) {
    return prisma.notification.findMany({ where: { userId }, orderBy: { createdAt: "desc" } });
  }
}

export const notificationService = new NotificationService();
