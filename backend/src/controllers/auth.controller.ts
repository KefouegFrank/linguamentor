/**
 * Authentication Controller
 * Handles HTTP requests for authentication endpoints
 */

import { Request, Response } from "express";
import { authService } from "../services/auth.service";
import { auditLogger } from "../utils/auditLogger";
import { verifyRefreshToken } from "../utils/auth.utils";

/**
 * Register a new user
 * POST /api/auth/register
 */
export const register = async (req: Request, res: Response): Promise<void> => {
  try {
    // Body already validated by middleware
    const result = await authService.register(req.body);

    // Return success response
    res.status(201).json({
      success: true,
      message: "User registered successfully",
      data: result,
    });

    // Audit log
    await auditLogger({
      action: "register",
      resource: "auth",
      userId: (result.user as any).id,
      ip: req.ip,
      userAgent: req.headers["user-agent"],
      metadata: { email: (result.user as any).email },
    });
  } catch (error) {
    // Handle business logic errors
    if (error instanceof Error) {
      // Check for specific error messages
      if (error.message.includes("already exists")) {
        res.status(409).json({
          success: false,
          message: error.message,
        });
        return;
      }

      if (error.message.includes("Password")) {
        res.status(400).json({
          success: false,
          message: error.message,
        });
        return;
      }
    }

    // Generic error
    console.error("Registration error:", error);
    res.status(500).json({
      success: false,
      message: "An error occurred during registration. Please try again.",
    });
  }
};

/**
 * Login user
 * POST /api/auth/login
 */
export const login = async (req: Request, res: Response): Promise<void> => {
  try {
    // Body already validated by middleware
    const result = await authService.login(req.body);

    // Return success response
    res.status(200).json({
      success: true,
      message: "Login successful",
      data: result,
    });

    // Audit log
    await auditLogger({
      action: "login",
      resource: "auth",
      userId: (result.user as any).id,
      ip: req.ip,
      userAgent: req.headers["user-agent"],
      metadata: { email: (result.user as any).email },
    });
  } catch (error) {
    // Handle business logic errors
    if (error instanceof Error) {
      // Don't reveal whether email or password is incorrect (security)
      if (error.message.includes("Invalid email or password")) {
        res.status(401).json({
          success: false,
          message: "Invalid email or password",
        });
        return;
      }

      if (error.message.includes("deactivated")) {
        res.status(403).json({
          success: false,
          message: error.message,
        });
        return;
      }
    }

    // Generic error
    console.error("Login error:", error);
    res.status(500).json({
      success: false,
      message: "An error occurred during login. Please try again.",
    });
  }
};

/**
 * Refresh access token
 * POST /api/auth/refresh
 */
export const refreshToken = async (
  req: Request,
  res: Response
): Promise<void> => {
  try {
    // Body already validated by middleware
    const result = await authService.refreshAccessToken(req.body.refreshToken);

    // Return success response
    res.status(200).json({
      success: true,
      message: "Token refreshed successfully",
      data: result,
    });

    // Audit log
    try {
      const payload = verifyRefreshToken(req.body.refreshToken);
      await auditLogger({
        action: "refresh_token",
        resource: "auth",
        userId: payload.userId,
        ip: req.ip,
        userAgent: req.headers["user-agent"],
      });
    } catch {
      // ignore audit logging errors
    }
  } catch (error) {
    // Handle business logic errors
    if (error instanceof Error) {
      if (
        error.message.includes("Invalid") ||
        error.message.includes("expired") ||
        error.message.includes("revoked")
      ) {
        res.status(401).json({
          success: false,
          message: "Invalid or expired refresh token",
        });
        return;
      }
    }

    // Generic error
    console.error("Token refresh error:", error);
    res.status(500).json({
      success: false,
      message: "An error occurred while refreshing token. Please try again.",
    });
  }
};

/**
 * Logout user (revoke refresh token)
 * POST /api/auth/logout
 */
export const logout = async (req: Request, res: Response): Promise<void> => {
  try {
    // Body already validated by middleware
    await authService.logout(req.body.refreshToken);

    // Return success response
    res.status(200).json({
      success: true,
      message: "Logged out successfully",
    });

    // Audit log
    try {
      const payload = verifyRefreshToken(req.body.refreshToken);
      await auditLogger({
        action: "logout",
        resource: "auth",
        userId: payload.userId,
        ip: req.ip,
        userAgent: req.headers["user-agent"],
      });
    } catch {
      // ignore audit logging errors
    }
  } catch (error) {
    // Even if logout fails, we return success (idempotent operation)
    console.error("Logout error:", error);
    res.status(200).json({
      success: true,
      message: "Logged out successfully",
    });
  }
};

// (logoutAll removed) - multi-device logout is not required at this time.

/**
 * Get current authenticated user profile
 * GET /api/auth/me
 * Requires authentication
 */
export const getCurrentUser = async (
  req: Request,
  res: Response
): Promise<void> => {
  try {
    // User ID is extracted from JWT by auth middleware
    const userId = req.user?.userId;

    if (!userId) {
      res.status(401).json({
        success: false,
        message: "Authentication required",
      });
      return;
    }

    // Get user data
    const user = await authService.getUserById(userId);

    // Return success response
    res.status(200).json({
      success: true,
      data: user,
    });
  } catch (error) {
    console.error("Get current user error:", error);
    res.status(500).json({
      success: false,
      message: "An error occurred while fetching user data. Please try again.",
    });
  }
};
