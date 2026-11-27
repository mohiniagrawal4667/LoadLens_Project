"""Generate a small sample dataset for reviewers who don't want to download the full ~290 MB CSV.

Produces a representative subset (~1% random sample) of the cleaned tickets
plus the derived segment-loads and route topology caches. Run after
``build_processed.py`` has finished.

Usage:
    python scripts/make_sample.py
"""
from __future__ import annotations

import json
from pathlib import Path

import _stdout_compat  # noqa: F401  (UTF-8 stdout for Windows console)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
import sys
sys.path.insert(0, str(PROJECT_ROOT))

from src.data_loader import (PROJECT_ROOT, CACHE_DIR, TICKETS_PARQUET,
                             SEGMENTS_PARQUET, TRIP_GRAPH_PARQUET, DQ_REPORT_JSON)
import pandas as pd

SAMPLE_DIR = PROJECT_ROOT / "data_sample"
SAMPLE_DIR.mkdir(parents=True, exist_ok=True)
SAMPLE_SIZE = 25_000         # ~1% of full ticket set


def main():
    print("Reading cleaned tickets...")
    df = pd.read_parquet(TICKETS_PARQUET)
    print(f"  full rows: {len(df):,}")

    # Stratified sampling on route, so all popular routes appear in the sample.
    n_routes_to_keep = 60
    top_routes = df["route"].value_counts().head(n_routes_to_keep).index.tolist()
    sub = df[df["route"].isin(top_routes)].copy()
    print(f"  keeping top {n_routes_to_keep} routes → {len(sub):,} rows")

    # Draw sample
    n = min(SAMPLE_SIZE, len(sub))
    sample = sub.sample(n=n, random_state=7).reset_index(drop=True)
    sample_path = SAMPLE_DIR / "tickets_sample.csv"
    sample.to_csv(sample_path, index=False)
    print(f"  wrote {sample_path}  ({len(sample):,} rows)")

    # Trim derived caches to entries seen in this sample only.
    segs = pd.read_parquet(SEGMENTS_PARQUET)
    segs_sample = segs[segs["route"].isin(sample["route"].unique())].reset_index(drop=True)
    segs_sample.to_parquet(SAMPLE_DIR / "segments_sample.parquet", index=False)
    print(f"  wrote segments_sample.parquet  ({len(segs_sample):,} segments)")

    trip_graph = pd.read_parquet(TRIP_GRAPH_PARQUET)
    trip_sample = trip_graph[trip_graph["route"].isin(sample["route"].unique())].reset_index(drop=True)
    trip_sample.to_parquet(SAMPLE_DIR / "trip_graph_sample.parquet", index=False)
    print(f"  wrote trip_graph_sample.parquet  ({len(trip_sample):,} entries)")

    # DQ summary (sanitise source_path so no local machine path is leaked)
    dq = json.loads(DQ_REPORT_JSON.read_text(encoding="utf-8"))
    if dq.get("source_path"):
        dq["source_path"] = Path(str(dq["source_path"])).name
    (SAMPLE_DIR / "sample_summary.json").write_text(json.dumps({
        "sample_rows": int(len(sample)),
        "sample_routes_kept": int(len(top_routes)),
        "full_dq_snapshot": dq,
    }, indent=2), encoding="utf-8")
    print(f"  wrote sample_summary.json")
    print("✓ Sample generation complete")


if __name__ == "__main__":
    main()
