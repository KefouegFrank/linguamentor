import { prisma } from '../prisma/client';
import { logger } from './logger';

export async function auditLogger(params: {
  action: string;
  resource?: string;
  userId?: string;
  ip?: string;
  userAgent?: string;
  metadata?: Record<string, any>;
}) {
  const { action, resource, userId, ip, userAgent, metadata } = params;
  try {
    await prisma.auditLog.create({
      data: {
        action,
        resource,
        userId,
        ip,
        userAgent,
        metadata: metadata as any,
      },
    });
  } catch (err) {
    logger.warn({ err, action, resource, userId }, 'Failed to write audit log');
  }
}

