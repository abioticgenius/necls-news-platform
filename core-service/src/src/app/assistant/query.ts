import type { Sequelize } from 'sequelize';
import { Op, QueryTypes } from 'sequelize';
import OpenAI from 'openai';
import { getAllArticles } from '../article/getAll';
import { Event } from '../../db/app-db/models/event.model';
import { EventFaq } from '../../db/app-db/models/eventfaq.model';
import { Language } from '../../db/app-db/models/language.model';
import { LocalizedEventData } from '../../db/app-db/models/localizedeventdata.model';
import { EventAnalysis } from '../../db/app-db/models/eventanalysis.model';
import { EventSoFar } from '../../db/app-db/models/eventsofar.model';
import { LocalizedEventAnalysis } from '../../db/app-db/models/localizedeventanalysis.model';
import { LocalizedEventSoFar } from '../../db/app-db/models/localizedeventsofar.model';
import { SeoTag } from '../../db/app-db/models/seotag.model';
import { ArticleResponse, TimelineItem, StakeholderImpactItem, ScenarioItem, ArticleDetail } from '../../types/ReqResTypes';
import { getSignedImageUrl } from '../aws/client';

// Import missing helper functions from query-helpers
import { extractEntities, isLatestQuery, extractNumber, getLocalizedMessage, getLanguageInstruction, isHindiText, translateToEnglish, isGreeting, isPersonalOrMetaQuery, isTopStoriesQuery } from './query-helpers';

// Use gpt-5-nano as requested
const ASSISTANT_MODEL = process.env.OPENAI_ASSISTANT_MODEL || 'gpt-5-nano';

// Local embedder – all-MiniLM-L6-v2 ONNX, same model as Python FastEmbed, runs in-process
import { embedText } from './embedder';

export async function getEventFaqs(eventId: string, languageId: string = 'en') {
  // Verify language exists
  const language = await Language.findByPk(languageId);
  if (!language) {
    throw new Error(`Language not found for languageId: ${languageId}`);
  }

  const records = await EventFaq.findAll({
    where: {
      event_id: eventId,
      language_id: languageId
    },
    order: [['sequence', 'ASC'], ['created_date', 'ASC']],
  });

  return records.map((faq: any) => ({
    id: faq.id,
    question: faq.question,
    answer: faq.answer,
    sequence: faq.sequence,
    created_date: faq.created_date,
  }));
}

// Fetch comprehensive article details
async function getFullArticleDetails(eventId: string, sequelize: Sequelize, locale: string = 'en'): Promise<any> {
  const languageId = locale || 'en';
  
  // Get basic event info with localized data
  const event = await Event.findByPk(eventId, {
    include: [
      {
        model: LocalizedEventData,
        as: 'localizedData',
        where: { language_id: languageId },
        required: false
      }
    ]
  });

  if (!event) return null;

  // Get story so far data with localized content
  const storySoFar = await EventSoFar.findAll({
    where: { event_id: eventId },
    include: [
      {
        model: LocalizedEventSoFar,
        as: 'LocalizedEventSoFar',
        where: { language_id: languageId },
        required: false
      }
    ],
    order: [['sequence', 'DESC']]
  });

  // Get analysis data (impacts and scenarios) with localized content
  const analyses = await EventAnalysis.findAll({
    where: { event_id: eventId },
    include: [
      {
        model: LocalizedEventAnalysis,
        as: 'LocalizedEventAnalysis',
        where: { language_id: languageId },
        required: false
      }
    ],
    order: [['sequence', 'ASC']]
  });

  const eventData = event.toJSON();

  const result = {
    id: eventData.id,
    title: eventData.localizedData?.[0]?.title || 'Article Title',
    description: eventData.localizedData?.[0]?.description || '',
    gistContent: eventData.localizedData?.[0]?.content || '',
    storySoFar: storySoFar.map((item: any) => {
      const itemData = item.toJSON();
      const localizedData = itemData.LocalizedEventSoFar?.[0];
      const localizedContent = localizedData?.content;
      const localizedContentType = localizedData?.contentType;

      // Try localized content first, then fallback to base content
      let finalContent = '';

      if (localizedContent && localizedContentType) {
        finalContent = parseContentToString(localizedContent, localizedContentType);
      } else if (item.content) {
        finalContent = parseContentToString(item.content, item.type || 'text');
      }


      return {
        title: item.title,
        description: item.description,
        content: finalContent,
        type: item.type
      };
    }),
    whatsNext: analyses.map((item: any) => {
      const itemData = item.toJSON();
      const localizedData = itemData.LocalizedEventAnalysis?.[0];
      const localizedContent = localizedData?.content;
      const localizedContentType = localizedData?.contentType;

      // Try localized content first, then fallback to base content
      let finalContent = '';
      let rawContent: any = null;

      if (localizedContent && localizedContentType) {
        finalContent = parseContentToString(localizedContent, localizedContentType);
        // Preserve raw content for stakeholder_impact and scenario types
        if (localizedContentType === 'stakeholder_impact' || localizedContentType === 'scenario') {
          rawContent = localizedContent;
        }
      } else if (item.content) {
        finalContent = parseContentToString(item.content, item.type || 'text');
        // Preserve raw content for stakeholder_impact and scenario types
        if (item.type === 'stakeholder_impact' || item.type === 'scenario') {
          rawContent = item.content;
        }
      }

      return {
        title: item.title,
        description: item.description,
        content: finalContent,
        rawContent: rawContent, // Preserve raw content for stakeholder_impact and scenario
        contentType: localizedContentType || item.type || 'text',
        type: localizedContentType || item.type || 'text' // Use the actual content type
      };
    })
  };


  return result;
}

// Parse content from JSONB to readable string based on content type
function parseContentToString(content: any, contentType: string): string {
  if (!content) return '';

  try {
    switch (contentType) {
      case 'bullets':
        // content is string[]
        if (Array.isArray(content)) {
          return content.map((bullet: string) => `• ${bullet}`).join('\n');
        }
        break;

      case 'text':
        // content is string
        if (typeof content === 'string') {
          return content;
        }
        break;

      case 'timeline':
        // content is ITimelineItem[]
        if (Array.isArray(content)) {
          return content.map((item: any) =>
            `${item.date}: ${item.content}`
          ).join('\n');
        }
        break;

      case 'table':
        // content is ITableContent[]
        if (Array.isArray(content)) {
          return content.map((table: any) => {
            let tableText = `${table.title}\n`;
            if (table.data && typeof table.data === 'object') {
              Object.entries(table.data).forEach(([key, value]) => {
                tableText += `${key}: ${value}\n`;
              });
            }
            return tableText;
          }).join('\n');
        }
        break;

      case 'stakeholder_impact':
        // content is IStakeholderImpact[]
        if (Array.isArray(content)) {
          return content.map((impact: any) =>
            `${impact.title}: ${Array.isArray(impact.description) ? impact.description.join(', ') : impact.description}. Impact: ${impact.impact}. Sentiment: ${impact.sentiment}`
          ).join('\n');
        }
        break;

      case 'scenario':
        // content is IScenario[]
        if (Array.isArray(content)) {
          return content.map((scenario: any) =>
            `Scenario: ${scenario.scenario}. Timeframe: ${scenario.timeframe}. Sentiment: ${scenario.sentiment}. Probability: ${scenario.probability}%`
          ).join('\n');
        }
        break;

      case 'concepts_decoded':
        // content is IConceptDecoded (object with any keys)
        if (typeof content === 'object' && content !== null) {
          return Object.entries(content).map(([key, value]) =>
            `${key}: ${value}`
          ).join('\n');
        }
        break;

      default:
        // Try to convert to string if it's a simple type
        if (typeof content === 'string') {
          return content;
        }
        if (Array.isArray(content)) {
          return content.map(item =>
            typeof item === 'string' ? item :
            typeof item === 'object' ? JSON.stringify(item) : String(item)
          ).join('\n');
        }
        if (typeof content === 'object') {
          return JSON.stringify(content);
        }
        return String(content);
    }
  } catch (error) {
    console.error('Error parsing content:', error, { content, contentType });
    return '';
  }

  return '';
}

// Classify query intent using pattern matching first, then OpenAI for ambiguous cases
async function classifyQueryIntent(question: string, openaiApiKey: string): Promise<string> {
  // First, try pattern matching for clear cases - this is more reliable
  const patternMatch = classifyQueryIntentFallback(question);
  
  // If pattern matching found a clear match (not just default summary), use it
  // This avoids unnecessary OpenAI calls and ensures accuracy for common patterns
  if (patternMatch !== 'summary') {
    return patternMatch;
  }
  
  // For ambiguous queries that defaulted to summary, use OpenAI to disambiguate
  const openai = new OpenAI({ apiKey: openaiApiKey });
  
  const prompt = `Classify the user's question about an article into one of these categories:
- "summary": Questions asking to summarize, explain, or give overview (ONLY for general summary requests)
- "story_so_far": Questions about how it happened, what led to this, background, context, causation, "what happened", "how did this happen"
- "stakeholder_impact": Questions about who is affected, who benefits, stakeholders, impacts
- "future_scenarios": Questions about what happens next, future, scenarios, predictions, "what will happen"

IMPORTANT: 
- "explain what happened" or "what happened" → story_so_far
- "how did this happen" → story_so_far
- "what will happen next" → future_scenarios

User question: "${question}"

Return ONLY the category name, nothing else.`;

  try {
    const completion = await Promise.race([
      openai.chat.completions.create({
        model: ASSISTANT_MODEL,
        messages: [
          {
            role: 'user',
            content: `You are a query classifier. Return only the category name: summary, story_so_far, stakeholder_impact, or future_scenarios. Be precise: "what happened" = story_so_far, "what will happen" = future_scenarios.\n\n${prompt}`,
          },
        ],
        max_completion_tokens: 10, // classifier returns 1 word
      } as any),
      new Promise<never>((_, reject) =>
        setTimeout(() => reject(new Error('OpenAI API timeout')), 20000)
      )
    ]);

    const intent = completion.choices[0]?.message?.content?.trim().toLowerCase() || 'summary';
    
    // Validate intent
    const validIntents = ['summary', 'story_so_far', 'stakeholder_impact', 'future_scenarios'];
    if (validIntents.includes(intent)) {
      return intent;
    }
    
    // Fallback to pattern matching if OpenAI returns invalid intent
    return patternMatch;
  } catch (error) {
    console.error('Error classifying query intent:', error);
    // Fallback to pattern matching
    return patternMatch;
  }
}

// Fallback pattern matching for intent classification
function classifyQueryIntentFallback(question: string): string {
  const lowerQuestion = question.toLowerCase().trim();
  
  // Story so far patterns - check first before other "what" patterns
  // Priority: "what happened" patterns should come before generic "what" patterns
  if (lowerQuestion.includes('what happened') || lowerQuestion.includes('what occurred') ||
      lowerQuestion.includes('explain what happened') || lowerQuestion.includes('explain what occurred') ||
      lowerQuestion.includes('what led') || lowerQuestion.includes('background') ||
      lowerQuestion.includes('context') || lowerQuestion.includes('why') ||
      lowerQuestion.includes('cause') || lowerQuestion.includes('reason') ||
      (lowerQuestion.includes('how') && (lowerQuestion.includes('happen') || lowerQuestion.includes('occur')))) {
    return 'story_so_far';
  }
  
  // Stakeholder impact patterns
  if (lowerQuestion.includes('who') && (lowerQuestion.includes('affect') || lowerQuestion.includes('impact') ||
      lowerQuestion.includes('benefit') || lowerQuestion.includes('stakeholder'))) {
    return 'stakeholder_impact';
  }
  
  // Future scenarios patterns - more specific to avoid conflicts with "what happened"
  if ((lowerQuestion.includes('what') && lowerQuestion.includes('next')) ||
      (lowerQuestion.includes('what') && lowerQuestion.includes('will happen')) ||
      lowerQuestion.includes('future') || lowerQuestion.includes('scenario') ||
      lowerQuestion.includes('predict') || lowerQuestion.includes('after this') ||
      lowerQuestion.includes('what happens next')) {
    return 'future_scenarios';
  }
  
  // Summary patterns - check after story_so_far to avoid conflicts
  if (lowerQuestion.includes('summarize') || lowerQuestion.includes('overview') ||
      (lowerQuestion.includes('explain') && !lowerQuestion.includes('what happened'))) {
    return 'summary';
  }
  
  // Default to summary
  return 'summary';
}

