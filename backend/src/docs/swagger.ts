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
