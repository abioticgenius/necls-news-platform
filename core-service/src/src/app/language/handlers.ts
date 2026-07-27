import { Router } from 'express';
import { getAllLanguages } from './getAll';
import { verifyFirebaseToken } from '../firebase/verifyFirebaseToken';

export function languageApi(): Router {
  const router = Router();
  
  // GET /api/languages - Get all languages
  router.get('/', verifyFirebaseToken, getAllLanguages);
  
  return router;
}
