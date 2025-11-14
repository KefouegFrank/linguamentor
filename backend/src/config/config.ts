/**
 * Application Configuration
 * Handles environment detection and configuration loading
 * Supports: local development, Docker development, and production
 */

import dotenv from "dotenv";
import path from "path";

// Determine environment
const isProduction = process.env.NODE_ENV === "production";
const isDevelopment =
  process.env.NODE_ENV === "development" || !process.env.NODE_ENV;

// Load environment files in priority order:
// 1. .env.local (highest priority - local overrides)
// 2. .env (default)
// 3. .env.production (if in production)
if (isProduction) {
  dotenv.config({ path: path.resolve(process.cwd(), ".env.production") });
}
dotenv.config({ path: path.resolve(process.cwd(), ".env.local") }); // Local overrides
dotenv.config(); // Default .env

const toStr = (v?: string, fallback = ""): string =>
  v === undefined ? fallback : v;
const toNum = (v?: string, fallback = 0): number => {
  if (v === undefined) return fallback;
  const parsed = parseInt(v, 10);
  return isNaN(parsed) ? fallback : parsed;
};

/**
 * Get database URL with smart host resolution
 * - In Docker: uses service name 'db'
 * - Locally: uses 'localhost'
 * - Production: uses provided DATABASE_URL
 */
const getDatabaseUrl = (): string => {
  const dbUrl = process.env.DATABASE_URL;

  if (!dbUrl) {
    throw new Error(
      "DATABASE_URL is required. Please set it in .env or .env.local file.\n" +
        "Example: postgresql://user:password@host:5432/database?schema=public"
    );
  }

  // If running in Docker (detected by container name or explicit flag)
  const isDocker =
    process.env.DOCKER_ENV === "true" ||
    process.env.DATABASE_HOST === "db" ||
    dbUrl.includes("@db:");

  // If URL already contains a host, optionally rewrite for local dev
  if (dbUrl.includes("@")) {
    // If running locally (not Docker, not production) and URL points to 'db', rewrite to 'localhost'
    if (!isProduction && !isDocker && dbUrl.includes("@db:")) {
      return dbUrl.replace("@db:", "@localhost:");
    }
    return dbUrl;
  }

  // Fallback: construct URL (shouldn't happen if DATABASE_URL is properly set)
  const dbHost = isDocker ? "db" : "localhost";
  const dbUser = process.env.DB_USER || "linguamentor_user";
  const dbPassword = process.env.DB_PASSWORD || "securepass";
  const dbName = process.env.DB_NAME || "linguamentor_db";

  return `postgresql://${dbUser}:${dbPassword}@${dbHost}:5432/${dbName}?schema=public`;
};

// Environment
export const NODE_ENV = process.env.NODE_ENV || "development";
export const IS_PRODUCTION = isProduction;
export const IS_DEVELOPMENT = isDevelopment;

// Server
export const PORT = toNum(process.env.PORT, 4000);

// Database
export const DATABASE_URL = getDatabaseUrl();

// Cookie
export const COOKIE_DOMAIN = toStr(process.env.COOKIE_DOMAIN, "localhost");
export const COOKIE_SECURE = (process.env.COOKIE_SECURE || "false") === "true";

// Logging
export const LOG_LEVEL = toStr(
  process.env.LOG_LEVEL,
  isProduction ? "info" : "debug"
);

// Redis
const REDIS_URL = toStr(process.env.REDIS_URL, "redis://localhost:6379");

// Upload settings
const UPLOAD_MAX_FILE_SIZE = toNum(
  process.env.UPLOAD_MAX_FILE_SIZE,
  50 * 1024 * 1024
); // 50MB
const UPLOAD_ALLOWED_MIME_TYPES = process.env.UPLOAD_ALLOWED_MIME_TYPES?.split(
  ","
) || [
  "audio/mpeg",
  "audio/wav",
  "audio/webm",
  "application/pdf",
  "text/plain",
  "application/json",
  "image/png",
  "image/jpeg",
];
const PRESIGNED_URL_EXPIRY = toNum(process.env.PRESIGNED_URL_EXPIRY, 3600); // seconds

// AWS / S3 settings
const AWS_REGION = toStr(process.env.AWS_REGION, "us-east-1");
const AWS_ACCESS_KEY_ID = toStr(process.env.AWS_ACCESS_KEY_ID, "");
const AWS_SECRET_ACCESS_KEY = toStr(process.env.AWS_SECRET_ACCESS_KEY, "");
const S3_BUCKET = toStr(process.env.S3_BUCKET, "linguamentor");
const S3_ENDPOINT = toStr(process.env.S3_ENDPOINT, "");

/**
 * Unified config object for modules that import `{ config }`
 */
export const config = {
  NODE_ENV,
  IS_PRODUCTION,
  IS_DEVELOPMENT,
  PORT,
  database: {
    url: DATABASE_URL,
  },
  redis: {
    url: REDIS_URL,
  },
  internalService: {
    token: toStr(process.env.INTERNAL_SERVICE_TOKEN, "dev-internal-token"),
    webhookSecret: toStr(process.env.WEBHOOK_SECRET, ""),
    aiQueueName: toStr(process.env.AI_QUEUE_NAME, "ai-jobs"),
  },
  upload: {
    maxFileSize: UPLOAD_MAX_FILE_SIZE,
    allowedMimeTypes: UPLOAD_ALLOWED_MIME_TYPES,
    presignedUrlExpiry: PRESIGNED_URL_EXPIRY,
  },
  aws: {
    region: AWS_REGION,
    accessKeyId: AWS_ACCESS_KEY_ID,
    secretAccessKey: AWS_SECRET_ACCESS_KEY,
    s3Bucket: S3_BUCKET,
    s3Endpoint: S3_ENDPOINT,
  },
};
