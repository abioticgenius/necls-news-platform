-- V7: Add pgvector embedding columns to seo_tag table
-- These columns are managed by migration only and must NOT be declared
-- as standard Sequelize DataTypes to avoid type reversion to real[].

CREATE EXTENSION IF NOT EXISTS vector;

ALTER TABLE seo_tag ADD COLUMN IF NOT EXISTS embedding vector(128);
ALTER TABLE seo_tag ADD COLUMN IF NOT EXISTS vector_updated_at TIMESTAMPTZ;
