import { Worker, Job } from 'bullmq';
import * as dotenv from 'dotenv';
import * as path from 'path';

dotenv.config({ path: path.resolve(__dirname, '../../.env') });

const queueName = 'evaluation-queue';

const redisConnection = {
  host: process.env.REDIS_HOST || '127.0.0.1',
  port: Number(process.env.REDIS_PORT) || 6379,
};

// Explicit type contract defining safe job structures
interface EvaluationJobPayload {
  userId: string;
  assetId: string;
  examType: 'IELTS' | 'TOEFL' | 'DELF';
}

const worker = new Worker<EvaluationJobPayload>(
  queueName,
  async (job: Job<EvaluationJobPayload>) => {
    console.log(`[Worker] Executing Job ID: ${job.id} | Name: ${job.name}`);
    console.log(`[Worker] Payload Data:`, job.data);

    // Business context validation logic will plug in here
    // Example: dispatching network request to Python AI execution service
    
    return { success: true, processedAt: new Date().toISOString() };
  },
  {
    connection: redisConnection,
    concurrency: 5, // Defensive concurrency wall for solo resource constraint
  }
);

// Global Event Listeners for Operational Visibility
worker.on('completed', (job) => {
  console.log(`[Worker OK] Job ${job.id} completed flawlessly.`);
});

worker.on('failed', (job, err) => {
  console.error(`[Worker ERROR] Job ${job?.id} crashed with reason: ${err.message}`);
});

// Graceful Lifecycle Teardown
const gracefulShutdown = async (signal: string) => {
  console.log(`[Worker] Received ${signal}, closing consumer connections cleanly...`);
  await worker.close();
  process.exit(0);
};

process.on('SIGTERM', () => gracefulShutdown('SIGTERM'));
process.on('SIGINT', () => gracefulShutdown('SIGINT'));

console.log(`[Worker Monolith Engine] Actively monitoring Redis Stream: "${queueName}"`);