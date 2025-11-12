/**
 * Authentication Type Definitions
 * Defines all types and interfaces used in the authentication system
 */

// Decouple from Prisma enums for build-time independence
export type UserRole = 'LEARNER' | 'ADMIN' | 'TEACHER';
export type CEFRLevel = 'A1' | 'A2' | 'B1' | 'B2' | 'C1' | 'C2';
export type TargetLanguage =
  | 'ENGLISH'
  | 'SPANISH'
  | 'FRENCH'
  | 'GERMAN'
  | 'MANDARIN'
  | 'JAPANESE'
  | 'KOREAN'
  | 'ARABIC'
  | 'PORTUGUESE'
  | 'ITALIAN';
export type ExamType = 'IELTS' | 'TOEFL' | 'DELF' | 'DELE' | 'JLPT' | 'HSK' | 'CEFR' | 'OTHER';

/**
 * User registration request payload
 */
export interface RegisterRequest {
  email: string;
  password: string;
  firstName?: string;
  lastName?: string;
  targetLanguage: TargetLanguage;
  nativeLanguage?: string;
  targetExam?: ExamType;
}

/**
 * User login request payload
 */
export interface LoginRequest {
  email: string;
  password: string;
}

/**
 * OAuth login request payload
 */
export interface OAuthLoginRequest {
  provider: 'google' | 'facebook' | 'apple';
  oauthId: string;
  email: string;
  firstName?: string;
  lastName?: string;
}

/**
 * Token refresh request payload
 */
export interface RefreshTokenRequest {
  refreshToken: string;
}

/**
 * Authentication response with tokens
 */
export interface AuthResponse {
  accessToken: string;
  refreshToken: string;
  user: UserResponse;
}

/**
 * User data returned in API responses (excludes sensitive fields)
 */
export interface UserResponse {
  id: string;
  email: string;
  firstName?: string;
  lastName?: string;
  role: UserRole;
  targetLanguage: TargetLanguage;
  nativeLanguage?: string;
  currentLevel: CEFRLevel;
  targetExam?: ExamType;
  readinessScore: number;
  totalStudyTime: number;
  currentStreak: number;
  longestStreak: number;
  subscriptionTier: string;
  emailVerified: boolean;
  createdAt: Date;
}

/**
 * JWT Access Token Payload
 */
export interface AccessTokenPayload {
  userId: string;
  email: string;
  role: UserRole;
  iat?: number; // issued at
  exp?: number; // expiration
}

/**
 * JWT Refresh Token Payload
 */
export interface RefreshTokenPayload {
  userId: string;
  tokenId: string; // Unique identifier for this refresh token
  iat?: number;
  exp?: number;
}

/**
 * Password reset request
 */
export interface PasswordResetRequest {
  email: string;
}

/**
 * Password reset confirmation
 */
export interface PasswordResetConfirm {
  token: string;
  newPassword: string;
}

/**
 * Email verification request
 */
export interface EmailVerificationRequest {
  token: string;
}