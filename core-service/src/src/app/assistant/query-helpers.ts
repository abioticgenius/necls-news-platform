/**
 * Helper functions for query processing and entity detection
 */

// Merged, deduplicated stop words set (module-level constant)
// Used for entity extraction filtering — words in this set are not considered entity terms
const STOP_WORDS = new Set([
  // 2-char stop words
  'vs', 'in', 'of', 'to', 'or', 'as', 'by', 'if', 'up', 'an', 'so', 'no',
  'he', 'it', 'we', 'my', 'go', 'do', 'be', 'me', 'is', 'am', 'ha',
  // Common stop words
  'the', 'and', 'for', 'are', 'but', 'not', 'you', 'all', 'can', 'her', 'was', 'one', 'our', 'out',
  'day', 'get', 'has', 'him', 'his', 'how', 'its', 'may', 'new', 'now', 'old', 'see', 'two', 'way',
  'who', 'boy', 'did', 'let', 'put', 'say', 'she', 'too', 'use', 'news', 'related', 'show',
  'top', 'what', 'whats', 'will', 'would', 'could', 'should', 'does', 'been', 'have', 'had',
  // Temporal/date-related words
  'today', 'yesterday', 'tomorrow', 'latest', 'recent', 'trending', 'happened', 'happen', 'happens', 'happening',
  'updates', 'update', 'breaking', 'developments', 'developing',
  'stories', 'story', 'articles', 'article', 'headlines', 'headline',
  'jan', 'january', 'feb', 'february', 'mar', 'march', 'apr', 'april', 'may', 'jun', 'june',
  'jul', 'july', 'aug', 'august', 'sep', 'september', 'oct', 'october', 'nov', 'november',
  'dec', 'december',
  'monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday',
  'week', 'month', 'year', 'ago', 'from', 'on', 'at', 'when', 'date', 'time',
  // Question-phrasing verbs / gerunds
  'going', 'coming', 'getting', 'making', 'taking', 'saying', 'telling', 'looking',
  'thinking', 'knowing', 'seeing', 'doing', 'tell', 'know', 'mean', 'means',
  'just', 'between', 'with', 'also', 'even', 'some', 'such', 'there', 'their', 'they',
  'them', 'then', 'than', 'like', 'more', 'most', 'very', 'really', 'ever', 'never',
  'always', 'still', 'only', 'much', 'many', 'both', 'each', 'other', 'another', 'same',
  'different', 'while', 'since', 'right', 'left', 'this', 'that', 'these', 'those',
  // Query intent words
  'summarize', 'summarizing', 'summary', 'summaries', 'summarisation', 'summarization',
  'overview', 'describe', 'description', 'explain', 'explanation', 'brief', 'briefing',
  'detail', 'details', 'elaborate', 'outline', 'breakdown', 'provide', 'list',
  // Ordinal numbers
  '1st', '2nd', '3rd', '4th', '5th', '6th', '7th', '8th', '9th', '10th',
  '11th', '12th', '13th', '14th', '15th', '16th', '17th', '18th', '19th', '20th',
  '21st', '22nd', '23rd', '24th', '25th', '26th', '27th', '28th', '29th', '30th', '31st',
  // Generic topic/status/action words
  'crisis', 'crises', 'issue', 'issues', 'problem', 'problems', 'situation', 'situations',
  'resolve', 'resolves', 'resolved', 'resolving', 'resolution', 'resolutions',
  'matter', 'matters', 'case', 'cases', 'event', 'events',
  'policy', 'policies', 'plan', 'plans', 'strategy', 'strategies',
  'impact', 'impacts', 'effect', 'effects', 'cause', 'causes', 'affect', 'affects',
  'level', 'levels', 'rate', 'rates', 'price', 'prices', 'cost', 'costs',
  'status', 'condition', 'conditions', 'result', 'results', 'outcome', 'outcomes',
  'begin', 'began', 'start', 'started', 'end', 'ended', 'over', 'done',
  'come', 'came', 'goes', 'went', 'take', 'took', 'give', 'gave',
  'think', 'thought', 'said', 'says', 'want', 'wants', 'need', 'needs',
  'talk', 'talks', 'meet', 'met', 'hold', 'held', 'call', 'calls',
  'report', 'reports', 'show', 'shows', 'find', 'found', 'face', 'faces',
  'rise', 'rose', 'fall', 'fell', 'drop', 'dropped', 'raise', 'raised', 'movie', 'film',
  // Sports / result verbs
  'won', 'win', 'wins', 'winning', 'winner', 'winners',
  'lost', 'lose', 'loses', 'losing', 'loser',
  'beat', 'beats', 'beaten', 'defeat', 'defeats', 'defeated',
  'drew', 'draw', 'draws', 'tie', 'tied', 'ties',
  'played', 'play', 'plays', 'playing', 'player', 'players',
  'scored', 'score', 'scores', 'scoring',
  // Generic temporal qualifiers
  'last', 'next', 'previous', 'upcoming', 'first', 'second', 'third', 'final',
  // Prepositions (from allStopWords)
  'about', 'above', 'across', 'after', 'against', 'along', 'among', 'around', 'before', 'behind',
  'below', 'beneath', 'beside', 'between', 'beyond', 'during', 'except', 'inside', 'into', 'near',
  'outside', 'over', 'through', 'throughout', 'toward', 'towards', 'under', 'underneath', 'until',
  'upon', 'within', 'without',
  // Question words
  'where', 'why', 'which', 'whose', 'whom',
  // Additional verbs
  'do', 'does', 'did', 'will', 'would', 'could', 'should', 'may', 'might', 'must', 'can', 'cannot',
]);

