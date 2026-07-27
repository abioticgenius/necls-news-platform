from __future__ import annotations

"""Delete rejected clusters older than N days (default: 10).

Keeps only clusters rejected within the last N days.
Uses COALESCE(rejected_at, updated_at) as the rejection timestamp so that
legacy rows without a rejected_at value are still covered.

Tables deleted in order (to respect FK constraints without CASCADE):
  1. story_members  (no CASCADE on cluster_id FK)
  2. meta_members   (no CASCADE on cluster_id FK)
  3. story_clusters (CASCADE auto-removes: db2_links, generations → sources /
                     summary_localized / slides → slide_localized, llm_runs)

Usage:
  python -m scripts.purge_old_rejected_clusters            # deletes (keeps last 10 days)
  python -m scripts.purge_old_rejected_clusters --dry-run  # preview only, no changes
  python -m scripts.purge_old_rejected_clusters --days 30  # keep last 30 days instead
"""

import argparse
import sys
from datetime import datetime, timedelta, timezone

import sqlalchemy as sa

from necls_backend.db import (
    engine,
    story_clusters,
    story_members,
    meta_members,
)

REJECTED_STATUSES = ("editorial_rejected", "manual_rejected")


def _cutoff(days: int) -> datetime:
    return datetime.now(tz=timezone.utc) - timedelta(days=days)


def _find_old_rejected(conn: sa.Connection, cutoff: datetime) -> list:
    """Return cluster_ids older than cutoff with a rejected status."""
    rows = conn.execute(
        sa.select(story_clusters.c.cluster_id, story_clusters.c.rejected_at, story_clusters.c.updated_at)
        .where(story_clusters.c.filter_status.in_(REJECTED_STATUSES))
        .where(
            sa.func.coalesce(story_clusters.c.rejected_at, story_clusters.c.updated_at) < cutoff
        )
    ).fetchall()
    return rows


def purge(days: int = 10, execute: bool = False) -> None:
    cutoff = _cutoff(days)
    print(f"Cutoff: {cutoff.isoformat()}  (keeping last {days} days)")

    with engine.begin() as conn:
        rows = _find_old_rejected(conn, cutoff)

        if not rows:
            print("No old rejected clusters found. Nothing to do.")
            return

        cluster_ids = [r.cluster_id for r in rows]
        print(f"Found {len(cluster_ids)} rejected cluster(s) older than {days} days.")

        if not execute:
            print("\n[DRY-RUN] Would delete the following cluster IDs:")
            for cid in cluster_ids:
                print(f"  {cid}")
            print("\nRe-run with --execute to perform the actual deletion.")
            return

        # 1. story_members
        sm_result = conn.execute(
            sa.delete(story_members).where(story_members.c.cluster_id.in_(cluster_ids))
        )
        print(f"  Deleted {sm_result.rowcount} story_members row(s).")

        # 2. meta_members
        mm_result = conn.execute(
            sa.delete(meta_members).where(meta_members.c.cluster_id.in_(cluster_ids))
        )
        print(f"  Deleted {mm_result.rowcount} meta_members row(s).")

        # 3. story_clusters (CASCADE removes db2_links, generations and all descendants)
        sc_result = conn.execute(
            sa.delete(story_clusters).where(story_clusters.c.cluster_id.in_(cluster_ids))
        )
        print(f"  Deleted {sc_result.rowcount} story_cluster(s) (CASCADE cleaned up related rows).")

    print("Done.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Purge rejected clusters older than N days."
    )
    parser.add_argument(
        "--days",
        type=int,
        default=10,
        help="Keep rejected clusters from the last N days (default: 10).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Preview what would be deleted without making any changes.",
    )
    args = parser.parse_args()

    if args.dry_run:
        print("[DRY-RUN MODE] No changes will be made.")

    purge(days=args.days, execute=not args.dry_run)


if __name__ == "__main__":
    main()
