# LoadLens — Final Architecture Audit

> **Audit Date:** 2026-11-27  
> **Repository:** `C:\Users\Asus\Desktop\Loadlens`  
> **Git State:** Initialized local Git repository; baseline checkpoint `a6f9069`, pre-Phase-9 checkpoint `8de71ef`, working tree contains final verified engineering fixes and documentation.

---

## 1. Folder Structure

```text
Loadlens/
├── app.py                              # Main Streamlit entrypoint, sidebar rail, cache/upload bootstrap, page router
├── app_pages.py                        # Five Streamlit page renderers + Plotly dark theme & callbacks
├── audit.py                            # 11-section strict evaluator & edge-case suite
├── smoke_test.py                       # Headless Streamlit AppTest check across all 5 pages
├── requirements.txt                    # Pinned Python dependencies (8 packages)
├── Dockerfile                          # Container build & healthcheck for port 8501
├── .dockerignore                       # Excludes raw data, caches, backups, and .git from container image
├── .env.example                        # Documents optional LOADLENS_TICKETS environment variable
├── .gitignore                          # Excludes .env, caches, raw datasets, GTFS sinks, logs
├── .streamlit/config.toml              # Dark theme tokens, maxUploadSize = 512 MB, gatherUsageStats = false
├── run.bat / run.sh                    # Single-command Windows / POSIX launchers
├── README.md / PROPOSAL.md / TECHNICAL_NOTE.md
├── CHANGELOG_FINAL.md / CURRENT_PROJECT_STATUS.md / FINAL_EVALUATION_AFTER_FIXES.md
├── ANTIGRAVITY_RECOVERY_REPORT.md / FINAL_QA_REPORT.md
│
├── src/
│   ├── __init__.py
│   ├── data_loader.py                  # CSV/Parquet ingestion, chunked CSV cleaning, IST tz fix, stop/route normalization
│   ├── topology.py                     # Directed OD graph reconstruction, WCC/SCC checks, chain-preserving topo sort
│   ├── load_engine.py                  # Time/day filtering, OD-collapsed vectorised segment expansion, Layer A/B/C metrics
│   ├── analytics.py                    # Route rankings, hourly/daily splits, peak shares, spring-layout city graph
│   ├── gtfs.py                         # Hardened GTFS ZIP extraction, mtime-cached feed loader, GTFS-first OD matching
│   ├── journey_planner.py              # Stop autocomplete, GTFS-first + topology-fallback direct journey search
│   └── ui_theme.py                     # Dark cyberpunk CSS injection, HUD telemetry strip, SVG route tracer & corridor strip
│
├── scripts/
│   ├── build_processed.py              # Pre-builds Parquet/JSON caches in data/cache/
│   ├── make_sample.py                  # Generates 25k-row sample in data_sample/
│   ├── validate.py                     # 7-point accounting, direction, and hourly reconciliation suite
│   └── _stdout_compat.py               # UTF-8 Windows console shim
│
├── tests/
│   └── test_regression.py              # 15-group deterministic regression suite (math, topology, GTFS, security, UI)
│
├── data_sample/
│   └── tickets_sample.csv              # Bundled 25,000-row October-2026 sample (4.34 MB, 60 routes)
├── data/
│   └── cache/                          # Generated Parquet/JSON cache sink (empty in repo)
└── LoadLens_backup_before_redesign/    # Pre-redesign backup (app.py, app_pages.py, ui_theme.py)
```

---

## 2. Application Architecture

LoadLens is a **monolithic Python/Streamlit analytical web application** with clean separation between its pure-Python computational core (`src/data_loader.py`, `src/topology.py`, `src/load_engine.py`, `src/analytics.py`, `src/gtfs.py`, `src/journey_planner.py`) and its presentation layer (`app.py`, `app_pages.py`, `src/ui_theme.py`). There is no external database, REST API server, or JavaScript frontend framework.

### Module Dependency Map

