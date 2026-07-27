import { Request, Response, Router } from 'express';
import { User } from '../../db/app-db/models/user.model';
import { verifyFirebaseToken } from '../firebase/verifyFirebaseToken';
import { calculateEarnedBadges } from './badge-config';

export async function getEarnedBadgesHandler(req: Request, res: Response) {
  try {
    const { uid } = req.user || {};

    if (!uid) {
      return res.status(401).json({ error: 'Unauthorized' });
    }

    const user = await User.findOne({ where: { uid } });
    if (!user) {
      return res.status(404).json({ error: 'User not found' });
    }

    // If user has no earned_badges yet, calculate them
    if (!user.earned_badges || user.earned_badges.length === 0) {
      if (user.milestones) {
        const earnedBadges = calculateEarnedBadges(user.milestones);
        user.earned_badges = earnedBadges;
        await user.save();
      } else {
        user.earned_badges = [];
      }
    }

    return res.json({
      earned_badges: user.earned_badges || [],
    });
  } catch (error) {
    console.error('Error getting earned badges:', error);
    res.status(500).json({ error: 'Failed to get earned badges' });
  }
}

export function badgeApi(): Router {
  const router = Router();
  router.get('/earned', verifyFirebaseToken, getEarnedBadgesHandler);
  return router;
}
