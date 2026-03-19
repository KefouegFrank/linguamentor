// services/api-gateway/src/index.ts

import Fastify, {
  FastifyInstance,
  FastifyRequest,
  FastifyReply,
  FastifyPluginAsync,
} from 'fastify'
import fp from 'fastify-plugin'
import helmet from '@fastify/helmet'
import cors from '@fastify/cors'
import rateLimit from '@fastify/rate-limit'
import jwt from '@fastify/jwt'
import httpProxy from '@fastify/http-proxy'
import { readFileSync } from 'fs'
import { resolve } from 'path'
import { randomUUID } from 'crypto'
import Redis from 'ioredis'
import * as dotenv from 'dotenv'

// ---------------------------------------------------------------------------
// Config
// ---------------------------------------------------------------------------
dotenv.config({ path: resolve(__dirname, '../../..', '.env') })

const config = {
  port:             parseInt(process.env.LM_APP_PORT ?? '3000', 10),
  env:              process.env.LM_APP_ENV            ?? 'development',
  jwtPublicKeyPath: process.env.LM_JWT_PUBLIC_KEY_PATH ?? '',
  redisUrl:         process.env.LM_REDIS_URL           ?? 'redis://localhost:6379',
  frontendUrl:      process.env.LM_FRONTEND_URL        ?? 'http://localhost:3001',

  services: {
    writing:   process.env.LM_WRITING_SERVICE_URL   ?? 'http://localhost:8001',
    voice:     process.env.LM_VOICE_SERVICE_URL     ?? 'http://localhost:8002',
    adaptive:  process.env.LM_ADAPTIVE_ENGINE_URL   ?? 'http://localhost:8003',
    readiness: process.env.LM_READINESS_ENGINE_URL  ?? 'http://localhost:8004',
  },

  rateLimits: {
    global: { max: 200, windowMs: 60_000  },
    auth:   { max: 10,  windowMs: 900_000 },
  },

  bodyLimit: 50 * 1024, // 50KB
} as const

// ---------------------------------------------------------------------------
// Redis
// ---------------------------------------------------------------------------
const redis = new Redis(config.redisUrl, {
  lazyConnect:          true,
  enableOfflineQueue:   false,
  maxRetriesPerRequest: 2,
  connectTimeout:       5000,
})
redis.on('error', (err) => console.error('[redis] error:', err.message))

// ---------------------------------------------------------------------------
// JWT public key
// ---------------------------------------------------------------------------
function loadJwtPublicKey(): string {
  if (!config.jwtPublicKeyPath) throw new Error('LM_JWT_PUBLIC_KEY_PATH is not set')
  const path = resolve(config.jwtPublicKeyPath)
  try { return readFileSync(path, 'utf-8') }
  catch { throw new Error(`JWT public key not found at: ${path}`) }
}

// ---------------------------------------------------------------------------
// Prompt injection filter — OWASP LLM01:2025
// ---------------------------------------------------------------------------
const INJECTION_PATTERNS: RegExp[] = [
  /ignore\s+(all\s+)?(previous|prior|above)\s+instructions?/i,
  /disregard\s+(all\s+)?(previous|prior|above)\s+instructions?/i,
  /forget\s+(all\s+)?(previous|prior|above)\s+instructions?/i,
  /you\s+are\s+now\s+(in\s+)?(developer|god|jailbreak|dan)\s+mode/i,
  /system\s*[:]\s*override/i,
  /\[SYSTEM\]/i,
  /\[INST\]/i,
  /<\|system\|>/i,
  /<\|im_start\|>/i,
  /reveal\s+(your\s+)?(system\s+)?prompt/i,
  /print\s+(your\s+)?(system\s+)?instructions/i,
  /what\s+(are|were)\s+your\s+(original\s+)?instructions/i,
  /repeat\s+(your\s+)?(system\s+)?prompt/i,
  /you\s+are\s+now\s+(a\s+)?(different|new|another)\s+(ai|assistant|model)/i,
  /act\s+as\s+(if\s+)?(you\s+(are|were)\s+)?(a\s+)?(different|unrestricted)/i,
  /pretend\s+(you\s+)?(are|have\s+no)\s+(restrictions|guidelines|rules)/i,
  /\{system\}/i,
  /\{\{.*instructions.*\}\}/i,
  /(.)\1{200,}/,
]

const INJECTABLE_FIELDS = new Set([
  'essay_text', 'content', 'text', 'message',
  'input', 'query', 'prompt', 'description', 'feedback',
])

const MAX_TRAVERSE_DEPTH = 5

