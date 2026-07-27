-- Creates the public ThinkO curated collections and stores their advanced
-- AND/OR tag rules in app_config.

WITH admin_user AS (
  SELECT id
  FROM users
  WHERE uid = 'thinkoadminuser'
),
desired_collections(id, title, description) AS (
  VALUES
    ('1dd4f340-743c-44e9-88af-a3e6834941b1'::uuid, 'Indian Markets', 'Curated updates on Indian equities, indices, commodities, IPOs, and market-moving domestic business news.'),
    ('244bc2f3-9779-4008-a764-c76d4ad57a9a'::uuid, 'Global Markets', 'Curated updates on global equities, commodities, central banks, and cross-border market moves.'),
    ('dc113696-4e44-40a5-840e-928c27a3bcd4'::uuid, 'Performance of specific companies', 'Curated company-specific updates on earnings, stock moves, IPOs, guidance, dividends, and corporate developments.'),
    ('6e450fd1-7b33-4553-abd3-80ae325360d9'::uuid, 'Geopolitics', 'Curated geopolitical stories covering diplomacy, conflict, security, sanctions, and global trade tensions.'),
    ('f47add40-f2e8-4763-b601-8f14804ee6a2'::uuid, 'Indian Economy', 'Curated stories on India macroeconomics, RBI policy, inflation, fiscal policy, currency, banking, and growth.'),
    ('21f6013c-8a37-49b1-8a6b-dd0f72733ae2'::uuid, 'Global Economy', 'Curated stories on global macroeconomics, trade, inflation, central banks, tariffs, currencies, and growth.')
)
INSERT INTO collection (id, user_id, title, description, is_thinko, is_public, "createdAt", "updatedAt")
SELECT desired_collections.id, admin_user.id, desired_collections.title, desired_collections.description, true, false, now(), now()
FROM desired_collections
CROSS JOIN admin_user
ON CONFLICT (user_id, title)
DO UPDATE SET
  description = EXCLUDED.description,
  is_thinko = true,
  is_public = false,
  "updatedAt" = now();

WITH collection_tags(collection_title, tag_names) AS (
  VALUES
    ('Indian Markets', ARRAY['markets', 'national_india', 'business', 'national_business', 'bse', 'nse', 'sensex', 'nifty_50', 'stock_performance', 'market_volatility']::text[]),
    ('Global Markets', ARRAY['markets', 'global', 'business', 'global_markets', 'global_business', 'federal_reserve', 'market_volatility', 'stock_performance']::text[]),
    ('Performance of specific companies', ARRAY['business', 'national_india', 'corporate', 'earnings', 'quarterly_results', 'stock_performance', 'ipo', 'q3_results', 'q1_results', 'q2_results', 'q4_results']::text[]),
    ('Geopolitics', ARRAY['geopolitics', 'foreign_affairs', 'war', 'national_diplomacy']::text[]),
    ('Indian Economy', ARRAY['economy', 'national_india', 'macro_economy', 'monetary_policy', 'fiscal_policy', 'inflation', 'rupee_decline', 'rupee_depreciation', 'rupee_record_low', 'rupee_falls', 'indian_rupee']::text[]),
    ('Global Economy', ARRAY['economy', 'global', 'global_trade', 'federal_reserve', 'trade']::text[])
),
matched_tags AS (
  SELECT
    c.id AS collection_id,
    st.id AS seo_tag_id
  FROM collection_tags ct
  JOIN users u ON u.uid = 'thinkoadminuser'
  JOIN collection c ON c.user_id = u.id AND c.title = ct.collection_title
  JOIN seo_tag st ON st.name = ANY(ct.tag_names)
)
INSERT INTO collection_seo_tag (id, collection_id, seo_tag_id, created_date)
SELECT
  (
    substr(md5(collection_id::text || ':' || seo_tag_id::text), 1, 8) || '-' ||
    substr(md5(collection_id::text || ':' || seo_tag_id::text), 9, 4) || '-' ||
    substr(md5(collection_id::text || ':' || seo_tag_id::text), 13, 4) || '-' ||
    substr(md5(collection_id::text || ':' || seo_tag_id::text), 17, 4) || '-' ||
    substr(md5(collection_id::text || ':' || seo_tag_id::text), 21, 12)
  )::uuid,
  collection_id,
  seo_tag_id,
  now()
FROM matched_tags
ON CONFLICT (collection_id, seo_tag_id) DO NOTHING;

