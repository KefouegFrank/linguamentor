FROM node:20-alpine AS deps
WORKDIR /app
COPY package.json pnpm-lock.yaml* ./
RUN npm install -g pnpm && pnpm install --frozen-lockfile
FROM node:20-alpine AS runner
WORKDIR /app
COPY --from=deps /app /app
EXPOSE 3000
CMD ["pnpm","dev"]