function detectPromptInjection(
  body: unknown
): { detected: boolean; field?: string; pattern?: string } {
  if (!body || typeof body !== 'object') return { detected: false }

  const visited = new WeakSet<object>()

  const traverse = (
    obj: object,
    depth: number,
    path: string
  ): { detected: boolean; field?: string; pattern?: string } => {
    if (depth > MAX_TRAVERSE_DEPTH) return { detected: false }
    if (visited.has(obj)) return { detected: false }
    visited.add(obj)

    const keys = Object.keys(obj)
    for (const key of keys) {
      if (key.startsWith('_') || key.startsWith('$') || key === 'constructor') continue
      const fieldName = path ? `${path}.${key}` : key
      let val: unknown
      try { val = (obj as Record<string, unknown>)[key] } catch { continue }

      if (typeof val === 'string' && INJECTABLE_FIELDS.has(key)) {
        for (const pattern of INJECTION_PATTERNS) {
          if (pattern.test(val)) return { detected: true, field: fieldName, pattern: pattern.toString() }
        }
        if (val.length > 10_000) return { detected: true, field: fieldName, pattern: 'length_exceeded' }
      } else if (
        val !== null &&
        typeof val === 'object' &&
        !Array.isArray(val) &&
        !(val instanceof Date) &&
        !(val instanceof RegExp) &&
        !(val instanceof Buffer)
      ) {
        const nested = traverse(val as object, depth + 1, fieldName)
        if (nested.detected) return nested
      }
    }
    return { detected: false }
  }

  return traverse(body as object, 0, '')
}

// The injection check as a preValidation handler — passed directly to each
// proxy registration. This is the documented @fastify/http-proxy pattern
// and guarantees it runs before proxying regardless of scope.
async function injectionGuard(req: FastifyRequest, reply: FastifyReply): Promise<void> {
  if (!['POST', 'PUT', 'PATCH'].includes(req.method.toUpperCase())) return
  if (!req.body) return

  const result = detectPromptInjection(req.body)
  if (result.detected) {
    req.log.warn({
      event:   'prompt_injection_detected',
      field:   result.field,
      pattern: result.pattern,
      ip:      req.ip,
      url:     req.url,
    }, 'Prompt injection attempt blocked')

    return reply.status(400).send({
      error:   true,
      message: 'Request contains content that cannot be processed.',
      code:    'INVALID_INPUT',
    })
  }
}

// ---------------------------------------------------------------------------
// Type augmentation
// ---------------------------------------------------------------------------
declare module 'fastify' {
  interface FastifyInstance {
    authenticate: (req: FastifyRequest, reply: FastifyReply) => Promise<void>
  }
}

declare module '@fastify/jwt' {
  interface FastifyJWT {
    payload: { sub: string; role: string; tier: string; type: string; iat: number; exp: number }
    user:    { sub: string; role: string; tier: string; type: string; iat: number; exp: number }
  }
}

// ---------------------------------------------------------------------------
// Auth plugin — fp() breaks encapsulation so decorator is visible everywhere
// ---------------------------------------------------------------------------
const authPlugin: FastifyPluginAsync = fp(async (fastify: FastifyInstance) => {
  fastify.decorate(
    'authenticate',
    async function (req: FastifyRequest, reply: FastifyReply): Promise<void> {
      try {
        await req.jwtVerify()
      } catch {
        reply.status(401).send({ error: true, message: 'Authentication required.', code: 'UNAUTHORIZED' })
      }
    }
  )
})

function requireRole(allowedRoles: string[]) {
  return async function (req: FastifyRequest, reply: FastifyReply): Promise<void> {
    const user = req.user as { role?: string } | undefined
    if (!user || !allowedRoles.includes(user.role ?? '')) {
      return reply.status(403).send({ error: true, message: 'Insufficient permissions.', code: 'FORBIDDEN' })
    }
  }
}

// ---------------------------------------------------------------------------
// Header helpers
// ---------------------------------------------------------------------------
type HeaderMap = Record<string, string>

function proxyHeaders(req: FastifyRequest): HeaderMap {
  const user = req.user as { sub?: string; role?: string; tier?: string } | undefined
  return {
    'x-request-id':    (req.headers['x-request-id'] as string) ?? req.id,
    'x-user-id':       user?.sub  ?? '',
    'x-user-role':     user?.role ?? '',
    'x-user-tier':     user?.tier ?? '',
    'x-forwarded-for': req.ip,
    'x-gateway':       'linguamentor-api-gateway',
  }
}

