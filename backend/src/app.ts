import express, { Application, Request, Response, NextFunction } from "express";
import cors from "cors";
import helmet from "helmet";
import authRoutes from "./routes/auth.routes";
import fileRoutes from "./routes/file.routes";
import jobRoutes from "./routes/job.routes";
import { corsConfig } from "./config/auth.config";
import { IS_DEVELOPMENT } from "./config/config";
import type { QueueService } from "./services/queue.service";
import { attachCorrelationId } from "./middleware/correlation.middleware";
import pinoHttp from "pino-http";
import { logger } from "./utils/logger";
import { metricsMiddleware, metricsHandler } from "./observability/metrics";
import { readinessHandler, livenessHandler } from "./health";
import { setupSwagger } from "./docs/swagger";

// Note: Environment variables are loaded in config/config.ts

export function createApp(_queueService?: QueueService): Application {
  const app = express();

  // Security
  app.use(
    helmet({
      contentSecurityPolicy: {
        useDefaults: true,
        directives: {
          defaultSrc: ["'self'"],
          imgSrc: ["'self'", "data:", "https:"],
          scriptSrc: ["'self'"],
          styleSrc: ["'self'", "https:"],
          connectSrc: ["'self'"],
        },
      },
      crossOriginEmbedderPolicy: true,
      crossOriginOpenerPolicy: true,
      crossOriginResourcePolicy: { policy: "same-site" },
    })
  );
  app.use(cors(corsConfig));

  // Body parsers
  app.use(express.json({ limit: "10mb" }));
  app.use(express.urlencoded({ extended: true, limit: "10mb" }));

  // Correlation ID + structured request logging
  app.use(attachCorrelationId);
  // Use default pino-http without custom options to satisfy TypeScript types
  app.use(pinoHttp());

  // Prometheus metrics for requests
  app.use(metricsMiddleware);

  // Mount routes
  app.use("/api/auth", authRoutes);
  app.use("/api/files", fileRoutes);
  app.use("/api/jobs", jobRoutes);
  // Health endpoints
  app.get("/health/live", livenessHandler);
  app.get("/health/ready", readinessHandler);
  // Metrics endpoint
  app.get("/metrics", metricsHandler);
  // Swagger docs (protected under /api/docs)
  setupSwagger(app);

  // Legacy health
  app.get("/health", (_req, res) => {
    res
      .status(200)
      .json({ success: true, message: "LinguaMentor API is running" });
  });

  // 404
  app.use((_req: Request, res: Response) => {
    res.status(404).json({ success: false, message: "Route not found" });
  });

  // Global error handler
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  app.use((err: Error, _req: Request, res: Response, _next: NextFunction) => {
    logger.error({ err }, "Unhandled error");
    res.status(500).json({ success: false, message: "Internal server error" });
  });

  return app;
}

export default createApp;
