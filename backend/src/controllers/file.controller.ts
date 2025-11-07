import { Request, Response, NextFunction } from 'express';
import { prisma } from '../prisma/prisma';
import { s3Service } from '../services/s3.service';
import { queueService, QUEUE_NAMES } from '../services/queue.service';
import { AppError } from '../utils/errorHandler';
import { config } from '../config/config';
import { FileStatus, FileType, JobType, JobPriority } from '@prisma/client';
import crypto from 'crypto';

/**
 * Request types
 */
interface AuthenticatedRequest extends Request {
  user?: {
    id: string;
    email: string;
    role: string;
  };
}

interface CreateFileUploadRequest extends AuthenticatedRequest {
  body: {
    filename: string;
    contentType: string;
    fileType: FileType;
    size: number;
    metadata?: Record<string, any>;
  };
}

interface ProcessFileRequest extends AuthenticatedRequest {
  params: {
    fileId: string;
  };
  body: {
    operation: 'transcribe' | 'translate' | 'summarize' | 'convert' | 'compress' | 'extract';
    targetLanguage?: string;
    parameters?: Record<string, any>;
    priority?: JobPriority;
    webhookUrl?: string;
  };
}

/**
 * Create a presigned upload URL
 */
export const createPresignedUpload = async (
  req: CreateFileUploadRequest,
  res: Response,
  next: NextFunction
) => {
  try {
    const { filename, contentType, fileType, size, metadata = {} } = req.body;
    const userId = req.user!.id;

    // Validate file size
    if (size > config.upload.maxFileSize) {
      throw new AppError('File size exceeds maximum allowed size', 400);
    }

    // Validate content type
    if (!config.upload.allowedMimeTypes.includes(contentType)) {
      throw new AppError('File type not allowed', 400);
    }

    // Create file record
    const file = await prisma.file.create({
      data: {
        filename,
        originalName: filename,
        contentType,
        size,
        type: fileType,
        status: FileStatus.PENDING,
        uploadedById: userId,
        metadata: JSON.stringify(metadata),
      },
    });

    // Generate presigned upload URL
    const { uploadUrl, fileKey } = await s3Service.generatePresignedUploadUrl(
      filename,
      contentType,
      config.upload.presignedUrlExpiry
    );

    // Update file with S3 key
    await prisma.file.update({
      where: { id: file.id },
      data: { s3Key: fileKey },
    });

    res.status(201).json({
      success: true,
      data: {
        fileId: file.id,
        uploadUrl,
        expiresIn: config.upload.presignedUrlExpiry,
        file: {
          id: file.id,
          filename: file.filename,
          contentType: file.contentType,
          size: file.size,
          type: file.type,
          status: file.status,
          createdAt: file.createdAt,
        },
      },
    });
  } catch (error) {
    next(error);
  }
};

/**
 * Confirm file upload completion
 */
export const confirmUpload = async (
  req: AuthenticatedRequest,
  res: Response,
  next: NextFunction
) => {
  try {
    const { fileId } = req.params;
    const userId = req.user!.id;

    const file = await prisma.file.findFirst({
      where: {
        id: fileId,
        uploadedById: userId,
      },
    });

    if (!file) {
      throw new AppError('File not found', 404);
    }

    if (!file.s3Key) {
      throw new AppError('File S3 key not found', 400);
    }

    // Verify file exists in S3
    const exists = await s3Service.fileExists(file.s3Key);
    if (!exists) {
      throw new AppError('File not found in storage', 404);
    }

    // Update file status
    const updatedFile = await prisma.file.update({
      where: { id: fileId },
      data: {
        status: FileStatus.UPLOADED,
        uploadedAt: new Date(),
      },
    });

    res.status(200).json({
      success: true,
      data: {
        file: updatedFile,
      },
    });
  } catch (error) {
    next(error);
  }
};

/**
 * Get file download URL
 */
export const getDownloadUrl = async (
  req: AuthenticatedRequest,
  res: Response,
  next: NextFunction
) => {
  try {
    const { fileId } = req.params;
    const userId = req.user!.id;

    const file = await prisma.file.findFirst({
      where: {
        id: fileId,
        uploadedById: userId,
      },
    });

    if (!file) {
      throw new AppError('File not found', 404);
    }

    if (!file.s3Key) {
      throw new AppError('File not available for download', 400);
    }

    // Generate presigned download URL
    const downloadUrl = await s3Service.generatePresignedDownloadUrl(
      file.s3Key,
      file.filename,
      config.upload.presignedUrlExpiry
    );

    res.status(200).json({
      success: true,
      data: {
        downloadUrl,
        expiresIn: config.upload.presignedUrlExpiry,
        file: {
          id: file.id,
          filename: file.filename,
          contentType: file.contentType,
          size: file.size,
          type: file.type,
        },
      },
    });
  } catch (error) {
    next(error);
  }
};

