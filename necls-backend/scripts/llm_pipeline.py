from __future__ import annotations

"""CLI for running the LLM pipeline to summarise clusters and generate audio."""

import argparse
import datetime as dt
import os

from necls_backend.llm_pipeline.pipeline import ClusterPipeline
from necls_backend.llm_pipeline.audio import AudioService


def cli() -> None:
    parser = argparse.ArgumentParser(
        description="Run the LLM pipeline for clusters on a given date"
    )
    parser.add_argument(
        "--date",
        help="Date in YYYY-MM-DD format (defaults to today in UTC)",
        default=None,
    )
    parser.add_argument(
        "--audio-bucket",
        default=os.getenv("AUDIO_BUCKET", ""),
        help="S3 bucket name for audio storage",
    )
    parser.add_argument(
        "--audio-prefix",
        default=os.getenv("AUDIO_PREFIX", ""),
        help="Optional S3 object prefix for audio files",
    )
    args = parser.parse_args()

    date = args.date or dt.datetime.now().date().isoformat()
    if not args.audio_bucket:
        raise ValueError("--audio-bucket is required (or set AUDIO_BUCKET environment variable)")
    audio = AudioService(
        bucket=args.audio_bucket, prefix=args.audio_prefix
    )
    pipeline = ClusterPipeline(audio_service=audio)
    pipeline.execute_for_date(date)


if __name__ == "__main__":
    cli()