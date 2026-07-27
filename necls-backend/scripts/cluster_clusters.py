from __future__ import annotations
import argparse
import os

from necls_backend.clustering import MetaClusterer


def cli():
    # Read default from environment variable
    default_threshold = 0.25
    if os.getenv("META_CLUSTERING_THRESHOLD"):
        try:
            default_threshold = float(os.getenv("META_CLUSTERING_THRESHOLD"))
        except ValueError:
            print(f"Warning: Invalid META_CLUSTERING_THRESHOLD value in environment, using default {default_threshold}")
    
    p = argparse.ArgumentParser(description="Cluster existing story clusters")
    p.add_argument("--algo", choices=["agglom"], default="agglom")
    p.add_argument("--threshold", type=float, default=default_threshold)
    p.add_argument("--min-size", type=int, default=3)
    p.add_argument("--min-samples", type=int, default=2)
    p.add_argument("--days", type=float, default=None,
                   help="Only clusters updated within this many days")
    p.add_argument("--verbose", action="store_true")
    a = p.parse_args()
    
    # Log when env var is used (if verbose)
    if a.verbose and os.getenv("META_CLUSTERING_THRESHOLD"):
        print(f"Using META_CLUSTERING_THRESHOLD from environment: {a.threshold}")
    
    MetaClusterer().cluster_once(algo=a.algo, threshold=a.threshold, min_size=a.min_size,
                                 min_samples=a.min_samples, days=a.days, verbose=a.verbose)


if __name__ == "__main__":
    cli()