// Extract summary content from article
function extractSummaryContent(articleDetails: any): string {
  const gistContent = articleDetails.gistContent || '';
  
  if (Array.isArray(gistContent)) {
    return gistContent.join('\n\n');
  }
  
  if (typeof gistContent === 'string' && gistContent.length > 0) {
    return gistContent;
  }
  
  // Fallback to description if gistContent is empty
  if (articleDetails.description) {
    return articleDetails.description;
  }
  
  return "Summary content is not available for this article.";
}


// Extract stakeholder impact content grouped by impact type
function extractStakeholderImpactContent(articleDetails: any): string {
  if (!articleDetails.whatsNext || !Array.isArray(articleDetails.whatsNext)) {
    return "Stakeholder impact information is not available for this article.";
  }
  
  // Find items with type 'stakeholder_impact' - check both type and contentType fields
  const stakeholderItems = articleDetails.whatsNext.filter((item: any) => 
    item.type === 'stakeholder_impact' || item.contentType === 'stakeholder_impact'
  );
  
  if (stakeholderItems.length === 0) {
    return "Stakeholder impact information is not available for this article.";
  }
  
  const positiveImpacts: string[] = [];
  const negativeImpacts: string[] = [];
  const neutralImpacts: string[] = [];
  
  stakeholderItems.forEach((item: any) => {
    // Try to use rawContent if available (array format), otherwise parse from content string
    let impacts: any[] = [];
    
    if (item.rawContent && Array.isArray(item.rawContent)) {
      impacts = item.rawContent;
    } else if (item.content && typeof item.content === 'string') {
      // Parse from string format: "Title: desc. Impact: positive. Sentiment: hopeful"
      const lines = item.content.split('\n').filter((line: string) => line.trim().length > 0);
      lines.forEach((line: string) => {
        const impactMatch = line.match(/^([^:]+):\s*(.+?)\.\s*Impact:\s*(\w+)\.?\s*(?:Sentiment:\s*(\w+))?/i);
        if (impactMatch) {
          impacts.push({
            title: impactMatch[1].trim(),
            description: impactMatch[2].trim(),
            impact: impactMatch[3].trim().toLowerCase(),
            sentiment: impactMatch[4]?.trim() || ''
          });
        }
      });
    }
    
    impacts.forEach((impact: any) => {
      if (impact && typeof impact === 'object') {
        const title = impact.title || 'Unknown stakeholder';
        const description = Array.isArray(impact.description) 
          ? impact.description.join(' ') 
          : (impact.description || '');
        const impactType = impact.impact?.toLowerCase() || 'neutral';
        const sentiment = impact.sentiment || '';
        
        const formatted = `${title}: ${description}${sentiment ? ` (Sentiment: ${sentiment})` : ''}`;
        
        if (impactType === 'positive') {
          positiveImpacts.push(`• ${formatted}`);
        } else if (impactType === 'negative') {
          negativeImpacts.push(`• ${formatted}`);
        } else {
          neutralImpacts.push(`• ${formatted}`);
        }
      }
    });
  });
  
  const sections: string[] = [];
  
  if (positiveImpacts.length > 0) {
    sections.push(`**Positive Impact:**\n${positiveImpacts.join('\n')}`);
  }
  
  if (negativeImpacts.length > 0) {
    sections.push(`**Negative Impact:**\n${negativeImpacts.join('\n')}`);
  }
  
  if (neutralImpacts.length > 0) {
    sections.push(`**Neutral Impact:**\n${neutralImpacts.join('\n')}`);
  }
  
  if (sections.length === 0) {
    return "Stakeholder impact information is not available for this article.";
  }
  
  return sections.join('\n\n');
}

// Extract future scenarios content
function extractFutureScenariosContent(articleDetails: any): string {
  if (!articleDetails.whatsNext || !Array.isArray(articleDetails.whatsNext)) {
    return "Future scenarios information is not available for this article.";
  }
  
  // Find items with type 'scenario' - check both type and contentType fields
  const scenarioItems = articleDetails.whatsNext.filter((item: any) => 
    item.type === 'scenario' || item.contentType === 'scenario'
  );
  
  if (scenarioItems.length === 0) {
    return "Future scenarios information is not available for this article.";
  }
  
  const scenarios: string[] = [];
  let scenarioIndex = 1;
  
  scenarioItems.forEach((item: any) => {
    // Try to use rawContent if available (array format), otherwise parse from content string
    let scenarioArray: any[] = [];
    
    if (item.rawContent && Array.isArray(item.rawContent)) {
      scenarioArray = item.rawContent;
    } else if (item.content && typeof item.content === 'string') {
      // Parse from string format: "Scenario: text. Timeframe: Short Term. Sentiment: Positive. Probability: 60%"
      const lines = item.content.split('\n').filter((line: string) => line.trim().length > 0);
      lines.forEach((line: string) => {
        const scenarioMatch = line.match(/Scenario:\s*(.+?)\.\s*Timeframe:\s*([^\.]+)\.\s*Sentiment:\s*([^\.]+)\.\s*Probability:\s*(\d+)%/i);
        if (scenarioMatch) {
          scenarioArray.push({
            scenario: scenarioMatch[1].trim(),
            timeframe: scenarioMatch[2].trim(),
            sentiment: scenarioMatch[3].trim(),
            probability: parseInt(scenarioMatch[4].trim(), 10)
          });
        }
      });
    }
    
    scenarioArray.forEach((scenario: any) => {
      if (scenario && typeof scenario === 'object') {
        const scenarioText = scenario.scenario || '';
        const probability = scenario.probability || 0;
        const timeframe = scenario.timeframe || '';
        const sentiment = scenario.sentiment || '';
        
        if (scenarioText) {
          const parts: string[] = [];
          parts.push(scenarioText);
          if (probability > 0) parts.push(`Probability: ${probability}%`);
          if (timeframe) parts.push(`Timeframe: ${timeframe}`);
          if (sentiment) parts.push(`Sentiment: ${sentiment}`);
          
          scenarios.push(`**Scenario ${scenarioIndex}:** ${parts.join(' | ')}`);
          scenarioIndex++;
        }
      }
    });
  });
  
  if (scenarios.length === 0) {
    return "Future scenarios information is not available for this article.";
  }
  
  return scenarios.join('\n\n');
}

// Direct question-to-content mapping for reliable responses
function generateDirectResponse(question: string, articleDetails: any): string {
  const lowerQuestion = question.toLowerCase().trim();


  // Extract content sections
  const storySoFar = extractStorySoFarContent(articleDetails);
  const impactsAndScenarios = extractImpactsAndScenariosContent(articleDetails);
  const gist = articleDetails.gistContent || '';

  // Who is affected / impacted questions
  if (lowerQuestion.includes('who') && (lowerQuestion.includes('affect') || lowerQuestion.includes('impact') ||
      lowerQuestion.includes('suffer') || lowerQuestion.includes('hurt') || lowerQuestion.includes('hit'))) {
    return extractAffectedEntities(impactsAndScenarios);
  }

  // Who benefits questions
  if (lowerQuestion.includes('who') && (lowerQuestion.includes('benefit') || lowerQuestion.includes('gain') ||
      lowerQuestion.includes('advantage') || lowerQuestion.includes('profit'))) {
    return extractBenefitingEntities(impactsAndScenarios);
  }

  // What happened / background questions
  if ((lowerQuestion.includes('what') && lowerQuestion.includes('happened')) ||
      lowerQuestion.includes('what occurred') || lowerQuestion.includes('background') ||
      lowerQuestion.includes('context')) {
    return extractCausationContent(storySoFar);
  }

  // Why did this happen / causation questions
  if (lowerQuestion.includes('why') || (lowerQuestion.includes('what') && lowerQuestion.includes('cause')) ||
      lowerQuestion.includes('how come') || lowerQuestion.includes('reason')) {
    return extractCausationContent(storySoFar);
  }

  // What happens next / future scenarios
  if ((lowerQuestion.includes('what') && lowerQuestion.includes('next')) ||
      (lowerQuestion.includes('what') && lowerQuestion.includes('happen')) ||
      lowerQuestion.includes('future') || lowerQuestion.includes('after') ||
      lowerQuestion.includes('scenario') || lowerQuestion.includes('then')) {
    return extractFutureScenarios(impactsAndScenarios);
  }

  // Is this good or bad / evaluation questions
  if ((lowerQuestion.includes('good') || lowerQuestion.includes('bad')) &&
      (lowerQuestion.includes('long term') || lowerQuestion.includes('short term') ||
       lowerQuestion.includes('overall') || lowerQuestion.includes('this'))) {
    return extractEvaluation(impactsAndScenarios);
  }

  // How does X affect Y / specific impact questions
  const entities = ['india', 'china', 'russia', 'ukraine', 'eu', 'european union', 'governments', 'consumers', 'oil traders'];
  for (const entity of entities) {
    if (lowerQuestion.includes(entity)) {
      return extractEntityImpact(entity, impactsAndScenarios);
    }
  }

  // Summary questions
  if (lowerQuestion.includes('summary') || lowerQuestion.includes('overview') ||
      (lowerQuestion.includes('what') && lowerQuestion.includes('about'))) {
    return `Summary: This article discusses "${articleDetails.title}". ${gist}`;
  }

  // Default to gist content
  if (gist) {
    return `According to the article: ${gist}`;
  }

  // Final fallback
  return "I can help you understand this article. Please ask questions about its content, summary, or analysis.";
}

// Extract story so far content as simple text
function extractStorySoFarContent(articleDetails: any): string {
  const content: string[] = [];

  if (articleDetails.storySoFar && Array.isArray(articleDetails.storySoFar)) {
    articleDetails.storySoFar.forEach((item: any) => {
      // Try localized content first, then fallback to regular content
      const itemContent = item.content;
      if (itemContent && typeof itemContent === 'string') {
        // Clean and extract meaningful text
        const lines = itemContent.split('\n').filter((line: string) => line.trim().length > 0);
        lines.forEach((line: string) => {
          const trimmed = line.trim();
          // Extract bullet points, remove markers
          if (trimmed.startsWith('•') || trimmed.startsWith('-') || trimmed.startsWith('*')) {
            content.push(trimmed.replace(/^[*•\-]\s*/, '').trim());
          }
          // Include substantial paragraphs
          else if (trimmed.length > 15 && !trimmed.includes('http') && !trimmed.match(/^\d+\./)) {
            content.push(trimmed);
          }
        });
      }
    });
  }

  const result = content.join('; ');
  return result;
}

// Extract impacts and scenarios content as simple text
function extractImpactsAndScenariosContent(articleDetails: any): string {
  let content = '';

  if (articleDetails.whatsNext && Array.isArray(articleDetails.whatsNext)) {
    articleDetails.whatsNext.forEach((item: any) => {
      if (item.content && typeof item.content === 'string') {
        content += item.content + '\n';
      }
      // Also check for description if content is missing
      else if (item.description && typeof item.description === 'string') {
        content += item.description + '\n';
      }
    });
  }

  return content;
}