/**
 * Detects if query is asking for a specific entity (person, place, organization)
 */
export function extractEntities(question: string): string[] {
  const entities: string[] = [];
  const lowerQuestion = question.toLowerCase();

  // Common entity patterns
  const entityPatterns = [
    // Person names (capitalized words)
    /\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b/g,
    // Common entities (case-insensitive)
    /\b(trump|biden|modi|putin|xi|musk|bezos|gates)\b/gi,
  ];

  for (const pattern of entityPatterns) {
    const matches = question.match(pattern);
    if (matches) {
      entities.push(...matches.map(m => m.toLowerCase()));
    }
  }

  // Extract capitalized words that might be entities (cities, places, people, organizations)
  const words = question.split(/\s+/);
  for (const word of words) {
    if (word.length > 2 && /^[A-Z][a-z]+$/.test(word)) {
      entities.push(word.toLowerCase());
    }
  }

  // Extract lowercase words that might be entities (locations, topics, etc.)
  // This is the PRIMARY method for extracting entities like "india", "china", etc.
  const lowercaseWords = lowerQuestion.split(/\W+/).filter(word => word.length > 1);
  for (const word of lowercaseWords) {
    if (!STOP_WORDS.has(word) && word.length > 1) {
      entities.push(word);
    }
  }

  // Filter out pure numbers and ordinal numbers
  const filteredEntities = entities.filter(entity => {
    if (/^\d+$/.test(entity)) return false; // pure numbers
    if (/^\d+(st|nd|rd|th)$/.test(entity)) return false; // ordinals
    return true;
  });

  let uniqueEntities = [...new Set(filteredEntities)]; // deduplicate

  // Remove single-word entities that are components of multi-word entities
  const multiWordEntities = uniqueEntities.filter(e => e.includes(' '));
  if (multiWordEntities.length > 0) {
    uniqueEntities = uniqueEntities.filter(entity => {
      if (entity.includes(' ')) return true;
      return !multiWordEntities.some(mwe => mwe.split(' ').includes(entity));
    });
  }

  // Final filter: remove any remaining stop words
  uniqueEntities = uniqueEntities.filter(entity => !STOP_WORDS.has(entity.toLowerCase()));

  return uniqueEntities;
}

/**
 * Expands a broad/abstract query term to its concrete SEO-tag and keyword equivalents.
 *
 * Used in two places:
 *  1. In-memory entity filter  — so "geopolitical" matches chunks tagged "global",
 *     "foreign_affairs", etc. even when the word "geopolitical" isn't in the text.
 *  2. ILIKE SQL fallback        — so the keyword search also covers the expanded terms.
 *
 * Keys are the lowercased extracted entity; values are the concrete terms to check.
 * The original entity is always tried first; the expansions supplement it.
 */
