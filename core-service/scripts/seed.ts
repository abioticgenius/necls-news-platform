#!/usr/bin/env npx ts-node

/**
 * Standalone seed script to populate the database with initial data
 * Usage: npm run seed or npx ts-node scripts/seed.ts
 */

import { config } from 'dotenv';
import { initAppDb } from '../src/db/app-db';
import { runSeeds } from '../src/db/seeds';

// Load environment variables
config();

async function seed() {
  try {
    console.log('🌱 Starting database seeding...');
    
    // Initialize database connection
    await initAppDb();
    
    // Run seeds
    await runSeeds();
    
    console.log('✅ Database seeding completed successfully!');
    process.exit(0);
  } catch (error) {
    console.error('❌ Error during seeding:', error);
    process.exit(1);
  }
}

// Run if this file is executed directly
if (require.main === module) {
  seed();
}
