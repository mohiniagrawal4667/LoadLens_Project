# Final Evaluation After Fixes — LoadLens

## 1. Bugs Fixed
1. **Corrupt GTFS ZIP crash (`app.py`, `src/gtfs.py`):** `extract_gtfs_zip` now catches `zipfile.BadZipFile` / empty `.zip` archives cleanly and `app.py` wraps extraction in `try/except`, displaying a clean sidebar error without crashing.
2. **Route topology interleaving & circular ring distortion (`src/topology.py`):**
   - Replaced hub-weight tie-breaking (`_topo_with_ties`) with longest-path & successor-preserving topological sorting (`_topo_chain_aware`).
   - Disconnected islands are excluded (`partial_disconnected`: e.g. `801-IGI-INDDOWN` keeps its 51-stop primary chain and excludes 2 isolated stops) rather than interleaved; severely fragmented graphs (`uncertain_disconnected`), circular ring routes (`uncertain_circular`: `OMS(+)UP`, `OMS(-)DOWN`), and low-reachability sparse graphs (`uncertain_ambiguous`) are omitted from linear multi-hop segment expansion.
3. **Time-window zero-demand omission & denominator inflation (`src/journey_planner.py`, `src/ui_theme.py`):**
   - `search_options_topology` emits every consecutive segment `r -> r + 1` in `[a, b)`, so `mean_segment_load` divides by the full `b - a` span.
   - `stop_timeline_html` keeps all intermediate stops visible with explicit `"0 tickets observed in selected window"` status.
   - Inactive routes in a filtered time window (`route_tickets == 0`) show `N/A` / insufficient data instead of `"0 pax · Low demand"`.
4. **GTFS partial-match & unmatched route misrepresentation (`src/gtfs.py`, `app_pages.py`, `src/ui_theme.py`):**
   - Unmatched GTFS routes carry `NaN`/`N/A` loads (never `0.0` or `"Low demand"`).
   - Partial ticket-to-GTFS matches (`< 50%` stop match) are flagged (`incomplete_coverage = True`) and ranked behind adequately matched routes.
5. **Cross-page demand-tier inconsistency & hardcoded dates (`app_pages.py`, `src/analytics.py`):**
   - Overview's "High-demand segment highlights" and Segment Explorer's segment tiers now use `network_load_percentile` (matching Journey Planner), while `RLI` is labelled strictly as within-route bottleneck intensity.
   - Hardcoded `"October 2026"` labels were replaced with dynamic `_date_range_label(tickets, dq)`.
6. **UI upload limit (`.streamlit/config.toml`):** Set `server.maxUploadSize = 512` (previously unconfigured 200 MB default).

---

## 2. Features Improved
- **GTFS-First Authoritative Sequencing (`src/gtfs.py`):** Matches ticket `(start_norm, end_norm)` directly onto the canonical GTFS trip's ordered stop sequence (`stop_times.txt`), handles repeated stops safely (excluding ambiguous multi-pair matches), and offers `"Lowest Demand Intensity"` vs. `"Balanced (Demand + Time)"` ranking with `+X.Xm` travel-time delta vs. fastest option.
- **Layered Demand Model (`src/load_engine.py`, `src/journey_planner.py`, `src/gtfs.py`):**
  - **Layer A:** Raw passenger-segment totals (`historical_segment_load`, `mean_segment_load`, `max_segment_load`).
  - **Layer B:** Average daily segment demand (`avg_daily_segment_load`) divided by actual observed `active_days`.
  - **Layer C:** Demand per observed vehicle (`pax_per_observed_vehicle`), computed strictly from `has_vehicle == True` tickets and guarded by reliability thresholds (`>= 25%` coverage, `>= 2` distinct vehicles, `>= 5` tagged tickets; otherwise `N/A`).
  - **Layer D:** Daily demand per scheduled GTFS trip (`pax_per_gtfs_trip`) when GTFS is active.
- **Data Quality & Topology Diagnostics (`app_pages.py`, `src/topology.py`):** Added topology reliability summaries (`confident`, `partial_disconnected`, `uncertain_circular`, etc.) in Data Quality and Segment Explorer, plus uncertain-route notices in Journey Planner.

