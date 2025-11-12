/**
 * Authentication Service
 * Handles all authentication business logic including registration, login, and token management
 */

import {
    RegisterRequest,
    LoginRequest,
    AuthResponse,
    UserResponse,
    AccessTokenPayload,
    RefreshTokenPayload,
} from '../types/auth.types';
import {
    hashPassword,
    comparePassword,
    validatePassword,
    generateAccessToken,
    generateRefreshToken,
    verifyRefreshToken,
    hashRefreshToken,
    getRefreshTokenExpiry,
    sanitizeUser,
} from '../utils/auth.utils';
import { securityConfig } from '../config/auth.config';
import { prisma } from '../prisma/client';
import crypto from 'node:crypto';


/**
 * Authentication Service Class
 */
export class AuthService {
    private static failedLoginAttempts: Map<string, { count: number; until?: number }> = new Map();
    /**
     * Register a new user
     * @param data - User registration data
     * @returns Authentication response with tokens and user data
     */
    async register(data: RegisterRequest): Promise<AuthResponse> {
        // Validate password strength
        const passwordValidation = validatePassword(data.password);
        if (!passwordValidation.isValid) {
            throw new Error(passwordValidation.error);
        }

        // Check if user already exists
        const existingUser = await prisma.user.findUnique({
            where: { email: data.email.toLowerCase() },
        });

        if (existingUser) {
            throw new Error('User with this email already exists');
        }

        // Hash password
        const passwordHash = await hashPassword(data.password);

        // Create user
        const user = await prisma.user.create({
            data: {
                email: data.email.toLowerCase(),
                passwordHash,
                firstName: data.firstName,
                lastName: data.lastName,
                targetLanguage: data.targetLanguage,
                nativeLanguage: data.nativeLanguage,
                targetExam: data.targetExam,
                currentLevel: 'A1', // Default starting level
                lastActiveAt: new Date(),
            },
        });

        // Generate tokens
        const { accessToken, refreshToken } = await this.generateTokenPair(user.id, user.email, user.role);

        return {
            accessToken,
            refreshToken,
            user: sanitizeUser(user) as UserResponse,
        };
    }

    /**
     * Authenticate user and generate tokens
     * @param data - Login credentials
     * @returns Authentication response with tokens and user data
     */
    async login(data: LoginRequest): Promise<AuthResponse> {
        const emailKey = data.email.toLowerCase();

        // Check lockout state (in-memory scaffolding)
        const lock = AuthService.failedLoginAttempts.get(emailKey);
        if (lock?.until && lock.until > Date.now()) {
            throw new Error('Account is temporarily locked. Please try again later.');
        }

        // Find user by email
        const user = await prisma.user.findUnique({
            where: { email: emailKey },
        });

        if (!user) {
            // increment attempts on unknown email to prevent enumeration hints
            this.incrementFailedAttempt(emailKey);
            throw new Error('Invalid email or password');
        }

        // Check if account is active
        if (!user.isActive) {
            throw new Error('Account is deactivated. Please contact support.');
        }

        // Verify password
        const isPasswordValid = await comparePassword(data.password, user.passwordHash);

        if (!isPasswordValid) {
            this.incrementFailedAttempt(emailKey);
            throw new Error('Invalid email or password');
        }

        // Successful login: clear failed attempts
        AuthService.failedLoginAttempts.delete(emailKey);

        // Update last active timestamp
        await prisma.user.update({
            where: { id: user.id },
            data: { lastActiveAt: new Date() },
        });

        // Generate tokens
        const { accessToken, refreshToken } = await this.generateTokenPair(user.id, user.email, user.role);

        return {
            accessToken,
            refreshToken,
            user: sanitizeUser(user) as UserResponse,
        };
    }

    /**
     * Refresh access token using refresh token
     * @param refreshToken - Valid refresh token
     * @returns New token pair
     */
    async refreshAccessToken(refreshToken: string): Promise<{ accessToken: string; refreshToken: string }> {
        // Verify and decode refresh token
        let payload: RefreshTokenPayload;
        try {
            payload = verifyRefreshToken(refreshToken);
        } catch (error) {
            throw new Error('Invalid or expired refresh token');
        }

        // Hash the token to look it up in database
        const tokenHash = hashRefreshToken(refreshToken);

        // Find refresh token in database
        const storedToken = await prisma.refreshToken.findFirst({
            where: {
                tokenHash,
                userId: payload.userId,
                revoked: false,
                expiresAt: {
                    gt: new Date(), // Token must not be expired
                },
            },
            include: {
                user: true,
            },
        });

        if (!storedToken) {
            throw new Error('Refresh token not found or has been revoked');
        }

        // Revoke the old refresh token (token rotation)
        await prisma.refreshToken.update({
            where: { id: storedToken.id },
            data: { revoked: true },
        });

        // Generate new token pair
        const newTokens = await this.generateTokenPair(
            storedToken.user.id,
            storedToken.user.email,
            storedToken.user.role
        );

        // Update the replaced_by_id field for audit trail
        await prisma.refreshToken.update({
            where: { id: storedToken.id },
            data: { replacedById: hashRefreshToken(newTokens.refreshToken) }, // Link to new token hash
        });

        return newTokens;
    }

