/**
 * Application Configuration
 * Handles environment detection and configuration loading
 * Supports: local development, Docker development, and production
 */

import dotenv from 'dotenv';
import path from 'path';

// Determine environment
const isProduction = process.env.NODE_ENV === 'production';
const isDevelopment = process.env.NODE_ENV === 'development' || !process.env.NODE_ENV;

// Load environment files in priority order:
// 1. .env.local (highest priority - local overrides)
// 2. .env (default)
// 3. .env.production (if in production)
if (isProduction) {
    dotenv.config({ path: path.resolve(process.cwd(), '.env.production') });
}
dotenv.config({ path: path.resolve(process.cwd(), '.env.local') }); // Local overrides
dotenv.config(); // Default .env

const toStr = (v?: string, fallback = ''): string => (v === undefined ? fallback : v);
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
            'DATABASE_URL is required. Please set it in .env or .env.local file.\n' +
            'Example: postgresql://user:password@host:5432/database?schema=public'
        );
    }

    // If running in Docker (detected by container name or explicit flag)
    const isDocker = process.env.DOCKER_ENV === 'true' || 
                     process.env.DATABASE_HOST === 'db' ||
                     dbUrl.includes('@db:');

    // If URL already contains a host, optionally rewrite for local dev
    if (dbUrl.includes('@')) {
        // If running locally (not Docker, not production) and URL points to 'db', rewrite to 'localhost'
        if (!isProduction && !isDocker && dbUrl.includes('@db:')) {
            return dbUrl.replace('@db:', '@localhost:');
        }
        return dbUrl;
    }

    // Fallback: construct URL (shouldn't happen if DATABASE_URL is properly set)
    const dbHost = isDocker ? 'db' : 'localhost';
    const dbUser = process.env.DB_USER || 'linguamentor_user';
    const dbPassword = process.env.DB_PASSWORD || 'securepass';
    const dbName = process.env.DB_NAME || 'linguamentor_db';
    
    return `postgresql://${dbUser}:${dbPassword}@${dbHost}:5432/${dbName}?schema=public`;
};

// Environment
export const NODE_ENV = process.env.NODE_ENV || 'development';
export const IS_PRODUCTION = isProduction;
export const IS_DEVELOPMENT = isDevelopment;

// Server
export const PORT = toNum(process.env.PORT, 4000);

// Database
export const DATABASE_URL = getDatabaseUrl();

// Cookie
export const COOKIE_DOMAIN = toStr(process.env.COOKIE_DOMAIN, 'localhost');
export const COOKIE_SECURE = (process.env.COOKIE_SECURE || 'false') === 'true';

// Logging
export const LOG_LEVEL = toStr(process.env.LOG_LEVEL, isProduction ? 'info' : 'debug');
