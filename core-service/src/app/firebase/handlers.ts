import { Router } from 'express';
import { getProfile } from './profile';
import { verifyFirebaseToken } from './verifyFirebaseToken';
import { registerDevice } from '../user/registerDevice';

export function firebaseApi(): Router {
  const router = Router();
  router.get("/auth/profile", verifyFirebaseToken, getProfile)
  // this will be rmeoved as its used to user
  router.post("/auth/register-device", verifyFirebaseToken, registerDevice)
  return router;
}
