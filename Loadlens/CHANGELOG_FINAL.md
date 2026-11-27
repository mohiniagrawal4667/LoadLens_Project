# CHANGELOG — Final Improvement & Submission-Readiness Build

## Summary of Changes

### 1. Data & Mathematical Correctness
- **Chain-preserving topology & uncertainty guards (`src/topology.py`):**
  - Replaced hub-weight tie-breaking (`_topo_with_ties`) with longest-path & direct-successor topological ordering (`_topo_chain_aware`) to eliminate geographic interleaving on linear routes (e.g., `717DOWN` Dwarka stops).
  - Separated disconnected components cleanly: minor disconnected islands (`partial_disconnected`, e.g., `801-IGI-INDDOWN`) are excluded rather than interleaved; severely fragmented graphs (`uncertain_disconnected`), circular/ring routes (`uncertain_circular`, e.g., `OMS(+)UP`, `OMS(-)DOWN`), and sparse ambiguous graphs (`uncertain_ambiguous`) are flagged in `topology_meta` and excluded from synthetic multi-hop segment expansion.
- **Time-window zero-demand segment preservation (`src/journey_planner.py`, `src/ui_theme.py`):**
  - `search_options_topology` now emits all consecutive segments `r -> r + 1` across `r in [a, b)` so `mean_segment_load` divides by the true `b - a` segment span rather than only non-zero segments.
  - `stop_timeline_html` keeps all intermediate stops visible with explicit `"0 tickets observed in selected window"` vs `"N/A"` status labels.
  - Routes with zero tickets across the entire selected time window are marked `has_matched_load = False` (`N/A` / insufficient data) instead of `"0 pax · Low demand"`.
- **Four-layer demand model (`src/load_engine.py`, `src/journey_planner.py`, `src/gtfs.py`):**
  - **Layer A:** Raw passenger-segment totals (`historical_segment_load`, `mean_segment_load`, `max_segment_load`).
  - **Layer B:** Average daily segment demand (`avg_daily_segment_load`) divided by actual observed `active_days`.
  - **Layer C:** Demand per observed vehicle (`pax_per_observed_vehicle`) computed strictly on vehicle-tagged rows (`has_vehicle == True`) and guarded by reliability thresholds (`>= 25%` coverage, `>= 2` distinct vehicles, `>= 5` tagged tickets; otherwise `N/A`).
  - **Layer D:** Scheduled-trip-normalized daily demand (`pax_per_gtfs_trip`) when GTFS is active.

### 2. GTFS-First Integration
- **Authoritative GTFS sequence matching (`src/gtfs.py`):**
  - Ticket OD pairs are matched directly against the canonical GTFS trip's full ordered stop sequence (`stop_times.txt`) for the corresponding route and direction.
  - Repeated stops creating ambiguous multiple valid `(i, j)` pairs are excluded (`ambiguous_stop_tickets`) rather than guessed.
  - Unmatched GTFS routes carry `NaN`/`N/A` demand (never `0.0` or `"Low demand"`).
  - Partial ticket-to-GTFS matches (`< 50%` stop match) are flagged (`incomplete_coverage = True`) and ranked behind adequately matched routes.
  - Added optional `"Balanced (Demand + Time)"` ranking mode alongside `"Lowest Demand Intensity"` with `+X.Xm` travel-time trade-off deltas.

### 3. Performance & Scalability
- **Unique-value dictionary mapping (`src/data_loader.py`):**
  - `parse_route` and `normalize_stop` now run once per unique value instead of per-row `.map(...).apply(pd.Series)`, cutting 100k-row `clean_with_report` runtime from `10.92s` to `4.09s` and reducing 25k-row peak traced memory from `89.0 MB` to `55.0 MB`.
  - Calendar integer helper columns (`ticket_hour`, `ticket_dow`) downcast to `int8`.
- **Caching (`src/gtfs.py`, `app_pages.py`):**
  - Cached GTFS feed parsing (`_load_gtfs_feed_cached`) by file size + `mtime_ns` and unique time-string parsing.
  - Added `@st.cache_data` wrappers `_cached_stop_index` and `_cached_window_slice` keyed by `dataset_sig` so UI filter interactions do not recompute full DataFrames on every rerun.
  - Filtered `tickets` to candidate routes before `route_vehicle_reliability_stats` in `search_options_topology`.

### 4. UI, Reliability & Data Integrity Fixes
- **Safe GTFS ZIP extraction (`src/gtfs.py`, `app.py`):** Wrapped `extract_gtfs_zip` with `BadZipFile` / empty-archive validation and `try/except` in `app.py` so bad ZIP uploads surface a clean error without crashing.
- **Upload limit (`.streamlit/config.toml`):** Set `server.maxUploadSize = 512` to support ~290 MB CSV uploads while capping memory exposure.
- **Dynamic dataset dates (`app_pages.py`):** Replaced hardcoded `"October 2026"` labels with `_date_range_label(tickets, dq)`.
- **Consistent demand tiers (`app_pages.py`, `src/analytics.py`, `src/ui_theme.py`):** Unified network-wide badges across Overview, Segment Explorer, and Journey Planner onto `network_load_percentile`, kept `RLI` explicitly labelled as within-route peak intensity, and added topology diagnostic tables to Data Quality and Segment Explorer.

### 5. Regression Verification
- Added `tests/test_regression.py` covering all 12 required verification scenarios.
- Updated `README.md` and `TECHNICAL_NOTE.md` to match implemented behavior.
