/**
 * Trending Topics Matcher
 * 
 * Matches trending topics from RSS feeds to articles in the database using vector embeddings.
 * Uses semantic search with 80% similarity threshold.
 */

import type { Sequelize } from 'sequelize';
import { QueryTypes } from 'sequelize';
import OpenAI from 'openai';
import { fetchTrendingNews, type NewsItem } from './rss-feeds';
import { EventSeoTag } from '../../db/app-db/models/eventseotag.model';
import { SeoTag } from '../../db/app-db/models/seotag.model';

interface TrendingMatchResult {
  event_id: string;
  title: string;
  similarity: number;
  rss_title: string;
}

const SIMILARITY_THRESHOLD = 0.8; // 80% similarity threshold (cosine similarity >= 0.8)
const RECENCY_HOURS = 24; // Only match articles from last 24 hours
const OPENAI_EMBEDDING_MODEL = 'text-embedding-3-small';
const EMBEDDING_DIMENSIONS = 384; // Match the dimension used in assistant_chunks

/**
 * Generates 384-dimensional embedding for text using OpenAI
 */
async function generateEmbedding(text: string, openai: OpenAI): Promise<number[]> {
  try {
    const response = await openai.embeddings.create({
      model: OPENAI_EMBEDDING_MODEL,
      input: text,
      dimensions: EMBEDDING_DIMENSIONS, // Request 384 dimensions to match assistant_chunks
    });
    return response.data[0].embedding;
  } catch (error) {
    console.error('Error generating embedding:', error);
    throw error;
  }
}


/**
 * Matches RSS feed items to articles using vector similarity
 * Returns list of event_ids that match trending topics
 */
export async function matchTrendingToArticles(
  rssItems: NewsItem[],
  sequelize: Sequelize,
  openaiApiKey: string,
  categoryId?: string
): Promise<string[]> {
  if (!rssItems || rssItems.length === 0) {
    return [];
  }

  const openai = new OpenAI({ apiKey: openaiApiKey });
  const matchedEventIds = new Set<string>();

  console.log(`Matching ${rssItems.length} RSS items to articles using vector similarity...`);

  // Process RSS items in batches to avoid rate limits
  const batchSize = 5;
  for (let i = 0; i < rssItems.length; i += batchSize) {
    const batch = rssItems.slice(i, i + batchSize);
    
    for (const rssItem of batch) {
      try {
        // Generate 384-dim embedding for RSS title
        const rssEmbedding = await generateEmbedding(rssItem.title, openai);
        
        // Format embedding as PostgreSQL array string for vector type
        // pgvector expects: '[0.1,0.2,0.3,...]' format
        const vectorString = '[' + rssEmbedding.join(',') + ']';

        // Build query using pgvector's cosine distance operator (<=>)
        // Cosine similarity = 1 - cosine_distance
        // We want similarity >= 0.8, so distance <= 0.2
        let query = `
          SELECT DISTINCT
            ac.event_id,
            ac.title,
            e.time_stamp,
            -- Calculate cosine similarity: 1 - (embedding <=> $1::vector)
            (1 - (ac.embedding <=> $1::vector)) as similarity
          FROM assistant_chunks ac
          JOIN event e ON ac.event_id = e.id
          WHERE ac.chunk_type = 'title'
            AND e.time_stamp > NOW() - INTERVAL '${RECENCY_HOURS} hours'
            AND (1 - (ac.embedding <=> $1::vector)) >= ${SIMILARITY_THRESHOLD}
        `;

        // Pass vector as string (PostgreSQL will cast it to vector type)
        const bindParams: any[] = [vectorString];

        // Add category filter if specified
        if (categoryId) {
          query += ` AND e.category_id = $${bindParams.length + 1}::uuid`;
          bindParams.push(categoryId);
        }

        query += `
          ORDER BY similarity DESC
          LIMIT 3
        `;

        const results = await sequelize.query(query, {
          bind: bindParams,
          type: QueryTypes.SELECT,
        }) as Array<{ event_id: string; title: string; similarity: number }>;

        for (const result of results) {
          matchedEventIds.add(result.event_id);
          console.log(`Matched: "${rssItem.title}" -> "${result.title}" (similarity: ${result.similarity.toFixed(3)})`);
        }

        // Small delay to avoid rate limits
        await new Promise(resolve => setTimeout(resolve, 200));
      } catch (error) {
        console.error(`Error matching RSS item "${rssItem.title}":`, error);
        continue;
      }
    }
  }

  console.log(`Matched ${matchedEventIds.size} articles to trending topics`);
  return Array.from(matchedEventIds);
}


