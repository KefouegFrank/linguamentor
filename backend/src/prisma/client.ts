// src/prisma/client.ts
import { PrismaClient } from "@prisma/client";

/*
  Single PrismaClient instance for the app lifecycle.
  Uses `globalThis` instead of a custom `global` alias so it's
  portable across environments and avoids TypeScript/Node global issues.
  Caches the client during development to prevent multiple instances
  when using hot-reload (e.g., ts-node-dev, nodemon, Next.js dev mode).
*/

declare global {
    var prisma: PrismaClient | undefined;
}

export const prisma =
    globalThis.prisma ??
    new PrismaClient({
        log: ["query", "warn", "error"],
    });

if (process.env.NODE_ENV !== "production") {
    globalThis.prisma = prisma;
}