// Extract entities that are negatively affected
function extractAffectedEntities(content: string): string {
  const lines = content.split('\n');
  const affected: string[] = [];


  lines.forEach(line => {
    const trimmed = line.trim();

    // Look for various patterns indicating negative impact
    if (trimmed.includes('Impact: negative') || trimmed.includes('Impact: Negative') ||
        trimmed.includes('negative impact') || trimmed.includes('adversely affected') ||
        trimmed.includes('will suffer') || trimmed.includes('face penalties') ||
        trimmed.includes('higher costs') || trimmed.includes('reduced access')) {

      // Try to find entity name in the same line or previous line
      const entityMatch = trimmed.match(/^([^:]+):/) || trimmed.match(/(\w+(?:\s+\w+)*)\s+(?:will|may|could|faces?|has|have)/i);

      if (entityMatch) {
        const entity = entityMatch[1].trim();
        if (!affected.includes(entity)) {
          affected.push(entity);
        }
      }
    }
  });

  // Also check for common affected entities by keyword
  const commonAffectedEntities = ['consumers', 'oil traders', 'china', 'india', 'european union', 'traders'];
  commonAffectedEntities.forEach(entity => {
    if (content.toLowerCase().includes(entity) &&
        (content.toLowerCase().includes('negative') || content.toLowerCase().includes('impact') ||
         content.toLowerCase().includes('affected') || content.toLowerCase().includes('suffer'))) {
      if (!affected.includes(entity)) {
        affected.push(entity);
      }
    }
  });

  if (affected.length > 0) {
    return `According to the article, these entities are negatively affected: ${affected.join(', ')}`;
  }

  return "I can help you understand this article. Please ask questions about its content, summary, or analysis.";
}

// Extract entities that benefit
function extractBenefitingEntities(content: string): string {
  const lines = content.split('\n');
  const beneficiaries: string[] = [];

  lines.forEach(line => {
    const trimmed = line.trim();
    if (trimmed.includes('Impact: neutral') || trimmed.includes('Impact: positive') ||
        trimmed.includes('Impact: Neutral') || trimmed.includes('Impact: Positive')) {
      // Find the entity name before this impact
      const entityMatch = trimmed.match(/^([^:]+):/);
      if (entityMatch) {
        beneficiaries.push(entityMatch[1].trim());
      }
    }
  });

  if (beneficiaries.length > 0) {
    return `According to the article, these entities may benefit or remain neutral: ${beneficiaries.join(', ')}`;
  }

  return "I can help you understand this article. Please ask questions about its content, summary, or analysis.";
}

// Extract causation/background content
function extractCausationContent(storySoFar: string): string {
  if (storySoFar && storySoFar.length > 0) {
    return `According to the article, this situation developed due to: ${storySoFar}`;
  }

  return "I can help you understand this article. Please ask questions about its content, summary, or analysis.";
}

// Extract future scenarios
function extractFutureScenarios(content: string): string {
  const lines = content.split('\n');
  const scenarios: string[] = [];


  lines.forEach(line => {
    const trimmed = line.trim();

    if (trimmed.includes('Scenario:') || trimmed.includes('scenario:')) {
      const scenarioText = trimmed.replace(/scenario:/i, '').trim();
      scenarios.push(scenarioText);
    }
    // Also look for future/prediction related content
    else if (trimmed.includes('will') || trimmed.includes('expected') || trimmed.includes('forecast') ||
             trimmed.includes('likely') || trimmed.includes('may') || trimmed.includes('could')) {
      if (trimmed.length > 20 && !scenarios.some(s => s.includes(trimmed.substring(0, 50)))) {
        scenarios.push(trimmed);
      }
    }
  });

  if (scenarios.length > 0) {
    return `According to the article, possible future scenarios include: ${scenarios.join('; ')}`;
  }

  return "I can help you understand this article. Please ask questions about its content, summary, or analysis.";
}

// Extract evaluation (good/bad)
function extractEvaluation(content: string): string {
  const lines = content.split('\n');
  let negativeCount = 0;
  let positiveCount = 0;

  lines.forEach(line => {
    if (line.includes('Impact: negative') || line.includes('Impact: Negative') ||
        line.includes('Sentiment: worried') || line.includes('Sentiment: negative')) {
      negativeCount++;
    }
    if (line.includes('Impact: positive') || line.includes('Impact: Positive') ||
        line.includes('Sentiment: hopeful') || line.includes('Sentiment: positive')) {
      positiveCount++;
    }
  });

  if (negativeCount > positiveCount) {
    return "According to the article, this appears to have more negative implications overall.";
  } else if (positiveCount > negativeCount) {
    return "According to the article, this appears to have more positive implications overall.";
  } else {
    return "According to the article, this has mixed implications with both positive and negative aspects.";
  }
}

// Extract specific entity impact
function extractEntityImpact(entity: string, content: string): string {
  const lines = content.split('\n');
  const entityPattern = new RegExp(`${entity}:`, 'i');

  for (const line of lines) {
    const trimmed = line.trim();
    if (entityPattern.test(trimmed)) {
      return `According to the article: ${trimmed}`;
    }
  }

  return "I can help you understand this article. Please ask questions about its content, summary, or analysis.";
}

function buildStructuredArticleContext(articleDetails: any): string {
  const parts: string[] = [];

  if (articleDetails.title) {
    parts.push(`Title:\n${articleDetails.title}`);
  }

  const summary = extractSummaryContent(articleDetails);
  if (summary && !summary.includes('not available')) {
    parts.push(`Summary:\n${summary}`);
  }

  const storySoFar = articleDetails.storySoFar?.map((item: any) => {
    const heading = item.title || item.description || 'Update';
    const content = item.content || '';
    return content ? `${heading}: ${content}` : heading;
  }).filter((text: string) => text.trim().length > 0).join('\n\n');
  if (storySoFar) {
    parts.push(`Story So Far:\n${storySoFar}`);
  }

  const impacts = extractStakeholderImpactContent(articleDetails);
  if (impacts && !impacts.includes('not available')) {
    parts.push(`Impacts:\n${impacts}`);
  }

  const scenarios = extractFutureScenariosContent(articleDetails);
  if (scenarios && !scenarios.includes('not available')) {
    parts.push(`Future Scenarios:\n${scenarios}`);
  }

  const related = articleDetails.whatsNext?.map((item: any) => {
    const label = item.title || item.description || item.type || 'Related';
    return item.content ? `${label}: ${item.content}` : '';
  }).filter((text: string) => text.trim().length > 0).join('\n\n');
  if (related) {
    parts.push(`Related Snippets:\n${related}`);
  }

  return parts.join('\n\n---\n\n');
}

function buildFallbackArticleAnswer(articleDetails: any, locale: string): string {
  const summary = extractSummaryContent(articleDetails);
  if (summary && !summary.includes('not available')) {
    return summary;
  }

  const storySoFar = extractStorySoFarContent(articleDetails);
  if (storySoFar) {
    return storySoFar;
  }

  return getLocalizedMessage('article_content_unavailable', locale);
}

