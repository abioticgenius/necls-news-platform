/**
 * Trending Tags Scheduler
 * 
 * Runs every 24 hours to refresh trending tags by matching RSS feeds to articles.
 */

import type { Sequelize } from 'sequelize';
import { refreshTrendingTags } from './trending-matcher';

const REFRESH_INTERVAL_MS = 24 * 60 * 60 * 1000; // 24 hours in milliseconds

let schedulerInterval: NodeJS.Timeout | null = null;

/**
 * Starts the trending tags scheduler
 */
export function startTrendingScheduler(
  sequelize: Sequelize,
  openaiApiKey: string
): void {
  console.log('Starting trending tags scheduler (24-hour interval)...');

  // Run immediately on startup (optional - comment out if you don't want this)
  // refreshTrendingTags(models, sequelize, openaiApiKey).catch(console.error);

  // Schedule periodic refresh
  schedulerInterval = setInterval(() => {
    console.log('[Scheduler] Running scheduled trending tags refresh...');
    refreshTrendingTags(sequelize, openaiApiKey)
      .then((result) => {
        console.log(`[Scheduler] Trending tags refreshed: ${result.matched} matched, ${result.tagged} tagged`);
      })
      .catch((error) => {
        console.error('[Scheduler] Error refreshing trending tags:', error);
      });
  }, REFRESH_INTERVAL_MS);

  console.log('Trending tags scheduler started. Next refresh in 24 hours.');
}

/**
 * Stops the trending tags scheduler
 */
export function stopTrendingScheduler(): void {
  if (schedulerInterval) {
    clearInterval(schedulerInterval);
    schedulerInterval = null;
    console.log('Trending tags scheduler stopped.');
  }
}

/**
 * Manually trigger trending tags refresh (for testing or admin use)
 */
export async function triggerTrendingRefresh(
  sequelize: Sequelize,
  openaiApiKey: string,
  categoryId?: string
): Promise<{ matched: number; tagged: number }> {
  console.log('Manually triggering trending tags refresh...');
  return await refreshTrendingTags( sequelize, openaiApiKey, categoryId);
}

