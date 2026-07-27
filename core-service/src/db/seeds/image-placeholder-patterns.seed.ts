import { AppConfig } from '../app-db/models/appconfig.model';

const DEFAULT_PATTERNS = [
  'placeholder',
  'default',
  'logo',
  'branding',
  'favicon',
  'icon',
  'watermark',
  '/logo.',
  '/icon.',
  '/favicon.',
  '/branding.',
  '/watermark.',
  'logo.png',
  'logo.jpg',
  'logo.jpeg',
  'logo.gif',
  'icon.png',
  'icon.jpg',
  'favicon.ico',
  'branding.png',
  'branding.jpg',
  'theprint',
  'ap-news',
  'apnews',
  'associated-press',
  'associatedpress',
  'site-logo',
  'site_logo',
  'header-logo',
  'header_logo',
  'footer-logo',
  'footer_logo',
  'nav-logo',
  'nav_logo',
  // News site placeholder patterns
  'live-blog',               // ET live-blog path images
  'newsletter',              // IE newsletter template images
  'morning-expresso',        // IE morning newsletter series
  'express-view',            // IE Express View editorial images
  'Express-view',            // IE Express View editorial images (capital variant)
  'og-image.png',            // Open Graph placeholder (e.g. thehindu og-image.png)
  '/theme/images/',          // The Hindu theme/branding image directory
  'overlay-toi_sw',          // TOI sitewide watermark overlay images
  '466BJJQ7PVGY5O53NZ3KL65MHM.png', // Known Reuters placeholder image
  // Known TOI placeholder msids
  'msid-47529300',
  'msid-117518778',
  'msid-117518772',
];

export async function seedImagePlaceholderPatterns() {
  try {
    console.log('Seeding image placeholder patterns...');
    
    const [config, created] = await AppConfig.findOrCreate({
      where: { config_key: 'image_placeholder_patterns' },
      defaults: {
        config_key: 'image_placeholder_patterns',
        config_value: DEFAULT_PATTERNS,
        description: 'Image placeholder patterns for thumbnail filtering',
      },
    });

    if (created) {
      console.log(`Created app_config record for image_placeholder_patterns with ${DEFAULT_PATTERNS.length} patterns`);
    } else {
      // Update existing config if it exists but doesn't have the right structure
      if (!Array.isArray(config.config_value) || config.config_value.length === 0) {
        await config.update({
          config_value: DEFAULT_PATTERNS,
          description: 'Image placeholder patterns for thumbnail filtering',
        });
        console.log(`Updated app_config record for image_placeholder_patterns with ${DEFAULT_PATTERNS.length} patterns`);
      } else {
        console.log(`app_config record for image_placeholder_patterns already exists with ${config.config_value.length} patterns`);
      }
    }

    console.log('Image placeholder patterns seeding completed successfully');
  } catch (error) {
    console.error('Error seeding image placeholder patterns:', error);
    throw error;
  }
}