export async function answerEventQuestion(params: any): Promise<any> {
  const { eventId, question, sequelize, openaiApiKey, locale = 'en' } = params;


  // Step 0: Detect and translate Hindi queries
  let originalQuestion = question;
  let processedQuestion = question;
  const isHindi = locale === 'hi' || isHindiText(question);
  
  // Step 1: Check if question matches any FAQ FIRST (before translation)
  // This ensures FAQ matching works correctly for both Hindi and English FAQs
  // Use original question for matching since FAQs are stored in the same language
  const faqs = await getEventFaqs(eventId, locale);
  const normalizedOriginalQuestion = originalQuestion.toLowerCase().trim();

  for (const faq of faqs) {
    const normalizedFaqQ = faq.question.toLowerCase().trim();
    // Check if question is similar to FAQ question (exact match or contains key words)
    if (normalizedOriginalQuestion === normalizedFaqQ ||
        normalizedOriginalQuestion.includes(normalizedFaqQ.substring(0, 20)) ||
        normalizedFaqQ.includes(normalizedOriginalQuestion.substring(0, 20))) {
      // Return FAQ answer directly - no translation needed since it's pre-stored
      return {
        answer: faq.answer,
        source: 'faq',
      };
    }
  }
  
  // Step 2: Translate for article content processing (only if not a FAQ match)
  if (isHindi) {
    try {
      processedQuestion = await translateToEnglish(question, openaiApiKey);
      
      if (processedQuestion === originalQuestion && isHindiText(originalQuestion)) {
      }
    } catch (error) {
      console.error(`[ARTICLE ASSISTANT] Translation error:`, error);
      processedQuestion = originalQuestion;
    }
  }

  try {
    // Step 3: Get full article details with locale support
    const articleDetails = await getFullArticleDetails(eventId, sequelize, locale);
    if (!articleDetails) {
      return {
        answer: getLocalizedMessage('article_not_found', locale),
        source: 'error',
      };
    }

    const retrievalArticleContext = buildStructuredArticleContext(articleDetails);
    const fallbackAnswer = buildFallbackArticleAnswer(articleDetails, locale);

    if (!retrievalArticleContext.trim()) {
      return {
        answer: getLocalizedMessage('article_content_unavailable', locale),
        source: 'retrieval',
      };
    }

    try {
      const openai = new OpenAI({ apiKey: openaiApiKey });
      const languageInstruction = getLanguageInstruction(locale);
      const systemMessage = `You are a ThinkO news article assistant. Answer using only the provided article context.

RESPONSE RULES:
- Use the article context as the source of truth.
- Maximum 120 words. Do not exceed this.
- 1-2 short sentences by default (or brief paragraphs if user asks for details).
- Be direct and factual. Avoid elaboration unless asked.
- Use bullets only if the user explicitly asks for a list.
- Always complete sentences, never cut off.

${languageInstruction}`;
      const userMessage = `Article context:
${retrievalArticleContext}

User question: ${originalQuestion}
Processed question: ${processedQuestion}`;

      const completion = await Promise.race([
        openai.chat.completions.create({
          model: ASSISTANT_MODEL,
          messages: [
            { role: 'system', content: systemMessage },
            { role: 'user', content: userMessage },
          ],
          max_completion_tokens: 200,
        } as any),
        new Promise<never>((_, reject) =>
          setTimeout(() => reject(new Error('Article assistant timeout')), 10000)
        ),
      ]);

      const llmAnswer = (completion as any).choices[0]?.message?.content?.trim();
      return {
        answer: llmAnswer || fallbackAnswer,
        source: 'retrieval',
      };
    } catch (_err) {
      console.error('[ARTICLE ASSISTANT] LLM call failed, falling back to retrieved content:', _err);
      return {
        answer: fallbackAnswer,
        source: 'retrieval',
      };
    }

    /*
    Legacy rule-based article answering removed from execution for Phase 0.
    Answers now come from buildStructuredArticleContext() + the LLM above.

    // Step 4: Use OpenAI to understand query intent
    // First, check for common keyword patterns to improve accuracy
    const lowerQuestion = processedQuestion.toLowerCase();
    let preDetectedIntent: string | null = null;
    
    // Check for "why" / "reason" / "cause" / "history" questions - these should return background
    if (lowerQuestion.includes('why') || lowerQuestion.includes('reason') ||
        lowerQuestion.includes('cause') || lowerQuestion.includes('caused') ||
        (lowerQuestion.includes('what') && lowerQuestion.includes('cause')) ||
        lowerQuestion.includes('how come') || lowerQuestion.includes('what led') ||
        lowerQuestion.includes('what prompted') || lowerQuestion.includes('what triggered') ||
        lowerQuestion.includes('history') || lowerQuestion.includes('historical') ||
        lowerQuestion.includes('background') || lowerQuestion.includes('context')) {
      preDetectedIntent = 'background';
    }
    // Check for "what happens next" / "what can happen" patterns - these should return scenarios
    else if (lowerQuestion.includes('what happen') || lowerQuestion.includes('what can happen') || 
        lowerQuestion.includes('what will happen') || lowerQuestion.includes('what might happen') ||
        lowerQuestion.includes('next step') || lowerQuestion.includes('what\'s next') ||
        lowerQuestion.includes('what could happen')) {
      preDetectedIntent = 'scenarios';
    }
    // Check for general future/scenario questions
    else if (lowerQuestion.includes('future scenario') || lowerQuestion.includes('possible scenario') ||
             lowerQuestion.includes('likely scenario')) {
      preDetectedIntent = 'scenarios';
    }
    // Check for "who don't benefit" / "who lose" / negative impact patterns (MUST come before general "impact" check)
    if ((lowerQuestion.includes('who don') && lowerQuestion.includes('benefit')) ||
        (lowerQuestion.includes('who doesn') && lowerQuestion.includes('benefit')) ||
        lowerQuestion.includes('who do not benefit') ||
        lowerQuestion.includes('who not benefit') ||
        lowerQuestion.includes('who lose') || lowerQuestion.includes('who loses') ||
        lowerQuestion.includes('who is negatively affected') ||
        lowerQuestion.includes('who are negatively affected') ||
        lowerQuestion.includes('negatively affected') ||
        lowerQuestion.includes('negatively impacted') ||
        lowerQuestion.includes('who are negatively impacted') ||
        lowerQuestion.includes('who is negatively impacted') ||
        lowerQuestion.includes('who suffer') || lowerQuestion.includes('who suffers') ||
        lowerQuestion.includes('adversely affected') ||
        lowerQuestion.includes('who is hurt') || lowerQuestion.includes('who are hurt')) {
      preDetectedIntent = 'who_not_benefits';
    }
    // Check for "who benefits" / positive impact patterns (MUST come before general "impact" check)
    else if (lowerQuestion.includes('who benefit') || lowerQuestion.includes('who gain') ||
             lowerQuestion.includes('who wins') || lowerQuestion.includes('positively impacted') ||
             lowerQuestion.includes('who is benefiting') || lowerQuestion.includes('who are benefiting') ||
             lowerQuestion.includes('benefit from') || lowerQuestion.includes('benefits from') ||
             lowerQuestion.includes('who is positively affected') ||
             lowerQuestion.includes('who are positively affected') ||
             lowerQuestion.includes('positively affected') ||
             lowerQuestion.includes('who gain from') || lowerQuestion.includes('who gains from')) {
      preDetectedIntent = 'who_benefits';
    }
    // Check for "who is affected" patterns (general - all impacts)
    else if (lowerQuestion.includes('who is affected') || lowerQuestion.includes('who are affected') ||
             lowerQuestion.includes('who is impacted') || lowerQuestion.includes('who are impacted') ||
             lowerQuestion.includes('affected by') || lowerQuestion.includes('impacted by')) {
      // Only set as who_affected if it's NOT explicitly positive or negative
      if (!lowerQuestion.includes('positively') && !lowerQuestion.includes('negatively') &&
          !lowerQuestion.includes('positive') && !lowerQuestion.includes('negative')) {
        preDetectedIntent = 'who_affected';
      }
    }
    // Check for general impact questions (stakeholder impacts, not scenarios) - must come LAST
    else if (lowerQuestion.includes('consequence') || lowerQuestion.includes('outcome') ||
             lowerQuestion.includes('impact') || lowerQuestion.includes('stakeholder')) {
      preDetectedIntent = 'impacts';
    }
    
    const openai = new OpenAI({ apiKey: openaiApiKey });
    
    const intentPrompt = `Analyze this question about a news article and identify which section is most relevant:
Question: "${processedQuestion}"

Available sections:
- "title": Article headline
- "summary": Brief overview/gist of the article
- "background": What happened, why it happened, context, story so far, past events
- "scenarios": Questions about what will happen next, what can happen, future scenarios, possible outcomes (return only scenario predictions)
- "impacts": Questions about stakeholder impacts, consequences, outcomes (general) - return ALL stakeholder impacts
- "who_affected": Questions asking who is affected (general, no positive/negative specification) - return ALL stakeholder impacts (positive, neutral, negative)
- "who_benefits": Questions asking who benefits, gains, wins, is positively impacted - return only POSITIVE or NEUTRAL stakeholder impacts
- "who_not_benefits": Questions asking who don't benefit, lose, is negatively impacted, suffers - return only NEGATIVE stakeholder impacts

Important classification rules (classify based on intent, not just keywords):
- POSITIVE/BENEFIT queries → "who_benefits":
  * "who benefits", "who benefit from", "who gains", "who wins"
  * "who is positively affected", "who are positively affected", "positively affected"
  * "who is benefiting", "who gains from", "who profits"
  * Any question asking about positive outcomes or gains for stakeholders
  
- NEGATIVE/LOSS queries → "who_not_benefits":
  * "who don't benefit", "who doesn't benefit", "who do not benefit"
  * "who lose", "who loses", "who is hurt"
  * "who is negatively affected", "who are negatively affected", "negatively affected"
  * "who suffer", "who suffers", "adversely affected"
  * Any question asking about negative outcomes or losses for stakeholders
  
- GENERAL AFFECTED queries → "who_affected":
  * "who is affected", "who are affected" (without positive/negative specification)
  * "who is impacted", "who are impacted" (general)
  * "affected by", "impacted by" (general context)
  * Any question asking about all stakeholders affected (regardless of impact type)
  
- FUTURE/SCENARIO queries → "scenarios":
  * "what happens next", "what will happen", "what can happen", "future scenarios"
  * Questions about possible outcomes or predictions
  
- GENERAL IMPACT queries → "impacts":
  * "impacts", "consequences", "outcomes" (not asking about specific stakeholders)
  * General questions about effects without specifying who

Examples:
- "who benefit from this" → who_benefits
- "who is positively affected" → who_benefits
- "who don't benefit" → who_not_benefits
- "who is negatively affected" → who_not_benefits
- "who are affected" → who_affected (all impacts)
- "who is affected by this" → who_affected (all impacts)

Respond with ONLY one word: title, summary, background, scenarios, impacts, who_affected, who_benefits, or who_not_benefits. If the question asks about multiple things or is unclear, respond with "summary".`;

    const intentCompletion = await openai.chat.completions.create({
      model: 'gpt-5-nano',
      messages: [
        {
          role: 'user',
          content: `You are a query analyzer. Respond with only one word: title, summary, background, scenarios, impacts, who_affected, who_benefits, or who_not_benefits.\n\n${intentPrompt}`,
        },
      ],
      max_completion_tokens: 10, // classifier returns 1 word
    } as any);

    const aiIntent = intentCompletion.choices[0]?.message?.content?.trim().toLowerCase() || 'summary';
    // Use pre-detected intent if available, otherwise use AI intent
    const intent = preDetectedIntent || aiIntent;

    // Step 4: Retrieve relevant article section using RAG (return article data directly)
    let answer = '';
    
    // Prepare article sections from localized data
    const articleSections = {
      title: articleDetails.title || '',
      summary: articleDetails.gistContent || '',
      background: articleDetails.storySoFar?.map((item: any) => {
        const content = item.content || item.description || '';
        return typeof content === 'string' ? content : JSON.stringify(content);
      }).filter((text: string) => text.length > 0).join('\n\n') || '',
    };

    // Parse whatsNext to separate stakeholder impacts from scenarios
    const stakeholderImpacts: string[] = [];
    const scenarios: string[] = [];

    articleDetails.whatsNext?.forEach((item: any) => {
      const itemType = item.type || '';
      const contentText = item.content || ''; // Content is already parsed by parseContentToString in getFullArticleDetails
      
      if (contentText && contentText.length > 0) {
        // Check item type to separate stakeholder impacts from scenarios
        if (itemType === 'scenario' || contentText.includes('Scenario:') || contentText.includes('scenario:')) {
          scenarios.push(contentText);
        } else if (itemType === 'stakeholder_impact' || contentText.includes('Impact:') || contentText.includes('impact:')) {
          // It's a stakeholder impact (has Impact field)
          stakeholderImpacts.push(contentText);
        } else {
          // Default: treat as stakeholder impact if it doesn't match scenario pattern
          if (!contentText.includes('Scenario:') && !contentText.includes('scenario:')) {
            stakeholderImpacts.push(contentText);
          }
        }
      }
    });

    // Retrieve section based on intent (RAG - return article data directly)
    if (intent === 'title' && articleSections.title) {
      answer = articleSections.title;
    } else if (intent === 'summary' && articleSections.summary) {
      answer = articleSections.summary;
    } else if (intent === 'background' && articleSections.background) {
      answer = articleSections.background;
    } else if (intent === 'scenarios') {
      // Return only scenarios (no stakeholder impacts)
      answer = scenarios.join('\n\n');
    } else if (intent === 'who_affected') {
      // Return ALL stakeholder impacts (no filtering, no scenarios)
      answer = stakeholderImpacts.join('\n\n');
    } else if (intent === 'who_benefits') {
      // Filter for positive/neutral stakeholder impacts only (no scenarios)
      // EXCLUDE negative impacts, only include positive or neutral
      // STRICT: Only include if impact type is explicitly positive or neutral
      // First, split combined stakeholder impacts into individual entries
      // Stakeholder entries are separated by newlines and each starts with a name followed by colon
      const allImpactEntries: string[] = [];
      stakeholderImpacts.forEach((impact) => {
        // Split by newline followed by a capital letter (stakeholder name) and colon
        // Pattern: newline + capital letter + text + colon
        const entries = impact.split(/\n(?=[A-Z][a-zA-Z\s]*:)/).filter(e => e.trim().length > 0);
        if (entries.length > 1) {
          allImpactEntries.push(...entries.map(e => e.trim()));
        } else {
          // If no split occurred, check if it's a single entry with Impact field
          const singleEntry = impact.trim();
          if (singleEntry.includes('Impact:') || singleEntry.includes('impact:')) {
            allImpactEntries.push(singleEntry);
          }
        }
      });
      
      const filtered = allImpactEntries.filter((impact) => {
        const lower = impact.toLowerCase();
        // Use regex to find the Impact field more reliably
        const impactMatch = lower.match(/impact:\s*(positive|negative|neutral)/i);
        const impactType = impactMatch ? impactMatch[1].toLowerCase() : null;
        
        // Only return if impact type is explicitly positive or neutral
        // If impact type cannot be determined, exclude it (don't include by default)
        if (!impactType) {
          return false;
        }
        
        return impactType === 'positive' || impactType === 'neutral';
      });
      answer = filtered.join('\n\n');
    } else if (intent === 'who_not_benefits') {
      // Filter for negative stakeholder impacts only (no scenarios)
      // EXCLUDE positive/neutral impacts, only include negative
      // First, split combined stakeholder impacts into individual entries
      // Stakeholder entries are separated by newlines and each starts with a name followed by colon
      const allImpactEntries: string[] = [];
      stakeholderImpacts.forEach((impact) => {
        // Split by newline followed by a capital letter (stakeholder name) and colon
        // Pattern: newline + capital letter + text + colon
        const entries = impact.split(/\n(?=[A-Z][a-zA-Z\s]*:)/).filter(e => e.trim().length > 0);
        if (entries.length > 1) {
          allImpactEntries.push(...entries.map(e => e.trim()));
        } else {
          // If no split occurred, check if it's a single entry with Impact field
          const singleEntry = impact.trim();
          if (singleEntry.includes('Impact:') || singleEntry.includes('impact:')) {
            allImpactEntries.push(singleEntry);
          }
        }
      });
      
      const filtered = allImpactEntries.filter((impact) => {
        const lower = impact.toLowerCase();
        const impactMatch = lower.match(/impact:\s*(positive|negative|neutral)/i);
        const impactType = impactMatch ? impactMatch[1].toLowerCase() : null;
        
        // Only return if impact type is negative (explicitly exclude positive/neutral)
        if (!impactType) {
          return false;
        }
        
        return impactType === 'negative';
      });
      answer = filtered.join('\n\n');
    } else if (intent === 'impacts') {
      // Return all stakeholder impacts (no scenarios)
      answer = stakeholderImpacts.join('\n\n');
    } else {
      // Fallback: try summary first, then title, then stakeholder impacts
      answer = articleSections.summary || articleSections.title || stakeholderImpacts.join('\n\n') || '';
    }

    // Build full article context: Summary + Story So Far + Ripple Effect + Next Drop
    const fullContextParts: string[] = [];
    if (articleSections.summary.trim()) {
      fullContextParts.push(`Article Summary:\n${articleSections.summary.trim()}`);
    }
    if (articleSections.background.trim()) {
      fullContextParts.push(`Story So Far:\n${articleSections.background.trim()}`);
    }
    if (stakeholderImpacts.length > 0) {
      fullContextParts.push(`Ripple Effect (Who Is Affected):\n${stakeholderImpacts.join('\n\n')}`);
    }
    if (scenarios.length > 0) {
      fullContextParts.push(`Next Drop (What Happens Next):\n${scenarios.join('\n\n')}`);
    }
    const fullArticleContext = fullContextParts.join('\n\n---\n\n') || answer.trim();

    if (!fullArticleContext.trim()) {
      return {
        answer: getLocalizedMessage('article_content_unavailable', locale),
        source: 'rag',
        intent: intent,
      };
    }

    // Use gpt-5-nano to generate a natural language response from the article content only
    try {
      const openai = new OpenAI({ apiKey: openaiApiKey });
      const languageInstruction = getLanguageInstruction(locale);
      const systemMessage = `You are a news article assistant. Use the provided article content to answer the user's question.

Rules:
- For questions about the news event itself (what happened, timeline, who is affected, impacts, scenarios): answer strictly from the article content only. Do not add facts not in the article.
- For explanatory questions about people, places, organisations, or terms that are mentioned in the article (e.g. "who is he?", "what is this organisation?", "where is this place?", "how does this affect me?"): use your knowledge to give a helpful explanation, but keep it relevant to the article's context.
- Never invent details about the news event.
${languageInstruction}`;
      const userMessage = `Article content:\n${fullArticleContext}\n\nUser question: ${originalQuestion}`;

      const completion = await Promise.race([
        openai.chat.completions.create({
          model: ASSISTANT_MODEL,
          messages: [
            { role: 'system', content: systemMessage },
            { role: 'user', content: userMessage },
          ],
          max_completion_tokens: 50,
        } as any),
        new Promise<never>((_, reject) =>
          setTimeout(() => reject(new Error('Article assistant timeout')), 8000)
        ),
      ]);

      const llmAnswer = (completion as any).choices[0]?.message?.content?.trim();
      return {
        answer: llmAnswer || answer.trim(),
        source: 'rag',
        intent: intent,
      };
    } catch (_err) {
      console.error('[ARTICLE ASSISTANT] LLM call failed, falling back to raw content:', _err);
      // On LLM failure, return raw article content as fallback
      return {
        answer: answer.trim(),
        source: 'rag',
        intent: intent,
      };
    }

    */
  } catch (error) {
    console.error('Error in article assistant:', error);
    return {
      answer: getLocalizedMessage('article_assistant_help', locale),
      source: 'error',
    };
  }
}

