/**
 * Job Routes
 * Defines all job-related API endpoints
 */

import { Router } from "express";
import { authenticate } from "../middleware/auth.middleware";
import {
  createJob,
  getJobStatus,
  listJobs,
  cancelJob,
  retryJob,
  handleJobWebhook,
  getQueueMetrics,
  cleanOldJobs,
} from "../controllers/job.controller";

const router = Router();

// Create a new job
router.post("/", authenticate, createJob);

// Get job status
router.get("/:jobId", authenticate, getJobStatus);

// List jobs
router.get("/", authenticate, listJobs);

// Cancel a job
router.post("/:jobId/cancel", authenticate, cancelJob);

// Retry a failed job
router.post("/:jobId/retry", authenticate, retryJob);

// Internal webhook (no auth, validated by service token/signature)
router.post("/webhook", (req, res, next) => handleJobWebhook(req as any, res, next));

// Queue metrics
router.get("/metrics", authenticate, getQueueMetrics);

// Clean old jobs in a queue
router.post("/clean", authenticate, cleanOldJobs);

export default router;
