# ── LinguaMentor API Gateway ─────────────────────────────────────────────
# Multi-stage build: Node 20 Alpine, Fastify front-door
# Exposes port 3000, connects to ai-service on localhost:8000
#
# Build context is the monorepo root. Source paths are prefixed with gateway/.

FROM node:20-alpine AS builder

WORKDIR /app
COPY gateway/package*.json ./
RUN npm ci --ignore-scripts

COPY gateway/tsconfig.json ./
COPY gateway/src/ ./src/
RUN npm run build

# ── Runtime image ───────────────────────────────────────────────────────
FROM node:20-alpine AS runner

WORKDIR /app

RUN apk add --no-cache tini
ENTRYPOINT ["/sbin/tini", "--"]

COPY --from=builder /app/dist        ./dist
COPY --from=builder /app/node_modules ./node_modules

EXPOSE 3000

USER node
CMD ["node", "dist/index.js"]
