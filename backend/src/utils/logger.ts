/**
 * Pino logger configured for JSON structured logs.
 * Includes correlation id and optional jobId tagging for cross-service tracing.
 */
import pino from "pino";

const level =
  process.env.LOG_LEVEL ||
  (process.env.NODE_ENV === "production" ? "info" : "debug");

export const logger = pino({
  level,
  base: undefined, // omit pid/hostname to reduce noise
  timestamp: pino.stdTimeFunctions.isoTime,
});

/**
 * Create a child logger with correlation id and optional jobId
 */
export const withContext = (context: {
  correlationId?: string;
  jobId?: string;
  userId?: string;
}) => {
  const bindings: Record<string, string> = {};
  if (context.correlationId) bindings.correlationId = context.correlationId;
  if (context.jobId) bindings.jobId = context.jobId;
  if (context.userId) bindings.userId = context.userId;
  return logger.child(bindings);
};
