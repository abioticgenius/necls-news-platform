from __future__ import annotations
import argparse, json, pathlib, os
from necls_backend.extractor import FeedCrawler
from necls_backend.db import ensure_db1_schema 

def cli():
    p = argparse.ArgumentParser(description="Extract & store articles")
    p.add_argument("--config", required=True, help="Path to feeds.json (see README)")
    p.add_argument("--interval", type=int, default=None, help="Minutes between runs (0=once)")
    p.add_argument("--hours", type=float, default=None, help="Only extract articles from last N hours (reads from EXTRACT_HOURS_RECENCY env if not set)")
    p.add_argument("--verbose", action="store_true")
    a = p.parse_args()

    if a.verbose:
        print("Ensuring DB1 schema...")
    ensure_db1_schema()
    if a.verbose:
        print("DB1 schema ready")

    # Read from environment variable if --hours not specified
    recency_hours = a.hours
    if recency_hours is None and os.getenv("EXTRACT_HOURS_RECENCY"):
        try:
            recency_hours = float(os.getenv("EXTRACT_HOURS_RECENCY"))
            if a.verbose:
                print(f"Using EXTRACT_HOURS_RECENCY from environment: {recency_hours} hours")
        except ValueError:
            print(f"Warning: Invalid EXTRACT_HOURS_RECENCY value in environment, ignoring")
            recency_hours = None

    cfg = json.loads(pathlib.Path(a.config).read_text())
    crawler = FeedCrawler(cfg.get("sources", cfg), interval_min=a.interval, recency_hours=recency_hours)
    if a.interval == 0:
        crawler.crawl_once(verbose=a.verbose)
    else:
        crawler.run_forever(verbose=a.verbose)

if __name__ == "__main__":
    cli()