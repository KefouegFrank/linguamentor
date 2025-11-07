/**
 * Authentication Controller
 * Handles HTTP requests for authentication endpoints
 */

import { Request, Response } from 'express';
import { authService } from '../services/auth.service';
import { emailService } from '../services/email.service';

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
      message: 'User registered successfully',
      data: result,
    });
  } catch (error) {
    // Handle business logic errors
    if (error instanceof Error) {
      // Check for specific error messages
      if (error.message.includes('already exists')) {
        res.status(409).json({
          success: false,
          message: error.message,
        });
        return;
      }

      if (error.message.includes('Password')) {
        res.status(400).json({
          success: false,
          message: error.message,
        });
        return;
      }
    }

    // Generic error
    console.error('Registration error:', error);
    res.status(500).json({
      success: false,
      message: 'An error occurred during registration. Please try again.',
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
      message: 'Login successful',
      data: result,
    });
  } catch (error) {
    // Handle business logic errors
    if (error instanceof Error) {
      // Don't reveal whether email or password is incorrect (security)
      if (error.message.includes('Invalid email or password')) {
        res.status(401).json({
          success: false,
          message: 'Invalid email or password',
        });
        return;
      }

      if (error.message.includes('deactivated')) {
        res.status(403).json({
          success: false,
          message: error.message,
        });
        return;
      }
    }

    // Generic error
    console.error('Login error:', error);
    res.status(500).json({
      success: false,
      message: 'An error occurred during login. Please try again.',
    });
  }
};

/**
 * Refresh access token
 * POST /api/auth/refresh
 */
export const refreshToken = async (req: Request, res: Response): Promise<void> => {
  try {
    // Body already validated by middleware
    const result = await authService.refreshAccessToken(req.body.refreshToken);

    // Return success response
    res.status(200).json({
      success: true,
      message: 'Token refreshed successfully',
      data: result,
    });
  } catch (error) {
    // Handle business logic errors
    if (error instanceof Error) {
      if (
        error.message.includes('Invalid') ||
        error.message.includes('expired') ||
        error.message.includes('revoked')
      ) {
        res.status(401).json({
          success: false,
          message: 'Invalid or expired refresh token',
        });
        return;
      }
    }

    // Generic error
    console.error('Token refresh error:', error);
    res.status(500).json({
      success: false,
      message: 'An error occurred while refreshing token. Please try again.',
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
      message: 'Logged out successfully',
    });
  } catch (error) {
    // Even if logout fails, we return success (idempotent operation)
    console.error('Logout error:', error);
    res.status(200).json({
      success: true,
      message: 'Logged out successfully',
    });
  }
};

// (logoutAll removed) - multi-device logout is not required at this time.

/**
 * Get current authenticated user profile
 * GET /api/auth/me
 * Requires authentication
 */
