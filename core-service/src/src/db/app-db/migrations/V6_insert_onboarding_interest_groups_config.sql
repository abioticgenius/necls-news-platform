INSERT INTO app_config (config_key, config_value)
VALUES (
  'onboarding_interest_groups',
  '[
  {
    "group": 1,
    "label": "Politics",
    "interestIds": [1, 2, 3],
    "collectionName": "Politics",
    "collectionTags": "politics",
    "minSelection": 2
  },
  {
    "group": 2,
    "label": "Judiciary",
    "interestIds": [4, 5, 6],
    "collectionName": "Judiciary",
    "collectionTags": "national_judiciary,bombay_high_court,supreme_court_of_india,delhi_high_court,karnataka_high_court,punjab_and_haryana_high_court,calcutta_high_court,kerala_high_court,allahabad_high_court,rajasthan_high_court,madras_high_court,kolkata_high_court,orissa_high_court,gujarat_high_court,patna_high_court,madhya_pradesh_high_court,telangana_high_court,chhattisgarh_high_court,meghalaya_high_court,gauhati_high_court,jammu_kashmir_high_court,haryana_high_court,andhra_pradesh_high_court,high_court",
    "minSelection": 2
  },
  {
    "group": 3,
    "label": "National",
    "interestIds": [7, 8, 9, 10, 11],
    "collectionName": "National",
    "collectionTags": "national_india",
    "minSelection": 3
  },
  {
    "group": 4,
    "label": "World Affairs",
    "interestIds": [12, 13],
    "collectionName": null,
    "collectionTags": null,
    "minSelection": 2
  },
  {
    "group": 5,
    "label": "Global",
    "interestIds": [14, 15, 16, 17],
    "collectionName": "Global",
    "collectionTags": "global",
    "minSelection": 3
  },
  {
    "group": 6,
    "label": "Business",
    "interestIds": [18, 19, 20, 21],
    "collectionName": "Business",
    "collectionTags": "business,corporate",
    "minSelection": 3
  },
  {
    "group": 7,
    "label": "Economy",
    "interestIds": [23, 24, 25],
    "collectionName": "Economy",
    "collectionTags": "economy",
    "minSelection": 2
  },
  {
    "group": 8,
    "label": "Technology",
    "interestIds": [26, 27, 28],
    "collectionName": "Technology",
    "collectionTags": "technology",
    "minSelection": 2
  },
  {
    "group": 9,
    "label": "Sports",
    "interestIds": [29, 30, 31],
    "collectionName": "Sports",
    "collectionTags": "sports",
    "minSelection": 2
  },
  {
    "group": 10,
    "label": "Education & Careers",
    "interestIds": [34, 35, 36],
    "collectionName": "Education",
    "collectionTags": "education",
    "minSelection": 2
  }
  ]'::jsonb
)
ON CONFLICT (config_key)
DO UPDATE SET
  config_value = EXCLUDED.config_value,
  updated_at = NOW(); -- optional if you have this column
