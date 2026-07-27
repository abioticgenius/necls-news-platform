from __future__ import annotations

import re
import sys
import requests
import urllib.parse
from urllib.parse import urljoin, urlparse, urlunparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import  json
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
import time
import sqlalchemy as sa
from typing import Any, Dict, List, Sequence, Set, Iterable
from collections import OrderedDict
import feedparser, schedule
from dateutil import parser as dateparser
from .config import settings
from .constants import REUTERS_HEADERS
from .crawler import ArticleExtractor, jsonify
from bs4 import BeautifulSoup
from .db import engine, articles, pg_insert

# Source timezone mapping
SOURCE_TIMEZONES: Dict[str, timezone | ZoneInfo] = {
    "Reuters": timezone.utc,
    "IANS": timezone.utc,
    "BusinessStandards": ZoneInfo("Asia/Kolkata"),  # IST
    "HindustanTimes": ZoneInfo("Asia/Kolkata"),
    "EconomicTimes": ZoneInfo("Asia/Kolkata"),
    "NDTV": ZoneInfo("Asia/Kolkata"),
    "Scroll": ZoneInfo("Asia/Kolkata"),
    "PrintNews": ZoneInfo("Asia/Kolkata"),
    "Tribune": ZoneInfo("Asia/Kolkata"),
    "LiveMintG": timezone.utc,  # GMT = UTC
    "UNIIndia": timezone.utc,  # GMT = UTC
    "TimesOfIndia": ZoneInfo("Asia/Kolkata"),
    "TheHindu": ZoneInfo("Asia/Kolkata"),
    "APNews": ZoneInfo("America/New_York"),  # EST
    "PTINews": ZoneInfo("Asia/Kolkata"),  # Assuming PTI is IST
    "IndianExpress": ZoneInfo("Asia/Kolkata"),  # Assuming IST
}

# Domain timezone mapping for fallback
DOMAIN_TIMEZONES: Dict[str, timezone | ZoneInfo] = {
    "reuters.com": timezone.utc,
    "ianslive.in": timezone.utc,
    "business-standard.com": ZoneInfo("Asia/Kolkata"),
    "hindustantimes.com": ZoneInfo("Asia/Kolkata"),
    "economictimes.indiatimes.com": ZoneInfo("Asia/Kolkata"),
    "ndtv.com": ZoneInfo("Asia/Kolkata"),
    "scroll.in": ZoneInfo("Asia/Kolkata"),
    "theprint.in": ZoneInfo("Asia/Kolkata"),
    "tribuneindia.com": ZoneInfo("Asia/Kolkata"),
    "livemint.com": timezone.utc,
    "uniindia.com": timezone.utc,
    "timesofindia.indiatimes.com": ZoneInfo("Asia/Kolkata"),
    "thehindu.com": ZoneInfo("Asia/Kolkata"),
    "apnews.com": ZoneInfo("America/New_York"),
    "ptinews.com": ZoneInfo("Asia/Kolkata"),
    "indianexpress.com": ZoneInfo("Asia/Kolkata"),
}

def _get_source_timezone(source_name: str | None, source_domain: str | None) -> timezone | ZoneInfo:
    """Get timezone for a source based on name or domain."""
    if source_name and source_name in SOURCE_TIMEZONES:
        return SOURCE_TIMEZONES[source_name]
    
    if source_domain:
        # Try to match domain
        domain_lower = source_domain.lower()
        for domain, tz_info in DOMAIN_TIMEZONES.items():
            if domain in domain_lower:
                return tz_info
    
    # Default to IST for Indian sources (most common in this setup)
    return ZoneInfo("Asia/Kolkata")

def _normalize_date_to_utc(date_obj, source_name: str | None = None, source_domain: str | None = None) -> datetime | None:
    """Normalize a date to UTC, handling naive datetimes based on source timezone."""
    if date_obj is None:
        return None
    
    if isinstance(date_obj, str):
        try:
            date_obj = dateparser.parse(date_obj)
        except Exception:
            return None
    
    if not isinstance(date_obj, datetime):
        return None
    
    # If already timezone-aware, convert to UTC
    if date_obj.tzinfo is not None:
        return date_obj.astimezone(timezone.utc)
    
    # If naive, assume it's in the source's timezone
    source_tz = _get_source_timezone(source_name, source_domain)
    return date_obj.replace(tzinfo=source_tz).astimezone(timezone.utc)


