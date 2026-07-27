-- ThinkO News Platform Database Initialization
-- This script creates both databases and enables required extensions

-- Create databases
CREATE DATABASE feedcrawler_db;
CREATE DATABASE app_db;

-- Connect to feedcrawler_db and enable pgvector
\c feedcrawler_db;
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Connect to app_db and enable pgvector
\c app_db;
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Note: Table creation is handled by:
-- - Core Service (via Sequelize ORM in app_db)
-- - NECLS Backend (via SQLAlchemy ORM in feedcrawler_db and app_db)
-- Run the services with initial startup to auto-create tables
