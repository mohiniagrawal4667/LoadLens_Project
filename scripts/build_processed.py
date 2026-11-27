"""Build the processed parquet cache from a ticket source.

Usage:
    python scripts/build_processed.py                       # auto-detect source
    python scripts/build_processed.py /path/to/October.csv  # explicit path
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

# Force UTF-8 stdout so log glyphs render on the Windows cp1252 default console.
import _stdout_compat  # noqa: F401

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.data_loader import (
    DQ_REPORT_JSON,
    SEGMENTS_PARQUET,
    TICKETS_PARQUET,
    TRIP_GRAPH_PARQUET,
    load_clean,
    resolve_source,
)
from src.load_engine import save_segments
from src.topology import save_topology


def main():
    p = argparse.ArgumentParser()
    p.add_argument("source", nargs="?", default=None,
                   help="Path to source parquet/CSV. Defaults to LOADLENS_TICKETS, "
                        "data/raw/, or data_sample/tickets_sample.csv.")
    p.add_argument("--force", action="store_true",
                   help="Recompute even if caches already exist.")
    args = p.parse_args()

    if (
        not args.force
        and args.source is None
        and TICKETS_PARQUET.exists()
        and SEGMENTS_PARQUET.exists()
        and TRIP_GRAPH_PARQUET.exists()
        and DQ_REPORT_JSON.exists()
    ):
        print("• Processed caches already exist in data/cache/ (pass --force to rebuild).")
        return

    src_path, src_kind = resolve_source(args.source)
    print(f"• Source ({src_kind}): {src_path}")

    print("• Cleaning raw tickets...")
    t0 = time.time()
    tickets = load_clean(force=True, source=src_path)
    print(f"  {len(tickets):,} rows  ({time.time()-t0:.1f}s)")

    print("• Building route topology...")
    t0 = time.time()
    ordering = save_topology(tickets)
    print(f"  {len(ordering):,} route+direction combinations  ({time.time()-t0:.1f}s)")

    print("• Computing segment loads...")
    t0 = time.time()
    meta = save_segments(tickets, ordering)
    print(f"  {meta['segments_aggregated']:,} segments  "
          f"({meta['used_ticket_rows']:,} used tickets, "
          f"{meta['skipped_backward_journeys']:,} rejected as back-tracked)  "
          f"({time.time()-t0:.1f}s)")

    print("✓ Done.")


if __name__ == "__main__":
    main()
