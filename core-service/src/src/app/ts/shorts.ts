import { Request, Response } from 'express';

const cache: { data: any; timestamp: number } | null = null;
const shortsCacheMap: Record<string, { data: any; timestamp: number }> = {};
const CACHE_TTL = 30 * 60 * 1000; 

const YOUTUBE_API_KEY = process.env.YOUTUBE_API_KEY;

interface YoutubeShort {
  videoId: string;
  title: string;
  description: string;
  thumbnail: string;
  channelTitle: string;
  publishedAt: string;
  embedUrl: string;
  shortUrl: string;
}

interface YoutubeSearchItem {
  id: {
    kind: string;
    videoId: string;
  };
  snippet: {
    publishedAt: string;
    channelId: string;
    title: string;
    description: string;
    thumbnails: {
      high: {
        url: string;
      };
    };
    channelTitle: string;
  };
}

interface YoutubeApiResponse {
  items: YoutubeSearchItem[];
  nextPageToken?: string;
  pageInfo?: {
    totalResults: number;
    resultsPerPage: number;
  };
}

export async function getShorts(req: Request, res: Response) {
  try {
    const maxResults = parseInt(req.query.maxResults as string) || 50;
    const pageToken = (req.query.pageToken as string) || '';
    const locale = (req.query.locale as string) || 'en';

    const cacheKey = `${locale}-${pageToken}-${maxResults}`;
    const now = Date.now();

    if (shortsCacheMap[cacheKey] && (now - shortsCacheMap[cacheKey].timestamp) < CACHE_TTL) {
      console.log('⚡ Returning cached response');
      return res.json(shortsCacheMap[cacheKey].data);
    }

    if (!YOUTUBE_API_KEY) {
      throw new Error('YOUTUBE_API_KEY is not set in environment variables');
    }

    const CHANNEL_IDS: Record<string, string> = {
      en: process.env.THINKO_CHANNEL_ID_EN || '', 
      hi: process.env.THINKO_CHANNEL_ID_HI || '',
    };

    const channelId = CHANNEL_IDS[locale] || CHANNEL_IDS['hi'];

    const params = new URLSearchParams({
      part: 'snippet',
      channelId: channelId,
      type: 'video',
      videoDuration: 'short',
      maxResults: maxResults.toString(),
      order: "date",
      key: YOUTUBE_API_KEY,
    });

    if (pageToken) {
      params.append('pageToken', pageToken);
    }

    const url = `https://www.googleapis.com/youtube/v3/search?${params.toString()}`;
    console.log('YouTube API URL:', url);

    const response = await fetch(url);

    if (!response.ok) {
      const errorData = await response.json();
      throw new Error(JSON.stringify(errorData));
    }

    const data = await response.json() as YoutubeApiResponse;

    console.log('📦 Total items from API:', data.items?.length);

    const shorts: YoutubeShort[] = (data.items || [])
      .filter((item) => {
        if (!item.id?.videoId) return false;

        const text = (
          (item.snippet.title || '') + ' ' +
         (item.snippet.description || '')
        ).toLowerCase();

      if (text.includes('#iran')) {
        return false;
      }

        console.log('✅ Included');
        return true;
      })
      .map((item) => ({
        videoId: item.id.videoId,
        title: item.snippet.title,
        description: item.snippet.description,
        thumbnail: 'https://i.ytimg.com/vi/${item.id.videoId}/maxresdefault.jpg',
        channelTitle: item.snippet.channelTitle,
        publishedAt: item.snippet.publishedAt,
        embedUrl: `https://www.youtube.com/embed/${item.id.videoId}?autoplay=1&mute=1&loop=1&playlist=${item.id.videoId}`,
        shortUrl: `https://youtube.com/shorts/${item.id.videoId}`,
      }));

    console.log('✅ Final shorts count after filtering:', shorts.length);

    const responseData = {
      shorts,
      nextPageToken: data.nextPageToken || null,
      totalResults: data.pageInfo?.totalResults || 0,
    };

    shortsCacheMap[cacheKey] = { data: responseData, timestamp: now };

    res.json(responseData);
  } catch (error) {
    console.error('❌ Error fetching YouTube Shorts:', error);
    res.status(500).json({ error: 'Failed to fetch YouTube Shorts' });
  }
}