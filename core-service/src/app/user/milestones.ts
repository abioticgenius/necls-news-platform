import { Request, Response } from 'express';
import { User, UserMilestones } from '../../db/app-db/models/user.model';
import { calculateStreak } from '../activity/track';

const INITIAL_MILESTONES: UserMilestones = {
  streak: {
    current: 0,
    rest_days_used_this_week: 0,
    last_activity_date: null,
  },
  articles_read: { total: 0 },
  shares_made: { total: 0 },
  assistant_queries: { total: 0 },
};

export async function getMilestones(req: Request, res: Response) {
  try {
    const { uid } = req?.user || {};

    if (!uid) {
      return res.status(401).json({ error: 'Unauthorized' });
    }

    const user = await User.findOne({ where: { uid } });
    if (!user) {
      return res.status(404).json({ error: 'User not found' });
    }

    // If user.milestones is null, initialize it
    if (!user.milestones) {
      user.milestones = JSON.parse(JSON.stringify(INITIAL_MILESTONES));

      // Recalculate streak from activity_dates
      if (user.activity_dates && user.activity_dates.length > 0) {
        const { current, restDaysUsedThisWeek } = calculateStreak(user.activity_dates);
        const milestones = user.milestones!;
        milestones.streak.current = current;
        milestones.streak.rest_days_used_this_week = restDaysUsedThisWeek;
        milestones.streak.last_activity_date = user.activity_dates[user.activity_dates.length - 1] || null;
      }

      await user.save();
    }

    res.json(user.milestones!);
  } catch (error) {
    console.error('Error fetching milestones', error);
    res.status(500).json({ error: 'Failed to fetch milestones' });
  }
}
