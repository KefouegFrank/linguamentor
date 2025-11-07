/**
 * Secure Token Service
 * Handles generation, storage, and validation of secure tokens for email verification and password reset
 */

import { PrismaClient } from '@prisma/client';
import crypto from 'crypto';
import { TokenType, TokenCreationResult, TokenValidationResult } from '../../types/auth.types';
import { AppError } from '../../utils/errors';
import { logger } from '../../utils/logger';

export class TokenService {
  private prisma: PrismaClient;
  private readonly TOKEN_EXPIRY_HOURS = {
    email_verification: 24, // 24 hours for email verification
    password_reset: 1, // 1 hour for password reset
  };

  constructor(prisma: PrismaClient) {
    this.prisma = prisma;
  }

  /**
   * Generate a cryptographically secure random token
   */
  private generateSecureToken(): string {
    // Generate 32 bytes of random data and convert to hex string
    return crypto.randomBytes(32).toString('hex');
  }

  /**
   * Create a new secure token for the specified type and user
   */
  async createToken(userId: string, tokenType: TokenType): Promise<TokenCreationResult> {
    try {
      const token = this.generateSecureToken();
      const expiresAt = new Date();
      expiresAt.setHours(expiresAt.getHours() + this.TOKEN_EXPIRY_HOURS[tokenType]);

      // Clean up any existing unused tokens for this user and type
      await this.cleanupExistingTokens(userId, tokenType);

      // Store the token based on type
      if (tokenType === 'email_verification') {
        await this.prisma.emailVerificationToken.create({
          data: {
            token,
            userId,
            expiresAt,
            used: false,
          },
        });
      } else if (tokenType === 'password_reset') {
        await this.prisma.passwordResetToken.create({
          data: {
            token,
            userId,
            expiresAt,
            used: false,
          },
        });
      }

      logger.info(`Created ${tokenType} token for user ${userId}`, {
        userId,
        tokenType,
        expiresAt,
      });

      return {
        token,
        expiresAt,
      };
    } catch (error) {
      logger.error(`Failed to create ${tokenType} token for user ${userId}:`, error);
      throw new AppError(`Failed to create ${tokenType} token`, 500);
    }
  }

  /**
   * Validate a token and return the associated user ID if valid
   */
  async validateToken(token: string, tokenType: TokenType): Promise<TokenValidationResult> {
    try {
      let tokenRecord;

      if (tokenType === 'email_verification') {
        tokenRecord = await this.prisma.emailVerificationToken.findUnique({
          where: { token },
          include: { user: true },
        });
      } else if (tokenType === 'password_reset') {
        tokenRecord = await this.prisma.passwordResetToken.findUnique({
          where: { token },
          include: { user: true },
        });
      }

      if (!tokenRecord) {
        return {
          isValid: false,
          error: 'Invalid token',
        };
      }

      // Check if token has been used
      if (tokenRecord.used) {
        return {
          isValid: false,
          error: 'Token has already been used',
        };
      }

      // Check if token has expired
      const now = new Date();
      if (tokenRecord.expiresAt < now) {
        return {
          isValid: false,
          error: 'Token has expired',
        };
      }

      // Check if user is active
      if (!tokenRecord.user.isActive) {
        return {
          isValid: false,
          error: 'User account is not active',
        };
      }

      return {
        isValid: true,
        userId: tokenRecord.userId,
      };
    } catch (error) {
      logger.error(`Failed to validate ${tokenType} token:`, error);
      return {
        isValid: false,
        error: 'Token validation failed',
      };
    }
  }

  /**
   * Mark a token as used after successful verification
   */
  async markTokenAsUsed(token: string, tokenType: TokenType): Promise<void> {
    try {
      if (tokenType === 'email_verification') {
        await this.prisma.emailVerificationToken.update({
          where: { token },
          data: { used: true },
        });
      } else if (tokenType === 'password_reset') {
        await this.prisma.passwordResetToken.update({
          where: { token },
          data: { used: true },
        });
      }

      logger.info(`Marked ${tokenType} token as used`, { token });
    } catch (error) {
      logger.error(`Failed to mark ${tokenType} token as used:`, error);
      throw new AppError(`Failed to mark token as used`, 500);
    }
  }

  /**
   * Clean up existing unused tokens for a user and token type
   */
  private async cleanupExistingTokens(userId: string, tokenType: TokenType): Promise<void> {
    try {
      if (tokenType === 'email_verification') {
        await this.prisma.emailVerificationToken.deleteMany({
          where: {
            userId,
            used: false,
          },
        });
      } else if (tokenType === 'password_reset') {
        await this.prisma.passwordResetToken.deleteMany({
          where: {
            userId,
            used: false,
          },
        });
      }

      logger.info(`Cleaned up existing ${tokenType} tokens for user ${userId}`);
    } catch (error) {
      logger.error(`Failed to cleanup existing ${tokenType} tokens:`, error);
      // Don't throw error here as this is a cleanup operation
    }
  }

  /**
   * Clean up expired tokens (can be used in a cron job)
   */
  async cleanupExpiredTokens(): Promise<void> {
    try {
      const now = new Date();

      // Clean up expired email verification tokens
      const deletedEmailTokens = await this.prisma.emailVerificationToken.deleteMany({
        where: {
          expiresAt: { lt: now },
        },
      });

      // Clean up expired password reset tokens
      const deletedPasswordTokens = await this.prisma.passwordResetToken.deleteMany({
        where: {
          expiresAt: { lt: now },
        },
      });

      logger.info('Cleaned up expired tokens', {
        deletedEmailTokens: deletedEmailTokens.count,
        deletedPasswordTokens: deletedPasswordTokens.count,
      });
    } catch (error) {
      logger.error('Failed to cleanup expired tokens:', error);
      throw new AppError('Failed to cleanup expired tokens', 500);
    }
  }
}