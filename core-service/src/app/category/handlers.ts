import { Router } from 'express';
import { getAllCategories } from './getAll';
import { verifyFirebaseToken } from '../firebase/verifyFirebaseToken';

export function categoryApi() {
  const router = Router();
  router.get('/', verifyFirebaseToken, getAllCategories);
  return router;
}
