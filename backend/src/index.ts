/**
 * Application entry — start server and manage lifecycle (DB connect/disconnect)
 */
import { createApp } from './app';
import { prisma } from './prisma/client';
import { config } from './config/config';
import { createQueueService } from './services/queue.service';
import { initializeWorkers, shutdownWorkers, scheduleRecurringUsageTasks } from './workers/queue.worker';

// Create the queue service
const queueService = createQueueService(config.redis.url);

const app = createApp(queueService);

console.log('Starting server...');
const server = app.listen(config.PORT, async () => {
    console.log(`LinguaMentor backend listening on port ${config.PORT}`);
    try {
        await prisma.$connect();
        console.log('Connected to DB');
        // Initialize queue workers after DB connection
        initializeWorkers();
        await scheduleRecurringUsageTasks();
        console.log('Workers initialized');
    } catch (err) {
        console.error('DB connection failed', err);
        process.exit(1);
    }
});
console.log('Server started.');

// Proper shutdown
process.on('SIGINT', async () => {
    console.log('SIGINT received. Shutting down.');
    await prisma.$disconnect();
    await shutdownWorkers();
    server.close(() => process.exit(0));
});

// Handle unhandled promise rejections
process.on('unhandledRejection', (reason, promise) => {
    console.error('Unhandled Rejection at:', promise, 'reason:', reason);
});

// Handle uncaught exceptions
process.on('uncaughtException', (error) => {
    console.error('Uncaught Exception:', error);
    process.exit(1);
});

export default app;
