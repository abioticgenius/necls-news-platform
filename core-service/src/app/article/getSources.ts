import { Logos } from '../../db/app-db/models/logos.model';
import { Source } from '../../db/app-db/models/source.model';
import { ArticleSource } from '../../types/ReqResTypes';
import { getSignedImageUrl } from '../aws/client';

export async function getArticleSources( articleId: String): Promise<ArticleSource[]> {
  try {
   
    const sources = await Source.findAll({
      where: { event_id: articleId },
      include: [
        {
          model: Logos,
          as: 'Logo',
          required: false
        }
      ],
      attributes: ['id', 'title', 'logo_id', 'source_url']
    });
    
    const formattedSources: ArticleSource[] = await Promise.all(
      sources.map(async (source: any) => {
        // Convert Sequelize model to plain object for easier data access
        const sourceData = source.toJSON ? source.toJSON() : source;
        const logo = sourceData.Logo;
        
        let signedLogoPath = '';
        if (logo?.logo_s3_path) {
          signedLogoPath = await getSignedImageUrl(logo.logo_s3_path);
        }
        let signedFaviconPath = '';
        if (logo?.favicon_s3_path) {
          signedFaviconPath = await getSignedImageUrl(logo.favicon_s3_path);
        }
        
        return {
          id: sourceData.id,
          name: sourceData.title || 'Unknown Source',
          logo: signedLogoPath,
          favicon: signedFaviconPath,
          url: sourceData.source_url
        };
      })
    );

    return formattedSources;
  } catch (error) {
    console.error('Error fetching article sources:', error);
    throw error;
  }
}
