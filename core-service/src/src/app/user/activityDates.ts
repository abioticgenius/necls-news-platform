import { Request, Response } from 'express';
import { User } from '../../db/app-db/models/user.model';
import { calculateStreak } from '../activity/track';

export async function getActivityDates(req: Request, res: Response) {
  try {
    const { uid } = req?.user || {};
    const monthParam = (req.query.month as string) || getCurrentMonth();

    if (!uid) {
      return res.status(401).json({ error: 'Unauthorized' });
    }

    const user = await User.findOne({ where: { uid } });
    if (!user) {
      return res.status(404).json({ error: 'User not found' });
    }

    // Calculate streak to get usedRestDays
    const { current: currentStreak, usedRestDays } = calculateStreak(user.activity_dates);

    // Parse month (YYYY-MM format)
    const [year, month] = monthParam.split('-').map(Number);
    const monthStart = new Date(year, month - 1, 1);
    const monthEnd = new Date(year, month, 0);

    // Filter activity_dates and usedRestDays to requested month
    const activeDaysInMonth: number[] = [];
    const restDaysInMonth: number[] = [];

    if (user.activity_dates) {
      user.activity_dates.forEach((dateStr) => {
        const date = new Date(dateStr + 'T00:00:00');
        if (date >= monthStart && date <= monthEnd) {
          activeDaysInMonth.push(date.getDate());
        }
      });
    }

    usedRestDays.forEach((dateStr) => {
      const date = new Date(dateStr + 'T00:00:00');
      if (date >= monthStart && date <= monthEnd) {
        restDaysInMonth.push(date.getDate());
      }
    });

    // Get current day (if it's in the requested month)
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    const currentDay = today >= monthStart && today <= monthEnd ? today.getDate() : null;

    res.json({
      month: monthParam,
      active_days: activeDaysInMonth,
      rest_days: restDaysInMonth,
      current_day: currentDay,
      current_streak: currentStreak,
    });
  } catch (error) {
    console.error('Error fetching activity dates', error);
    res.status(500).json({ error: 'Failed to fetch activity dates' });
  }
}

function getCurrentMonth(): string {
  const now = new Date();
  const year = now.getFullYear();
  const month = String(now.getMonth() + 1).padStart(2, '0');
  return `${year}-${month}`;
}
