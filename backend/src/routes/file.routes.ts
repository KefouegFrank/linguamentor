/**
 * File Routes
 * Defines all file-related API endpoints
 */

import { Router } from "express";
import { authenticate } from "../middleware/auth.middleware";
import {
  createPresignedUpload,
  confirmUpload,
  getDownloadUrl,
  processFile,
  listFiles,
  getFile,
  deleteFile,
} from "../controllers/file.controller";

const router = Router();

// Create presigned URL for upload
router.post("/upload-url", authenticate, createPresignedUpload);

// Confirm upload completion
router.post("/:fileId/confirm", authenticate, confirmUpload);

// Get presigned download URL
router.get("/:fileId/download-url", authenticate, getDownloadUrl);

// Process a file with an operation
router.post("/:fileId/process", authenticate, processFile);

// List files
router.get("/", authenticate, listFiles);

// Get file details
router.get("/:fileId", authenticate, getFile);

// Delete file
router.delete("/:fileId", authenticate, deleteFile);

export default router;

