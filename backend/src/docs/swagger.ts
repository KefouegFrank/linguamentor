import swaggerJsdoc from "swagger-jsdoc";
import swaggerUi from "swagger-ui-express";
import type { Application, Request, Response, NextFunction } from "express";
import { optionalAuthenticate, authorize } from "../middleware/auth.middleware";
import type { UserRole } from "../types/auth.types";
import { config } from "../config/config";

const swaggerDefinition = {
  openapi: "3.0.0",
  info: {
    title: "LinguaMentor API",
    version: "1.0.0",
    description: "API documentation for LinguaMentor backend",
  },
  servers: [{ url: "/api", description: "Primary API base" }],
  components: {
    securitySchemes: {
      bearerAuth: {
        type: "http",
        scheme: "bearer",
        bearerFormat: "JWT",
      },
    },
    schemas: {
      ExamStatus: {
        type: "string",
        enum: ["PENDING", "IN_PROGRESS", "COMPLETED", "CANCELLED"],
      },
      SubmissionType: {
        type: "string",
        enum: ["TEXT", "AUDIO"],
      },
      ExamResult: {
        type: "object",
        properties: {
          id: { type: "string" },
          score: { type: "number" },
          rubric: { type: "object" },
          feedback: { type: "string" },
          metadata: { type: "object" },
          createdAt: { type: "string", format: "date-time" },
        },
      },
      ExamSubmission: {
        type: "object",
        properties: {
          id: { type: "string" },
          sessionId: { type: "string" },
          submissionType: { $ref: "#/components/schemas/SubmissionType" },
          textData: { type: "string" },
          fileId: { type: "string" },
          aiResultId: { type: "string" },
          aiResult: { $ref: "#/components/schemas/ExamResult" },
          createdAt: { type: "string", format: "date-time" },
        },
      },
      ExamSession: {
        type: "object",
        properties: {
          id: { type: "string" },
          userId: { type: "string" },
          status: { $ref: "#/components/schemas/ExamStatus" },
          examType: { type: "string" },
          startedAt: { type: "string", format: "date-time" },
          completedAt: { type: "string", format: "date-time" },
          metadata: { type: "object" },
          submissions: {
            type: "array",
            items: { $ref: "#/components/schemas/ExamSubmission" },
          },
          createdAt: { type: "string", format: "date-time" },
          updatedAt: { type: "string", format: "date-time" },
        },
      },
      Notification: {
        type: "object",
        properties: {
          id: { type: "string" },
          userId: { type: "string" },
          type: {
            type: "string",
            enum: [
              "EMAIL_VERIFICATION",
              "PASSWORD_RESET",
              "EXAM_COMPLETED",
              "EXAM_FEEDBACK_READY",
              "QUOTA_EXCEEDED",
              "SYSTEM_ALERT",
            ],
          },
          title: { type: "string" },
          message: { type: "string" },
          isRead: { type: "boolean" },
          readAt: { type: "string", format: "date-time" },
          metadata: { type: "object" },
          createdAt: { type: "string", format: "date-time" },
          updatedAt: { type: "string", format: "date-time" },
        },
      },
      UserUsage: {
        type: "object",
        properties: {
          id: { type: "string" },
          userId: { type: "string" },
          tokensUsed: { type: "integer" },
          dailyQuota: { type: "integer" },
          monthlyQuota: { type: "integer" },
          lastReset: { type: "string", format: "date-time" },
          createdAt: { type: "string", format: "date-time" },
          updatedAt: { type: "string", format: "date-time" },
        },
      },
      ErrorResponse: {
        type: "object",
        properties: {
          success: { type: "boolean", example: false },
          message: { type: "string" },
          code: { type: "string" },
        },
      },
    },
  },
  security: [{ bearerAuth: [] }],
};

const options = {
  swaggerDefinition,
  apis: ["src/routes/*.ts", "src/controllers/*.ts", "src/app.ts"],
};

export function setupSwagger(app: Application) {
  const spec = swaggerJsdoc(options as any);

  // Docs route: public in development, admin-only otherwise
  if (config.IS_DEVELOPMENT) {
    app.use(
      "/api/docs",
      swaggerUi.serve,
      swaggerUi.setup(spec, { explorer: true })
    );
  } else {
    app.use(
      "/api/docs",
      optionalAuthenticate,
      authorize("ADMIN" as UserRole),
      swaggerUi.serve,
      swaggerUi.setup(spec, { explorer: true })
    );
  }
}
