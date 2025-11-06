/**
 * Application entry — start server and manage lifecycle (DB connect/disconnect)
 */
import { createApp } from './app';
import { prisma } from './prisma/client';
import { PORT } from './config/config';

const app = createApp();

const server = app.listen(PORT, async () => {
    console.log(`LinguaMentor backend listening on port ${PORT}`);
    try {
        await prisma.$connect();
        console.log('Connected to DB');
    } catch (err) {
        console.error('DB connection failed', err);
        process.exit(1);
    }
});

// Proper shutdown
process.on('SIGINT', async () => {
    console.log('SIGINT received. Shutting down.');
    await prisma.$disconnect();
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