export const ENTITY_EXPANSIONS: Record<string, string[]> = {
  // ── Geopolitical / international ──────────────────────────────────────────
  geopolitical:   ['global', 'foreign_affairs', 'diplomacy', 'international', 'war', 'conflict', 'tension'],
  geopolitics:    ['global', 'foreign_affairs', 'diplomacy', 'international'],
  international:  ['global', 'foreign_affairs'],
  diplomatic:     ['diplomacy', 'foreign_affairs', 'international'],
  diplomacy:      ['foreign_affairs', 'international', 'diplomatic'],
  bilateral:      ['diplomacy', 'foreign_affairs', 'international'],
  multilateral:   ['diplomacy', 'foreign_affairs', 'international', 'global'],
  sovereignty:    ['border', 'territory', 'conflict', 'foreign_affairs'],
  sanctions:      ['sanction', 'embargo', 'restriction', 'trade'],
  ceasefire:      ['war', 'conflict', 'peace', 'truce'],
  peacekeeping:   ['peace', 'conflict', 'united_nations', 'military'],

  // ── Conflict / military ────────────────────────────────────────────────────
  military:       ['war', 'army', 'defense', 'forces', 'security', 'conflict'],
  warfare:        ['war', 'military', 'conflict', 'battle', 'attack'],
  conflict:       ['war', 'military', 'tension', 'battle', 'attack'],
  terrorism:      ['terror', 'militant', 'extremism', 'attack', 'security'],
  insurgency:     ['militant', 'terror', 'conflict', 'military'],
  nuclear:        ['nuclear_deal', 'nuclear_weapons', 'nonproliferation', 'missile'],

  // ── Economy / trade ───────────────────────────────────────────────────────
  economic:       ['economy', 'business', 'finance', 'trade', 'gdp', 'growth'],
  economics:      ['economy', 'business', 'finance', 'gdp'],
  financial:      ['finance', 'business', 'economy', 'banking', 'market'],
  fiscal:         ['budget', 'tax', 'deficit', 'finance', 'economy'],
  monetary:       ['rbi', 'fed', 'interest_rate', 'inflation', 'central_bank'],
  tariff:         ['trade', 'import', 'export', 'sanction', 'tariff'],

  // ── Political / governance ────────────────────────────────────────────────
  political:      ['politics', 'government', 'election', 'parliament', 'policy'],
  governance:     ['government', 'policy', 'parliament', 'administration'],
  legislative:    ['parliament', 'congress', 'bill', 'law', 'legislation'],
  democratic:     ['election', 'democracy', 'vote', 'government'],

  // ── Technology ────────────────────────────────────────────────────────────
  technological:  ['technology', 'tech', 'innovation', 'digital', 'artificial_intelligence'],
  cybersecurity:  ['cyber', 'hack', 'security', 'digital', 'technology'],
  // "ai news" / "artificial intelligence news" cross-linking.
  // The capitalized-words NLP pattern extracts 'artificial intelligence' as ONE combined entity
  // AND also 'artificial' + 'intelligence' individually (three total).
  // All three must be in ENTITY_EXPANSIONS so each clause resolves to 'ai' / 'artificial_intelligence'
  // and doesn't fail the AND gate for articles that only carry the short 'ai' seo_tag.
  // Frontend sends category queries as underscore-joined slugs (e.g. 'artificial_intelligence').
  // These must also expand to 'ai' so articles tagged only 'ai' (not 'artificial_intelligence') are found.
  'artificial intelligence': ['ai', 'artificial_intelligence', 'machine learning', 'ml'],
  artificial_intelligence:   ['ai', 'artificial intelligence', 'machine learning', 'ml'],
  ai:             ['artificial_intelligence', 'artificial intelligence', 'machine learning', 'ml'],
  artificial:     ['ai', 'artificial_intelligence', 'machine learning'],
  it:             ['information technology', 'technology', 'tech', 'digital'],

  // ── Environment / climate ─────────────────────────────────────────────────
  environmental:  ['climate', 'environment', 'pollution', 'sustainability', 'ecology'],
  environmental_policy: ['climate', 'environment', 'carbon', 'emissions'],

  // ── Humanitarian ─────────────────────────────────────────────────────────
  humanitarian:   ['aid', 'relief', 'refugee', 'rights', 'crisis'],
  refugee:        ['displacement', 'asylum', 'humanitarian', 'migration'],

  // ── World leaders / notable figures ────────────────────────────────────────
  trump:  ['donald trump', 'donald j trump', 'donald john trump', 'president trump'],
  biden:  ['joe biden', 'joseph biden', 'president biden'],
  modi:   ['narendra modi', 'pm modi', 'prime minister modi'],
  musk:   ['elon musk'],
  bezos:  ['jeff bezos'],

  // ── IPL team abbreviations ─────────────────────────────────────────────────
  rr:   ['rajasthan royals', 'rajasthan_royals'],
  mi:   ['mumbai indians', 'mumbai_indians'],
  csk:  ['chennai super kings', 'super kings'],
  rcb:  ['royal challengers', 'royal challengers bengaluru'],
  kkr:  ['kolkata knight riders', 'knight riders'],
  srh:  ['sunrisers hyderabad', 'sunrisers'],
  dc:   ['delhi capitals'],
  gt:   ['gujarat titans'],
  lsg:  ['lucknow super giants', 'super giants'],
  pbks: ['punjab kings'],
};

