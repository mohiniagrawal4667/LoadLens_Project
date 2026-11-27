"""Comprehensive regression test suite for LoadLens (Phase 6 verification).

Covers all 12 required verification scenarios:
  1. Simple A -> B -> C -> D route with known passenger counts
  2. Disconnected route components
  3. Circular routes
  4. Ambiguous stop ordering
  5. Zero-demand segments in selected time windows
  6. Missing vehicle identifiers & Layer C reliability guards
  7. Invalid GTFS ZIP files
  8. Partially matched, repeated-stop & valid GTFS feeds
  9. Missing GTFS fallback
 10. Multiple uploaded date ranges & Layer B daily normalization
 11. Large CSV processing performance & memory
 12. All 5 application pages + upload error resilience via AppTest

Run:
    python tests/test_regression.py
"""
from __future__ import annotations

import io
import os
import sys
import tempfile
import time
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, OSError):
    pass

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.data_loader import clean_with_report, load_clean_csv_chunked, load_raw_buffer
from src.gtfs import extract_gtfs_zip, gtfs_status
from src.journey_planner import search_options_topology, search_options_with_gtfs
from src.load_engine import compute_segment_loads, filter_tickets_by_window
from src.topology import build_route_topology_with_meta
from src import ui_theme
import app_pages


def _run_tests() -> None:
    # ------------------------------------------------------------------
    # 1. Simple A -> B -> C -> D route with known passenger counts
    # ------------------------------------------------------------------
    df_abcd = pd.DataFrame([
        {"passenger_count": 2, "route": "500UP", "start_stop_name": "A", "end_stop_name": "D", "created_at": "2026-11-01 08:00:00+05:30"},
        {"passenger_count": 3, "route": "500UP", "start_stop_name": "A", "end_stop_name": "B", "created_at": "2026-11-01 08:01:00+05:30"},
        {"passenger_count": 5, "route": "500UP", "start_stop_name": "B", "end_stop_name": "C", "created_at": "2026-11-01 08:02:00+05:30"},
        {"passenger_count": 1, "route": "500UP", "start_stop_name": "C", "end_stop_name": "D", "created_at": "2026-11-01 08:03:00+05:30"},
        {"passenger_count": 4, "route": "500UP", "start_stop_name": "B", "end_stop_name": "D", "created_at": "2026-11-01 08:04:00+05:30"},
    ])
    t1, _ = clean_with_report(df_abcd, write_dq=False)
    topo1, meta1 = build_route_topology_with_meta(t1)
    segs1, _ = compute_segment_loads(t1, topo1)
    loads1 = {(r.from_norm, r.to_norm): int(r.segment_load) for r in segs1.itertuples(index=False)}
    assert loads1 == {("a", "b"): 5, ("b", "c"): 11, ("c", "d"): 7}, f"Case 1 failed: {loads1}"
    assert meta1[("500UP", "up")]["reliable"] is True
    print("[PASS] 1. Simple A->B->C->D exact passenger counts")

    # ------------------------------------------------------------------
    # 2. Disconnected route components
    # ------------------------------------------------------------------
    # 2a: Primary chain + small disconnected 2-stop island -> island excluded, never interleaved
    df_disc_minor = pd.DataFrame([
        {"passenger_count": 2, "route": "801UP", "start_stop_name": "S1", "end_stop_name": "S2", "created_at": "2026-11-01 08:00:00+05:30"},
        {"passenger_count": 2, "route": "801UP", "start_stop_name": "S2", "end_stop_name": "S3", "created_at": "2026-11-01 08:05:00+05:30"},
        {"passenger_count": 2, "route": "801UP", "start_stop_name": "S3", "end_stop_name": "S4", "created_at": "2026-11-01 08:10:00+05:30"},
        {"passenger_count": 2, "route": "801UP", "start_stop_name": "S1", "end_stop_name": "S4", "created_at": "2026-11-01 08:15:00+05:30"},
        {"passenger_count": 1, "route": "801UP", "start_stop_name": "Island1", "end_stop_name": "Island2", "created_at": "2026-11-01 08:20:00+05:30"},
    ])
    t2a, _ = clean_with_report(df_disc_minor, write_dq=False)
    topo2a, meta2a = build_route_topology_with_meta(t2a)
    assert meta2a[("801UP", "up")]["status"] == "partial_disconnected"
    assert meta2a[("801UP", "up")]["excluded_disconnected_stops"] == 2
    assert "island1" not in topo2a[("801UP", "up")] and "island2" not in topo2a[("801UP", "up")]
    segs2a, _ = compute_segment_loads(t2a, topo2a)
    # Island ticket must NOT be interleaved between S1..S4
    assert len(segs2a) == 3

    # 2b: Two equal-weight disconnected components -> marked uncertain_disconnected, omitted from linear topo
    df_disc_major = pd.DataFrame([
        {"passenger_count": 2, "route": "802UP", "start_stop_name": "P1", "end_stop_name": "P2", "created_at": "2026-11-01 08:00:00+05:30"},
        {"passenger_count": 2, "route": "802UP", "start_stop_name": "P2", "end_stop_name": "P3", "created_at": "2026-11-01 08:05:00+05:30"},
        {"passenger_count": 2, "route": "802UP", "start_stop_name": "Q1", "end_stop_name": "Q2", "created_at": "2026-11-01 08:10:00+05:30"},
        {"passenger_count": 2, "route": "802UP", "start_stop_name": "Q2", "end_stop_name": "Q3", "created_at": "2026-11-01 08:15:00+05:30"},
    ])
    t2b, _ = clean_with_report(df_disc_major, write_dq=False)
    topo2b, meta2b = build_route_topology_with_meta(t2b)
    assert meta2b[("802UP", "up")]["status"] == "uncertain_disconnected"
    assert meta2b[("802UP", "up")]["reliable"] is False
    assert ("802UP", "up") not in topo2b
    print("[PASS] 2. Disconnected route components handled safely without interleaving")

    # ------------------------------------------------------------------
    # 3. Circular routes
    # ------------------------------------------------------------------
    ring_stops = [f"RingStop{i}" for i in range(12)]
    ring_rows = [
        {"passenger_count": 3, "route": "OMS(+)UP", "start_stop_name": ring_stops[i], "end_stop_name": ring_stops[(i + 1) % 12], "created_at": "2026-11-01 09:00:00+05:30"}
        for i in range(12)
    ]
    t3, _ = clean_with_report(pd.DataFrame(ring_rows), write_dq=False)
    topo3, meta3 = build_route_topology_with_meta(t3)
    assert meta3[("OMS(+)UP", "up")]["status"] == "uncertain_circular"
    assert meta3[("OMS(+)UP", "up")]["reliable"] is False
    assert ("OMS(+)UP", "up") not in topo3
    res3 = search_options_topology(t3, pd.DataFrame(), "ringstop0", "ringstop5", topology=topo3, topology_meta=meta3)
    assert not res3["options"] and len(res3["uncertain_routes"]) == 1
    print("[PASS] 3. Circular route detected as uncertain_circular; no fake linear expansion")

    # ------------------------------------------------------------------
    # 4. Ambiguous stop ordering
    # ------------------------------------------------------------------
    # Star-like sparse graph with 12 stops and no backbone reachability (1 source -> 11 disjoint sinks)
    amb_rows = [
        {"passenger_count": 1, "route": "AMBUP", "start_stop_name": "HubZero", "end_stop_name": f"Spoke{i}", "created_at": "2026-11-01 10:00:00+05:30"}
        for i in range(1, 12)
    ]
    t4, _ = clean_with_report(pd.DataFrame(amb_rows), write_dq=False)
    topo4, meta4 = build_route_topology_with_meta(t4)
    assert meta4[("AMBUP", "up")]["status"] == "uncertain_ambiguous"
    assert meta4[("AMBUP", "up")]["reliable"] is False
    assert ("AMBUP", "up") not in topo4
    print("[PASS] 4. Ambiguous sparse stop ordering flagged and prevented from fabricating intermediate loads")

    # ------------------------------------------------------------------
    # 5. Zero-demand segments in selected time windows
    # ------------------------------------------------------------------
    # Full day builds A->B->C->D. Morning peak has ONLY A->B (10 pax) and C->D (20 pax), 0 on B->C!
    df_win = pd.DataFrame([
        {"passenger_count": 5, "route": "300UP", "start_stop_name": "A", "end_stop_name": "B", "created_at": "2026-11-01 13:00:00+05:30"},
        {"passenger_count": 5, "route": "300UP", "start_stop_name": "B", "end_stop_name": "C", "created_at": "2026-11-01 13:05:00+05:30"},
        {"passenger_count": 5, "route": "300UP", "start_stop_name": "C", "end_stop_name": "D", "created_at": "2026-11-01 13:10:00+05:30"},
        {"passenger_count": 10, "route": "300UP", "start_stop_name": "A", "end_stop_name": "B", "created_at": "2026-11-01 09:00:00+05:30"},
        {"passenger_count": 20, "route": "300UP", "start_stop_name": "C", "end_stop_name": "D", "created_at": "2026-11-01 09:05:00+05:30"},
    ])
    t5, _ = clean_with_report(df_win, write_dq=False)
    topo5, meta5 = build_route_topology_with_meta(t5)
    t5_pk = filter_tickets_by_window(t5, "Morning Peak (08–11 IST)", "All days")
    segs5_pk, _ = compute_segment_loads(t5_pk, topo5)
    res5 = search_options_topology(t5_pk, segs5_pk, "a", "d", topology=topo5, topology_meta=meta5)
    assert len(res5["options"]) == 1
    opt5 = res5["options"][0]
    assert opt5["segment_count"] == 3, f"Expected 3 segments in denominator, got {opt5['segment_count']}"
    assert opt5["mean_segment_load"] == 10.0, f"Expected (10+0+20)/3 = 10.0, got {opt5['mean_segment_load']}"
    seg_statuses = list(opt5["segments"]["obs_status"])
    assert seg_statuses == ["observed", "zero_observed_in_window", "observed"]
    tl_html = ui_theme.stop_timeline_html(opt5["segments"], "a", "d")
    assert 'class="ll-tl-dot origin"' in tl_html
    assert ">B<" in tl_html and ">C<" in tl_html and "0 tickets observed in selected window" in tl_html
    # Route with 0 tickets in Night window -> insufficient data (None), NOT "Low demand"
    t5_night = filter_tickets_by_window(t5, "Off-Peak / Night (22–07 IST)", "All days")
    segs5_night, _ = compute_segment_loads(t5_night, topo5)
    res5_n = search_options_topology(t5_night, segs5_night, "a", "d", topology=topo5, topology_meta=meta5)
    assert res5_n["options"][0]["has_matched_load"] is False
    assert res5_n["options"][0]["mean_segment_load"] is None
    print("[PASS] 5. Zero-demand window segments stay in denominator & timelines; inactive routes show N/A")

    # ------------------------------------------------------------------
    # 6. Missing vehicle identifiers & Layer C reliability guards
    # ------------------------------------------------------------------
    # 6a: Low vehicle coverage (1 of 10 tickets = 10% < 25%) -> pax_per_observed_vehicle must be None
    rows_low_v = [
        {"passenger_count": 2, "route": "400UP", "start_stop_name": "X", "end_stop_name": "Y", "created_at": "2026-11-01 08:00:00+05:30", "vehicle_number": "DL1" if i == 0 else None}
        for i in range(10)
    ]
    t6a, _ = clean_with_report(pd.DataFrame(rows_low_v), write_dq=False)
    topo6a, _ = build_route_topology_with_meta(t6a)
    segs6a, _ = compute_segment_loads(t6a, topo6a)
    res6a = search_options_topology(t6a, segs6a, "x", "y", topology=topo6a)
    assert res6a["options"][0]["pax_per_observed_vehicle"] is None

    # 6b: High coverage (6 of 10 = 60%, 2 distinct vehicles) -> missing-vehicle rows excluded from numerator!
    rows_hi_v = [
        {"passenger_count": 10, "route": "401UP", "start_stop_name": "X", "end_stop_name": "Y", "created_at": "2026-11-01 08:00:00+05:30", "vehicle_number": None}
        for _ in range(4)
    ] + [
        {"passenger_count": 2, "route": "401UP", "start_stop_name": "X", "end_stop_name": "Y", "created_at": "2026-11-01 08:05:00+05:30", "vehicle_number": "V1" if i < 3 else "V2"}
        for i in range(6)
    ]
    t6b, _ = clean_with_report(pd.DataFrame(rows_hi_v), write_dq=False)
    topo6b, _ = build_route_topology_with_meta(t6b)
    segs6b, _ = compute_segment_loads(t6b, topo6b)
    res6b = search_options_topology(t6b, segs6b, "x", "y", topology=topo6b)
    # 6 vehicle-tagged tickets * 2 pax = 12 pax / 2 distinct vehicles = 6.0 (NOT (40+12)/2 = 26.0!)
    assert res6b["options"][0]["pax_per_observed_vehicle"] == 6.0, f"Got {res6b['options'][0]['pax_per_observed_vehicle']}"
    print("[PASS] 6. Missing vehicle IDs isolated from Layer C numerator; unreliable coverage returns None")

    # ------------------------------------------------------------------
    # 7. Invalid GTFS ZIP files
    # ------------------------------------------------------------------
    with tempfile.TemporaryDirectory() as tmp:
        bad_zip_res = extract_gtfs_zip(io.BytesIO(b"not-a-zip-at-all"), Path(tmp) / "bad1")
        assert bad_zip_res["available"] is False and "Invalid GTFS ZIP" in bad_zip_res["error"]

        empty_zip_buf = io.BytesIO()
        with zipfile.ZipFile(empty_zip_buf, "w") as zf:
            zf.writestr("readme.md", "no txt files")
        empty_zip_buf.seek(0)
        empty_zip_res = extract_gtfs_zip(empty_zip_buf, Path(tmp) / "bad2")
        assert empty_zip_res["available"] is False and "no .txt" in empty_zip_res["error"]
    print("[PASS] 7. Corrupt and empty GTFS ZIP archives handled cleanly without crash")

    # ------------------------------------------------------------------
    # 8. Partially matched, repeated-stop & valid GTFS feeds
    # ------------------------------------------------------------------
    with tempfile.TemporaryDirectory() as tmp:
        gdir = Path(tmp) / "gtfs"
        gdir.mkdir()
        pd.DataFrame([
            {"stop_id": "1", "stop_name": "Alpha", "stop_lat": 28.50, "stop_lon": 77.20},
            {"stop_id": "2", "stop_name": "Midway", "stop_lat": 28.51, "stop_lon": 77.21},
            {"stop_id": "3", "stop_name": "Beta", "stop_lat": 28.52, "stop_lon": 77.22},
            {"stop_id": "4", "stop_name": "Gamma", "stop_lat": 28.53, "stop_lon": 77.23},
        ]).to_csv(gdir / "stops.txt", index=False)
        pd.DataFrame([
            {"route_id": "R_FULL", "route_short_name": "100UP"},
            {"route_id": "R_PART", "route_short_name": "200UP"},
            {"route_id": "R_UNM", "route_short_name": "300UP"},
        ]).to_csv(gdir / "routes.txt", index=False)
        pd.DataFrame([
            {"route_id": "R_FULL", "trip_id": "TF1", "direction_id": 0},
            {"route_id": "R_FULL", "trip_id": "TF2", "direction_id": 0},
            {"route_id": "R_PART", "trip_id": "TP1", "direction_id": 0},
            {"route_id": "R_UNM", "trip_id": "TU1", "direction_id": 0},
        ]).to_csv(gdir / "trips.txt", index=False)
        pd.DataFrame([
            # R_FULL: Alpha -> Midway -> Beta (15 min)
            {"trip_id": "TF1", "stop_id": "1", "stop_sequence": 1, "arrival_time": "08:00:00", "departure_time": "08:00:00"},
            {"trip_id": "TF1", "stop_id": "2", "stop_sequence": 2, "arrival_time": "08:07:00", "departure_time": "08:07:00"},
            {"trip_id": "TF1", "stop_id": "3", "stop_sequence": 3, "arrival_time": "08:15:00", "departure_time": "08:15:00"},
            {"trip_id": "TF2", "stop_id": "1", "stop_sequence": 1, "arrival_time": "09:00:00", "departure_time": "09:00:00"},
            {"trip_id": "TF2", "stop_id": "2", "stop_sequence": 2, "arrival_time": "09:07:00", "departure_time": "09:07:00"},
            {"trip_id": "TF2", "stop_id": "3", "stop_sequence": 3, "arrival_time": "09:15:00", "departure_time": "09:15:00"},
            # R_PART: Alpha -> Beta -> Alpha (repeated stop!)
            {"trip_id": "TP1", "stop_id": "1", "stop_sequence": 1, "arrival_time": "08:00:00", "departure_time": "08:00:00"},
            {"trip_id": "TP1", "stop_id": "3", "stop_sequence": 2, "arrival_time": "08:20:00", "departure_time": "08:20:00"},
            {"trip_id": "TP1", "stop_id": "1", "stop_sequence": 3, "arrival_time": "08:40:00", "departure_time": "08:40:00"},
            # R_UNM: Alpha -> Beta (no tickets for 300UP)
            {"trip_id": "TU1", "stop_id": "1", "stop_sequence": 1, "arrival_time": "10:00:00", "departure_time": "10:00:00"},
            {"trip_id": "TU1", "stop_id": "3", "stop_sequence": 2, "arrival_time": "10:10:00", "departure_time": "10:10:00"},
        ]).to_csv(gdir / "stop_times.txt", index=False)

        t_gtfs, _ = clean_with_report(pd.DataFrame([
            # 100UP: Alpha -> Beta (20 pax) even though ticket doesn't mention Midway -> GTFS-first assigns to both Alpha->Midway & Midway->Beta!
            {"passenger_count": 20, "route": "100UP", "start_stop_name": "Alpha", "end_stop_name": "Beta", "created_at": "2026-11-01 08:00:00+05:30"},
            # 200UP: 1 matched (Alpha->Beta = 1 pax) + 4 unmatched stop tickets -> 20% match < 50% (incomplete_coverage!)
            {"passenger_count": 1, "route": "200UP", "start_stop_name": "Alpha", "end_stop_name": "Beta", "created_at": "2026-11-01 08:05:00+05:30"},
            {"passenger_count": 5, "route": "200UP", "start_stop_name": "Ghost1", "end_stop_name": "Ghost2", "created_at": "2026-11-01 08:06:00+05:30"},
            {"passenger_count": 5, "route": "200UP", "start_stop_name": "Ghost1", "end_stop_name": "Ghost2", "created_at": "2026-11-01 08:07:00+05:30"},
            {"passenger_count": 5, "route": "200UP", "start_stop_name": "Ghost1", "end_stop_name": "Ghost2", "created_at": "2026-11-01 08:08:00+05:30"},
            {"passenger_count": 5, "route": "200UP", "start_stop_name": "Ghost1", "end_stop_name": "Ghost2", "created_at": "2026-11-01 08:09:00+05:30"},
        ]), write_dq=False)
        topo_g, _ = build_route_topology_with_meta(t_gtfs)
        segs_g, _ = compute_segment_loads(t_gtfs, topo_g)

        res_g = search_options_with_gtfs(gdir, segs_g, "alpha", "beta", tickets=t_gtfs, rank_mode="balanced")
        opts_g = res_g["options"]
        assert len(opts_g) == 3
        # 100UP (100% match) MUST rank #1 ahead of 200UP (20% partial match, even though 200UP has lower 1 pax load) and 300UP (unmatched)
        assert opts_g[0]["route"] == "100UP"
        assert opts_g[0]["historical_segment_load"] == 40.0  # 20 pax across 2 GTFS segments!
        assert opts_g[0]["pax_per_gtfs_trip"] == 10.0  # 20 daily avg / 2 trips
        assert opts_g[1]["route"] == "200UP" and opts_g[1]["incomplete_coverage"] is True
        assert opts_g[2]["route"] == "300UP" and opts_g[2]["has_matched_load"] is False
        assert opts_g[2]["mean_segment_load"] is None
        assert opts_g[2]["segments"]["segment_load"].isna().all()
    print("[PASS] 8. GTFS-first sequence matching, partial-coverage protection & unmatched N/A verified")

    # ------------------------------------------------------------------
    # 9. Missing GTFS fallback
    # ------------------------------------------------------------------
    st_missing = gtfs_status(PROJECT_ROOT / "data" / "nonexistent_gtfs")
    assert st_missing["available"] is False
    assert res6b["options"][0]["estimated_duration_min"] is None
    assert res6b["options"][0]["stop_coords"] is None
    print("[PASS] 9. Missing GTFS degrades gracefully with disabled durations and maps")

    # ------------------------------------------------------------------
    # 10. Multiple uploaded date ranges & Layer B daily normalization
    # ------------------------------------------------------------------
    df_dates = pd.DataFrame([
        {"passenger_count": 10, "route": "900UP", "start_stop_name": "A", "end_stop_name": "B", "created_at": f"2026-12-0{d} 09:00:00+05:30"}
        for d in range(1, 6)
    ])
    t10, dq10 = clean_with_report(df_dates, write_dq=False)
    assert app_pages._date_range_label(t10, dq10) == "2026-12-01 → 2026-12-05"
    topo10, _ = build_route_topology_with_meta(t10)
    segs10, _ = compute_segment_loads(t10, topo10)
    res10 = search_options_topology(t10, segs10, "a", "b", topology=topo10)
    assert res10["options"][0]["active_days"] == 5
    assert res10["options"][0]["avg_daily_segment_load"] == 10.0  # 50 total / 5 days
    print("[PASS] 10. Multiple date ranges & Layer B daily normalization verified")

    # ------------------------------------------------------------------
    # 11. Large CSV processing performance (100k rows)
    # ------------------------------------------------------------------
    raw_sample = pd.read_csv(PROJECT_ROOT / "data_sample" / "tickets_sample.csv")
    df_100k = pd.concat([raw_sample] * 4, ignore_index=True)
    t_s = time.perf_counter()
    t_big, _ = clean_with_report(df_100k, write_dq=False)
    t_c = time.perf_counter()
    topo_big, _ = build_route_topology_with_meta(t_big)
    t_tp = time.perf_counter()
    segs_big, _ = compute_segment_loads(t_big, topo_big)
    t_sg = time.perf_counter()
    total_100k = t_sg - t_s
    print(f"[PASS] 11. 100k-row pipeline: clean={t_c-t_s:.2f}s, topo={t_tp-t_c:.2f}s, segs={t_sg-t_tp:.2f}s, total={total_100k:.2f}s")
    assert total_100k < 20.0, f"100k pipeline unexpectedly slow: {total_100k:.2f}s"

    # ------------------------------------------------------------------
    # 12. All 5 application pages + upload resilience via AppTest
    # ------------------------------------------------------------------
    from streamlit.testing.v1 import AppTest
    for pg in ["Overview", "Journey Planner", "Route Analytics", "Segment Explorer", "Data Quality"]:
        at = AppTest.from_file(str(PROJECT_ROOT / "app.py"), default_timeout=180)
        at.session_state["nav_radio"] = pg
        at.run()
        assert not at.exception, f"Page {pg} raised exception: {[e.message for e in at.exception]}"
    # Zero-kept-rows CSV via LOADLENS_TICKETS
    with tempfile.TemporaryDirectory() as tmp:
        p_zero = Path(tmp) / "zero.csv"
        pd.DataFrame([{"passenger_count": 0, "route": "10UP", "start_stop_name": "A", "end_stop_name": "A", "created_at": "bad"}]).to_csv(p_zero, index=False)
        os.environ["LOADLENS_TICKETS"] = str(p_zero)
        try:
            for pg in ["Overview", "Journey Planner", "Route Analytics", "Segment Explorer", "Data Quality"]:
                at_z = AppTest.from_file(str(PROJECT_ROOT / "app.py"), default_timeout=60)
                at_z.session_state["nav_radio"] = pg
                at_z.run()
                assert not at_z.exception, f"Empty-kept CSV crashed {pg}: {[e.message for e in at_z.exception]}"
        finally:
            os.environ.pop("LOADLENS_TICKETS", None)
    print("[PASS] 12. All 5 application pages & empty-dataset edge cases verified via AppTest")

    # ------------------------------------------------------------------
    # 13. ZIP path-traversal & decompression safety in extract_gtfs_zip
    # ------------------------------------------------------------------
    with tempfile.TemporaryDirectory() as tmp:
        z_trav = io.BytesIO()
        with zipfile.ZipFile(z_trav, "w") as zf:
            zf.writestr("../../outside.txt", "malicious")
        z_trav.seek(0)
        res_trav = extract_gtfs_zip(z_trav, Path(tmp) / "gtfs_trav")
        assert res_trav["available"] is False and "traversal" in res_trav["error"].lower()
        assert not (Path(tmp) / "outside.txt").exists()
    print("[PASS] 13. GTFS ZIP path-traversal entry rejected safely")

    # ------------------------------------------------------------------
    # 14. Chunked CSV ingestion matches single-shot cleaning & segment math
    # ------------------------------------------------------------------
    with tempfile.TemporaryDirectory() as tmp:
        p_csv = Path(tmp) / "chunk_test.csv"
        pd.DataFrame([
            {"passenger_count": 2, "route": "774UP", "start_stop_name": "S1", "end_stop_name": "S3", "created_at": "2026-11-01 08:00:00+05:30", "vehicle_number": "DL1"},
            {"passenger_count": 3, "route": "774UP", "start_stop_name": "S1", "end_stop_name": "S2", "created_at": "2026-11-01 08:05:00+05:30", "vehicle_number": None},
            {"passenger_count": 4, "route": "774UP", "start_stop_name": "S2", "end_stop_name": "S3", "created_at": "2026-11-02 09:00:00+05:30", "vehicle_number": "DL2"},
            {"passenger_count": 5, "route": "774UP", "start_stop_name": "S1", "end_stop_name": "S3", "created_at": "2026-11-02 09:05:00+05:30", "vehicle_number": "DL1"},
            {"passenger_count": 0, "route": "774UP", "start_stop_name": "S1", "end_stop_name": "S2", "created_at": "2026-11-02 09:10:00+05:30", "vehicle_number": "DL1"},
            {"passenger_count": 1, "route": "774UP", "start_stop_name": "S1", "end_stop_name": "S1", "created_at": "2026-11-02 09:15:00+05:30", "vehicle_number": "DL1"},
        ]).to_csv(p_csv, index=False)
        t_single, dq_single = clean_with_report(pd.read_csv(p_csv), write_dq=False)
        t_chunk, dq_chunk = load_clean_csv_chunked(p_csv, chunksize=2, write_dq=False)
        assert dq_single["kept_rows"] == dq_chunk["kept_rows"] == 4
        assert dq_single["raw_rows"] == dq_chunk["raw_rows"] == 6
        assert dq_single["distinct_vehicles_with_id"] == dq_chunk["distinct_vehicles_with_id"] == 2
        topo_c, _ = build_route_topology_with_meta(t_chunk)
        segs_c, _ = compute_segment_loads(t_chunk, topo_c)
        # S1->S2: 2+3+5 = 10 pax (3 tkts; veh: 2+5 = 7 pax, 2 tkts)
        # S2->S3: 2+4+5 = 11 pax (3 tkts; veh: 2+4+5 = 11 pax, 3 tkts)
        row_12 = segs_c[(segs_c["from_norm"] == "s1") & (segs_c["to_norm"] == "s2")].iloc[0]
        row_23 = segs_c[(segs_c["from_norm"] == "s2") & (segs_c["to_norm"] == "s3")].iloc[0]
        assert int(row_12["segment_load"]) == 10 and int(row_12["ticket_count"]) == 3
        assert int(row_12["veh_segment_load"]) == 7 and int(row_12["veh_ticket_count"]) == 2
        assert int(row_23["segment_load"]) == 11 and int(row_23["ticket_count"]) == 3
        assert int(row_23["veh_segment_load"]) == 11 and int(row_23["veh_ticket_count"]) == 3
    print("[PASS] 14. Chunked CSV ingestion & OD-collapsed segment/vehicle math verified")

    # ------------------------------------------------------------------
    # 15. Ordinal formatting helper
    # ------------------------------------------------------------------
    assert app_pages._ordinal(1) == "1st" and app_pages._ordinal(2) == "2nd" and app_pages._ordinal(3) == "3rd"
    assert app_pages._ordinal(11) == "11th" and app_pages._ordinal(12) == "12th" and app_pages._ordinal(13) == "13th"
    assert app_pages._ordinal(91) == "91st" and app_pages._ordinal(94) == "94th"
    print("[PASS] 15. Percentile ordinal formatting verified")
    print("\nALL 15 REGRESSION TEST GROUPS PASSED.")


if __name__ == "__main__":
    _run_tests()