```text
app.py
 ├── src/ui_theme.py         (CSS, HTML components, demand tier palette)
 ├── src/data_loader.py      (load_raw, load_raw_buffer, clean_with_report)
 ├── src/topology.py         (build_route_topology_with_meta, load_topology*)
 ├── src/load_engine.py      (compute_segment_loads, load_segments)
 ├── src/gtfs.py             (extract_gtfs_zip, gtfs_status)
 └── app_pages.py            (5 page renderers)
      ├── src/ui_theme.py
      ├── src/analytics.py   (pure aggregations + NetworkX spring layout)
      ├── src/load_engine.py (filter_tickets_by_window, compute_segment_loads)
      ├── src/gtfs.py        (gtfs_status, load_gtfs_feed)
      └── src/journey_planner.py
           ├── src/data_loader.py  (normalize_stop)
           ├── src/gtfs.py         (gtfs_status, search_gtfs_direct_options)
           ├── src/load_engine.py  (count_active_days, route_vehicle_reliability_stats)
           └── src/topology.py     (load_topology)
```

No circular imports exist across `src/`, `app_pages.py`, or `app.py`.

---

## 3. Main Execution Flow

1. `streamlit run app.py` configures the page (`st.set_page_config`) and injects the compiled CSS theme (`ui_theme.inject_css()` via `st.html`).
2. Sidebar (`app.py:183-274`) renders the `LOADLENS` lockup, 5-module radio navigation (`Overview`, `Journey Planner`, `Route Analytics`, `Segment Explorer`, `Data Quality`), and `Data & GTFS Sources` uploaders.
3. **GTFS resolution:** If a `.zip` is uploaded, `extract_gtfs_zip()` validates and extracts `.txt` files into `data/gtfs_uploaded/<md5>/` (using `gtfs_status()` validation). Otherwise `data/gtfs/` is checked.
4. **Ticket dataset resolution (`_process_uploaded_bytes` or `_load_default_dataset`):**
   - Precedence: Sidebar upload → `LOADLENS_TICKETS` env var → `data/cache/*.parquet` → `data/raw/*` → `data_sample/tickets_sample.csv`.
   - Cached via `@st.cache_data` keyed by upload bytes or file size/mtime signature (`_cache_signature()`).
5. Sidebar renders `SYSTEM TELEMETRY` (source label, cleaned tickets, chains, uncertain count, segments, active mode).
6. Router (`app.py:280-297`) dispatches to the active renderer in `app_pages.py`.

---

## 4. Important Modules & Responsibilities

| Module | Responsibility | Key Public Entrypoints |
|---|---|---|
| `app.py` | Streamlit bootstrap, caching, sidebar navigation, upload handling, routing | `_process_uploaded_bytes`, `_load_default_dataset`, `_cache_signature` |
| `app_pages.py` | 5 page UI renderers, Plotly dark theming, widget state callbacks | `render_overview`, `render_journey_planner`, `render_route_analytics`, `render_segment_explorer`, `render_data_quality`, `_swap_jp_queries` |
| `src/data_loader.py` | CSV/Parquet ingestion, chunked CSV reader, IST normalization, stop/route parsing, DQ accounting | `normalize_stop`, `parse_route`, `clean_with_report`, `load_clean_csv_chunked`, `load_clean` |
| `src/topology.py` | Directed graph construction, WCC/SCC structural diagnostics, cycle breaking, chain-aware topological sort | `build_route_topology_with_meta`, `build_route_topology`, `save_topology`, `load_topology` |
| `src/load_engine.py` | Time/day slicing, OD-collapsed segment expansion, Layer A/B/C indicators, vehicle reliability guards | `filter_tickets_by_window`, `compute_segment_loads`, `route_vehicle_reliability_stats` |
| `src/analytics.py` | Route ranking, hourly/daily splits, peak share, top segments, NetworkX schematic graph | `route_demand_ranking`, `peak_vs_offpeak`, `top_segments`, `city_network_graph_data` |
| `src/gtfs.py` | Bounded ZIP extraction, header/schema validation, mtime-cached feed loader, GTFS-first sequence search | `extract_gtfs_zip`, `gtfs_status`, `load_gtfs_feed`, `search_gtfs_direct_options` |
| `src/journey_planner.py` | Stop index/autocomplete + unified GTFS-first / topology-fallback planner | `stop_index`, `suggest_stop`, `search_options_topology`, `search_options_with_gtfs` |
| `src/ui_theme.py` | Cyberpunk dark CSS stylesheet, HUD cards, route tracer SVG, vertical timeline, corridor strip | `inject_css`, `editorial_hero`, `page_hero`, `hud_metrics_strip`, `animated_route_tracer_html`, `stop_timeline_html`, `corridor_strip_html` |

