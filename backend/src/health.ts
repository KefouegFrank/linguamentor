import { Request, Response } from 'express';
import { prisma } from './prisma/client';

export const livenessHandler = async (_req: Request, res: Response) => {
  res.status(200).json({ success: true, status: 'alive' });
};

export const readinessHandler = async (_req: Request, res: Response) => {
  try {
    // Simple DB readiness check
    await prisma.$queryRaw`SELECT 1`;
    res.status(200).json({ success: true, status: 'ready' });
  } catch (error) {
    res.status(503).json({ success: false, status: 'not_ready', error: 'db_unavailable' });
  }
};

