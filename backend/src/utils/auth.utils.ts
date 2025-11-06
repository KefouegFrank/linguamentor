/**
 * Authentication Utility Functions
 * Provides password hashing, JWT generation/verification, and token management
 * Security note: bcrypt with default salt rounds is acceptable for auth.
 * Adjust rounds if needed; keep balance between security and performance.
 */

import bcrypt from 'bcrypt';
import jwt, { type Secret, type SignOptions } from 'jsonwebtoken';
import crypto from 'node:crypto';
import { jwtConfig, bcryptConfig, passwordPolicy } from '../config/auth.config';
import { AccessTokenPayload, RefreshTokenPayload } from '../types/auth.types';

/**
 * Hash a plain text password using bcrypt
 * @param password - Plain text password
 * @returns Hashed password
 */
export const hashPassword = async (password: string): Promise<string> => {
    return bcrypt.hash(password, bcryptConfig.saltRounds);
};

/**
 * Compare plain text password with hashed password
 * @param password - Plain text password
 * @param hash - Hashed password from database
 * @returns True if passwords match, false otherwise
 */
export const comparePassword = async (
    password: string,
    hash: string
): Promise<boolean> => {
    return bcrypt.compare(password, hash);
};

/**
 * Validate password against security policy
 * @param password - Password to validate
 * @returns Object with validation result and error message
 */
export const validatePassword = (
    password: string
): { isValid: boolean; error?: string } => {
    if (password.length < passwordPolicy.minLength) {
        return {
            isValid: false,
            error: `Password must be at least ${passwordPolicy.minLength} characters long`,
        };
    }

    if (passwordPolicy.requireUppercase && !/[A-Z]/.test(password)) {
        return {
            isValid: false,
            error: 'Password must contain at least one uppercase letter',
        };
    }

    if (passwordPolicy.requireLowercase && !/[a-z]/.test(password)) {
        return {
            isValid: false,
            error: 'Password must contain at least one lowercase letter',
        };
    }

    if (passwordPolicy.requireNumbers && !/\d/.test(password)) {
        return {
            isValid: false,
            error: 'Password must contain at least one number',
        };
    }

    if (passwordPolicy.requireSpecialChars && !/[!@#$%^&*(),.?":{}|<>]/.test(password)) {
        return {
            isValid: false,
            error: 'Password must contain at least one special character',
        };
    }

    return { isValid: true };
};

/**
 * Generate JWT access token
 * @param payload - Token payload containing user data
 * @returns Signed JWT access token
 */
export const generateAccessToken = (payload: AccessTokenPayload): string => {
    const options: SignOptions = {
        expiresIn: jwtConfig.accessToken.expiresIn as any,
        issuer: jwtConfig.issuer,
        audience: jwtConfig.audience,
    };
    return jwt.sign(payload as object, jwtConfig.accessToken.secret as unknown as Secret, options);
};

/**
 * Generate JWT refresh token
 * @param payload - Token payload containing user ID and token ID
 * @returns Signed JWT refresh token
 */
export const generateRefreshToken = (payload: RefreshTokenPayload): string => {
    const options: SignOptions = {
        expiresIn: jwtConfig.refreshToken.expiresIn as any,
        issuer: jwtConfig.issuer,
        audience: jwtConfig.audience,
    };
    return jwt.sign(payload as object, jwtConfig.refreshToken.secret as unknown as Secret, options);
};

/**
 * Verify and decode JWT access token
 * @param token - JWT access token
 * @returns Decoded token payload
 * @throws Error if token is invalid or expired
 */
export const verifyAccessToken = (token: string): AccessTokenPayload => {
    try {
        return jwt.verify(token, jwtConfig.accessToken.secret, {
            issuer: jwtConfig.issuer,
            audience: jwtConfig.audience,
        }) as AccessTokenPayload;
    } catch (error) {
        if (error instanceof jwt.TokenExpiredError) {
            throw new Error('Access token has expired');
        }
        if (error instanceof jwt.JsonWebTokenError) {
            throw new Error('Invalid access token');
        }
        throw new Error('Token verification failed');
    }
};

/**
 * Verify and decode JWT refresh token
 * @param token - JWT refresh token
 * @returns Decoded token payload
 * @throws Error if token is invalid or expired
 */
export const verifyRefreshToken = (token: string): RefreshTokenPayload => {
    try {
        return jwt.verify(token, jwtConfig.refreshToken.secret, {
            issuer: jwtConfig.issuer,
            audience: jwtConfig.audience,
        }) as RefreshTokenPayload;
    } catch (error) {
        if (error instanceof jwt.TokenExpiredError) {
            throw new Error('Refresh token has expired');
        }
        if (error instanceof jwt.JsonWebTokenError) {
            throw new Error('Invalid refresh token');
        }
        throw new Error('Token verification failed');
    }
};

/**
 * Generate a secure random token for email verification or password reset
 * @returns 32-byte random hex string
 */
export const generateSecureToken = (): string => {
    return crypto.randomBytes(32).toString('hex');
};

/**
 * Hash a refresh token using SHA-256 for storage
 * @param token - Plain refresh token
 * @returns SHA-256 hash of the token
 */
export const hashRefreshToken = (token: string): string => {
    return crypto.createHash('sha256').update(token).digest('hex');
};

/**
 * Calculate expiration date for refresh token
 * @returns Date object representing token expiration
 */
export const getRefreshTokenExpiry = (): Date => {
    // Parse the expiresIn string (e.g., '7d' -> 7 days)
    const expiresIn = jwtConfig.refreshToken.expiresIn;
    const match = expiresIn.match(/^(\d+)([smhd])$/);

    if (!match) {
        throw new Error('Invalid refresh token expiry format');
    }

    const value = parseInt(match[1], 10);
    const unit = match[2];

    const now = new Date();

    switch (unit) {
        case 's':
            return new Date(now.getTime() + value * 1000);
        case 'm':
            return new Date(now.getTime() + value * 60 * 1000);
        case 'h':
            return new Date(now.getTime() + value * 60 * 60 * 1000);
        case 'd':
            return new Date(now.getTime() + value * 24 * 60 * 60 * 1000);
        default:
            throw new Error('Invalid time unit');
    }
};

/**
 * Sanitize user object for API responses (remove sensitive fields)
 * @param user - User object from database
 * @returns Sanitized user object
 */
export const sanitizeUser = (user: any): any => {
    const { passwordHash, ...sanitized } = user;
    return sanitized;
};