import 'dotenv/config';
import type { Express } from 'express';
import { categoryApi } from './category/handlers';
import { articleApi } from './article/handlers';
import { languageApi } from './language/handlers';
import cors from 'cors';
import { voiceApi } from './voice/handlers';
import { tsApi } from './ts/handlers';
import { firebaseApi } from './firebase/handlers';
import { tagApi } from './tag/handlers';
import { collectionApi } from './collection/handlers';
import { assistantApi } from './assistant/handlers';
import { configApi } from './config/handlers';
import { userApi } from './user/handlers';
import { internalApi } from './internal/handlers';
import { activityApi } from './activity/handlers';
import { badgeApi } from './badge/handlers';
import { milestoneApi } from './milestone/handlers';

// CORS configuration that allows localhost and production
const corsOptions = {
  origin: (origin: string | undefined, callback: (err: Error | null, allow?: boolean) => void) => {
    const allowedOrigins = [
      'http://localhost:8081',
      'http://localhost:19006',
      'http://localhost:3000',
      'http://localhost:19000',
      'https://app.thinko.in',
      process.env.WEB_URL
    ].filter(Boolean);
    
    // Allow requests with no origin (like mobile apps or curl requests)
    if (!origin) {
      return callback(null, true);
    }
    
    // Allow localhost origins
    if (origin.includes('localhost') || origin.includes('127.0.0.1')) {
      return callback(null, true);
    }
    
    // Check if origin is in allowed list
    if (allowedOrigins.includes(origin)) {
      return callback(null, true);
    }
    
    callback(new Error('Not allowed by CORS'));
  },
  credentials: true
};

export function registerAppDbRoutes(app: Express) {
  console.log('Registering App DB routes...');

  app.use(cors(corsOptions));
  app.use('/api/tags', tagApi());
  app.use('/api/categories', categoryApi());
  app.use('/api/articles', articleApi());
  app.use('/api/collections', collectionApi());
  app.use('/api/languages', languageApi());
  app.use("/api/firebase", firebaseApi());
  app.use("/api/user", userApi());
  app.use('/api/assistant', assistantApi());
  app.use('/api/config', configApi());
  app.use('/api/internal', internalApi());
  app.use('/api/activity', activityApi());
  app.use('/api/badge', badgeApi());
  app.use('/api/milestone', milestoneApi());
  console.log('App DB routes registered successfully');
}

export function registerProcessingDbRoutes(app: Express) {
  // Processing DB routes can be added here later if needed
}

export function registerVoiceRoutes(app: Express) {
  console.log('Registering Open AI routes...');
  
  app.use(cors(corsOptions));
  
  app.use('/api/voice', voiceApi());
  console.log('Open AI routes registered successfully');
}

export function registerTsRoutes(app: Express) {
  console.log('Registering ts routes...');
  app.use(cors(corsOptions));
  // Route: Fetch Ts/Instagram Reels
  app.use("/api/ts", tsApi());
  console.log('ts routes registered successfully');
}