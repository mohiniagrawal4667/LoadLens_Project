# LoadLens — Technical Note

**System:** Crowdedness-Aware Journey Planner & Historical Demand Engine  
**Codebase:** `app.py`, `app_pages.py`, `src/` (`data_loader.py`, `topology.py`, `load_engine.py`, `journey_planner.py`, `gtfs.py`, `analytics.py`, `ui_theme.py`)

---

## 1. Data Ingestion & Normalization (`src/data_loader.py`)

- **Supported inputs:** `.parquet`, `.pq`, and `.csv` via `LOADLENS_TICKETS`, `data/raw/`, prebuilt `data/cache/`, sidebar upload (`.streamlit/config.toml` configured with `maxUploadSize = 512`), or the bundled 25,000-row sample (`data_sample/tickets_sample.csv`).
- **Required schema:** `passenger_count`, `route`, `start_stop_name`, `end_stop_name`, `created_at`. Optional columns (`vehicle_number`, `amount`, `ticket_type_id`) degrade gracefully if absent.
- **Unique-value dictionary mapping:** `normalize_stop` and `parse_route` are computed once per unique string and mapped back onto the DataFrame, eliminating per-row `apply(pd.Series)` overhead. Calendar fields (`ticket_hour`, `ticket_dow`) use compact `int8` dtypes.
- **Timezone normalization:** `created_at` strings with offsets (`Z`, `+05:30`, etc.) are parsed as UTC and converted to naive local IST (`Asia/Kolkata`). Charts label this explicitly as ticket-creation time, not verified physical boarding time. Dataset date spans are derived dynamically from `ticket_date` min/max.
- **Stop normalization (`normalize_stop`):** Splits `"A / B"` alternate names on the left-side anchor, strips trailing terminal markers `(T)` / `(E)`, lowercases, removes non-alphanumeric characters, and expands common sign-writer abbreviations (`sation`/`stn` → `station`, `rd` → `road`, `bdr` → `border`, `ext`/`extn` → `extension`, `mkt` → `market`, `appt`/`appartment`/`appartments` → `apartment`, `distrist` → `district`, `xing` → `crossing`, `hosp` → `hospital`, etc.). Exact string matching after normalization is used by :mod:`src.gtfs` and :mod:`src.journey_planner`.
- **Exclusions & row accounting:** Rows are dropped and tracked in `dq_report` across four mutually exclusive buckets:
  1. `dropped_missing_core` (null required fields / unparseable timestamps)
  2. `dropped_invalid_stop_names` (punctuation-only / empty after normalization)
  3. `dropped_nonpositive_passenger_count` (`passenger_count <= 0`)
  4. `dropped_same_origin_and_destination` (`start_norm == end_norm`)
- **Missing `vehicle_number` handling:** Missing values are never imputed. `has_vehicle` flags presence; missing-vehicle tickets are kept separate from observed-vehicle demand denominators.

---

## 2. Route Topology Reconstruction (`src/topology.py`)

When official GTFS is supplied, `trips.txt` and `stop_times.txt` are used as the authoritative stop sequence (Section 4). When GTFS is absent, `build_route_topology_with_meta` reconstructs per-`(route, direction)` chains conservatively:

1. Build a weighted directed graph `G` per `(route, direction)` from observed `(start_norm, end_norm)` ticket counts.
2. **Disconnected components:** Identify weakly connected components (WCCs). Disconnected components are never merged into one interleaved linear sequence. If the primary WCC accounts for ≥ 75% of ticket weight, only the primary WCC is ordered (`status = "partial_disconnected"`) and minor isolated stops are excluded; otherwise the route is marked `uncertain_disconnected` and omitted from linear expansion.
3. **Cycle removal (`_acyclicise`):** Iteratively finds directed cycles (`nx.find_cycle`) and removes the deterministic minimum-weight back-edge.
4. **Chain-preserving topological sort (`_topo_chain_aware`):** Orders nodes by preferring direct successors of the previously placed stop and longest remaining directed path to a sink (`height[u]`), breaking remaining ties by incident ticket weight.
5. **Circular & ambiguous detection:**
   - Known/heavy circular routes (`OMS`/`MUDRIKA`/`RING` with `max_scc_size >= 5`, `max_scc_size >= 30` with ≥ 3 cycle edges removed, or `>= 10` nodes with `>= 15%` cycle weight) are marked `uncertain_circular` (`reliable = False`).
   - Sparse DAGs with `>= 10` stops and `< 25%` consecutive DAG reachability (`adj_reach_pct`) are marked `uncertain_ambiguous` (`reliable = False`).
   - Uncertain routes are omitted from synthetic intermediate segment expansion so passenger loads are never invented across unrelated stops; Journey Planner surfaces an explicit notice when a query matches stops on an excluded circular/uncertain route.

---

## 3. Segment Load Engine & Layered Demand Model (`src/load_engine.py`, `src/journey_planner.py`)