    /**
     * Logout user by revoking refresh token
     * @param refreshToken - Refresh token to revoke
     */
    async logout(refreshToken: string): Promise<void> {
        const tokenHash = hashRefreshToken(refreshToken);

        await prisma.refreshToken.updateMany({
            where: {
                tokenHash,
                revoked: false,
            },
            data: {
                revoked: true,
            },
        });
    }

    /**
     * Logout user from all devices by revoking all refresh tokens
     * @param userId - User ID
     */
    async logoutAllDevices(userId: string): Promise<void> {
        await prisma.refreshToken.updateMany({
            where: {
                userId,
                revoked: false,
            },
            data: {
                revoked: true,
            },
        });
    }

    /**
     * Get user by ID
     * @param userId - User ID
     * @returns User data without sensitive fields
     */
    async getUserById(userId: string): Promise<UserResponse> {
        const user = await prisma.user.findUnique({
            where: { id: userId },
        });

        if (!user) {
            throw new Error('User not found');
        }

        return sanitizeUser(user) as UserResponse;
    }

    /**
     * Generate access and refresh token pair
     * @param userId - User ID
     * @param email - User email
     * @param role - User role
     * @returns Token pair
     * @private
     */
    private async generateTokenPair(
        userId: string,
        email: string,
        role: string
    ): Promise<{ accessToken: string; refreshToken: string }> {
        // Generate access token
        const accessTokenPayload: AccessTokenPayload = {
            userId,
            email,
            role: role as any,
        };
        const accessToken = generateAccessToken(accessTokenPayload);

        // Generate refresh token with unique ID
        const tokenId = crypto.randomUUID();
        const refreshTokenPayload: RefreshTokenPayload = {
            userId,
            tokenId,
        };
        const refreshToken = generateRefreshToken(refreshTokenPayload);

        // Store refresh token in database (hashed)
        const tokenHash = hashRefreshToken(refreshToken);
        const expiresAt = getRefreshTokenExpiry();

        // Clean up old tokens if user has too many
        await this.cleanupOldTokens(userId);

        // Store new refresh token
        await prisma.refreshToken.create({
            data: {
                tokenHash,
                userId,
                expiresAt,
            },
        });

        return { accessToken, refreshToken };
    }

    /**
     * Clean up old refresh tokens for a user (keep only the most recent N tokens)
     * @param userId - User ID
     * @private
     */
    private async cleanupOldTokens(userId: string): Promise<void> {
        // Get all non-revoked tokens for user
        const tokens = await prisma.refreshToken.findMany({
            where: {
                userId,
                revoked: false,
                expiresAt: {
                    gt: new Date(),
                },
            },
            orderBy: {
                createdAt: 'desc',
            },
        });

        // If user has too many tokens, revoke the oldest ones
        if (tokens.length > securityConfig.maxRefreshTokensPerUser) {
            const tokensToRevoke = tokens.slice(securityConfig.maxRefreshTokensPerUser);
            const tokenIdsToRevoke = tokensToRevoke.map((t: any) => t.id);

            await prisma.refreshToken.updateMany({
                where: {
                    id: {
                        in: tokenIdsToRevoke,
                    },
                },
                data: {
                    revoked: true,
                },
            });
        }
    }

    /**
     * Clean up expired refresh tokens (run periodically via cron job)
     */
    async cleanupExpiredTokens(): Promise<number> {
        const result = await prisma.refreshToken.deleteMany({
            where: {
                OR: [
                    {
                        expiresAt: {
                            lt: new Date(),
                        },
                    },
                    {
                        revoked: true,
                        createdAt: {
                            lt: new Date(Date.now() - 30 * 24 * 60 * 60 * 1000), // 30 days old
                        },
                    },
                ],
            },
        });

        return result.count;
    }

    private incrementFailedAttempt(emailKey: string): void {
        const current = AuthService.failedLoginAttempts.get(emailKey) ?? { count: 0 };
        const nextCount = current.count + 1;
        const next: { count: number; until?: number } = { count: nextCount };
        if (nextCount >= securityConfig.maxLoginAttempts) {
            next.until = Date.now() + securityConfig.lockoutDuration * 60 * 1000;
        }
        AuthService.failedLoginAttempts.set(emailKey, next);
    }
}

// Export singleton instance
export const authService = new AuthService();