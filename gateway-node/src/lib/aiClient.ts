/**
 * Internal AI Service Communication Client
 * Handles point-to-point HTTP requests to the isolated Python AI Monolith.
 */
export const aiClient = {
  async request(endpoint: string, method: 'GET' | 'POST', queryParams?: Record<string, string>) {
    const aiServiceUrl = process.env.AI_SERVICE_URL || 'http://127.0.0.1:8000';
    
    // Construct target URL safely along with query string mapping
    const url = new URL(`${aiServiceUrl}${endpoint}`);
    if (queryParams) {
      Object.entries(queryParams).forEach(([key, val]) => url.searchParams.append(key, val));
    }

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
      });

      clearTimeout(id);

      if (!response.ok) {
        throw new Error(`AI Monolith responded with status code: ${response.status}`);
      }

      return await response.json();
    } catch (error: any) {
      clearTimeout(id);
      throw new Error(`Failed to bridge connection to internal AI Service: ${error.message}`);
    }
  },
};