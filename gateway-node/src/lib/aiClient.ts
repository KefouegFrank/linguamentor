/**
 * Internal AI Service Communication Client
 * Handles point-to-point HTTP requests to the isolated Python AI Monolith.
 */

import { Prisma } from '@prisma/client';

export const aiClient = {
  async request<T = Prisma.InputJsonValue>(
    endpoint: string,
    method: 'GET' | 'POST',
    body?: Record<string, unknown>
  ): Promise<T> {
    const aiServiceUrl = process.env.AI_SERVICE_URL || 'http://127.0.0.1:8000';
    const url = new URL(`${aiServiceUrl}${endpoint}`);

    // Enforce an explicit 10-second timeout circuit breaker
    const controller = new AbortController();
    const id = setTimeout(() => controller.abort(), 10000);

    try {
      const response = await fetch(url.toString(), {
        method,
        signal: controller.signal,
        headers: {
          'Content-Type': 'application/json',
        },
        body: method === 'POST' && body ? JSON.stringify(body) : undefined,
      });

      clearTimeout(id);

      if (!response.ok) {
        const errorBody = await response.text();
        console.error(`[AI Monolith 422 Debug] Detailed Response Layer:`, errorBody);

        throw new Error(`AI Monolith responded with status code: ${response.status} | | Details: ${errorBody}`);
      }

      return (await response.json()) as T;
    } catch (error: any) {
      clearTimeout(id);
      throw new Error(`Failed to bridge connection to internal AI Service: ${error.message}`);
    }
  },
};