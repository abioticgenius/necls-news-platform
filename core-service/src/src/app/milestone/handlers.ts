import { Request, Response, Router } from 'express';
import { User } from '../../db/app-db/models/user.model';
import { getMilestoneInfo } from './milestone-config';
import { verifyFirebaseToken } from '../firebase/verifyFirebaseToken';

/**
 * GET /api/milestone/progress
 * Returns detailed milestone information for the current user including levels and messages
 */
export async function getMilestoneProgress(req: Request, res: Response) {
  try {
    const uid = req.user?.uid;
    if (!uid) {
      return res.status(401).json({ error: 'Unauthorized' });
    }

    const user = await User.findOne({ where: { uid } });
    if (!user) {
      return res.status(404).json({ error: 'User not found' });
    }

    // Initialize milestones if null
    if (!user.milestones) {
      user.milestones = {
        streak: {
          current: 0,
          rest_days_used_this_week: 0,
          last_activity_date: null,
        },
        articles_read: { total: 0 },
        shares_made: { total: 0 },
        assistant_queries: { total: 0 },
      };
    }

    // Get milestone information
    const milestoneInfo = getMilestoneInfo(user.milestones);

    return res.json({
      milestones: user.milestones,
      milestoneInfo,
    });
  } catch (error) {
    console.error('[getMilestoneProgress]', error);
    return res.status(500).json({ error: 'Internal server error' });
  }
}

export function milestoneApi(): Router {
  const router = Router();
  router.get('/progress', verifyFirebaseToken, getMilestoneProgress);
  return router;
}
