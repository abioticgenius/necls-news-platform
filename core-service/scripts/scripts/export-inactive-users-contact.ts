import 'dotenv/config';
import { Sequelize, QueryTypes } from 'sequelize';
import { firebaseAuth } from '../src/app/firebase/firebase';

const LIMIT = Number(process.env.INACTIVE_USERS_LIMIT ?? 100);

type InactiveUser = {
  user_id: string;
  uid: string;
  email: string | null;
  name: string | null;
  last_active_at: Date | null;
};

const sequelize = new Sequelize(
  process.env.APP_DB_NAME!,
  process.env.APP_DB_USER!,
  process.env.APP_DB_PASSWORD!,
  {
    host: process.env.APP_DB_HOST!,
    port: Number(process.env.APP_DB_PORT!),
    dialect: 'postgres',
    logging: false,
    dialectOptions: {
      ssl:
        process.env.APP_DB_SSL === 'true'
          ? { require: true, rejectUnauthorized: false }
          : undefined,
    },
  }
);

async function main() {
  console.log(`[inactive-users] Querying up to ${LIMIT} inactive users...`);

  const users = await sequelize.query<InactiveUser>(
    `
      WITH latest_user_activity AS (
        SELECT
          u.id AS user_id,
          u.uid,
          u.email,
          u.name,
          MAX(COALESCE(ud.last_active_at, ud."updatedAt", ud."createdAt")) AS last_active_at
        FROM users u
        LEFT JOIN user_devices ud
          ON ud.user_id = u.id
        GROUP BY u.id, u.uid, u.email, u.name
      )

      SELECT
        user_id,
        uid,
        email,
        name,
        last_active_at
      FROM latest_user_activity
      WHERE last_active_at < NOW() - INTERVAL '30 days'
         OR last_active_at IS NULL
      ORDER BY last_active_at ASC NULLS FIRST
      LIMIT :limit;
    `,
    {
      replacements: { limit: LIMIT },
      type: QueryTypes.SELECT,
    }
  );

  console.log(`[inactive-users] Found ${users.length} inactive users to enrich.`);

  if (users.length === 0) {
    await sequelize.close();
    return;
  }

  const enriched = [];
  const startedAt = Date.now();

  for (let index = 0; index < users.length; index += 1) {
    const user = users[index];
    const position = index + 1;

    console.log(`[inactive-users] ${position}/${users.length} fetching Firebase user ${user.uid}`);

    try {
      const firebaseUser = await firebaseAuth.getUser(user.uid);

      enriched.push({
        user_id: user.user_id,
        uid: user.uid,
        db_email: user.email,
        firebase_email: firebaseUser.email ?? null,
        firebase_phone: firebaseUser.phoneNumber ?? null,
        db_name: user.name,
        firebase_name: firebaseUser.displayName ?? null,
        providers: firebaseUser.providerData.map((p) => p.providerId).join(','),
        last_active_at: user.last_active_at,
      });
    } catch (error: any) {
      enriched.push({
        user_id: user.user_id,
        uid: user.uid,
        db_email: user.email,
        firebase_email: null,
        firebase_phone: null,
        db_name: user.name,
        firebase_name: null,
        providers: null,
        last_active_at: user.last_active_at,
        error: error?.message,
      });
    }

    if (position % 10 === 0 || position === users.length) {
      const elapsedSeconds = ((Date.now() - startedAt) / 1000).toFixed(1);
      console.log(`[inactive-users] Progress ${position}/${users.length} done after ${elapsedSeconds}s`);
    }
  }

  console.log('[inactive-users] Enrichment complete. Results:');
  console.table(enriched);
  await sequelize.close();
}

main().catch(async (error) => {
  console.error(error);
  await sequelize.close();
  process.exit(1);
});
