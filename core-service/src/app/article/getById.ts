
import { EventAnalysis } from '../../db/app-db/models/eventanalysis.model';
import { Event } from '../../db/app-db/models/event.model';
import { EventSoFar } from '../../db/app-db/models/eventsofar.model';
import { Language } from '../../db/app-db/models/language.model';
import { LocalizedEventAnalysis } from '../../db/app-db/models/localizedeventanalysis.model';
import { LocalizedEventData } from '../../db/app-db/models/localizedeventdata.model';
import { LocalizedEventSoFar } from '../../db/app-db/models/localizedeventsofar.model';
import { Logos } from '../../db/app-db/models/logos.model';
import { SeoTag } from '../../db/app-db/models/seotag.model';
import { Source } from '../../db/app-db/models/source.model';
import { ArticleResponse, ArticleDetail, ContentType } from '../../types/ReqResTypes';
import { getSignedImageUrl, getSignedAudioUrl } from '../aws/client';

export async function getArticleById(
    id: string,
    locale: string = 'en', // Keep locale parameter name for API compatibility
): Promise<ArticleResponse | null> {
    try {
        // Since language.id is now TEXT and primary key, we can directly use locale as the language ID
        const language = await Language.findByPk(locale);

        if (!language) {
            throw new Error(`Language not found for locale: ${locale}`);
        }

        // Get the main event with all related data
        const event = await Event.findByPk(id, {
            include: [
               /*  {
                    model: Category,
                    attributes: ['name']
                }, */
                {
                    model: Source,
                    as: 'Sources',
                    include: [
                        {
                            model: Logos,
                            as: 'Logo',
                            required: false,
                            attributes: ['id', 'favicon_s3_path', 'logo_s3_path', 'name', 'website']
                        }
                    ],
                    attributes: ['id', 'title', 'logo_id', 'source_url'] // Explicitly include logo_id for reference
                },
                {
                    model: LocalizedEventData,
                    as: 'localizedData',
                    where: { language_id: language.id },
                    attributes: ['title', 'description', 'content', 'contentType', 'audio', 'audioFullStory'],
                    required: false
                },
                {
                    model: EventSoFar,
                    as: 'EventSoFar',
                    include: [
                        {
                            model: LocalizedEventSoFar,
                            as: 'LocalizedEventSoFar',
                            where: { language_id: language.id },
                            attributes: ['content', 'contentType'],
                            required: false
                        }
                    ],
                    order: [['sequence', 'ASC']]
                },
                {
                    model: EventAnalysis,
                    as: 'EventAnalysis',
                    include: [
                        {
                            model: LocalizedEventAnalysis,
                            as: 'LocalizedEventAnalysis',
                            where: { language_id: language.id },
                            attributes: ['content', 'contentType'],
                            required: false
                        }
                    ],
                    order: [['sequence', 'ASC']]
                },
                {
                    model: SeoTag,
                    as: 'SeoTags',
                    attributes: ['name', 'type'],
                    through: { attributes: [] }, // Don't include junction table attributes
                    required: false
                }
            ],
        });

        if (!event) {
            return null;
        }

        const eventLocalizedData = (event as any).localizedData?.[0]?.get();
        if (!eventLocalizedData) {
            return null;
        }

        const eventSoFarItems = (event as any).EventSoFar || [];
        const eventAnalysisItems = (event as any).EventAnalysis || [];

        // Transform EventSoFar items to ArticleDetail[] format
        const storySoFar: ArticleDetail[] = eventSoFarItems
            .map((eventSoFarItem: any) => {
                const localizedData = eventSoFarItem.LocalizedEventSoFar?.[0]?.get();
                if (!localizedData || !localizedData.contentType || !localizedData.content) {
                    return null;
                }

                const contentType: ContentType = localizedData.contentType || 'text';
                let transformedContent: any = localizedData.content;

                // Transform content based on type
                if (contentType === 'bullets') {
                    // Ensure it's an array
                    transformedContent = Array.isArray(localizedData.content) 
                        ? localizedData.content 
                        : [];
                } else if (contentType === 'text') {
                    // Ensure it's a string
                    transformedContent = typeof localizedData.content === 'string' 
                        ? localizedData.content 
                        : String(localizedData.content || '');
                } else if (contentType === 'timeline') {
                    // Ensure it's an array of TimelineItem
                    transformedContent = Array.isArray(localizedData.content) 
                        ? localizedData.content 
                        : [];
                } else if (contentType === 'table') {
                    // Ensure it's an array of TableItem
                    transformedContent = Array.isArray(localizedData.content) 
                        ? localizedData.content 
                        : [];
                } else if (contentType === 'stakeholder_impact') {
                    // Ensure it's an array of StakeholderImpactItem
                    transformedContent = Array.isArray(localizedData.content) 
                        ? localizedData.content 
                        : [];
                } else if (contentType === 'scenario') {
                    // Ensure it's an array of ScenarioItem and handle backward compatibility
                    if (Array.isArray(localizedData.content)) {
                        transformedContent = localizedData.content.map((item: any) => {
                            // Handle backward compatibility: convert old string format to array
                            let scenarioArray: string[];
                            if (Array.isArray(item.scenario)) {
                                // New format: already an array
                                scenarioArray = item.scenario;
                            } else if (typeof item.scenario === 'string' && item.scenario.trim()) {
                                // Old format: single sentence string -> convert to single-item array
                                scenarioArray = [item.scenario.trim()];
                            } else {
                                // Fallback: empty array
                                scenarioArray = [];
                            }
                            
                            return {
                                scenario: scenarioArray,
                                probability: item.probability,
                                timeframe: item.timeframe,
                                sentiment: item.sentiment
                            };
                        });
                    } else {
                        transformedContent = [];
                    }
                } else if (contentType === 'concepts_decoded') {
                    // Keep as object
                    transformedContent = localizedData.content;
                }

                return {
                    sequence: eventSoFarItem.get().sequence,
                    title: undefined,
                    description: undefined,
                    type: contentType,
                    content: transformedContent
                };
            })
            .filter((item: ArticleDetail | null): item is ArticleDetail => item !== null)
            .sort((a: ArticleDetail, b: ArticleDetail) => a.sequence - b.sequence);

        // Transform EventAnalysis items to whatsNext ArticleDetail[] format
        const whatsNext: ArticleDetail[] = eventAnalysisItems
            .map((eventAnalysisItem: any) => {
                const localizedData = eventAnalysisItem.LocalizedEventAnalysis?.[0]?.get();
                if (!localizedData || !localizedData.contentType || !localizedData.content) {
                    return null;
                }

                const contentType: ContentType = localizedData.contentType || 'text';
                let transformedContent: any = localizedData.content;

                // Transform content based on type
                if (contentType === 'bullets') {
                    transformedContent = Array.isArray(localizedData.content) 
                        ? localizedData.content 
                        : [];
                } else if (contentType === 'text') {
                    transformedContent = typeof localizedData.content === 'string' 
                        ? localizedData.content 
                        : String(localizedData.content || '');
                } else if (contentType === 'timeline') {
                    transformedContent = Array.isArray(localizedData.content) 
                        ? localizedData.content 
                        : [];
                } else if (contentType === 'table') {
                    transformedContent = Array.isArray(localizedData.content) 
                        ? localizedData.content 
                        : [];
                } else if (contentType === 'stakeholder_impact') {
                    transformedContent = Array.isArray(localizedData.content) 
                        ? localizedData.content 
                        : [];
                } else if (contentType === 'scenario') {
                    // Remove redundant description and implications fields and handle backward compatibility
                    if (Array.isArray(localizedData.content)) {
                        transformedContent = localizedData.content.map((item: any) => {
                            // Handle backward compatibility: convert old string format to array
                            let scenarioArray: string[];
                            if (Array.isArray(item.scenario)) {
                                // New format: already an array
                                scenarioArray = item.scenario;
                            } else if (typeof item.scenario === 'string' && item.scenario.trim()) {
                                // Old format: single sentence string -> convert to single-item array
                                scenarioArray = [item.scenario.trim()];
                            } else {
                                // Fallback: empty array
                                scenarioArray = [];
                            }
                            
                            return {
                                scenario: scenarioArray,
                                probability: item.probability,
                                timeframe: item.timeframe,
                                sentiment: item.sentiment
                            };
                        });
                    } else {
                        transformedContent = [];
                    }
                } else if (contentType === 'concepts_decoded') {
                    transformedContent = localizedData.content;
                }

                return {
                    sequence: eventAnalysisItem.get().sequence,
                    title: undefined,
                    description: undefined,
                    type: contentType,
                    content: transformedContent
                };
            })
            .filter((item: ArticleDetail | null): item is ArticleDetail => item !== null)
            .sort((a: ArticleDetail, b: ArticleDetail) => a.sequence - b.sequence);

        // Convert event to plain object to simplify data access
        const eventData = (event as any).toJSON ? (event as any).toJSON() : event;
        
        const sourceItems = eventData.Sources || [];
       // const categoryName = eventData.Category?.name || '';

        // Extract SEO tags and impact tags
        const seoTagItems = eventData.SeoTags || [];
        const seoTags = seoTagItems
            .map((seoTag: any) => {
                const seoTagName = seoTag?.name;
                if (!seoTagName || typeof seoTagName !== 'string') {
                    return null;
                }
                // Add hashtag if not present
                return seoTagName.startsWith('#') ? seoTagName : `#${seoTagName}`;
            })
            .filter((name: string | null): name is string => name !== null);

        const impactTags = seoTagItems
            .filter((seoTag: any) => seoTag?.type === 'Impact')
            .map((seoTag: any) => seoTag.name as string)
            .filter((name: string) => !!name);

        // Extract and deduplicate favicons from all sources
        // Sequelize query already includes Logo association, so we can access it directly as plain objects
        const faviconPaths = sourceItems
            .map((source: any) => source.Logo?.favicon_s3_path)
            .filter((path: string | null | undefined): path is string => {
                return path !== null && path !== undefined && typeof path === 'string' && path.trim() !== '';
            })
            .filter((path: string, index: number, arr: string[]) => arr.indexOf(path) === index); // Remove duplicates

        // Generate signed URLs for favicons
        const favicons = await Promise.all(
            faviconPaths.map(async (path: string) => {
                try {
                    return await getSignedImageUrl(path);
                } catch (error) {
                    console.warn('Failed to generate signed URL for favicon:', path, error);
                    return null;
                }
            })
        );

        // Filter out any failed URL generations
        const validFavicons = favicons.filter((url): url is string => url !== null);

        // Generate signed URLs for audio files
        const audioGist = await getSignedAudioUrl(eventLocalizedData.audio || '');
        const audioFullStory = await getSignedAudioUrl(eventLocalizedData.audioFullStory || '');

        // Generate signed URL for image (including backup images)
        const signedImageUrl = await getSignedImageUrl(event.image || '');

        // Extract description: use description field from database (keep it separate from gistContent)
        const description = eventLocalizedData.description || undefined;

        // Extract gistContent from LocalizedEventData.content
        // gistContent should always come from content field, independent of description
        let gistContent: string[] | string;
        const contentType = eventLocalizedData.contentType || 'text';
        
        if (contentType === 'bullets') {
            // Extract bullets array
            gistContent = Array.isArray(eventLocalizedData.content) 
                ? eventLocalizedData.content 
                : [];
        } else if (contentType === 'text') {
            // Extract text string - always use content field for gistContent
            if (typeof eventLocalizedData.content === 'string' && eventLocalizedData.content.trim() !== '') {
                gistContent = eventLocalizedData.content;
            } else {
                // If content is empty, use empty string (don't fall back to description)
                gistContent = '';
            }
        } else {
            // For other types, use description or first content item
            if (description) {
                gistContent = description;
            } else if (Array.isArray(eventLocalizedData.content) && eventLocalizedData.content.length > 0) {
                // Try to extract first item as string
                const firstItem = eventLocalizedData.content[0];
                if (typeof firstItem === 'string') {
                    gistContent = firstItem;
                } else if (typeof firstItem === 'object' && firstItem !== null) {
                    // Try to get a text field from the object
                    gistContent = (firstItem as any).content || (firstItem as any).description || JSON.stringify(firstItem);
                } else {
                    gistContent = '';
                }
            } else {
                gistContent = '';
            }
        }

        const article: ArticleResponse = {
            id: event.id,
            image: signedImageUrl || '',
            imageSourceUrl: event.image_source_url || undefined,
            audio: audioGist || undefined,
            audioFullStory: audioFullStory || undefined,
            // category: categoryName,
            date: event.time_stamp.toISOString(),
            sourceCount: sourceItems.length,
            favicons: validFavicons,
            title: eventLocalizedData.title || 'Event Title',
            description: description || undefined,
            contentType: contentType,
            gistContent: gistContent,
            storySoFar: storySoFar,
            whatsNext: whatsNext,
            seoTags: seoTags.length > 0 ? seoTags : undefined,
            impactTags: impactTags.length > 0 ? impactTags : undefined,
        };

        return article;
    } catch (error) {
        console.error('Error fetching article by ID:', error);
        throw error;
    }
}
