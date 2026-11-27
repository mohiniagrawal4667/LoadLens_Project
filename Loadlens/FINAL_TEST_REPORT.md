# LoadLens — Final Test Report

> **Test Execution Date:** 2026-11-27  
> **Scope:** All automated suites and live Chromium browser verification executed **after the final Phase 9 code edits**.

---

## 1. Automated Test Suite Results

| Suite / Check | Command / Driver | Status | Verified Output Summary |
|---|---|---|---|
| **Evaluator & Edge-Case Suite** | `python audit.py` | **PASS** | `FAILURES : 0`, `WARNINGS : 0`; `25,000` sample rows reconciled (`24,215` forward + `24` backward + `761` uncertain/disconnected); `2,793` segments non-negative; `0` ranking inversions across `171` multi-route OD pairs; IST conversion, missing `vehicle_number`, opposite directions, duplicate/cyclic stops, missing/partial/active GTFS, and window slicing all passed. |
| **Validation Suite** | `python scripts\validate.py` | **PASS** | All `7/7` checks passed: row accounting delta `0`, min/max/mean segment loads (`1` / `450` / `115.21`), direction order check, `321,793` pax-segments across `26,938` pax-journeys (`avg 11.95` segs), `71.4%` peak share, random journey traceability, hourly sum `26,938 == 26,938`. |
| **Streamlit Smoke Test** | `python smoke_test.py` | **PASS** | All `5` pages rendered via `AppTest` with `0` exceptions: `Overview` (`md=8, plotly=3`), `Route Analytics` (`md=10, df=1, plotly=6`), `Segment Explorer` (`md=14, df=1, plotly=2`), `Journey Planner` (`md=13, df=3, plotly=3`), `Data Quality` (`md=12, df=2, plotly=2`). |
| **15-Group Regression Suite** | `python tests\test_regression.py` | **PASS** | `ALL 15 REGRESSION TEST GROUPS PASSED.` Covers A→B→C→D math, disconnected islands & fragmented graphs, circular routes, ambiguous DAGs, zero-demand window segments & origin dot (`ll-tl-dot origin`), missing `vehicle_number` Layer C guards, corrupt/empty GTFS ZIPs, GTFS sequence/partial/repeated-stop matching, missing GTFS fallback, multi-date `_date_range_label` (`→`), 100k performance (`2.91s`), 5-page + empty-CSV `AppTest`, ZIP path-traversal rejection (Case 13), chunked CSV vs. single-shot + OD-collapsed math (Case 14), and `_ordinal` formatting (Case 15). |
| **Naive $L_s$ Brute-Force Proof** | Inline Python verification vs. `compute_segment_loads` | **PASS** | Bit-for-bit equality across all `2,793` segments on `tickets_sample.csv` (`MATH_PROOF_EXACT`). |
| **250k Chunked vs. Single-Shot CSV Benchmark** | Inline Python + `tracemalloc` on `43.4 MB` CSV | **PASS** | Identical `kept_rows` (`250,000`) and `distinct_vehicles_with_id`; chunked(`50k`) ran in `57.79s` / `143.2 MB` peak vs. single-shot `133.99s` / `177.3 MB` peak. |
| **Journey Planner Interactive `AppTest` (13 flows)** | Inline `AppTest` + `test_gtfs_flows.py` | **PASS** | Verified `ov_go_jp`, `Badarpur Border → Kalkaji Mandir` (3 options), `jp_active_trace`, `TIME_WINDOWS`, `DAY_TYPES`, `jp_swap`, invalid/same/empty stops, GTFS active mode, `Lowest Demand Intensity` vs. `Balanced (Demand + Time)`, and `Route Geometry` map. |

---

## 2. Live Browser Visual QA (`http://localhost:8501`)

Verified in live Chromium against the running Streamlit server:

| Check | Status | Notes |
|---|---|---|
| All 5 pages render, CSS injection (`st.html`), dark `#070910` grid, fonts, telemetry sidebar | **PASS** | `0` console/page errors, `0` `.stException` tracebacks, `0` `"undefined"` Plotly titles, sidebar active cyan dot clear of label text. |
| Horizontal tracer (`.ll-tracer-track`) & corridor (`.ll-corridor`) scrolling | **PASS** | Both scroll cleanly inside their containers without page overflow. |
| Responsive breakpoints (`1080px`, `860px`, `720px`) | **PASS** | `0` horizontal page overflow across tested viewports; `.ll-hud-strip` and `.ll-kpi-grid` reflowed cleanly. |
| Browser file uploads (`tickets_sample.csv`, `sample_gtfs.zip`) | **PASS** | Both uploaded via sidebar; `SYSTEM TELEMETRY` updated to `Uploaded: tickets_sample.csv` and `MODE · ACTIVE · GTFS-FIRST`; GTFS durations and `Route Geometry` map rendered. |
| Post-Phase-9 `⇄` swap & ordinal suffixes (`Badarpur Border → Kalkaji Mandir`) | **PASS** | Clicking `⇄` updated both visible `Boarding stop` (`Kalkaji Mandir`) and `Destination stop` (`Badarpur Border`) labels and rendered `3` reverse corridors (`#1 · 774DOWN`, `#2 · 433UP`, `#3 · 511ADOWN`); ordinals rendered cleanly (`71st`, `73rd`, `95th`, `96th`). |

---

## 3. Skipped / Unverified Scope & Remaining Risks

| Item | Status | Reason |
|---|---|---|
| Full ~290 MB (~2.56M rows) runtime/memory test | **NOT RUN** | Full raw dataset is not in the repository; benchmarked up to `250,000` rows. |
| `Dockerfile` image build & cloud deploy | **NOT RUN** | Container build / external cloud deployment was not executed in this local verification pass. |
| Dependency CVE scan (`pip-audit`) | **NOT RUN** | `pip-audit` tool not installed in Python environment. |
| Browser `.parquet` upload via UI widget | **NOT RUN** | `.csv` and GTFS `.zip` uploaded in browser; `.parquet` ingestion tested in Python (`data_loader.py`). |
| CARTO map tile imagery in restricted network | **OBSERVATION** | `Route Geometry` markers/controls render cleanly; external map tiles appear solid dark gray when tile network access is restricted/slow. |
