import { Client } from 'pg';

const client = new Client({
  host: 'localhost',
  port: 5434,
  user: 'postgres',
  password: 'neclstesting',
  database: 'appdb-prod-new',
  ssl: { rejectUnauthorized: false }
});

async function run() {
  await client.connect();
  
  console.log('=== Sample user_devices records ===\n');
  
  const result = await client.query(`
    SELECT 
      user_id,
      device_id,
      platform,
      last_active_at,
      "createdAt",
      "updatedAt"
    FROM user_devices 
    ORDER BY last_active_at DESC NULLS LAST
    LIMIT 15;
  `);
  
  result.rows.forEach(row => {
    console.log(`User: ${row.user_id}`);
    console.log(`  Device: ${row.device_id}`);
    console.log(`  Platform: ${row.platform}`);
    console.log(`  Last Active: ${row.last_active_at}`);
    console.log(`  Created: ${row.createdAt}`);
    console.log(`  Updated: ${row.updatedAt}`);
    console.log('');
  });
  
  console.log('\n=== Statistics ===\n');
  const stats = await client.query(`
    SELECT 
      COUNT(*) as total_records,
      COUNT(DISTINCT user_id) as unique_users,
      COUNT(CASE WHEN last_active_at IS NOT NULL THEN 1 END) as with_activity,
      COUNT(CASE WHEN last_active_at IS NULL THEN 1 END) as without_activity,
      MIN(last_active_at) as earliest_activity,
      MAX(last_active_at) as latest_activity
    FROM user_devices;
  `);
  
  console.log(JSON.stringify(stats.rows[0], null, 2));
  
  console.log('\n=== Sample: Multiple devices per user ===\n');
  const multi = await client.query(`
    SELECT 
      user_id,
      COUNT(*) as device_count,
      STRING_AGG(platform, ', ') as platforms,
      MAX(last_active_at) as latest_activity,
      MIN(last_active_at) as earliest_activity
    FROM user_devices
    WHERE last_active_at IS NOT NULL
    GROUP BY user_id
    HAVING COUNT(*) > 1
    LIMIT 5;
  `);
  
  multi.rows.forEach(row => {
    console.log(`User: ${row.user_id}`);
    console.log(`  Devices: ${row.device_count} (${row.platforms})`);
    console.log(`  Latest activity: ${row.latest_activity}`);
    console.log(`  Earliest activity: ${row.earliest_activity}`);
    console.log('');
  });
  
  console.log('\n=== One user\'s full activity history ===\n');
  if (result.rows.length > 0) {
    const userId = result.rows[0].user_id;
    const history = await client.query(`
      SELECT 
        device_id,
        platform,
        last_active_at,
        "createdAt"
      FROM user_devices
      WHERE user_id = $1
      ORDER BY last_active_at DESC;
    `, [userId]);
    
    console.log(`User ${userId}:`);
    history.rows.forEach(row => {
      console.log(`  ${row.platform} | ${row.device_id} | Active: ${row.last_active_at} | Created: ${row.createdAt}`);
    });
  }
  
  await client.end();
}

run().catch(err => {
  console.error('Error:', err);
  process.exit(1);
});
