import { Router } from 'express';
import { getConfig } from './getConfig';
import { verifyFirebaseToken } from '../firebase/verifyFirebaseToken';

export function configApi() {
  const router = Router();
  router.get('/:key',verifyFirebaseToken, getConfig);
  return router;
}
