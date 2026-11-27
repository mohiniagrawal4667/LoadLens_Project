"""Strict evaluator & software tester suite for LoadLens.

Tests all 10 required cases against both:
  - The active dataset (processed cache if built, else bundled sample)
  - Controlled synthetic CSV / GTFS edge-case fixtures

Run:
    python audit.py
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

import pandas as pd

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, OSError):
    pass

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from src import analytics
from src.data_loader import (
    DQ_REPORT_JSON,
    SAMPLE_CSV,
    SEGMENTS_PARQUET,
    SEGMENT_META_JSON,
    TICKETS_PARQUET,
    TRIP_GRAPH_PARQUET,
    clean_with_report,
    load_raw,
)
from src.gtfs import gtfs_status
from src.journey_planner import (
    gtfs_available,
    search_options_topology,
    search_options_with_gtfs,
    stop_index,
    suggest_stop,
)
from src.load_engine import compute_segment_loads, filter_tickets_by_window, load_segments
from src.topology import build_route_topology, load_topology

failures = []
warnings_list = []


def section(title: str, n: int) -> None:
    print(f"\n{'=' * 72}\nTEST {n} -- {title}\n{'=' * 72}")


def fail(t: int, msg: str) -> None:
    failures.append((t, msg))
    print(f"  [FAIL] {msg}")


def warn(msg: str) -> None:
    warnings_list.append(msg)
    print(f"  [WARN] {msg}")


def passed(msg: str) -> None:
    print(f"  [PASS] {msg}")


def load_active_dataset():
    if (
        TICKETS_PARQUET.exists()
        and SEGMENTS_PARQUET.exists()
        and TRIP_GRAPH_PARQUET.exists()
        and DQ_REPORT_JSON.exists()
        and SEGMENT_META_JSON.exists()
    ):
        tickets = pd.read_parquet(TICKETS_PARQUET)
        dq = json.loads(DQ_REPORT_JSON.read_text(encoding="utf-8"))
        topology = load_topology()
        segments = load_segments()
        seg_meta = json.loads(SEGMENT_META_JSON.read_text(encoding="utf-8"))
        mode = "cache"
    else:
        raw = load_raw(SAMPLE_CSV)
        tickets, dq = clean_with_report(raw, source_signature=str(SAMPLE_CSV), write_dq=False)
        topology = build_route_topology(tickets)
        segments, seg_meta = compute_segment_loads(tickets, topology)
        mode = "sample"
    return tickets, dq, topology, segments, seg_meta, mode


tickets, dq, topology, segments, seg_meta, mode = load_active_dataset()
print(f"Active dataset mode: {mode} ({len(tickets):,} cleaned rows, {len(segments):,} segments)")

# -------------------------------------------------------------------------
section("FULL TICKET CSV INGESTION & ROW ACCOUNTING", 1)
expected_kept = (
    dq["raw_rows"]
    - dq.get("dropped_missing_core", 0)
    - dq.get("dropped_invalid_stop_names", 0)
    - dq.get("dropped_nonpositive_passenger_count", 0)
    - dq.get("dropped_same_origin_and_destination", 0)
)
if dq["kept_rows"] == expected_kept and len(tickets) == dq["kept_rows"]:
    passed(f"Active dataset row accounting closes: raw={dq['raw_rows']:,}, kept={dq['kept_rows']:,}")
else:
    fail(1, f"Active row math mismatch: kept={dq['kept_rows']} expected={expected_kept}")

# Synthetic CSV ingestion + timezone + exclusions
with tempfile.TemporaryDirectory() as tmp:
    csv_path = Path(tmp) / "test_tickets.csv"
    pd.DataFrame([
        # Valid IST (+05:30) and UTC (Z) rows
        {"passenger_count": 2, "route": "717AUP", "start_stop_name": "Stop A", "end_stop_name": "Stop B", "created_at": "2026-10-01 08:30:00+05:30", "vehicle_number": "DL1PC0001"},
        {"passenger_count": 1, "route": "717AUP", "start_stop_name": "Stop B", "end_stop_name": "Stop C", "created_at": "2026-10-01T03:00:00Z", "vehicle_number": None},
        # Dropped: missing core (NaN stop)
        {"passenger_count": 1, "route": "717AUP", "start_stop_name": None, "end_stop_name": "Stop C", "created_at": "2026-10-01 09:00:00+05:30", "vehicle_number": "DL1"},
        # Dropped: invalid stop name (punctuation only -> normalizes to "")
        {"passenger_count": 1, "route": "717AUP", "start_stop_name": "---", "end_stop_name": "Stop C", "created_at": "2026-10-01 09:05:00+05:30", "vehicle_number": "DL1"},
        # Dropped: non-positive passenger_count
        {"passenger_count": 0, "route": "717AUP", "start_stop_name": "Stop A", "end_stop_name": "Stop C", "created_at": "2026-10-01 09:10:00+05:30", "vehicle_number": "DL1"},
        # Dropped: same origin & destination after normalization
        {"passenger_count": 1, "route": "717AUP", "start_stop_name": "Anand Vihar (Isbt)", "end_stop_name": "Anand Vihar", "created_at": "2026-10-01 09:15:00+05:30", "vehicle_number": "DL1"},
    ]).to_csv(csv_path, index=False)

    raw_syn = load_raw(csv_path)
    cln_syn, dq_syn = clean_with_report(raw_syn, source_signature=str(csv_path), write_dq=False)
    syn_expected = (
        dq_syn["raw_rows"]
        - dq_syn["dropped_missing_core"]
        - dq_syn["dropped_invalid_stop_names"]
        - dq_syn["dropped_nonpositive_passenger_count"]
        - dq_syn["dropped_same_origin_and_destination"]
    )
    if (
        dq_syn["raw_rows"] == 6
        and dq_syn["kept_rows"] == 2 == syn_expected
        and dq_syn["dropped_missing_core"] == 1
        and dq_syn["dropped_invalid_stop_names"] == 1
        and dq_syn["dropped_nonpositive_passenger_count"] == 1
        and dq_syn["dropped_same_origin_and_destination"] == 1
        and (cln_syn["ticket_hour"] == 8).all()
    ):
        passed("Synthetic CSV ingestion: all 4 exclusion buckets, row math, and IST conversion verified")
    else:
        fail(1, f"Synthetic CSV ingestion failed: dq={dq_syn}, hours={cln_syn['ticket_hour'].tolist()}")

# -------------------------------------------------------------------------
section("MISSING vehicle_number HANDLING", 2)
n_total = len(tickets)
n_missing_flag = int((~tickets["has_vehicle"]).sum())
if dq["missing_vehicle_number"] == dq["missing_vehicle_number_count"] == n_missing_flag:
    passed(f"Missing vehicle_number accurately counted ({n_missing_flag:,}/{n_total:,} = {dq['missing_vehicle_number_pct']:.2f}%)")
else:
    fail(2, f"Mismatch in missing vehicle count: dq={dq['missing_vehicle_number']} vs flag={n_missing_flag}")

# Test CSV without vehicle_number column at all + literal "nan" values
df_no_veh = pd.DataFrame([
    {"passenger_count": 3, "route": "100UP", "start_stop_name": "A", "end_stop_name": "B", "created_at": "2026-10-05 10:00:00+05:30"},
    {"passenger_count": 2, "route": "100UP", "start_stop_name": "A", "end_stop_name": "B", "created_at": "2026-10-05 11:00:00+05:30"},
])
cln_nv, dq_nv = clean_with_report(df_no_veh, write_dq=False)
topo_nv = build_route_topology(cln_nv)
segs_nv, _ = compute_segment_loads(cln_nv, topo_nv)
if (not cln_nv["has_vehicle"].any()) and dq_nv["distinct_vehicles_with_id"] == 0 and int(segs_nv["segment_load"].sum()) == 5:
    passed("Absent vehicle_number column handled gracefully: 0 distinct vehicles, 5 pax preserved in segment load")
else:
    fail(2, f"Missing vehicle_number column handling broken: dq={dq_nv}, segs={segs_nv}")

# -------------------------------------------------------------------------
section("INVALID / UNMATCHED STOP NAMES", 3)
empty_norm = int(((tickets["start_norm"] == "") | (tickets["end_norm"] == "")).sum())
if empty_norm == 0:
    passed("Zero empty normalized stop names survive cleaning")
else:
    fail(3, f"Found {empty_norm} empty normalized stops in cleaned tickets")

idx = stop_index(tickets)
bad_sugg = suggest_stop("zzzznonexistentstop999", idx, k=8)
if len(bad_sugg) == 0:
    passed("suggest_stop returns empty for unmatched stop query (no silent popular-stop fallback)")
else:
    fail(3, f"suggest_stop returned {len(bad_sugg)} unrelated stops for unmatched query")

res_unknown = search_options_topology(tickets, segments, "zzzznonexistent", "badarpur border", topology=topology)
if not res_unknown["options"] and "not found" in res_unknown["message"].lower():
    passed("search_options_topology rejects unknown stop with explicit message")
else:
    fail(3, f"search_options_topology mishandled unknown stop: {res_unknown}")

# -------------------------------------------------------------------------
section("BOARDING STOP BEFORE DESTINATION (valid direction)", 4)
rank_index = {(r, d): rm for (r, d), rm in topology.items()}
n_before = n_after = n_eq = n_unk = 0
for row in tickets.itertuples(index=False):
    rm = rank_index.get((row.route, row.direction))
    if rm is None:
        n_unk += 1
        continue
    sa, sb = rm.get(row.start_norm), rm.get(row.end_norm)
    if sa is None or sb is None:
        n_unk += 1
    elif sa < sb:
        n_before += 1
    elif sa > sb:
        n_after += 1
    else:
        n_eq += 1

if n_before == seg_meta["used_ticket_rows"] and n_eq == 0:
    passed(f"Valid forward journeys used: {n_before:,}; equal-rank impossible: {n_eq}")
else:
    fail(4, f"Forward count mismatch: n_before={n_before} vs meta={seg_meta['used_ticket_rows']}, n_eq={n_eq}")

# -------------------------------------------------------------------------
section("BOARDING STOP AFTER DESTINATION (back-tracked)", 5)
if n_after == seg_meta["skipped_backward_journeys"]:
    passed(f"Back-tracked journeys rejected in segment_meta: {n_after:,}")
else:
    fail(5, f"Backward count mismatch: n_after={n_after} vs meta={seg_meta['skipped_backward_journeys']}")

# Synthetic back-tracked check: A->B (10x), B->C (10x), plus 1 ticket C->A (back-tracked)
df_dir = pd.DataFrame(
    [{"passenger_count": 1, "route": "10UP", "start_stop_name": "Stop A", "end_stop_name": "Stop B", "created_at": "2026-10-01 08:00:00+05:30"}] * 5
    + [{"passenger_count": 1, "route": "10UP", "start_stop_name": "Stop B", "end_stop_name": "Stop C", "created_at": "2026-10-01 08:05:00+05:30"}] * 5
    + [{"passenger_count": 4, "route": "10UP", "start_stop_name": "Stop C", "end_stop_name": "Stop A", "created_at": "2026-10-01 08:10:00+05:30"}]
)
cln_dir, _ = clean_with_report(df_dir, write_dq=False)
topo_dir = build_route_topology(cln_dir)
segs_dir, meta_dir = compute_segment_loads(cln_dir, topo_dir)
res_rev = search_options_topology(cln_dir, segs_dir, "stop c", "stop a", topology=topo_dir)
if meta_dir["skipped_backward_journeys"] == 1 and int(segs_dir["segment_load"].sum()) == 10 and not res_rev["options"]:
    passed("Back-tracked ticket (C->A on A->B->C) excluded from load (10 pax) and returns 0 options in planner")
else:
    fail(5, f"Back-tracked handling failed: meta={meta_dir}, load={segs_dir['segment_load'].sum()}, res={res_rev}")

# -------------------------------------------------------------------------
section("OPPOSITE ROUTE DIRECTIONS", 6)
df_opp = pd.DataFrame([
    {"passenger_count": 2, "route": "717UP", "start_stop_name": "Alpha", "end_stop_name": "Beta", "created_at": "2026-10-01 08:00:00+05:30"},
    {"passenger_count": 3, "route": "717UP", "start_stop_name": "Beta", "end_stop_name": "Gamma", "created_at": "2026-10-01 08:05:00+05:30"},
    {"passenger_count": 5, "route": "717DOWN", "start_stop_name": "Gamma", "end_stop_name": "Beta", "created_at": "2026-10-01 09:00:00+05:30"},
    {"passenger_count": 7, "route": "717DOWN", "start_stop_name": "Beta", "end_stop_name": "Alpha", "created_at": "2026-10-01 09:05:00+05:30"},
])
cln_opp, _ = clean_with_report(df_opp, write_dq=False)
topo_opp = build_route_topology(cln_opp)
segs_opp, _ = compute_segment_loads(cln_opp, topo_opp)
opt_up = search_options_topology(cln_opp, segs_opp, "alpha", "gamma", topology=topo_opp)
opt_dn = search_options_topology(cln_opp, segs_opp, "gamma", "alpha", topology=topo_opp)
if (
    len(opt_up["options"]) == 1 and opt_up["options"][0]["route"] == "717UP" and opt_up["options"][0]["direction"] == "up"
    and len(opt_dn["options"]) == 1 and opt_dn["options"][0]["route"] == "717DOWN" and opt_dn["options"][0]["direction"] == "down"
):
    passed("Opposite directions (717UP vs 717DOWN) maintain independent topologies without cross-leakage")
else:
    fail(6, f"Opposite directions failed: up={opt_up}, dn={opt_dn}")

# -------------------------------------------------------------------------
section("DUPLICATE & REPEATED STOPS", 7)
dup_keys = tickets.groupby(["route", "direction", "start_norm", "end_norm"]).size()
n_dup_groups = int((dup_keys > 1).sum())
if n_dup_groups > 0:
    passed(f"Repeated OD tickets preserved & aggregated across {n_dup_groups:,} distinct OD groups")
else:
    warn("No duplicate OD keys found in active dataset")

# Cycle / repeated stop test in synthetic data
df_cyc = pd.DataFrame([
    {"passenger_count": 2, "route": "LOOPUP", "start_stop_name": "S1", "end_stop_name": "S2", "created_at": "2026-10-01 08:00:00+05:30"},
    {"passenger_count": 2, "route": "LOOPUP", "start_stop_name": "S1", "end_stop_name": "S2", "created_at": "2026-10-01 08:01:00+05:30"},
    {"passenger_count": 2, "route": "LOOPUP", "start_stop_name": "S2", "end_stop_name": "S3", "created_at": "2026-10-01 08:02:00+05:30"},
    {"passenger_count": 1, "route": "LOOPUP", "start_stop_name": "S2", "end_stop_name": "S3", "created_at": "2026-10-01 08:02:30+05:30"},
    {"passenger_count": 1, "route": "LOOPUP", "start_stop_name": "S3", "end_stop_name": "S1", "created_at": "2026-10-01 08:03:00+05:30"},
])
cln_cyc, _ = clean_with_report(df_cyc, write_dq=False)
topo_cyc = build_route_topology(cln_cyc)
segs_cyc, meta_cyc = compute_segment_loads(cln_cyc, topo_cyc)
if int(segs_cyc["segment_load"].sum()) == 7 and meta_cyc["skipped_backward_journeys"] == 1:
    passed("Duplicate OD tickets summed (S1->S2=4 pax) and cycle edge S3->S1 broken/rejected cleanly")
else:
    fail(7, f"Duplicate/cycle test failed: segs={segs_cyc}, meta={meta_cyc}")

# -------------------------------------------------------------------------
section("EMPTY FILTERS / INVALID ORIGIN-DESTINATION SELECTIONS", 8)
empty_df = tickets.iloc[0:0].copy()
empty_segs = segments.iloc[0:0].copy()
r_rank = analytics.route_demand_ranking(empty_df)
r_peak = analytics.peak_vs_offpeak(empty_df)
r_top_seg = analytics.top_segments(empty_segs)
r_same = search_options_topology(tickets, segments, "ali village", "ali village", topology=topology)
r_blank = search_options_topology(tickets, segments, "", "", topology=topology)
if (
    len(r_rank) == 0
    and r_peak["peak_passenger_volume"] == 0
    and len(r_top_seg) == 0
    and not r_same["options"]
    and not r_blank["options"]
):
    passed("Empty DataFrames, empty queries, and identical origin/dest handled gracefully without crash")
else:
    fail(8, "Empty filter / invalid selection test failed")

# -------------------------------------------------------------------------
section("MISSING GTFS FILES (AND SUPPLIED GTFS VERIFICATION)", 9)
gtfs_dir = PROJECT_ROOT / "data" / "gtfs"
st_missing = gtfs_status(gtfs_dir)
if not st_missing["available"]:
    passed(f"Missing GTFS detected cleanly ({st_missing['error']})")
else:
    passed(f"GTFS detected in {gtfs_dir}")

# Verify topology mode disables fabricated durations (estimated_duration_min must be None)
sample_route, sample_dir = next(iter(topology.keys()))
sample_ranks = sorted(topology[(sample_route, sample_dir)].items(), key=lambda x: x[1])
if len(sample_ranks) >= 2:
    o_s, d_s = sample_ranks[0][0], sample_ranks[-1][0]
    res_no_gtfs = search_options_topology(tickets, segments, o_s, d_s, topology=topology)
    if res_no_gtfs["options"] and all(o["estimated_duration_min"] is None for o in res_no_gtfs["options"]):
        passed("No fabricated heuristic duration when GTFS is absent (estimated_duration_min is None)")
    else:
        fail(9, f"Expected None duration without GTFS, got: {res_no_gtfs['options'][:1]}")

# Partial GTFS + valid synthetic GTFS verification
with tempfile.TemporaryDirectory() as tmp:
    gdir = Path(tmp) / "gtfs"
    gdir.mkdir()
    pd.DataFrame([{"stop_id": "1", "stop_name": "Alpha"}, {"stop_id": "2", "stop_name": "Beta"}]).to_csv(gdir / "stops.txt", index=False)
    partial_status = gtfs_status(gdir)
    if not partial_status["available"] and set(partial_status["missing_files"]) == {"routes.txt", "trips.txt", "stop_times.txt"}:
        passed("Partial GTFS folder identifies exact missing files")
    else:
        fail(9, f"Partial GTFS status unexpected: {partial_status}")

    pd.DataFrame([{"route_id": "R1", "route_short_name": "717UP"}]).to_csv(gdir / "routes.txt", index=False)
    pd.DataFrame([{"route_id": "R1", "trip_id": "T1", "direction_id": 0}]).to_csv(gdir / "trips.txt", index=False)
    pd.DataFrame([
        {"trip_id": "T1", "stop_id": "1", "stop_sequence": 1, "arrival_time": "08:00:00", "departure_time": "08:00:00"},
        {"trip_id": "T1", "stop_id": "2", "stop_sequence": 2, "arrival_time": "08:12:00", "departure_time": "08:12:00"},
    ]).to_csv(gdir / "stop_times.txt", index=False)
    res_gtfs = search_options_with_gtfs(gdir, segs_opp, "alpha", "beta")
    if res_gtfs["options"] and res_gtfs["options"][0]["estimated_duration_min"] == 12.0 and res_gtfs["options"][0]["historical_segment_load"] == 2.0:
        passed("Valid GTFS computes real 12.0 min scheduled duration from stop_times.txt + pairs ticket load (2 pax)")
    else:
        fail(9, f"Valid GTFS search failed: {res_gtfs}")

    # Verify GTFS route_short_name without direction suffix matches and does NOT absorb unrelated routes
    segs_mix = pd.DataFrame([
        {"route": "717AUP", "direction": "up", "rank_a": 0, "rank_b": 1, "from_norm": "alpha", "to_norm": "beta", "segment_load": 50.0, "ticket_count": 40, "relative_load_index": 0.5},
        {"route": "999UP", "direction": "up", "rank_a": 0, "rank_b": 1, "from_norm": "alpha", "to_norm": "beta", "segment_load": 9999.0, "ticket_count": 8000, "relative_load_index": 0.9},
    ])
    pd.DataFrame([{"route_id": "R2", "route_short_name": "717A"}]).to_csv(gdir / "routes.txt", index=False)
    pd.DataFrame([{"route_id": "R2", "trip_id": "T1", "direction_id": 0}]).to_csv(gdir / "trips.txt", index=False)
    res_gtfs_base = search_options_with_gtfs(gdir, segs_mix, "alpha", "beta")
    if res_gtfs_base["options"] and res_gtfs_base["options"][0]["historical_segment_load"] == 50.0:
        passed("GTFS base route_short_name ('717A' + dir 0 -> '717AUP') matches cleanly without unrelated route contamination")
    else:
        fail(9, f"GTFS route matching contaminated or missed: {res_gtfs_base}")

# -------------------------------------------------------------------------
section("SEGMENT PASSENGER-LOAD CALCULATION", 10)
neg = int((segments["segment_load"] < 0).sum())
bucket_sum = (
    int(seg_meta.get("used_ticket_rows", 0))
    + int(seg_meta.get("skipped_backward_journeys", 0))
    + int(seg_meta.get("skipped_same_stop", 0))
    + int(seg_meta.get("skipped_unknown_stops", 0))
)
if neg == 0 and bucket_sum == seg_meta.get("input_rows", -1):
    passed(f"All {len(segments):,} segments non-negative; ticket buckets reconcile ({bucket_sum:,} == {seg_meta['input_rows']:,})")
else:
    fail(10, f"Segment math failure: neg={neg}, bucket_sum={bucket_sum} vs input={seg_meta.get('input_rows')}")

# Exact per-segment verification on synthetic multi-stop route A -> B -> C -> D
df_seg_test = pd.DataFrame([
    {"passenger_count": 2, "route": "500UP", "start_stop_name": "A", "end_stop_name": "D", "created_at": "2026-10-01 08:00:00+05:30"},
    {"passenger_count": 3, "route": "500UP", "start_stop_name": "A", "end_stop_name": "B", "created_at": "2026-10-01 08:01:00+05:30"},
    {"passenger_count": 5, "route": "500UP", "start_stop_name": "B", "end_stop_name": "C", "created_at": "2026-10-01 08:02:00+05:30"},
    {"passenger_count": 1, "route": "500UP", "start_stop_name": "C", "end_stop_name": "D", "created_at": "2026-10-01 08:03:00+05:30"},
    {"passenger_count": 4, "route": "500UP", "start_stop_name": "B", "end_stop_name": "D", "created_at": "2026-10-01 08:04:00+05:30"},
])
cln_s, _ = clean_with_report(df_seg_test, write_dq=False)
topo_s = build_route_topology(cln_s)
segs_s, _ = compute_segment_loads(cln_s, topo_s)
loads_map = {(r.from_norm, r.to_norm): int(r.segment_load) for r in segs_s.itertuples(index=False)}
# Expected: A->B = 2+3 = 5; B->C = 2+5+4 = 11; C->D = 2+1+4 = 7
if loads_map == {("a", "b"): 5, ("b", "c"): 11, ("c", "d"): 7}:
    passed(f"Exact segment load arithmetic verified: {loads_map}")
else:
    fail(10, f"Exact segment load mismatch: got {loads_map}, expected A->B=5, B->C=11, C->D=7")

# -------------------------------------------------------------------------
section("CROSS-ROUTE RANKING MONOTONICITY & TIME-WINDOW FILTERING", 11)
top_stops = idx["stop_norm"].tolist()[:25]
inversions = 0
multi_pairs = 0
for i in range(len(top_stops)):
    for j in range(len(top_stops)):
        if i == j:
            continue
        res = search_options_topology(tickets, segments, top_stops[i], top_stops[j], topology=topology, max_options=10)
        opts = res["options"]
        if len(opts) >= 2:
            multi_pairs += 1
            for k in range(len(opts) - 1):
                if opts[k]["mean_segment_load"] > opts[k + 1]["mean_segment_load"]:
                    inversions += 1
if multi_pairs > 0 and inversions == 0:
    passed(f"Zero cross-route mean_segment_load inversions across {multi_pairs} multi-route OD pairs")
else:
    fail(11, f"Cross-route ranking inversions={inversions} across {multi_pairs} pairs")

pk_tickets = filter_tickets_by_window(tickets, time_window="Morning Peak (08–11 IST)", day_type="Weekdays (Mon–Fri)")
md_tickets = filter_tickets_by_window(tickets, time_window="Midday (12–16 IST)", day_type="Weekends (Sat–Sun)")
pk_segs, _ = compute_segment_loads(pk_tickets, topology)
md_segs, _ = compute_segment_loads(md_tickets, topology)
if 0 < len(pk_tickets) < len(tickets) and 0 < len(md_tickets) < len(tickets) and pk_segs["segment_load"].sum() != md_segs["segment_load"].sum():
    passed(f"Time-window slicing works: Morning Peak Weekday={int(pk_segs['segment_load'].sum()):,} pax-segs vs Midday Weekend={int(md_segs['segment_load'].sum()):,} pax-segs")
else:
    fail(11, f"Time-window filtering failed: pk={len(pk_tickets)}, md={len(md_tickets)}")

# -------------------------------------------------------------------------
print("\n" + "=" * 72)
print(f"FAILURES : {len(failures)}")
for t, m in failures:
    print(f"  - TEST {t}: {m}")
print(f"WARNINGS : {len(warnings_list)}")
for w in warnings_list:
    print(f"  - {w}")
print("=" * 72)
sys.exit(0 if not failures else 1)
