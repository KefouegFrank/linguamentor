import { Request, Response, NextFunction } from 'express';
import crypto from 'crypto';

/**
 * Attaches a correlation ID to each request for cross-service tracing.
 * Uses existing `x-correlation-id` header if provided, otherwise generates a UUID.
 */
export function attachCorrelationId(req: Request, _res: Response, next: NextFunction): void {
  const headerId = req.headers['x-correlation-id'];
  const id = typeof headerId === 'string' && headerId.trim().length > 0 ? headerId : crypto.randomUUID();
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  (req as any).correlationId = id;
  next();
}

declare global {
  namespace Express {
    interface Request {
      correlationId?: string;
    }
  }
}