/**
 * Returns the entity plus all its expanded equivalents.
 * Falls back to just the entity itself when no expansion exists.
 */
export function getEntitySearchTerms(entity: string): string[] {
  const e = entity.toLowerCase();
  const expansions = ENTITY_EXPANSIONS[e];
  return expansions ? [e, ...expansions] : [e];
}

/**
 * Detects broad "what's happening" style queries and pure recency queries.
 * Returns true for "latest", "recent", "happening", "going on", "today?" type queries.
 */
export function isLatestQuery(question: string): boolean {
  const lowerQuestion = question.toLowerCase();
  const words = lowerQuestion.split(/\s+/).filter(w => w.length > 0);

  return (
    lowerQuestion.includes('latest') ||
    lowerQuestion.includes('recent') ||
    lowerQuestion.includes('happening') ||
    lowerQuestion.includes('going on') ||
    lowerQuestion.includes('whats up') ||
    /\bnew\b/i.test(lowerQuestion) ||
    (/\btoday\b/i.test(lowerQuestion) && words.length <= 4)  // short "today?" queries
  );
}

/**
 * Extracts a number from the user's question (e.g., "5 trending news" -> 5)
 */
export function extractNumber(question: string): number | null {
  const match = question.match(/\b(\d+)\b/);
  return match ? parseInt(match[1], 10) : null;
}

/**
 * Detects if the query is a greeting
 * @param question - User's question/query
 * @returns true if the query is a greeting
 */
