import { Request, Response } from 'express';

const IG_ACCOUNT_ID = process.env.IG_ACCOUNT_ID;  
const ACCESS_TOKEN = process.env.IG_ACCESS_TOKEN;

interface InstagramMedia {
  id: string;
  caption?: string;
  media_type: string;
  media_url?: string;
  thumbnail_url?: string;
  permalink: string;
  timestamp: string;
}

interface GraphApiResponse {
  data: InstagramMedia[];
  paging?: {
    next?: string;
    previous?: string;
  };
}
export async function getReels(req: Request, res: Response) {
  try {
    const fields = [
      "id",
      "caption",
      "media_type",
      "media_url",
      "thumbnail_url",
      "permalink",
      "timestamp",
    ].join(",");

    const url = `https://graph.facebook.com/v24.0/${IG_ACCOUNT_ID}/media?fields=${fields}&access_token=${ACCESS_TOKEN}`;
console.log(url);

    const response = await fetch(url);
    
    if (!response.ok) {
      const errorData = await response.json();
      throw new Error(JSON.stringify(errorData));
    }

    const data = await response.json() as GraphApiResponse;;

    // Filter only Reels (media_type === "VIDEO")
    const reels = (data.data || []).filter(
      (item) => item.media_type === "VIDEO"
    );

    res.json({ reels });
  } catch (error) {
    console.error("❌ Error fetching reels:", error);
    res.status(500).json({ error: "Failed to fetch reels" });
  }
}