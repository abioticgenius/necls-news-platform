from __future__ import annotations

"""Run the full news processing pipeline sequentially on a schedule."""

import os
import subprocess
import sys
import time
from pathlib import Path

import schedule


def load_env_file(env_path: str | os.PathLike | None = ".env") -> None:
    """Load KEY=VALUE pairs from a simple .env file into os.environ."""
    if not env_path:
        return
    path = Path(env_path)
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key, value)


def run(cmd: list[str]) -> None:
    """Run a subprocess and raise on failure."""
    print("Running:", " ".join(cmd))
    subprocess.run(cmd, check=True, env=os.environ)


def job() -> None:
    root = Path(__file__).resolve().parent.parent
    
    # extract_articles.py will automatically read EXTRACT_HOURS_RECENCY from environment
    run([
        sys.executable, 
        str(root / "scripts/extract_articles.py"), 
        "--config", str(root / "feeds.json"), 
        "--interval", "0", 
        "--verbose"
    ])
    # cluster_articles.py will automatically read CLUSTERING_THRESHOLD and CLUSTERING_THETA from environment
    run([sys.executable, str(root / "scripts/cluster_articles.py"), "--algo", "agglom", "--days", "1", "--verbose"])
    # cluster_clusters.py will automatically read META_CLUSTERING_THRESHOLD from environment
    run([sys.executable, str(root / "scripts/cluster_clusters.py"), "--algo", "agglom", "--verbose"])
    run([sys.executable, str(root / "scripts/llm_pipeline.py")])
    run([sys.executable, str(root / "scripts/sync_app_db.py")])
    run([sys.executable, str(root / "scripts/compute_tag_vectors.py")])


def main() -> None:
    load_env_file()
    interval = int(os.getenv("PIPELINE_INTERVAL_MIN", "0"))
    job()
    if interval > 0:
        schedule.every(interval).minutes.do(job)
        while True:
            schedule.run_pending()
            time.sleep(1)


if __name__ == "__main__":
    main()