---

## 5. Data Flow (Raw Ticket Input to Displayed Results)

1. **Ingest:** `load_raw` / `load_raw_buffer` / `load_clean_csv_chunked` reads CSV/Parquet.
2. **Clean & Normalize:** Required columns checked (`passenger_count`, `route`, `start_stop_name`, `end_stop_name`, `created_at`). Timestamps converted to naive `Asia/Kolkata` IST. Stop names normalized once per unique string (`normalize_stop`). Routes parsed once per unique label (`parse_route`). Four mutually exclusive exclusion buckets recorded in `dq_report`. Missing `vehicle_number` flagged via `has_vehicle` without imputation.
3. **Topology:** `build_route_topology_with_meta` constructs directed OD graphs per `(route, direction)`, isolates minor disconnected islands (`partial_disconnected`), removes minimum-weight cycle edges, orders stops via `_topo_chain_aware`, and flags circular/severely disconnected/ambiguous routes as unreliable (`reliable=False`).
4. **Segment Aggregation:** `compute_segment_loads` joins ticket `(start_norm, end_norm)` ranks, rejects `start_rank >= end_rank`, pre-aggregates identical `(route, direction, start_rank, end_rank)` OD groups, expands consecutive segments `[b..e)`, computes `segment_load`, `avg_daily_load`, `veh_segment_load`, `relative_load_index`, and `network_load_percentile`.
5. **Presentation:** `app_pages.py` slices by IST time window / day type on demand (`_cached_window_slice`) and renders ranked options, Plotly charts, and forensic tables.

---

## 6. GTFS Integration Flow

1. Required files: `stops.txt`, `routes.txt`, `trips.txt`, `stop_times.txt` validated by `gtfs_status()`.
2. `load_gtfs_feed()` caches parsed CSVs via `functools.lru_cache(maxsize=4)` keyed by `(file_size, mtime_ns)` and parses `HH:MM:SS` (`arr_sec`, `dep_sec`, supporting `>=24h` GTFS times).
3. `search_gtfs_direct_options()` joins origin and destination `stop_id`s on `stop_times.txt` (`seq_o < seq_d`), picks the shortest valid span on a single trip if repeated stops occur, computes median scheduled duration in minutes, and builds stop coordinates if `stop_lat`/`stop_lon` exist.
4. `_match_tickets_for_gtfs_route()` matches ticket rows strictly by exact route label or parsed `<number><variant>` + direction (`up`/`down`) without leaking unrelated routes.
5. `_aggregate_tickets_on_gtfs_sequence()` maps ticket `(start_norm, end_norm)` onto the canonical trip sequence, excluding ambiguous repeated-stop pairs (`len(valid_pairs) > 1`) and flagging partial coverage (`< 50%`).

---

## 7. Journey Recommendation Algorithm

* **Scope:** Direct (0-transfer) routes only.
* **Topology Mode (`search_options_topology`):**
  - Evaluates all consecutive rank segments `r -> r + 1` for `r in [a, b)`, preserving zero-ticket segments in active windows (`obs_status="zero_observed_in_window"`) in the `b - a` denominator, while marking completely inactive routes (`route_tickets == 0`) as `has_matched_load=False` (`N/A`).
  - Ranks matched routes before unmatched routes by lowest `(avg_daily_segment_load, mean_segment_load, max_segment_load, segment_count)`.
* **GTFS Mode (`search_gtfs_direct_options`):**
  - Prioritizes adequately matched (`>= 50%` stop match) routes ahead of partial matches (`incomplete_coverage=True`), ahead of unmatched routes (`N/A`).
  - Uses comparable demand metric across matched options (`pax_per_gtfs_trip` if all matched options have trip counts, else `avg_daily_segment_load`, else `mean_segment_load`).
  - `"Lowest Demand Intensity"` sorts purely by demand key; `"Balanced (Demand + Time)"` scores `0.65 * norm_demand + 0.35 * norm_duration` using min-max normalization across matched options.

