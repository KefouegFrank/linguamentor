import { FastifyReply, FastifyRequest } from 'fastify';

/**
 * Reusable Security Guard Hook
 * Intercepts incoming requests, verifies JWT token validity, 
 * and blocks unauthorized execution before hitting route logic.
 */
export const requireAuth = async (request: FastifyRequest, reply: FastifyReply) => {
  try {
    // Native @fastify/jwt verification. Extracts 'Bearer <token>',
    // validates the cryptographic signature, and sets request.user.
    await request.jwtVerify();
  } catch (err) {
    // Halt lifecycle execution immediately if token fails verification
    return reply.status(401).send({
      error: 'Unauthorized',
      message: 'Access denied. Invalid token.',
    });
  }
};