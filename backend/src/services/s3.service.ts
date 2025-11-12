import {
  S3Client,
  PutObjectCommand,
  GetObjectCommand,
  DeleteObjectCommand,
  HeadObjectCommand,
} from "@aws-sdk/client-s3";
import { getSignedUrl } from "@aws-sdk/s3-request-presigner";
import { randomUUID } from "crypto";
import { config } from "../config/config";
import { AppError } from "../utils/errors";
import { Readable } from "stream";

export interface PresignedUploadResult {
  uploadUrl: string;
  fileKey: string;
}

export class S3Service {
  private s3Client: S3Client;
  private bucket: string;
  private defaultExpiresIn = 3600; // 1 hour

  constructor() {
    this.bucket = config.aws.s3Bucket;

    const s3Config: any = {
      region: config.aws.region || "us-east-1",
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
  async generatePresignedUploadUrl(
    fileName: string,
    contentType: string,
    expiresIn: number = this.defaultExpiresIn
  ): Promise<PresignedUploadResult> {
    try {
      const fileKey = this.generateFileKey(fileName);

      const command = new PutObjectCommand({
        Bucket: this.bucket,
        Key: fileKey,
        ContentType: contentType,
      });

      const uploadUrl = await getSignedUrl(this.s3Client, command, {
        expiresIn,
      });

      return {
        uploadUrl,
        fileKey,
      };
    } catch (error: any) {
      throw new AppError(
        `Failed to generate upload URL: ${error.message}`,
        500
      );
    }
  }

  /**
   * Generate a presigned URL for file download
   */
  async generatePresignedDownloadUrl(
    fileKey: string,
    fileName: string,
    expiresIn: number = this.defaultExpiresIn
  ): Promise<string> {
    try {
      const command = new GetObjectCommand({
        Bucket: this.bucket,
        Key: fileKey,
        ResponseContentDisposition: `attachment; filename="${fileName}"`,
      });

      const downloadUrl = await getSignedUrl(this.s3Client, command, {
        expiresIn,
      });

      return downloadUrl;
    } catch (error: any) {
      throw new AppError(
        `Failed to generate download URL: ${error.message}`,
        500
      );
    }
  }

  /**
   * Upload a file to S3
   */
  async uploadFile(
    fileBuffer: Buffer,
    fileKey: string,
    contentType: string,
    metadata?: Record<string, string>
  ): Promise<string> {
    try {
      const command = new PutObjectCommand({
        Bucket: this.bucket,
        Key: fileKey,
        Body: fileBuffer,
        ContentType: contentType,
        Metadata: metadata,
      });

      await this.s3Client.send(command);

      return this.getPublicUrl(fileKey);
    } catch (error: any) {
      throw new AppError(`Failed to upload file: ${error.message}`, 500);
    }
  }

  /**
   * Download a file from S3
   */
  async downloadFile(fileKey: string): Promise<Buffer> {
    try {
      const command = new GetObjectCommand({
        Bucket: this.bucket,
        Key: fileKey,
      });

      const response = await this.s3Client.send(command);

      if (!response.Body) {
        throw new Error("No file body in response");
      }

      // Convert stream to buffer
      const stream = response.Body as Readable;
      const chunks: Buffer[] = [];

      for await (const chunk of stream) {
        chunks.push(chunk);
      }

      return Buffer.concat(chunks);
    } catch (error: any) {
      throw new AppError(`Failed to download file: ${error.message}`, 500);
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
    } catch (error: any) {
      throw new AppError(`Failed to delete file: ${error.message}`, 500);
    }
  }

  /**
   * Check if a file exists in S3
   */
  async fileExists(fileKey: string): Promise<boolean> {
    try {
      const command = new HeadObjectCommand({
        Bucket: this.bucket,
        Key: fileKey,
      });

      await this.s3Client.send(command);
      return true;
    } catch (error: any) {
      if (error.name === "NoSuchKey" || error.name === "NotFound") {
        return false;
      }
      throw new AppError(
        `Failed to check file existence: ${error.message}`,
        500
      );
    }
  }

  /**
   * Generate a unique file key
   */
  private generateFileKey(originalName: string): string {
    const timestamp = Date.now();
    const randomId = randomUUID().split("-")[0];
    const sanitizedName = originalName.replace(/[^a-zA-Z0-9.-]/g, "_");
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
    return `https://${this.bucket}.s3.${config.aws.region || "us-east-1"}.amazonaws.com/${fileKey}`;
  }
}

export const s3Service = new S3Service();
