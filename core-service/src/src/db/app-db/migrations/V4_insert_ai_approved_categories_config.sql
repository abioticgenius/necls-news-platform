INSERT INTO app_config (config_key, config_value)
VALUES (
  'approved_categories',
  '[
    "Politics",
    "Business",
    "Economy",
    "Technology",
    "Sports",
    "Health & Science",
    "Education",
    "Environment",
    "Society",
    "Entertainment",
    "Lifestyle",
    "Explainers & Features",
    "National India",
    "Global",
    "State",
    "Regional"
  ]'::jsonb
)
ON CONFLICT (config_key)
DO UPDATE SET
  config_value = EXCLUDED.config_value,
  updated_at   = NOW();