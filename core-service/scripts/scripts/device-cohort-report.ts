import 'dotenv/config';
import { Sequelize, QueryTypes } from 'sequelize';

type ReportRow = {
  cohort_date: string;
  stage: 'day_0' | 'day_1' | 'day_2';
  device_count: string;
};

type Args = {
  startDate?: string;
  days: number;
  platform?: string;
};

function parseArgs(argv: string[]): Args {
  const args: Args = { days: 3 };

  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i];
    const next = argv[i + 1];

    if (arg === '--start-date' && next) {
      args.startDate = next;
      i += 1;
    } else if (arg === '--days' && next) {
      args.days = Number(next);
      i += 1;
    } else if (arg === '--platform' && next) {
      args.platform = next;
      i += 1;
    } else if (arg === '--help') {
      printHelp();
      process.exit(0);
    }
  }

  if (!Number.isInteger(args.days) || args.days < 1) {
    throw new Error('--days must be a positive integer');
  }

  if (args.startDate && !/^\d{4}-\d{2}-\d{2}$/.test(args.startDate)) {
    throw new Error('--start-date must be in YYYY-MM-DD format');
  }

  return args;
}

function printHelp() {
  console.log(`
Usage:
  npx ts-node scripts/device-cohort-report.ts [--start-date YYYY-MM-DD] [--days 3] [--platform ios|android|web]

What it reports:
  Counts globally unique device_id values by first-seen date.
  The stage is relative to the device's first-seen date:
    day_0 = first-seen day
    day_1 = one day after first-seen
    day_2 = two days after first-seen

Note:
  This is an acquisition/cohort-age report. It is not a true retention report
  unless the app stores per-day device activity history.
`);
}

function createSequelize() {
  return new Sequelize(
    process.env.APP_DB_NAME!,
    process.env.APP_DB_USER!,
    process.env.APP_DB_PASSWORD!,
    {
      host: process.env.APP_DB_HOST!,
      port: Number(process.env.APP_DB_PORT!),
      dialect: 'postgres',
      logging: false,
      dialectOptions: {
        ssl: process.env.APP_DB_SSL === 'true'
          ? { require: true, rejectUnauthorized: false }
          : undefined,
      },
    }
  );
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const sequelize = createSequelize();

  const replacements: Record<string, string | number> = {
    days: args.days,
  };

  const where: string[] = [];

  if (args.startDate) {
    replacements.startDate = args.startDate;
    where.push(`first_seen_at::date >= :startDate::date`);
    where.push(`first_seen_at::date < (:startDate::date + (:days::int || ' days')::interval)`);
  } else {
    where.push(`first_seen_at::date >= (CURRENT_DATE - (:days::int - 1))`);
    where.push(`first_seen_at::date <= CURRENT_DATE`);
  }

  if (args.platform) {
    replacements.platform = args.platform;
    where.push(`platform = :platform`);
  }

  const rows = await sequelize.query<ReportRow>(
    `
      WITH first_seen_devices AS (
        SELECT
          device_id,
          MIN("createdAt") AS first_seen_at,
          (ARRAY_AGG(platform ORDER BY "createdAt" ASC))[1] AS platform
        FROM user_devices
        WHERE device_id IS NOT NULL AND device_id <> ''
        GROUP BY device_id
      ),
      cohorts AS (
        SELECT
          first_seen_at::date AS cohort_date,
          COUNT(*)::bigint AS devices
        FROM first_seen_devices
        WHERE ${where.join(' AND ')}
        GROUP BY first_seen_at::date
      ),
      stages AS (
        SELECT generate_series(0, 2) AS day_offset
      )
      SELECT
        cohorts.cohort_date::text,
        ('day_' || stages.day_offset)::text AS stage,
        cohorts.devices::text AS device_count
      FROM cohorts
      CROSS JOIN stages
      ORDER BY cohorts.cohort_date, stages.day_offset;
    `,
    {
      replacements,
      type: QueryTypes.SELECT,
    }
  );

  if (rows.length === 0) {
    console.log('No devices found for the selected window.');
    await sequelize.close();
    return;
  }

  console.table(
    rows.map((row) => ({
      cohort_date: row.cohort_date,
      stage: row.stage,
      device_count: Number(row.device_count),
    }))
  );

  await sequelize.close();
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