INSERT INTO app_config (config_key, config_value, description, updated_at)
VALUES (
  'curated_collection_rules',
  $json$
  {
    "1dd4f340-743c-44e9-88af-a3e6834941b1": {
      "groupOperator": "OR",
      "groups": [
        { "operator": "AND", "tags": ["markets", "national_india"] },
        { "operator": "AND", "tags": ["markets", "national_business"] },
        { "operator": "OR", "tags": ["bse", "nse", "sensex", "nifty_50"] },
        { "operator": "AND", "tags": ["stock_performance", "national_india"] },
        { "operator": "AND", "tags": ["market_volatility", "national_india"] }
      ]
    },
    "Indian Markets": {
      "groupOperator": "OR",
      "groups": [
        { "operator": "AND", "tags": ["markets", "national_india"] },
        { "operator": "AND", "tags": ["markets", "national_business"] },
        { "operator": "OR", "tags": ["bse", "nse", "sensex", "nifty_50"] },
        { "operator": "AND", "tags": ["stock_performance", "national_india"] },
        { "operator": "AND", "tags": ["market_volatility", "national_india"] }
      ]
    },
    "244bc2f3-9779-4008-a764-c76d4ad57a9a": {
      "groupOperator": "OR",
      "groups": [
        { "operator": "AND", "tags": ["markets", "global"] },
        { "operator": "AND", "tags": ["global_markets"] },
        { "operator": "AND", "tags": ["global_business", "markets"] },
        { "operator": "AND", "tags": ["federal_reserve", "global"] },
        { "operator": "AND", "tags": ["market_volatility", "global"] },
        { "operator": "AND", "tags": ["stock_performance", "global"] }
      ]
    },
    "Global Markets": {
      "groupOperator": "OR",
      "groups": [
        { "operator": "AND", "tags": ["markets", "global"] },
        { "operator": "AND", "tags": ["global_markets"] },
        { "operator": "AND", "tags": ["global_business", "markets"] },
        { "operator": "AND", "tags": ["federal_reserve", "global"] },
        { "operator": "AND", "tags": ["market_volatility", "global"] },
        { "operator": "AND", "tags": ["stock_performance", "global"] }
      ]
    },
    "dc113696-4e44-40a5-840e-928c27a3bcd4": {
      "groupOperator": "OR",
      "groups": [
        { "operator": "AND", "tags": ["business", "national_india"] },
        { "operator": "AND", "tags": ["corporate", "national_india"] },
        { "operator": "AND", "tags": ["business", "earnings"] },
        { "operator": "AND", "tags": ["business", "quarterly_results"] },
        { "operator": "OR", "tags": ["stock_performance", "national_india"] },
        { "operator": "AND", "tags": ["ipo", "national_india"] },
        { "operator": "AND", "tags": ["q3_results", "national_india"] },
        { "operator": "AND", "tags": ["q1_results", "national_india"] },
        { "operator": "AND", "tags": ["q2_results", "national_india"] },
        { "operator": "AND", "tags": ["q4_results", "national_india"] }
      ]
    },
    "Performance of specific companies": {
      "groupOperator": "OR",
      "groups": [
        { "operator": "AND", "tags": ["business", "national_india"] },
        { "operator": "AND", "tags": ["corporate", "national_india"] },
        { "operator": "AND", "tags": ["business", "earnings"] },
        { "operator": "AND", "tags": ["business", "quarterly_results"] },
        { "operator": "OR", "tags": ["stock_performance", "national_india"] },
        { "operator": "AND", "tags": ["ipo", "national_india"] },
        { "operator": "AND", "tags": ["q3_results", "national_india"] },
        { "operator": "AND", "tags": ["q1_results", "national_india"] },
        { "operator": "AND", "tags": ["q2_results", "national_india"] },
        { "operator": "AND", "tags": ["q4_results", "national_india"] }
      ]
    },
    "6e450fd1-7b33-4553-abd3-80ae325360d9": {
      "groupOperator": "OR",
      "groups": [
        { "operator": "OR", "tags": ["geopolitics", "foreign_affairs", "war", "national_diplomacy"] }
      ]
    },
    "Geopolitics": {
      "groupOperator": "OR",
      "groups": [
        { "operator": "OR", "tags": ["geopolitics", "foreign_affairs", "war", "national_diplomacy"] }
      ]
    },
    "f47add40-f2e8-4763-b601-8f14804ee6a2": {
      "groupOperator": "OR",
      "groups": [
        { "operator": "AND", "tags": ["economy", "national_india"] },
        { "operator": "AND", "tags": ["national_india", "macro_economy"] },
        { "operator": "AND", "tags": ["national_india", "monetary_policy"] },
        { "operator": "AND", "tags": ["national_india", "fiscal_policy"] },
        { "operator": "AND", "tags": ["national_india", "inflation"] },
        { "operator": "AND", "tags": ["rupee_decline", "national_india"] },
        { "operator": "AND", "tags": ["national_india", "rupee_depreciation"] },
        { "operator": "AND", "tags": ["national_india", "rupee_record_low"] },
        { "operator": "AND", "tags": ["national_india", "rupee_falls"] },
        { "operator": "AND", "tags": ["national_india", "indian_rupee"] }
      ]
    },
    "Indian Economy": {
      "groupOperator": "OR",
      "groups": [
        { "operator": "AND", "tags": ["economy", "national_india"] },
        { "operator": "AND", "tags": ["national_india", "macro_economy"] },
        { "operator": "AND", "tags": ["national_india", "monetary_policy"] },
        { "operator": "AND", "tags": ["national_india", "fiscal_policy"] },
        { "operator": "AND", "tags": ["national_india", "inflation"] },
        { "operator": "AND", "tags": ["rupee_decline", "national_india"] },
        { "operator": "AND", "tags": ["national_india", "rupee_depreciation"] },
        { "operator": "AND", "tags": ["national_india", "rupee_record_low"] },
        { "operator": "AND", "tags": ["national_india", "rupee_falls"] },
        { "operator": "AND", "tags": ["national_india", "indian_rupee"] }
      ]
    },
    "21f6013c-8a37-49b1-8a6b-dd0f72733ae2": {
      "groupOperator": "OR",
      "groups": [
        { "operator": "AND", "tags": ["economy", "global"] },
        { "operator": "AND", "tags": ["global_trade"] },
        { "operator": "AND", "tags": ["federal_reserve", "global"] },
        { "operator": "AND", "tags": ["global", "trade"] }
      ]
    },
    "Global Economy": {
      "groupOperator": "OR",
      "groups": [
        { "operator": "AND", "tags": ["economy", "global"] },
        { "operator": "AND", "tags": ["global_trade"] },
        { "operator": "AND", "tags": ["federal_reserve", "global"] },
        { "operator": "AND", "tags": ["global", "trade"] }
      ]
    }
  }
  $json$::jsonb,
  'Advanced AND/OR tag rules for backend-managed curated collections.',
  now()
)
ON CONFLICT (config_key)
DO UPDATE SET
  config_value = EXCLUDED.config_value,
  description = EXCLUDED.description,
  updated_at = now();
