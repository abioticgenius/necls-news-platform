import Parser from 'rss-parser';

interface NewsFeed {
  name: string;
  category: string;
  url: string;
}

export interface NewsItem {
  title: string;
  link: string;
  description: string;
  pubDate: string;
  source: string;
  category: string;
}

// RSS Feed configuration
const NEWS_FEEDS: NewsFeed[] = [
  // NDTV
  { name: 'NDTV', category: 'Top Stories', url: 'https://feeds.feedburner.com/ndtvnews-top-stories' },
  { name: 'NDTV', category: 'Latest Stories', url: 'https://feeds.feedburner.com/NdtvNews-LatestNews' },
  { name: 'NDTV', category: 'India News', url: 'https://feeds.feedburner.com/ndtvnews-india-news' },
  
  // Times of India
  { name: 'Times of India', category: 'Most Read', url: 'https://timesofindia.indiatimes.com/rssfeeds/4719148.cms' },
  { name: 'Times of India', category: 'Most Shared', url: 'https://timesofindia.indiatimes.com/rssfeeds/-2128672765.cms' },
  { name: 'Times of India', category: 'Most Commented', url: 'https://timesofindia.indiatimes.com/rssfeeds/-2128830821.cms' },
  { name: 'Times of India', category: 'Top Stories', url: 'https://timesofindia.indiatimes.com/rssfeeds/-2128936835.cms' },
  { name: 'Times of India', category: 'Most Recent', url: 'https://timesofindia.indiatimes.com/rssfeeds/296589292.cms' },
  
  // India Today
  { name: 'India Today', category: 'Top Stories', url: 'https://www.indiatoday.in/rss/home' },
  { name: 'India Today', category: 'Trending News', url: 'https://www.indiatoday.in/rss/1206514' },
  { name: 'India Today', category: 'India News', url: 'https://www.indiatoday.in/rss/1206577' },
  { name: 'India Today', category: 'Business', url: 'https://www.indiatoday.in/rss/1206550' },
  { name: 'India Today', category: 'Technology', url: 'https://www.indiatoday.in/rss/1206585' },
  
  // The Hindu
  { name: 'The Hindu', category: 'Latest News', url: 'https://www.thehindu.com/news/national/?service=rss' },
  
  // Indian Express
  { name: 'Indian Express', category: 'Trending', url: 'https://indianexpress.com/section/trending/feed/' },
];

const parser = new Parser({
  timeout: 8000, // 8 second timeout per feed
  customFields: {
    item: ['description', 'content:encoded', 'media:content'],
  },
});

/**
 * Fetches and parses a single RSS feed
 */
async function fetchFeed(feed: NewsFeed): Promise<NewsItem[]> {
  try {
    console.log(`Fetching feed: ${feed.name} - ${feed.category}`);
    const parsed = await parser.parseURL(feed.url);
    const items: NewsItem[] = [];
    
    if (!parsed.items || parsed.items.length === 0) {
      console.warn(`No items found in feed ${feed.name} - ${feed.category}`);
      return [];
    }
    
    for (const item of parsed.items) {
      try {
        // Clean HTML from description
        const description = cleanHtml(item.contentSnippet || item.content || item.description || '');
        
        if (!item.title || !item.link) {
          continue; // Skip items without title or link
        }
        
        items.push({
          title: item.title,
          link: item.link,
          description: description.substring(0, 300), // Limit description length
          pubDate: item.pubDate || item.isoDate || new Date().toISOString(),
          source: feed.name,
          category: feed.category,
        });
      } catch (itemError) {
        console.warn(`Error processing item in feed ${feed.name}:`, itemError);
        continue; // Skip this item and continue with others
      }
    }
    
    console.log(`Successfully fetched ${items.length} items from ${feed.name} - ${feed.category}`);
    return items;
  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : String(error);
    console.error(`Error fetching feed ${feed.name} - ${feed.category}:`, errorMessage);
    return [];
  }
}

/**
 * Cleans HTML tags from text
 */
function cleanHtml(html: string): string {
  return html
    .replace(/<[^>]*>/g, '') // Remove HTML tags
    .replace(/&nbsp;/g, ' ')
    .replace(/&amp;/g, '&')
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .replace(/\s+/g, ' ')
    .trim();
}

/**
 * Fetches all RSS feeds and aggregates the results
 * Returns top trending items sorted by recency and relevance
 */
