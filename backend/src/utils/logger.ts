/**
 * Simple logger utility for logging messages
 * In production, this could be replaced with Winston, Pino, or similar logging libraries
 */

export const logger = {
  info: (message: string, meta?: any) => {
    const timestamp = new Date().toISOString();
    console.log(`[${timestamp}] INFO: ${message}`, meta ? JSON.stringify(meta) : '');
  },

  error: (message: string, error?: any) => {
    const timestamp = new Date().toISOString();
    console.error(`[${timestamp}] ERROR: ${message}`, error);
  },

  warn: (message: string, meta?: any) => {
    const timestamp = new Date().toISOString();
    console.warn(`[${timestamp}] WARN: ${message}`, meta ? JSON.stringify(meta) : '');
  },

  debug: (message: string, meta?: any) => {
    // Only log debug messages in development
    if (process.env.NODE_ENV !== 'production') {
      const timestamp = new Date().toISOString();
      console.debug(`[${timestamp}] DEBUG: ${message}`, meta ? JSON.stringify(meta) : '');
    }
  },
};