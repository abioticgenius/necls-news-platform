import { AppConfig } from '../db/app-db/models/appconfig.model';

let cachedPatterns: string[] | null = null;
let lastCacheTime: number = 0;
const CACHE_TTL = 5 * 60 * 1000; // 5 minutes cache

/**
 * Get active placeholder patterns from app_config table.
 * Results are cached for 5 minutes to reduce database queries.
 * 
 * @returns Array of active pattern strings
 */
export async function getActivePlaceholderPatterns(): Promise<string[]> {
  const now = Date.now();
  
  // Return cached patterns if still valid
  if (cachedPatterns && (now - lastCacheTime) < CACHE_TTL) {
    return cachedPatterns;
  }

  try {
    const config = await AppConfig.findOne({
      where: { config_key: 'image_placeholder_patterns' },
    });

    if (config && config.config_value) {
      // config_value is JSONB, should be an array of strings
      let patterns: string[] = [];
      
      if (Array.isArray(config.config_value)) {
        patterns = config.config_value.map(p => String(p)).filter(p => p.length > 0);
      } else if (typeof config.config_value === 'object' && config.config_value !== null) {
        // Handle object format if needed (e.g., { patterns: [...] })
        const obj = config.config_value as any;
        if (Array.isArray(obj.patterns)) {
          patterns = obj.patterns.map((p: any) => String(p)).filter((p: string) => p.length > 0);
        }
      }

      if (patterns.length > 0) {
        cachedPatterns = patterns;
        lastCacheTime = now;
        return cachedPatterns;
      }
    }

    // If no config found or invalid format, return default patterns
    console.warn('image_placeholder_patterns config not found or invalid, using defaults');
    return getDefaultPatterns();
  } catch (error) {
    console.error('Error fetching placeholder patterns:', error);
    // Return default patterns as fallback
    return getDefaultPatterns();
  }
}

/**
 * Clear the cache (useful after admin updates patterns)
 */
export function clearPlaceholderPatternsCache(): void {
  cachedPatterns = null;
  lastCacheTime = 0;
}

/**
 * Default patterns used as fallback if database query fails
 */
function getDefaultPatterns(): string[] {
  return [
    'placeholder', 'default', 'logo', 'branding', 'favicon',
    'icon', 'watermark',
    '/logo.', '/icon.', '/favicon.', '/branding.', '/watermark.',
    'logo.png', 'logo.jpg', 'logo.jpeg', 'logo.gif',
    'icon.png', 'icon.jpg', 'favicon.ico',
    'branding.png', 'branding.jpg',
    'theprint', 'ap-news', 'apnews', 'associated-press', 'associatedpress',
    'site-logo', 'site_logo', 'header-logo', 'header_logo',
    'footer-logo', 'footer_logo', 'nav-logo', 'nav_logo',
    // News site placeholder patterns
    'live-blog',                  // ET live-blog path images
    'newsletter',                 // IE newsletter template images
    'morning-expresso',           // IE morning newsletter series
    'express-view',               // IE Express View editorial images
    'Express-view',               // IE Express View editorial images (capital variant)
    'og-image.png',               // Open Graph placeholder (e.g. thehindu og-image.png)
    '/theme/images/',             // The Hindu theme/branding image directory
    'overlay-toi_sw',             // TOI sitewide watermark overlay images
    '466BJJQ7PVGY5O53NZ3KL65MHM.png', // Known Reuters placeholder image
    // Known TOI placeholder msids
    'msid-47529300',
    'msid-117518778',
    'msid-117518772',
  ];
}