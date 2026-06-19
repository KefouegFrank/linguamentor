import { FastifyInstance, FastifyPluginOptions } from 'fastify';
import { requireAuth } from '../hooks/autgGuard';
import { aiClient } from '../lib/aiClient';
import { prisma } from '../lib/prisma';
import { Prisma } from '@prisma/client';
import { error } from 'console';
import { Session } from 'inspector/promises';


export const diagnosticRoutes = async (fastify: FastifyInstance, options: FastifyPluginOptions) => {

  /**
   * POST /api/v1/diagnostic/start
   * Triggers generation, records the session context, and returns the tracking token.
   */
  fastify.post(
    '/start',
    { preHandler: [requireAuth] },
    async (request, reply) => {
      // Unpack identity coordinates populated from the JWT session hook
      const { sub: userId } = request.user as { sub: string };

      try {
        // 1. Proactively block execution if an incomplete diagnostic test session is already open
        const activeSession = await prisma.diagnosticSession.findFirst({
          where: { userId, status: 'IN_PROGRESS' }
        })

        if (activeSession) {
          return reply.status(400).send({
            error: 'Bad Request',
            message: 'You already have an evaluation session in progress',
            SessionId: activeSession.id,
            generatedContent: activeSession.generatedContent
          });
        }

        //2 Fetch user profile to tailor diagnostic generation parameters
        const profile = await prisma.learnerProfile.findUnique({
          where: { userId },
        });

        if (!profile) {
          return reply.status(404).send({
            error: 'Not Found',
            message: 'Learner profile context could not be located.',
          });
        }

        //3 Delegate the generation task to internal Python Monolith
        const promptString = `Generate an adaptive baseline diagnostic evaluation template for a native learner pursuing language target: ${profile.targetLanguage}.`;

        const aiResponse = await aiClient.request<Prisma.InputJsonValue>(
          '/api/v1/orchestrator/test-inference',
          'POST',
          {
            prompt: promptString,
            tier: 'mid-tier',
          }
        );

        //4 Save session inside an atomic transaction block
        const sessionRecord = await prisma.diagnosticSession.create({
          data: {
            userId,
            status: 'IN_PROGRESS',
            generatedContent: aiResponse // saved cleanly into binary JSONB column
          }
        });

        //5 Present the payload structure to client along with tracking token coordinates
        return reply.status(200).send({
          success: true,
          SessionId: sessionRecord.id,
          profileStatus: {
            language: profile.targetLanguage,
            currentLevel: profile.currentLevel,
          },
          assessmentData: sessionRecord.generatedContent,
        });

      } catch (error: any) {
        console.error('Raw error:', error)
        fastify.log.error('Failed to instatiate dynamic evaluation session:', error);
        return reply.status(502).send({
          error: 'Bad Gateway',
          message: 'The gateway encountered an error connecting to internal AI computation tiers.',
        });
      }
    }
  );
};