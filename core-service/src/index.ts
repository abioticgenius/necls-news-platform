import dotenv from 'dotenv';
import express, { Request, Response } from 'express';
import type { Sequelize } from 'sequelize';
import { registerAppDbRoutes, registerVoiceRoutes, registerProcessingDbRoutes, registerTsRoutes } from './app';
import { AppDbModels, initAppDb } from './db/app-db';
import { initProcessingDb, ProcessingDbModels } from './db/processing-db';
import { startTrendingScheduler } from './app/assistant/trending-scheduler';
import { warmupEmbedder } from './app/assistant/embedder';

dotenv.config();
let appDbModels: AppDbModels;
let appDbSequelize: Sequelize;
let processingDbModels: ProcessingDbModels;
let processingDb: Sequelize;

const app = express();
app.use(express.json());

// Add request logging middleware
app.use((req, res, next) => {
  console.log(`[${new Date().toISOString()}] ${req.method} ${req.path}`);
  console.log('Query params:', req.query);
  console.log('Body:', req.body);

  // Set sequelize for handlers that need the
  req.appDbSequelize = appDbSequelize;
  next();
});

app.get('/categories', async (req: Request, res: Response) => {
    try {
        const categories = await appDbModels.Category.findAll();
        res.json(categories);
    } catch (err) {
        console.error('Error in GET /categories:', err);
        res.status(500).json({ error: 'Failed to fetch categories' });
    }
});

const PORT = Number(process.env.PORT) || 7090;


async function startServer() {
    try {
        const appDbResult = await initAppDb();
        appDbSequelize = appDbResult.sequelize;
        appDbModels = appDbResult.models;
        
        // Initialize processing database only if environment variables are provided
        //if (process.env.PROCESSING_DB_HOST) {
        //    try {
        //        const processingDbResult = await initProcessingDb();
        //        processingDb = processingDbResult.sequelize;
        //        processingDbModels = processingDbResult.models;
        //        registerProcessingDbRoutes(app);
        //        console.log('Processing Database initialized successfully!');
        //    } catch (err) {
        //        const errorMessage = err instanceof Error ? err.message : 'Unknown error';
        //        console.warn('Processing Database initialization failed, continuing without it:', errorMessage);
        //    }
        //} else {
        //    console.log('Processing Database environment variables not provided, skipping initialization.');
        //}

        // Register all API routes
        registerAppDbRoutes(app);
        registerVoiceRoutes(app);
        registerTsRoutes(app);

        // Start trending tags scheduler (runs every 24 hours)
        if (process.env.OPENAI_API_KEY) {
            // startTrendingScheduler(appDbModels, appDb, process.env.OPENAI_API_KEY);
            // console.log('Trending tags scheduler started.');
        } else {
            console.warn('OPENAI_API_KEY not found, skipping trending tags scheduler.');
        }

        // Add health check endpoint
        app.get('/health', (req: Request, res: Response) => {
            res.status(200).json({ 
                status: 'healthy', 
                timestamp: new Date().toISOString(),
                version: process.env.npm_package_version || '1.0.1',
                uptime: process.uptime()
            });
        });

        // Warm up the embedding model in the background so the first query is fast
        warmupEmbedder();

        console.log('Connections to both databases have been established successfully.');
        app.listen(PORT, '0.0.0.0', () => {
            console.log(`Express server running on 0.0.0.0:${PORT}`);
        });
    } catch (err) {
        console.error('Unable to connect to the databases:', err);
    }
}

startServer();
