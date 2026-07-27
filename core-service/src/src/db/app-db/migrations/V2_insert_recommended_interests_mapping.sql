INSERT INTO app_config (config_key, config_value)
VALUES (
  'recommended_interests_mapping',
  '[
  { "group": "1", "collectionName": "Politics", "tags": "politics" },
  { "group": "2", "collectionName": "Global", "tags": "global" },
  { "group": "3", "collectionName": "Business", "tags": "business" },
  { "group": "4", "collectionName": "Economy", "tags": "economy" },
  { "group": "5", "collectionName": "Technology", "tags": "technology" },
  { "group": "6", "collectionName": "Sports", "tags": "sports" },
  { "group": "7", "collectionName": "Health & Science", "tags": "health_&_science" },
  { "group": "8", "collectionName": "Education", "tags": "education" },
  { "group": "9", "collectionName": "Environment", "tags": "environment" },
  { "group": "10", "collectionName": "Society", "tags": "society" },
  { "group": "11", "collectionName": "National", "tags": "national_india" },
  { "group": "12", "collectionName": "State", "tags": "state" },

  { "group": "101", "collectionName": "Politics", "tags": "politics" },
  { "group": "101", "collectionName": "State Politics", "tags": "state_politics" },
  { "group": "101", "collectionName": "Legislation", "tags": "parliament,legislation,national_policy,national_judiciary" },
  { "group": "101", "collectionName": "Political Parties", "tags": "parties,coalitions,allegations" },
  { "group": "101", "collectionName": "Centre - State", "tags": "centre-state" },
  { "group": "101", "collectionName": "Elections", "tags": "elections" },
  { "group": "101", "collectionName": "Diplomacy", "tags": "national_diplomacy" },
  { "group": "101", "collectionName": "Judiciary", "tags": "national_judiciary,bombay_high_court,supreme_court_of_india,delhi_high_court,karnataka_high_court,punjab_and_haryana_high_court,calcutta_high_court,kerala_high_court,allahabad_high_court,rajasthan_high_court,madras_high_court,kolkata_high_court,orissa_high_court,gujarat_high_court,patna_high_court,madhya_pradesh_high_court,telangana_high_court,chhattisgarh_high_court,meghalaya_high_court,gauhati_high_court,jammu_kashmir_high_court,haryana_high_court,andhra_pradesh_high_court,high_court" },

  { "group": "102", "collectionName": "Global", "tags": "global" },
  { "group": "102", "collectionName": "Geopolitics", "tags": "geopolitics" },
  { "group": "102", "collectionName": "Global Markets", "tags": "global_markets,global_economy" },
  { "group": "102", "collectionName": "Global Trade", "tags": "global_business,global_trade" },
  { "group": "102", "collectionName": "World Affairs", "tags": "geopolitics,national_diplomacy,foreign_affairs" },
  { "group": "102", "collectionName": "Trump", "tags": "donald_trump" },
  { "group": "102", "collectionName": "Global Conflicts", "tags": "global_defence,war,sanctions" },

  { "group": "103", "collectionName": "Business", "tags": "business" },
  { "group": "103", "collectionName": "Markets", "tags": "markets" },
  { "group": "103", "collectionName": "Banking & Finance", "tags": "banking,finance" },
  { "group": "103", "collectionName": "Industry", "tags": "industry,corporate" },
  { "group": "103", "collectionName": "Startups", "tags": "startups,internet_and_platforms,consumer_tech" },

  { "group": "104", "collectionName": "Economy", "tags": "economy" },
  { "group": "104", "collectionName": "Economic Policy", "tags": "monetary_policy,fiscal_policy" },
  { "group": "104", "collectionName": "Macro Economy", "tags": "macro_economy" },
  { "group": "104", "collectionName": "Economy Data", "tags": "data" },

  { "group": "105", "collectionName": "Technology", "tags": "technology" },
  { "group": "105", "collectionName": "AI", "tags": "artificial_intelligence" },
  { "group": "105", "collectionName": "Internet", "tags": "internet_and_platforms,digital_infrastructure,semiconductors,data_and_privacy,blockchain,space_technology" },
  { "group": "105", "collectionName": "Tech Policy", "tags": "tech_policy,data_and_privacy" },

  { "group": "106", "collectionName": "Sports", "tags": "sports" },
  { "group": "106", "collectionName": "Cricket", "tags": "cricket" },
  { "group": "106", "collectionName": "Football", "tags": "football" },
  { "group": "106", "collectionName": "National Sports", "tags": "national_sports" },

  { "group": "107", "collectionName": "Health & Science", "tags": "health_&_science" },
  { "group": "107", "collectionName": "Public Health", "tags": "public_health" },
  { "group": "107", "collectionName": "Diseases", "tags": "outbreaks,medicine" },
  { "group": "107", "collectionName": "Health Policy", "tags": "health_policy" },

  { "group": "108", "collectionName": "Education", "tags": "education" },
  { "group": "108", "collectionName": "Higher Education", "tags": "higher_education" },
  { "group": "108", "collectionName": "Competition", "tags": "entrance_exams,study_abroad" },
  { "group": "108", "collectionName": "Jobs", "tags": "career,govt_jobs,employment,careers_and_jobs" },
  { "group": "108", "collectionName": "Govt Jobs", "tags": "govt_jobs" },
  { "group": "108", "collectionName": "EdTech", "tags": "edtech" },

  { "group": "109", "collectionName": "Environment", "tags": "environment" },
  { "group": "109", "collectionName": "nature", "tags": "nature_and_wildlife,climate_and_weather" },
  { "group": "109", "collectionName": "pollution and waste", "tags": "pollution,waste_and_water" },
  { "group": "109", "collectionName": "Sustainable Energy", "tags": "sustainable_energy,environment_policy" },

  { "group": "110", "collectionName": "Society", "tags": "society" },
  { "group": "110", "collectionName": "Public Safety", "tags": "public_safety" },
  { "group": "110", "collectionName": "Crime and Justice", "tags": "national_crime,national_judiciary,global_crime,global_judiciary,state_crime,state_judiciary" },
  { "group": "110", "collectionName": "National Crime", "tags": "national_crime" },
  { "group": "110", "collectionName": "Human Rights", "tags": "civil_society_and_rights,caste_and_religion,labour" },
  { "group": "110", "collectionName": "Entertainment", "tags": "entertainment" },

  { "group": "111", "collectionName": "National", "tags": "national_india" },
  { "group": "111", "collectionName": "Parliament", "tags": "parliament" },
  { "group": "111", "collectionName": "National Regulators", "tags": "national_regulators,national_governance" },
  { "group": "111", "collectionName": "Defence", "tags": "national_defence" },
  { "group": "111", "collectionName": "National Judiciary", "tags": "national_judiciary" },
  { "group": "111", "collectionName": "Policy", "tags": "national_policy,state_policy" },

  { "group": "112", "collectionName": "State", "tags": "state" },
  { "group": "112", "collectionName": "State Governance", "tags": "state_policy,state_schemes,state_governance" },
  { "group": "112", "collectionName": "State Development", "tags": "state_economy,state_development" },
  { "group": "112", "collectionName": "state_schemes", "tags": "state_schemes,state_policy" },
  { "group": "112", "collectionName": "State Crime", "tags": "state_crime" },
  { "group": "112", "collectionName": "Regional", "tags": "regional,interstate" }
]'::jsonb
)
ON CONFLICT (config_key)
DO UPDATE SET 
  config_value = EXCLUDED.config_value,
  updated_at = NOW(); -- optional if you have this column