def _rss_date_string_to_utc(date_str: str | None) -> datetime | None:
    """Parse RSS/Atom date string to UTC. Treats naive parsed result as UTC (RSS often sends GMT without TZ)."""
    if not date_str:
        return None
    try:
        dt = dateparser.parse(date_str)
    except Exception:
        return None
    if not isinstance(dt, datetime):
        return None
    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc)
    return dt.replace(tzinfo=timezone.utc)

def normalize_url(url: str) -> str:
    """
    Normalize URL to prevent duplicates and fix redirect loops.
    
    Normalizes URLs by:
    - Lowercasing scheme and netloc (hostname)
    - Collapsing consecutive slashes in path (fixes redirect loops)
    - Removing trailing slashes from path
    - Removing query parameters (tracking params don't affect content for news)
    - Removing fragments (client-side only)
    
    This ensures URLs that differ only by trailing slashes, query params,
    or fragments are treated as the same URL.
    """
    if not url or not url.strip():
        return url
    parsed = urlparse(url.strip())
    # Collapse consecutive slashes in path (e.g., /news//article -> /news/article)
    path = parsed.path
    while '//' in path:
        path = path.replace('//', '/')
    path = path.rstrip('/')
    # Normalize: lowercase scheme/netloc, strip trailing slash, remove query/fragment
    normalized = urlunparse((
        parsed.scheme.lower(),
        parsed.netloc.lower(),
        path,
        '',  # params (rarely used)
        '',  # query - stripped (tracking params don't affect content for news)
        ''   # fragment - always stripped (client-side only)
    ))
    return normalized

class LRUSet:
    """Minimal fixed-size set with LRU eviction."""
    def __init__(self, capacity: int = 50000):
        self.capacity = capacity
        self._data: OrderedDict[str, None] = OrderedDict()

    def add(self, item: str) -> None:
        if item in self._data:
            self._data.move_to_end(item)
        else:
            self._data[item] = None
            if len(self._data) > self.capacity:
                self._data.popitem(last=False)

    def __contains__(self, item: str) -> bool:
        return item in self._data

