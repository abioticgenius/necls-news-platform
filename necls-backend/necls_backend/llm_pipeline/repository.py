from __future__ import annotations

import os
import pandas as pd
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert as pg_insert
from datetime import datetime, timedelta, timezone

from ..db import (
    engine,
    articles,
    story_clusters,
    story_members,
    meta_members, db2_links, llm_runs,
)


class ArticleRepository:
    """Data-access layer for article and cluster information."""

    def __init__(self, engine=engine):
        self.engine = engine

    def get_today_clusters(self, date: str, recency_hours: float = None, min_size: int = None) -> pd.DataFrame:
        """Get clusters that haven't been processed yet (not in db2_links).
        
        Args:
            date: Date string (kept for backward compatibility, but not used if recency_hours is set)
            recency_hours: Optional. If set, only gets clusters updated in last N hours.
                          If None, reads from EXTRACT_HOURS_RECENCY env var.
                          If env var is not set, falls back to date-based filtering.
            min_size: Optional. Minimum cluster size to include. If None, reads from 
                      MIN_CLUSTER_SIZE env var (defaults to 3).
        """
        if recency_hours is None:
            # Try to read from environment variable
            env_recency = os.getenv("EXTRACT_HOURS_RECENCY")
            if env_recency:
                try:
                    recency_hours = float(env_recency)
                except ValueError:
                    recency_hours = None
        
        # Get min_size from parameter, env var, or default to 3
        if min_size is None:
            env_min_size = os.getenv("MIN_CLUSTER_SIZE")
            if env_min_size:
                try:
                    min_size = int(env_min_size)
                except ValueError:
                    min_size = 3  # Default fallback
            else:
                min_size = 3  # Default
        
        stmt = (
            sa.select(
                story_clusters.c.cluster_id,
                story_clusters.c.first_date,
                story_clusters.c.last_date,
                story_clusters.c.size,
                story_clusters.c.headline,
                story_clusters.c.filter_status,
                sa.func.row_number()
                .over(
                    partition_by=story_clusters.c.size,
                    order_by=story_clusters.c.last_date,
                )
                .label("rn"),
            )
            .where(story_clusters.c.size >= min_size)
            # Only get clusters that haven't been processed yet (not in db2_links)
            .where(
                ~story_clusters.c.cluster_id.in_(
                    sa.select(db2_links.c.cluster_id)
                )
            )
        )
        
        # Optionally add recency filter; always include manual_approved regardless of date
        if recency_hours:
            cutoff = datetime.now(timezone.utc) - timedelta(hours=recency_hours)
            stmt = stmt.where(
                sa.or_(
                    story_clusters.c.last_date >= cutoff,
                    story_clusters.c.filter_status == "manual_approved",
                )
            )
        else:
            stmt = stmt.where(
                sa.or_(
                    sa.func.date(story_clusters.c.last_date) == sa.bindparam("date"),
                    story_clusters.c.filter_status == "manual_approved",
                )
            )
        
        with self.engine.connect() as conn:
            params = {} if recency_hours else {"date": date}
            return pd.read_sql(stmt, conn, params=params)

    def get_meta_clusters(self, cluster_id: str) -> pd.DataFrame:
        meta_ids = sa.select(meta_members.c.meta_id).where(
            meta_members.c.cluster_id == sa.bindparam("cluster_id")
        )
        related_clusters = (
            sa.select(meta_members.c.cluster_id)
            .where(meta_members.c.meta_id.in_(meta_ids))
            .where(meta_members.c.cluster_id != sa.bindparam("cluster_id"))
        )
        sm = story_members.alias("sm")
        a = articles.alias("a")
        subq = (
            sa.select(
                sm.c.cluster_id,
                a.c.id,
                a.c.url,
                a.c.text,
                a.c.title,
                a.c.date_publish,
                sa.func.row_number()
                .over(
                    partition_by=(sm.c.cluster_id, sa.func.date(a.c.date_publish)),
                    order_by=a.c.date_publish,
                )
                .label("rn"),
            )
            .join(a, a.c.id == sm.c.article_id)
            .where(sm.c.cluster_id.in_(related_clusters))
        ).subquery()
        stmt = sa.select(subq).where(subq.c.rn == 1)
        with self.engine.connect() as conn:
            return pd.read_sql(stmt, conn, params={"cluster_id": cluster_id})

    def get_articles(self, cluster_id: str) -> pd.DataFrame:
        sm = story_members
        a = articles
        stmt = (
            sa.select(sm.c.cluster_id, *a.c)
            .join(a, a.c.id == sm.c.article_id)
            .where(sm.c.cluster_id == sa.bindparam("cluster_id"))
            .where(a.c.language == "en")
        )
        with self.engine.connect() as conn:
            df = pd.read_sql(stmt, conn, params={"cluster_id": cluster_id})
        df["date_publish"] = df["date_publish"].astype(str)
        return df

    def has_llm_output(self, cluster_id: str) -> bool:
        """Return True if LLM output already exists for the cluster."""
        stmt = (
            sa.select(sa.func.count())
            .select_from(llm_runs)
            .where(llm_runs.c.cluster_id == sa.bindparam("cluster_id"))
        )
        with self.engine.connect() as conn:
            return conn.execute(stmt, {"cluster_id": cluster_id}).scalar() > 0

