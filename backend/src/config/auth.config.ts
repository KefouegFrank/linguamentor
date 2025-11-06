/**
 * Authentication Configuration
 * Centralized configuration for JWT, bcrypt, and security settings
 */

import { config } from 'dotenv';

config();

/**
 * JWT Configuration
 */
export const jwtConfig = {
  // Access token settings (short-lived)
  accessToken: {
    secret: process.env.JWT_ACCESS_SECRET || 'your-super-secret-access-key-change-in-production',
    expiresIn: '15m', // 15 minutes
  },
  
  // Refresh token settings (long-lived)
  refreshToken: {
    secret: process.env.JWT_REFRESH_SECRET || 'your-super-secret-refresh-key-change-in-production',
    expiresIn: '7d', // 7 days
  },
  
  // Token issuer and audience
  issuer: process.env.JWT_ISSUER || 'lingumentor-api',
  audience: process.env.JWT_AUDIENCE || 'lingumentor-users',
};

/**
 * Bcrypt Configuration
 */
export const bcryptConfig = {
  // Number of salt rounds (10-12 is recommended for production)
  saltRounds: parseInt(process.env.BCRYPT_SALT_ROUNDS || '12', 10),
};

/**
 * Password Policy Configuration
 */
export const passwordPolicy = {
  minLength: 8,
  requireUppercase: true,
  requireLowercase: true,
  requireNumbers: true,
  requireSpecialChars: true,
};

/**
 * Account Security Configuration
 */
export const securityConfig = {
  // Maximum failed login attempts before account lockout
  maxLoginAttempts: 5,
  
  // Account lockout duration in minutes
  lockoutDuration: 15,
  
  // Basic route-level rate limiting (defaults; override via env if desired)
  rateLimit: {
    login: {
      windowMs: 15 * 60 * 1000, // 15 minutes
      max: 10,
    },
    refresh: {
      windowMs: 15 * 60 * 1000, // 15 minutes
      max: 60,
    },
  },
  
  // Email verification token expiry (24 hours)
  emailVerificationExpiry: 24 * 60 * 60 * 1000,
  
  // Password reset token expiry (1 hour)
  passwordResetExpiry: 60 * 60 * 1000,
  
  // Maximum number of active refresh tokens per user
  maxRefreshTokensPerUser: 5,
};

/**
 * OAuth Configuration (for future implementation)
 */
export const oauthConfig = {
  google: {
    clientId: process.env.GOOGLE_CLIENT_ID || '',
    clientSecret: process.env.GOOGLE_CLIENT_SECRET || '',
  },
  facebook: {
    clientId: process.env.FACEBOOK_CLIENT_ID || '',
    clientSecret: process.env.FACEBOOK_CLIENT_SECRET || '',
  },
  apple: {
    clientId: process.env.APPLE_CLIENT_ID || '',
    clientSecret: process.env.APPLE_CLIENT_SECRET || '',
  },
};

/**
 * CORS Configuration
 */
export const corsConfig = {
  origin: process.env.CORS_ORIGIN?.split(',') || ['http://localhost:4000'],
  credentials: true,
};