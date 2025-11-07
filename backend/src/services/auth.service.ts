/**
 * Authentication Service
 * Handles all authentication business logic including registration, login, and token management
 */

import { User } from "@prisma/client";
import {
  RegisterRequest,
  LoginRequest,
  AuthResponse,
  UserResponse,
  AccessTokenPayload,
  RefreshTokenPayload,
  TargetLanguage,
  ExamType,
} from "../types/auth.types";
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
  generateSecureToken,
} from "../utils/auth.utils";
import { securityConfig } from "../config/auth.config";
import { prisma } from "../prisma/client";
import crypto, { randomBytes } from "node:crypto";
import { emailService } from "./email.service";
import { TokenService } from "./token.service";
import { logger } from "../utils/logger";

/**
 * Authentication Service Class
 */
export class AuthService {
  private static failedLoginAttempts: Map<
    string,
    { count: number; until?: number }
  > = new Map();

  private tokenService: TokenService;

  constructor() {
    this.tokenService = new TokenService(prisma);
  }
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
      throw new Error("User with this email already exists");
    }

    // Hash password
    const passwordHash = await hashPassword(data.password);

    // Create user
    const user = await prisma.user.create({
      data: {
        email: data.email.toLowerCase(),
        passwordHash,
        firstName: data.firstName || null,
        lastName: data.lastName || null,
        targetLanguage: data.targetLanguage as TargetLanguage,
        nativeLanguage: data.nativeLanguage || null,
        targetExam: (data.targetExam as ExamType) || null,
        currentLevel: "A1", // Default starting level
        role: "LEARNER",
        readinessScore: 0,
        totalStudyTime: 0,
        currentStreak: 0,
        longestStreak: 0,
        isActive: true,
        emailVerified: false,
        subscriptionTier: "FREE",
        lastActiveAt: new Date(),
        createdAt: new Date(),
        updatedAt: new Date(),
      },
    });

    // Generate tokens
    const { accessToken, refreshToken } = await this.generateTokenPair(
      user.id,
      user.email,
      user.role
    );

    // Create email verification token
    try {
      const verificationToken = await this.tokenService.createToken(
        user.id,
        "email_verification"
      );

      // Send verification email
      await emailService.sendVerificationEmail(
        user.email,
        verificationToken.token,
        user.firstName || user.email
      );

      logger.info(`Email verification sent to user ${user.id}`);
    } catch (emailError) {
      logger.error("Failed to send verification email:", emailError);
      // Don't fail registration if email sending fails
      // User can request verification email later
    }

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
      throw new Error("Account is temporarily locked. Please try again later.");
    }

    // Find user by email
    const user = await prisma.user.findUnique({
      where: { email: emailKey },
    });

    if (!user) {
      // increment attempts on unknown email to prevent enumeration hints
      this.incrementFailedAttempt(emailKey);
      throw new Error("Invalid email or password");
    }

    // Check if account is active
    if (!user.isActive) {
      throw new Error("Account is deactivated. Please contact support.");
    }

    // Verify password
    const isPasswordValid = await comparePassword(
      data.password,
      user.passwordHash
    );

    if (!isPasswordValid) {
      this.incrementFailedAttempt(emailKey);
      throw new Error("Invalid email or password");
    }

    // Successful login: clear failed attempts
    AuthService.failedLoginAttempts.delete(emailKey);

    // Update last active timestamp
    await prisma.user.update({
      where: { id: user.id },
      data: { lastActiveAt: new Date() },
    });

    // Generate tokens
    const { accessToken, refreshToken } = await this.generateTokenPair(
      user.id,
      user.email,
      user.role
    );

    return {
      accessToken,
      refreshToken,
      user: sanitizeUser(user) as UserResponse,
    };
  }

  /**
   * Generate access and refresh tokens
   */
  async generateTokens(
    userId: string
  ): Promise<{ accessToken: string; refreshToken: string }> {
    try {
      const user = await prisma.user.findUnique({ where: { id: userId } });
      if (!user) {
        throw new Error("User not found");
      }
      const accessTokenPayload = {
        userId: user.id,
        email: user.email,
        role: user.role,
      };
      const tokenId = randomBytes(16).toString("hex");
      const refreshTokenPayload = { userId: user.id, tokenId };
      const accessToken = generateAccessToken(accessTokenPayload);
      const refreshToken = await generateRefreshToken(refreshTokenPayload);
      return { accessToken, refreshToken };
    } catch (error) {
      console.error("Token generation error:", error);
      throw new Error("Failed to generate tokens");
    }
  }

  /**
   * Refresh access token using refresh token
   * @param refreshToken - Valid refresh token
   * @returns New token pair
   */
  async refreshAccessToken(
    refreshToken: string
  ): Promise<{ accessToken: string; refreshToken: string }> {
    // Verify and decode refresh token
    let payload: RefreshTokenPayload;
    try {
      payload = verifyRefreshToken(refreshToken);
    } catch (error) {
      throw new Error("Invalid or expired refresh token");
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
      throw new Error("Refresh token not found or has been revoked");
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
   * Request password reset
   */
  async requestPasswordReset(email: string): Promise<{ resetToken?: string }> {
    try {
      // Find user by email
      const user = await prisma.user.findUnique({
        where: { email: email.toLowerCase() },
      });

      if (!user) {
        // Don't reveal if user exists for security
        return {};
      }

      // Create password reset token
      const resetTokenData = await this.tokenService.createToken(
        user.id,
        "password_reset"
      );

      // Send password reset email
      try {
        await emailService.sendPasswordResetEmail(
          user.email,
          resetTokenData.token,
          user.firstName || user.email
        );

        logger.info(`Password reset email sent to user ${user.id}`);
      } catch (emailError) {
        logger.error("Failed to send password reset email:", emailError);
        throw new Error("Failed to send password reset email");
      }

      return {
        resetToken: resetTokenData.token,
      };
    } catch (error) {
      logger.error("Password reset request error:", error);
      throw new Error("Failed to process password reset request");
    }
  }

  /**
   * Reset password with token
   */
  async resetPassword(token: string, newPassword: string): Promise<void> {
    try {
      // Validate password strength
      const passwordValidation = validatePassword(newPassword);
      if (!passwordValidation.isValid) {
        throw new Error(passwordValidation.error);
      }

      // Validate the reset token
      const validationResult = await this.tokenService.validateToken(
        token,
        "password_reset"
      );
      if (!validationResult.isValid) {
        throw new Error(
          validationResult.error || "Invalid or expired reset token"
        );
      }

      const userId = validationResult.userId!;

      // Get user to check current password
      const user = await prisma.user.findUnique({
        where: { id: userId },
      });

      if (!user) {
        throw new Error("User not found");
      }

      // Check if new password is different from current
      const isSamePassword = await comparePassword(
        newPassword,
        user.passwordHash
      );
      if (isSamePassword) {
        throw new Error("New password must be different from current password");
      }

      // Hash new password
      const hashedPassword = await hashPassword(newPassword);

      // Update user password
      await prisma.user.update({
        where: { id: userId },
        data: {
          passwordHash: hashedPassword,
        },
      });

      // Mark token as used
      await this.tokenService.markTokenAsUsed(token, "password_reset");

      // Invalidate all existing refresh tokens for security
      await prisma.refreshToken.updateMany({
        where: { userId },
        data: { revoked: true },
      });

      logger.info(`Password reset completed for user ${userId}`);
    } catch (error) {
      logger.error("Password reset error:", error);
      throw error; // Re-throw to preserve specific error messages
    }
  }

  /**
   * Verify email with token
   */
  async verifyEmail(token: string): Promise<void> {
    try {
      // Validate the verification token
      const validationResult = await this.tokenService.validateToken(
        token,
        "email_verification"
      );
      if (!validationResult.isValid) {
        throw new Error(
          validationResult.error || "Invalid or expired verification token"
        );
      }

      const userId = validationResult.userId!;

      // Update user's email verification status
      await prisma.user.update({
        where: { id: userId },
        data: {
          emailVerified: true,
        },
      });

      // Mark token as used
      await this.tokenService.markTokenAsUsed(token, "email_verification");

      logger.info(`Email verification completed for user ${userId}`);
    } catch (error) {
      logger.error("Email verification error:", error);
      throw error; // Re-throw to preserve specific error messages
    }
  }

  /**
   * Resend email verification
   */
  async resendVerificationEmail(
    userId: string
  ): Promise<{ verificationToken: string }> {
    try {
      // Get user information
      const user = await prisma.user.findUnique({
        where: { id: userId },
      });

      if (!user) {
        throw new Error("User not found");
      }

      // Check if email is already verified
      if (user.emailVerified) {
        throw new Error("Email is already verified");
      }

      // Create new email verification token
      const verificationToken = await this.tokenService.createToken(
        userId,
        "email_verification"
      );

      // Send verification email
      try {
        await emailService.sendVerificationEmail(
          user.email,
          verificationToken.token,
          user.firstName || user.email
        );

        logger.info(`Verification email resent to user ${userId}`);
      } catch (emailError) {
        logger.error("Failed to send verification email:", emailError);
        throw new Error("Failed to send verification email");
      }

      return { verificationToken: verificationToken.token };
    } catch (error) {
      logger.error("Resend verification email error:", error);
      throw error; // Re-throw to preserve specific error messages
    }
  }

  /**
   * Change password for authenticated user
   */
  async changePassword(
    userId: string,
    currentPassword: string,
    newPassword: string
  ): Promise<void> {
    try {
      // Get user with password
      const user = await prisma.user.findUnique({
        where: { id: userId },
      });

      if (!user) {
        throw new Error("User not found");
      }

      // Verify current password
      const isCurrentPasswordValid = await comparePassword(
        currentPassword,
        user.passwordHash
      );
      if (!isCurrentPasswordValid) {
        throw new Error("Current password is incorrect");
      }

      // Check if new password is different from current
      const isSamePassword = await comparePassword(
        newPassword,
        user.passwordHash
      );
      if (isSamePassword) {
        throw new Error("New password must be different from current password");
      }

      // Hash new password
      const hashedPassword = await hashPassword(newPassword);

      // Update user password
      await prisma.user.update({
        where: { id: userId },
        data: {
          passwordHash: hashedPassword,
        },
      });

      // Invalidate all existing refresh tokens for security
      await prisma.refreshToken.updateMany({
        where: { userId },
        data: { revoked: true },
      });
    } catch (error) {
      console.error("Change password error:", error);
      throw error; // Re-throw to preserve specific error messages
    }
  }

  /**
   * Update user profile
   */
  async updateProfile(
    userId: string,
    profileData: {
      firstName?: string;
      lastName?: string;
      targetLanguage?: string;
      nativeLanguage?: string;
      targetExam?: string;
      currentLevel?: string;
    }
  ): Promise<UserResponse> {
    try {
      // Update user profile
      const updatedUser = await prisma.user.update({
        where: { id: userId },
        data: {
          firstName: profileData.firstName,
          lastName: profileData.lastName,
          targetLanguage: profileData.targetLanguage as any,
          nativeLanguage: profileData.nativeLanguage,
          targetExam: profileData.targetExam as any,
          currentLevel: profileData.currentLevel as any,
          updatedAt: new Date(),
        },
      });

      return sanitizeUser(updatedUser) as UserResponse;
    } catch (error) {
      console.error("Update profile error:", error);
      throw error; // Re-throw to preserve specific error messages
    }
  }

  /**
   * Delete user account
   */
  async deleteAccount(userId: string, password: string): Promise<void> {
    try {
      // Get user with password
      const user = await prisma.user.findUnique({
        where: { id: userId },
      });

      if (!user) {
        throw new Error("User not found");
      }

      // Verify password before deletion
      const isPasswordValid = await comparePassword(
        password,
        user.passwordHash
      );
      if (!isPasswordValid) {
        throw new Error("Invalid password");
      }

      // Delete user (cascade will handle related data)
      await prisma.user.delete({
        where: { id: userId },
      });
    } catch (error) {
      console.error("Delete account error:", error);
      throw error; // Re-throw to preserve specific error messages
    }
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
      throw new Error("User not found");
    }

    return sanitizeUser(user) as UserResponse;
  }

  /**
   * Get user by email (internal use)
   */
  async getUserByEmail(email: string): Promise<User | null> {
    try {
      return await prisma.user.findUnique({
        where: { email: email.toLowerCase() },
      });
    } catch (error) {
      console.error("Get user by email error:", error);
      return null;
    }
  }

  /**
   * Get user by ID (internal use)
   */
  async getUserByIdInternal(userId: string): Promise<User | null> {
    try {
      return await prisma.user.findUnique({
        where: { id: userId },
      });
    } catch (error) {
      console.error("Get user by ID error:", error);
      return null;
    }
  }

  /**
   * Create OAuth user
   */
  async createOAuthUser(userData: {
    email: string;
    firstName?: string;
    lastName?: string;
    avatar?: string;
    provider: string;
    providerId: string;
  }): Promise<User> {
    try {
      const { email, firstName, lastName, avatar, provider, providerId } =
        userData;

      // Create user with OAuth info
      const user = await prisma.user.create({
        data: {
          email: email.toLowerCase(),
          passwordHash: "", // OAuth users don't have passwords
          firstName: firstName || null,
          lastName: lastName || null,
          targetLanguage: "ENGLISH", // Default target language
          role: "LEARNER",
          readinessScore: 0,
          totalStudyTime: 0,
          currentStreak: 0,
          longestStreak: 0,
          isActive: true,
          emailVerified: true, // OAuth providers verify email
          subscriptionTier: "FREE",
          oauthProvider: provider,
          oauthId: providerId,
          lastActiveAt: new Date(),
          createdAt: new Date(),
          updatedAt: new Date(),
        },
      });

      return sanitizeUser(user);
    } catch (error) {
      console.error("Create OAuth user error:", error);
      throw error;
    }
  }

  /**
   * Update OAuth info for existing user
   */
  async updateOAuthInfo(
    userId: string,
    oauthData: {
      provider: string;
      providerId: string;
      avatar?: string;
    }
  ): Promise<User> {
    try {
      const { provider, providerId } = oauthData;

      const user = await prisma.user.update({
        where: { id: userId },
        data: {
          oauthProvider: provider,
          oauthId: providerId,
          emailVerified: true,
        },
      });

      return sanitizeUser(user);
    } catch (error) {
      console.error("Update OAuth info error:", error);
      throw error;
    }
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
        createdAt: "desc",
      },
    });

    // If user has too many tokens, revoke the oldest ones
    if (tokens.length > securityConfig.maxRefreshTokensPerUser) {
      const tokensToRevoke = tokens.slice(
        securityConfig.maxRefreshTokensPerUser
      );
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
    const current = AuthService.failedLoginAttempts.get(emailKey) ?? {
      count: 0,
    };
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
