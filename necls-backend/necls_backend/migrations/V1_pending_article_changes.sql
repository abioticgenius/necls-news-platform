-- Create table
CREATE TABLE IF NOT EXISTS pending_article_changes (
    id                  SERIAL PRIMARY KEY,
    created_at          TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    created_by_id       INTEGER NOT NULL REFERENCES review_users(id),
    created_by_username VARCHAR(255) NOT NULL,
    change_type         VARCHAR(50) NOT NULL,
    target_event_id     UUID NOT NULL,
    target_title        TEXT,
    summary             TEXT,
    payload             JSONB NOT NULL,
    status              VARCHAR(20) NOT NULL DEFAULT 'pending',
    reviewed_at         TIMESTAMP WITH TIME ZONE,
    reviewed_by_id      INTEGER REFERENCES review_users(id)
);

-- Index for listing pending changes
CREATE INDEX IF NOT EXISTS idx_pending_article_changes_status
    ON pending_article_changes (status);

-- Index for ordering by submission time
CREATE INDEX IF NOT EXISTS idx_pending_article_changes_created_at
    ON pending_article_changes (created_at DESC);