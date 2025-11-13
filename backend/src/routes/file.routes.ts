/**
 * File Routes
 * Defines all file-related API endpoints
 */

import { Router } from "express";
import { authenticate } from "../middleware/auth.middleware";
import { validateBody, validateParamUuid } from "../middleware/validation.middleware";
import { createRateLimiter } from "../middleware/rateLimit.middleware";
import {
  createPresignedUpload,
  confirmUpload,
  getDownloadUrl,
  processFile,
  listFiles,
  getFile,
  deleteFile,
} from "../controllers/file.controller";
import { createUploadSchema, processFileSchema } from "../validation/file.validation";

const router = Router();

// Basic rate limiters to mitigate abuse on heavy endpoints
const uploadUrlLimiter = createRateLimiter({ windowMs: 60_000, max: 30 });
const processFileLimiter = createRateLimiter({ windowMs: 60_000, max: 20 });

/**
 * @swagger
 * tags:
 *   name: Files
 *   description: File management and processing endpoints
 */

/**
 * @swagger
 * /files/upload-url:
 *   post:
 *     tags: [Files]
 *     summary: Create presigned upload URL
 *     security:
 *       - bearerAuth: []
 *     requestBody:
 *       required: true
 *       content:
 *         application/json:
 *           schema:
 *             type: object
 *             required: [filename, contentType]
 *             properties:
 *               filename:
 *                 type: string
 *               contentType:
 *                 type: string
 *               fileType:
 *                 type: string
 *                 description: Logical file type/category
 *               size:
 *                 type: integer
 *                 format: int64
 *               metadata:
 *                 type: object
 *     responses:
 *       200:
 *         description: Presigned URL and upload info
 */

/**
 * @swagger
 * /files/{fileId}/confirm:
 *   post:
 *     tags: [Files]
 *     summary: Confirm upload completion
 *     security:
 *       - bearerAuth: []
 *     parameters:
 *       - in: path
 *         name: fileId
 *         required: true
 *         schema:
 *           type: string
 *     responses:
 *       200:
 *         description: Upload confirmed
 */

/**
 * @swagger
 * /files/{fileId}/download-url:
 *   get:
 *     tags: [Files]
 *     summary: Get presigned download URL
 *     security:
 *       - bearerAuth: []
 *     parameters:
 *       - in: path
 *         name: fileId
 *         required: true
 *         schema:
 *           type: string
 *     responses:
 *       200:
 *         description: Presigned download URL
 */

/**
 * @swagger
 * /files/{fileId}/process:
 *   post:
 *     tags: [Files]
 *     summary: Process a file with an operation
 *     security:
 *       - bearerAuth: []
 *     parameters:
 *       - in: path
 *         name: fileId
 *         required: true
 *         schema:
 *           type: string
 *     requestBody:
 *       required: true
 *       content:
 *         application/json:
 *           schema:
 *             type: object
 *             required: [operation]
 *             properties:
 *               operation:
 *                 type: string
 *                 enum: [transcribe, translate, summarize, convert, compress, extract]
 *               targetLanguage:
 *                 type: string
 *               parameters:
 *                 type: object
 *               priority:
 *                 type: string
 *               webhookUrl:
 *                 type: string
 *                 format: uri
 *     responses:
 *       202:
 *         description: Processing started; returns job details
 */

/**
 * @swagger
 * /files:
 *   get:
 *     tags: [Files]
 *     summary: List files for current user
 *     security:
 *       - bearerAuth: []
 *     responses:
 *       200:
 *         description: List of files
 */

/**
 * @swagger
 * /files/{fileId}:
 *   get:
 *     tags: [Files]
 *     summary: Get file details
 *     security:
 *       - bearerAuth: []
 *     parameters:
 *       - in: path
 *         name: fileId
 *         required: true
 *         schema:
 *           type: string
 *     responses:
 *       200:
 *         description: File details
 *   delete:
 *     tags: [Files]
 *     summary: Delete a file
 *     security:
 *       - bearerAuth: []
 *     parameters:
 *       - in: path
 *         name: fileId
 *         required: true
 *         schema:
 *           type: string
 *     responses:
 *       200:
 *         description: File deleted
 */

// Create presigned URL for upload
router.post("/upload-url", authenticate, uploadUrlLimiter, validateBody(createUploadSchema), createPresignedUpload);

// Confirm upload completion
router.post("/:fileId/confirm", authenticate, validateParamUuid('fileId'), confirmUpload);

// Get presigned download URL
router.get("/:fileId/download-url", authenticate, validateParamUuid('fileId'), getDownloadUrl);

// Process a file with an operation
router.post("/:fileId/process", authenticate, validateParamUuid('fileId'), processFileLimiter, validateBody(processFileSchema), processFile);

// List files
router.get("/", authenticate, listFiles);

// Get file details
router.get("/:fileId", authenticate, validateParamUuid('fileId'), getFile);

// Delete file
router.delete("/:fileId", authenticate, validateParamUuid('fileId'), deleteFile);

export default router;
