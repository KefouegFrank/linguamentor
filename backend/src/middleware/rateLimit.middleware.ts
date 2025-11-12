import { Request, Response, NextFunction } from 'express';

type Options = {
    windowMs: number;
    max: number;
};

type Bucket = {
    count: number;
    resetAt: number;
};

const buckets = new Map<string, Bucket>();

export function createRateLimiter(options: Options) {
    const { windowMs, max } = options;

    return (req: Request, res: Response, next: NextFunction): void => {
        const key = `${req.ip}:${req.path}`;
        const now = Date.now();
        const current = buckets.get(key);

        if (!current || current.resetAt <= now) {
            buckets.set(key, { count: 1, resetAt: now + windowMs });
            next();
            return;
        }

        if (current.count >= max) {
            const retryAfterSec = Math.ceil((current.resetAt - now) / 1000);
            res.setHeader('Retry-After', String(retryAfterSec));
            res.status(429).json({ success: false, message: 'Too many requests. Please try again later.' });
            return;
        }

        current.count += 1;
        buckets.set(key, current);
        next();
    };
}


