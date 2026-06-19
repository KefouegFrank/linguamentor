import * as dotenv from 'dotenv';
dotenv.config({ path: '../.env' });

import Fastify, { FastifyInstance } from 'fastify';
import fastifyJwt from '@fastify/jwt';
import { prisma } from './lib/prisma';
import { authRoutes } from './routes/auth';

const fastify = Fastify({ logger: true });

// register cryptograhic JWT serivce engine
fastify.register(fastifyJwt, {
  secret: process.env.JWT_SECRET || 'your_jwt_secret_here'
});

// Core Server Health Check
fastify.get("/health", async () => {
  return { status: "UP", service: "gateway-node", version: "1.0.0" };
});

// API Version 1 Encapsulated Routing Core
const apiV1Routes = async (server: FastifyInstance) => {
  server.get("/status", async () => {
    // Simple verification check reading the database state
    try {
      await prisma.$queryRaw`SELECT 1`;
      return { version: "v1.0.0", channel: "stable", database: "CONNECTED" };
    } catch (error) {
      server.log.error(
        "Database connection failed during status check:",
        error,
      );
      return { version: "v1.0.0", channel: "stable", database: "DISCONNECTED" };
    }
  });

  //Mount Authentication Domain Routes under /api/v1/auth
  server.register(authRoutes, { prefix: "/auth" });
};

// Register API v1 Routes under the explicit legal namespace
fastify.register(apiV1Routes, { prefix: "/api/v1" });

const start = async () => {
  try {
    // Verify database connection before binding to network port
    await prisma.$connect();
    fastify.log.info("Database connection established successfully.");

    const port = Number(process.env.GATEWAY_PORT) || 3000;
    await fastify.listen({ port, host: "0.0.0.0" });
  } catch (err) {
    // console.error("RAW ERROR:", err);
    fastify.log.error("Fatal initialization error:", err);
    await prisma.$disconnect();
    process.exit(1);
  }
};

start();
