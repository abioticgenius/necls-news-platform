import uuid, json, datetime as dt
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY
from sqlalchemy.dialects.postgresql import insert as pg_insert
from pgvector.sqlalchemy import Vector
from .config import settings
engine = sa.create_engine(settings.db2_url, future=True, pool_pre_ping=True)

meta2 = sa.MetaData()

category = sa.Table(
    "category", meta2,
    sa.Column("id", UUID(as_uuid=True), primary_key=True),
    sa.Column("name", sa.Text, nullable=False, unique=True),
)

event = sa.Table(
    "event", meta2,
    sa.Column("id", UUID(as_uuid=True), primary_key=True),
    sa.Column("image", sa.Text),
    sa.Column("image_source_url", sa.Text),
    sa.Column("time_stamp", sa.DateTime(timezone=True)),
    sa.Column("created_date", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.Column("article_type", sa.Text),
)

event_analysis = sa.Table(
    "event_analysis", meta2,
    sa.Column("id", UUID(as_uuid=True), primary_key=True),
    sa.Column("event_id", UUID(as_uuid=True), sa.ForeignKey("event.id", ondelete="CASCADE"), nullable=False),
    sa.Column("sequence", sa.Integer, nullable=False),
    sa.UniqueConstraint("event_id", "sequence", name="uq_event_analysis_event_seq"),
)

event_so_far = sa.Table(
    "event_so_far", meta2,
    sa.Column("id", UUID(as_uuid=True), primary_key=True),
    sa.Column("event_id", UUID(as_uuid=True), sa.ForeignKey("event.id", ondelete="CASCADE"), nullable=False),
    sa.Column("sequence", sa.Integer, nullable=False),
    sa.UniqueConstraint("event_id", "sequence", name="uq_event_so_far_event_seq"),
)

source = sa.Table(
    "source", meta2,
    sa.Column("id", UUID(as_uuid=True), primary_key=True),
    sa.Column("logo_id", UUID(as_uuid=True), sa.ForeignKey("logos.id")),
    sa.Column("event_id", UUID(as_uuid=True), sa.ForeignKey("event.id", ondelete="CASCADE"), nullable=False),
    sa.Column("source_url", sa.Text, nullable=False),
    sa.Column("title", sa.Text),
    sa.UniqueConstraint("event_id", "source_url", name="uq_source_event_url"),
)

localized_event_data = sa.Table(
    "localized_event_data", meta2,
    sa.Column("id", UUID(as_uuid=True), primary_key=True),
    sa.Column("language_id", sa.Text, nullable=False),
    sa.Column("event_id", UUID(as_uuid=True), sa.ForeignKey("event.id", ondelete="CASCADE"), nullable=False),
    sa.Column("title", sa.Text, nullable=False),
    sa.Column("description", sa.Text),
    sa.Column("content", JSONB),
    sa.Column("content_type", sa.Text),
    sa.Column("audio", sa.Text),
    sa.Column("audio_full_story", sa.Text),
    sa.Column("quotes", JSONB),  # [{id, quote, speaker, source}]
    sa.UniqueConstraint("event_id", "language_id", name="uq_led_event_lang"),
)

localized_event_so_far = sa.Table(
    "localized_event_so_far", meta2,
    sa.Column("id", UUID(as_uuid=True), primary_key=True),
    sa.Column("language_id", sa.Text, nullable=False),
    sa.Column("event_so_far_id", UUID(as_uuid=True), sa.ForeignKey("event_so_far.id", ondelete="CASCADE"), nullable=False),
    sa.Column("content", JSONB),
    sa.Column("content_type", sa.Text),
    sa.UniqueConstraint("event_so_far_id", "language_id", name="uq_lesf_event_lang"),
)

localized_event_analysis = sa.Table(
    "localized_event_analysis", meta2,
    sa.Column("id", UUID(as_uuid=True), primary_key=True),
    sa.Column("language_id", sa.Text, nullable=False),
    sa.Column("event_analysis_id", UUID(as_uuid=True), sa.ForeignKey("event_analysis.id", ondelete="CASCADE"), nullable=False),
    sa.Column("content", JSONB),
    sa.Column("content_type", sa.Text),
    sa.UniqueConstraint("event_analysis_id", "language_id", name="uq_lea_event_lang"),
)

language = sa.Table(
    "language", meta2,
    sa.Column("id", sa.Text, primary_key=True),
    sa.Column("name", sa.Text, nullable=False),
)

logos = sa.Table(
    "logos", meta2,
    sa.Column("id", UUID(as_uuid=True), primary_key=True),
    sa.Column("name", sa.Text, nullable=False),
    sa.Column("website", sa.Text, nullable=False),
    sa.Column("favicon_s3_path", sa.Text, nullable=True),
    sa.Column("logo_s3_path", sa.Text, nullable=True),

)

seo_tag = sa.Table(
    "seo_tag", meta2,
    sa.Column("id", UUID(as_uuid=True), primary_key=True),
    sa.Column("name", sa.Text, nullable=False),  # Can be multi-word (2-4 words)
    sa.Column(
        "type",
        sa.Enum(
            "tag",
            "Category",
            "Sub Category",
            "Core Event",
            "Associated Event",
            "Entity",
            "Place",
            "Impact",
            name="enum_seo_tag_type",
        ),
        nullable=False,
        server_default=sa.text("'tag'::enum_seo_tag_type"),
    ),
    sa.Column("created_date", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.Column("embedding", Vector(128), nullable=True),           # SVD embedding — added by migration 003
    sa.Column("vector_updated_at", sa.DateTime(timezone=True), nullable=True),  # NULL = dirty, needs recompute
    sa.UniqueConstraint("name", "type", name="uq_seo_tag_name_type"),
)

event_seo_tag = sa.Table(
    "event_seo_tag", meta2,
    sa.Column("id", UUID(as_uuid=True), primary_key=True),
    sa.Column("event_id", UUID(as_uuid=True), sa.ForeignKey("event.id", ondelete="CASCADE"), nullable=False),
    sa.Column("seo_tag_id", UUID(as_uuid=True), sa.ForeignKey("seo_tag.id", ondelete="CASCADE"), nullable=False),
    sa.Column("weight", sa.Integer, nullable=False, server_default=sa.text("50")),
    sa.Column("role", sa.Enum('core', 'contextual', name="enum_event_seo_tag_role"), nullable=False, server_default=sa.text("'contextual'::enum_event_seo_tag_role")),
    sa.Column("linked_to_tag_id", UUID(as_uuid=True), sa.ForeignKey("seo_tag.id", ondelete="SET NULL"), nullable=True),
    sa.Column("created_date", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.UniqueConstraint("event_id", "seo_tag_id", name="uq_event_seo_tag_event_tag"),
)

seo_tag_relation = sa.Table(
    "seo_tag_relation", meta2,
    sa.Column("id", UUID(as_uuid=True), primary_key=True),
    sa.Column("parent_tag_id", UUID(as_uuid=True), sa.ForeignKey("seo_tag.id", ondelete="CASCADE"), nullable=False),
    sa.Column("child_tag_id", UUID(as_uuid=True), sa.ForeignKey("seo_tag.id", ondelete="CASCADE"), nullable=False),
    sa.Column("created_date", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.UniqueConstraint("parent_tag_id", "child_tag_id", name="uq_seo_tag_relation_unique"),
    sa.Index("idx_seo_tag_relation_parent", "parent_tag_id"),
    sa.Index("idx_seo_tag_relation_child", "child_tag_id"),
)

event_faq = sa.Table(
    "event_faq",
    meta2,
    sa.Column("id", UUID(as_uuid=True), primary_key=True),
    sa.Column("event_id", UUID(as_uuid=True), sa.ForeignKey("event.id", ondelete="CASCADE"), nullable=False),
    sa.Column("language_id", sa.Text, nullable=False),
    sa.Column("question", sa.Text, nullable=False),
    sa.Column("answer", sa.Text, nullable=False),
    sa.Column("sequence", sa.SmallInteger, nullable=False, server_default="0"),
    sa.Column("created_date", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.UniqueConstraint("event_id", "language_id", "question", name="uq_event_faq_event_lang_question"),
)

collection = sa.Table(
    "collection", meta2,
    sa.Column("id", UUID(as_uuid=True), primary_key=True),
    sa.Column("user_id", UUID(as_uuid=True), nullable=True),
    sa.Column("title", sa.Text, nullable=False),
    sa.Column("description", sa.Text),
    sa.Column("is_thinko", sa.Boolean, server_default=sa.text("false")),
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
)

collection_seo_tag = sa.Table(
    "collection_seo_tag", meta2,
    sa.Column("id", UUID(as_uuid=True), primary_key=True),
    sa.Column("collection_id", UUID(as_uuid=True), sa.ForeignKey("collection.id", ondelete="CASCADE"), nullable=False),
    sa.Column("seo_tag_id", UUID(as_uuid=True), sa.ForeignKey("seo_tag.id", ondelete="CASCADE"), nullable=False),
    sa.Column("created_date", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.UniqueConstraint("collection_id", "seo_tag_id", name="uq_collection_seo_tag_collection_tag"),
)

# Assistant chunks table for RAG system
assistant_chunks = sa.Table(
    "assistant_chunks", meta2,
    sa.Column("id", UUID(as_uuid=True), primary_key=True),
    sa.Column("event_id", UUID(as_uuid=True), sa.ForeignKey("event.id", ondelete="CASCADE"), nullable=False),
    sa.Column("chunk_text", sa.Text, nullable=False),
    sa.Column("embedding", Vector(384), nullable=False),  # Requires pgvector extension
    sa.Column("chunk_type", sa.Text, nullable=False),  # 'title', 'description', 'content', etc.
    sa.Column("sequence", sa.Integer, nullable=False, server_default="0"),
    sa.Column("title", sa.Text),  # Event title for context
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.Index("idx_assistant_chunks_event", "event_id"),
)

# App config table for storing application configuration as key-value pairs
app_config = sa.Table(
    "app_config", meta2,
    sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
    sa.Column("config_key", sa.Text, nullable=False, unique=True),
    sa.Column("config_value", JSONB, nullable=False),
    sa.Column("description", sa.Text),
    sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.Index("idx_app_config_key", "config_key"),
)

users = sa.Table(
    "users", meta2,
    sa.Column("id", UUID(as_uuid=True), primary_key=True),
    sa.Column("uid", sa.Text),
)

user_devices = sa.Table(
    "user_devices", meta2,
    sa.Column("id", UUID(as_uuid=True), primary_key=True),
    sa.Column("user_id", UUID(as_uuid=True), nullable=False),
    sa.Column("device_id", sa.Text, nullable=False),
    sa.Column("fcm_token", sa.Text, nullable=False),
    sa.Column("platform", sa.Text, nullable=False),
    sa.Column("app_version", sa.Text, nullable=True),
    sa.Column("last_active_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
    sa.Column("createdAt", sa.DateTime(timezone=True), nullable=False),
    sa.Column("updatedAt", sa.DateTime(timezone=True), nullable=False),
)

# Tables are created by ensure_db2_schema() or Sequelize sync
# meta2.create_all(engine) is not called at import time to avoid connection errors

def ensure_seo_tag_enum():
    """Verify seo_tag_type enum exists with all required values.
    Core Service owns schema creation - this just verifies.
    Called automatically by sync_app_db.py before syncing.
    """
    required_values = [
        'tag', 'Category', 'Sub Category', 'Core Event', 'Associated Event', 'Entity', 'Place', 'Impact'
    ]
    
    try:
        with engine.connect() as conn:
            # Verify enum type exists
            enum_exists = conn.execute(sa.text("""
                SELECT EXISTS (
                    SELECT 1 FROM pg_type 
                    WHERE typname = 'enum_seo_tag_type'
                );
            """)).scalar()
            
            if not enum_exists:
                raise Exception(
                    "CRITICAL: enum_seo_tag_type does not exist. "
                    "Please start Core Service first to create schema."
                )
            
            # Get current enum values
            result = conn.execute(sa.text("""
                SELECT enumlabel 
                FROM pg_enum 
                WHERE enumtypid = 'enum_seo_tag_type'::regtype 
                ORDER BY enumsortorder;
            """))
            existing_values = {row[0] for row in result}
            
            # Verify all required values exist
            missing = set(required_values) - existing_values
            
            if missing:
                error_msg = (
                    f"CRITICAL: enum_seo_tag_type is missing values: {missing}. "
                    f"Please update Core Service SeoTag model with these values and restart."
                )
                print(f"[ERROR] {error_msg}")
                raise Exception(error_msg)
            else:
                print(f"[OK] enum_seo_tag_type verified ({len(required_values)} values)")
                
    except Exception as e:
        print(f"[ERROR] Enum verification failed: {e}")
        import traceback
        traceback.print_exc()
        raise

def _ensure_event_faq_language_id():
    """Ensure language_id column exists in event_faq table.
    This is called automatically during database initialization to handle schema migrations.
    Fully idempotent - safe to call multiple times.
    """
    try:
        with engine.begin() as conn:
            # Helper function to check if constraint exists
            # PostgreSQL unique constraints can exist as either:
            # 1. A constraint in pg_constraint (when created with ALTER TABLE ADD CONSTRAINT)
            # 2. A unique index in pg_indexes (when created with CREATE UNIQUE INDEX or SQLAlchemy UniqueConstraint)
            def constraint_exists(conn, constraint_name: str, table_name: str) -> bool:
                """Check if a constraint/index exists by checking both pg_constraint and pg_indexes."""
                # Check pg_constraint first
                exists_as_constraint = conn.execute(
                    sa.text(f"""
                        SELECT EXISTS (
                            SELECT 1 FROM pg_constraint 
                            WHERE conname = :constraint_name
                            AND conrelid = '{table_name}'::regclass
                        );
                    """),
                    {"constraint_name": constraint_name}
                ).scalar()
                
                # Check pg_indexes (unique constraints are often implemented as unique indexes)
                exists_as_index = conn.execute(
                    sa.text("""
                        SELECT EXISTS (
                            SELECT 1 FROM pg_indexes 
                            WHERE tablename = :table_name
                            AND indexname = :constraint_name
                        );
                    """),
                    {"table_name": table_name, "constraint_name": constraint_name}
                ).scalar()
                
                return exists_as_constraint or exists_as_index
            
            # Check if column exists
            column_exists = conn.execute(
                sa.text("""
                    SELECT EXISTS (
                        SELECT 1 FROM information_schema.columns 
                        WHERE table_schema = 'public'
                        AND table_name = 'event_faq' 
                        AND column_name = 'language_id'
                    );
                """)
            ).scalar()
            
            if not column_exists:
                # Column doesn't exist, add it
                print("[INFO] Adding language_id column to event_faq table...")
                
                # Step 1: Add column as nullable initially
                conn.execute(sa.text("ALTER TABLE event_faq ADD COLUMN language_id TEXT;"))
                
                # Step 2: Set default value to 'en' for existing FAQs
                conn.execute(sa.text("UPDATE event_faq SET language_id = 'en' WHERE language_id IS NULL;"))
                
                # Step 3: Make column NOT NULL
                conn.execute(sa.text("ALTER TABLE event_faq ALTER COLUMN language_id SET NOT NULL;"))
                
                print("[OK] Added language_id column to event_faq")
            
            # Always check and ensure constraint exists (idempotent)
            # The constraint is defined in the SQLAlchemy table definition, but may not exist
            # if the table was created before the constraint was added to the definition
            if not constraint_exists(conn, "uq_event_faq_event_lang_question", "event_faq"):
                print("[INFO] Adding unique constraint uq_event_faq_event_lang_question...")
                
                # Drop old constraint if it exists (for migration from old schema)
                conn.execute(
                    sa.text("ALTER TABLE event_faq DROP CONSTRAINT IF EXISTS uq_event_faq_event_question;")
                )
                
                # Add new constraint - use IF NOT EXISTS equivalent by checking first
                # Since we already checked, this should be safe, but wrap in try-except as final safeguard
                try:
                    conn.execute(
                        sa.text("""
                            ALTER TABLE event_faq 
                            ADD CONSTRAINT uq_event_faq_event_lang_question 
                            UNIQUE (event_id, language_id, question);
                        """)
                    )
                    print("[OK] Added unique constraint uq_event_faq_event_lang_question")
                except Exception as e:
                    # If constraint was created concurrently or check missed it, that's fine
                    error_msg = str(e).lower()
                    if "already exists" in error_msg or "duplicate" in error_msg:
                        print("[INFO] Constraint uq_event_faq_event_lang_question already exists (skipped)")
                    else:
                        raise
            else:
                print("[OK] Constraint uq_event_faq_event_lang_question already exists")
                
    except Exception as e:
        # Table might not exist yet - that's okay, Core Service will create it
        # Only log if it's not a "table does not exist" error
        error_msg = str(e).lower()
        if "does not exist" not in error_msg and "relation" not in error_msg:
            print(f"[WARN] Could not ensure event_faq.language_id: {e}")

def _ensure_event_seo_tag_columns():
    """Ensure role and linked_to_tag_id columns exist in event_seo_tag table.
    This is called automatically during database initialization to handle schema migrations.
    """
    try:
        with engine.begin() as conn:
            # Check if role column exists
            role_exists = conn.execute(
                sa.text("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = 'event_seo_tag' 
                    AND column_name = 'role';
                """)
            ).fetchone()
            
            if not role_exists:
                print("[INFO] Adding role column to event_seo_tag table...")
                # Create enum type if it doesn't exist
                conn.execute(
                    sa.text("""
                        DO $$ BEGIN
                            CREATE TYPE enum_event_seo_tag_role AS ENUM ('core', 'contextual');
                        EXCEPTION
                            WHEN duplicate_object THEN null;
                        END $$;
                    """)
                )
                # Add role column with default
                conn.execute(
                    sa.text("""
                        ALTER TABLE event_seo_tag 
                        ADD COLUMN role enum_event_seo_tag_role NOT NULL DEFAULT 'contextual';
                    """)
                )
                print("[OK] Added role column to event_seo_tag")
            
            # Check if linked_to_tag_id column exists
            linked_exists = conn.execute(
                sa.text("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = 'event_seo_tag' 
                    AND column_name = 'linked_to_tag_id';
                """)
            ).fetchone()
            
            if not linked_exists:
                print("[INFO] Adding linked_to_tag_id column to event_seo_tag table...")
                conn.execute(
                    sa.text("""
                        ALTER TABLE event_seo_tag 
                        ADD COLUMN linked_to_tag_id UUID 
                        REFERENCES seo_tag(id) ON DELETE SET NULL;
                    """)
                )
                print("[OK] Added linked_to_tag_id column to event_seo_tag")
    except Exception as e:
        print(f"[WARN] Could not ensure event_seo_tag columns: {e}")

def _ensure_seo_tag_relation_table():
    """Ensure seo_tag_relation table exists.
    This is called automatically during database initialization to handle schema migrations.
    """
    try:
        with engine.begin() as conn:
            # Check if table exists
            table_exists = conn.execute(
                sa.text("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_schema = 'public' 
                        AND table_name = 'seo_tag_relation'
                    );
                """)
            ).scalar()
            
            if not table_exists:
                print("[INFO] Creating seo_tag_relation table...")
                # Create table
                conn.execute(
                    sa.text("""
                        CREATE TABLE seo_tag_relation (
                            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                            parent_tag_id UUID NOT NULL REFERENCES seo_tag(id) ON DELETE CASCADE,
                            child_tag_id UUID NOT NULL REFERENCES seo_tag(id) ON DELETE CASCADE,
                            created_date TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                            CONSTRAINT uq_seo_tag_relation_unique UNIQUE (parent_tag_id, child_tag_id)
                        );
                    """)
                )
                # Create indexes
                conn.execute(
                    sa.text("""
                        CREATE INDEX idx_seo_tag_relation_parent ON seo_tag_relation(parent_tag_id);
                        CREATE INDEX idx_seo_tag_relation_child ON seo_tag_relation(child_tag_id);
                    """)
                )
                print("[OK] Created seo_tag_relation table")
    except Exception as e:
        print(f"[WARN] Could not ensure seo_tag_relation table: {e}")

def _ensure_temporal_indexes_db2():
    """Ensure temporal indexes exist on DB2 for optimal temporal query performance."""
    try:
        with engine.begin() as conn:
            # Index on event.time_stamp for temporal filtering of events
            conn.execute(sa.text("""
                CREATE INDEX IF NOT EXISTS idx_event_time_stamp
                ON event(time_stamp)
                WHERE time_stamp IS NOT NULL;
            """))

            # Composite index for event filtering with time_stamp
            conn.execute(sa.text("""
                CREATE INDEX IF NOT EXISTS idx_event_time_stamp_id
                ON event(time_stamp DESC, id)
                WHERE time_stamp IS NOT NULL;
            """))


            print("✓ DB2 temporal indexes verified/created")
    except Exception as e:
        # Silently fail - indexes might already exist or table might not be ready
        # This is expected during initial setup
        print(f"[INFO] DB2 temporal indexes: {e}")

def ensure_db2_schema():
    """Verify DB2 schema exists and is accessible.
    Core Service owns schema creation - Python backend just verifies.
    Called automatically by sync_app_db.py before syncing.
    """
    try:
        print("[INFO] Verifying DB2 schema (Core Service owns schema creation)...")

        # Ensure event_faq has language_id column (for backward compatibility)
        _ensure_event_faq_language_id()

        # Ensure event_seo_tag has role and linked_to_tag_id columns
        _ensure_event_seo_tag_columns()

        # Ensure seo_tag_relation table exists
        _ensure_seo_tag_relation_table()

        # Ensure temporal indexes exist for optimal performance
        _ensure_temporal_indexes_db2()
        
        with engine.connect() as conn:
            # Verify critical tables exist
            critical_tables = [
                'seo_tag', 'event', 'localized_event_data', 'event_seo_tag',
                'event_faq', 'source', 'collection', 'collection_seo_tag',
                'assistant_chunks', 'event_so_far', 'event_analysis',
                'localized_event_so_far', 'localized_event_analysis',
                'language', 'logos', 'category', 'seo_tag_relation', 'app_config'
            ]
            
            missing_tables = []
            for table_name in critical_tables:
                exists = conn.execute(sa.text(f"""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_schema = 'public' 
                        AND table_name = '{table_name}'
                    );
                """)).scalar()
                
                if not exists:
                    missing_tables.append(table_name)
            
            if missing_tables:
                raise Exception(
                    f"CRITICAL: Missing tables in DB2: {missing_tables}. "
                    f"Please start Core Service first to create schema."
                )
            
            print(f"[OK] All {len(critical_tables)} critical tables verified")
            
            # Verify unique constraint/index exists on seo_tag (name, type)
            constraint_check = conn.execute(sa.text("""
                SELECT EXISTS (
                    SELECT 1 FROM pg_indexes 
                    WHERE tablename = 'seo_tag' 
                    AND schemaname = 'public'
                    AND (
                        indexname = 'uq_seo_tag_name_type'
                        OR (indexdef LIKE '%UNIQUE%' AND indexdef LIKE '%name%' AND indexdef LIKE '%type%')
                    )
                );
            """)).scalar()
            
            if not constraint_check:
                print("[WARN] Unique constraint on seo_tag (name, type) not found.")
                print("[WARN] This may cause duplicate tag issues.")
                print("[WARN] Please ensure Core Service SeoTag model has indexes defined.")
            else:
                print("[OK] seo_tag unique constraint/index verified")
            
            # Verify pgvector extension exists (needed for assistant_chunks)
            vector_exists = conn.execute(sa.text("""
                SELECT EXISTS (
                    SELECT 1 FROM pg_extension 
                    WHERE extname = 'vector'
                );
            """)).scalar()
            
            if not vector_exists:
                print("[WARN] pgvector extension not installed. assistant_chunks may not work.")
            else:
                print("[OK] pgvector extension verified")
        
        print("[OK] DB2 schema verification complete")
        
    except Exception as e:
        import traceback
        print(f"[ERROR] DB2 schema verification failed: {e}")
        traceback.print_exc()
        raise