---

## 3. Tests Executed & Actual Results

All suites below were executed after all final code and documentation edits:

| Test Suite | Command | Result | Key Observed Output |
|---|---|---|---|
| **Evaluator Suite** | `python audit.py` | **PASS** | `FAILURES : 0`, `WARNINGS : 0`; `24,215` forward + `24` backward + `761` excluded uncertain/disconnected + `0` same = `25,000` sample rows; `2,793` segments; `0` ranking inversions across `171` multi-route OD pairs. |
| **Streamlit Smoke Test** | `python smoke_test.py` | **PASS** | All 5 pages (`Overview`, `Route Analytics`, `Segment Explorer`, `Journey Planner`, `Data Quality`) rendered via `AppTest` with `0` exceptions. |
| **Validation Suite** | `python scripts/validate.py` | **PASS** | All 7 checks passed (`321,793` pax-segments, `26,938` pax-journeys, `avg segments = 11.95`, `71.4%` peak share, hourly totals `26,938 == 26,938`). |
| **12-Case Regression Suite** | `python tests/test_regression.py` | **PASS** | All 12 test groups passed (A→B→C→D, disconnected components, circular routes, ambiguous ordering, zero-demand window segments, missing vehicle IDs, corrupt/empty GTFS ZIPs, partial/repeated-stop GTFS, missing GTFS, multi-date ranges, 100k performance, all 5 AppTest pages + empty CSV). |

---

## 4. Performance Measurements

| Benchmark | Before Fixes | After Fixes | Notes |
|---|---|---|---|
| **25,000 rows (`tickets_sample.csv`)** (`tracemalloc` active) | `clean=7.77s`, `total=8.92s`, `peak_mem=89.0 MB` | `clean=3.72s`, `topo=3.69s`, `segs=0.99s`, `total=8.41s`, `peak_mem=55.0 MB` | `-52%` clean time, `-38%` peak traced memory (`tracemalloc` adds overhead to graph loops). |
| **100,000 rows (4x sample, no `tracemalloc`)** | `clean=10.92s`, `topo=0.34s`, `segs=0.42s`, `total=11.68s` | `clean=3.10s`, `topo=0.76s`, `segs=1.15s`, `total=5.01s` | `-71.6%` clean time, `-57.1%` total pipeline time via unique-value dict mapping. |
| **Caching in UI (`app_pages.py`, `src/gtfs.py`)** | Re-parsed GTFS CSVs & recomputed windowed segments on every interaction | Cached via `_load_gtfs_feed_cached` (size + `mtime_ns`), `_cached_stop_index`, `_cached_window_slice` | Prevents redundant recomputation across UI widget interactions. |

---

## 5. Remaining Limitations & Unverified Scope
- **Full ~290 MB dataset (~2.5M rows) not tested directly:** Neither the full raw CSV nor `data/cache/` Parquet files were present in the workspace, so full-dataset runtime and memory behavior were not measured directly (only benchmarked up to 100,000 rows).
- **Live browser socket rendering blocked in sandbox:** Probing `http://127.0.0.1:8599` from the evaluation environment failed with `WinError 10013` (sandbox socket restriction). All UI pages, navigation, callbacks, and error states were verified headlessly via Streamlit `AppTest`.
- **Direct (0-transfer) routes only:** Multi-leg transfer routing is not implemented.
- **No trip-level clustering or live occupancy:** Without verified trip IDs on ticket rows (and with `vehicle_number` missing on ~44.7% of the sample), LoadLens reports historical demand intensity and per-observed-vehicle demand on vehicle-tagged subsets, never physical seat occupancy or real-time crowding.
- **Static GTFS `calendar.txt` not required:** Scheduled GTFS trip counts (`trips.txt`) are not filtered by active day-of-week `service_id` when `calendar.txt` is absent.

---

## 6. Incomplete Features
- 1-transfer / multi-leg crowdedness-aware journey routing.
- Vehicle run / trip-ID clustering from `vehicle_number` + `created_at` timestamps.
- `calendar.txt` / `frequencies.txt` parsing for day-specific scheduled trip counts in GTFS mode.
- Live GTFS-RT vehicle/occupancy feed ingestion.
