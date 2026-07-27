import { Router } from 'express';
import { deleteCollection, getCollectionById, getRecommendedCollections, getThinkoCollections, getUserCollections, previewCollection, saveCollection } from './functions';
import { verifyFirebaseToken } from '../firebase/verifyFirebaseToken';

export function collectionApi() {
  const router = Router();
  router.post('/save', verifyFirebaseToken, saveCollection);
  router.delete('/delete/:id', verifyFirebaseToken, deleteCollection);
  router.get('/', verifyFirebaseToken, getUserCollections);
  router.get('/thinko', verifyFirebaseToken, getThinkoCollections);
  router.get('/recommended', verifyFirebaseToken, getRecommendedCollections);
  router.get('/:id', verifyFirebaseToken, getCollectionById);
  router.post('/preview', verifyFirebaseToken, previewCollection );
  return router;
}
