/**
 * Authentication Routes
 * Defines all authentication-related API endpoints
 */

import { Router } from 'express';
import { z } from 'zod';
import {
    register,
    login,
    refreshToken,
    logout,
    getCurrentUser,
} from '../controllers/auth.controller';
import { authenticate } from '../middleware/auth.middleware';
import { validateBody } from '../middleware/validation.middleware';
import { registerSchema, loginSchema, refreshTokenSchema } from '../validation/auth.validation';
import { securityConfig } from '../config/auth.config';
import { createRateLimiter } from '../middleware/rateLimit.middleware';

const router = Router();

// Rate limiters (route-level)
const loginLimiter = createRateLimiter({
    windowMs: securityConfig.rateLimit.login.windowMs,
    max: securityConfig.rateLimit.login.max,
});

const refreshLimiter = createRateLimiter({
    windowMs: securityConfig.rateLimit.refresh.windowMs,
    max: securityConfig.rateLimit.refresh.max,
});

/**
 * Public routes (no authentication required)
 */

// POST /api/auth/register - Register a new user
router.post('/register', validateBody(registerSchema), register);

// POST /api/auth/login - Login user
router.post('/login', loginLimiter, validateBody(loginSchema), login);

// POST /api/auth/refresh - Refresh access token
router.post('/refresh', refreshLimiter, validateBody(refreshTokenSchema), refreshToken);

// POST /api/auth/logout - Logout user (revoke refresh token)
router.post('/logout', validateBody(refreshTokenSchema), logout);

/**
 * Protected routes (authentication required)
 */

// GET /api/auth/me - Get current authenticated user
router.get('/me', authenticate, getCurrentUser);


export default router;