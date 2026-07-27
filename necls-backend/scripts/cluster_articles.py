from __future__ import annotations
import argparse
import os
from necls_backend.clustering import StoryClusterer


def cli():
    # Read defaults from environment variables
    default_threshold = 0.6
    if os.getenv("CLUSTERING_THRESHOLD"):
        try:
            default_threshold = float(os.getenv("CLUSTERING_THRESHOLD"))
        except ValueError:
            print(f"Warning: Invalid CLUSTERING_THRESHOLD value in environment, using default {default_threshold}")
    
    default_theta = 0.55
    if os.getenv("CLUSTERING_THETA"):
        try:
            default_theta = float(os.getenv("CLUSTERING_THETA"))
        except ValueError:
            print(f"Warning: Invalid CLUSTERING_THETA value in environment, using default {default_theta}")
    
    default_hours = None
    if os.getenv("CLUSTERING_HOURS"):
        try:
            default_hours = float(os.getenv("CLUSTERING_HOURS"))
        except ValueError:
            print(f"Warning: Invalid CLUSTERING_HOURS value in environment, ignoring")

    p = argparse.ArgumentParser(description="Cluster freshly extracted articles")
    p.add_argument("--algo", choices=["agglom"], default="agglom")
    p.add_argument("--threshold", type=float, default=default_threshold, help="Phase 2 clustering threshold (distance)")
    p.add_argument("--theta", type=float, default=default_theta, help="Phase 1 attach threshold (similarity)")
    p.add_argument("--min-size", type=int, default=1)
    p.add_argument("--min-samples", type=int, default=2)
    p.add_argument("--hours", type=float, default=default_hours, help="±time window in hours for centroid attach/batching (overrides --days)")
    p.add_argument("--days", type=float, default=None, help="±time window in days (use --hours instead for finer control)")
    p.add_argument("--verbose", action="store_true")
    a = p.parse_args()

    effective_days = a.hours / 24.0 if a.hours is not None else a.days

    # Log when env vars are used (if verbose)
    if a.verbose:
        if os.getenv("CLUSTERING_THRESHOLD"):
            print(f"Using CLUSTERING_THRESHOLD from environment: {a.threshold}")
        if os.getenv("CLUSTERING_THETA"):
            print(f"Using CLUSTERING_THETA from environment: {a.theta}")
        if a.hours is not None:
            print(f"Using time window: {a.hours}h → {effective_days:.4f} days")
        elif effective_days is not None:
            print(f"Using time window: {effective_days} days")

    StoryClusterer().cluster_once(algo=a.algo, threshold=a.threshold, min_size=a.min_size,
                                  min_samples=a.min_samples, days=effective_days, theta=a.theta, verbose=a.verbose)

if __name__ == "__main__":
    cli()