export function isGreeting(question: string): boolean {
  const lowerQuestion = question.toLowerCase().trim();
  
  // Common greeting patterns
  const greetingPatterns = [
    // Simple greetings
    /^(hi|hello|hey|greetings|howdy|hola|namaste)$/i,
    // Greetings with punctuation
    /^(hi|hello|hey|greetings|howdy|hola|namaste)[!.,]*$/i,
    // Greetings with "there" or "you"
    /^(hi|hello|hey)\s+(there|you|ya)[!.,]*$/i,
    // Time-based greetings
    /^(good\s+(morning|afternoon|evening|night|day))[!.,]*$/i,
    // How are you variations
    /^(how\s+(are\s+you|do\s+you\s+do|is\s+it\s+going))[!.,?]*$/i,
    // What's up variations
    /^(what'?s?\s+up|wassup|sup)[!.,?]*$/i,
    // Hindi greetings
    /^(नमस्ते|नमस्कार|प्रणाम)[!.,]*$/i,
  ];
  
  // Check if the question matches any greeting pattern
  for (const pattern of greetingPatterns) {
    if (pattern.test(lowerQuestion)) {
      return true;
    }
  }
  
  // Check if it's a very short query (1-2 words) that might be a greeting
  const words = lowerQuestion.split(/\s+/).filter(w => w.length > 0);
  if (words.length <= 2) {
    const commonGreetings = ['hi', 'hello', 'hey', 'greetings', 'howdy', 'hola', 'namaste', 'नमस्ते', 'नमस्कार'];
    if (commonGreetings.some(greeting => lowerQuestion.includes(greeting))) {
      return true;
    }
  }
  
  return false;
}

export function isPersonalOrMetaQuery(question: string): boolean {
  const lowerQuestion = question.toLowerCase().trim();

  // Personal statements and comments (should get brief response)
  const personalPatterns = [
    // Birthday, anniversary, celebration comments
    /^it was my\s+(birthday|anniversary|wedding)/i,
    /^my (birthday|anniversary|wedding) (was|is|will be)/i,
    /^(happy|sad|excited|proud|angry)/i,
    // Personal stories/comments
    /^i (had|have|went|went to|did|am|am going)/i,
    /^(yesterday|today|tomorrow|last|next)\s+i\s+(had|went|did)/i,
  ];

  // Meta questions about the assistant itself
  const metaPatterns = [
    // About the assistant's capabilities
    /^(what|can|who) (are|is|do|can|should) you(\s+do)?/i,
    /^who are you/i,
    /^what can you (do|help with|assist with)/i,
    /^are you an? (ai|assistant|bot)/i,
    // Relationship/personal requests
    /^(be|become|act as|pretend to be) my\s+/i,
    /^(are|would) you my\s+/i,
    /^can you (be|become|date|marry) me/i,
    // Casual chatter
    /^(how|tell me|show me) (about|something about)/i,
    /^(do you|have you|are you) /i,
  ];

  // Check personal patterns
  for (const pattern of personalPatterns) {
    if (pattern.test(lowerQuestion)) {
      return true;
    }
  }

  // Check meta patterns
  for (const pattern of metaPatterns) {
    if (pattern.test(lowerQuestion)) {
      return true;
    }
  }

  return false;
}

/**
 * Language localization messages
 */
const localizedMessages: Record<string, Record<string, string>> = {
  en: {
    'no_articles_found': "I couldn't find any relevant articles matching your question. Please try rephrasing or asking about a different topic.",
    'error_occurred': "I encountered an error while searching for articles. Please try again.",
    'error_fetching_trending': "I couldn't fetch trending news articles at the moment. Please try again later.",
    'error_trending': "I encountered an error while fetching trending news. Please try again.",
    'no_articles_date': "I couldn't find any articles from {date}.",
    'top_news_from': "Top news from {date}: {title}",
    'top_news_list': "Top {count} news stories from {date}:\n{list}",
    'found_articles_period': "Found {count} articles from that time period. Here are the top {top}:\n{list}",
    'category_not_found': "I couldn't find any recent {category} news articles.",
    'category_found_no_summary': "I found {count} {category} articles but couldn't generate a summary. Here are the articles:",
    'article_not_found': "Article not found.",
    'article_content_unavailable': "Article content not available.",
    'article_assistant_help': "I can help you understand this article. Please ask questions about its content, summary, or analysis.",
    'greeting': "Hello! I'm ThinkO Assistant, your friendly news assistant. I can help you find and understand news articles on various topics. What would you like to know about?",
    'latest_news_intro': "Here are the latest news articles:",
  },
  hi: {
    'no_articles_found': "मुझे आपके प्रश्न से मेल खाने वाला कोई लेख नहीं मिला। कृपया अपने प्रश्न को दोबारा लिखें या किसी अन्य विषय के बारे में पूछें।",
    'error_occurred': "लेख खोजते समय मुझे एक त्रुटि का सामना करना पड़ा। कृपया पुनः प्रयास करें।",
    'error_fetching_trending': "मैं इस समय ट्रेंडिंग समाचार लेख प्राप्त नहीं कर सका। कृपया बाद में पुनः प्रयास करें।",
    'error_trending': "ट्रेंडिंग समाचार प्राप्त करते समय मुझे एक त्रुटि का सामना करना पड़ा। कृपया पुनः प्रयास करें।",
    'no_articles_date': "मुझे {date} से कोई लेख नहीं मिला।",
    'top_news_from': "{date} से शीर्ष समाचार: {title}",
    'top_news_list': "{date} से शीर्ष {count} समाचार कहानियां:\n{list}",
    'found_articles_period': "उस समय अवधि से {count} लेख मिले। यहां शीर्ष {top} हैं:\n{list}",
    'category_not_found': "मुझे हाल की {category} समाचार लेख नहीं मिले।",
    'category_found_no_summary': "मुझे {count} {category} लेख मिले लेकिन मैं सारांश उत्पन्न नहीं कर सका। यहां लेख हैं:",
    'article_not_found': "लेख नहीं मिला।",
    'article_content_unavailable': "लेख सामग्री उपलब्ध नहीं है।",
    'article_assistant_help': "मैं आपको इस लेख को समझने में मदद कर सकता हूं। कृपया इसकी सामग्री, सारांश, या विश्लेषण के बारे में प्रश्न पूछें।",
    'greeting': "नमस्ते! मैं ThinkO Assistant हूं, आपका मित्रतापूर्ण समाचार सहायक। मैं आपको विभिन्न विषयों पर समाचार लेख खोजने और समझने में मदद कर सकता हूं। आप किस बारे में जानना चाहेंगे?",
    'latest_news_intro': "यहां नवीनतम समाचार लेख हैं:",
  },
};

/**
 * Gets a localized message for the given key and locale
 * @param key - Message key
 * @param locale - Language locale (e.g., 'en', 'hi')
 * @param replacements - Optional object with replacement values for placeholders like {date}, {count}, etc.
 */
export function getLocalizedMessage(key: string, locale: string = 'en', replacements?: Record<string, string | number>): string {
  const localeMessages = localizedMessages[locale] || localizedMessages['en'];
  let message = localeMessages[key] || localizedMessages['en'][key] || key;
  
  // Replace placeholders if replacements provided
  if (replacements) {
    for (const [placeholder, value] of Object.entries(replacements)) {
      message = message.replace(new RegExp(`\\{${placeholder}\\}`, 'g'), String(value));
    }
  }
  
  return message;
}

// Language instruction strings for LLM prompts
const LANGUAGE_INSTRUCTIONS: Record<string, string> = {
  en: 'Respond in English.',
  hi: 'Respond in Hindi (हिंदी). Use Devanagari script for Hindi text.',
};

// Devanagari script Unicode range for Hindi detection
const DEVANAGARI_REGEX = /[\u0900-\u097F]/;

/**
 * Gets language instruction for OpenAI prompts
 * @param locale - Language locale (e.g., 'en', 'hi')
 */
export function getLanguageInstruction(locale: string = 'en'): string {
  return LANGUAGE_INSTRUCTIONS[locale] || LANGUAGE_INSTRUCTIONS['en'];
}

/**
 * Detects if text contains Hindi characters (Devanagari script)
 * @param text - Text to check
 * @returns true if text contains Hindi characters
 */
export function isHindiText(text: string): boolean {
  return DEVANAGARI_REGEX.test(text);
}

/**
 * Translates Hindi text to English using OpenAI
 * @param text - Hindi text to translate
 * @param openaiApiKey - OpenAI API key
 * @returns Translated English text, or original text if translation fails
 */
/**
 * Simple keyword-based fallback translation for common Hindi words
 * This is used when OpenAI translation fails or times out
 */
function fallbackHindiTranslation(text: string): string {
  const hindiToEnglish: Record<string, string> = {
    'राजनीति': 'politics',
    'राजनीतिक': 'politics',
    'भारत': 'india',
    'भारतीय': 'india',
    'चीन': 'china',
    'चीनी': 'china',
    'अमेरिका': 'usa',
    'अमेरिकी': 'usa',
    'अर्थव्यवस्था': 'economy',
    'आर्थिक': 'economy',
    'खेल': 'sports',
    'खेलों': 'sports',
    'तकनीक': 'technology',
    'तकनीकी': 'technology',
    'स्वास्थ्य': 'health',
    'विज्ञान': 'science',
    'शिक्षा': 'education',
    'मनोरंजन': 'entertainment',
    'समाचार': 'news',
    'खबर': 'news',
    'खबरें': 'news',
    'ताज़ा': 'latest',
    'नवीनतम': 'latest',
    'हाल की': 'recent',
    'क्या': 'what',
    'कौन': 'who',
    'कब': 'when',
    'कहाँ': 'where',
    'कैसे': 'how',
    'क्यों': 'why',
  };
  
  let translated = text.toLowerCase();
  for (const [hindi, english] of Object.entries(hindiToEnglish)) {
    const regex = new RegExp(hindi, 'gi');
    translated = translated.replace(regex, english);
  }
  
  // If we replaced some Hindi words, return the mixed translation
  // Otherwise return original to indicate fallback didn't work
  if (translated !== text.toLowerCase()) {
    return translated;
  }
  return text;
}
export async function translateToEnglish(text: string, openaiApiKey: string, retryCount: number = 0): Promise<string> {
  const maxRetries = 2; // Total 3 attempts (initial + 2 retries)
  const baseTimeoutMs = 6000; // Increased to 6 seconds for better reliability
  
  try {
    // Import OpenAI dynamically to avoid circular dependencies
    const OpenAI = (await import('openai')).default;
    const openai = new OpenAI({ apiKey: openaiApiKey });

    // Exponential backoff: 6s, 5s, 4s (slightly reduced on retries to save time)
    const timeoutMs = baseTimeoutMs - (retryCount * 1000);
    const timeoutPromise = new Promise<never>((_, reject) => {
      setTimeout(() => {
        reject(new Error(`Translation timeout after ${timeoutMs}ms`));
      }, timeoutMs);
    });

    // Try with a more explicit prompt to avoid empty responses
    const completionPromise = openai.chat.completions.create({
      model: 'gpt-5-nano',
      messages: [
        {
          role: 'system',
          content: 'Translate Hindi text to English. Always provide the English translation. Only return the translation, nothing else.',
        },
        {
          role: 'user',
          content: text,
        },
      ],
      max_completion_tokens: 800, // Increased further to allow for reasoning tokens (can use up to 500) + actual translation
      temperature: 1, // gpt-5-nano only supports temperature 1
    });

    const completion = await Promise.race([completionPromise, timeoutPromise]);

    const rawContent = (completion as any).choices[0]?.message?.content;
    const translated = rawContent ? rawContent.trim() : null;
    
    // Check if translation is valid: must exist, have content, be different from original, and not contain Hindi
    if (translated && translated.length > 0 && translated !== text && !isHindiText(translated)) {
      return translated;
    } else {
      // Invalid translation - trigger retry if we have attempts left
      if (retryCount < maxRetries) {
        throw new Error('Invalid translation response');
      }
      return text; // Return original if all retries exhausted
    }
  } catch (error: any) {
    const isTimeout = error.message?.includes('timeout') || error.message?.includes('Translation timeout');
    
    // If timeout and we have retries left, retry with exponential backoff
    if (isTimeout && retryCount < maxRetries) {
      const backoffDelay = Math.min(500 * Math.pow(2, retryCount), 2000); // 500ms, 1000ms, max 2000ms
      await new Promise(resolve => setTimeout(resolve, backoffDelay));
      return translateToEnglish(text, openaiApiKey, retryCount + 1);
    }
    
    // If all retries exhausted or non-timeout error, try fallback
    console.error(`[TRANSLATION] Error translating text (attempt ${retryCount + 1}):`, error.message || error);
    
    // Try keyword-based fallback translation
    const fallback = fallbackHindiTranslation(text);
    if (fallback !== text && !isHindiText(fallback)) {
      return fallback;
    }
    
    return text; // Final fallback: return original text
  }
}

/**
 * Detects if the query is asking for "Top Stories" / "for_you" content
 * @param question - User's question/query
 * @returns true if the query is asking for top stories
 */
export function isTopStoriesQuery(question: string): boolean {
  const lowerQuestion = question.toLowerCase().trim();

  const topStoriesPatterns = [
    /\btop\s+stories?\b/i,
    /\bfor\s+you\b/i,
    /\brecommended\s+(?:stories?|news)\b/i,
    /\bcurated\s+(?:stories?|news)\b/i,
    /\bpersonalized\s+(?:stories?|news)\b/i,
    /\bshow\s+me\s+top\s+(?:stories?|news)\b/i,
    /\bwhat.*for.*me\b/i,
  ];

  for (const pattern of topStoriesPatterns) {
    if (pattern.test(lowerQuestion)) {
      return true;
    }
  }

  return false;
}