export const getCurrentUser = async (req: Request, res: Response): Promise<void> => {
  try {
    // User ID is extracted from JWT by auth middleware
    const userId = req.user?.userId;

    if (!userId) {
      res.status(401).json({
        success: false,
        message: 'Authentication required',
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
    console.error('Get current user error:', error);
    res.status(500).json({
      success: false,
      message: 'An error occurred while fetching user data. Please try again.',
    });
  }
};

/**
 * Request password reset
 */
export const requestPasswordReset = async (req: Request, res: Response): Promise<void> => {
  try {
    const { email } = req.body;
    
    // Request password reset
    const { resetToken } = await authService.requestPasswordReset(email);
    
    // If user exists, send reset email (but don't reveal if user exists)
    if (resetToken) {
      try {
        // Get user details for email
        const user = await authService.getUserByEmail(email);
        if (user) {
          await emailService.sendPasswordResetEmail(
            email,
            resetToken,
            user.firstName || user.email
          );
        }
      } catch (emailError) {
        console.error('Failed to send password reset email:', emailError);
        // Continue even if email fails - don't reveal user existence
      }
    }
    
    // Always return success to prevent user enumeration
    res.status(200).json({
      success: true,
      message: 'If an account with that email exists, a password reset link has been sent.',
    });
  } catch (error) {
    console.error('Password reset request error:', error);
    res.status(500).json({
      success: false,
      message: 'Failed to process password reset request',
    });
  }
};

/**
 * Reset password with token
 */
export const resetPassword = async (req: Request, res: Response): Promise<void> => {
  try {
    const { token, newPassword } = req.body;
    
    await authService.resetPassword(token, newPassword);
    
    res.status(200).json({
      success: true,
      message: 'Password has been reset successfully',
    });
  } catch (error: any) {
    console.error('Password reset error:', error);
    res.status(400).json({
      success: false,
      message: error.message || 'Failed to reset password',
    });
  }
};

/**
 * Verify email with token
 */
export const verifyEmail = async (req: Request, res: Response): Promise<void> => {
  try {
    const { token } = req.body;
    
    await authService.verifyEmail(token);
    
    res.status(200).json({
      success: true,
      message: 'Email has been verified successfully',
    });
  } catch (error: any) {
    console.error('Email verification error:', error);
    res.status(400).json({
      success: false,
      message: error.message || 'Failed to verify email',
    });
  }
};

/**
 * Resend email verification
 */
export const resendVerificationEmail = async (req: Request, res: Response): Promise<void> => {
  try {
    const userId = req.user!.userId;
    
    const { verificationToken } = await authService.resendVerificationEmail(userId);
    
    // Send verification email
    try {
      const user = await authService.getUserById(userId);
      await emailService.sendVerificationEmail(
        user.email,
        verificationToken,
        user.firstName || user.email
      );
    } catch (emailError) {
      console.error('Failed to send verification email:', emailError);
      res.status(500).json({
        success: false,
        message: 'Failed to send verification email',
      });
      return;
    }
    
    res.status(200).json({
      success: true,
      message: 'Verification email has been sent',
    });
  } catch (error: any) {
    console.error('Resend verification email error:', error);
    res.status(400).json({
      success: false,
      message: error.message || 'Failed to resend verification email',
    });
  }
};

/**
 * Change password for authenticated user
 */
export const changePassword = async (req: Request, res: Response): Promise<void> => {
  try {
    const userId = req.user!.userId;
    const { currentPassword, newPassword } = req.body;
    
    await authService.changePassword(userId, currentPassword, newPassword);
    
    res.status(200).json({
      success: true,
      message: 'Password has been changed successfully',
    });
  } catch (error: any) {
    console.error('Change password error:', error);
    res.status(400).json({
      success: false,
      message: error.message || 'Failed to change password',
    });
  }
};

/**
 * Update user profile
 */
export const updateProfile = async (req: Request, res: Response): Promise<void> => {
  try {
    const userId = req.user!.userId;
    const { firstName, lastName, targetLanguage, nativeLanguage, targetExam, currentLevel } = req.body;
    
    const updatedUser = await authService.updateProfile(userId, {
       firstName,
  lastName,
  targetLanguage,
  nativeLanguage,
  targetExam,
  currentLevel,
      // bio,
      // avatar,
    });
    
    res.status(200).json({
      success: true,
      data: updatedUser,
      message: 'Profile has been updated successfully',
    });
  } catch (error: any) {
    console.error('Update profile error:', error);
    res.status(400).json({
      success: false,
      message: error.message || 'Failed to update profile',
    });
  }
};

/**
 * Delete user account
 */
export const deleteAccount = async (req: Request, res: Response): Promise<void> => {
  try {
    const userId = req.user!.userId;
    const { password } = req.body;
    
    await authService.deleteAccount(userId, password);
    
    res.status(200).json({
      success: true,
      message: 'Account has been deleted successfully',
    });
  } catch (error: any) {
    console.error('Delete account error:', error);
    res.status(400).json({
      success: false,
      message: error.message || 'Failed to delete account',
    });
  }
};