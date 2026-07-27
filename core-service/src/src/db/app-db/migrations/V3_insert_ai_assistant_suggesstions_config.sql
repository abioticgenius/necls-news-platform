INSERT INTO app_config (config_key, config_value)
VALUES (
  'assistant_suggestions',
  '[
    { "key": "top_stories", "label": "Top Stories", "value": "Show me the top stories", "chat_text": "Show me the top stories", "width": 100 },
    { "key": "artificial_intelligence", "label": "AI", "value": "artificial_intelligence", "chat_text": "Artificial Intelligence news", "width": 40 },
    { "key": "geopolitics", "label": "Geopolitics", "value": "geopolitics", "chat_text": "Geopolitics news", "width": 100 },
    { "key": "technology", "label": "Technology", "value": "technology", "chat_text": "Technology news", "width": 100 },
    { "key": "trump", "label": "Trump", "value": "trump", "chat_text": "Trump news", "width": 70 }
  ]'::jsonb
)
ON CONFLICT (config_key)
DO UPDATE SET 
  config_value = EXCLUDED.config_value,
  updated_at = NOW();