- **Vectorised expansion:** For each cleaned ticket on a reliable topology with `start_rank < end_rank`, `passenger_count` is added across every consecutive rank edge `[start_rank, end_rank - 1]` using NumPy `np.repeat`. Vehicle-tagged subset sums (`veh_segment_load`) are accumulated in parallel strictly for rows with `has_vehicle == True`.
- **Zero-ticket window preservation:** In `search_options_topology`, every consecutive segment `r -> r + 1` for `r in range(a, b)` is emitted (`segment_count = b - a`). Segments with zero tickets in a filtered IST window on an active route are included in the denominator (`0.0`, `obs_status = "zero_observed_in_window"`) and rendered in the stop timeline. Inactive routes in the selected window (`route_tickets == 0`) are marked insufficient data (`N/A`) rather than `"Low demand"`.
- **Time-window hour buckets (`TIME_WINDOWS`):** Morning Peak covers `08:00–11:59 IST` (`ticket_hour` 8–11), Midday covers `12:00–16:59 IST` (`12–16`), Evening Peak covers `17:00–21:59 IST` (`17–21`), and Off-Peak / Night covers `22:00–07:59 IST` (`22–23, 0–7`).
- **Four-layer demand model (never physical occupancy):**
  - **Layer A (Raw totals):** `historical_segment_load`, `mean_segment_load`, `max_segment_load`.
  - **Layer B (Daily intensity):** `avg_daily_segment_load = mean_segment_load / active_days`, using the actual number of distinct observed `ticket_date` values in the active slice.
  - **Layer C (Observed-vehicle demand):** `pax_per_observed_vehicle = mean(veh_segment_load) / distinct_vehicles`, computed strictly from `has_vehicle == True` tickets and guarded by `vehicle_coverage_pct >= 25%`, `distinct_vehicles >= 2`, and `vehicle_tickets >= 5` (otherwise `N/A`). Never assumes 1 vehicle ID = 1 trip.
  - **Layer D (Scheduled GTFS trip indicator):** `pax_per_gtfs_trip = avg_daily_segment_load / gtfs_scheduled_trips` when GTFS is active and `has_matched_load == True`.
- **Network-wide vs. within-route indicators:** Network-wide badges on Overview, Segment Explorer, and Journey Planner consistently use `network_load_percentile` (`Low < 0.40`, `Moderate 0.40–0.75`, `High >= 0.75`), while `relative_load_index` is labelled strictly as within-route bottleneck intensity.

---

## 4. GTFS-First Integration (`src/gtfs.py`)

- **Cached feed parsing:** `load_gtfs_feed` validates `stops.txt`, `routes.txt`, `trips.txt`, and `stop_times.txt` and caches parsed frames by file size + `mtime_ns` (`_load_gtfs_feed_cached`) with unique-value time string parsing.
- **Corrupt archive safety:** `extract_gtfs_zip` validates ZIP integrity and `.txt` presence cleanly without crashing on invalid archives.
- **Authoritative GTFS sequence matching:** Matches ticket `(route, direction)` onto the canonical GTFS trip's full ordered stop sequence, resolving `(start_norm, end_norm)` positions `(i, j)` with `i < j`:
  - Repeated stops creating multiple valid `(i, j)` pairs are classified as `ambiguous_stop_tickets` and excluded rather than guessed.
  - Unmatched GTFS routes (`has_matched_load == False`) carry `NaN` / `N/A` loads (never `0.0` or `"Low demand"`).
  - Partial matches (`< 50%` eligible route tickets matched onto GTFS stops) are flagged (`incomplete_coverage = True`) and ranked behind adequately matched routes so sparse matching cannot yield artificially favourable rankings.
  - Supports both `"Lowest Demand Intensity"` and `"Balanced (Demand + Time)"` (`0.65 * norm_demand + 0.35 * norm_duration`) ranking with explicit `+X.Xm` travel-time delta vs. fastest option.

---

## 5. Verification & Test Coverage

- `python audit.py`: End-to-end 11-case evaluator covering row accounting, missing `vehicle_number`, unmatched stops, forward vs. back-tracked tickets, opposite directions, duplicate/cyclic stops, empty filters, missing/partial/active GTFS, segment arithmetic, cross-route ranking monotonicity, and time-window filtering.
- `python scripts/validate.py`: Row-exclusion sum, non-negative segment loads, direction leakage, passenger-segment reconciliation, peak share, random journey traceability, and hourly totals.
- `python smoke_test.py`: Headless Streamlit `AppTest` rendering all 5 pages.
- `python tests/test_regression.py`: 15-group regression suite covering A→B→C→D, disconnected components, circular routes, ambiguous ordering, zero-demand window segments, missing vehicle IDs, corrupt/traversal GTFS ZIPs, partial/repeated-stop GTFS, missing GTFS, multi-date ranges, 100k-row performance, all 5 Streamlit pages + empty-dataset edge cases, chunked CSV math, and ordinal formatting.
