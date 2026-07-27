from __future__ import annotations

"""Synchronize processed clusters from DB1 into the application DB (DB2)."""

import sqlalchemy as sa

from necls_backend.db import engine as db1_engine, generations, db2_links
from necls_backend.app_db import engine as db2_engine, ensure_db2_schema, ensure_seo_tag_enum
from necls_backend.save_to_app_db import export_cluster_to_db2


def _clusters_to_sync() -> list[str]:
    """Return cluster IDs that are new or updated since last sync."""
    g = generations.alias("g")
    latest = (
        sa.select(g.c.cluster_id, sa.func.max(g.c.created_at).label("last_gen"))
        .where(g.c.artifact == "summary")
        .group_by(g.c.cluster_id)
        .subquery()
    )

    l = db2_links.alias("l")
    stmt = (
        sa.select(latest.c.cluster_id)
        .outerjoin(l, l.c.cluster_id == latest.c.cluster_id)
        .where(sa.or_(l.c.cluster_id == None, l.c.last_synced_at < latest.c.last_gen))
    )
    with db1_engine.connect() as conn:
        return [str(row) for row in conn.execute(stmt).scalars().all()]


def main() -> None:
    """Sync data from DB1 (processing) to DB2 (application).
    
    IMPORTANT: Core Service must be started FIRST to create DB2 schema.
    Python backend verifies schema exists, then syncs data.
    """
    print("=" * 70)
    print("[INFO] Python Backend Data Sync - Starting")
    print("=" * 70)
    
    db2_engine.dispose()  # Refresh connection pool
    
    # Verify schema exists (Core Service creates it)
    try:
        ensure_db2_schema()
    except Exception as exc:
        print(f"[ERROR] DB2 schema verification failed: {exc}")
        print("[ERROR] Please ensure Core Service is running and has created the schema")
        print("[ERROR] Startup order: 1) Core Service  2) Python Backend")
        raise

    # Verify enum exists (Core Service creates it)
    try:
        ensure_seo_tag_enum()
    except Exception as exc:
        print(f"[ERROR] SEO tag enum verification failed: {exc}")
        raise

    # Proceed with data sync
    cluster_ids = _clusters_to_sync()
    if not cluster_ids:
        return

    for cid in cluster_ids:
        try:
            export_cluster_to_db2(cid, db1_engine, db2_engine)
        except Exception as exc:  # pragma: no cover - runtime/DB failure
            print(f"[ERROR] Failed to sync {cid}: {exc}")
    
    print("=" * 70)
    print("[INFO] Data sync complete")
    print("=" * 70)


if __name__ == "__main__":
    main()