// Temporal query utilities
interface TemporalContext {
  is_temporal: boolean;
  date_range: {
    start: string;
    end: string;
  };
  article_count: number;
}

class TemporalQueryParser {
  private static readonly     TEMPORAL_PATTERNS = {
      yesterday: { days: 1 },
      "yesterday's": { days: 1 },
      'the day before yesterday': { days: 2 },
      'day before yesterday': { days: 2 },
      'last week': { days: 7 },
      'last month': { days: 30 },
      today: { days: 0 },
      "today's": { days: 0 }
    };

  static parseTemporalQuery(query: string): TemporalContext | null {
    const queryLower = query.toLowerCase();

    // Check for specific date patterns FIRST (before extracting article count)
    // This prevents dates like "jan 13" from being interpreted as "13 articles"
    const specificDateResult = this.parseSpecificDate(queryLower);
    if (specificDateResult) {
      // Extract article count only if it's NOT part of the date pattern
      // Look for numbers that are NOT in date context (e.g., "top 10", "5 news")
      const datePattern = /(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec|january|february|march|april|may|june|july|august|september|october|november|december)\s+\d{1,2}(?:st|nd|rd|th)?|\d{1,2}(?:st|nd|rd|th)?\s+(?:of\s+)?(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec|january|february|march|april|may|june|july|august|september|october|november|december)/i;
      const queryWithoutDate = queryLower.replace(datePattern, '');
      const numberMatch = queryWithoutDate.match(/\b(\d+)\b/);
      if (numberMatch) {
        const requestedCount = Math.min(parseInt(numberMatch[1]), 20); // Max 20
        specificDateResult.article_count = requestedCount;
      }
      return specificDateResult;
    }

    // Extract number from query (e.g., "top 10", "5 news", etc.) - only if no date pattern matched
    const numberMatch = queryLower.match(/\b(\d+)\b/);
    let requestedCount = 5; // Default
    if (numberMatch) {
      requestedCount = Math.min(parseInt(numberMatch[1]), 20); // Max 20
    }

    // Check for specific temporal patterns (relative dates)
    for (const [pattern, config] of Object.entries(this.TEMPORAL_PATTERNS)) {
      if (queryLower.includes(pattern)) {
        const endDate = new Date();
        const startDate = new Date();
        startDate.setDate(endDate.getDate() - config.days);

        // For single-day patterns (yesterday, today), set both start and end to the same date
        // For multi-day patterns (last week, last month), use the range
        const isSingleDay = config.days === 0 || config.days === 1 ||
                           pattern === 'yesterday' || pattern === "yesterday's" ||
                           pattern === 'today' || pattern === "today's";
        
        const result: TemporalContext = {
          is_temporal: true,
          date_range: {
            start: isSingleDay ? startDate.toISOString().split('T')[0] : startDate.toISOString().split('T')[0],
            end: isSingleDay ? startDate.toISOString().split('T')[0] : endDate.toISOString().split('T')[0],
          },
          article_count: requestedCount
        };

        return result;
      }
    }

    return null;
  }

  private static parseSpecificDate(query: string): TemporalContext | null {
    // Map every month name/abbreviation to a zero-padded month number
    const MONTHS: Record<string, string> = {
      jan: '01', january: '01',
      feb: '02', february: '02',
      mar: '03', march: '03',
      apr: '04', april: '04',
      may: '05',
      jun: '06', june: '06',
      jul: '07', july: '07',
      aug: '08', august: '08',
      sep: '09', september: '09',
      oct: '10', october: '10',
      nov: '11', november: '11',
      dec: '12', december: '12',
    };

    const mp = Object.keys(MONTHS).join('|');

    // "2nd april", "2nd of april", "2 april"  →  day captured in group 1, month in group 2
    const dayFirst  = new RegExp(`(\\d{1,2})(?:st|nd|rd|th)?\\s+(?:of\\s+)?(${mp})(?!\\w)`, 'i');
    // "april 2nd", "april 2"  →  month in group 1, day in group 2
    const monthFirst = new RegExp(`(${mp})(?!\\w)\\s+(\\d{1,2})(?:st|nd|rd|th)?`, 'i');

    let day: number | null = null;
    let monthNum: string | null = null;

    const m1 = query.match(dayFirst);
    if (m1) {
      day = parseInt(m1[1]);
      monthNum = MONTHS[m1[2].toLowerCase()];
    } else {
      const m2 = query.match(monthFirst);
      if (m2) {
        monthNum = MONTHS[m2[1].toLowerCase()];
        day = parseInt(m2[2]);
      }
    }

    if (!day || !monthNum || day < 1 || day > 31) return null;

    const currentYear = new Date().getFullYear();
    const dateString = `${currentYear}-${monthNum}-${String(day).padStart(2, '0')}`;

    return {
      is_temporal: true,
      date_range: { start: dateString, end: dateString },
      article_count: 20,
    };
  }
}

async function handleTemporalQuery(question: string, temporalContext: TemporalContext, sequelize: Sequelize, openaiApiKey: string, locale: string = 'en'): Promise<QueryResult> {

  try {
    // Find events within the date range
    const startDate = new Date(temporalContext.date_range.start + 'T00:00:00Z');
    const endDate = new Date(temporalContext.date_range.end + 'T23:59:59Z');


    const languageId = locale || 'en';
    const events = await sequelize.models.Event.findAll({
      where: {
        time_stamp: {
          [Op.gte]: startDate,
          [Op.lt]: endDate
        }
      },
      include: [
        {
          model: sequelize.models.LocalizedEventData,
          as: 'localizedData',
          where: { language_id: languageId },
          required: false
        }
      ],
      order: [['time_stamp', 'DESC']], // Most recent first within the date range
      limit: Math.min(temporalContext.article_count, 20) // Respect user limit, max 20
    });


    if (events.length === 0) {
      return {
        answer: getLocalizedMessage('no_articles_date', locale, { date: temporalContext.date_range.start }),
        references: []
      };
    }

    // Format references with ranking by recency
    const references = await Promise.all(events.map(async (event: any, index: number) => {
      const eventData = event.toJSON ? event.toJSON() : event;
      const localizedData = eventData.localizedData?.[0];

      // Generate signed URL for image (including backup images)
      const signedImageUrl = await getSignedImageUrl(eventData.image || '');

      return {
        id: eventData.id,
        title: localizedData?.title || 'Untitled Article',
        description: localizedData?.description || 'No description available',
        date: eventData.time_stamp ? new Date(eventData.time_stamp) : new Date(),
        relevance_score: Math.max(1.0 - (index * 0.05), 0.1), // Higher score for more recent articles
        seo_tags: [], // TODO: Populate with actual SEO tags when available
        image: signedImageUrl || ''
      };
    }));

    // Sort references by date descending (most recent first)
    references.sort((a, b) => b.date.getTime() - a.date.getTime());

    // Check if this is a specific date query (same start and end date)
    const isSpecificDate = temporalContext.date_range.start === temporalContext.date_range.end;
    const requestedCount = Math.min(temporalContext.article_count, events.length);

    if (isSpecificDate) {
      // For specific date queries, return top news from that day
      const topTitles = references.slice(0, requestedCount).map(ref => ref.title);
      const dateLocale = locale === 'hi' ? 'hi-IN' : 'en-US';
      const dateStr = new Date(temporalContext.date_range.start).toLocaleDateString(dateLocale, {
        year: 'numeric',
        month: 'long',
        day: 'numeric'
      });

      let answer;
      if (requestedCount === 1) {
        answer = getLocalizedMessage('top_news_from', locale, { date: dateStr, title: topTitles[0] });
      } else {
        const titleList = topTitles.map((title, i) => `${i + 1}. ${title}`).join('\n');
        answer = getLocalizedMessage('top_news_list', locale, { date: dateStr, count: requestedCount, list: titleList });
      }

      return {
        answer,
        references: references.slice(0, requestedCount)
      };
    } else {
      // For date ranges, return summary format
      const topTitles = references.slice(0, Math.min(5, requestedCount)).map(ref => ref.title);
      const titleList = topTitles.map((title, i) => `${i + 1}. ${title}`).join('\n');
      const answer = getLocalizedMessage('found_articles_period', locale, { 
        count: events.length, 
        top: Math.min(5, requestedCount), 
        list: titleList 
      });

      return {
        answer,
        references: references.slice(0, requestedCount)
      };
    }

  } catch (error) {
    console.error('[TEMPORAL QUERY] Error:', error);
    return {
      answer: getLocalizedMessage('error_occurred', locale),
      references: []
    };
  }
}

