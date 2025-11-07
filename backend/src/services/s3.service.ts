import { S3Client, PutObjectCommand, GetObjectCommand, DeleteObjectCommand } from '@aws-sdk/client-s3';
import { getSignedUrl } from '@aws-sdk/s3-request-presigner';
import { randomUUID } from 'crypto';
import { config } from '../config/config';
import { AppError } from '../utils/errorHandler';

export interface PresignedUploadUrl {
  uploadUrl: string;
  fileKey: string;
  expiresAt: Date;
}

export interface PresignedDownloadUrl {
  downloadUrl: string;
  expiresAt: Date;
}

export interface FileUploadOptions {
  fileName: string;
  contentType: string;
  fileSize?: number;
  expiresIn?: number; // seconds
  metadata?: Record<string, string>;
}

export class S3Service {
  private s3Client: S3Client;
  private bucket: string;
  private defaultExpiresIn = 3600; // 1 hour

  constructor() {
    this.bucket = config.aws.s3Bucket;
    
    const s3Config: any = {
      region: config.aws.region || 'us-east-1',
      credentials: {
        accessKeyId: config.aws.accessKeyId,
        secretAccessKey: config.aws.secretAccessKey,
      },
    };

    // Support for MinIO and other S3-compatible services
    if (config.aws.s3Endpoint) {
      s3Config.endpoint = config.aws.s3Endpoint;
      s3Config.forcePathStyle = true; // Required for MinIO
    }

    this.s3Client = new S3Client(s3Config);
  }

  /**
   * Generate a presigned URL for file upload
   */
  async generateUploadPresignedUrl(options: FileUploadOptions): Promise<PresignedUploadUrl> {
    try {
      const fileKey = this.generateFileKey(options.fileName);
      const expiresIn = options.expiresIn || this.defaultExpiresIn;
      
      // Validate file size if provided
      if (options.fileSize && options.fileSize > 500 * 1024 * 1024) { // 500MB limit
        throw new AppError('File size exceeds maximum allowed size of 500MB', 400);
      }

      const command = new PutObjectCommand({
        Bucket: this.bucket,
        Key: fileKey,
        ContentType: options.contentType,
        Metadata: {
          originalName: options.fileName,
          uploadTime: new Date().toISOString(),
          ...options.metadata,
        },
      });

      const uploadUrl = await getSignedUrl(this.s3Client, command, { expiresIn });
      
      return {
        uploadUrl,
        fileKey,
        expiresAt: new Date(Date.now() + expiresIn * 1000),
      };
    } catch (error) {
      if (error instanceof AppError) throw error;
      throw new AppError(`Failed to generate upload URL: ${error.message}`, 500);
    }
  }

  /**
   * Generate a presigned URL for file download
   */
  async generateDownloadPresignedUrl(fileKey: string, expiresIn: number = this.defaultExpiresIn): Promise<PresignedDownloadUrl> {
    try {
      const command = new GetObjectCommand({
        Bucket: this.bucket,
        Key: fileKey,
      });

      const downloadUrl = await getSignedUrl(this.s3Client, command, { expiresIn });
      
      return {
        downloadUrl,
        expiresAt: new Date(Date.now() + expiresIn * 1000),
      };
    } catch (error) {
      throw new AppError(`Failed to generate download URL: ${error.message}`, 500);
    }
  }

  /**
   * Delete a file from S3
   */
  async deleteFile(fileKey: string): Promise<void> {
    try {
      const command = new DeleteObjectCommand({
        Bucket: this.bucket,
        Key: fileKey,
      });

      await this.s3Client.send(command);
    } catch (error) {
      throw new AppError(`Failed to delete file: ${error.message}`, 500);
    }
  }

  /**
   * Check if a file exists in S3
   */
  async fileExists(fileKey: string): Promise<boolean> {
    try {
      const command = new GetObjectCommand({
        Bucket: this.bucket,
        Key: fileKey,
      });

      await this.s3Client.send(command);
      return true;
    } catch (error) {
      if (error.name === 'NoSuchKey') {
        return false;
      }
      throw new AppError(`Failed to check file existence: ${error.message}`, 500);
    }
  }

  /**
   * Generate a unique file key
   */
  private generateFileKey(originalName: string): string {
    const timestamp = Date.now();
    const randomId = randomUUID().split('-')[0];
    const sanitizedName = originalName.replace(/[^a-zA-Z0-9.-]/g, '_');
    return `uploads/${timestamp}-${randomId}-${sanitizedName}`;
  }

  /**
   * Get the public URL for a file (if bucket is public)
   */
  getPublicUrl(fileKey: string): string {
    if (config.aws.s3Endpoint) {
      // For MinIO and other S3-compatible services
      return `${config.aws.s3Endpoint}/${this.bucket}/${fileKey}`;
    }
    return `https://${this.bucket}.s3.${config.aws.region || 'us-east-1'}.amazonaws.com/${fileKey}`;
  }
}

export const s3Service = new S3Service();