function publicHeaders(req: FastifyRequest): HeaderMap {
  return {
    'x-request-id':    (req.headers['x-request-id'] as string) ?? req.id,
    'x-forwarded-for': req.ip,
    'x-gateway':       'linguamentor-api-gateway',
  }
}

// ---------------------------------------------------------------------------
// App factory
// ---------------------------------------------------------------------------
async function buildApp(): Promise<FastifyInstance> {
  const isProd   = config.env === 'production'
  const usePretty = !isProd && process.stdout.isTTY

  const app = Fastify({
    logger: {
      level: isProd ? 'info' : 'debug',
      ...(usePretty && {
        transport: {
          target: 'pino-pretty',
          options: { colorize: true, translateTime: 'HH:MM:ss', ignore: 'pid,hostname' },
        },
      }),
    },
    bodyLimit:  config.bodyLimit,
    trustProxy: true,
    genReqId:   () => randomUUID(),
  })

  // [1] Security headers
  await app.register(helmet, {
    contentSecurityPolicy: {
      directives: {
        defaultSrc: ["'none'"], scriptSrc: ["'none'"],
        objectSrc:  ["'none'"], frameAncestors: ["'none'"],
      },
    },
    hsts: { maxAge: 31_536_000, includeSubDomains: true, preload: true },
    crossOriginResourcePolicy: { policy: 'same-origin' },
    noSniff: true, xssFilter: true, frameguard: { action: 'deny' }, hidePoweredBy: true,
  })

  // [2] CORS
  await app.register(cors, {
    origin:         isProd ? [config.frontendUrl] : ['http://localhost:3001', 'http://localhost:3000'],
    credentials:    true,
    methods:        ['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS'],
    allowedHeaders: ['Content-Type', 'Authorization', 'X-Request-ID'],
    exposedHeaders: ['X-Request-ID'],
  })

  // [3] Rate limiting
  await app.register(rateLimit, {
    global:     true,
    max:        config.rateLimits.global.max,
    timeWindow: config.rateLimits.global.windowMs,
    redis,
    keyGenerator: (req) => req.ip,
    errorResponseBuilder: (_req, context) => ({
      error: true,
      message: `Rate limit exceeded. Try again in ${Math.ceil(context.ttl / 1000)} seconds.`,
      retryAfter: Math.ceil(context.ttl / 1000),
    }),
    allowList: (req) => req.url === '/health' || req.url === '/ready',
  })

  // [4] JWT verify-only
  await app.register(jwt, {
    secret:  { public: loadJwtPublicKey() },
    sign:    { algorithm: 'RS256' },
    verify:  { algorithms: ['RS256'] },
  })

  // [5] Auth decorator (fp — visible to all scopes)
  await app.register(authPlugin)

  // Correlation ID on every request
  app.addHook('onRequest', async (req, reply) => {
    const id = (req.headers['x-request-id'] as string) ?? req.id
    req.headers['x-request-id'] = id
    reply.header('X-Request-ID', id)
  })

  // ---------------------------------------------------------------------------
  // Health probes — no auth, exempt from rate limiting
  // ---------------------------------------------------------------------------
  app.get('/health', async (_req, reply) =>
    reply.send({ status: 'ok', service: 'api-gateway' })
  )
  app.get('/ready', async (_req, reply) => {
    try {
      await redis.ping()
      return reply.send({ status: 'ready', redis: 'ok' })
    } catch {
      return reply.send({ status: 'ready', redis: 'degraded' })
    }
  })

  // ---------------------------------------------------------------------------
  // Public auth routes
  // No injection filter here — passwords/tokens are not AI inputs
  // ---------------------------------------------------------------------------
  await app.register(async (instance) => {
    await instance.register(httpProxy, {
      upstream:      config.services.writing,
      prefix:        '/api/v1/auth',
      rewritePrefix: '/api/v1/auth',
      replyOptions: {
        rewriteRequestHeaders: (_req, headers) => ({
          ...headers, ...publicHeaders(_req as FastifyRequest),
        }),
      },
    })
  })

  // ---------------------------------------------------------------------------
  // Protected routes — JWT required + injection filter on AI-bound endpoints
  // ---------------------------------------------------------------------------
  await app.register(async (instance) => {
    instance.addHook('preHandler', instance.authenticate)

    // User session management — no AI inputs, no injection filter needed
    await instance.register(httpProxy, {
      upstream:      config.services.writing,
      prefix:        '/api/v1/user',
      rewritePrefix: '/api/v1/user',
      replyOptions: {
        rewriteRequestHeaders: (_req, headers) => ({
          ...headers, ...proxyHeaders(_req as FastifyRequest),
        }),
      },
    })

    // Writing evaluation — AI-bound, injection filter applied via preValidation
    await instance.register(httpProxy, {
      upstream:        config.services.writing,
      prefix:          '/api/v1/writing',
      rewritePrefix:   '/api/v1/writing',
      preValidation:   injectionGuard,   // ← runs before proxy, after JWT
      replyOptions: {
        rewriteRequestHeaders: (_req, headers) => ({
          ...headers, ...proxyHeaders(_req as FastifyRequest),
        }),
      },
    })

    // Speaking (Phase 2) — AI-bound
    await instance.register(httpProxy, {
      upstream:        config.services.writing,
      prefix:          '/api/v1/speaking',
      rewritePrefix:   '/api/v1/speaking',
      preValidation:   injectionGuard,
      replyOptions: {
        rewriteRequestHeaders: (_req, headers) => ({
          ...headers, ...proxyHeaders(_req as FastifyRequest),
        }),
      },
    })

    // Exam simulation (Phase 3) — has essay text fields
    await instance.register(httpProxy, {
      upstream:        config.services.writing,
      prefix:          '/api/v1/exam',
      rewritePrefix:   '/api/v1/exam',
      preValidation:   injectionGuard,
      replyOptions: {
        rewriteRequestHeaders: (_req, headers) => ({
          ...headers, ...proxyHeaders(_req as FastifyRequest),
        }),
      },
    })

    // Adaptive engine (Phase 2)
    await instance.register(httpProxy, {
      upstream:      config.services.adaptive,
      prefix:        '/api/v1/adaptive',
      rewritePrefix: '/api/v1/adaptive',
      replyOptions: {
        rewriteRequestHeaders: (_req, headers) => ({
          ...headers, ...proxyHeaders(_req as FastifyRequest),
        }),
      },
    })

    // Readiness engine (Phase 4)
    await instance.register(httpProxy, {
      upstream:      config.services.readiness,
      prefix:        '/api/v1/readiness',
      rewritePrefix: '/api/v1/readiness',
      replyOptions: {
        rewriteRequestHeaders: (_req, headers) => ({
          ...headers, ...proxyHeaders(_req as FastifyRequest),
        }),
      },
    })
  })

  // ---------------------------------------------------------------------------
  // Admin-only routes
  // ---------------------------------------------------------------------------
  await app.register(async (instance) => {
    instance.addHook('preHandler', instance.authenticate)
    instance.addHook('preHandler', requireRole(['admin']))

    await instance.register(httpProxy, {
      upstream:      config.services.writing,
      prefix:        '/calibration',
      rewritePrefix: '/calibration',
      replyOptions: {
        rewriteRequestHeaders: (_req, headers) => ({
          ...headers, ...proxyHeaders(_req as FastifyRequest),
        }),
      },
    })

    await instance.register(httpProxy, {
      upstream:      config.services.writing,
      prefix:        '/wer',
      rewritePrefix: '/wer',
      replyOptions: {
        rewriteRequestHeaders: (_req, headers) => ({
          ...headers, ...proxyHeaders(_req as FastifyRequest),
        }),
      },
    })
  })

  return app
}

// ---------------------------------------------------------------------------
// Graceful shutdown
// ---------------------------------------------------------------------------
async function gracefulShutdown(app: FastifyInstance, signal: string): Promise<void> {
  app.log.info(`${signal} received — starting graceful shutdown`)
  try {
    await app.close()
    await redis.quit()
    app.log.info('Gateway shutdown complete')
    process.exit(0)
  } catch (err) {
    app.log.error({ err }, 'Error during shutdown')
    process.exit(1)
  }
}

// ---------------------------------------------------------------------------
// Entry point
// ---------------------------------------------------------------------------
async function main(): Promise<void> {
  const app = await buildApp()

  process.on('SIGTERM', () => gracefulShutdown(app, 'SIGTERM'))
  process.on('SIGINT',  () => gracefulShutdown(app, 'SIGINT'))
  process.on('unhandledRejection', (reason) => {
    app.log.error({ reason }, 'Unhandled promise rejection')
    process.exit(1)
  })

  try {
    const address = await app.listen({ port: config.port, host: '0.0.0.0' })
    app.log.info(`API Gateway listening on ${address} [${config.env}]`)
  } catch (err) {
    app.log.error({ err }, 'Failed to start gateway')
    process.exit(1)
  }
}

main()