/** Disabled: dedicated RSS/trending path not used; trending is handled via category/tag flow. */
const USE_TRENDING_RSS_PATH = false;

async function handleTrendingNewsQuery(question: string, sequelize: Sequelize, openaiApiKey: string, locale: string = 'en'): Promise<QueryResult> {

  try {
    const DEFAULT_LIMIT = 5;
    const MAX_CAP = 20;
    const requestedCount = Math.min(extractNumber(question) ?? DEFAULT_LIMIT, MAX_CAP);

    // Fetch newest articles from DB (getAllArticles orders by time_stamp DESC)
    const { articles } = await getAllArticles({
      languageId: locale,
      limit: requestedCount,
    });

    if (articles.length === 0) {
      return {
        answer: getLocalizedMessage('error_fetching_trending', locale),
        references: []
      };
    }

    const descriptionFallback = locale === 'hi' ? 'कोई विवरण उपलब्ध नहीं' : 'No description available';
    const references = articles.map((a) => ({
      id: a.id,
      title: a.title,
      description: a.description || descriptionFallback,
      date: a.date,
      relevance_score: 1.0,
      seo_tags: [] as string[],
      image: a.image || ''
    }));

    const answer = locale === 'hi'
      ? 'यहां कुछ ट्रेंडिंग समाचार लेख हैं:'
      : 'Here are some trending news articles:';

    return {
      answer,
      references
    };

  } catch (error) {
    console.error('[TRENDING QUERY] Error:', error);
    return {
      answer: getLocalizedMessage('error_trending', locale),
      references: []
    };
  }
}

async function handleLatestNewsQuery(question: string, locale: string = 'en', openaiApiKey?: string): Promise<QueryResult> {
  try {
    const DEFAULT_LIMIT = 5;
    const MAX_CAP = 20;
    const requestedCount = Math.min(extractNumber(question) ?? DEFAULT_LIMIT, MAX_CAP);

    const { articles } = await getAllArticles({
      languageId: locale,
      limit: requestedCount,
    });

    if (articles.length === 0) {
      return {
        answer: getLocalizedMessage('error_fetching_trending', locale),
        references: []
      };
    }

    const descriptionFallback = locale === 'hi' ? 'कोई विवरण उपलब्ध नहीं' : 'No description available';
    const references = articles.map((a) => ({
      id: a.id,
      title: a.title,
      description: a.description || descriptionFallback,
      date: a.date,
      relevance_score: 1.0,
      seo_tags: [] as string[],
      image: a.image || ''
    }));

    // If no OpenAI key, return fallback (for backward compat)
    if (!openaiApiKey) {
      return {
        answer: getLocalizedMessage('latest_news_intro', locale),
        references
      };
    }

    // Build context from articles for LLM
    const articleContext = articles
      .map(a => `- ${a.title}${a.description ? ': ' + a.description : ''}`)
      .join('\n');

    const languageInstruction = getLanguageInstruction(locale);
    const systemPrompt = `You are a ThinkO news assistant. The user wants the latest news. Based on the articles below:
1. Write 1-2 sentences on what's happening (max 30 words).
2. List 3 stories with one-line summaries (max 20 words each).
MAXIMUM TOTAL: 100 words. No elaboration. Direct and concise only. ${languageInstruction}`;

    const userPrompt = `Latest articles:\n${articleContext}\n\nSummarize in the format above.`;

    try {
      const openai = new OpenAI({ apiKey: openaiApiKey });
      const timeoutPromise = new Promise<never>((_, reject) =>
        setTimeout(() => reject(new Error('LLM timeout')), 10000)
      );

      const completionPromise = openai.chat.completions.create({
        model: process.env.OPENAI_ASSISTANT_MODEL || 'gpt-5-nano',
        messages: [
          { role: 'system', content: systemPrompt },
          { role: 'user', content: userPrompt },
        ],
        max_completion_tokens: 250,
      } as any);

      const completion = await Promise.race([completionPromise, timeoutPromise]);
      const answer = (completion as any).choices[0]?.message?.content || getLocalizedMessage('latest_news_intro', locale);

      return { answer, references };
    } catch {
      // Fallback to template if LLM fails
      return {
        answer: getLocalizedMessage('latest_news_intro', locale),
        references
      };
    }
  } catch (error) {
    console.error('[LATEST NEWS QUERY] Error:', error);
    return {
      answer: getLocalizedMessage('error_trending', locale),
      references: []
    };
  }
}

function isTopNewsQuery(question: string): boolean {
  const lower = question.toLowerCase();
  // Exclude "stories" - those are handled by isTopStoriesQuery
  const asksForNews = /\b(news|headline|headlines|article|articles)\b/.test(lower);
  const asksForTop = /\b(top|important|major|biggest|main|key|leading|headline|headlines)\b/.test(lower);
  const hasStories = /\bstories?\b/.test(lower);
  // Return true only if asking for top news, but NOT for top stories
  return asksForNews && asksForTop && !hasStories;
}

function formatReferenceFallbackAnswer(references: Reference[], locale: string): string {
  const topRefs = references.slice(0, 3);
  if (topRefs.length === 0) {
    return getLocalizedMessage('no_articles_found', locale);
  }

  if (topRefs.length === 1) {
    return locale === 'hi'
      ? `मुझे इससे जुड़ी खबर मिली: ${topRefs[0].title}`
      : `I found a relevant story: ${topRefs[0].title}`;
  }

  const titles = topRefs.map(ref => ref.title).join('; ');
  return locale === 'hi'
    ? `मुझे इससे जुड़ी ये खबरें मिलीं: ${titles}`
    : `I found these relevant stories: ${titles}`;
}

function selectContextChunks(chunks: ChunkRow[], limit: number = 8, perEventLimit: number = 2): ChunkRow[] {
  const now = Date.now();
  const sorted = [...chunks].sort((a, b) => {
    const aSimilarity = a.similarity ?? 0;
    const bSimilarity = b.similarity ?? 0;
    const aAgeDays = a.time_stamp ? Math.max(0, (now - new Date(a.time_stamp).getTime()) / 86400000) : 30;
    const bAgeDays = b.time_stamp ? Math.max(0, (now - new Date(b.time_stamp).getTime()) / 86400000) : 30;
    const aScore = aSimilarity + Math.max(0, 0.12 - (aAgeDays * 0.01));
    const bScore = bSimilarity + Math.max(0, 0.12 - (bAgeDays * 0.01));
    return bScore - aScore;
  });

  const selected: ChunkRow[] = [];
  const perEvent = new Map<string, number>();
  for (const chunk of sorted) {
    const count = perEvent.get(chunk.event_id) ?? 0;
    if (count >= perEventLimit) continue;
    selected.push(chunk);
    perEvent.set(chunk.event_id, count + 1);
    if (selected.length >= limit) break;
  }

  return selected;
}

async function handleTopStoriesQuery(question: string, locale: string = 'en', openaiApiKey?: string): Promise<QueryResult> {
  try {
    const DEFAULT_LIMIT = 5;
    const MAX_CAP = 20;
    const requestedCount = Math.min(extractNumber(question) ?? DEFAULT_LIMIT, MAX_CAP);

    // Look up ALL "for_you" tags (there might be multiple with different weights)
    const forYouTags = await SeoTag.findAll({
      where: { name: 'for_you' },
      attributes: ['id'],
    });

    if (forYouTags.length === 0) {
      return {
        answer: getLocalizedMessage('error_fetching_trending', locale),
        references: []
      };
    }

    const forYouTagIds = forYouTags.map(t => t.id);
    console.log(`[TOP STORIES] Found ${forYouTagIds.length} "for_you" tag(s):`, forYouTagIds);

    // Fetch articles tagged with ANY "for_you" tag
    const { articles } = await getAllArticles({
      languageId: locale,
      limit: requestedCount,
      orTags: forYouTagIds,
    });

    if (articles.length === 0) {
      return {
        answer: getLocalizedMessage('error_fetching_trending', locale),
        references: []
      };
    }

    const descriptionFallback = locale === 'hi' ? 'कोई विवरण उपलब्ध नहीं' : 'No description available';
    const references = articles.map((a) => ({
      id: a.id,
      title: a.title,
      description: a.description || descriptionFallback,
      date: a.date,
      relevance_score: 1.0,
      seo_tags: [] as string[],
      image: a.image || ''
    }));

    // If no OpenAI key, return fallback
    if (!openaiApiKey) {
      return {
        answer: locale === 'hi' ? 'आपके लिए शीर्ष कहानियाँ यहाँ हैं:' : 'Here are your top stories:',
        references
      };
    }

    // Build context from articles for LLM
    const articleContext = articles
      .map(a => `- ${a.title}${a.description ? ': ' + a.description : ''}`)
      .join('\n');

    const languageInstruction = getLanguageInstruction(locale);
    const topStoriesCount = Math.min(requestedCount, articles.length);
    const systemPrompt = `You are a ThinkO news assistant. Write a 1-sentence summary of what's happening, then list the top ${topStoriesCount} stories. Maximum 100 words total. Be extremely concise. No elaboration or filler. ${languageInstruction}`;

    const userPrompt = `Top stories for you:\n${articleContext}\n\nProvide a brief natural summary of these personalized top ${topStoriesCount} stories.`;

    try {
      const openai = new OpenAI({ apiKey: openaiApiKey });
      const timeoutPromise = new Promise<never>((_, reject) =>
        setTimeout(() => reject(new Error('LLM timeout')), 10000)
      );

      const completionPromise = openai.chat.completions.create({
        model: process.env.OPENAI_ASSISTANT_MODEL || 'gpt-5-nano',
        messages: [
          { role: 'system', content: systemPrompt },
          { role: 'user', content: userPrompt },
        ],
        max_completion_tokens: 250,
      } as any);

      const completion = await Promise.race([completionPromise, timeoutPromise]);
      const answer = (completion as any).choices[0]?.message?.content || (locale === 'hi' ? 'आपके लिए शीर्ष कहानियाँ यहाँ हैं:' : 'Here are your top stories:');

      return { answer, references };
    } catch {
      // Fallback to simple intro if LLM fails
      return {
        answer: locale === 'hi' ? 'आपके लिए शीर्ष कहानियाँ यहाँ हैं:' : 'Here are your top stories:',
        references
      };
    }
  } catch (error) {
    console.error('[TOP STORIES QUERY] Error:', error);
    return {
      answer: getLocalizedMessage('error_trending', locale),
      references: []
    };
  }
}

interface QueryResult {
  answer: string;
  references: Reference[];
}

interface Reference {
  id: string;
  title: string;
  description: string;
  date: Date;
  relevance_score: number;
  seo_tags: string[];
  image: string;
}

interface ChunkRow {
  event_id: string;
  chunk_text: string;
  title: string;
  chunk_type: string;
  time_stamp: Date;
  seo_tags: string[];
  image?: string;
  similarity?: number;
}

interface QueryParams {
  question: string;
  sequelize: Sequelize;
  openaiApiKey: string;
  locale?: string; // Language locale (e.g., 'en', 'hi'), defaults to 'en'
}

