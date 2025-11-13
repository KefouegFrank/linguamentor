/**
 * Job Routes
 * Defines all job-related API endpoints
 */

import { Router } from "express";
import { authenticate } from "../middleware/auth.middleware";
import { validateBody, validateParamUuid } from "../middleware/validation.middleware";
import { createRateLimiter } from "../middleware/rateLimit.middleware";
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
import { createJobSchema, webhookSchema } from "../validation/job.validation";

const router = Router();

// Limit job creation to mitigate spam
const jobCreateLimiter = createRateLimiter({ windowMs: 60_000, max: 50 });

/**
 * @swagger
 * tags:
 *   name: Jobs
 *   description: Background job management endpoints
 */

/**
 * @swagger
 * /jobs:
 *   post:
 *     tags: [Jobs]
 *     summary: Create a new job
 *     security:
 *       - bearerAuth: []
 *     requestBody:
 *       required: true
 *       content:
 *         application/json:
 *           schema:
 *             type: object
 *             required: [type, data]
 *             properties:
 *               type:
 *                 type: string
 *               priority:
 *                 type: string
 *               fileId:
 *                 type: string
 *               data:
 *                 type: object
 *               webhookUrl:
 *                 type: string
 *                 format: uri
 *               delay:
 *                 type: integer
 *                 format: int32
 *     responses:
 *       202:
 *         description: Job accepted for processing
 *   get:
 *     tags: [Jobs]
 *     summary: List jobs for current user
 *     security:
 *       - bearerAuth: []
 *     responses:
 *       200:
 *         description: List of jobs
 */

/**
 * @swagger
 * /jobs/{jobId}:
 *   get:
 *     tags: [Jobs]
 *     summary: Get job status
 *     security:
 *       - bearerAuth: []
 *     parameters:
 *       - in: path
 *         name: jobId
 *         required: true
 *         schema:
 *           type: string
 *     responses:
 *       200:
 *         description: Job details
 */

/**
 * @swagger
 * /jobs/{jobId}/cancel:
 *   post:
 *     tags: [Jobs]
 *     summary: Cancel a job
 *     security:
 *       - bearerAuth: []
 *     parameters:
 *       - in: path
 *         name: jobId
 *         required: true
 *         schema:
 *           type: string
 *     responses:
 *       200:
 *         description: Job cancelled
 */

/**
 * @swagger
 * /jobs/{jobId}/retry:
 *   post:
 *     tags: [Jobs]
 *     summary: Retry a failed job
 *     security:
 *       - bearerAuth: []
 *     parameters:
 *       - in: path
 *         name: jobId
 *         required: true
 *         schema:
 *           type: string
 *     responses:
 *       200:
 *         description: Job retried
 */

/**
 * @swagger
 * /jobs/webhook:
 *   post:
 *     tags: [Jobs]
 *     summary: Internal webhook callback
 *     description: Used by internal services to report job updates.
 *     requestBody:
 *       required: true
 *       content:
 *         application/json:
 *           schema:
 *             type: object
 *             properties:
 *               jobId:
 *                 type: string
 *               status:
 *                 type: string
 *               result:
 *                 type: object
 *               error:
 *                 type: string
 *               metadata:
 *                 type: object
 *     responses:
 *       200:
 *         description: Webhook processed
 */

/**
 * @swagger
 * /jobs/metrics:
 *   get:
 *     tags: [Jobs]
 *     summary: Queue metrics
 *     security:
 *       - bearerAuth: []
 *     responses:
 *       200:
 *         description: Metrics payload
 */

/**
 * @swagger
 * /jobs/clean:
 *   post:
 *     tags: [Jobs]
 *     summary: Clean old jobs in a queue
 *     security:
 *       - bearerAuth: []
 *     requestBody:
 *       required: false
 *       content:
 *         application/json:
 *           schema:
 *             type: object
 *             properties:
 *               queue:
 *                 type: string
 *               status:
 *                 type: string
 *     responses:
 *       200:
 *         description: Cleanup executed
 */

// Create a new job
router.post("/", authenticate, jobCreateLimiter, validateBody(createJobSchema), createJob);

// Get job status
router.get("/:jobId", authenticate, validateParamUuid('jobId'), getJobStatus);

// List jobs
router.get("/", authenticate, listJobs);

// Cancel a job
router.post("/:jobId/cancel", authenticate, validateParamUuid('jobId'), cancelJob);

// Retry a failed job
router.post("/:jobId/retry", authenticate, validateParamUuid('jobId'), retryJob);

// Internal webhook (no auth, validated by service token/signature)
router.post("/webhook", validateBody(webhookSchema), (req, res, next) => handleJobWebhook(req as any, res, next));

// Queue metrics
router.get("/metrics", authenticate, getQueueMetrics);

// Clean old jobs in a queue
router.post("/clean", authenticate, cleanOldJobs);

export default router;
