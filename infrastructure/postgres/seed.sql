-- ThinkO News Platform - Seed Data for Demo
-- This file inserts sample data for testing and demonstration

\c app_db;

-- Sample Users
INSERT INTO users (id, uid, email, name, picture, interests, activity_dates, milestones, earned_badges, "createdAt", "updatedAt")
VALUES
  (
    'user-001'::uuid,
    'firebase_uid_001',
    'demo@example.com',
    'Demo User',
    'https://example.com/avatar.jpg',
    '{"ai","technology","finance"}',
    '{2024-01-20,2024-01-21,2024-01-22,2024-01-23,2024-01-24}',
    '{"streak": {"current": 5, "rest_days_used_this_week": 0, "last_activity_date": "2024-01-24"}, "articles_read": {"total": 42}, "shares_made": {"total": 3}, "assistant_queries": {"total": 12}}',
    '{1,2,8}',
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP
  );

-- Sample Categories
INSERT INTO categories (id, name, "createdAt", "updatedAt")
VALUES
  (gen_random_uuid(), 'Technology', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
  (gen_random_uuid(), 'Finance', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
  (gen_random_uuid(), 'Sports', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
  (gen_random_uuid(), 'Politics', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
  (gen_random_uuid(), 'Science', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP);

-- Sample Languages
INSERT INTO languages (id, name, code, "createdAt", "updatedAt")
VALUES
  ('en'::text, 'English', 'en', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
  ('hi'::text, 'Hindi', 'hi', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP);

-- Sample SEO Tags
WITH tag_ids AS (
  SELECT gen_random_uuid() as ai_tag,
         gen_random_uuid() as ml_tag,
         gen_random_uuid() as finance_tag
)
INSERT INTO seo_tags (id, name, type, embedding, vector_updated_at, "createdAt", "updatedAt")
SELECT
  ai_tag,
  'Artificial Intelligence',
  'tag',
  '[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 0.11, 0.12, 0.13, 0.14, 0.15, 0.16, 0.17, 0.18, 0.19, 0.20]'::vector(384),
  CURRENT_TIMESTAMP,
  CURRENT_TIMESTAMP,
  CURRENT_TIMESTAMP
FROM tag_ids
UNION ALL
SELECT
  ml_tag,
  'Machine Learning',
  'tag',
  '[0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.1, 0.21, 0.22, 0.23, 0.24, 0.25, 0.26, 0.27, 0.28, 0.29, 0.30]'::vector(384),
  CURRENT_TIMESTAMP,
  CURRENT_TIMESTAMP,
  CURRENT_TIMESTAMP
FROM tag_ids
UNION ALL
SELECT
  finance_tag,
  'Finance',
  'Category',
  '[0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.1, 1.2, 0.31, 0.32, 0.33, 0.34, 0.35, 0.36, 0.37, 0.38, 0.39, 0.40]'::vector(384),
  CURRENT_TIMESTAMP,
  CURRENT_TIMESTAMP,
  CURRENT_TIMESTAMP
FROM tag_ids;

-- Sample Events (News Articles)
WITH event_ids AS (
  SELECT gen_random_uuid() as event1,
         gen_random_uuid() as event2,
         gen_random_uuid() as event3
),
tag_ids AS (
  SELECT id as ai_tag FROM seo_tags WHERE name = 'Artificial Intelligence' LIMIT 1
)
INSERT INTO events (id, title, description, time_stamp, image, image_source_url, article_type, "createdAt")
SELECT
  event1,
  'OpenAI Releases GPT-5: A New Era of AI',
  'OpenAI has unveiled its latest language model, GPT-5, which demonstrates significant improvements in reasoning and multi-modal capabilities. The model is now available through the API.',
  CURRENT_TIMESTAMP - interval '5 days',
  'https://example.com/images/gpt5-announcement.jpg',
  'https://example.com/images/gpt5-announcement.jpg',
  'News',
  CURRENT_TIMESTAMP
FROM event_ids
UNION ALL
SELECT
  event2,
  'Stock Market Surges on AI Boom',
  'Technology stocks have surged following the announcement of next-generation AI models, with major tech companies seeing significant gains.',
  CURRENT_TIMESTAMP - interval '3 days',
  'https://example.com/images/stock-market.jpg',
  'https://example.com/images/stock-market.jpg',
  'News',
  CURRENT_TIMESTAMP
FROM event_ids
UNION ALL
SELECT
  event3,
  'Companies Embrace AI for Business Automation',
  'A new report shows that 78% of enterprises plan to increase their AI investments in 2024, focusing on automation and efficiency gains.',
  CURRENT_TIMESTAMP - interval '1 day',
  'https://example.com/images/enterprise-ai.jpg',
  'https://example.com/images/enterprise-ai.jpg',
  'News',
  CURRENT_TIMESTAMP
FROM event_ids;

-- Sample Localized Event Data (English)
WITH event_ids AS (
  SELECT id FROM events ORDER BY time_stamp DESC LIMIT 3
)
INSERT INTO localized_event_data (id, event_id, language_id, title, description, content)
SELECT
  gen_random_uuid(),
  event_ids.id,
  'en',
  events.title,
  events.description,
  'This is the full content of the article in English. It provides comprehensive information about the topic, including context, analysis, and implications. ' ||
  'The AI revolution continues to impact various sectors of the economy and society. ' ||
  'Organizations must prepare for rapid technological change and workforce adaptation.'
FROM event_ids
JOIN events ON events.id = event_ids.id;

-- Sample Collections
WITH user_id AS (
  SELECT id FROM users LIMIT 1
)
INSERT INTO collections (id, user_id, title, description, is_thinko, is_public, "createdAt", "updatedAt")
SELECT
  gen_random_uuid(),
  user_id.id,
  'AI in Enterprise',
  'Articles about AI adoption in business and enterprise environments',
  false,
  true,
  CURRENT_TIMESTAMP,
  CURRENT_TIMESTAMP
FROM user_id;

-- Sample Bookmarks
WITH user_id AS (
  SELECT id FROM users LIMIT 1
),
event_id AS (
  SELECT id FROM events ORDER BY time_stamp DESC LIMIT 1
)
INSERT INTO bookmarks (id, user_id, event_id, "createdAt")
SELECT
  gen_random_uuid(),
  user_id.id,
  event_id.id,
  CURRENT_TIMESTAMP
FROM user_id, event_id;

-- Sample Event Analysis
WITH event_id AS (
  SELECT id FROM events ORDER BY time_stamp DESC LIMIT 1
)
INSERT INTO event_analyses (id, event_id, type, content, sequence, "createdAt")
SELECT
  gen_random_uuid(),
  event_id.id,
  'text',
  'The release of GPT-5 marks a significant milestone in AI development. This new model demonstrates improved reasoning capabilities, particularly in complex problem-solving scenarios. The implications span across multiple sectors including healthcare, finance, and education.',
  1,
  CURRENT_TIMESTAMP
FROM event_id;

-- Sample Event FAQ
WITH event_id AS (
  SELECT id FROM events ORDER BY time_stamp DESC LIMIT 1
)
INSERT INTO event_faqs (id, event_id, language_id, question, answer, sequence, "createdAt")
SELECT
  gen_random_uuid(),
  event_id.id,
  'en',
  'What is GPT-5 and how is it different from GPT-4?',
  'GPT-5 is the latest iteration of OpenAI\'s language model. It features improved reasoning, better understanding of context, and enhanced multi-modal capabilities compared to GPT-4. The model is faster and more efficient.',
  1,
  CURRENT_TIMESTAMP
FROM event_id
UNION ALL
SELECT
  gen_random_uuid(),
  event_id.id,
  'en',
  'When will GPT-5 be available to the public?',
  'GPT-5 is currently available through the OpenAI API for developers and organizations. A consumer-facing version through ChatGPT Plus is expected to be rolled out gradually over the coming weeks.',
  2,
  CURRENT_TIMESTAMP
FROM event_id;

-- Sample Sources (Cited Articles)
WITH event_id AS (
  SELECT id FROM events ORDER BY time_stamp DESC LIMIT 1
)
INSERT INTO sources (id, event_id, source_url, title, article_date, "createdAt")
SELECT
  gen_random_uuid(),
  event_id.id,
  'https://openai.com/blog/gpt5-announcement',
  'OpenAI Announces GPT-5 Release',
  CURRENT_TIMESTAMP - interval '5 days',
  CURRENT_TIMESTAMP
FROM event_id
UNION ALL
SELECT
  gen_random_uuid(),
  event_id.id,
  'https://techcrunch.com/ai-stories',
  'TechCrunch: AI Breakthroughs',
  CURRENT_TIMESTAMP - interval '5 days',
  CURRENT_TIMESTAMP
FROM event_id;

-- Sample Event-Tag Relationships
WITH event_id AS (
  SELECT id FROM events ORDER BY time_stamp DESC LIMIT 1
),
tag_id AS (
  SELECT id FROM seo_tags WHERE name = 'Artificial Intelligence' LIMIT 1
)
INSERT INTO event_seo_tags (id, event_id, seo_tag_id, weight, "createdAt")
SELECT
  gen_random_uuid(),
  event_id.id,
  tag_id.id,
  100,
  CURRENT_TIMESTAMP
FROM event_id, tag_id;

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_events_time_stamp ON events(time_stamp DESC);
CREATE INDEX IF NOT EXISTS idx_localized_event_data_event_id ON localized_event_data(event_id);
CREATE INDEX IF NOT EXISTS idx_event_seo_tags_event_id ON event_seo_tags(event_id);
CREATE INDEX IF NOT EXISTS idx_user_devices_is_active ON user_devices(is_active);
CREATE INDEX IF NOT EXISTS idx_bookmarks_user_id ON bookmarks(user_id);

-- Note: Additional indexes for pgvector searches should be created after data is loaded:
-- CREATE INDEX ON assistant_chunks USING ivfflat (embedding vector_cosine_ops);
