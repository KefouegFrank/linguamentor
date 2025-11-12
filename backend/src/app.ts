import express, { Application, Request, Response, NextFunction } from 'express';
import cors from 'cors';
import helmet from 'helmet';
import authRoutes from './routes/auth.routes';
import fileRoutes from './routes/file.routes';
import jobRoutes from './routes/job.routes';
import { corsConfig } from './config/auth.config';
import { IS_DEVELOPMENT } from './config/config';
import type { QueueService } from './services/queue.service';

// Note: Environment variables are loaded in config/config.ts

export function createApp(_queueService?: QueueService): Application {
    const app = express();

    // Security
    app.use(helmet());
    app.use(cors(corsConfig));

    // Body parsers
    app.use(express.json({ limit: '10mb' }));
    app.use(express.urlencoded({ extended: true, limit: '10mb' }));

    // Dev request logging
    if (IS_DEVELOPMENT) {
        app.use((req: Request, _res: Response, next: NextFunction) => {
            console.log(`[${new Date().toISOString()}] ${req.method} ${req.path}`);
            next();
        });
    }

    // Mount routes
    app.use('/api/auth', authRoutes);
    app.use('/api/files', fileRoutes);
    app.use('/api/jobs', jobRoutes);

    // Health
    app.get('/health', (_req, res) => {
        res.status(200).json({ success: true, message: 'LinguaMentor API is running' });
    });

    // 404
    app.use((_req: Request, res: Response) => {
        res.status(404).json({ success: false, message: 'Route not found' });
    });

    // Global error handler
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    app.use((err: Error, _req: Request, res: Response, _next: NextFunction) => {
        console.error('Unhandled error:', err);
        res.status(500).json({ success: false, message: 'Internal server error' });
    });

    return app;
}

export default createApp;
