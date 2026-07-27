import { Router } from 'express';
import { verifyFirebaseToken } from '../firebase/verifyFirebaseToken';
import { registerDevice } from './registerDevice';
import { migrateUser, updateProfile } from './profile';
import { getMilestones } from './milestones';
import { getActivityDates } from './activityDates';

export function userApi(): Router {
  const router = Router();
  router.post("/register-device", verifyFirebaseToken, registerDevice)
  //used to update user interests, can be extended to update other profile info in the future
  router.post("/profile", verifyFirebaseToken, updateProfile)
  router.post("/migrate-user", verifyFirebaseToken, migrateUser)
  router.get("/milestones", verifyFirebaseToken, getMilestones)
  router.get("/activity-dates", verifyFirebaseToken, getActivityDates)

  return router;
}
