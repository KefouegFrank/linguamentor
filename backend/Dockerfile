# Build stage (also used for development)
FROM node:20-alpine AS builder

# Install the exact pnpm version specified in package.json
RUN corepack enable && corepack prepare pnpm@10.20.0 --activate

WORKDIR /app

# Copy dependency files
COPY package.json pnpm-lock.yaml ./

# Install ALL dependencies (including devDependencies for TypeScript compilation)
RUN pnpm install --frozen-lockfile

# Copy source code
COPY . .

# Build TypeScript
RUN pnpm build

# Development stage (stops here for dev)
FROM builder AS development
EXPOSE 4000
CMD ["pnpm", "dev"]

# Production stage
FROM node:20-alpine AS production

# Install the exact pnpm version
RUN corepack enable && corepack prepare pnpm@10.20.0 --activate

WORKDIR /app

# Copy dependency files
COPY package.json pnpm-lock.yaml ./

# Install ONLY production dependencies
RUN pnpm install --frozen-lockfile --prod

# Copy built application from builder
COPY --from=builder /app/dist ./dist

# Create non-root user and set ownership
RUN addgroup -S app && adduser -S app -G app && \
    chown -R app:app /app

# Switch to non-root user
USER app

EXPOSE 4000

CMD ["node", "dist/index.js"]