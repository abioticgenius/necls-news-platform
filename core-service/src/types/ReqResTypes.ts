import { AppDbModels } from "../db/app-db";

export interface GetAllArticlesParams {
    languageId?: string;
    after?: string;
    before?: string;
    limit?: number;
    // category?: string;
    collectionId?: string;
    orTags?: string[];  // article must match at least one of these tags
    andTag?: string;    // article must ALSO match this tag (AND'd against each orTag)
  }
  
  export interface FormattedArticle {
    id: string;
    image: string;
    audio: string;
    audioFullStory?: string;
    // category: string | null;
    date: Date;
    sourceCount: number;
    favicons: string[];
    title: string;
    description: string;
    impactTags?: string[];
  }
  
  export interface PaginatedArticlesResponse {
    articles: FormattedArticle[];
    hasMore: boolean;
    nextCursor?: string;
    prevCursor?: string;
  }


// Centralized Content Type Definitions
export const CONTENT_TYPES = {
    BULLETS: 'bullets',
    TEXT: 'text',
    TABLE: 'table',
    TIMELINE: 'timeline',
    CONCEPTS_DECODED: 'concepts_decoded',
    STAKEHOLDER_IMPACT: 'stakeholder_impact',
    SCENARIO: 'scenario',
} as const;

export type ContentType = typeof CONTENT_TYPES[keyof typeof CONTENT_TYPES];

// Array of content types for Sequelize ENUM
export const CONTENT_TYPE_VALUES = [
    CONTENT_TYPES.BULLETS,
    CONTENT_TYPES.TEXT,
    CONTENT_TYPES.TABLE,
    CONTENT_TYPES.TIMELINE,
    CONTENT_TYPES.CONCEPTS_DECODED,
    CONTENT_TYPES.STAKEHOLDER_IMPACT,
    CONTENT_TYPES.SCENARIO,
] as const;

// Content type definitions
export type BulletsContent = string[];

export interface TimelineItem {
    date: string;
    content: string;
}

export interface TableItem {
    title: string;
    data: { [key: string]: string };
}

export interface StakeholderImpactItem {
    title: string;
    description: string[]; // Array of description strings
    impact: "positive" | "negative" | "neutral";
    sentiment: "hopeful" | "worried" | "supportive" | "opposed" | "neutral" | "uncertain";
}

export interface ScenarioItem {
    scenario: string;
    probability: number;
    timeframe: "Short Term" | "Long Term";
    sentiment: "Positive" | "Negative" | "Neutral";
}

export interface ConceptDecoded {
    // Structure to be defined based on backend data
    [key: string]: any;
}

// ArticleDetail interface matching frontend IArticleDetail
export interface ArticleDetail {
    sequence: number;
    title?: string;
    description?: string;
    type: ContentType;
    content: BulletsContent | string | TimelineItem[] | TableItem[] | StakeholderImpactItem[] | ScenarioItem[] | ConceptDecoded;
}

export interface ArticleResponse {
    id: string;
    image: string;
    imageSourceUrl?: string;
    audio?: string;
    audioFullStory?: string;
    // category: string;
    date: string;
    sourceCount: number;
    favicons: string[];
    title: string;
    description?: string;
    contentType: ContentType;
    gistContent: string[] | string;
    storySoFar: ArticleDetail[];
    whatsNext: ArticleDetail[];
    seoTags?: string[]; // Array of SEO tag names (2-4 words with hashtags)
    impactTags?: string[]; // Array of impact tag names
}

export interface ArticleSource {
  id: string;
  name: string;
  logo: string;
  favicon: string;
  url: string;
}
