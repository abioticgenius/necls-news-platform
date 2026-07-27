-- Complete replacement for V1_insert_onboarding_interests_config.sql.
-- Every onboarding interest uses the uniform rule-capable structure. Flat tag collections are represented as OR rules.
INSERT INTO app_config (config_key, config_value, description, updated_at)
SELECT
  'backup_onboarding_interests_before_v10',
  config_value,
  description,
  NOW()
FROM app_config
WHERE config_key = 'onboarding_interests'
ON CONFLICT (config_key)
DO UPDATE SET
  config_value = EXCLUDED.config_value,
  description = EXCLUDED.description,
  updated_at = NOW();

INSERT INTO app_config (config_key, config_value)
VALUES (
  'onboarding_interests',
  '[
  {
    "id": 1,
    "tags": "state,politics",
    "label": "State Politics",
    "collectionName": "State Politics",
    "collectionRule": {
      "groupOperator": "OR",
      "groups": [
        {
          "operator": "AND",
          "tags": [
            "state",
            "politics"
          ]
        }
      ]
    }
  },
  {
    "id": 2,
    "tags": "politics,india",
    "label": "National Politics",
    "collectionName": "National Politics",
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
    "id": 3,
    "tags": "national_judiciary,bombay_high_court,supreme_court_of_india,delhi_high_court,karnataka_high_court,punjab_and_haryana_high_court,calcutta_high_court,kerala_high_court,allahabad_high_court,rajasthan_high_court,madras_high_court,kolkata_high_court,orissa_high_court,gujarat_high_court,patna_high_court,madhya_pradesh_high_court,telangana_high_court,chhattisgarh_high_court,meghalaya_high_court,gauhati_high_court,jammu_and_kashmir_high_court,haryana_high_court,andhra_pradesh_high_court,high_court",
    "label": "Judiciary",
    "collectionName": "Judiciary",
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
    "id": 4,
    "tags": "parliament,india,legislation,national_judiciary",
    "label": "National Law",
    "collectionName": "National Law",
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
          "operator": "OR",
          "tags": [
            "national_judiciary"
          ]
        }
      ]
    }
  },
  {
    "id": 5,
    "tags": "parliament,global,legislation,global_policy,global_judiciary",
    "label": "Global Law",
    "collectionName": "Global Law",
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
          "operator": "OR",
          "tags": [
            "global_policy"
          ]
        },
        {
          "operator": "OR",
          "tags": [
            "global_judiciary"
          ]
        }
      ]
    }
  },
  {
    "id": 6,
    "tags": "geopolitics,national_diplomacy,foreign_affairs",
    "label": "Foreign Affairs",
    "collectionName": "World Affairs",
    "collectionRule": {
      "groupOperator": "OR",
      "groups": [
        {
          "operator": "OR",
          "tags": [
            "geopolitics"
          ]
        },
        {
          "operator": "OR",
          "tags": [
            "national_diplomacy"
          ]
        },
        {
          "operator": "OR",
          "tags": [
            "foreign_affairs"
          ]
        }
      ]
    }
  },
  {
    "id": 7,
    "tags": "geopolitics",
    "label": "Geopolitics",
    "collectionName": "Geopolitics",
    "collectionRule": {
      "groupOperator": "OR",
      "groups": [
        {
          "operator": "OR",
          "tags": [
            "geopolitics"
          ]
        }
      ]
    }
  },
  {
    "id": 8,
    "tags": "markets",
    "label": "Stock Markets",
    "collectionName": "Markets",
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
    "id": 9,
    "tags": "markets,india,national_business,bse,nse,sensex,nifty_50,stock_performance,market_volatility",
    "label": "Indian Markets",
    "collectionName": "Indian Markets",
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
            "markets",
            "national_business"
          ]
        },
        {
          "operator": "OR",
          "tags": [
            "bse"
          ]
        },
        {
          "operator": "OR",
          "tags": [
            "nse"
          ]
        },
        {
          "operator": "OR",
          "tags": [
            "sensex"
          ]
        },
        {
          "operator": "OR",
          "tags": [
            "nifty_50"
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
    "id": 10,
    "tags": "markets,global,global_markets,global_business,federal_reserve,stock_performance,market_volatility",
    "label": "Global Markets",
    "collectionName": "Global Markets",
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
          "operator": "OR",
          "tags": [
            "global_markets"
          ]
        },
        {
          "operator": "AND",
          "tags": [
            "global_business",
            "markets"
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
    "id": 11,
    "tags": "startups,internet_and_platforms,consumer_tech",
    "label": "Startups",
    "collectionName": "Startups",
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
    "id": 12,
    "tags": "business,india,corporate",
    "label": "Business India",
    "collectionName": "Indian Business",
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
    "id": 13,
    "tags": "business,global,corporate",
    "label": "Business World",
    "collectionName": "Global Business",
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
    "id": 14,
    "tags": "economy,india,macro_economy,monetary_policy,fiscal_policy,inflation,rupee_decline,rupee_depreciation,rupee_record_low,rupee_falls,indian_rupee",
    "label": "Economy India",
    "collectionName": "Indian Economy",
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
    "id": 15,
    "tags": "economy,global,global_trade,federal_reserve,trade",
    "label": "Economy World",
    "collectionName": "Global Economy",
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
    "id": 16,
    "tags": "artificial_intelligence",
    "label": "AI",
    "collectionName": "AI",
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
    "id": 17,
    "tags": "technology",
    "label": "Technology",
    "collectionName": "Technology",
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
    "id": 18,
    "tags": "cricket",
    "label": "Cricket",
    "collectionName": "Cricket",
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
    "id": 19,
    "tags": "football",
    "label": "Football",
    "collectionName": "Football",
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
    "id": 20,
    "tags": "sports,india",
    "label": "National Sports",
    "collectionName": "National Sports",
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
    "id": 21,
    "tags": "sports,global",
    "label": "Global Sports",
    "collectionName": "Global Sports",
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
    "id": 22,
    "tags": "health_&_science",
    "label": "Health & Science",
    "collectionName": "Health & Science",
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
    "id": 23,
    "tags": "environment",
    "label": "Environment",
    "collectionName": "Environment",
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
    "id": 24,
    "tags": "education",
    "label": "Education",
    "collectionName": "Education",
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
    "id": 25,
    "tags": "state",
    "label": "State",
    "collectionName": "State",
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
  }
]'::jsonb
)
ON CONFLICT (config_key)
DO UPDATE SET
  config_value = EXCLUDED.config_value,
  updated_at = NOW();
