const { Sequelize } = require('sequelize');

const sequelize = new Sequelize({
  host: 'localhost',
  port: 5434,
  username: 'postgres',
  password: 'neclstesting',
  database: 'appdb-prod-new',
  dialect: 'postgres',
  ssl: true,
  logging: false,
  dialectOptions: {
    ssl: {
      rejectUnauthorized: false
    }
  }
});

async function run() {
  try {
    await sequelize.authenticate();
    console.log('✓ Connected to database\n');
    
    console.log('=== Sample user_devices records (last 10) ===\n');
    const result = await sequelize.query(`
      SELECT 
        user_id,
        device_id,
        platform,
        last_active_at,
        "createdAt",
        "updatedAt"
      FROM user_devices 
      ORDER BY last_active_at DESC NULLS LAST
      LIMIT 10;
    `);
    
    result[0].forEach((row) => {
      console.log(`User: ${row.user_id}`);
      console.log(`  Device: ${row.device_id} (${row.platform})`);
      console.log(`  Last Active: ${row.last_active_at}`);
      console.log(`  Created: ${row.createdAt}`);
      console.log('');
    });
    
    console.log('\n=== Overall Statistics ===\n');
    const stats = await sequelize.query(`
      SELECT 
        COUNT(*)::int as total_records,
        COUNT(DISTINCT user_id)::int as unique_users,
        COUNT(CASE WHEN last_active_at IS NOT NULL THEN 1 END)::int as with_activity,
        COUNT(CASE WHEN last_active_at IS NULL THEN 1 END)::int as without_activity,
        MIN(last_active_at) as earliest_activity,
        MAX(last_active_at) as latest_activity
      FROM user_devices;
    `);
    
    console.log(JSON.stringify(stats[0][0], null, 2));
    
    console.log('\n\n=== Sample user with multiple devices ===\n');
    const multi = await sequelize.query(`
      SELECT 
        user_id,
        COUNT(*)::int as device_count,
        STRING_AGG(platform::text, ', ') as platforms
      FROM user_devices
      WHERE last_active_at IS NOT NULL
      GROUP BY user_id
      HAVING COUNT(*) > 1
      LIMIT 1;
    `);
    
    if (multi[0].length > 0) {
      const userId = multi[0][0].user_id;
      console.log(`User ${userId} - ${multi[0][0].device_count} devices (${multi[0][0].platforms})\n`);
      
      const deviceHistory = await sequelize.query(`
        SELECT 
          device_id,
          platform,
          last_active_at,
          "createdAt"
        FROM user_devices
        WHERE user_id = $1
        ORDER BY last_active_at DESC;
      `, { bind: [userId] });
      
      deviceHistory[0].forEach((row) => {
        const dateStr = row.last_active_at ? row.last_active_at.toISOString().split('T')[0] : 'NULL';
        console.log(`  ${(row.platform + ':').padEnd(12)} ${row.device_id} | Last Active: ${dateStr}`);
      });
    }
    
    console.log('\n\n=== Platform Distribution ===\n');
    const dist = await sequelize.query(`
      SELECT 
        platform,
        COUNT(*)::int as device_count,
        COUNT(CASE WHEN last_active_at IS NOT NULL THEN 1 END)::int as active_count
      FROM user_devices
      GROUP BY platform;
    `);
    
    dist[0].forEach((row) => {
      console.log(`${row.platform.padEnd(10)}: ${row.device_count} devices (${row.active_count} with activity)`);
    });
    
    await sequelize.close();
  } catch (err) {
    console.error('Error:', err);
    process.exit(1);
  }
}

run();
