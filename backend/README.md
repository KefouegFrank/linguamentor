# LinguaMentor Backend

Node.js + TypeScript backend with authentication, PostgreSQL, and Docker support.

## 🚀 Quick Start

### Prerequisites
- Node.js 20+
- pnpm (or npm/yarn)
- Docker & Docker Compose (for containerized development)

### Local Development (Without Docker)

1. **Install dependencies**
   ```bash
   pnpm install
   ```

2. **Set up environment**
   ```bash
   # Copy example file
   cp .env.example .env.local
   
   # Edit .env.local and set DATABASE_URL to use localhost:
   # DATABASE_URL=postgresql://linguamentor_user:securepass@localhost:5432/linguamentor_db?schema=public
   ```

3. **Start database (using Docker)**
   ```bash
   pnpm run db:up
   ```

4. **Generate Prisma client**
   ```bash
   pnpm run prisma:generate
   ```

5. **Run migrations** (if needed)
   ```bash
   pnpm run prisma:migrate
   ```

6. **Start development server**
   ```bash
   pnpm run dev
   ```

### Docker Development

1. **Set up environment**
   ```bash
   # Copy example file
   cp .env.example .env
   
   # Edit .env and ensure DATABASE_URL uses 'db' hostname:
   # DATABASE_URL=postgresql://linguamentor_user:securepass@db:5432/linguamentor_db?schema=public
   ```

2. **Start all services**
   ```bash
   pnpm run dev:docker
   # Or with rebuild:
   pnpm run dev:docker:build
   ```

3. **Stop services**
   ```bash
   pnpm run dev:docker:down
   ```

### Production

1. **Build for production**
   ```bash
   pnpm run build:prod
   ```

2. **Start production server**
   ```bash
   pnpm run start:prod
   ```

3. **Docker Production**
   ```bash
   # Create .env.production with production values
   cp .env.example .env.production
   # Edit .env.production with production secrets
   
   # Start production stack
   pnpm run prod:docker:build
   ```

## 📁 Project Structure

```
backend/
├── src/
│   ├── config/          # Configuration (env, auth, etc.)
│   ├── controllers/     # Request handlers
│   ├── middleware/      # Express middleware
│   ├── routes/          # API routes
│   ├── services/        # Business logic
│   ├── types/           # TypeScript types
│   ├── utils/           # Utility functions
│   ├── validation/      # Zod schemas
│   └── prisma/          # Prisma client
├── prisma/
│   └── schema.prisma    # Database schema
├── docker-compose.dev.yml   # Development Docker setup
├── docker-compose.prod.yml  # Production Docker setup
└── .env.example         # Environment template
```

## 🔧 Environment Configuration

### Environment Files Priority

1. `.env.local` (highest priority - for local development)
2. `.env` (default - for Docker development)
3. `.env.production` (for production)

### Required Variables

```env
# Server
NODE_ENV=development
PORT=4000

# Database
DATABASE_URL=postgresql://user:password@host:5432/database?schema=public

# JWT
JWT_ACCESS_SECRET=your-secret-key
JWT_REFRESH_SECRET=your-refresh-secret
JWT_ISSUER=lingumentor-api
JWT_AUDIENCE=lingumentor-users

# Bcrypt
BCRYPT_SALT_ROUNDS=12

# CORS
CORS_ORIGIN=http://localhost:3000,http://localhost:4000
```

### Database Connection

- **Local Development**: Use `localhost` as host
  ```env
  DATABASE_URL=postgresql://linguamentor_user:securepass@localhost:5432/linguamentor_db?schema=public
  ```

- **Docker Development**: Use `db` as host (service name)
  ```env
  DATABASE_URL=postgresql://linguamentor_user:securepass@db:5432/linguamentor_db?schema=public
  ```

- **Production**: Use your production database URL
  ```env
  DATABASE_URL=postgresql://user:password@prod-host:5432/database?schema=public
  ```

## 📜 Available Scripts

### Development
- `pnpm run dev` - Start local dev server
- `pnpm run dev:docker` - Start Docker dev environment
- `pnpm run dev:docker:build` - Rebuild and start Docker dev
- `pnpm run dev:docker:down` - Stop Docker dev environment

### Database
- `pnpm run db:up` - Start database container only
- `pnpm run db:down` - Stop database container
- `pnpm run db:logs` - View database logs
- `pnpm run prisma:generate` - Generate Prisma client
- `pnpm run prisma:migrate` - Run database migrations
- `pnpm run prisma:studio` - Open Prisma Studio

### Production
- `pnpm run build:prod` - Build for production
- `pnpm run start:prod` - Start production server
- `pnpm run prod:docker` - Start production Docker stack
- `pnpm run prod:docker:build` - Rebuild and start production
- `pnpm run prod:docker:down` - Stop production stack

### Code Quality
- `pnpm run lint` - Run ESLint
- `pnpm run format` - Format code with Prettier

## 🔐 Authentication

The backend implements JWT-based authentication with:
- Access tokens (short-lived, 15 minutes)
- Refresh tokens (long-lived, 7 days)
- Token rotation on refresh
- Rate limiting on login/refresh endpoints
- Account lockout after failed attempts

### API Endpoints

- `POST /api/auth/register` - Register new user
- `POST /api/auth/login` - Login user
- `POST /api/auth/refresh` - Refresh access token
- `POST /api/auth/logout` - Logout (revoke refresh token)
- `GET /api/auth/me` - Get current user (protected)

## 🐳 Docker

### Development Stack
- PostgreSQL 16 (Alpine)
- Node.js 20 (Alpine)
- Hot-reload enabled
- Volume mounts for live code changes

### Production Stack
- Optimized multi-stage build
- Production dependencies only
- Health checks
- Restart policies

## 🛠️ Troubleshooting

### Database Connection Issues

**Error**: `Can't reach database server at 'db':5432`

**Solution**: 
- If running locally: Use `localhost` in DATABASE_URL
- If running in Docker: Ensure database service is running and use `db` as hostname
- Check database container: `docker ps`
- View database logs: `pnpm run db:logs`

### Prisma Client Not Found

**Solution**:
```bash
pnpm run prisma:generate
```

### Port Already in Use

**Solution**: Change PORT in `.env` or stop the conflicting service

## 📝 Notes

- Environment variables are loaded automatically with priority: `.env.local` > `.env` > `.env.production`
- The config system automatically detects Docker vs local environment
- Prisma client is generated before TypeScript compilation
- All sensitive files (`.env*`) are gitignored except `.env.example`
