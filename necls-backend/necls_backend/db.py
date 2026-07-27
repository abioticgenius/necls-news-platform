"""DB engine + table metadata centralised here."""
from __future__ import annotations
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert as pg_insert
from pgvector.sqlalchemy import Vector
from pathlib import Path
from .config import settings
from sqlalchemy.dialects import postgresql as pg

import uuid
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY

engine = sa.create_engine(settings.db_url, future=True, pool_pre_ping=True)
meta   = sa.MetaData()

# ---------------------------------------------------------------------------
# Articles (raw content extracted by crawler)
articles = sa.Table(
    "articles", meta,
    sa.Column("id",            sa.String(64), primary_key=True),
    sa.Column("url",           sa.Text,  nullable=False),
    sa.Column("title",         sa.Text),
    sa.Column("authors",       sa.JSON),
    sa.Column("date_publish",  sa.DateTime(timezone=True)),
    sa.Column("description",   sa.Text),
    sa.Column("image_url",     sa.Text),
    sa.Column("language",      sa.String(8)),
    sa.Column("source_domain", sa.String(255)),
    sa.Column("text",          sa.Text),
    sa.Column("fetched_at",    sa.DateTime(timezone=True), nullable=False),
    sa.Column("feed_data",     sa.JSON,  nullable=False),
    sa.Column("is_gnews", sa.Boolean, nullable=False, server_default=sa.text("false")),
)

# ---------------------------------------------------------------------------
#  Embeddings + clustering tables (created even if not used right away)
EMB_DIM = 384

def _created():
    return sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)

def _updated():
    return sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False)

article_vectors = sa.Table(
    "article_vectors", meta,
    sa.Column("article_id", sa.String(64), sa.ForeignKey("articles.id"), primary_key=True),
    sa.Column("emb", Vector(EMB_DIM), nullable=False),
    _created(), _updated(),
)

# Review users table (for tracking who approved/rejected clusters)
review_users = sa.Table(
    "review_users", meta,
    sa.Column("id", sa.Integer, primary_key=True),
    sa.Column("username", sa.Text, nullable=False),
    sa.Column("email", sa.Text),
    _created(), _updated(),
)

