import { Router, Request, Response } from 'express';
import { getAllTags, getContextualTags } from './getAll';
import { verifyFirebaseToken } from '../firebase/verifyFirebaseToken';

// Express handler for assistant query
async function getTags(req: Request, res: Response) {
  return getContextualTags(req, res);
}
export function tagApi() {
  const router = Router();
  router.get('/', verifyFirebaseToken, getAllTags);
  router.post('/contextual', verifyFirebaseToken, getTags);
  return router;
}
