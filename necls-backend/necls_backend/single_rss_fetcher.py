from __future__ import annotations

from typing import Any, Dict, Iterable, List, Sequence

import sqlalchemy as sa
import numpy as np
import feedparser
import re
import html
from .clustering import StoryClusterer
from .extractor import ArticleExtractor, FeedCrawler
from .db import engine, articles
from datetime import datetime
from zoneinfo import ZoneInfo          # Python ≥3.9
from dateutil import parser            # pip install python-dateutil
import random
from collections import defaultdict

LOCAL_TZ = ZoneInfo("Asia/Kolkata")    # adjust if you prefer a different zone

def cos_sim(a: np.ndarray, b: np.ndarray) -> float:
    """Compute cosine similarity between two vectors."""
    a = np.asarray(a)
    b = np.asarray(b)
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))

class RssFetcher:
    """Fetch and store articles from a single RSS feed."""

    def __init__(self, crawler: FeedCrawler | None = None, *, model_id: str | None = None):
        self.crawler = crawler or FeedCrawler([])
        self.extractor = self.crawler.xtr
        self.model = StoryClusterer(model_id).model

    # -------------------------- helpers -------------------------
    def _fetch_existing(self, urls: Sequence[str]) -> Dict[str, Dict[str, Any]]:
        """Return mapping of URL -> article row for those already stored."""
        if not urls:
            return {}
        with engine.connect() as conn:
            rows = conn.execute(sa.select(articles).where(articles.c.url.in_(list(urls))))
            return {row.url: dict(row._mapping) for row in rows}

    def _to_datetime(self, value):
        """
        Convert `value` to a timezone-aware datetime in LOCAL_TZ.
        """
        if isinstance(value, datetime):
            dt = value
        else:  # assume it's a str-like thing
            dt = parser.parse(value)

        # Make sure tzinfo is set and harmonised
        dt = dt.astimezone(LOCAL_TZ) if dt.tzinfo else dt.replace(tzinfo=LOCAL_TZ)
        return dt

    def sample_one_per_day(self, results, seed=None):
        """
        results: iterable of dicts with a 'date_publish' key (or adjust accessor)
        seed   : optional, for reproducibility

        Returns a list containing exactly one randomly-selected row per distinct day.
        """
        if seed is not None:
            random.seed(seed)

        by_day = defaultdict(list)

        for row in results:
            try:
                dt = self._to_datetime(row["date_publish"])
                row['date_publish_iso'] = dt.date().isoformat()
                by_day[dt.date()].append(row)  # date() strips the time-of-day
            except Exception as e:
                print(f"[ERROR] Failed to parse date for article: {e}")
                continue

        # One random row from each day’s bucket
        return [random.choice(rows) for rows in by_day.values()]

    def html_to_text(self, raw_html: str) -> str:
        tar_re = re.compile(r"<[^>]+>")
        ws_re = re.compile(r"\s+")
        no_tags = tar_re.sub("", raw_html)
        unescaped = html.unescape(no_tags)
        clean = ws_re.sub(" ", unescaped).strip()
        return clean

    # -------------------------- main API -----------------------
    def fetch(self, rss_url: str, title: str, *, threshold: float = 0.55) -> List[Dict[str, Any]]:
        """Return articles from ``rss_url`` semantically similar to ``title``."""
        feed = feedparser.parse(self.extractor.fetch(rss_url).content)
        top_entries = [e for e in feed.entries[0:50]]
        query_vec = next(self.model.embed([title]))
        entry_texts = [(e.get("title", "") + " " + self.html_to_text(e.get("summary", ""))) for e in top_entries]
        entry_vecs = list(self.model.embed(entry_texts))
        results: List[Dict[str, Any]] = []
        to_store: List[Dict[str, Any]] = []
        urls: List[str] = []
        resolved: List[tuple[str, Any, Any]] = []
        for entry, vec in zip(top_entries, entry_vecs):
            sim = cos_sim(query_vec, vec)
            if sim < threshold:
                continue
            url, resp = self.extractor.resolve_link(entry.get("link"))
            if not url:
                continue
            urls.append(url)
            resolved.append((url, resp, entry))
        existing = self._fetch_existing(urls)

        for url, resp, entry in resolved:
            if url in existing:
                results.append(existing[url])
                continue
            art = self.extractor.extract(url, entry, resp)
            if art:
                art["is_gnews"] = True
                results.append(art)
                to_store.append(art)

        if to_store:
            self.crawler.bulk_store(to_store)
        return results