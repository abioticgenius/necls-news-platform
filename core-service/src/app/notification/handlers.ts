import { Router, Response } from 'express';

export function notificationApi(): Router {
  const router = Router();

  // Placeholder for public notification endpoints if needed in the future
  router.get('/health', (_, res: Response) => {
    res.json({ status: 'ok' });
  });

  return router;
}