export async function fetchTrendingNews(limit: number = 30): Promise<NewsItem[]> {
  console.log(`Fetching trending news from ${NEWS_FEEDS.length} RSS feeds...`);
  
  try {
    // Fetch all feeds in parallel with timeout protection
    const feedPromises = NEWS_FEEDS.map(async (feed) => {
      try {
        // Add timeout to each feed fetch (10 seconds max per feed)
        return await Promise.race([
          fetchFeed(feed),
          new Promise<NewsItem[]>((_, reject) => 
            setTimeout(() => reject(new Error(`Timeout fetching ${feed.name}`)), 10000)
          )
        ]);
      } catch (error) {
        const errorMsg = error instanceof Error ? error.message : String(error);
        console.error(`Feed fetch failed for ${feed.name} - ${feed.category}:`, errorMsg);
        return []; // Return empty array on error, don't fail the entire operation
      }
    });
    
    const feedResults = await Promise.allSettled(feedPromises);
    
    // Aggregate all items
    const allItems: NewsItem[] = [];
    let successCount = 0;
    let failureCount = 0;
    
    for (const result of feedResults) {
      if (result.status === 'fulfilled') {
        allItems.push(...result.value);
        if (result.value.length > 0) {
          successCount++;
        }
      } else {
        failureCount++;
      }
    }
    
    console.log(`RSS fetch complete: ${successCount} successful, ${failureCount} failed, ${allItems.length} total items`);
    
    if (allItems.length === 0) {
      console.warn('No news items fetched from any RSS feed');
      return [];
    }
    
    // Remove duplicates - only exact title matches (not similar)
    const uniqueItems = removeExactDuplicates(allItems);
    console.log(`After deduplication: ${uniqueItems.length} unique items`);
    
    // Ensure source diversity - group by source and limit per source
    const sourceGroups = new Map<string, NewsItem[]>();
    for (const item of uniqueItems) {
      if (!sourceGroups.has(item.source)) {
        sourceGroups.set(item.source, []);
      }
      sourceGroups.get(item.source)!.push(item);
    }
    
    // Sort each source's items by date
    for (const [source, items] of sourceGroups.entries()) {
      items.sort((a, b) => {
        const dateA = new Date(a.pubDate).getTime();
        const dateB = new Date(b.pubDate).getTime();
        return dateB - dateA;
      });
    }
    
    // Distribute items across sources (max 3-4 per source to ensure diversity)
    const maxPerSource = Math.max(3, Math.ceil(limit / Math.min(sourceGroups.size, 5)));
    const diverseItems: NewsItem[] = [];
    const sourceArray = Array.from(sourceGroups.entries());
    
    // Round-robin distribution to ensure diversity
    let round = 0;
    while (diverseItems.length < limit && round < maxPerSource) {
      for (const [source, items] of sourceArray) {
        if (diverseItems.length >= limit) break;
        if (items.length > round) {
          diverseItems.push(items[round]);
        }
      }
      round++;
    }
    
    // Fill remaining slots with most recent items if needed
    if (diverseItems.length < limit) {
      const remaining = uniqueItems
        .filter(item => !diverseItems.some(di => di.title === item.title && di.source === item.source))
        .sort((a, b) => {
          const dateA = new Date(a.pubDate).getTime();
          const dateB = new Date(b.pubDate).getTime();
          return dateB - dateA;
        })
        .slice(0, limit - diverseItems.length);
      diverseItems.push(...remaining);
    }
    
    console.log(`Returning ${diverseItems.length} trending news items from ${sourceGroups.size} sources`);
    return diverseItems;
  } catch (error) {
    console.error('Error in fetchTrendingNews:', error);
    throw error; // Re-throw to be handled by caller
  }
}

/**
 * Removes exact duplicate news items (same title and source)
 */
function removeExactDuplicates(items: NewsItem[]): NewsItem[] {
  const seen = new Set<string>();
  const unique: NewsItem[] = [];
  
  for (const item of items) {
    // Create a unique key from title + source
    const key = `${item.title.toLowerCase().trim()}|${item.source}`;
    
    if (!seen.has(key)) {
      seen.add(key);
      unique.push(item);
    }
  }
  
  return unique;
}

/**
 * Checks if two titles are similar (likely the same story)
 */
function areTitlesSimilar(title1: string, title2: string): boolean {
  // Simple similarity check: if one title contains most words of the other
  const words1 = title1.split(/\s+/).filter(w => w.length > 3);
  const words2 = title2.split(/\s+/).filter(w => w.length > 3);
  
  if (words1.length === 0 || words2.length === 0) return false;
  
  const commonWords = words1.filter(w => words2.includes(w));
  const similarity = commonWords.length / Math.max(words1.length, words2.length);
  
  // Consider similar if > 60% word overlap
  return similarity > 0.6;
}

/**
 * Checks if a user question is asking for trending news
 * @param question - The user's question
 * @param entities - Optional array of extracted entities. If provided and not empty, returns false (not a trending query)
 */
export function isTrendingNewsQuery(question: string, entities?: string[]): boolean {
  // If entities are provided and not empty, this is NOT a trending query
  // This prevents "india news today" from being treated as trending
  if (entities && entities.length > 0) {
    return false;
  }
  
  const normalized = question.toLowerCase();
  
  // If temporal keywords present, not trending (should be handled by temporal query)
  // This ensures queries with "today", "yesterday", etc. are treated as temporal, not trending
  const temporalKeywords = ['today', "today's", 'yesterday', "yesterday's", 'last week', 'last month', 'the day before yesterday', 'days ago', 'weeks ago'];
  if (temporalKeywords.some(keyword => normalized.includes(keyword))) {
    return false;
  }
  
  const trendingKeywords = [
    'trending',
    'trending news',
    'trending topics',
    'trending stories',
    'top news',
    'top stories',
    'latest news',
    // Removed 'news today' - now handled by temporal queries
    'what\'s trending',
    'what is trending',
    'current news',
    'breaking news',
    'hot news',
    'popular news',
    'most read',
    'most shared',
  ];
  
  return trendingKeywords.some(keyword => normalized.includes(keyword));
}

