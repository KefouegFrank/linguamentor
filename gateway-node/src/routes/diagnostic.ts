import { FastifyInstance, FastifyPluginOptions } from 'fastify';
import { requireAuth } from '../hooks/autgGuard';
import { aiClient } from '../lib/aiClient';
import { prisma } from '../lib/prisma';


export const diagnosticRoutes = async (fastify: FastifyInstance, options: FastifyPluginOptions) => {
  
  /**
   * POST /api/v1/diagnostic/start
   * Securely triggers the diagnostic placement process.
   */
  fastify.post(
    '/start',
    { preHandler: [requireAuth] },
    async (request, reply) => {
      // Unpack identity coordinates populated from the JWT session hook
      const { sub: userId } = request.user as { sub: string };

      try {
        // 1. Fetch user profile to tailor diagnostic generation parameters
        const profile = await prisma.learnerProfile.findUnique({
          where: { userId },
        });

        if (!profile) {
          return reply.status(404).send({
            error: 'Not Found',
            message: 'Learner profile context could not be located.',
          });
        }

        // 2. Delegate the generation of adaptive assessment vectors to the Python Monolith
        const promptString = `Generate an adaptive baseline diagnostic evaluation template for a native learner pursuing language target: ${profile.targetLanguage}.`;
        
        const aiResponse = await aiClient.request('/api/v1/orchestrator/test-inference', 'POST', {
          prompt: promptString,
          tier: 'mid-tier',
        });

        // 3. Return combined payload representing completed gateway cross-communication
        return reply.status(200).send({
          success: true,
          profileStatus: {
            language: profile.targetLanguage,
            currentLevel: profile.currentLevel,
          },
          orchestratorOutput: aiResponse,
        });

      } catch (error: any) {
        fastify.log.error('Inter-service bridge failure on diagnostic start:', error);
        return reply.status(502).send({
          error: 'Bad Gateway',
          message: 'The gateway was unable to complete core tasks with internal AI engines.',
        });
      }
    }
  );
};