---

## 8. External Dependencies & Services

* **Python Packages (`requirements.txt`):** `pandas==2.3.3`, `pyarrow==23.0.0`, `numpy==2.4.2`, `streamlit==1.54.0`, `plotly==7.1.0`, `networkx==3.7`, `python-dateutil==2.9.0.post0`, `pytz==2025.2`.
* **External Network Assets (Client-Browser Only):**
  1. Google Fonts CSS (`fonts.googleapis.com`) loaded by the browser via `@import` in `src/ui_theme.py:89` (degrades gracefully to system sans/monospace fonts offline).
  2. CARTO `carto-darkmatter` map tiles requested by Plotly `Scattermap`/`line_map` when GTFS coordinates are active (degrades cleanly to dark gray map surface if blocked/offline).
* **No external APIs, databases, or authentication keys are used.**

---

## 9. Existing Technical Debt

1. **Streamlit `st.file_uploader` full-file memory model:** Sidebar upload (`app.py:236`) passes `uploaded_tickets.getvalue()` bytes into `load_raw_buffer`; for a 290 MB CSV on a 1 GB container, uploading via browser consumes extra RAM compared to prebuilt `data/cache/` via `scripts/build_processed.py`.
2. **GTFS `calendar.txt` / `frequencies.txt` not parsed:** Scheduled trip counts (`trips.txt`) are not filtered by weekday/weekend `service_id`.
3. **Single-process in-memory `tickets` DataFrame:** Analytics pages (`Route Analytics`, `Overview`) query the cleaned `tickets` DataFrame directly rather than precomputed summary tables.
4. **Uploaded GTFS disk accumulation:** `data/gtfs_uploaded/<md5>/` persists per unique ZIP hash for the container lifetime unless cleaned on restart.
5. **Pre-existing non-production docs:** Legacy Phase 1/QA markdown files (`CURRENT_PROJECT_STATUS.md`, `FINAL_EVALUATION_AFTER_FIXES.md`, `ANTIGRAVITY_RECOVERY_REPORT.md`, `FINAL_QA_REPORT.md`, `CHANGELOG_FINAL.md`) remain in root alongside the final Phase 10 reports.

---

## 10. Duplicate, Unused, or Abandoned Files

* **`LoadLens_backup_before_redesign/`:** Contains pre-redesign snapshots (`app.py`, `app_pages.py`, `ui_theme.py`). Preserved intentionally as historical recovery reference (now superseded by Git history `a6f9069` / `8de71ef`; excluded from Docker builds via `.dockerignore`).
* **`package-lock.json` (REMOVED):** Was an unused 87-byte empty npm lockfile with zero dependencies; removed via `git rm` to eliminate packaging confusion.

---

## 11. Potential Security & Deployment Risks

* **Addressed in Phase 9:**
  - Hardened `extract_gtfs_zip()` (`src/gtfs.py`) against path traversal (`..`, null bytes), symlinks, excessive archive entries (`>64`), and ZIP-bomb decompression (`>150 MB` per file / `>250 MB` total uncompressed via streaming byte counting).
  - Hardened `app.py:218` to validate `gtfs_status(target)["available"]` before reusing cached extracted GTFS directories and clean up failed extractions.
  - Added `.env.example`, `.gitignore` `.env` rule, `Dockerfile`, and `.dockerignore` (preventing raw datasets or `.git` from shipping in containers).
* **Remaining Operational Considerations:**
  - **Public deployment memory sizing:** `2.56M`-row raw datasets require $\ge 2\text{ GB}$ RAM containers (Render/Fly/Cloud Run/VPS) rather than 1 GB free-tier hosts.
  - **No authentication / multi-tenant rate limiting:** If deployed publicly with `maxUploadSize = 512`, reverse-proxy rate limiting or reduced `maxUploadSize` (e.g., `100` MB for public demo) is recommended to prevent DoS via repeated large uploads.
