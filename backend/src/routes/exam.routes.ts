import { Router } from "express";
import { createSession, submitToSession, getSession } from "../controllers/exam.controller";
import { authenticate } from "../middleware/auth.middleware";
import { createRateLimiter } from "../middleware/rateLimit.middleware";

const router = Router();
const limiter = createRateLimiter({ windowMs: 60 * 1000, max: 60 });

/**
 * @swagger
 * /api/exams/sessions:
 *   post:
 *     summary: Create a new exam session
 *     tags: [Exams]
 *     security:
 *       - bearerAuth: []
 *     requestBody:
 *       required: true
 *       content:
 *         application/json:
 *           schema:
 *             type: object
 *             required: [examType]
 *             properties:
 *               examType:
 *                 type: string
 *                 description: Exam type identifier
 *               metadata:
 *                 type: object
 *     responses:
 *       201:
 *         description: Session created
 *         content:
 *           application/json:
 *             schema:
 *               type: object
 *               properties:
 *                 success:
 *                   type: boolean
 *                   example: true
 *                 data:
 *                   type: object
 *                   properties:
 *                     session:
 *                       $ref: '#/components/schemas/ExamSession'
 *       400:
 *         description: Validation error
 *         content:
 *           application/json:
 *             schema:
 *               $ref: '#/components/schemas/ErrorResponse'
 *       401:
 *         description: Unauthorized
 *         content:
 *           application/json:
 *             schema:
 *               $ref: '#/components/schemas/ErrorResponse'
 */
router.post("/sessions", authenticate, limiter, createSession);

/**
 * @swagger
 * /api/exams/sessions/{sessionId}/submit:
 *   post:
 *     summary: Submit an answer for an exam session
 *     tags: [Exams]
 *     security:
 *       - bearerAuth: []
 *     parameters:
 *       - in: path
 *         name: sessionId
 *         required: true
 *         schema:
 *           type: string
 *     requestBody:
 *       required: true
 *       content:
 *         application/json:
 *           schema:
 *             type: object
 *             required: [submissionType]
 *             properties:
 *               submissionType:
 *                 $ref: '#/components/schemas/SubmissionType'
 *               textData:
 *                 type: string
 *                 description: Required if submissionType is TEXT
 *               fileId:
 *                 type: string
 *                 description: Required if submissionType is AUDIO
 *     responses:
 *       202:
 *         description: Submission accepted and scoring job queued
 *         content:
 *           application/json:
 *             schema:
 *               type: object
 *               properties:
 *                 success:
 *                   type: boolean
 *                   example: true
 *                 data:
 *                   type: object
 *                   properties:
 *                     submission:
 *                       $ref: '#/components/schemas/ExamSubmission'
 *                     jobId:
 *                       type: string
 *       400:
 *         description: Validation error or invalid session state
 *         content:
 *           application/json:
 *             schema:
 *               $ref: '#/components/schemas/ErrorResponse'
 *       401:
 *         description: Unauthorized
 *         content:
 *           application/json:
 *             schema:
 *               $ref: '#/components/schemas/ErrorResponse'
 *       404:
 *         description: Session not found
 *         content:
 *           application/json:
 *             schema:
 *               $ref: '#/components/schemas/ErrorResponse'
 */
router.post("/sessions/:sessionId/submit", authenticate, limiter, submitToSession);

/**
 * @swagger
 * /api/exams/sessions/{sessionId}:
 *   get:
 *     summary: Get an exam session with submissions and results
 *     tags: [Exams]
 *     security:
 *       - bearerAuth: []
 *     parameters:
 *       - in: path
 *         name: sessionId
 *         required: true
 *         schema:
 *           type: string
 *     responses:
 *       200:
 *         description: Session details
 *         content:
 *           application/json:
 *             schema:
 *               type: object
 *               properties:
 *                 success:
 *                   type: boolean
 *                   example: true
 *                 data:
 *                   type: object
 *                   properties:
 *                     session:
 *                       $ref: '#/components/schemas/ExamSession'
 *       401:
 *         description: Unauthorized
 *         content:
 *           application/json:
 *             schema:
 *               $ref: '#/components/schemas/ErrorResponse'
 *       404:
 *         description: Session not found
 *         content:
 *           application/json:
 *             schema:
 *               $ref: '#/components/schemas/ErrorResponse'
 */
router.get("/sessions/:sessionId", authenticate, limiter, getSession);

export default router;
