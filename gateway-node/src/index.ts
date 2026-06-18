import Fastify, { FastifyInstance } from 'fastify';
import * as dotenv from 'dotenv';

dotenv.config({ path: '../.env' });

const fastify = Fastify({ logger: true });

// Core Server Health Check (Operational Metric Engine Context)
fastify.get('/health', async () => {
  return { status: 'UP', service: 'gateway-node', version: '1.0.0' };
});

/**
 * API Version 1 Encapsulated Routing Core
 * All foundational platform logic hooks onto this namespace.
 */
const apiV1Routes = async (server: FastifyInstance) => {
  server.get('/status', async () => {
    return { version: 'v1.0.0', channel: 'stable', context: 'authenticated-runtime' };
  });

  // Future foundational routes map clean under this tree:
  // server.post('/auth/register', registerHandler);
  // server.post('/evaluations/submit', submitHandler);
};

// Register API v1 Routes under the explicit legal namespace
fastify.register(apiV1Routes, { prefix: '/api/v1' });

const start = async () => {
  try {
    const port = Number(process.env.GATEWAY_PORT) || 3000;
    await fastify.listen({ port, host: '0.0.0.0' });
    fastify.log.info(`Gateway Engine Running securely via API Versioning Matrix.`);
  } catch (err) {
    fastify.log.error(err);
    process.exit(1);
  }
};

start();