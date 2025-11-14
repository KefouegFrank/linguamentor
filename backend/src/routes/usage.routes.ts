import { Router } from "express";
import { authenticate, authorize } from "../middleware/auth.middleware";
import { createRateLimiter } from "../middleware/rateLimit.middleware";
import { getMyUsage, patchUsageQuota } from "../controllers/usage.controller";

const router = Router();

router.get("/me", authenticate, createRateLimiter({ windowMs: 60_000, max: 60 }), getMyUsage);
/**
 * @swagger
 * /api/usage/quota:
 *   patch:
 *     summary: Update user usage quotas (admin only)
 *     tags: [Usage]
 *     security:
 *       - bearerAuth: []
 *     requestBody:
 *       required: true
 *       content:
 *         application/json:
 *           schema:
 *             type: object
 *             properties:
 *               dailyQuota:
 *                 type: integer
 *                 minimum: 0
 *               monthlyQuota:
 *                 type: integer
 *                 minimum: 0
 *     responses:
 *       200:
 *         description: Quotas updated
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
 *                     usage:
 *                       $ref: '#/components/schemas/UserUsage'
 *       401:
 *         description: Unauthorized
 *         content:
 *           application/json:
 *             schema:
 *               $ref: '#/components/schemas/ErrorResponse'
 *       403:
 *         description: Forbidden (requires ADMIN role)
 *         content:
 *           application/json:
 *             schema:
 *               $ref: '#/components/schemas/ErrorResponse'
 */
router.patch("/quota", authenticate, authorize("ADMIN"), createRateLimiter({ windowMs: 60_000, max: 30 }), patchUsageQuota);

export default router;
/**
 * @swagger
 * /api/usage/me:
 *   get:
 *     summary: Get my current usage and quotas
 *     tags: [Usage]
 *     security:
 *       - bearerAuth: []
 *     responses:
 *       200:
 *         description: Current usage
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
 *                     usage:
 *                       $ref: '#/components/schemas/UserUsage'
 *       401:
 *         description: Unauthorized
 *         content:
 *           application/json:
 *             schema:
 *               $ref: '#/components/schemas/ErrorResponse'
 */
