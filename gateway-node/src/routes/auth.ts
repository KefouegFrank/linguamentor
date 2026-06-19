import { FastifyInstance, FastifyPluginOptions } from "fastify";
import bcrypt from "bcrypt";
import { prisma } from "../lib/prisma";

interface RegisterBody {
  email: string;
  password: string;
  targetLanguage: "ENGLISH" | "FRENCH";
}

interface LoginBody {
  email: string;
  password: string;
}

export const authRoutes = async (
  fastify: FastifyInstance,
  options: FastifyPluginOptions,
) => {
  /**
   * POST /api/v1/auth/register
   */
  fastify.post<{ Body: RegisterBody }>(
    "/register",
    {
      schema: {
        body: {
          type: "object",
          required: ["email", "password", "targetLanguage"],
          properties: {
            email: { type: "string", format: "email" },
            password: { type: "string", minLength: 8 },
            targetLanguage: { type: "string", enum: ["ENGLISH", "FRENCH"] },
          },
        },
      },
    },
    async (request, reply) => {
      const { email, password, targetLanguage } = request.body;
      try {
        const existingUser = await prisma.user.findUnique({ where: { email } });
        if (existingUser) {
          return reply.status(409).send({
            error: "Conflict",
            message: "Account already exists.",
          });
        }

        const saltRounds = 12;
        const passwordHash = await bcrypt.hash(password, saltRounds);

        const newUser = await prisma.$transaction(async (tx) => {
          const user = await tx.user.create({ data: { email, passwordHash } });
          const profile = await tx.learnerProfile.create({
            data: { userId: user.id, targetLanguage, currentLevel: "A1" },
          });
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

        return reply.status(201).send({
          id: newUser.id,
          email: newUser.email,
          createdAt: newUser.createdAt,
        });
      } catch (error) {
        fastify.log.error("Registration pipeline failed:", error);
        return reply.status(500).send({
          error: "Internal Server Error",
          message: "An unexpected error occurred while creating your account.",
        });
      }
    },
  );

  /**
   * POST /api/v1/auth/login
   * Validates identity credentials and returns a secure, stateless JWT token signature.
   */
  fastify.post<{ Body: LoginBody }>(
    "/login",
    {
      schema: {
        body: {
          type: "object",
          required: ["email", "password"],
          properties: {
            email: { type: "string", format: "email" },
            password: { type: "string" },
          },
        },
      },
    },
    async (request, reply) => {
      const { email, password } = request.body;

      try {
        // 1. Fetch user by PII identity email key
        const user = await prisma.user.findUnique({ where: { email } });
        if (!user) {
          return reply.status(401).send({
            error: "Unauthorized",
            message: "Invalid credentials.",
          });
        }

        // 2. Perform high-entropy timing-safe password resolution comparison
        const isPasswordValid = await bcrypt.compare(
          password,
          user.passwordHash,
        );
        if (!isPasswordValid) {
          return reply.status(401).send({
            error: "Unauthorized",
            message: "Invalid credentials.",
          });
        }

        // 3. Construct clean stateless session token payload
        const tokenPayload = {
          sub: user.id,
          email: user.email,
        };

        // 4. Issue cryptographically signed token utilizing Fastify's native JWT service
        const accessToken = fastify.jwt.sign(tokenPayload, { expiresIn: "7d" }); // 7-day rolling window strategy

        return reply.status(200).send({
          accessToken,
          user: {
            id: user.id,
            email: user.email,
          },
        });
      } catch (error) {
        fastify.log.error("Login routing transactional failure:", error);
        return reply.status(500).send({
          error: "Internal Server Error",
          message: "An unexpected system error occurred during verification.",
        });
      }
    },
  );
};
