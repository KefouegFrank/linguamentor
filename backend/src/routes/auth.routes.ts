/**
 * Authentication Routes
 * Defines all authentication-related API endpoints
 */

import { Router } from "express";
import { z } from "zod";
import {
  register,
  login,
  refreshToken,
  logout,
  getCurrentUser,
} from "../controllers/auth.controller";
import { authenticate } from "../middleware/auth.middleware";
import { validateBody } from "../middleware/validation.middleware";
import {
  registerSchema,
  loginSchema,
  refreshTokenSchema,
  passwordResetRequestSchema,
  passwordResetConfirmSchema,
  emailVerificationSchema,
} from "../validation/auth.validation";
import { securityConfig } from "../config/auth.config";
import { createRateLimiter } from "../middleware/rateLimit.middleware";
import {
  sendVerificationEmail,
  confirmEmailVerification,
  requestPasswordReset,
  confirmPasswordReset,
} from "../controllers/auth.controller";

const router = Router();

/**
 * @swagger
 * tags:
 *   name: Auth
 *   description: Authentication endpoints
 */

/**
 * @swagger
 * /auth/register:
 *   post:
 *     tags: [Auth]
 *     summary: Register a new user
 *     description: Creates a new user account.
 *     requestBody:
 *       required: true
 *       content:
 *         application/json:
 *           schema:
 *             type: object
 *             required: [email, password]
 *             properties:
 *               email:
 *                 type: string
 *                 format: email
 *               password:
 *                 type: string
 *                 minLength: 8
 *               firstName:
 *                 type: string
 *               lastName:
 *                 type: string
 *               targetLanguage:
 *                 type: string
 *     responses:
 *       201:
 *         description: User registered successfully
 *       400:
 *         description: Validation error
 */

/**
 * @swagger
 * /auth/login:
 *   post:
 *     tags: [Auth]
 *     summary: Login with email and password
 *     requestBody:
 *       required: true
 *       content:
 *         application/json:
 *           schema:
 *             type: object
 *             required: [email, password]
 *             properties:
 *               email:
 *                 type: string
 *                 format: email
 *               password:
 *                 type: string
 *     responses:
 *       200:
 *         description: Login successful; returns tokens and user
 *       401:
 *         description: Invalid credentials
 */

/**
 * @swagger
 * /auth/refresh:
 *   post:
 *     tags: [Auth]
 *     summary: Refresh access token
 *     requestBody:
 *       required: true
 *       content:
 *         application/json:
 *           schema:
 *             type: object
 *             required: [refreshToken]
 *             properties:
 *               refreshToken:
 *                 type: string
 *     responses:
 *       200:
 *         description: New access token issued
 */

/**
 * @swagger
 * /auth/logout:
 *   post:
 *     tags: [Auth]
 *     summary: Logout and revoke refresh token
 *     requestBody:
 *       required: true
 *       content:
 *         application/json:
 *           schema:
 *             type: object
 *             required: [refreshToken]
 *             properties:
 *               refreshToken:
 *                 type: string
 *     responses:
 *       200:
 *         description: Logged out
 */

/**
 * @swagger
 * /auth/me:
 *   get:
 *     tags: [Auth]
 *     summary: Get current authenticated user
 *     security:
 *       - bearerAuth: []
 *     responses:
 *       200:
 *         description: Current user profile
 *       401:
 *         description: Unauthorized
 */

/**
 * @swagger
 * /auth/verify/send:
 *   post:
 *     tags: [Auth]
 *     summary: Send verification email
 *     security:
 *       - bearerAuth: []
 *     responses:
 *       200:
 *         description: Verification email sent
 */

/**
 * @swagger
 * /auth/verify/confirm:
 *   post:
 *     tags: [Auth]
 *     summary: Confirm email verification
 *     requestBody:
 *       required: true
 *       content:
 *         application/json:
 *           schema:
 *             type: object
 *             required: [token]
 *             properties:
 *               token:
 *                 type: string
 *     responses:
 *       200:
 *         description: Email verified
 *       400:
 *         description: Invalid or expired token
 */

/**
 * @swagger
 * /auth/password/reset/request:
 *   post:
 *     tags: [Auth]
 *     summary: Request a password reset
 *     requestBody:
 *       required: true
 *       content:
 *         application/json:
 *           schema:
 *             type: object
 *             required: [email]
 *             properties:
 *               email:
 *                 type: string
 *                 format: email
 *     responses:
 *       200:
 *         description: Password reset email sent
 */

/**
 * @swagger
 * /auth/password/reset/confirm:
 *   post:
 *     tags: [Auth]
 *     summary: Confirm password reset
 *     requestBody:
 *       required: true
 *       content:
 *         application/json:
 *           schema:
 *             type: object
 *             required: [token, newPassword]
 *             properties:
 *               token:
 *                 type: string
 *               newPassword:
 *                 type: string
 *                 minLength: 8
 *     responses:
 *       200:
 *         description: Password updated
 */

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
router.post("/register", validateBody(registerSchema), register);

// POST /api/auth/login - Login user
router.post("/login", loginLimiter, validateBody(loginSchema), login);

// POST /api/auth/refresh - Refresh access token
router.post(
  "/refresh",
  refreshLimiter,
  validateBody(refreshTokenSchema),
  refreshToken
);

// POST /api/auth/logout - Logout user (revoke refresh token)
router.post("/logout", validateBody(refreshTokenSchema), logout);

/**
 * Protected routes (authentication required)
 */

// GET /api/auth/me - Get current authenticated user
router.get("/me", authenticate, getCurrentUser);

/**
 * Email verification routes
 */
// Send verification email to current user
router.post("/verify/send", authenticate, sendVerificationEmail);
// Confirm email verification
router.post(
  "/verify/confirm",
  validateBody(emailVerificationSchema),
  confirmEmailVerification
);

/**
 * Password reset routes
 */
// Request password reset
router.post(
  "/password/reset/request",
  validateBody(passwordResetRequestSchema),
  requestPasswordReset
);
// Confirm password reset
router.post(
  "/password/reset/confirm",
  validateBody(passwordResetConfirmSchema),
  confirmPasswordReset
);

export default router;