story_clusters = sa.Table(
    "story_clusters", meta,
    sa.Column("cluster_id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
    sa.Column("headline",   sa.Text),
    sa.Column("first_date", sa.DateTime(timezone=True)),
    sa.Column("last_date",  sa.DateTime(timezone=True)),
    sa.Column("size",       sa.Integer),
    sa.Column("centroid",   Vector(EMB_DIM)),
    sa.Column("filter_status", sa.String(30), default="pending"),
    sa.Column("rejection_reason", sa.Text),
    sa.Column("rejected_at", sa.DateTime(timezone=True)),
    sa.Column("rejected_by", sa.Integer, sa.ForeignKey("review_users.id", ondelete="SET NULL"), nullable=True),
    sa.Column("auto_approved", sa.Boolean, default=False),
    sa.Column("auto_approved_at", sa.DateTime(timezone=True)),
    _created(), _updated(),
)

story_members = sa.Table(
    "story_members", meta,
    sa.Column("cluster_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("story_clusters.cluster_id")),
    sa.Column("article_id", sa.String(64), sa.ForeignKey("articles.id")),
    sa.PrimaryKeyConstraint("cluster_id", "article_id"),
    _created(), _updated(),
)

meta_clusters = sa.Table(
    "meta_clusters", meta,
    sa.Column("meta_id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
    sa.Column("headline",   sa.Text),
    sa.Column("first_date", sa.DateTime(timezone=True)),
    sa.Column("last_date",  sa.DateTime(timezone=True)),
    sa.Column("size",       sa.Integer),
    sa.Column("centroid",   Vector(EMB_DIM)),
    _created(), _updated(),
)

meta_members = sa.Table(
    "meta_members", meta,
    sa.Column("meta_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("meta_clusters.meta_id")),
    sa.Column("cluster_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("story_clusters.cluster_id")),
    sa.PrimaryKeyConstraint("meta_id", "cluster_id"),
    _created(), _updated(),
)

db2_links = sa.Table(
    "db2_links", meta,
    sa.Column("cluster_id", pg.UUID(as_uuid=True),
              sa.ForeignKey("story_clusters.cluster_id", ondelete="CASCADE"),
              primary_key=True),
    sa.Column("db2_event_id", pg.UUID(as_uuid=True), nullable=False),
    sa.Column("last_synced_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
)

# ---------------- generations (single table holds most meta) ----------------
generations = sa.Table(
    "generations", meta,
    sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
    sa.Column("cluster_id", pg.UUID(as_uuid=True),
              sa.ForeignKey("story_clusters.cluster_id", ondelete="CASCADE"),
              nullable=False),
    sa.Column("artifact", sa.Text, nullable=False),  # 'summary' | 'story_so_far' | 'looking_ahead'
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.Column("model_name", sa.Text),
    sa.Column("input_hash", sa.Text),                 # SHA-256 of normalized input payload
    # generation-level metadata (folded in to reduce tables)
    sa.Column("sources_used", pg.ARRAY(sa.Text), server_default=sa.text("'{}'"), nullable=False),
    sa.Column("sources_excluded", pg.ARRAY(sa.Text), server_default=sa.text("'{}'"), nullable=False),
    sa.Column("last_updated_article", sa.DateTime(timezone=True)),
    sa.Column("confidence_score", sa.Float),
    # arbitrary artifact-specific bag (e.g., categories/tags/faq etc.)
    sa.Column("extra", pg.JSONB),
    sa.UniqueConstraint("cluster_id", "artifact", "input_hash", name="uq_generations_cluster_artifact_hash"),
    sa.Index("idx_generations_cluster_artifact", "cluster_id", "artifact"),
)

# ---------------- sources (per generation) ----------------
sources = sa.Table(
    "sources", meta,
    sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
    sa.Column("generation_id", pg.UUID(as_uuid=True),
              sa.ForeignKey("generations.id", ondelete="CASCADE"),
              nullable=False),
    sa.Column("url", sa.Text, nullable=False),
    sa.Column("title", sa.Text),
    sa.Column("article_date", sa.DateTime(timezone=True)),
    sa.Column("logo", sa.Text),
    sa.UniqueConstraint("generation_id", "url", name="uq_sources_gid_url"),
    sa.Index("idx_sources_generation", "generation_id"),
)

# ---------------- summary (already shaped for DB2 LocalizedEventData) ----------------
summary_localized = sa.Table(
    "summary_localized", meta,
    sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
    sa.Column("generation_id", pg.UUID(as_uuid=True),
              sa.ForeignKey("generations.id", ondelete="CASCADE"),
              nullable=False),
    sa.Column("language_id", sa.Text, nullable=False),      # 'en', 'hi', ...
    sa.Column("last_updated_at", sa.DateTime(timezone=True)),
    sa.Column("headline", sa.Text, nullable=False),
    sa.Column("mini_headline", sa.Text),
    sa.Column("mini_summary", sa.Text),
    sa.Column("audio_text", sa.Text),
    sa.Column("audio_s3_url", sa.Text),
    sa.Column("audio_full_story_s3_url", sa.Text),
    # content for DB2
    sa.Column("bullets", pg.ARRAY(sa.Text), server_default=sa.text("'{}'"), nullable=False),
    # quotes & facts as JSON arrays (stable, schema-free)
    sa.Column("quotes", pg.JSONB),  # [{id, quote, speaker, source}]
    sa.Column("facts", pg.JSONB),   # [{claim, sources_claimed, sources_total, confidence, reason}]
    sa.UniqueConstraint("generation_id", "language_id", name="uq_summary_gen_lang"),
)

# ---------------- slides (generic for story_so_far & looking_ahead) ----------------
slides = sa.Table(
    "slides", meta,
    sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
    sa.Column("generation_id", pg.UUID(as_uuid=True),
              sa.ForeignKey("generations.id", ondelete="CASCADE"),
              nullable=False),
    sa.Column("type", sa.Text, nullable=False),      # e.g., 'timeline'|'explainer'|'trendline'|'stakeholder_view'|'forecast'|'scenarios'|...
    sa.Column("sequence", sa.Integer, nullable=False, server_default="1"),  # order preserved for DB2
    sa.Index("idx_slides_gen_seq", "generation_id", "sequence"),
)

slide_localized = sa.Table(
    "slide_localized", meta,
    sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
    sa.Column("slide_id", pg.UUID(as_uuid=True),
              sa.ForeignKey("slides.id", ondelete="CASCADE"),
              nullable=False),
    sa.Column("language_id", sa.Text, nullable=False),
    sa.Column("success", sa.Boolean, nullable=False, server_default=sa.text("true")),
    sa.Column("failure_reason", sa.Text),
    sa.Column("heading", sa.Text),
    # fully generic payload
    sa.Column("content_type", sa.Text, nullable=False),   # 'bullets'|'text'|'timeline'|'table'|'stakeholder_impact'|'scenario'|...
    sa.Column("content", pg.JSONB, nullable=False),
    sa.UniqueConstraint("slide_id", "language_id", name="uq_slide_loc_lang"),
)

# ---------------- per-artifact token usage ----------------
llm_runs = sa.Table(
    "llm_runs", meta,
    sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.Column("cluster_id", pg.UUID(as_uuid=True),
              sa.ForeignKey("story_clusters.cluster_id", ondelete="CASCADE"),
              nullable=False),
    sa.Column("generation_id", pg.UUID(as_uuid=True), sa.ForeignKey("generations.id", ondelete="SET NULL")),
    sa.Column("artifact", sa.Text),
    sa.Column("model_name", sa.Text),
    sa.Column("system_fingerprint", sa.Text),
    sa.Column("provider_response_id", sa.Text),
    sa.Column("finish_reason", sa.Text),
    sa.Column("prompt_tokens", sa.Integer),
    sa.Column("completion_tokens", sa.Integer),
    sa.Column("total_tokens", sa.Integer),
    sa.Column("prompt_tokens_details", pg.JSONB),
    sa.Column("completion_tokens_details", pg.JSONB),
    sa.Column("logprobs", pg.JSONB),
    sa.Column("raw_payload", pg.JSONB),
    sa.Index("idx_llm_runs_cluster", "cluster_id"),
)

sa.Index("ix_articles_id", articles.c.id, unique=True)
sa.Index("ix_articles_url", articles.c.url, unique=True)

# Auto‑create if missing (only if connection is available)
# This prevents errors on import when database doesn't exist yet
def init_database():
    """Initialize database tables. Call this explicitly after ensuring database exists."""
    try:
        meta.create_all(engine)
        # Add any missing columns that may have been added after initial table creation
        _ensure_audio_columns()
        _ensure_filter_status_column()
        _ensure_approval_columns()
        _ensure_review_status_columns()
        _ensure_temporal_indexes_db1()
    except Exception as e:
        # Silently fail on import - database will be created when explicitly called
        pass

def _ensure_audio_columns():
    """Ensure audio_full_story_s3_url column exists in summary_localized table.
    This is called automatically during database initialization to handle schema migrations.
    """
    try:
        with engine.begin() as conn:
            # Check if column exists
            result = conn.execute(
                sa.text("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = 'summary_localized' 
                    AND column_name = 'audio_full_story_s3_url';
                """)
            )
            
            if not result.fetchone():
                # Column doesn't exist, add it
                conn.execute(
                    sa.text("""
                        ALTER TABLE summary_localized 
                        ADD COLUMN IF NOT EXISTS audio_full_story_s3_url TEXT;
                    """)
                )
                print("✓ Added audio_full_story_s3_url column to summary_localized")
    except Exception as e:
        # Table might not exist yet, or column already exists - that's okay
        # This is expected during initial setup
        pass

def _ensure_filter_status_column():
    """Ensure filter_status column exists in story_clusters table.
    This is called automatically during database initialization to handle schema migrations.
    """
    try:
        with engine.begin() as conn:
            # Check if column exists
            result = conn.execute(
                sa.text("""
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_name = 'story_clusters'
                    AND column_name = 'filter_status';
                """)
            )

            if not result.fetchone():
                # Column doesn't exist, add it
                conn.execute(
                    sa.text("""
                        ALTER TABLE story_clusters
                        ADD COLUMN IF NOT EXISTS filter_status VARCHAR(30) DEFAULT 'pending';
                    """)
                )
                print("✓ Added filter_status column to story_clusters")
    except Exception as e:
        # Table might not exist yet, or column already exists - that's okay
        # This is expected during initial setup
        pass

def _ensure_approval_columns():
    """Ensure approval/rejection tracking columns exist in story_clusters table.
    This is called automatically during database initialization to handle schema migrations.
    """
    try:
        with engine.begin() as conn:
            # Check and add rejection_reason column
            result = conn.execute(
                sa.text("""
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_name = 'story_clusters'
                    AND column_name = 'rejection_reason';
                """)
            )

            if not result.fetchone():
                conn.execute(
                    sa.text("""
                        ALTER TABLE story_clusters
                        ADD COLUMN IF NOT EXISTS rejection_reason TEXT;
                    """)
                )
                print("✓ Added rejection_reason column to story_clusters")

            # Check and add rejected_at column
            result = conn.execute(
                sa.text("""
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_name = 'story_clusters'
                    AND column_name = 'rejected_at';
                """)
            )

            if not result.fetchone():
                conn.execute(
                    sa.text("""
                        ALTER TABLE story_clusters
                        ADD COLUMN IF NOT EXISTS rejected_at TIMESTAMP WITH TIME ZONE;
                    """)
                )
                print("✓ Added rejected_at column to story_clusters")

            # Check and add rejected_by column
            result = conn.execute(
                sa.text("""
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_name = 'story_clusters'
                    AND column_name = 'rejected_by';
                """)
            )

            if not result.fetchone():
                conn.execute(
                    sa.text("""
                        ALTER TABLE story_clusters
                        ADD COLUMN IF NOT EXISTS rejected_by INTEGER REFERENCES review_users(id);
                    """)
                )
                print("✓ Added rejected_by column to story_clusters")

            # Check and add auto_approved column
            result = conn.execute(
                sa.text("""
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_name = 'story_clusters'
                    AND column_name = 'auto_approved';
                """)
            )

            if not result.fetchone():
                conn.execute(
                    sa.text("""
                        ALTER TABLE story_clusters
                        ADD COLUMN IF NOT EXISTS auto_approved BOOLEAN DEFAULT FALSE;
                    """)
                )
                print("✓ Added auto_approved column to story_clusters")

            # Check and add auto_approved_at column
            result = conn.execute(
                sa.text("""
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_name = 'story_clusters'
                    AND column_name = 'auto_approved_at';
                """)
            )

            if not result.fetchone():
                conn.execute(
                    sa.text("""
                        ALTER TABLE story_clusters
                        ADD COLUMN IF NOT EXISTS auto_approved_at TIMESTAMP WITH TIME ZONE;
                    """)
                )
                print("✓ Added auto_approved_at column to story_clusters")

    except Exception as e:
        # Table might not exist yet, or columns already exist - that's okay
        # This is expected during initial setup
        pass

def _ensure_review_status_columns():
    """Ensure review_status table has all required columns for auto-approval."""
    try:
        with engine.begin() as conn:
            # Check and add approval_status column
            result = conn.execute(
                sa.text("""
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_name = 'review_status'
                    AND column_name = 'approval_status';
                """)
            )

            if not result.fetchone():
                conn.execute(
                    sa.text("""
                        ALTER TABLE review_status
                        ADD COLUMN IF NOT EXISTS approval_status VARCHAR(20) DEFAULT 'pending';
                    """)
                )
                print("✓ Added approval_status column to review_status")

            # Check and add approved_at column
            result = conn.execute(
                sa.text("""
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_name = 'review_status'
                    AND column_name = 'approved_at';
                """)
            )

            if not result.fetchone():
                conn.execute(
                    sa.text("""
                        ALTER TABLE review_status
                        ADD COLUMN IF NOT EXISTS approved_at TIMESTAMP WITH TIME ZONE;
                    """)
                )
                print("✓ Added approved_at column to review_status")

            # Check and add rejection_reason column
            result = conn.execute(
                sa.text("""
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_name = 'review_status'
                    AND column_name = 'rejection_reason';
                """)
            )

            if not result.fetchone():
                conn.execute(
                    sa.text("""
                        ALTER TABLE review_status
                        ADD COLUMN IF NOT EXISTS rejection_reason TEXT;
                    """)
                )
                print("✓ Added rejection_reason column to review_status")

            # Check and add processing_status column
            result = conn.execute(
                sa.text("""
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_name = 'review_status'
                    AND column_name = 'processing_status';
                """)
            )

            if not result.fetchone():
                conn.execute(
                    sa.text("""
                        ALTER TABLE review_status
                        ADD COLUMN IF NOT EXISTS processing_status VARCHAR(20) DEFAULT 'pending';
                    """)
                )
                print("✓ Added processing_status column to review_status")

            # Check and add processed_at column
            result = conn.execute(
                sa.text("""
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_name = 'review_status'
                    AND column_name = 'processed_at';
                """)
            )

            if not result.fetchone():
                conn.execute(
                    sa.text("""
                        ALTER TABLE review_status
                        ADD COLUMN IF NOT EXISTS processed_at TIMESTAMP WITH TIME ZONE;
                    """)
                )
                print("✓ Added processed_at column to review_status")

    except Exception as e:
        # Table might not exist yet, or columns already exist - that's okay
        # This is expected during initial setup
        pass

def _ensure_temporal_indexes_db1():
    """Ensure temporal indexes exist on DB1 for optimal temporal query performance."""
    try:
        # Create indexes outside transaction for CONCURRENTLY to work
        with engine.connect() as conn:
            # Index on articles.date_publish for fast temporal filtering
            conn.execute(sa.text("""
                CREATE INDEX IF NOT EXISTS idx_articles_date_publish
                ON articles(date_publish)
                WHERE date_publish IS NOT NULL;
            """))

            # Composite index on articles(date_publish, title) for sorting
            conn.execute(sa.text("""
                CREATE INDEX IF NOT EXISTS idx_articles_date_publish_title
                ON articles(date_publish DESC, title)
                WHERE date_publish IS NOT NULL AND title IS NOT NULL;
            """))

            # Index on articles(source_domain, date_publish) for source filtering
            conn.execute(sa.text("""
                CREATE INDEX IF NOT EXISTS idx_articles_source_date
                ON articles(source_domain, date_publish DESC)
                WHERE source_domain IS NOT NULL AND date_publish IS NOT NULL;
            """))

            print("✓ DB1 temporal indexes verified/created")
    except Exception as e:
        # Silently fail - indexes might already exist or table might not be ready
        # This is expected during initial setup
        print(f"[INFO] DB1 temporal indexes: {e}")

def ensure_db1_schema(raise_on_error: bool = False):
    """Ensure DB1 schema is up to date. Call this at application startup.
    Creates tables if missing and adds any new columns.
    
    Args:
        raise_on_error: If True, raise exceptions instead of silently failing.
                        Use True when called from scripts/pipeline.
    """
    try:
        # Create vector extension first (required for VECTOR columns)
        with engine.begin() as conn:
            conn.execute(sa.text("CREATE EXTENSION IF NOT EXISTS vector;"))
        # Create all tables
        meta.create_all(engine)
        _ensure_audio_columns()
        _ensure_filter_status_column()
        _ensure_approval_columns()
        _ensure_review_status_columns()
    except Exception as e:
        if raise_on_error:
            print(f"[ERROR] Failed to ensure DB1 schema: {e}")
            import traceback
            traceback.print_exc()
            raise
        # Silently fail if database connection is not available
        # This allows the module to be imported even when DB is not ready
        pass