# ---------------------------------------------------------------------------
class FeedCrawler:
    """High‑level orchestration: iterate sources, extract & bulk‑insert."""

    def __init__(self, sources_cfg: Sequence[Dict[str, Any]], interval_min: int | None = None, recency_hours: float | None = None):
        self.sources = self._expand_dynamic_sitemaps(sources_cfg)
        self.interval = interval_min or settings.crawl_interval_min
        self.recency_hours = recency_hours  # Filter articles by publish date recency
        self.xtr = ArticleExtractor()
        # self.seen_file =  settings.data_dir / "seen_urls.json"
        self.recent_seen = LRUSet(50_000)
        # self.seen: Set[str] = self._load_seen()

    @staticmethod
    def _expand_dynamic_sitemaps(sources_cfg: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Expand placeholders in sitemap URLs.

        Any sitemap URL containing ``{date}`` is expanded into three URLs for
        today and the previous two days using the ``YYYY-MM-DD`` format.
        """
        today = datetime.now(timezone.utc).date()
        expanded_sources: List[Dict[str, Any]] = []
        for src in sources_cfg:
            new_src = dict(src)
            expanded_sitemaps: List[str] = []
            for url in src.get("sitemaps", []):
                if "{date}" in url:
                    for offset in range(1):
                        day = today - timedelta(days=offset)
                        expanded_sitemaps.append(url.replace("{date}", day.strftime("%Y-%m-%d")))
                else:
                    expanded_sitemaps.append(url)
            new_src["sitemaps"] = expanded_sitemaps
            expanded_sources.append(new_src)
        return expanded_sources

    def _is_seen(self, url: str) -> bool:
        url = normalize_url(url)
        if url in self.recent_seen:
            return True
        with engine.connect() as conn:
            if self.recency_hours is None or self.recency_hours == 0:
                # No recency filter: any existing URL is considered seen
                found = conn.execute(
                    sa.select(articles.c.url).where(articles.c.url == url)
                ).first()
            else:
                # With recency filter: only consider seen if within recency window
                cutoff = datetime.now(timezone.utc) - timedelta(hours=self.recency_hours)
                found = conn.execute(
                    sa.select(articles.c.url).where(
                        sa.and_(
                            articles.c.url == url,
                            sa.or_(
                                articles.c.date_publish.is_(None),  # Include articles without date
                                articles.c.date_publish >= cutoff   # Or within recency window
                            )
                        )
                    )
                ).first()
        if found:
            self.recent_seen.add(url)
            return True
        return False

    def _mark_seen(self, urls: Iterable[str]):
        for u in urls:
            self.recent_seen.add(u)

    def _filter_unseen_urls(self, urls: Iterable[str]) -> set[str]:
        """Return URLs not seen before, checking the DB in bulk.
        When recency_hours is set, only considers URLs as 'seen' if they exist
        AND are within the recency window."""
        unique = []
        dedup = set()
        for u in urls:
            if not u or u in self.recent_seen or u in dedup:
                continue
            unique.append(u)
            dedup.add(u)
        if not unique:
            return set()
        
        with engine.connect() as conn:
            if self.recency_hours is None or self.recency_hours == 0:
                # No recency filter: any existing URL is considered seen
                rows = conn.execute(
                    sa.select(articles.c.url).where(articles.c.url.in_(unique))
                ).fetchall()
                found = {r[0] for r in rows}
            else:
                # With recency filter: only consider seen if within recency window
                cutoff = datetime.now(timezone.utc) - timedelta(hours=self.recency_hours)
                rows = conn.execute(
                    sa.select(articles.c.url).where(
                        sa.and_(
                            articles.c.url.in_(unique),
                            sa.or_(
                                articles.c.date_publish.is_(None),  # Include articles without date
                                articles.c.date_publish >= cutoff   # Or within recency window
                            )
                        )
                    )
                ).fetchall()
                found = {r[0] for r in rows}
        
        for u in found:
            self.recent_seen.add(u)
        return set(u for u in unique if u not in found)

    def _is_recent_enough(self, date_publish, source_name: str | None = None, source_domain: str | None = None) -> bool:
        """Check if article is within the recency window."""
        if self.recency_hours is None or self.recency_hours == 0:
            return True  # No filtering if not set or 0 (0 means "no filter")
        
        if date_publish is None:
            return True  # Include articles without date (let clustering decide)
        
        # Normalize date to UTC using source timezone
        date_publish = _normalize_date_to_utc(date_publish, source_name, source_domain)
        
        if date_publish is None:
            return True
        
        # Calculate cutoff time
        cutoff = datetime.now(timezone.utc) - timedelta(hours=self.recency_hours)
        
        return date_publish >= cutoff

    # ------------------- seen‑set persistence -------------------
    def _load_seen(self) -> Set[str]:
        if self.seen_file.exists():
            try:
                return set(json.loads(self.seen_file.read_text()))
            except json.JSONDecodeError as e:
                print(f"[ERROR] Failed to load seen URLs file: {e}")
        return set()

    def _save_seen(self):
        self.seen_file.write_text(json.dumps(sorted(self.seen), ensure_ascii=False, indent=2))

    # ------------------- DB bulk insert -------------------------
    def bulk_store(self, batch: List[Dict[str, Any]], feed_info=None, source_name: str | None = None):
        if not batch:
            return

        # Filter by recency before storing
        filtered_batch = []
        rows = []
        filtered_out = 0

        for art in batch:
            art_copy = art.copy()
            dp = art_copy.get("date_publish")
            source_domain = art_copy.get("source_domain")

            # Normalize date to UTC using source timezone (handles naive datetimes correctly)
            dp_normalized = _normalize_date_to_utc(dp, source_name, source_domain)

            # Check if article is recent enough (normalization happens inside _is_recent_enough)
            if self._is_recent_enough(dp, source_name, source_domain):
                filtered_batch.append(art_copy)
                rows.append({
                    "id":            art_copy["id"],
                    "url":           art_copy["url"],
                    "title":         art_copy.get("title"),
                    "authors":       art_copy.get("authors"),
                    "date_publish":  dp_normalized,  # Normalized to UTC
                    "description":   art_copy.get("description"),
                    "image_url":     art_copy.get("image_url"),
                    "language":      art_copy.get("language"),
                    "source_domain": art_copy.get("source_domain"),
                    "text":          art_copy.get("text"),
                    "fetched_at":    art_copy["fetched_at"],
                    "feed_data":     art_copy.get("feed_data"),
                    "is_gnews":     bool(art_copy.get("is_gnews", False)),
                })
            else:
                filtered_out += 1
                if source_name and "espn" in source_name.lower():
                    print(f"[DEBUG] {source_name}: Filtered by recency: {art_copy.get('title', 'N/A')[:50]} (date: {dp})")

        if filtered_out > 0:
            print(f"[INFO] {source_name}: Filtered out {filtered_out} articles by recency (kept {len(rows)})")

        if not rows:
            return

        with engine.begin() as conn:
            conn.execute(
                pg_insert(articles)
                .values(rows)
                .on_conflict_do_nothing(index_elements=["id"])
            )

    def extract_from_source(self, src, verbose: bool = False):
        disk_batch = []
        source_name = src.get("name")

        rss_feeds = list(src.get("rss", []))
        sitemaps = list(src.get("sitemaps", []))
        reuters_feeds = list(src.get("reuters", []))

        if "robots" in src:
            sitemaps += self.xtr._discover_sitemaps(src["robots"])

        for r_section in reuters_feeds:
            try:
                r_articles = self.fetch_all_reuters(section=r_section)
            except Exception as e:
                print(f"[ERROR] Reuters feed {r_section} failed: {e}")
                continue
            r_article_batch: List[Dict[str, Any]] = []

            urls = ['https://www.reuters.com' + e['canonical_url'] for e in r_articles]
            allowed = self._filter_unseen_urls(urls)

            tasks = [(link, entry) for entry in r_articles
                if (link := 'https://www.reuters.com' + entry['canonical_url']) not in self.recent_seen and link in allowed
            ]
            with ThreadPoolExecutor(max_workers=8) as pool:
                futures = [pool.submit(self.xtr.extract_for_reuters, link, entry) for link, entry in tasks]
                for f in as_completed(futures):
                    art = f.result()
                    if art:
                        r_article_batch.append(art)

            self.bulk_store(r_article_batch, r_section, source_name=source_name)
            disk_batch.extend(r_article_batch)
            self._mark_seen([a['url'] for a in r_article_batch])
        # ---- RSS ----
        for rss in rss_feeds:
            try:
                feed = feedparser.parse(self.xtr.fetch(rss).content)
            except Exception as e:
                print(f"[ERROR] RSS feed {rss} failed: {e}")
                continue

            # Pre-filter by publish date BEFORE fetching articles (performance optimization)
            # Note: feedparser's published_parsed/updated_parsed are already in UTC; do NOT
            # apply source timezone or we wrongly shift times and drop recent entries (e.g. TheHindu).
            entries = feed.entries
            initial_count = len(entries)

            if self.recency_hours is not None and self.recency_hours > 0:
                cutoff = datetime.now(timezone.utc) - timedelta(hours=self.recency_hours)
                recent_entries = []
                for entry in entries:
                    pub_date = None
                    if hasattr(entry, 'published_parsed') and entry.published_parsed:
                        try:
                            # feedparser time tuple is already UTC
                            pub_date = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
                        except Exception:
                            pass
                    if pub_date is None and hasattr(entry, 'updated_parsed') and entry.updated_parsed:
                        try:
                            pub_date = datetime(*entry.updated_parsed[:6], tzinfo=timezone.utc)
                        except Exception:
                            pass
                    if pub_date is None and hasattr(entry, 'published') and entry.published:
                        pub_date = _rss_date_string_to_utc(entry.published)
                    if pub_date is None and hasattr(entry, 'updated') and entry.updated:
                        pub_date = _rss_date_string_to_utc(entry.updated)
                    if pub_date is None or pub_date >= cutoff:
                        recent_entries.append(entry)

                filtered_count = len(recent_entries)
                if filtered_count != initial_count:
                    print(f"[DEBUG] {source_name} RSS recency filter: {initial_count} → {filtered_count} articles (filtered {initial_count - filtered_count})")
                entries = recent_entries

            resolved = [self.xtr.resolve_link(normalize_url(e.get("link"))) for e in entries]
            allowed = self._filter_unseen_urls([u for u, _ in resolved])

            feed_batch: List[Dict[str, Any]] = []
            tasks = [
                (entry, url, resp)
                for entry, (url, resp) in zip(entries, resolved)
                if url and url in allowed and url not in self.recent_seen
            ]

            print(f"[DEBUG] {source_name} RSS: {len(entries)} entries, {len(tasks)} to fetch")

            failed_count = 0
            with ThreadPoolExecutor(max_workers=8) as pool:
                future_to_url = {
                    pool.submit(self.xtr.extract, url, entry, resp): (url, entry)
                    for entry, url, resp in tasks
                }
                for f in as_completed(future_to_url):
                    url, entry = future_to_url[f]
                    try:
                        art = f.result()
                        if art:
                            feed_batch.append(art)
                        else:
                            failed_count += 1
                    except Exception as e:
                        failed_count += 1
                        print(f"[ERROR] {source_name}: Failed to extract {url}: {e}")

            if failed_count > 0:
                print(f"[DEBUG] {source_name} RSS: {failed_count} articles failed extraction")

            self.bulk_store(feed_batch, rss, source_name=source_name)
            print(f"[DEBUG] {source_name}: extracted {len(feed_batch)} articles from RSS")
            disk_batch.extend(feed_batch)
            self._mark_seen([a['url'] for a in feed_batch])

        # ---- Sitemaps ----
        for sm in sitemaps:
            entries = self.xtr._parse_sitemap(sm)
            initial_count = len(entries)

            # Pre-filter by lastmod date BEFORE fetching articles (huge performance gain!)
            if self.recency_hours is not None and self.recency_hours > 0:
                cutoff = datetime.now(timezone.utc) - timedelta(hours=self.recency_hours)

                recent_entries = []
                for entry in entries:
                    lastmod = entry.get("lastmod")
                    if lastmod:
                        try:
                            # Normalize using source timezone
                            lastmod_dt = _normalize_date_to_utc(lastmod, source_name, None)
                            if lastmod_dt and lastmod_dt >= cutoff:
                                recent_entries.append(entry)
                            # else: skip old article (don't even fetch it!)
                        except:
                            recent_entries.append(entry)  # Include if can't parse
                    else:
                        recent_entries.append(entry)  # Include if no date

                filtered_count = len(recent_entries)
                if filtered_count != initial_count:
                    print(f"[DEBUG] {source_name} recency filter: {initial_count} → {filtered_count} articles (filtered {initial_count - filtered_count})")
                entries = recent_entries
            
            locs = [i.get("loc", "") for i in entries]
            resolved = [
                (normalize_url(loc), None) if 'www.reuters.com' in loc else self.xtr.resolve_link(normalize_url(loc))
                for loc in locs
            ]
            allowed = self._filter_unseen_urls([u for u, _ in resolved])

            sm_batch: List[Dict[str, Any]] = []
            tasks = []
            for item, (url, resp) in zip(entries, resolved):
                if url not in allowed:
                    continue
                if 'www.reuters.com' in url:
                    tasks.append((True, url, item, None))
                else:
                    tasks.append((False, url, item, resp))

            print(f"[DEBUG] {source_name} sitemap: {len(entries)} total entries, {len(tasks)} to fetch")

            with ThreadPoolExecutor(max_workers=8) as pool:
                futures = []
                url_to_task = {}
                for is_reuters, url, item, resp in tasks:
                    if is_reuters:
                        future = pool.submit(self.xtr.extract_for_reuters, url, item, resp)
                    else:
                        future = pool.submit(self.xtr.extract, url, item, resp)
                    futures.append(future)
                    url_to_task[future] = (url, is_reuters)

                failed_count = 0
                for f in as_completed(futures):
                    url, is_reuters = url_to_task[f]
                    try:
                        art = f.result()
                        if art:
                            sm_batch.append(art)
                        else:
                            failed_count += 1
                            if "espn" in source_name.lower():
                                print(f"[DEBUG] {source_name}: Failed to extract article: {url}")
                    except Exception as e:
                        failed_count += 1
                        print(f"[ERROR] {source_name}: Exception extracting {url}: {e}")

            print(f"[DEBUG] {source_name}: extracted {len(sm_batch)} articles from sitemap")
            self.bulk_store(sm_batch, sm, source_name=source_name)
            print(f"[DEBUG] {source_name}: stored {len(sm_batch)} articles")
            disk_batch.extend(sm_batch)
            self._mark_seen([a['url'] for a in sm_batch])
        return disk_batch

    def get_reuters_data(self, offset, section="/world/india/"):
        json_obj = {
            "arc-site": "reuters",
            "fetch_type": "collection",
            "offset": offset,
            "section_id": section,
            "size": 20,
            "uri": section,
            "website": "reuters"
        }
        json_str = json.dumps(json_obj)
        encoded_str = urllib.parse.quote(json_str)
        url = f"https://www.reuters.com/pf/api/v3/content/fetch/articles-by-section-alias-or-id-v1?query={encoded_str}&_website=reuters"
        payload = {}
        response = requests.request("GET", url, headers=REUTERS_HEADERS, data=payload)
        return response


    def fetch_all_reuters(self, offset: int = 0,
                          section: str = "/world/india/",
                          collected: list | None = None,
                          pause: float = 0.25) -> list[dict]:
        """
        Recursively fetch every article in `section` from Reuters’ content‐fetch API.

        Parameters
        ----------
        offset : int
            Start position in the collection (multiple of 20).
        section : str
            Same `section` string you pass to `get_reuters_data`.
        collected : list | None
            The running list that holds all articles pulled so far.
        pause : float
            Seconds to sleep between successive requests to be polite.

        Returns
        -------
        list[dict]
            Full list of article records returned by the endpoint.
        """
        if collected is None:
            collected = []

        resp = self.get_reuters_data(offset, section)
        if resp.status_code != 200:
            raise RuntimeError(f"Request failed at offset {offset}: {resp.status_code}")

        payload = resp.json()["result"]
        reuters_articles = payload.get("articles", [])
        collected.extend(reuters_articles)
        total_size = payload["pagination"]["total_size"]

        next_offset = offset + len(reuters_articles)
        if next_offset >= total_size:
            return collected

        if pause:
            time.sleep(pause)
        return self.fetch_all_reuters(next_offset, section, collected, pause)

    # ------------------- main crawl logic -----------------------
    def crawl_once(self, verbose: bool = False):
        disk_batch: List[Dict[str, Any]] = []
        try:
            with ThreadPoolExecutor(max_workers=8) as pool:
                futures = [pool.submit(self.extract_from_source, src, verbose) for src in self.sources]
                for f in as_completed(futures):
                    disk_batch.extend(f.result())
        except KeyboardInterrupt:
            print("✋  Ctrl-C caught — stopping threads…", file=sys.stderr)
            pool.shutdown(wait=False, cancel_futures=True)  # Py ≥ 3.9
            raise

    # ------------------- scheduler helpers --------------------
    def run_forever(self, verbose: bool = False):
        self.crawl_once(verbose=verbose)
        if self.interval > 0:
            schedule.every(self.interval).minutes.do(self.crawl_once, verbose=verbose)
            print(f"Polling every {self.interval} min — Ctrl‑C to stop")
            try:
                while True:
                    schedule.run_pending(); time.sleep(1)
            except KeyboardInterrupt:
                print("\nStopping… bye!")