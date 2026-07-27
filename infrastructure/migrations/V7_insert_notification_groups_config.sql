INSERT INTO app_config (config_key, config_value)
VALUES ('notification_groups', '[]'::jsonb)
ON CONFLICT (config_key)
DO UPDATE SET
  config_value = EXCLUDED.config_value,
  updated_at = NOW();
