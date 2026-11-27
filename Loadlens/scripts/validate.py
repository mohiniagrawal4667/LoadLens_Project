"""Validation suite — sample journeys, ordering checks and load sanity tests.

Run:
    python scripts/validate.py
"""
from __future__ import annotations

import json
import random
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
sys.path.insert(0, str(PROJECT_ROOT))

import _stdout_compat  # noqa: F401

from src import analytics
from src.data_loader import (
    DQ_REPORT_JSON,
    SAMPLE_CSV,
    SEGMENTS_PARQUET,
    TICKETS_PARQUET,
    TRIP_GRAPH_PARQUET,
    clean_with_report,
    load_raw,
)
from src.journey_planner import search_options_topology
from src.load_engine import compute_segment_loads, load_segments
from src.topology import build_route_topology, load_topology


def line(s: str = "=") -> None:
    print(f"\n{s * 60}")


def main():
    print("LoadLens — validation suite")
    line()

    if TICKETS_PARQUET.exists() and SEGMENTS_PARQUET.exists() and TRIP_GRAPH_PARQUET.exists() and DQ_REPORT_JSON.exists():
        import pandas as pd
        tickets = pd.read_parquet(TICKETS_PARQUET)
        segments = load_segments()
        topology = load_topology()
        dq = json.loads(DQ_REPORT_JSON.read_text(encoding="utf-8"))
        print("Mode: processed cache (data/cache/)")
    else:
        raw = load_raw(SAMPLE_CSV)
        tickets, dq = clean_with_report(raw, source_signature=str(SAMPLE_CSV), write_dq=False)
        topology = build_route_topology(tickets)
        segments, _ = compute_segment_loads(tickets, topology)
        print("Mode: bundled sample (data_sample/tickets_sample.csv)")

    # ---- 1. Source-row count check -----------------------------------------
    line("-")
    print("[1] Row counts vs. raw source")
    print(f"  raw          : {dq['raw_rows']:,}")
    print(f"  kept         : {dq['kept_rows']:,}")
    delta = dq["raw_rows"] - dq["kept_rows"]
    expected = (
        dq.get("dropped_missing_core", 0)
        + dq.get("dropped_invalid_stop_names", 0)
        + dq.get("dropped_nonpositive_passenger_count", 0)
        + dq.get("dropped_same_origin_and_destination", 0)
    )
    print(f"  delta        : {delta:,} (expected {expected:,})")
    assert delta == expected, "Row counts do not match exclusion sum"
    print("  PASS")

    # ---- 2. Segment loads are non-negative ---------------------------------
    line("-")
    print("[2] Segment loads non-negative")
    assert (segments["segment_load"] >= 0).all(), "Negative segment load detected"
    print(f"  min  = {int(segments['segment_load'].min()):,}")
    print(f"  max  = {int(segments['segment_load'].max()):,}")
    print(f"  mean = {segments['segment_load'].mean():.2f}")
    print("  PASS")

    # ---- 3. Boarding / destination ordering ---------------------------------
    line("-")
    print("[3] Boarding-stop precedes destination (no inverse direction leakage)")
    rank_index = {(r, d): rank_map for (r, d), rank_map in topology.items()}
    inv = 0
    total = 0
    for r in tickets.itertuples(index=False):
        rm = rank_index.get((r.route, r.direction))
        if rm is None:
            continue
        sa = rm.get(r.start_norm)
        sb = rm.get(r.end_norm)
        if sa is not None and sb is not None:
            total += 1
            if sa > sb:
                inv += 1
    print(f"  total tickets matched to topology  : {total:,}")
    print(f"  with start_rank < end_rank        : {total - inv:,}")
    print(f"  with start_rank > end_rank        : {inv:,}")
    print("  PASS" if inv < total * 0.005 else "  WARN: >0.5% inversions")

    # ---- 4. Reload load totals ---------------------------------------------
    line("-")
    print("[4] Per-ticket passenger totals reconcile with observation")
    total_seg_load = float(segments["segment_load"].sum())
    print(f"  total passenger-segments          : {total_seg_load:,.0f}")
    print(f"  total passenger-journeys          : {tickets['passenger_count'].sum():,.0f}")
    ratio = total_seg_load / tickets["passenger_count"].sum()
    print(f"  avg segments crossed per journey  : {ratio:.2f}")
    assert total_seg_load >= tickets["passenger_count"].sum() * 0.99
    print("  PASS")

    # ---- 5. Peak vs off-peak delta -----------------------------------------
    line("-")
    print("[5] Peak vs off-peak comparison (matches the KPI tile)")
    pq = analytics.peak_vs_offpeak(tickets)
    print(f"  peak   = {pq['peak_passenger_volume']:,}  ({pq['peak_share_pct']}%)")
    print(f"  off    = {pq['offpeak_passenger_volume']:,}")
    assert 0.0 < pq["peak_share_pct"] < 100.0
    print("  PASS")

    # ---- 6. Random sample journeys -----------------------------------------
    line("-")
    print("[6] Random sample journeys (manual traceability)")
    random.seed(11)
    routes = sorted({(r, d) for r, d in topology.keys()})
    sample_pairs = []
    for _ in range(10):
        r, d = random.choice(routes)
        ranks = topology[(r, d)]
        ordered = list(ranks.keys())
        if len(ordered) < 4:
            continue
        a_idx = random.randint(0, len(ordered) - 3)
        b_idx = random.randint(a_idx + 1, len(ordered) - 1)
        sample_pairs.append((ordered[a_idx], ordered[b_idx], r, d))

    for o, d, r, direction in sample_pairs[:6]:
        sub = tickets[(tickets["route"] == r) &
                      (tickets["direction"] == direction) &
                      (tickets["start_norm"] == o) &
                      (tickets["end_norm"] == d)]
        n = len(sub)
        total_psg = int(sub["passenger_count"].sum()) if n else 0
        result = search_options_topology(
            tickets, segments, o, d, topology=topology, max_options=20
        )
        matched = [
            opt for opt in result["options"]
            if opt["route"] == r and opt["direction"] == direction
        ]
        opt_load = matched[0]["historical_segment_load"] if matched else 0
        print(f"  {r:18} {direction:5}  {o!r:28} -> {d!r:28}  "
              f"tickets={n:>4}  pax={total_psg:>5}  route_seg_load={int(opt_load):>6}")

    # ---- 7. Heatmap-side cross check ---------------------------------------
    line("-")
    print("[7] Hour-of-day totals sum equals total volume")
    h_total = int(tickets["passenger_count"].sum())
    h_sum = int(tickets.groupby("ticket_hour")["passenger_count"].sum().sum())
    print(f"  total          : {h_total:,}")
    print(f"  hour-grouped   : {h_sum:,}")
    assert h_total == h_sum
    print("  PASS")

    print("\nAll validations completed.")


if __name__ == "__main__":
    main()
