INSERT INTO app_config (config_key, config_value)
VALUES (
  'onboarding_interests',
  '[
  {"id":1,"tags":"state_politics","label":"State Politics","collectionName":"State Politics"},
  {"id":2,"tags":"parties,coalitions,allegations","label":"Political Parties","collectionName":"Political Parties"},
  {"id":3,"tags":"politics","label":"Politics","collectionName":"Politics"},

  {"id":4,"tags":"national_judiciary,supreme_court_of_india","label":"Supreme Court","collectionName":"Supreme Court"},
  {"id":5,"tags":"bombay_high_court,delhi_high_court,karnataka_high_court,punjab_and_haryana_high_court,calcutta_high_court,kerala_high_court,allahabad_high_court,rajasthan_high_court,madras_high_court,kolkata_high_court,orissa_high_court,gujarat_high_court,patna_high_court,madhya_pradesh_high_court,telangana_high_court,chhattisgarh_high_court,meghalaya_high_court,gauhati_high_court,jammu_kashmir_high_court,haryana_high_court,andhra_pradesh_high_court,high_court","label":"High Courts","collectionName":"High Court"},
  {"id":6,"tags":"national_judiciary,bombay_high_court,supreme_court_of_india,delhi_high_court,karnataka_high_court,punjab_and_haryana_high_court,calcutta_high_court,kerala_high_court,allahabad_high_court,rajasthan_high_court,madras_high_court,kolkata_high_court,orissa_high_court,gujarat_high_court,patna_high_court,madhya_pradesh_high_court,telangana_high_court,chhattisgarh_high_court,meghalaya_high_court,gauhati_high_court,jammu_kashmir_high_court,haryana_high_court,andhra_pradesh_high_court,high_court","label":"Judiciary","collectionName":"Judiciary"},

  {"id":7,"tags":"parliament,legislation,national_policy,national_judiciary","label":"Law","collectionName":"Legislation"},
  {"id":8,"tags":"national_aviation,aviation","label":"Aviation","collectionName":"Aviation"},
  {"id":9,"tags":"national_regulators","label":"Regulators","collectionName":"Regulators"},
  {"id":10,"tags":"national_schemes,national_governance","label":"National Schemes","collectionName":"Govt Schemes"},
  {"id":11,"tags":"national_india","label":"National","collectionName":"National"},

  {"id":12,"tags":"geopolitics,national_diplomacy,foreign_affairs","label":"Foreign Affairs","collectionName":"World Affairs"},
  {"id":13,"tags":"geopolitics","label":"Geopolitics","collectionName":"Geopolitics"},

  {"id":14,"tags":"donald_trump","label":"Trump","collectionName":"Trump"},
  {"id":15,"tags":"china","label":"China","collectionName":"China"},
  {"id":16,"tags":"israel","label":"Israel","collectionName":"Israel"},
  {"id":17,"tags":"global","label":"Global","collectionName":"Global"},

  {"id":18,"tags":"markets","label":"Stock Markets","collectionName":"Markets"},
  {"id":19,"tags":"industry,corporate","label":"Industry","collectionName":"Industry"},
  {"id":20,"tags":"banking,finance","label":"Banking & Finance","collectionName":"Banking"},
  {"id":21,"tags":"startups,internet_and_platforms,consumer_tech","label":"Startups","collectionName":"Startups"},
  {"id":22,"tags":"business","label":"Business","collectionName":"Business"},

  {"id":23,"tags":"monetary_policy,fiscal_policy","label":"Economic Policy","collectionName":"Economic Policy"},
  {"id":24,"tags":"data","label":"Economy Data","collectionName":"Economy Data"},
  {"id":25,"tags":"economy","label":"Economy","collectionName":"Economy"},

  {"id":26,"tags":"artificial_intelligence","label":"AI","collectionName":"AI"},
  {"id":27,"tags":"internet_and_platforms,digital_infrastructure,semiconductors,data_and_privacy,blockchain,space_technology","label":"Internet","collectionName":"Internet"},
  {"id":28,"tags":"technology","label":"Technology","collectionName":"Technology"},

  {"id":29,"tags":"cricket","label":"Cricket","collectionName":"Cricket"},
  {"id":30,"tags":"football","label":"Football","collectionName":"Football"},
  {"id":31,"tags":"sports","label":"Sports","collectionName":"Sports"},

  {"id":32,"tags":"health_&_science","label":"Health & Science","collectionName":"Health & Science"},
  {"id":33,"tags":"environment","label":"Environment","collectionName":"Environment"},

  {"id":34,"tags":"career,govt_jobs,employment,careers_and_jobs","label":"Jobs","collectionName":"Jobs"},
  {"id":35,"tags":"govt_jobs","label":"UPSC","collectionName":"Govt Jobs"},
  {"id":36,"tags":"education","label":"Education","collectionName":"Education"},

  {"id":37,"tags":"national_crime,national_judiciary,global_crime,global_judiciary,state_crime,state_judiciary","label":"Crime and Justice","collectionName":"Crime and Justice"},
  {"id":38,"tags":"state_policy,state_schemes,state_governance","label":"State Governance","collectionName":"State Governance"},
  {"id":39,"tags":"state","label":"State","collectionName":"State"}
  ]'::jsonb
)
ON CONFLICT (config_key)
DO UPDATE SET
  config_value = EXCLUDED.config_value,
  updated_at = NOW(); -- optional if you have this column