/**
 * Authentication Middleware
 * Protects routes by verifying JWT access tokens and extracting user information
 */

import { Request, Response, NextFunction } from 'express';
import { verifyAccessToken } from '../utils/auth.utils';
import { AccessTokenPayload, type UserRole } from '../types/auth.types';

/**
 * Extend Express Request interface to include user data
 */
declare global {
  namespace Express {
    interface Request {
      user?: AccessTokenPayload;
    }
  }
}

/**
 * Middleware to authenticate requests using JWT access token
 * Extracts token from Authorization header (Bearer token)
 */
export const authenticate = async (
  req: Request,
  res: Response,
  next: NextFunction
): Promise<void> => {
  try {
    // Extract token from Authorization header
    const authHeader = req.headers.authorization;

    if (!authHeader) {
      res.status(401).json({
        success: false,
        message: 'Authentication required. No token provided.',
      });
      return;
    }

    // Check if header follows Bearer token format
    if (!authHeader.startsWith('Bearer ')) {
      res.status(401).json({
        success: false,
        message: 'Invalid token format. Expected: Bearer <token>',
      });
      return;
    }

    // Extract token
    const token = authHeader.substring(7); // Remove 'Bearer ' prefix

    // Verify token
    const payload = verifyAccessToken(token);

    // Attach user data to request object
    req.user = payload;

    // Continue to next middleware/route handler
    next();
  } catch (error) {
    // Handle specific token errors
    if (error instanceof Error) {
      const msg = error.message.toLowerCase();
      if (msg.includes('expired')) {
        res.status(401).json({
          success: false,
          message: 'Token has expired. Please refresh your token.',
          code: 'TOKEN_EXPIRED',
        });
        return;
      }

      if (msg.includes('invalid')) {
        res.status(401).json({
          success: false,
          message: 'Invalid token. Please login again.',
          code: 'INVALID_TOKEN',
        });
        return;
      }
    }

    // Generic error
    res.status(401).json({
      success: false,
      message: 'Authentication failed.',
    });
  }
};

/**
 * Middleware to check if authenticated user has required role(s)
 * @param allowedRoles - Array of roles that are allowed to access the route
 * @returns Middleware function
 */
export const authorize = (...allowedRoles: UserRole[]) => {
  return (req: Request, res: Response, next: NextFunction): void => {
    // Check if user is authenticated
    if (!req.user) {
      res.status(401).json({
        success: false,
        message: 'Authentication required.',
      });
      return;
    }

    // Check if user has required role
    if (!allowedRoles.includes(req.user.role)) {
      res.status(403).json({
        success: false,
        message: 'You do not have permission to access this resource.',
      });
      return;
    }

    // User is authorized, continue
    next();
  };
};

/**
 * Optional authentication middleware
 * Does not fail if no token is provided, but attaches user data if valid token exists
 * Useful for routes that have different behavior for authenticated vs unauthenticated users
 */
export const optionalAuthenticate = async (
  req: Request,
  res: Response,
  next: NextFunction
): Promise<void> => {
  try {
    const authHeader = req.headers.authorization;

    if (!authHeader || !authHeader.startsWith('Bearer ')) {
      // No token provided, continue without user data
      next();
      return;
    }

    const token = authHeader.substring(7);
    const payload = verifyAccessToken(token);

    // Attach user data to request
    req.user = payload;

    next();
  } catch (error) {
    // Token is invalid but we don't fail the request
    // Just continue without user data
    next();
  }
};