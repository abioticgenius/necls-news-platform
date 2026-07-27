import { User, UserMilestones } from '../../db/app-db/models/user.model';
import { calculateEarnedBadges } from '../badge/badge-config';

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

function getMonday(date: Date): Date {
  const d = new Date(date);
  d.setHours(0, 0, 0, 0);
  const day = d.getDay();
  const diff = day === 0 ? -6 : 1 - day;
  d.setDate(d.getDate() + diff);
  return d;
}

function formatDateOnly(date: Date): string {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

export function calculateStreak(activityDates: string[] | null): {
  current: number;
  restDaysUsedThisWeek: number;
  usedRestDays: string[];
} {
  if (!activityDates || activityDates.length === 0) {
    return { current: 0, restDaysUsedThisWeek: 0, usedRestDays: [] };
  }

  const dates = new Set(activityDates);
  const today = new Date();
  today.setHours(0, 0, 0, 0);

  let streak = 0;
  let checkDate = new Date(today);
  let currentWeekMonday = getMonday(today);
  let restUsedInCheckWeek = 0;
  const usedRestDays: string[] = [];
  let restDaysUsedThisWeek = 0;
  let foundFirstActivity = false;

  for (let i = 0; i < 800; i++) {
    const dateStr = formatDateOnly(checkDate);

    // Check if we've crossed into a new week
    if (checkDate < currentWeekMonday) {
      currentWeekMonday = getMonday(checkDate);
      restUsedInCheckWeek = 0;
    }

    if (dates.has(dateStr)) {
      // Active day
      foundFirstActivity = true;
      streak++;
    } else {
      // Inactive day
      if (!foundFirstActivity) {
        // Haven't found any activity yet, stop
        break;
      }

      if (restUsedInCheckWeek < 1) {
        // Check if there are more inactive days earlier in this week
        // If yes, save rest day for the earlier/more important gap
        let hasMoreInactiveDaysInWeek = false;
        const checkTemp = new Date(checkDate);
        checkTemp.setDate(checkTemp.getDate() - 1);
        while (checkTemp >= currentWeekMonday) {
          if (!dates.has(formatDateOnly(checkTemp))) {
            hasMoreInactiveDaysInWeek = true;
            break;
          }
          checkTemp.setDate(checkTemp.getDate() - 1);
        }

        if (hasMoreInactiveDaysInWeek) {
          // Save rest day for the earlier gap, not this one
          break;
        }

        // No more gaps in this week, use rest day for this one
        restUsedInCheckWeek++;
        usedRestDays.push(dateStr);
        if (checkDate >= getMonday(today) && checkDate <= today) {
          restDaysUsedThisWeek++;
        }
      } else {
        // No rest day available for this week → streak ends
        break;
      }
    }

    // Move to previous day
    checkDate.setDate(checkDate.getDate() - 1);
  }

  // Remove trailing rest day if it has no activity before it
  if (usedRestDays.length > 0) {
    const dayAfterStop = new Date(checkDate);
    dayAfterStop.setDate(dayAfterStop.getDate() + 1);
    const dayAfterStopStr = formatDateOnly(dayAfterStop);

    if (usedRestDays[usedRestDays.length - 1] === dayAfterStopStr) {
      usedRestDays.pop();
      if (dayAfterStop >= getMonday(today) && dayAfterStop <= today) {
        restDaysUsedThisWeek--;
      }
    }
  }

  // Post-process: identify gaps that should have rest days for display
  // For each gap between activity periods, mark the first missed day of each week as a rest day
  const sortedActivityDates = [...activityDates].sort();
  for (let i = 0; i < sortedActivityDates.length - 1; i++) {
    const currentDate = new Date(sortedActivityDates[i] + 'T00:00:00');
    const nextDate = new Date(sortedActivityDates[i + 1] + 'T00:00:00');
    const nextDay = new Date(currentDate);
    nextDay.setDate(nextDay.getDate() + 1);

    // Find gap between consecutive activity dates
    if (nextDay >= nextDate) continue;

    const weekRestDays = new Map<string, string>(); // weekMonday -> first missed day in that week
    let checkGapDate = new Date(nextDay);
    while (checkGapDate < nextDate) {
      const gapDateStr = formatDateOnly(checkGapDate);
      if (!usedRestDays.includes(gapDateStr)) {
        const weekMonday = formatDateOnly(getMonday(checkGapDate));
        if (!weekRestDays.has(weekMonday)) {
          weekRestDays.set(weekMonday, gapDateStr);
        }
      }
      checkGapDate.setDate(checkGapDate.getDate() + 1);
    }

    // Add first missed day of each week as rest day (for display)
    for (const restDay of weekRestDays.values()) {
      if (!usedRestDays.includes(restDay) && new Date(restDay + 'T00:00:00') <= today) {
        usedRestDays.push(restDay);
        const restDayDate = new Date(restDay + 'T00:00:00');
        if (restDayDate >= getMonday(today) && restDayDate <= today) {
          restDaysUsedThisWeek++;
        }
      }
    }
  }

  return {
    current: streak,
    restDaysUsedThisWeek,
    usedRestDays,
  };
}

export async function recordActivity(
  user: User,
  type: 'article_read' | 'take_shared' | 'assistant_query'
): Promise<UserMilestones> {
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const todayStr = formatDateOnly(today);

  // Initialize milestones if null
  if (!user.milestones) {
    user.milestones = JSON.parse(JSON.stringify(INITIAL_MILESTONES));
  }

  // Add today to activity_dates if not already there
  if (!user.activity_dates) {
    user.activity_dates = [];
  }
  if (!user.activity_dates.includes(todayStr)) {
    user.activity_dates.push(todayStr);
  }

  // Increment the relevant counter
  const milestones = user.milestones!;
  switch (type) {
    case 'article_read':
      milestones.articles_read.total += 1;
      break;
    case 'take_shared':
      milestones.shares_made.total += 1;
      break;
    case 'assistant_query':
      milestones.assistant_queries.total += 1;
      break;
  }

  // Recalculate streak
  const { current, restDaysUsedThisWeek } = calculateStreak(user.activity_dates);
  milestones.streak.current = current;
  milestones.streak.rest_days_used_this_week = restDaysUsedThisWeek;
  milestones.streak.last_activity_date = user.activity_dates[user.activity_dates.length - 1] || null;

  // Calculate earned badges based on milestones
  const earnedBadges = calculateEarnedBadges(milestones);
  user.earned_badges = earnedBadges;

  // Mark JSONB fields as changed so Sequelize persists them
  user.changed('milestones', true);
  user.changed('activity_dates', true);
  user.changed('earned_badges', true);

  // Save user
  await user.save();

  return milestones;
}
