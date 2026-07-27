-- Complete replacement for V2_insert_recommended_interests_mapping.sql.
-- Every recommended mapping uses the uniform rule-capable structure. Flat tag collections are represented as OR rules.
INSERT INTO app_config (config_key, config_value, description, updated_at)
SELECT
  'backup_recommended_interests_mapping_before_v11',
  config_value,
  description,
  NOW()
FROM app_config
WHERE config_key = 'recommended_interests_mapping'
ON CONFLICT (config_key)
DO UPDATE SET
  config_value = EXCLUDED.config_value,
  description = EXCLUDED.description,
  updated_at = NOW();

INSERT INTO app_config (config_key, config_value)
VALUES (
  'recommended_interests_mapping',
  '[
  {
    "group": "1",
    "collectionName": "Politics",
    "tags": "politics",
    "collectionRule": {
      "groupOperator": "OR",
      "groups": [
        {
          "operator": "OR",
          "tags": [
            "politics"
          ]
        }
      ]
    }
  },
  {
    "group": "2",
    "collectionName": "Global",
    "tags": "global",
    "collectionRule": {
      "groupOperator": "OR",
      "groups": [
        {
          "operator": "OR",
          "tags": [
            "global"
          ]
        }
      ]
    }
  },
  {
    "group": "3",
    "collectionName": "Business",
    "tags": "business",
    "collectionRule": {
      "groupOperator": "OR",
      "groups": [
        {
          "operator": "OR",
          "tags": [
            "business"
          ]
        }
      ]
    }
  },
  {
    "group": "4",
    "collectionName": "Economy",
    "tags": "economy",
    "collectionRule": {
      "groupOperator": "OR",
      "groups": [
        {
          "operator": "OR",
          "tags": [
            "economy"
          ]
        }
      ]
    }
  },
  {
    "group": "5",
    "collectionName": "Technology",
    "tags": "technology",
    "collectionRule": {
      "groupOperator": "OR",
      "groups": [
        {
          "operator": "OR",
          "tags": [
            "technology"
          ]
        }
      ]
    }
  },
  {
    "group": "6",
    "collectionName": "Sports",
    "tags": "sports",
    "collectionRule": {
      "groupOperator": "OR",
      "groups": [
        {
          "operator": "OR",
          "tags": [
            "sports"
          ]
        }
      ]
    }
  },
  {
    "group": "7",
    "collectionName": "Health & Science",
    "tags": "health_&_science",
    "collectionRule": {
      "groupOperator": "OR",
      "groups": [
        {
          "operator": "OR",
          "tags": [
            "health_&_science"
          ]
        }
      ]
    }
  },
  {
    "group": "8",
    "collectionName": "Education",
    "tags": "education",
    "collectionRule": {
      "groupOperator": "OR",
      "groups": [
        {
          "operator": "OR",
          "tags": [
            "education"
          ]
        }
      ]
    }
  },
  {
    "group": "9",
    "collectionName": "Environment",
    "tags": "environment",
    "collectionRule": {
      "groupOperator": "OR",
      "groups": [
        {
          "operator": "OR",
          "tags": [
            "environment"
          ]
        }
      ]
    }
  },
  {
    "group": "10",
    "collectionName": "Society",
    "tags": "society",
    "collectionRule": {
      "groupOperator": "OR",
      "groups": [
        {
          "operator": "OR",
          "tags": [
            "society"
          ]
        }
      ]
    }
  },
  {
    "group": "11",
    "collectionName": "National",
    "tags": "india",
    "collectionRule": {
      "groupOperator": "OR",
      "groups": [
        {
          "operator": "OR",
          "tags": [
            "india"
          ]
        }
      ]
    }
  },
  {
    "group": "12",
    "collectionName": "State",
    "tags": "state",
    "collectionRule": {
      "groupOperator": "OR",
      "groups": [
        {
          "operator": "OR",
          "tags": [
            "state"
          ]
        }
      ]
    }
  },
  {
    "group": "101",
    "collectionName": "Politics",
    "tags": "politics",
    "collectionRule": {
      "groupOperator": "OR",
      "groups": [
        {
          "operator": "OR",
          "tags": [
            "politics"
          ]
        }
      ]
    }
  },
  {
    "group": "101",
    "collectionName": "State Politics",
    "tags": "politics,state",
    "collectionRule": {
      "groupOperator": "OR",
      "groups": [
        {
          "operator": "AND",
          "tags": [
            "state", "politics"
          ]
        }
      ]
    }
  },
  {
    "group": "101",
    "collectionName": "National Politics",
    "tags": "india,politics",
    "collectionRule": {
      "groupOperator": "OR",
      "groups": [
        {
          "operator": "AND",
          "tags": [
            "politics",
            "india"
          ]
        }
      ]
    }
  },
  {
    "group": "101",
    "collectionName": "Political Parties",
    "tags": "allegations,coalitions,india,parties",
    "collectionRule": {
      "groupOperator": "OR",
      "groups": [
        {
          "operator": "AND",
          "tags": [
            "coalitions",
            "india"
          ]
        },
        {
          "operator": "AND",
          "tags": [
            "allegations",
            "india"
          ]
        },
        {
          "operator": "AND",
          "tags": [
            "parties",
            "india"
          ]
        }
      ]
    }
  },
  {
    "group": "101",
    "collectionName": "Centre - State",
    "tags": "centre-state",
    "collectionRule": {
      "groupOperator": "OR",
      "groups": [
        {
          "operator": "OR",
          "tags": [
            "centre-state"
          ]
        }
      ]
    }
  },
  {
    "group": "101",
    "collectionName": "Elections",
    "tags": "elections",
    "collectionRule": {
      "groupOperator": "OR",
      "groups": [
        {
          "operator": "OR",
          "tags": [
            "elections"
          ]
        }
      ]
    }
  },
  {
    "group": "101",
    "collectionName": "Diplomacy",
    "tags": "national_diplomacy",
    "collectionRule": {
      "groupOperator": "OR",
      "groups": [
        {
          "operator": "OR",
          "tags": [
            "national_diplomacy"
          ]
        }
      ]
    }
  },
  {
    "group": "102",
    "collectionName": "Global",
    "tags": "global",
    "collectionRule": {
      "groupOperator": "OR",
      "groups": [
        {
          "operator": "OR",
          "tags": [
            "global"
          ]
        }
      ]
    }
  },
  {
    "group": "102",
    "collectionName": "Geopolitics",
    "tags": "geopolitics,foreign_affairs,war,national_diplomacy",
    "collectionRule": {
      "groupOperator": "OR",
      "groups": [
        {
          "operator": "OR",
          "tags": [
            "geopolitics",
            "foreign_affairs",
            "war",
            "national_diplomacy"


          ]
        }
      ]
    }
  },
  {
    "group": "102",
    "collectionName": "Global Law",
    "tags": "parliament,global,legislation,global_policy,global_judiciary",
    "collectionRule": {
      "groupOperator": "OR",
      "groups": [
        {
          "operator": "AND",
          "tags": [
            "parliament",
            "global"
          ]
        },
        {
          "operator": "AND",
          "tags": [
            "legislation",
            "global"
          ]
        },
        {
          "operator": "AND",
          "tags": [
            "global_policy", "global"          ]
        },
        {
          "operator": "AND",
          "tags": [
            "global_judiciary", "global"
          ]
        }
      ]
    }
  },
  {
    "group": "102",
    "collectionName": "Global Politics",
    "tags": "politics,global",
    "collectionRule": {
      "groupOperator": "OR",
      "groups": [
        {
          "operator": "AND",
          "tags": [
            "politics",
            "global"
          ]
        }
      ]
    }
  },
  {
    "group": "102",
    "collectionName": "Global Trade",
    "tags": "global_business,global_trade",
    "collectionRule": {
      "groupOperator": "OR",
      "groups": [
        {
          "operator": "AND",
          "tags": [
            "global","business"
          ]
        },
      "groups": [
        {
          "operator": "AND",
          "tags": [
            "global","trade"
          ]
        },
      ]
    }
  },
  {
    "group": "102",
    "collectionName": "World Affairs",
    "tags": "geopolitics,national_diplomacy,foreign_affairs",
    "collectionRule": {
      "groupOperator": "OR",
      "groups": [
        {
          "operator": "OR",
          "tags": [
            "geopolitics", "national_diplomacy", "foreign_affairs"
          ]
        }
      ]
    }
  },
  {
    "group": "102",
    "collectionName": "Trump",
    "tags": "donald_trump",
    "collectionRule": {
      "groupOperator": "OR",
      "groups": [
        {
          "operator": "OR",
          "tags": [
            "donald_trump"
          ]
        }
      ]
    }
  },
  {
    "group": "102",
    "collectionName": "China",
    "tags": "china",
    "collectionRule": {
      "groupOperator": "OR",
      "groups": [
        {
          "operator": "OR",
          "tags": [
            "china"
          ]
        }
      ]
    }
  },
  {
    "group": "102",
    "collectionName": "Global Conflicts",
    "tags": "global_defence,war,sanctions",
    "collectionRule": {
      "groupOperator": "OR",
      "groups": [
        {
          "operator": "OR",
          "tags": [
            "global_defence",
            "war",
            "sanctions"
          ]
        }
      ]
    }
  },
  {
    "group": "103",
    "collectionName": "Business",
    "tags": "business",
    "collectionRule": {
      "groupOperator": "OR",
      "groups": [
        {
          "operator": "OR",
          "tags": [
            "business"
          ]
        }
      ]
    }
  },
{
    "group": "113",
    "collectionName": "Markets",
    "tags": "markets",
    "collectionRule": {
      "groupOperator": "OR",
      "groups": [
        {
          "operator": "OR",
          "tags": [
            "markets"
          ]
        }
      ]
    }
  },
  
{
    "group": "113",
    "collectionName": "Indian Markets",
    "tags": "markets,india,business,national_business,bse,nse,sensex,nifty_50,stock_performance,market_volatility",
    "collectionRule": {
      "groupOperator": "OR",
      "groups": [
        {
          "operator": "AND",
          "tags": [
            "markets",
            "india"
          ]
        },
        {
          "operator": "AND",
          "tags": [
            "business",
            "india"
          ]
        },
        {
          "operator": "AND",
          "tags": [
            "india",
            "national_business"
          ]
        },
        {
          "operator": "AND",
          "tags": [
            "bse", "india"
          ]
        },
        {
          "operator": "AND",
          "tags": [
            "nse" , "india"
          ]
        },
        {
          "operator": "AND",
          "tags": [
            "sensex", "india"
          ]
        },
        {
          "operator": "AND",
          "tags": [
            "nifty_50", "india"
          ]
        },
        {
          "operator": "AND",
          "tags": [
            "stock_performance",
            "india"
          ]
        },
        {
          "operator": "AND",
          "tags": [
            "market_volatility",
            "india"
          ]
        }
      ]
    }
  },
  {
    "group": "113",
    "collectionName": "Global Markets",
    "tags": "markets,global,business,global_markets,global_business,federal_reserve,stock_performance,market_volatility",
    "collectionRule": {
      "groupOperator": "OR",
      "groups": [
        {
          "operator": "AND",
          "tags": [
            "markets",
            "global"
          ]
        },
        {
          "operator": "AND",
          "tags": [
            "business",
            "global"
          ]
        },
        {
          "operator": "AND",
          "tags": [
            "global_markets", "global"
          ]
        },
        {
          "operator": "AND",
          "tags": [
            "global_business",
            "global"
          ]
        },
        {
          "operator": "AND",
          "tags": [
            "federal_reserve",
            "global"
          ]
        },
        {
          "operator": "AND",
          "tags": [
            "stock_performance",
            "global"
          ]
        },
        {
          "operator": "AND",
          "tags": [
            "market_volatility",
            "global"
          ]
        }
      ]
    }
  },
  {
    "group": "103",
    "collectionName": "Company Performance",
    "tags": "corporate,india,earnings,quarterly_results,stock_performance",
    "collectionRule": {
      "groupOperator": "OR",
      "groups": [
        {
          "operator": "OR",
          "tags": [
            "corporate",
            "india",
            "earnings",
            "quarterly_results",
            "stock_performance"
          ]
        }
      ]
    }
  },
  {
    "group": "103",
    "collectionName": "Business India",
    "tags": "business,corporate,india",
    "collectionRule": {
      "groupOperator": "OR",
      "groups": [
        {
          "operator": "AND",
          "tags": [
            "business",
            "india"
          ]
        },
        {
          "operator": "AND",
          "tags": [
            "corporate",
            "india"
          ]
        }
      ]
    }
  },
  {
    "group": "103",
    "collectionName": "Business World",
    "tags": "business,global,corporate",
    "collectionRule": {
      "groupOperator": "OR",
      "groups": [
        {
          "operator": "AND",
          "tags": [
            "business",
            "global"
          ]
        },
        {
          "operator": "AND",
          "tags": [
            "corporate",
            "global"
          ]
        }
      ]
    }
  },
  {
    "group": "103",
    "collectionName": "Banking India",
    "tags": "banking,india",
    "collectionRule": {
      "groupOperator": "OR",
      "groups": [
        {
          "operator": "AND",
          "tags": [
            "banking",
            "india"
          ]
        }
      ]
    }
  },
  {
    "group": "103",
    "collectionName": "Industry India",
    "tags": "india,industry",
    "collectionRule": {
      "groupOperator": "OR",
      "groups": [
        {
          "operator": "AND",
          "tags": [
            "industry",
            "india"
          ]
        }
      ]
    }
  },
  {
    "group": "103",
    "collectionName": "Industry World",
    "tags": "industry,global",
    "collectionRule": {
      "groupOperator": "OR",
      "groups": [
        {
          "operator": "AND",
          "tags": [
            "industry",
            "global"
          ]
        }
      ]
    }
  },
  {
    "group": "103",
    "collectionName": "Banking World",
    "tags": "banking,global",
    "collectionRule": {
      "groupOperator": "OR",
      "groups": [
        {
          "operator": "AND",
          "tags": [
            "banking",
            "global"
          ]
        }
      ]
    }
  },
  {
    "group": "104",
    "collectionName": "Economy",
    "tags": "economy",
    "collectionRule": {
      "groupOperator": "OR",
      "groups": [
        {
          "operator": "OR",
          "tags": [
            "economy"
          ]
        }
      ]
    }
  },
  {
    "group": "104",
    "collectionName": "Economy India",
    "tags": "economy,india,macro_economy",
    "collectionRule": {
      "groupOperator": "OR",
      "groups": [
        {
          "operator": "AND",
          "tags": [
            "economy",
            "india"
          ]
        },
        {
          "operator": "AND",
          "tags": [
            "india",
            "macro_economy"
          ]
        },
        {
          "operator": "AND",
          "tags": [
            "india",
            "monetary_policy"
          ]
        },
        {
          "operator": "AND",
          "tags": [
            "india",
            "fiscal_policy"
          ]
        },
        {
          "operator": "AND",
          "tags": [
            "india",
            "inflation"
          ]
        },
        {
          "operator": "AND",
          "tags": [
            "india",
            "rupee_decline"
          ]
        },
        {
          "operator": "AND",
          "tags": [
            "india",
            "rupee_depreciation"
          ]
        },
        {
          "operator": "AND",
          "tags": [
            "india",
            "rupee_record_low"
          ]
        },
        {
          "operator": "AND",
          "tags": [
            "india",
            "rupee_falls"
          ]
        },
        {
          "operator": "AND",
          "tags": [
            "india",
            "indian_rupee"
          ]
        }
      ]
    }
  },
  {
    "group": "104",
    "collectionName": "Economy World",
    "tags": "economy,global,global_trade",
    "collectionRule": {
      "groupOperator": "OR",
      "groups": [
        {
          "operator": "AND",
          "tags": [
            "economy",
            "global"
          ]
        },
        {
          "operator": "OR",
          "tags": [
            "global_trade"
          ]
        },
        {
          "operator": "AND",
          "tags": [
            "federal_reserve",
            "global"
          ]
        },
        {
          "operator": "AND",
          "tags": [
            "global",
            "trade"
          ]
        }
      ]
    }
  },
  {
    "group": "104",
    "collectionName": "Economic Policy",
    "tags": "monetary_policy,fiscal_policy",
    "collectionRule": {
      "groupOperator": "OR",
      "groups": [
        {
          "operator": "OR",
          "tags": [
            "monetary_policy"
          ]
        },
        {
          "operator": "OR",
          "tags": [
            "fiscal_policy"
          ]
        }
      ]
    }
  },
  {
    "group": "104",
    "collectionName": "Macro Economy",
    "tags": "macro_economy",
    "collectionRule": {
      "groupOperator": "OR",
      "groups": [
        {
          "operator": "OR",
          "tags": [
            "macro_economy"
          ]
        }
      ]
    }
  },
  {
    "group": "104",
    "collectionName": "Economy Data",
    "tags": "data",
    "collectionRule": {
      "groupOperator": "OR",
      "groups": [
        {
          "operator": "OR",
          "tags": [
            "data"
          ]
        }
      ]
    }
  },
  {
    "group": "105",
    "collectionName": "Technology",
    "tags": "technology",
    "collectionRule": {
      "groupOperator": "OR",
      "groups": [
        {
          "operator": "OR",
          "tags": [
            "technology"
          ]
        }
      ]
    }
  },
  {
    "group": "105",
    "collectionName": "Startups",
    "tags": "startups,internet_and_platforms,consumer_tech",
    "collectionRule": {
      "groupOperator": "OR",
      "groups": [
        {
          "operator": "OR",
          "tags": [
            "startups"
          ]
        },
        {
          "operator": "OR",
          "tags": [
            "internet_and_platforms"
          ]
        },
        {
          "operator": "OR",
          "tags": [
            "consumer_tech"
          ]
        }
      ]
    }
  },
  {
    "group": "105",
    "collectionName": "AI",
    "tags": "artificial_intelligence",
    "collectionRule": {
      "groupOperator": "OR",
      "groups": [
        {
          "operator": "OR",
          "tags": [
            "artificial_intelligence"
          ]
        }
      ]
    }
  },
  {
    "group": "105",
    "collectionName": "Internet",
    "tags": "internet_and_platforms,digital_infrastructure,semiconductors,data_and_privacy,blockchain,space_technology",
    "collectionRule": {
      "groupOperator": "OR",
      "groups": [
        {
          "operator": "OR",
          "tags": [
            "internet_and_platforms"
          ]
        },
        {
          "operator": "OR",
          "tags": [
            "digital_infrastructure"
          ]
        },
        {
          "operator": "OR",
          "tags": [
            "semiconductors"
          ]
        },
        {
          "operator": "OR",
          "tags": [
            "data_and_privacy"
          ]
        },
        {
          "operator": "OR",
          "tags": [
            "blockchain"
          ]
        },
        {
          "operator": "OR",
          "tags": [
            "space_technology"
          ]
        }
      ]
    }
  },
  {
    "group": "105",
    "collectionName": "Tech Policy",
    "tags": "tech_policy,data_and_privacy",
    "collectionRule": {
      "groupOperator": "OR",
      "groups": [
        {
          "operator": "OR",
          "tags": [
            "tech_policy",
            "data_and_privacy"
          ]
        }
      ]
    }
  },
  {
    "group": "106",
    "collectionName": "Sports",
    "tags": "sports",
    "collectionRule": {
      "groupOperator": "OR",
      "groups": [
        {
          "operator": "OR",
          "tags": [
            "sports"
          ]
        }
      ]
    }
  },
  {
    "group": "106",
    "collectionName": "Global Sports",
    "tags": "sports,global",
    "collectionRule": {
      "groupOperator": "OR",
      "groups": [
        {
          "operator": "AND",
          "tags": [
            "sports",
            "global"
          ]
        }
      ]
    }
  },
  {
    "group": "106",
    "collectionName": "Cricket",
    "tags": "cricket",
    "collectionRule": {
      "groupOperator": "OR",
      "groups": [
        {
          "operator": "OR",
          "tags": [
            "cricket"
          ]
        }
      ]
    }
  },
  {
    "group": "106",
    "collectionName": "Football",
    "tags": "football",
    "collectionRule": {
      "groupOperator": "OR",
      "groups": [
        {
          "operator": "OR",
          "tags": [
            "football"
          ]
        }
      ]
    }
  },
  {
    "group": "106",
    "collectionName": "National Sports",
    "tags": "india,sports",
    "collectionRule": {
      "groupOperator": "OR",
      "groups": [
        {
          "operator": "AND",
          "tags": [
            "sports",
            "india"
          ]
        }
      ]
    }
  },
  {
    "group": "107",
    "collectionName": "Health & Science",
    "tags": "health_&_science",
    "collectionRule": {
      "groupOperator": "OR",
      "groups": [
        {
          "operator": "OR",
          "tags": [
            "health_&_science"
          ]
        }
      ]
    }
  },
  {
    "group": "107",
    "collectionName": "Public Health",
    "tags": "public_health",
    "collectionRule": {
      "groupOperator": "OR",
      "groups": [
        {
          "operator": "OR",
          "tags": [
            "public_health"
          ]
        }
      ]
    }
  },
  {
    "group": "107",
    "collectionName": "Diseases",
    "tags": "outbreaks,medicine",
    "collectionRule": {
      "groupOperator": "OR",
      "groups": [
        {
          "operator": "OR",
          "tags": [
            "outbreaks",
            "medicine"
          ]
        }
      ]
    }
  },
  {
    "group": "107",
    "collectionName": "Health Policy",
    "tags": "health_policy",
    "collectionRule": {
      "groupOperator": "OR",
      "groups": [
        {
          "operator": "OR",
          "tags": [
            "health_policy"
          ]
        }
      ]
    }
  },
  {
    "group": "108",
    "collectionName": "Education",
    "tags": "education",
    "collectionRule": {
      "groupOperator": "OR",
      "groups": [
        {
          "operator": "OR",
          "tags": [
            "education"
          ]
        }
      ]
    }
  },
  {
    "group": "108",
    "collectionName": "Higher Education",
    "tags": "higher_education",
    "collectionRule": {
      "groupOperator": "OR",
      "groups": [
        {
          "operator": "OR",
          "tags": [
            "higher_education"
          ]
        }
      ]
    }
  },
  {
    "group": "108",
    "collectionName": "Competition",
    "tags": "entrance_exams,study_abroad",
    "collectionRule": {
      "groupOperator": "OR",
      "groups": [
        {
          "operator": "OR",
          "tags": [
            "entrance_exams",
            "study_abroad"
          ]
        }
      ]
    }
  },
  {
    "group": "108",
    "collectionName": "Jobs",
    "tags": "career,govt_jobs,employment,careers_and_jobs",
    "collectionRule": {
      "groupOperator": "OR",
      "groups": [
        {
          "operator": "OR",
          "tags": [
            "career"
          ]
        },
        {
          "operator": "OR",
          "tags": [
            "govt_jobs"
          ]
        },
        {
          "operator": "OR",
          "tags": [
            "employment"
          ]
        },
        {
          "operator": "OR",
          "tags": [
            "careers_and_jobs"
          ]
        }
      ]
    }
  },
  {
    "group": "108",
    "collectionName": "Govt Jobs",
    "tags": "govt_jobs",
    "collectionRule": {
      "groupOperator": "OR",
      "groups": [
        {
          "operator": "OR",
          "tags": [
            "govt_jobs"
          ]
        }
      ]
    }
  },
  {
    "group": "108",
    "collectionName": "EdTech",
    "tags": "edtech",
    "collectionRule": {
      "groupOperator": "OR",
      "groups": [
        {
          "operator": "OR",
          "tags": [
            "edtech"
          ]
        }
      ]
    }
  },
  {
    "group": "109",
    "collectionName": "Environment",
    "tags": "environment",
    "collectionRule": {
      "groupOperator": "OR",
      "groups": [
        {
          "operator": "OR",
          "tags": [
            "environment"
          ]
        }
      ]
    }
  },
  {
    "group": "109",
    "collectionName": "nature",
    "tags": "nature_and_wildlife,climate_and_weather",
    "collectionRule": {
      "groupOperator": "OR",
      "groups": [
        {
          "operator": "OR",
          "tags": [
            "nature_and_wildlife",
            "climate_and_weather"
          ]
        }
      ]
    }
  },
  {
    "group": "109",
    "collectionName": "pollution and waste",
    "tags": "pollution,waste_and_water",
    "collectionRule": {
      "groupOperator": "OR",
      "groups": [
        {
          "operator": "OR",
          "tags": [
            "pollution",
            "waste_and_water"
          ]
        }
      ]
    }
  },
  {
    "group": "109",
    "collectionName": "Sustainable Energy",
    "tags": "sustainable_energy,environmental_policy",
    "collectionRule": {
      "groupOperator": "OR",
      "groups": [
        {
          "operator": "OR",
          "tags": [
            "sustainable_energy",
            "environmental_policy"
          ]
        }
      ]
    }
  },
  {
    "group": "110",
    "collectionName": "Society",
    "tags": "society",
    "collectionRule": {
      "groupOperator": "OR",
      "groups": [
        {
          "operator": "OR",
          "tags": [
            "society"
          ]
        }
      ]
    }
  },
  {
    "group": "110",
    "collectionName": "Aviation",
    "tags": "national_aviation,civil_aviation",
    "collectionRule": {
      "groupOperator": "OR",
      "groups": [
        {
          "operator": "OR",
          "tags": [
            "national_aviation"
          ]
        },
        {
          "operator": "OR",
          "tags": [
            "civil_aviation"
          ]
        }
      ]
    }
  },
  {
    "group": "110",
    "collectionName": "Public Safety",
    "tags": "public_safety",
    "collectionRule": {
      "groupOperator": "OR",
      "groups": [
        {
          "operator": "OR",
          "tags": [
            "public_safety"
          ]
        }
      ]
    }
  },
  {
    "group": "110",
    "collectionName": "Crime and Justice",
    "tags": "national_crime,national_judiciary,global_crime,global_judiciary,state_crime,state_judiciary",
    "collectionRule": {
      "groupOperator": "OR",
      "groups": [
        {
          "operator": "OR",
          "tags": [
            "national_crime"
          ]
        },
        {
          "operator": "OR",
          "tags": [
            "national_judiciary"
          ]
        },
        {
          "operator": "OR",
          "tags": [
            "global_crime"
          ]
        },
        {
          "operator": "OR",
          "tags": [
            "global_judiciary"
          ]
        },
        {
          "operator": "OR",
          "tags": [
            "state_crime"
          ]
        },
        {
          "operator": "OR",
          "tags": [
            "state_judiciary"
          ]
        }
      ]
    }
  },
  {
    "group": "110",
    "collectionName": "National Crime",
    "tags": "national,crime",
    "collectionRule": {
      "groupOperator": "OR",
      "groups": [
        {
          "operator": "AND",
          "tags": [
            "india" ,"crime"
          ]
        }
      ]
    }
  },
  {
    "group": "110",
    "collectionName": "Human Rights",
    "tags": "civil_society_and_rights,caste_and_religion,labour",
    "collectionRule": {
      "groupOperator": "OR",
      "groups": [
        {
          "operator": "OR",
          "tags": [
            "civil_society_and_rights",
            "caste_and_religion",
            "labour"
          ]
        }
      ]
    }
  },
  {
    "group": "110",
    "collectionName": "Entertainment",
    "tags": "entertainment",
    "collectionRule": {
      "groupOperator": "OR",
      "groups": [
        {
          "operator": "OR",
          "tags": [
            "entertainment"
          ]
        }
      ]
    }
  },
  {
    "group": "111",
    "collectionName": "National",
    "tags": "india",
    "collectionRule": {
      "groupOperator": "OR",
      "groups": [
        {
          "operator": "OR",
          "tags": [
            "india"
          ]
        }
      ]
    }
  },
  {
    "group": "111",
    "collectionName": "Parliament",
    "tags": "parliament",
    "collectionRule": {
      "groupOperator": "OR",
      "groups": [
        {
          "operator": "OR",
          "tags": [
            "parliament"
          ]
        }
      ]
    }
  },
  {
    "group": "111",
    "collectionName": "Supreme Court",
    "tags": "national_judiciary,supreme_court_of_india",
    "collectionRule": {
      "groupOperator": "OR",
      "groups": [
        {
          "operator": "OR",
          "tags": [
            "national_judiciary"
          ]
        },
        {
          "operator": "OR",
          "tags": [
            "supreme_court_of_india"
          ]
        }
      ]
    }
  },
  {
    "group": "111",
    "collectionName": "High Court",
    "tags": "bombay_high_court,delhi_high_court,karnataka_high_court,punjab_and_haryana_high_court,calcutta_high_court,kerala_high_court,allahabad_high_court,rajasthan_high_court,madras_high_court,kolkata_high_court,orissa_high_court,gujarat_high_court,patna_high_court,madhya_pradesh_high_court,telangana_high_court,chhattisgarh_high_court,meghalaya_high_court,gauhati_high_court,jammu_and_kashmir_high_court,haryana_high_court,andhra_pradesh_high_court,high_court",
    "collectionRule": {
      "groupOperator": "OR",
      "groups": [
        {
          "operator": "OR",
          "tags": [
            "bombay_high_court"
          ]
        },
        {
          "operator": "OR",
          "tags": [
            "delhi_high_court"
          ]
        },
        {
          "operator": "OR",
          "tags": [
            "karnataka_high_court"
          ]
        },
        {
          "operator": "OR",
          "tags": [
            "punjab_and_haryana_high_court"
          ]
        },
        {
          "operator": "OR",
          "tags": [
            "calcutta_high_court"
          ]
        },
        {
          "operator": "OR",
          "tags": [
            "kerala_high_court"
          ]
        },
        {
          "operator": "OR",
          "tags": [
            "allahabad_high_court"
          ]
        },
        {
          "operator": "OR",
          "tags": [
            "rajasthan_high_court"
          ]
        },
        {
          "operator": "OR",
          "tags": [
            "madras_high_court"
          ]
        },
        {
          "operator": "OR",
          "tags": [
            "kolkata_high_court"
          ]
        },
        {
          "operator": "OR",
          "tags": [
            "orissa_high_court"
          ]
        },
        {
          "operator": "OR",
          "tags": [
            "gujarat_high_court"
          ]
        },
        {
          "operator": "OR",
          "tags": [
            "patna_high_court"
          ]
        },
        {
          "operator": "OR",
          "tags": [
            "madhya_pradesh_high_court"
          ]
        },
        {
          "operator": "OR",
          "tags": [
            "telangana_high_court"
          ]
        },
        {
          "operator": "OR",
          "tags": [
            "chhattisgarh_high_court"
          ]
        },
        {
          "operator": "OR",
          "tags": [
            "meghalaya_high_court"
          ]
        },
        {
          "operator": "OR",
          "tags": [
            "gauhati_high_court"
          ]
        },
        {
          "operator": "OR",
          "tags": [
            "jammu_and_kashmir_high_court"
          ]
        },
        {
          "operator": "OR",
          "tags": [
            "haryana_high_court"
          ]
        },
        {
          "operator": "OR",
          "tags": [
            "andhra_pradesh_high_court"
          ]
        },
        {
          "operator": "OR",
          "tags": [
            "high_court"
          ]
        }
      ]
    }
  },
  {
    "group": "111",
    "collectionName": "Judiciary",
    "tags": "national_judiciary,bombay_high_court,supreme_court_of_india,delhi_high_court,karnataka_high_court,punjab_and_haryana_high_court,calcutta_high_court,kerala_high_court,allahabad_high_court,rajasthan_high_court,madras_high_court,kolkata_high_court,orissa_high_court,gujarat_high_court,patna_high_court,madhya_pradesh_high_court,telangana_high_court,chhattisgarh_high_court,meghalaya_high_court,gauhati_high_court,jammu_and_kashmir_high_court,haryana_high_court,andhra_pradesh_high_court,high_court",
    "collectionRule": {
      "groupOperator": "OR",
      "groups": [
        {
          "operator": "OR",
          "tags": [
            "national_judiciary"
          ]
        },
        {
          "operator": "OR",
          "tags": [
            "bombay_high_court"
          ]
        },
        {
          "operator": "OR",
          "tags": [
            "supreme_court_of_india"
          ]
        },
        {
          "operator": "OR",
          "tags": [
            "delhi_high_court"
          ]
        },
        {
          "operator": "OR",
          "tags": [
            "karnataka_high_court"
          ]
        },
        {
          "operator": "OR",
          "tags": [
            "punjab_and_haryana_high_court"
          ]
        },
        {
          "operator": "OR",
          "tags": [
            "calcutta_high_court"
          ]
        },
        {
          "operator": "OR",
          "tags": [
            "kerala_high_court"
          ]
        },
        {
          "operator": "OR",
          "tags": [
            "allahabad_high_court"
          ]
        },
        {
          "operator": "OR",
          "tags": [
            "rajasthan_high_court"
          ]
        },
        {
          "operator": "OR",
          "tags": [
            "madras_high_court"
          ]
        },
        {
          "operator": "OR",
          "tags": [
            "kolkata_high_court"
          ]
        },
        {
          "operator": "OR",
          "tags": [
            "orissa_high_court"
          ]
        },
        {
          "operator": "OR",
          "tags": [
            "gujarat_high_court"
          ]
        },
        {
          "operator": "OR",
          "tags": [
            "patna_high_court"
          ]
        },
        {
          "operator": "OR",
          "tags": [
            "madhya_pradesh_high_court"
          ]
        },
        {
          "operator": "OR",
          "tags": [
            "telangana_high_court"
          ]
        },
        {
          "operator": "OR",
          "tags": [
            "chhattisgarh_high_court"
          ]
        },
        {
          "operator": "OR",
          "tags": [
            "meghalaya_high_court"
          ]
        },
        {
          "operator": "OR",
          "tags": [
            "gauhati_high_court"
          ]
        },
        {
          "operator": "OR",
          "tags": [
            "jammu_and_kashmir_high_court"
          ]
        },
        {
          "operator": "OR",
          "tags": [
            "haryana_high_court"
          ]
        },
        {
          "operator": "OR",
          "tags": [
            "andhra_pradesh_high_court"
          ]
        },
        {
          "operator": "OR",
          "tags": [
            "high_court"
          ]
        }
      ]
    }
  },
  {
    "group": "111",
    "collectionName": "National Law",
    "tags": "parliament,legislation,national_policy,national_judiciary",
    "collectionRule": {
      "groupOperator": "OR",
      "groups": [
        {
          "operator": "AND",
          "tags": [
            "parliament",
            "india"
          ]
        },
        {
          "operator": "AND",
          "tags": [
            "legislation",
            "india"
          ]
        },
        {
          "operator": "AND",
          "tags": [
            "national_judiciary", "india"
          ]
        }


      ]
    }
  },
  {
    "group": "111",
    "collectionName": "Govt Schemes",
    "tags": "national_schemes,national_governance",
    "collectionRule": {
      "groupOperator": "OR",
      "groups": [
        {
          "operator": "AND",
          "tags": [
            "national_schemes", "india"
          ]
        },
        {
          "operator": "AND",
          "tags": [
            "national_governance", "india"
          ]
        }
      ]
    }
  },
  {
    "group": "111",
    "collectionName": "National Regulators",
    "tags": "national_regulators,national_governance",
    "collectionRule": {
      "groupOperator": "OR",
      "groups": [
        {
          "operator": "OR",
          "tags": [
            "national_regulators",
            "national_governance"
          ]
        }
      ]
    }
  },
  {
    "group": "111",
    "collectionName": "Defence",
    "tags": "national_defence",
    "collectionRule": {
      "groupOperator": "OR",
      "groups": [
        {
          "operator": "OR",
          "tags": [
            "national_defence"
          ]
        }
      ]
    }
  },
  {
    "group": "111",
    "collectionName": "Policy",
    "tags": "national_policy,state_policy",
    "collectionRule": {
      "groupOperator": "OR",
      "groups": [
        {
          "operator": "OR",
          "tags": [
            "national_policy",
            "state_policy"
          ]
        }
      ]
    }
  },
  {
    "group": "112",
    "collectionName": "State Governance",
    "tags": "state_policy,state_schemes,state_governance",
    "collectionRule": {
      "groupOperator": "OR",
      "groups": [
        {
          "operator": "OR",
          "tags": [
            "state_policy"
          ]
        },
        {
          "operator": "OR",
          "tags": [
            "state_schemes"
          ]
        },
        {
          "operator": "OR",
          "tags": [
            "state_governance"
          ]
        }
      ]
    }
  },
  {
    "group": "112",
    "collectionName": "State Development",
    "tags": "state_economy,state_development",
    "collectionRule": {
      "groupOperator": "OR",
      "groups": [
        {
          "operator": "OR",
          "tags": [
            "state_economy",
            "state_development"
          ]
        }
      ]
    }
  },
  {
    "group": "112",
    "collectionName": "State Crime",
    "tags": "state,crime",
    "collectionRule": {
      "groupOperator": "OR",
      "groups": [
        {
          "operator": "AND",
          "tags": [
            "state","crime"
          ]
        }
      ]
    }
  },
  {
    "group": "112",
    "collectionName": "Regional",
    "tags": "regional,interstate",
    "collectionRule": {
      "groupOperator": "OR",
      "groups": [
        {
          "operator": "OR",
          "tags": [
            "regional",
            "interstate"
          ]
        }
      ]
    }
  }
]'::jsonb
)
ON CONFLICT (config_key)
DO UPDATE SET
  config_value = EXCLUDED.config_value,
  updated_at = NOW();
