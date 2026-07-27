/**
 * Milestone Configuration
 * Defines progression levels for each user activity track with thresholds and messages
 */

export interface MilestoneLevel {
  level: number;
  threshold: number;
  title: string;
  message: string;
  onboardingMessage?: string;
  nextThreshold?: number;
}

export interface MilestoneTrack {
  trackName: string;
  levels: MilestoneLevel[];
}

export const MILESTONE_TRACKS = {
  streaks: {
    trackName: 'Streaks',
    levels: [
      {
        level: 1,
        threshold: 0,
        title: 'Ignite',
        message: "You're building something real.",
        onboardingMessage: 'Start your streak today!',
        nextThreshold: 3,
      },
      {
        level: 2,
        threshold: 3,
        title: 'Spark',
        message: 'Look at you, showing up.',
        nextThreshold: 7,
      },
      {
        level: 3,
        threshold: 7,
        title: 'Pro',
        message: "This is who you are now.",
        nextThreshold: 21,
      },
      {
        level: 4,
        threshold: 21,
        title: 'Diamond',
        message: 'Rare. Genuinely impressive.',
        nextThreshold: 75,
      },
      {
        level: 5,
        threshold: 75,
        title: 'Century',
        message: "Legendary. This one's permanent.",
        nextThreshold: 100,
      },
      {
        level: 6,
        threshold: 100,
        title: 'Sage',
        message: "A full year. Incredible.",
        nextThreshold: 365,
      },
    ],
  },

  stories: {
    trackName: 'Stories',
    levels: [
      {
        level: 1,
        threshold: 0,
        title: 'Starter',
        message: "Nice. You're off to a start.",
        onboardingMessage: 'Your first story awaits.',
        nextThreshold: 10,
      },
      {
        level: 2,
        threshold: 10,
        title: 'Informed',
        message: "You're properly in the loop.",
        nextThreshold: 50,
      },
      {
        level: 3,
        threshold: 50,
        title: 'Well Read',
        message: "You really know your stuff.",
        nextThreshold: 200,
      },
      {
        level: 4,
        threshold: 200,
        title: 'Newsroom',
        message: 'Seriously well-informed. Well done.',
        nextThreshold: 500,
      },
      {
        level: 5,
        threshold: 500,
        title: 'Oracle',
        message: "Elite. Most never get here.",
        nextThreshold: 1000,
      },
      {
        level: 6,
        threshold: 1000,
        title: 'The Compass',
        message: "You've consumed more stories than most people read in a lifetime.",
        nextThreshold: 999999,
      },
    ],
  },

  shares: {
    trackName: 'Shares',
    levels: [
      {
        level: 1,
        threshold: 0,
        title: 'Origin',
        message: "Nice one. That's a take.",
        onboardingMessage: 'Got a take? Share it.',
        nextThreshold: 1,
      },
      {
        level: 2,
        threshold: 1,
        title: 'Catalyst',
        message: "People are listening to you.",
        nextThreshold: 10,
      },
      {
        level: 3,
        threshold: 10,
        title: 'Maverick',
        message: "You think for yourself. Respect.",
        nextThreshold: 30,
      },
      {
        level: 4,
        threshold: 30,
        title: 'Legend',
        message: "Top tier. You're a Legend.",
        nextThreshold: 75,
      },
    ],
  },

  assistantQueries: {
    trackName: 'AI Asks',
    levels: [
      {
        level: 1,
        threshold: 0,
        title: 'Spark',
        message: "Great question.",
        onboardingMessage: 'Curious? Just ask.',
        nextThreshold: 1,
      },
      {
        level: 2,
        threshold: 1,
        title: 'Curious',
        message: "You never just accept. Smart move.",
        nextThreshold: 25,
      },
      {
        level: 3,
        threshold: 25,
        title: 'Deep Diver',
        message: "You go deeper. Always.",
        nextThreshold: 100,
      },
      {
        level: 4,
        threshold: 100,
        title: 'Cosmos',
        message: 'Boundless curiosity. Unstoppable.',
        nextThreshold: 300,
      },
    ],
  },
};

/**
 * Get the current milestone level for a given track and value
 */
export function getCurrentMilestoneLevel(
  trackKey: 'streaks' | 'stories' | 'shares' | 'assistantQueries',
  value: number
): MilestoneLevel | null {
  const track = MILESTONE_TRACKS[trackKey];
  if (!track) return null;

  // Find the highest level that the user has reached
  let currentLevel = track.levels[0];
  for (const level of track.levels) {
    if (value >= level.threshold) {
      currentLevel = level;
    } else {
      break;
    }
  }

  return currentLevel;
}

/**
 * Get milestone information for all tracks
 */
export function getMilestoneInfo(milestones: any) {
  return {
    streaks: {
      current: milestones.streak.current,
      level: getCurrentMilestoneLevel('streaks', milestones.streak.current),
    },
    stories: {
      current: milestones.articles_read.total,
      level: getCurrentMilestoneLevel('stories', milestones.articles_read.total),
    },
    shares: {
      current: milestones.shares_made.total,
      level: getCurrentMilestoneLevel('shares', milestones.shares_made.total),
    },
    assistantQueries: {
      current: milestones.assistant_queries.total,
      level: getCurrentMilestoneLevel('assistantQueries', milestones.assistant_queries.total),
    },
  };
}
