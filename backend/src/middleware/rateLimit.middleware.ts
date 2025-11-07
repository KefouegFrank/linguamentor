import { Request, Response, NextFunction } from 'express';
import IORedis from 'ioredis';
import { AppError } from '../utils/errors';

interface RateLimitOptions {
    windowMs: number; // Time window in milliseconds
    max: number; // Maximum number of requests per window
    keyGenerator?: (req: Request) => string; // Custom key generator
    message?: string; // Custom error message
    skipSuccessfulRequests?: boolean; // Don't count successful requests
    skipFailedRequests?: boolean; // Don't count failed requests
}

interface RateLimitInfo {
  total: number;
  remaining: number;
  reset: Date;
}

/**
 * Redis-backed rate limiting middleware
 */
export const createRateLimiter = (redisConnection: IORedis, options: RateLimitOptions) => {
  const {
    windowMs,
    max,
    keyGenerator = (req: Request) => req.ip || 'unknown',
    message = 'Too many requests, please try again later',
    skipSuccessfulRequests = false,
    skipFailedRequests = false,
  } = options;

  return async (req: Request, res: Response, next: NextFunction) => {
    try {
      const key = `rate_limit:${keyGenerator(req)}`;
      const windowSeconds = Math.ceil(windowMs / 1000);
      
      // Get current count using Redis pipeline for atomic operations
      const pipeline = redisConnection.pipeline();
      pipeline.incr(key);
      pipeline.expire(key, windowSeconds);
      
      const results = await pipeline.exec();
      const current = (results?.[0]?.[1] as number) || 0;
      
      // Calculate remaining requests and reset time
      const remaining = Math.max(0, max - current);
      const resetTime = new Date(Date.now() + windowMs);
      
      // Set rate limit headers
      res.setHeader('X-RateLimit-Limit', max);
      res.setHeader('X-RateLimit-Remaining', remaining);
      res.setHeader('X-RateLimit-Reset', resetTime.toISOString());
      
      // Check if limit exceeded
      if (current > max) {
        // Add Retry-After header
        const retryAfter = Math.ceil(windowMs / 1000);
        res.setHeader('Retry-After', retryAfter);
        
        return res.status(429).json({
          success: false,
          error: {
            message,
            code: 'RATE_LIMIT_EXCEEDED',
            retryAfter,
          },
        });
      }
      
      // Store rate limit info for potential use in response
      (req as any).rateLimit = {
        total: max,
        remaining,
        reset: resetTime,
      } as RateLimitInfo;
      
      // Handle skip options
      if (skipSuccessfulRequests || skipFailedRequests) {
        const originalSend = res.send;
        const originalJson = res.json;
        
        res.send = function(data: any) {
          handleResponse(this.statusCode);
          return originalSend.call(this, data);
        };
        
        res.json = function(data: any) {
          handleResponse(this.statusCode);
          return originalJson.call(this, data);
        };
        
        function handleResponse(statusCode: number) {
          const isSuccess = statusCode >= 200 && statusCode < 400;
          const isFailure = statusCode >= 400;
          
          if ((skipSuccessfulRequests && isSuccess) || (skipFailedRequests && isFailure)) {
            // Decrement the counter since we're skipping this request
            redisConnection.decr(key).catch(err => {
              console.error('Failed to decrement rate limit counter:', err);
            });
          }
        }
      }
      
      next();
    } catch (error) {
      console.error('Rate limiting error:', error);
      // Fail open - allow request if rate limiting fails
      next();
    }
  };
};

/**
 * User-specific rate limiter (by user ID)
 */
export const userRateLimiter = (redisConnection: IORedis) => createRateLimiter(redisConnection, {
  windowMs: 15 * 60 * 1000, // 15 minutes
  max: 100, // 100 requests per 15 minutes
  keyGenerator: (req: Request) => {
    const user = (req as any).user;
    return user ? `user:${user.id}` : `ip:${req.ip || 'unknown'}`;
  },
  message: 'Too many requests from this user, please try again later',
});

/**
 * API-specific rate limiter (stricter for API endpoints)
 */
export const apiRateLimiter = (redisConnection: IORedis) => createRateLimiter(redisConnection, {
  windowMs: 60 * 1000, // 1 minute
  max: 60, // 60 requests per minute
  keyGenerator: (req: Request) => {
    const user = (req as any).user;
    return user ? `api:${user.id}` : `api:${req.ip || 'unknown'}`;
  },
  message: 'Too many API requests, please try again later',
});

/**
 * File upload rate limiter (more restrictive)
 */
export const uploadRateLimiter = (redisConnection: IORedis) => createRateLimiter(redisConnection, {
  windowMs: 60 * 60 * 1000, // 1 hour
  max: 10, // 10 uploads per hour
  keyGenerator: (req: Request) => {
    const user = (req as any).user;
    return user ? `upload:${user.id}` : `upload:${req.ip || 'unknown'}`;
  },
  message: 'Too many file uploads, please try again later',
});

/**
 * Job creation rate limiter
 */
export const jobRateLimiter = (redisConnection: IORedis) => createRateLimiter(redisConnection, {
  windowMs: 5 * 60 * 1000, // 5 minutes
  max: 20, // 20 jobs per 5 minutes
  keyGenerator: (req: Request) => {
    const user = (req as any).user;
    return user ? `job:${user.id}` : `job:${req.ip || 'unknown'}`;
  },
  message: 'Too many job requests, please try again later',
});

/**
 * Authentication rate limiter (for login/register endpoints)
 */
export const authRateLimiter = (redisConnection: IORedis) => createRateLimiter(redisConnection, {
  windowMs: 15 * 60 * 1000, // 15 minutes
  max: 5, // 5 attempts per 15 minutes
  keyGenerator: (req: Request) => `auth:${req.ip || 'unknown'}`,
  message: 'Too many authentication attempts, please try again later',
  skipSuccessfulRequests: true, // Don't count successful logins
});

/**
 * Webhook rate limiter (for service-to-service communication)
 */
export const webhookRateLimiter = (redisConnection: IORedis) => createRateLimiter(redisConnection, {
  windowMs: 60 * 1000, // 1 minute
  max: 1000, // 1000 webhooks per minute (high limit for services)
  keyGenerator: (req: Request) => `webhook:${req.ip || 'unknown'}`,
  message: 'Too many webhook requests, please try again later',
});

/**
 * Custom rate limiter factory
 */
export const createCustomRateLimiter = (redisConnection: IORedis, options: Partial<RateLimitOptions> & { name: string }) => {
  const { name, ...rateLimitOptions } = options;
  
  return createRateLimiter(redisConnection, {
    windowMs: 60 * 1000, // 1 minute default
    max: 60, // 60 requests per minute default
    keyGenerator: (req: Request) => `${name}:${req.ip || 'unknown'}`,
    message: `Too many ${name} requests, please try again later`,
    ...rateLimitOptions,
  });
};

/**
 * Rate limit error handler
 */
export const rateLimitErrorHandler = (err: any, req: Request, res: Response, next: NextFunction) => {
  if (err.status === 429 || err.statusCode === 429) {
    return res.status(429).json({
      success: false,
      error: {
        message: err.message || 'Too many requests, please try again later',
        code: 'RATE_LIMIT_EXCEEDED',
        retryAfter: err.retryAfter || 60,
      },
    });
  }
  next(err);
};