/**
 * Ensures trending tag exists in seo_tag table
 * Returns the tag ID
 */
export async function ensureTrendingTag(
  sequelize: Sequelize
): Promise<string> {
  // Check if trending tag exists
  let trendingTag = await SeoTag.findOne({
    where: {
      name: 'trending',
      type: 'tag',
    },
  });

  if (!trendingTag) {
    // Create trending tag
    trendingTag = await SeoTag.create({
      name: 'trending',
      type: 'tag',
    });
    console.log('Created trending tag in seo_tag table');
  }

  return (trendingTag as any).id;
}

/**
 * Adds trending tag to events
 */
export async function addTrendingTagToEvents(
  eventIds: string[],
  sequelize: Sequelize
): Promise<number> {
  if (eventIds.length === 0) {
    return 0;
  }

  const trendingTagId = await ensureTrendingTag(sequelize);
  let addedCount = 0;

  for (const eventId of eventIds) {
    try {
      // Check if tag already exists
      const existing = await EventSeoTag.findOne({
        where: {
          event_id: eventId,
          seo_tag_id: trendingTagId,
        },
      });

      if (!existing) {
        await EventSeoTag.create({
          event_id: eventId,
          seo_tag_id: trendingTagId,
          weight: 100, // High weight for trending
        });
        addedCount++;
      }
    } catch (error) {
      console.error(`Error adding trending tag to event ${eventId}:`, error);
      continue;
    }
  }

  console.log(`Added trending tag to ${addedCount} events`);
  return addedCount;
}

/**
 * Removes trending tag from all events
 */
export async function removeTrendingTags(
  sequelize: Sequelize
): Promise<number> {
  const trendingTag = await SeoTag.findOne({
    where: {
      name: 'trending',
      type: 'tag',
    },
  });

  if (!trendingTag) {
    return 0;
  }

  const deleted = await EventSeoTag.destroy({
    where: {
      seo_tag_id: (trendingTag as any).id,
    },
  });

  console.log(`Removed trending tag from ${deleted} events`);
  return deleted;
}

/**
 * Main function to refresh trending tags
 * Fetches RSS feeds, matches to articles, and updates tags
 */
export async function refreshTrendingTags(
  sequelize: Sequelize,
  openaiApiKey: string,
  categoryId?: string
): Promise<{ matched: number; tagged: number }> {
  console.log('='.repeat(60));
  console.log('Refreshing trending tags...');
  console.log('='.repeat(60));

  try {
    // Step 1: Remove all existing trending tags
    await removeTrendingTags(sequelize);

    // Step 2: Fetch trending news from RSS feeds
    const rssItems = await fetchTrendingNews(50); // Get more items for better matching
    console.log(`Fetched ${rssItems.length} RSS items`);

    if (rssItems.length === 0) {
      console.log('No RSS items found, skipping trending tag refresh');
      return { matched: 0, tagged: 0 };
    }

    // Step 3: Match RSS items to articles
    const matchedEventIds = await matchTrendingToArticles(
      rssItems,
      sequelize,
      openaiApiKey,
      categoryId
    );

    // Step 4: Add trending tags to matched events
    const taggedCount = await addTrendingTagToEvents(
      matchedEventIds,
      sequelize
    );

    console.log('='.repeat(60));
    console.log(`Trending tag refresh complete: ${matchedEventIds.length} matched, ${taggedCount} tagged`);
    console.log('='.repeat(60));

    return {
      matched: matchedEventIds.length,
      tagged: taggedCount,
    };
  } catch (error) {
    console.error('Error refreshing trending tags:', error);
    throw error;
  }
}

