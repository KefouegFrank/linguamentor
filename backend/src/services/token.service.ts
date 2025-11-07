import crypto from "node:crypto";
import { PrismaClient } from "@prisma/client";
import { logger } from "../utils/logger";

export class TokenService {
  constructor(private prisma: PrismaClient) {}

  /**
   * Generate a cryptographically secure token
   */
  private generateSecureToken(): string {
    return crypto.randomBytes(32).toString("hex");
  }

  /**
   * Create a token for email verification or password reset
   */
  async createToken(
    userId: string,
    type: "email_verification" | "password_reset"
  ): Promise<{ token: string; expiresAt: Date }> {
    try {
      // Clean up any existing tokens of the same type for this user
      await this.cleanupExistingTokens(userId, type);

      // Generate a secure token
      const token = this.generateSecureToken();

      // Set expiration based on token type
      const expiresAt = new Date();
      if (type === "email_verification") {
        expiresAt.setHours(expiresAt.getHours() + 24); // 24 hours
      } else {
        expiresAt.setHours(expiresAt.getHours() + 1); // 1 hour for password reset
      }

      // Store token in database based on type
      if (type === "email_verification") {
        await this.prisma.emailVerificationToken.create({
          data: {
            token,
            userId,
            expiresAt,
            used: false,
            createdAt: new Date(),
          },
        });
      } else {
        await this.prisma.passwordResetToken.create({
          data: {
            token,
            userId,
            expiresAt,
            used: false,
            createdAt: new Date(),
          },
        });
      }

      logger.info(`Token created for user ${userId} of type ${type}`);

      return { token, expiresAt };
    } catch (error) {
      logger.error("Error creating token:", error);
      throw new Error("Failed to create token");
    }
  }

  /**
   * Validate a token
   */
  async validateToken(
    token: string,
    type: "email_verification" | "password_reset"
  ): Promise<{ isValid: boolean; userId?: string; error?: string }> {
    try {
      // Find the token in database based on type
      let tokenRecord;
      if (type === "email_verification") {
        tokenRecord = await this.prisma.emailVerificationToken.findUnique({
          where: { token },
        });
      } else {
        tokenRecord = await this.prisma.passwordResetToken.findUnique({
          where: { token },
        });
      }

      if (!tokenRecord) {
        return { isValid: false, error: "Invalid token" };
      }

      // Check if token has been used
      if (tokenRecord.used) {
        return { isValid: false, error: "Token has already been used" };
      }

      // Check if token has expired
      if (tokenRecord.expiresAt < new Date()) {
        return { isValid: false, error: "Token has expired" };
      }

      return { isValid: true, userId: tokenRecord.userId };
    } catch (error) {
      logger.error("Error validating token:", error);
      return { isValid: false, error: "Failed to validate token" };
    }
  }

  /**
   * Mark a token as used
   */
  async markTokenAsUsed(
    token: string,
    type: "email_verification" | "password_reset"
  ): Promise<void> {
    try {
      if (type === "email_verification") {
        await this.prisma.emailVerificationToken.update({
          where: { token },
          data: {
            used: true,
          },
        });
      } else {
        await this.prisma.passwordResetToken.update({
          where: { token },
          data: {
            used: true,
          },
        });
      }

      logger.info(`Token marked as used: ${token}`);
    } catch (error) {
      logger.error("Error marking token as used:", error);
      throw new Error("Failed to mark token as used");
    }
  }

  /**
   * Clean up existing tokens of the same type for a user
   */
  private async cleanupExistingTokens(
    userId: string,
    type: "email_verification" | "password_reset"
  ): Promise<void> {
    try {
      if (type === "email_verification") {
        await this.prisma.emailVerificationToken.deleteMany({
          where: {
            userId,
            used: false,
          },
        });
      } else {
        await this.prisma.passwordResetToken.deleteMany({
          where: {
            userId,
            used: false,
          },
        });
      }

      logger.info(`Cleaned up existing ${type} tokens for user ${userId}`);
    } catch (error) {
      logger.error("Error cleaning up existing tokens:", error);
      // Don't throw - this is a cleanup operation
    }
  }

  /**
   * Clean up expired tokens (can be used in a cron job)
   */
  async cleanupExpiredTokens(): Promise<void> {
    try {
      // Clean up expired email verification tokens
      const emailResult = await this.prisma.emailVerificationToken.deleteMany({
        where: {
          expiresAt: {
            lt: new Date(),
          },
        },
      });

      // Clean up expired password reset tokens
      const passwordResult = await this.prisma.passwordResetToken.deleteMany({
        where: {
          expiresAt: {
            lt: new Date(),
          },
        },
      });

      const totalDeleted = emailResult.count + passwordResult.count;
      logger.info(`Cleaned up ${totalDeleted} expired tokens`);
    } catch (error) {
      logger.error("Error cleaning up expired tokens:", error);
      throw new Error("Failed to clean up expired tokens");
    }
  }
}
