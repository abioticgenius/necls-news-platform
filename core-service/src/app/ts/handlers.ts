import { Router } from 'express';
import { getReels } from './reels';
import { verifyFirebaseToken } from '../firebase/verifyFirebaseToken';
import { getShorts } from './shorts';

export function tsApi(): Router {
  const router = Router();
  router.get('/reels', verifyFirebaseToken, getReels);
  router.get('/shorts', verifyFirebaseToken, getShorts);
  return router;
}
