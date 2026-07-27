-- Complete replacement for V6_insert_onboarding_interest_groups_config.sql.
-- Generated from the Interest Groups sheet in Mapping for onboarding - updated.xlsx.
-- Resolves interest IDs, output tags, and output collectionRule from V10 onboarding_interests.

INSERT INTO app_config (config_key, config_value, description, updated_at)
SELECT
  'backup_onboarding_interest_groups_before_v12',
  config_value,
  description,
  NOW()
FROM app_config
WHERE config_key = 'onboarding_interest_groups'
ON CONFLICT (config_key)
DO UPDATE SET
  config_value = EXCLUDED.config_value,
  description = EXCLUDED.description,
  updated_at = NOW();

WITH src AS (
  SELECT
    elem,
    lower(elem->>'label') AS label_key,
    lower(elem->>'collectionName') AS collection_key
  FROM app_config
  CROSS JOIN LATERAL jsonb_array_elements(config_value) elem
  WHERE config_key = 'onboarding_interests'
),
cfg AS (
  SELECT jsonb_build_array(
    jsonb_strip_nulls(jsonb_build_object(
      'group', 1,
      'label', 'National Politics',
      'interestIds', jsonb_build_array(
        (SELECT (elem->>'id')::int FROM src WHERE label_key = lower('State Politics') OR collection_key = lower('State Politics') LIMIT 1),
        (SELECT (elem->>'id')::int FROM src WHERE label_key = lower('Political Parties') OR collection_key = lower('Political Parties') LIMIT 1)
      ),
      'collectionName', (SELECT elem->>'collectionName' FROM src WHERE label_key = lower('National Politics') OR collection_key = lower('National Politics') LIMIT 1),
      'collectionTags', (SELECT elem->>'tags' FROM src WHERE label_key = lower('National Politics') OR collection_key = lower('National Politics') LIMIT 1),
      'collectionRule', (SELECT elem->'collectionRule' FROM src WHERE label_key = lower('National Politics') OR collection_key = lower('National Politics') LIMIT 1),
      'minSelection', 2
    )),
    jsonb_strip_nulls(jsonb_build_object(
      'group', 2,
      'label', 'Politics',
      'interestIds', jsonb_build_array(
        (SELECT (elem->>'id')::int FROM src WHERE label_key = lower('National Politics') OR collection_key = lower('National Politics') LIMIT 1),
        (SELECT (elem->>'id')::int FROM src WHERE label_key = lower('Global Politics') OR collection_key = lower('Global Politics') LIMIT 1)
      ),
      'collectionName', 'Politics',
      'collectionTags', 'politics',
      'collectionRule', '{"groupOperator":"OR","groups":[{"operator":"OR","tags":["politics"]}]}'::jsonb,
      'minSelection', 2
    )),
    jsonb_strip_nulls(jsonb_build_object(
      'group', 3,
      'label', 'Judiciary',
      'interestIds', jsonb_build_array(
        (SELECT (elem->>'id')::int FROM src WHERE label_key = lower('Supreme Court') OR collection_key = lower('Supreme Court') LIMIT 1),
        (SELECT (elem->>'id')::int FROM src WHERE label_key = lower('High Courts') OR collection_key = lower('High Court') LIMIT 1),
        (SELECT (elem->>'id')::int FROM src WHERE label_key = lower('Judiciary') OR collection_key = lower('Judiciary') LIMIT 1)
      ),
      'collectionName', (SELECT elem->>'collectionName' FROM src WHERE label_key = lower('Judiciary') OR collection_key = lower('Judiciary') LIMIT 1),
      'collectionTags', (SELECT elem->>'tags' FROM src WHERE label_key = lower('Judiciary') OR collection_key = lower('Judiciary') LIMIT 1),
      'collectionRule', (SELECT elem->'collectionRule' FROM src WHERE label_key = lower('Judiciary') OR collection_key = lower('Judiciary') LIMIT 1),
      'minSelection', 2
    )),
    jsonb_strip_nulls(jsonb_build_object(
      'group', 4,
      'label', 'National',
      'interestIds', jsonb_build_array(
        (SELECT (elem->>'id')::int FROM src WHERE label_key = lower('National Law') OR collection_key = lower('National Law') LIMIT 1),
        (SELECT (elem->>'id')::int FROM src WHERE label_key = lower('Aviation') OR collection_key = lower('Aviation') LIMIT 1),
        (SELECT (elem->>'id')::int FROM src WHERE label_key = lower('Regulators') OR collection_key = lower('Regulators') LIMIT 1),
        (SELECT (elem->>'id')::int FROM src WHERE label_key = lower('Govt Schemes') OR collection_key = lower('Govt Schemes') LIMIT 1),
        (SELECT (elem->>'id')::int FROM src WHERE label_key = lower('National') OR collection_key = lower('National') LIMIT 1)
      ),
      'collectionName', (SELECT elem->>'collectionName' FROM src WHERE label_key = lower('National') OR collection_key = lower('National') LIMIT 1),
      'collectionTags', (SELECT elem->>'tags' FROM src WHERE label_key = lower('National') OR collection_key = lower('National') LIMIT 1),
      'collectionRule', (SELECT elem->'collectionRule' FROM src WHERE label_key = lower('National') OR collection_key = lower('National') LIMIT 1),
      'minSelection', 3
    )),
    jsonb_strip_nulls(jsonb_build_object(
      'group', 5,
      'label', 'Global Law',
      'interestIds', jsonb_build_array(
        (SELECT (elem->>'id')::int FROM src WHERE label_key = lower('Global Law') OR collection_key = lower('Global Law') LIMIT 1)
      ),
      'collectionName', (SELECT elem->>'collectionName' FROM src WHERE label_key = lower('Global Law') OR collection_key = lower('Global Law') LIMIT 1),
      'collectionTags', (SELECT elem->>'tags' FROM src WHERE label_key = lower('Global Law') OR collection_key = lower('Global Law') LIMIT 1),
      'collectionRule', (SELECT elem->'collectionRule' FROM src WHERE label_key = lower('Global Law') OR collection_key = lower('Global Law') LIMIT 1),
      'minSelection', 1
    )),
    jsonb_strip_nulls(jsonb_build_object(
      'group', 6,
      'label', 'Group 6',
      'interestIds', jsonb_build_array(
        (SELECT (elem->>'id')::int FROM src WHERE label_key = lower('World Affairs') OR collection_key = lower('World Affairs') LIMIT 1),
        (SELECT (elem->>'id')::int FROM src WHERE label_key = lower('Geopolitics') OR collection_key = lower('Geopolitics') LIMIT 1)
      ),
      'collectionName', NULL,
      'collectionTags', NULL,
      'minSelection', 2
    )),
    jsonb_strip_nulls(jsonb_build_object(
      'group', 7,
      'label', 'Global',
      'interestIds', jsonb_build_array(
        (SELECT (elem->>'id')::int FROM src WHERE label_key = lower('Trump') OR collection_key = lower('Trump') LIMIT 1),
        (SELECT (elem->>'id')::int FROM src WHERE label_key = lower('China') OR collection_key = lower('China') LIMIT 1),
        (SELECT (elem->>'id')::int FROM src WHERE label_key = lower('Israel') OR collection_key = lower('Israel') LIMIT 1),
        (SELECT (elem->>'id')::int FROM src WHERE label_key = lower('Global') OR collection_key = lower('Global') LIMIT 1)
      ),
      'collectionName', (SELECT elem->>'collectionName' FROM src WHERE label_key = lower('Global') OR collection_key = lower('Global') LIMIT 1),
      'collectionTags', (SELECT elem->>'tags' FROM src WHERE label_key = lower('Global') OR collection_key = lower('Global') LIMIT 1),
      'collectionRule', (SELECT elem->'collectionRule' FROM src WHERE label_key = lower('Global') OR collection_key = lower('Global') LIMIT 1),
      'minSelection', 3
    )),
    jsonb_strip_nulls(jsonb_build_object(
      'group', 8,
      'label', 'Indian Business',
      'interestIds', jsonb_build_array(
        (SELECT (elem->>'id')::int FROM src WHERE label_key = lower('Indian Markets') OR collection_key = lower('Indian Markets') LIMIT 1),
        (SELECT (elem->>'id')::int FROM src WHERE label_key = lower('Industry India') OR collection_key = lower('Indian Industry') LIMIT 1),
        (SELECT (elem->>'id')::int FROM src WHERE label_key = lower('Banking India') OR collection_key = lower('Indian Banking') LIMIT 1),
        (SELECT (elem->>'id')::int FROM src WHERE label_key = lower('Business India') OR collection_key = lower('Indian Business') LIMIT 1)
      ),
      'collectionName', (SELECT elem->>'collectionName' FROM src WHERE label_key = lower('Business India') OR collection_key = lower('Indian Business') LIMIT 1),
      'collectionTags', (SELECT elem->>'tags' FROM src WHERE label_key = lower('Business India') OR collection_key = lower('Indian Business') LIMIT 1),
      'collectionRule', (SELECT elem->'collectionRule' FROM src WHERE label_key = lower('Business India') OR collection_key = lower('Indian Business') LIMIT 1),
      'minSelection', 3
    )),
    jsonb_strip_nulls(jsonb_build_object(
      'group', 9,
      'label', 'Global Business',
      'interestIds', jsonb_build_array(
        (SELECT (elem->>'id')::int FROM src WHERE label_key = lower('Global Markets') OR collection_key = lower('Global Markets') LIMIT 1),
        (SELECT (elem->>'id')::int FROM src WHERE label_key = lower('Industry World') OR collection_key = lower('Global Industry') LIMIT 1),
        (SELECT (elem->>'id')::int FROM src WHERE label_key = lower('Banking World') OR collection_key = lower('Global Banking') LIMIT 1),
        (SELECT (elem->>'id')::int FROM src WHERE label_key = lower('Business World') OR collection_key = lower('Global Business') LIMIT 1)
      ),
      'collectionName', (SELECT elem->>'collectionName' FROM src WHERE label_key = lower('Business World') OR collection_key = lower('Global Business') LIMIT 1),
      'collectionTags', (SELECT elem->>'tags' FROM src WHERE label_key = lower('Business World') OR collection_key = lower('Global Business') LIMIT 1),
      'collectionRule', (SELECT elem->'collectionRule' FROM src WHERE label_key = lower('Business World') OR collection_key = lower('Global Business') LIMIT 1),
      'minSelection', 3
    )),
    jsonb_strip_nulls(jsonb_build_object(
      'group', 10,
      'label', 'Indian Economy',
      'interestIds', jsonb_build_array(
        (SELECT (elem->>'id')::int FROM src WHERE label_key = lower('Economic Policy') OR collection_key = lower('Economic Policy') LIMIT 1),
        (SELECT (elem->>'id')::int FROM src WHERE label_key = lower('Economy Data') OR collection_key = lower('Economy Data') LIMIT 1)
      ),
      'collectionName', (SELECT elem->>'collectionName' FROM src WHERE label_key = lower('Economy India') OR collection_key = lower('Indian Economy') LIMIT 1),
      'collectionTags', (SELECT elem->>'tags' FROM src WHERE label_key = lower('Economy India') OR collection_key = lower('Indian Economy') LIMIT 1),
      'collectionRule', (SELECT elem->'collectionRule' FROM src WHERE label_key = lower('Economy India') OR collection_key = lower('Indian Economy') LIMIT 1),
      'minSelection', 2
    )),
    jsonb_strip_nulls(jsonb_build_object(
      'group', 11,
      'label', 'Economy',
      'interestIds', jsonb_build_array(
        (SELECT (elem->>'id')::int FROM src WHERE label_key = lower('Economy India') OR collection_key = lower('Indian Economy') LIMIT 1),
        (SELECT (elem->>'id')::int FROM src WHERE label_key = lower('Economy World') OR collection_key = lower('Global Economy') LIMIT 1)
      ),
      'collectionName', 'Economy',
      'collectionTags', 'economy',
      'collectionRule', '{"groupOperator":"OR","groups":[{"operator":"OR","tags":["economy"]}]}'::jsonb,
      'minSelection', 2
    )),
    jsonb_strip_nulls(jsonb_build_object(
      'group', 12,
      'label', 'Technology',
      'interestIds', jsonb_build_array(
        (SELECT (elem->>'id')::int FROM src WHERE label_key = lower('AI') OR collection_key = lower('AI') LIMIT 1),
        (SELECT (elem->>'id')::int FROM src WHERE label_key = lower('Internet') OR collection_key = lower('Internet') LIMIT 1),
        (SELECT (elem->>'id')::int FROM src WHERE label_key = lower('Technology') OR collection_key = lower('Technology') LIMIT 1)
      ),
      'collectionName', (SELECT elem->>'collectionName' FROM src WHERE label_key = lower('Technology') OR collection_key = lower('Technology') LIMIT 1),
      'collectionTags', (SELECT elem->>'tags' FROM src WHERE label_key = lower('Technology') OR collection_key = lower('Technology') LIMIT 1),
      'collectionRule', (SELECT elem->'collectionRule' FROM src WHERE label_key = lower('Technology') OR collection_key = lower('Technology') LIMIT 1),
      'minSelection', 2
    )),
    jsonb_strip_nulls(jsonb_build_object(
      'group', 13,
      'label', 'Sports',
      'interestIds', jsonb_build_array(
        (SELECT (elem->>'id')::int FROM src WHERE label_key = lower('Cricket') OR collection_key = lower('Cricket') LIMIT 1),
        (SELECT (elem->>'id')::int FROM src WHERE label_key = lower('Football') OR collection_key = lower('Football') LIMIT 1)
      ),
      'collectionName', 'Sports',
      'collectionTags', 'sports',
      'collectionRule', '{"groupOperator":"OR","groups":[{"operator":"OR","tags":["sports"]}]}'::jsonb,
      'minSelection', 2
    )),
    jsonb_strip_nulls(jsonb_build_object(
      'group', 14,
      'label', 'Sports',
      'interestIds', jsonb_build_array(
        (SELECT (elem->>'id')::int FROM src WHERE label_key = lower('National Sports') OR collection_key = lower('National Sports') LIMIT 1),
        (SELECT (elem->>'id')::int FROM src WHERE label_key = lower('Global Sports') OR collection_key = lower('Global Sports') LIMIT 1)
      ),
      'collectionName', 'Sports',
      'collectionTags', 'sports',
      'collectionRule', '{"groupOperator":"OR","groups":[{"operator":"OR","tags":["sports"]}]}'::jsonb,
      'minSelection', 2
    )),
    jsonb_strip_nulls(jsonb_build_object(
      'group', 15,
      'label', 'Education',
      'interestIds', jsonb_build_array(
        (SELECT (elem->>'id')::int FROM src WHERE label_key = lower('Jobs') OR collection_key = lower('Jobs') LIMIT 1),
        (SELECT (elem->>'id')::int FROM src WHERE label_key = lower('UPSC') OR collection_key = lower('Govt Jobs') LIMIT 1),
        (SELECT (elem->>'id')::int FROM src WHERE label_key = lower('Education') OR collection_key = lower('Education') LIMIT 1)
      ),
      'collectionName', (SELECT elem->>'collectionName' FROM src WHERE label_key = lower('Education') OR collection_key = lower('Education') LIMIT 1),
      'collectionTags', (SELECT elem->>'tags' FROM src WHERE label_key = lower('Education') OR collection_key = lower('Education') LIMIT 1),
      'collectionRule', (SELECT elem->'collectionRule' FROM src WHERE label_key = lower('Education') OR collection_key = lower('Education') LIMIT 1),
      'minSelection', 2
    ))
  ) AS config_value
)
INSERT INTO app_config (config_key, config_value)
SELECT 'onboarding_interest_groups', config_value
FROM cfg
ON CONFLICT (config_key)
DO UPDATE SET
  config_value = EXCLUDED.config_value,
  updated_at = NOW();
