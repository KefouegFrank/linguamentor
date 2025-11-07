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
    requestPasswordReset,
    resetPassword,
    verifyEmail,
    resendVerificationEmail,
    changePassword,
    updateProfile,
    deleteAccount,
} from '../controllers/auth.controller';
import { oauthController } from '../controllers/oauth.controller';
import { authenticate } from '../middleware/auth.middleware';
import { validateBody } from '../middleware/validation.middleware';
import {
    registerSchema,
    loginSchema,
    refreshTokenSchema,
    passwordResetRequestSchema,
    passwordResetConfirmSchema,
    emailVerificationSchema,
    changePasswordSchema,
    updateProfileSchema,
    deleteAccountSchema,
    oauthLoginSchema,
} from '../validation/auth.validation';
import { securityConfig } from '../config/auth.config';
import { createRateLimiter } from '../middleware/rateLimit.middleware';
import { QueueService } from '../services/queue.service';

export const createAuthRouter = (queueService: QueueService) => {
  const router = Router();

  // Rate limiters (route-level)
  const loginLimiter = createRateLimiter(queueService['connection'], {
      windowMs: securityConfig.rateLimit.login.windowMs,
      max: securityConfig.rateLimit.login.max,
  });

  const refreshLimiter = createRateLimiter(queueService['connection'], {
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
 * Password reset routes (public)
 */
router.post('/password-reset/request', validateBody(passwordResetRequestSchema), requestPasswordReset);
router.post('/password-reset/confirm', validateBody(passwordResetConfirmSchema), resetPassword);

/**
 * Email verification routes (public)
 */
router.post('/verify-email', validateBody(emailVerificationSchema), verifyEmail);

/**
 * OAuth routes
 */
router.get('/oauth/:provider', oauthController.initiateOAuth);
router.get('/oauth/:provider/callback', oauthController.handleOAuthCallback);
router.post('/oauth/mobile', validateBody(oauthLoginSchema), oauthController.mobileOAuthLogin);

/**
 * Protected routes (authentication required)
 */

// GET /api/auth/me - Get current authenticated user
router.get('/me', authenticate, getCurrentUser);

/**
 * Account management routes (protected)
 */
router.post('/resend-verification', authenticate, resendVerificationEmail);
router.post('/change-password', authenticate, validateBody(changePasswordSchema), changePassword);
router.put('/profile', authenticate, validateBody(updateProfileSchema), updateProfile);
router.delete('/account', authenticate, validateBody(deleteAccountSchema), deleteAccount);


  return router;
};