/**
 * Process file with AI operations
 */
export const processFile = async (
  req: ProcessFileRequest,
  res: Response,
  next: NextFunction
) => {
  try {
    const { fileId } = req.params;
    const { operation, targetLanguage, parameters = {}, priority = JobPriority.MEDIUM, webhookUrl } = req.body;
    const userId = req.user!.id;

    const file = await prisma.file.findFirst({
      where: {
        id: fileId,
        uploadedById: userId,
      },
    });

    if (!file) {
      throw new AppError('File not found', 404);
    }

    if (file.status !== FileStatus.UPLOADED) {
      throw new AppError('File not ready for processing', 400);
    }

    // Determine job type and queue based on operation
    let jobType: JobType;
    let queueName: string;

    switch (operation) {
      case 'transcribe':
      case 'translate':
      case 'summarize':
        jobType = JobType.AI_PROCESSING;
        queueName = QUEUE_NAMES.AI_PROCESSING;
        break;
      case 'convert':
      case 'compress':
      case 'extract':
        jobType = JobType.FILE_PROCESSING;
        queueName = QUEUE_NAMES.FILE_PROCESSING;
        break;
      default:
        throw new AppError('Invalid operation', 400);
    }

    // Create job data
    const jobData = {
      fileId: file.id,
      userId,
      operation,
      targetLanguage,
      webhookUrl,
      parameters,
    };

    // Add job to queue
    const jobId = await queueService.addJob(
      queueName,
      jobType,
      jobData,
      priority
    );

    res.status(201).json({
      success: true,
      data: {
        jobId,
        message: 'File processing job queued successfully',
      },
    });
  } catch (error) {
    next(error);
  }
};

/**
 * List user files
 */
export const listFiles = async (
  req: AuthenticatedRequest,
  res: Response,
  next: NextFunction
) => {
  try {
    const userId = req.user!.id;
    const {
      page = 1,
      limit = 10,
      type,
      status,
      search,
      sortBy = 'createdAt',
      sortOrder = 'desc',
    } = req.query;

    const where: any = { uploadedById: userId };

    if (type) {
      where.type = type;
    }

    if (status) {
      where.status = status;
    }

    if (search) {
      where.OR = [
        { filename: { contains: search as string, mode: 'insensitive' } },
        { originalName: { contains: search as string, mode: 'insensitive' } },
      ];
    }

    const skip = (Number(page) - 1) * Number(limit);

    const [files, total] = await Promise.all([
      prisma.file.findMany({
        where,
        skip,
        take: Number(limit),
        orderBy: { [sortBy as string]: sortOrder as 'asc' | 'desc' },
        select: {
          id: true,
          filename: true,
          originalName: true,
          contentType: true,
          size: true,
          type: true,
          status: true,
          createdAt: true,
          uploadedAt: true,
          metadata: true,
        },
      }),
      prisma.file.count({ where }),
    ]);

    res.status(200).json({
      success: true,
      data: {
        files,
        pagination: {
          page: Number(page),
          limit: Number(limit),
          total,
          pages: Math.ceil(total / Number(limit)),
        },
      },
    });
  } catch (error) {
    next(error);
  }
};

/**
 * Get file details
 */
export const getFile = async (
  req: AuthenticatedRequest,
  res: Response,
  next: NextFunction
) => {
  try {
    const { fileId } = req.params;
    const userId = req.user!.id;

    const file = await prisma.file.findFirst({
      where: {
        id: fileId,
        uploadedById: userId,
      },
      include: {
        jobs: {
          select: {
            id: true,
            type: true,
            status: true,
            priority: true,
            createdAt: true,
            startedAt: true,
            completedAt: true,
            progress: true,
          },
          orderBy: { createdAt: 'desc' },
        },
      },
    });

    if (!file) {
      throw new AppError('File not found', 404);
    }

    res.status(200).json({
      success: true,
      data: {
        file,
      },
    });
  } catch (error) {
    next(error);
  }
};

/**
 * Delete file
 */
export const deleteFile = async (
  req: AuthenticatedRequest,
  res: Response,
  next: NextFunction
) => {
  try {
    const { fileId } = req.params;
    const userId = req.user!.id;

    const file = await prisma.file.findFirst({
      where: {
        id: fileId,
        uploadedById: userId,
      },
    });

    if (!file) {
      throw new AppError('File not found', 404);
    }

    // Delete from S3 if it exists
    if (file.s3Key) {
      try {
        await s3Service.deleteFile(file.s3Key);
      } catch (error) {
        console.error('Failed to delete file from S3:', error);
        // Continue with database deletion even if S3 deletion fails
      }
    }

    // Delete from database
    await prisma.file.delete({
      where: { id: fileId },
    });

    res.status(200).json({
      success: true,
      message: 'File deleted successfully',
    });
  } catch (error) {
    next(error);
  }
};