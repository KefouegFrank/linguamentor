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

/**
 * Validate a route parameter as UUID v4 (string)
 */
export const validateParamUuid = (paramName: string) => {
    const uuidV4Regex = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
    return (req: Request, res: Response, next: NextFunction) => {
        const value = (req.params as any)[paramName];
        if (typeof value !== 'string' || !uuidV4Regex.test(value)) {
            return res.status(400).json({
                success: false,
                message: `Invalid parameter: ${paramName}`,
                code: 'PARAM_VALIDATION_ERROR',
            });
        }
        next();
    };
};
