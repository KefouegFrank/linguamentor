/**
 * Authentication Input Validation
 * Validates request payloads using Zod schemas
 */

import { z } from 'zod';
// Decouple from Prisma enums to avoid build dependency
const TargetLanguageValues = [
  'ENGLISH',
  'SPANISH',
  'FRENCH',
  'GERMAN',
  'MANDARIN',
  'JAPANESE',
  'KOREAN',
  'ARABIC',
  'PORTUGUESE',
  'ITALIAN',
] as const;

const ExamTypeValues = [
  'IELTS',
  'TOEFL',
  'DELF',
  'DELE',
  'JLPT',
  'HSK',
  'CEFR',
  'OTHER',
] as const;

/**
 * Email validation schema
 */
const emailSchema = z
  .string()
  .email('Invalid email address')
  .toLowerCase()
  .trim();

/**
 * Password validation schema
 */
const passwordSchema = z
  .string()
  .min(8, 'Password must be at least 8 characters long')
  .regex(/[A-Z]/, 'Password must contain at least one uppercase letter')
  .regex(/[a-z]/, 'Password must contain at least one lowercase letter')
  .regex(/\d/, 'Password must contain at least one number')
  .regex(/[!@#$%^&*(),.?":{}|<>]/, 'Password must contain at least one special character');

/**
 * Registration request validation schema
 */
export const registerSchema = z.object({
  email: emailSchema,
  password: passwordSchema,
  firstName: z.string().min(1).max(50).optional(),
  lastName: z.string().min(1).max(50).optional(),
  targetLanguage: z.enum(TargetLanguageValues),
  nativeLanguage: z.string().min(2).max(50).optional(),
  targetExam: z.enum(ExamTypeValues).optional(),
});

/**
 * Login request validation schema
 */
export const loginSchema = z.object({
  email: emailSchema,
  password: z.string().min(1, 'Password is required'),
});

/**
 * Refresh token request validation schema
 */
export const refreshTokenSchema = z.object({
  refreshToken: z.string().min(1, 'Refresh token is required'),
});

/**
 * Password reset request validation schema
 */
export const passwordResetRequestSchema = z.object({
  email: emailSchema,
});

/**
 * Password reset confirmation validation schema
 */
export const passwordResetConfirmSchema = z.object({
  token: z.string().min(1, 'Reset token is required'),
  newPassword: passwordSchema,
});

/**
 * Email verification validation schema
 */
export const emailVerificationSchema = z.object({
  token: z.string().min(1, 'Verification token is required'),
});

/**
 * Type inference from schemas
 */
export type RegisterInput = z.infer<typeof registerSchema>;
export type LoginInput = z.infer<typeof loginSchema>;
export type RefreshTokenInput = z.infer<typeof refreshTokenSchema>;
export type PasswordResetRequestInput = z.infer<typeof passwordResetRequestSchema>;
export type PasswordResetConfirmInput = z.infer<typeof passwordResetConfirmSchema>;
export type EmailVerificationInput = z.infer<typeof emailVerificationSchema>;