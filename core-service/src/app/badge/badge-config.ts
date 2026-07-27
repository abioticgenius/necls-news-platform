/**
 * Badge unlock thresholds based on user milestones
 * Each badge has a threshold that must be met to unlock it
 */

export interface BadgeThreshold {
  id: number;
  title: string;
  category: 'Streaks' | 'Stories' | 'Shares' | 'AI_ASKS';
  threshold: number;
  milestoneField: 'streak.current' | 'articles_read.total' | 'shares_made.total' | 'assistant_queries.total';
  description: string;
}

export const BADGE_THRESHOLDS: BadgeThreshold[] = [
  // STREAKS BADGES
  {
    id: 1,
    title: 'IGNITE',
    category: 'Streaks',
    threshold: 3,
    milestoneField: 'streak.current',
    description: 'Start a 3-day streak',
  },
  {
    id: 2,
    title: 'SPARK',
    category: 'Streaks',
    threshold: 7,
    milestoneField: 'streak.current',
    description: 'Maintain a 7-day streak',
  },
  {
    id: 3,
    title: 'PRO',
    category: 'Streaks',
    threshold: 21,
    milestoneField: 'streak.current',
    description: 'Keep a 21-day streak going',
  },
  {
    id: 4,
    title: 'DIAMOND',
    category: 'Streaks',
    threshold: 75,
    milestoneField: 'streak.current',
    description: 'Achieve a 75-day streak',
  },
  {
    id: 5,
    title: 'CENTURY',
    category: 'Streaks',
    threshold: 100,
    milestoneField: 'streak.current',
    description: 'Reach a 100-day streak',
  },
  {
    id: 6,
    title: 'SAGE',
    category: 'Streaks',
    threshold: 365,
    milestoneField: 'streak.current',
    description: 'Complete a full year of streaks',
  },

  // STORIES BADGES
  {
    id: 7,
    title: 'STARTER',
    category: 'Stories',
    threshold: 10,
    milestoneField: 'articles_read.total',
    description: 'Read 10 stories',
  },
  {
    id: 8,
    title: 'INFORMED',
    category: 'Stories',
    threshold: 50,
    milestoneField: 'articles_read.total',
    description: 'Read 50 stories',
  },
  {
    id: 9,
    title: 'WELL READ',
    category: 'Stories',
    threshold: 200,
    milestoneField: 'articles_read.total',
    description: 'Read 200 stories',
  },
  {
    id: 10,
    title: 'NEWS ROOM',
    category: 'Stories',
    threshold: 500,
    milestoneField: 'articles_read.total',
    description: 'Read 500 stories',
  },
  {
    id: 11,
    title: 'ORACLE',
    category: 'Stories',
    threshold: 1000,
    milestoneField: 'articles_read.total',
    description: 'Read 1000 stories',
  },

  // SHARES BADGES
  {
    id: 12,
    title: 'ORIGIN',
    category: 'Shares',
    threshold: 1,
    milestoneField: 'shares_made.total',
    description: 'Make your first share',
  },
  {
    id: 13,
    title: 'CATALYST',
    category: 'Shares',
    threshold: 10,
    milestoneField: 'shares_made.total',
    description: 'Share 10 times',
  },
  {
    id: 14,
    title: 'MAVERICK',
    category: 'Shares',
    threshold: 30,
    milestoneField: 'shares_made.total',
    description: 'Share 30 times',
  },
  {
    id: 15,
    title: 'LEGEND',
    category: 'Shares',
    threshold: 75,
    milestoneField: 'shares_made.total',
    description: 'Share 75 times',
  },

  // AI ASKS BADGES
  {
    id: 16,
    title: 'SPARK',
    category: 'AI_ASKS',
    threshold: 1,
    milestoneField: 'assistant_queries.total',
    description: 'Ask the AI once',
  },
  {
    id: 17,
    title: 'CURIOUS',
    category: 'AI_ASKS',
    threshold: 25,
    milestoneField: 'assistant_queries.total',
    description: 'Ask the AI 25 times',
  },
  {
    id: 18,
    title: 'DIVER',
    category: 'AI_ASKS',
    threshold: 100,
    milestoneField: 'assistant_queries.total',
    description: 'Ask the AI 100 times',
  },
  {
    id: 19,
    title: 'COSMOS',
    category: 'AI_ASKS',
    threshold: 300,
    milestoneField: 'assistant_queries.total',
    description: 'Ask the AI 300 times',
  },
];

/**
 * Calculate which badges a user has earned based on their milestones
 * @param milestones User's milestones object
 * @returns Array of earned badge IDs
 */
export function calculateEarnedBadges(milestones: any): number[] {
  if (!milestones) return [];

  const earnedBadges: number[] = [];

  for (const badge of BADGE_THRESHOLDS) {
    let currentValue = 0;

    // Get the current value from milestones based on the field
    if (badge.milestoneField === 'streak.current') {
      currentValue = milestones.streak?.current || 0;
    } else if (badge.milestoneField === 'articles_read.total') {
      currentValue = milestones.articles_read?.total || 0;
    } else if (badge.milestoneField === 'shares_made.total') {
      currentValue = milestones.shares_made?.total || 0;
    } else if (badge.milestoneField === 'assistant_queries.total') {
      currentValue = milestones.assistant_queries?.total || 0;
    }

    // Check if threshold is met
    if (currentValue >= badge.threshold) {
      earnedBadges.push(badge.id);
    }
  }

  return earnedBadges;
}
