const fs = require('fs');
const path = require('path');
const dotenv = require('dotenv');
const { Client } = require('pg');

const ROOT = path.resolve(__dirname, '..');
const MIGRATION_PATH = path.join(
  ROOT,
  'src',
  'db',
  'app-db',
  'migrations',
  'V10_insert_onboarding_interests_with_rules.sql'
);

dotenv.config({ path: path.join(ROOT, process.env.ENV_FILE || '.env') });

const REQUIRED_RULE_LABELS = [
  'Political Parties',
  'National Politics',
  'Global Politics',
  'National Law',
  'Global Law',
  'Indian Markets',
  'Global Markets',
  'Indian Industry',
  'Global Industry',
  'Indian Banking',
  'Global Banking',
  'Indian Business',
  'Global Business',
  'Indian Economy',
  'Global Economy',
  'National Sports',
  'Global Sports',
];

function parseMigrationInterests() {
  const text = fs.readFileSync(MIGRATION_PATH, 'utf8');
  const match = text.match(/VALUES\s*\(\s*'onboarding_interests'\s*,\s*'([\s\S]*)'::jsonb/);
  if (!match) throw new Error(`Could not extract onboarding_interests JSON from ${MIGRATION_PATH}`);
  return JSON.parse(match[1].replace(/''/g, "'"));
}

function isValidRule(rule) {
  return Boolean(
    rule &&
    Array.isArray(rule.groups) &&
    rule.groups.length > 0 &&
    rule.groups.every(group =>
      group &&
      (group.operator === 'AND' || group.operator === 'OR') &&
      Array.isArray(group.tags) &&
      group.tags.length > 0 &&
      group.tags.every(tag => typeof tag === 'string' && tag.trim())
    )
  );
}

function unique(values) {
  return [...new Set(values.filter(Boolean))];
}

function tagsForInterest(interest) {
  if (isValidRule(interest.collectionRule)) {
    return unique(interest.collectionRule.groups.flatMap(group => group.tags.map(tag => tag.trim())));
  }

  return unique(
    String(interest.tags || '')
      .split(',')
      .map(tag => tag.trim())
  );
}

function sqlForRule(rule, startIndex) {
  const parts = [];
  const params = [];
  let index = startIndex;

  for (const group of rule.groups) {
    const tags = unique(group.tags.map(tag => tag.trim()));
    params.push(tags);
    const tagsParam = `$${index++}`;

    if (group.operator === 'AND') {
      params.push(tags.length);
      const countParam = `$${index++}`;
      parts.push(`
        SELECT est.event_id
        FROM event_seo_tag est
        JOIN seo_tag st ON st.id = est.seo_tag_id
        WHERE st.name = ANY(${tagsParam}::text[])
        GROUP BY est.event_id
        HAVING COUNT(DISTINCT st.name) = ${countParam}
      `);
    } else {
      parts.push(`
        SELECT est.event_id
        FROM event_seo_tag est
        JOIN seo_tag st ON st.id = est.seo_tag_id
        WHERE st.name = ANY(${tagsParam}::text[])
        GROUP BY est.event_id
      `);
    }
  }

  return {
    sql: parts.join('\nUNION\n'),
    params,
    nextIndex: index,
  };
}

async function fetchRuleStats(client, interest) {
  const rule = isValidRule(interest.collectionRule)
    ? interest.collectionRule
    : {
      groupOperator: 'OR',
      groups: [{ operator: 'OR', tags: tagsForInterest(interest) }],
    };

  const built = sqlForRule(rule, 1);
  const countSql = `
    WITH matched AS (${built.sql})
    SELECT COUNT(DISTINCT event_id)::int AS count
    FROM matched
  `;
  const sampleSql = `
    WITH matched AS (${built.sql})
    SELECT e.id, e.time_stamp, e.image, led.title
    FROM event e
    JOIN matched m ON m.event_id = e.id
    LEFT JOIN localized_event_data led
      ON led.event_id = e.id
     AND led.language_id = 'en'
    ORDER BY e.time_stamp DESC NULLS LAST, e.id DESC
    LIMIT 5
  `;

  const [countResult, sampleResult] = await Promise.all([
    client.query(countSql, built.params),
    client.query(sampleSql, built.params),
  ]);

  const flatTags = tagsForInterest(interest);
  const flatResult = await client.query(`
    SELECT COUNT(DISTINCT est.event_id)::int AS count
    FROM event_seo_tag est
    JOIN seo_tag st ON st.id = est.seo_tag_id
    WHERE st.name = ANY($1::text[])
  `, [flatTags]);

  return {
    strictCount: countResult.rows[0].count,
    flatOrCount: flatResult.rows[0].count,
    samples: sampleResult.rows,
  };
}

async function main() {
  const interests = parseMigrationInterests();
  const ids = interests.map(interest => interest.id);
  const duplicateIds = ids.filter((id, index) => ids.indexOf(id) !== index);
  const labels = interests.map(interest => interest.label);
  const duplicateLabels = labels.filter((label, index) => labels.indexOf(label) !== index);
  const ruleInterests = interests.filter(interest => interest.collectionRule);
  const invalidRules = ruleInterests.filter(interest => !isValidRule(interest.collectionRule));
  const missingRequiredRules = REQUIRED_RULE_LABELS.filter(
    label => !ruleInterests.some(interest => interest.label === label)
  );
  const flatTagCoverageProblems = ruleInterests.filter(interest => {
    const flatTags = unique(String(interest.tags || '').split(',').map(tag => tag.trim()));
    const ruleTags = tagsForInterest(interest);
    return ruleTags.some(tag => !flatTags.includes(tag));
  });

  const allTags = unique(interests.flatMap(tagsForInterest));
  const client = new Client({
    host: process.env.APP_DB_HOST,
    port: Number(process.env.APP_DB_PORT),
    user: process.env.APP_DB_USER,
    password: process.env.APP_DB_PASSWORD,
    database: process.env.APP_DB_NAME,
    ssl: process.env.APP_DB_SSL === 'true' ? { rejectUnauthorized: false } : false,
  });

  await client.connect();

  const tagRows = await client.query(`
    SELECT st.name, COUNT(DISTINCT est.event_id)::int AS event_count
    FROM seo_tag st
    LEFT JOIN event_seo_tag est ON est.seo_tag_id = st.id
    WHERE st.name = ANY($1::text[])
    GROUP BY st.name
  `, [allTags]);
  const dbTagCounts = new Map(tagRows.rows.map(row => [row.name, row.event_count]));
  const missingTags = allTags.filter(tag => !dbTagCounts.has(tag));

  const selectedForSamples = [
    ...ruleInterests,
    ...interests.filter(interest => !interest.collectionRule).slice(0, 8),
  ];

  const results = [];
  for (const interest of selectedForSamples) {
    const stats = await fetchRuleStats(client, interest);
    results.push({
      id: interest.id,
      label: interest.label,
      hasRule: Boolean(interest.collectionRule),
      tagCount: tagsForInterest(interest).length,
      strictCount: stats.strictCount,
      flatOrCount: stats.flatOrCount,
      narrowedByRule: stats.flatOrCount - stats.strictCount,
      sampleTitles: stats.samples.map(row => row.title || row.id),
    });
  }

  await client.end();

  const zeroRuleMatches = results.filter(result => result.hasRule && result.strictCount === 0);
  const ruleBroadened = results.filter(
    result => result.hasRule && result.strictCount > result.flatOrCount
  );
  const failed =
    duplicateIds.length ||
    duplicateLabels.length ||
    invalidRules.length ||
    missingRequiredRules.length ||
    flatTagCoverageProblems.length ||
    missingTags.length ||
    ruleBroadened.length;

  const report = {
    db: {
      host: process.env.APP_DB_HOST,
      port: process.env.APP_DB_PORT,
      database: process.env.APP_DB_NAME,
    },
    structuralChecks: {
      interestCount: interests.length,
      ruleInterestCount: ruleInterests.length,
      duplicateIds,
      duplicateLabels,
      invalidRuleLabels: invalidRules.map(interest => interest.label),
      missingRequiredRules,
      flatTagCoverageProblemLabels: flatTagCoverageProblems.map(interest => interest.label),
    },
    tagChecks: {
      uniqueTagCount: allTags.length,
      missingTags,
      zeroEventTags: [...dbTagCounts.entries()]
        .filter(([, count]) => count === 0)
        .map(([name]) => name),
    },
    matchChecks: {
      sampledInterestCount: results.length,
      zeroRuleMatches: zeroRuleMatches.map(result => result.label),
      ruleBroadened: ruleBroadened.map(result => result.label),
      results,
    },
    status: failed ? 'FAIL' : 'PASS_WITH_WARNINGS_ALLOWED',
    note: zeroRuleMatches.length
      ? 'Some rule-backed interests currently match zero events in this DB; this may be data availability, not code failure.'
      : 'All rule-backed sampled interests matched at least one event in this DB.',
  };

  console.log(JSON.stringify(report, null, 2));

  if (failed) process.exit(1);
}

main().catch(error => {
  console.error(error);
  process.exit(1);
});
