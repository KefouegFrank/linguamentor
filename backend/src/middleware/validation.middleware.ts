import { Request, Response, NextFunction } from 'express';
import { ZodSchema } from 'zod';

/**
 * Validate request body against a Zod schema.
 * Returns sanitized data on req.body or a 400 Validation response.
 */
export const validateBody = <T>(schema: ZodSchema<T>) => {
    return (req: Request, res: Response, next: NextFunction) => {
        const result = schema.safeParse(req.body);
        if (!result.success) {
            return res.status(400).json({
                success: false,
                message: 'Validation failed',
                code: 'VALIDATION_ERROR',
                details: result.error.issues,
            });
        }

        // Replace body with parsed/typed data
        req.body = result.data;
        return next();
    };
};
