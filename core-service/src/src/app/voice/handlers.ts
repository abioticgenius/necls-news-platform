import { Router } from 'express';
import { transcribe } from './transcribe';
import multer from 'multer';
import { verifyFirebaseToken } from '../firebase/verifyFirebaseToken';

const upload = multer({ storage: multer.memoryStorage() });

export function voiceApi(): Router {
  const router = Router();
  
  router.post('/transcribe', verifyFirebaseToken, upload.single('file'), transcribe);
  
  return router;
}