function isDatabaseInfoQuery(question: string): boolean {
  const lower = question.toLowerCase().trim();
  return (
    (lower.includes('database') || lower.includes('data') || lower.includes('knowledge')) &&
    (lower.includes('latest') || lower.includes('recent') || lower.includes('up to date') ||
     lower.includes('updated') || lower.includes('how old') || lower.includes('cutoff') ||
     lower.includes('how latest') || lower.includes('how new'))
  );
}

export async function queryAssistant(params: QueryParams): Promise<QueryResult> {
  const { question, sequelize, openaiApiKey, locale = 'en' } = params;

  // Step 0: Check for greetings and personal/meta queries FIRST (route to LLM directly, not RAG)
  if (isGreeting(question) || isPersonalOrMetaQuery(question)) {
    console.log(`[DIRECT LLM] Greeting or meta query: "${question}"`);
    try {
      const openai = new OpenAI({ apiKey: openaiApiKey });
      const languageInstruction = getLanguageInstruction(locale);
      const systemPrompt = `You are the ThinkO news assistant. Respond naturally and friendly to the user's greeting or question. Be conversational and concise. Keep your response to 1-2 sentences. Explain that you help find and understand news and current events. Vary your responses - don't repeat the same greeting every time. ${languageInstruction}`;

      const completion = await Promise.race([
        openai.chat.completions.create({
          model: ASSISTANT_MODEL,
          messages: [
            { role: 'system', content: systemPrompt },
            { role: 'user', content: question },
          ],
          max_completion_tokens: 100,
        } as any),
        new Promise<never>((_, reject) =>
          setTimeout(() => reject(new Error('LLM timeout')), 5000)
        ),
      ]);

      const answer = (completion as any).choices[0]?.message?.content || 'Hi there!';
      return {
        answer: answer.trim(),
        references: [],
      };
    } catch (error) {
      console.error('[DIRECT LLM] Error:', error);
      // Fallback to brief intro if LLM fails
      const fallback = locale === 'hi'
        ? 'नमस्ते! मैं ThinkO न्यूज सहायक हूँ। मैं आपको समाचार खोजने में मदद कर सकता हूँ।'
        : 'Hi! I\'m ThinkO\'s news assistant. I can help you find and understand news.';
      return {
        answer: fallback,
        references: [],
      };
    }
  }

  // Step 0.05: Check for suggestion keys (when user clicks a suggestion button)
  if (question.toLowerCase().trim() === 'top_stories') {
    console.log(`[TOP STORIES SUGGESTION] User clicked Top Stories suggestion`);
    return await handleTopStoriesQuery(question, locale, openaiApiKey);
  }

  // Step 0.1: Check for database/knowledge-cutoff queries and answer with actual DB date
  if (isDatabaseInfoQuery(question)) {
    try {
      const latestEvent = await sequelize.models.Event.findOne({
        order: [['time_stamp', 'DESC']],
        attributes: ['time_stamp'],
      });
      const latestDate = latestEvent
        ? new Date((latestEvent as any).time_stamp).toLocaleDateString(
            locale === 'hi' ? 'hi-IN' : 'en-GB',
            { day: 'numeric', month: 'long', year: 'numeric' }
          )
        : new Date().toLocaleDateString('en-GB', { day: 'numeric', month: 'long', year: 'numeric' });
      const answer =
        locale === 'hi'
          ? `हमारा समाचार डेटाबेस निरंतर अपडेट होता रहता है। सबसे हाल के लेख ${latestDate} तक के हैं।`
          : `Our news database is continuously updated with the latest articles. The most recent articles are from ${latestDate}.`;
      return { answer, references: [] };
    } catch (_err) {
      console.error('[DB INFO QUERY] Error fetching latest event date:', _err);
      const answer =
        locale === 'hi'
          ? 'हमारा समाचार डेटाबेस प्रतिदिन अपडेट किया जाता है।'
          : 'Our news database is updated daily with the latest news articles.';
      return { answer, references: [] };
    }
  }

  // Step 0.5: Detect and translate Hindi queries
  let originalQuestion = question;
  let processedQuestion = question;
  const isHindi = locale === 'hi' || isHindiText(question);
  
  if (isHindi) {
    try {
      // Translation now has built-in retry logic with exponential backoff
      // It will retry up to 2 times automatically on timeout
      processedQuestion = await translateToEnglish(question, openaiApiKey);
      
      // Validate translation: must be different from original and not contain Hindi
      const translationSuccess = processedQuestion !== originalQuestion && !isHindiText(processedQuestion);
      
      // If translation completely failed (still Hindi), try to proceed anyway
      // The system might still be able to extract some entities/categories from transliterated text
      if (!translationSuccess && isHindiText(processedQuestion)) {
        console.warn(`[TRANSLATION] Translation failed, proceeding with original Hindi text`);
        // Don't return error - let the system try to process it
        // It might still work for simple queries or we'll get a proper "no articles" message
      }
    } catch (error) {
      console.error(`[TRANSLATION] Translation error:`, error);
      processedQuestion = originalQuestion;
      // Don't return error - proceed with original text
      // The query processing might still work or will return appropriate "no articles" message
    }
  } else {
  }


  // Step 1: Check for Top Stories FIRST (before Top News, to avoid false matches)
  // "top stories" should route to for_you tagged articles, not temporal top news
  // BUT: if user specifies an entity/topic qualifier (e.g., "top news about rbi"),
  // fall through to RAG pipeline for entity-filtered results
  const entities = extractEntities(processedQuestion);
  const hasEntityQualifier = entities.length > 0;

  if (isTopStoriesQuery(processedQuestion) && !hasEntityQualifier) {
    console.log(`[TOP STORIES] Detected top stories query: "${processedQuestion}"`);
    return await handleTopStoriesQuery(processedQuestion, locale, openaiApiKey);
  }

  // Step 1b: Top News query - now routes to Top Stories (both use for_you tagged articles)
  // UNLESS there's an entity qualifier, then let RAG handle it for entity-filtered results
  if (isTopNewsQuery(processedQuestion) && !hasEntityQualifier) {
    console.log(`[TOP NEWS] Detected top news query: "${processedQuestion}" - routing to Top Stories`);
    return await handleTopStoriesQuery(processedQuestion, locale, openaiApiKey);
  }

  // If top query with entity qualifier, fall through to RAG pipeline for semantic search
  if ((isTopNewsQuery(processedQuestion) || isTopStoriesQuery(processedQuestion)) && hasEntityQualifier) {
    console.log(`[TOP QUERY WITH ENTITY] Detected "${processedQuestion}" with entity filter [${entities.join(', ')}] - routing to RAG pipeline`);
  }

  // Check for temporal context
  const temporalContext: TemporalContext | null = TemporalQueryParser.parseTemporalQuery(processedQuestion);

  // If temporal context found AND no entities, use handleTemporalQuery directly
  // Phase 0: date filters should constrain retrieval, not bypass embedding/RAG.

  // Latest news: only when query is PURELY about recency with no topic keywords.
  // "latest news" → yes; "latest ai developments" / "latest india news" → no (go to semantic search)
  const latestOnlyStopWords = new Set([
    'latest', 'recent', 'news', 'today', 'trending', 'new', 'show', 'give', 'tell',
    'what', 'are', 'the', 'me', 'some', 'any', 'top', 'big', 'now',
    'happening', 'going', 'on', 'right', 'up', 'doing', 'happened', 'occurred'
  ]);
  // 2-char acronyms that are valid topic entities — explicitly excluded from the
  // "no topic keywords" path so "ai news" / "it news" / "uk news" don't fall through
  // to handleLatestNewsQuery (which only checks w.length > 2 otherwise).
  const known2CharTopics = new Set(['ai', 'it', 'uk', 'eu', 'us', 'un', 'vc',
    'rr', 'mi', 'gt', 'dc', 'csk', 'rcb', 'kkr', 'srh', 'lsg', 'pbks']);
  const hasTopicKeywords = processedQuestion.toLowerCase()
    .split(/\W+/)
    .some(w => !latestOnlyStopWords.has(w) && (w.length > 2 || known2CharTopics.has(w)));

  if (!temporalContext && !hasTopicKeywords && isLatestQuery(processedQuestion)) {
    return await handleLatestNewsQuery(processedQuestion, locale, openaiApiKey);
  }

  // Step 2: Retrieve relevant chunks via global pgvector similarity search.
  // ─────────────────────────────────────────────────────────────────────────
  // PRIMARY – pgvector cosine similarity using stored FastEmbed embeddings.
  //   The query is embedded in-process (all-MiniLM-L6-v2 ONNX, same model
  //   as Python FastEmbed) so vectors are compatible with assistant_chunks.
  //
  // FALLBACK – ILIKE keyword search (used when embedder fails to load).
  // ─────────────────────────────────────────────────────────────────────────

  // Minimum cosine similarity a chunk must reach to be considered relevant.
  // Raised from 0.3 to filter out semantically-adjacent-but-unrelated results.
  const SIMILARITY_THRESHOLD = 0.45;

  let chunks: ChunkRow[] = [];
  let usedOlderArticles = false;
  let topSimilarity = -1; // -1 = not computed (ILIKE fallback path used)

  // ── 2a. Embed the query locally (all-MiniLM-L6-v2 ONNX, in-process) ─────
  const queryVec = await embedText(processedQuestion);
  console.log(`[rag] embedText: ${queryVec !== null ? `vector[${queryVec.length}]` : (chunks.length > 0 ? 'skipped (early ILIKE found results)' : 'null')}`);

  if (queryVec !== null) {
    const vecLiteral = `[${queryVec.join(',')}]`;

    // Helper: build + run a pgvector query with optional extra WHERE clauses
    const runSemQuery = async (extraClauses: string[], extraBinds: any[], limit = 20): Promise<ChunkRow[]> => {
      const bind = [vecLiteral, ...extraBinds];
      const parts = [
        `SELECT
          ac.event_id,
          ac.chunk_text,
          ac.title,
          ac.chunk_type,
          e.time_stamp,
          e.image,
          array_agg(DISTINCT st.name) FILTER (WHERE st.name IS NOT NULL) AS seo_tags,
          1 - (ac.embedding <=> $1::vector) AS similarity
        FROM assistant_chunks ac
        JOIN event e ON ac.event_id = e.id
        LEFT JOIN event_seo_tag est ON e.id = est.event_id
        LEFT JOIN seo_tag st ON est.seo_tag_id = st.id
        WHERE 1=1`,
        ...extraClauses,
        `GROUP BY ac.id, ac.event_id, ac.chunk_text, ac.title, ac.chunk_type, e.time_stamp, e.image, ac.embedding
        ORDER BY ac.embedding <=> $1::vector
        LIMIT ${Math.floor(limit)}`,
      ];
      return sequelize.query(parts.join('\n'), { bind, type: QueryTypes.SELECT }) as Promise<ChunkRow[]>;
    };

    if (temporalContext) {
      // User specified an explicit date — respect it, no recency window
      chunks = await runSemQuery(
        [`AND e.time_stamp >= $2::date`, `AND e.time_stamp < ($3::date + INTERVAL '1 day')`],
        [temporalContext.date_range.start, temporalContext.date_range.end],
      );
    } else {
      // Pass 1: last 5 days — fetch 20 candidates so the entity-filter has a large
      // enough pool to surface the most RECENT relevant articles, not just the most
      // similar ones (which may be a day or two older).
      chunks = await runSemQuery([`AND e.time_stamp >= NOW() - INTERVAL '5 days'`], [], 20);
      console.log(`[rag] recent (5d) search returned ${chunks.length} chunks`);

      // Pass 2: last 10 days
      if (chunks.length === 0) {
        chunks = await runSemQuery([`AND e.time_stamp >= NOW() - INTERVAL '10 days'`], [], 20);
        console.log(`[rag] recent (10d) search returned ${chunks.length} chunks`);
        if (chunks.length > 0) {
          usedOlderArticles = true;
        }
      }

      // Pass 3: all-time — fetch top 20 candidates, keep only those above the similarity
      // threshold, then sort by recency so the LLM sees the latest relevant coverage first.
      if (chunks.length === 0) {
        const allCandidates = await runSemQuery([], [], 20);
        const thresholded = allCandidates.filter(c => (c.similarity ?? 0) >= SIMILARITY_THRESHOLD);
        thresholded.sort((a, b) => new Date(b.time_stamp).getTime() - new Date(a.time_stamp).getTime());
        chunks = thresholded.slice(0, 20);
        if (chunks.length > 0) {
          usedOlderArticles = true;
          console.log(`[rag] fell back to global threshold-filtered search, top chunk date: ${chunks[0]?.time_stamp}`);
        }
      }
    }

    topSimilarity = chunks[0]?.similarity ?? 0;
    console.log(`[rag] final chunks=${chunks.length}, top similarity: ${topSimilarity.toFixed(3)}, older=${usedOlderArticles}`);
  }

  // ── 2b. ILIKE fallback (embedder returned null on model error) ────────────
  if (chunks.length === 0) {
    const querySegments = [`
      SELECT
        ac.event_id,
        ac.chunk_text,
        ac.title,
        ac.chunk_type,
        e.time_stamp,
        e.image,
        array_agg(DISTINCT st.name) FILTER (WHERE st.name IS NOT NULL) AS seo_tags
      FROM assistant_chunks ac
      JOIN event e ON ac.event_id = e.id
      LEFT JOIN event_seo_tag est ON e.id = est.event_id
      LEFT JOIN seo_tag st ON est.seo_tag_id = st.id
      WHERE 1=1
    `];
    const bindValues: any[] = [];
    let bindIndex = 1;

    if (temporalContext) {
      querySegments.push(`AND e.time_stamp >= $${bindIndex}::date`);
      bindValues.push(temporalContext.date_range.start);
      bindIndex++;
      querySegments.push(`AND e.time_stamp < ($${bindIndex}::date + INTERVAL '1 day')`);
      bindValues.push(temporalContext.date_range.end);
      bindIndex++;
    }

    querySegments.push(`GROUP BY ac.id, ac.event_id, ac.chunk_text, ac.title, ac.chunk_type, e.time_stamp, e.image`);
    querySegments.push(`ORDER BY e.time_stamp DESC LIMIT 20`);

    chunks = await sequelize.query(querySegments.join('\n'), {
      bind: bindValues,
      type: QueryTypes.SELECT,
    }) as ChunkRow[];
  }

  if (chunks.length === 0) {
    return {
      answer: getLocalizedMessage('no_articles_found', locale),
      references: [],
    };
  }

  // Step 5: Group the strongest retrieved chunks by event for a compact prompt.
  // Keep retrieval broad (10-20 chunks), but only send the best few to the LLM so
  // responses reliably finish inside the short API timeout.
  const contextChunks = selectContextChunks(chunks, 8, 2);
  const eventMap = new Map<string, ChunkRow[]>();
  for (const chunk of contextChunks) {
    if (!eventMap.has(chunk.event_id)) {
      eventMap.set(chunk.event_id, []);
    }
    eventMap.get(chunk.event_id)!.push(chunk);
  }


  // Step 6: Prepare context for LLM and references with signed image URLs (parallel signing)
  const contextParts: string[] = [];

  const references: Reference[] = await Promise.all(
    Array.from(eventMap.entries()).map(async ([eventId, eventChunks]) => {
      const firstChunk = eventChunks[0];
      const articleTitle = firstChunk.title || 'Untitled';
      const combinedText = eventChunks.map(c => {
        const snippet = c.chunk_text.replace(/\s+/g, ' ').trim();
        const trimmed = snippet.length > 320 ? snippet.substring(0, 320) + '...' : snippet;
        const chunkType = c.chunk_type ? `[${c.chunk_type}] ` : '';
        return `${chunkType}${trimmed}`;
      }).join('\n\n');

      const tags = (firstChunk.seo_tags ?? []).join(', ');
      const tagLine = tags ? `Tags: ${tags}\n` : '';
      const dateLine = firstChunk.time_stamp ? `Date: ${new Date(firstChunk.time_stamp).toISOString().split('T')[0]}\n` : '';
      contextParts.push(`Title: ${articleTitle}\n${dateLine}${tagLine}Snippets:\n${combinedText}`);

      const signedImageUrl = firstChunk.image
        ? (await getSignedImageUrl(firstChunk.image)) || ''
        : '';

      return {
        id: eventId,
        title: articleTitle,
        description: combinedText.substring(0, 300) + (combinedText.length > 300 ? '...' : ''),
        date: firstChunk.time_stamp ? new Date(firstChunk.time_stamp) : new Date(),
        relevance_score: eventChunks.length / Math.max(contextChunks.length, 1),
        seo_tags: firstChunk.seo_tags || [],
        image: signedImageUrl,
      };
    })
  );

  // Sort references by date descending (most recent first)
  references.sort((a, b) => b.date.getTime() - a.date.getTime());

  // Filter out weakly-associated references.
  // relevance_score = chunks_from_this_event / total_chunks, so a score of 0.05 means
  // only 1 chunk out of 20 came from that article — a weak signal that it's relevant.
  // Keep only references that contributed meaningfully, or fall back to top 3 if all scores are low.
  const MIN_RELEVANCE = 0.1;
  const filtered = references.filter(r => r.relevance_score >= MIN_RELEVANCE);
  const finalReferences = filtered.length > 0 ? filtered : references.slice(0, 3);

  const context = contextParts.join('\n\n---\n\n');

  // Step 7: Call OpenAI to generate answer
  const languageInstruction = getLanguageInstruction(locale);
  
  // Build prompt with translation context if applicable
  let questionContext = '';
  if (isHindi && originalQuestion !== processedQuestion) {
    questionContext = `The user asked (in Hindi): "${originalQuestion}"\nThis translates to: "${processedQuestion}"\n\nPlease answer based on the translated question, but respond in ${locale === 'hi' ? 'Hindi' : 'English'}.`;
  } else {
    questionContext = `User Question: ${processedQuestion}`;
  }
  
  // When no recent articles matched, compute the date of the oldest article shown
  // so the LLM can mention the timeframe to the user.
  let olderArticlesNote = '';
  if (usedOlderArticles && chunks.length > 0) {
    const dates = chunks
      .map(c => c.time_stamp ? new Date(c.time_stamp) : null)
      .filter(Boolean) as Date[];
    if (dates.length > 0) {
      const latest = new Date(Math.max(...dates.map(d => d.getTime())));
      const formatted = latest.toLocaleDateString('en-GB', { day: 'numeric', month: 'long', year: 'numeric' });
      olderArticlesNote = `\n\nNote: No articles from the last 3 days were found on this topic. The articles above are from around ${formatted}. Mention this timeframe briefly in your answer (e.g. "As of [date]...").`;
    }
  }

  const prompt = `ThinkO article context:
${context}

${questionContext}${olderArticlesNote}

Answer as the ThinkO assistant. Use the article facts above for events and decisions. For implications and outcomes, reason from the facts and your knowledge. Do not mention retrieval, context, snippets, or internal processes.`;

  // Prepare fallback message (already localized)
  const fallbackMessage = locale === 'hi' 
    ? "मुझे कुछ प्रासंगिक लेख मिले, लेकिन मैं प्रतिक्रिया उत्पन्न नहीं कर सका। कृपया नीचे दिए गए संदर्भ देखें।"
    : "I found some relevant articles, but couldn't generate a response. Please check the references below.";

  // Check if we have any references before calling OpenAI
  if (finalReferences.length === 0) {
    return {
      answer: getLocalizedMessage('no_articles_found', locale),
      references: [],
    };
  }

  // Use OpenAI API with error handling and timeout
  const openai = new OpenAI({ apiKey: openaiApiKey });

  const retrievalSystemMessage = `You are a ThinkO news assistant. Use the article context provided to answer factual questions about events, decisions, and news. When the user asks about implications, impacts, or outcomes (e.g. "how does this affect me?", "what happens next?"), use the article facts as a base and reason clearly about likely effects using your knowledge. Do not mention retrieval, context, or internal processes. Do not say information is unavailable — use what you know.

For temporal queries (e.g. "news from yest", "what happened tdy", "tmrw stories"), interpret informal abbreviations naturally and answer based on the article dates provided: "yest"=yesterday, "tdy"=today, "tmrw"=tomorrow.

RESPONSE LENGTH:
- News/topic queries: Maximum 120 words. Provide 1-2 concise paragraphs with only essential information.
- Personal comments or casual questions: 1 sentence. Do not elaborate.
- Factual questions without articles: Shortest possible answer (1-2 sentences).

GUIDELINES:
- Be extremely direct and concise. Eliminate all filler, redundancy, and unnecessary elaboration.
- One fact per sentence. No compound sentences with "and" or "also".
- Skip introductory phrases like "It's important to note", "Interestingly", "Another point is".
- Always complete sentences, never cut off mid-sentence.
- Prioritize key information: WHO, WHAT, WHEN, WHY. Skip everything else.

${languageInstruction}`;

  const timeoutMs = 10000;

  console.log(`[ai] calling model=${ASSISTANT_MODEL}, apiKey=${openaiApiKey ? 'set' : 'MISSING'}, timeout=${timeoutMs}ms`);

  try {
    // Use Promise.race to implement timeout
    const timeoutPromise = new Promise<never>((_, reject) => {
      setTimeout(() => {
        reject(new Error('OpenAI API call timed out'));
      }, timeoutMs);
    });

    const completionPromise = openai.chat.completions.create({
      model: ASSISTANT_MODEL,
      messages: [
        {
          role: 'user',
          content: `${retrievalSystemMessage}\n\n${prompt}`,
        },
      ],
      max_completion_tokens: 300,
    } as any);

    const completion = await Promise.race([completionPromise, timeoutPromise]);

    // If we get here, completion is valid (not timeout)
    const rawContent = (completion as any).choices[0]?.message?.content;
    const finishReason = (completion as any).choices[0]?.finish_reason;
    console.log(`[ai] finish_reason=${finishReason}, rawContent=${JSON.stringify(rawContent?.substring(0, 150))}`);
    const answer = rawContent || fallbackMessage;
    console.log(`[ai] got response, length=${answer.length}`);

    return {
      answer: answer.trim(),
      references: finalReferences,
    };
  } catch (error: any) {
    // Check if it's a timeout error
    const isTimeout = error.message?.includes('timed out') ||
                      error.name === 'APIConnectionTimeoutError' ||
                      error.code === 'ECONNABORTED' ||
                      error.message?.includes('timeout');

    if (isTimeout) {
      console.error(`[AI ERROR] OpenAI call timed out after ${timeoutMs}ms`);
      // On timeout, keep the user-facing answer clean and let cards carry details.
      const fallbackAnswer = formatReferenceFallbackAnswer(finalReferences, locale);
      return { answer: fallbackAnswer, references: finalReferences };
    }

    console.error('[AI ERROR] OpenAI call failed:', error?.message || error, 'status:', error?.status, 'code:', error?.code);

    if (finalReferences.length === 0) {
      return { answer: getLocalizedMessage('no_articles_found', locale), references: [] };
    }

    return { answer: fallbackMessage, references: finalReferences };
  }
}
