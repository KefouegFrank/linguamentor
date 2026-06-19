import { FastifyInstance, FastifyPluginOptions } from 'fastify';
import bcrypt from 'bcrypt';
import { prisma } from '../lib/prisma';

// Strong-typing the incoming request body contract
interface RegisterBody {
  email: string;
  password: string;
  targetLanguage: 'ENGLISH' | 'FRENCH';
}

export const authRoutes = async (fastify: FastifyInstance, options: FastifyPluginOptions) => {
  
  /**
   * POST /api/v1/auth/register
   * Securely creates a user account, initializes profile, and sets baseline skill metrics.
   */
  fastify.post<{ Body: RegisterBody }>(
    '/register',
    {
      schema: {
        body: {
          type: 'object',
          required: ['email', 'password', 'targetLanguage'],
          properties: {
            email: { type: 'string', format: 'email' },
            password: { type: 'string', minLength: 8 },
            targetLanguage: { type: 'string', enum: ['ENGLISH', 'FRENCH'] },
          },
        },
      },
    },
    async (request, reply) => {
      const { email, password, targetLanguage } = request.body;

      try {
        // 1. Proactively check for existing account to prevent unique constraint crashes
        const existingUser = await prisma.user.findUnique({ where: { email } });
        if (existingUser) {
          return reply.status(409).send({
            error: 'Conflict',
            message: 'Account already exists.',
          });
        }

        // 2. Compute secure cryptographic hash (Work factor/Salt rounds = 12)
        const saltRounds = 12;
        const passwordHash = await bcrypt.hash(password, saltRounds);

        // 3. Execute ACID-compliant transaction to build identity ecosystem
        const newUser = await prisma.$transaction(async (tx) => {
          // Step A: Create Core User Entity
          const user = await tx.user.create({
            data: {
              email,
              passwordHash,
            },
          });

          // Step B: Create Profile tied to User
          const profile = await tx.learnerProfile.create({
            data: {
              userId: user.id,
              targetLanguage,
              currentLevel: 'A1', // Systems defaults to A1 baseline pre-diagnostic
            },
          });

          // Step C: Create empty Baseline 4D Skill Vector tied to Profile
          await tx.skillVector.create({
            data: {
              profileId: profile.id,
              grammarScore: 0.0,
              vocabularyScore: 0.0,
              pronunciationScore: 0.0,
              coherenceScore: 0.0,
            },
          });

          return user;
        });

        // 4. Send successful response (Excluding critical PII and security tokens)
        return reply.status(201).send({
          id: newUser.id,
          email: newUser.email,
          createdAt: newUser.createdAt,
        });

      } catch (error) {
        fastify.log.error('Registration pipeline failed processing:', error);
        return reply.status(500).send({
          error: 'Internal Server Error',
          message: 'An unexpected error occurred while creating your account.',
        });
      }
    }
  );
};