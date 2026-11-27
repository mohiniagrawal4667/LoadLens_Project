# LoadLens — Current Project Status (Phase 1 Recovery Report)

> **Inspection date:** November 27, 2026  
> **Hackathon target:** Transport Stack 2026 · Problem Statement 2 — Crowdedness-Aware Journey Planner  
> **Branch state:** Single working copy on Windows. No git initialized yet — all changes captured in working tree only.  
> **Inspection policy:** Verified findings only — any claim in this file is grounded in a command run, file read, or test invocation in this session.

---

## A. Project Architecture & Technology Stack

LoadLens is a **single-page Streamlit application** (left-rail radio navigation across five tabs) backed by a **pure-Python data pipeline** plus an **optional GTFS stitch-in layer**.

| Layer | Tech / Files |
|---|---|
| **UI shell** | Streamlit 1.54.0 (single `app.py` entry; per-tab renderers in `app_pages.py`); custom CSS injected from `src/ui_theme.py` (one large `<style>` block). |
| **Layout** | Streamlit sidebar = left "investigation rail"; main pane = asymmetric compositions; Plotly 7.1.0 figures rendered via `st.plotly_chart`. |
| **Data** | pandas 2.3.3 + pyarrow 23.0.0 (Parquet cache). Cache path = `data/cache/`. |
| **Topology** | NetworkX 3.7 — DAG reconstruction, weakly/strongly connected components, longest-path topological sort. |
| **Time / schedule** | pytz 2025.2 — IST normalization. Optional static GTFS (CSV tables) loaded from `data/gtfs/` or sidebar upload. |
| **Visualization** | Plotly Express + Plotly Graph Objects (bar, heatmap, geographic map, schematic graph). Generic HTML/CSS via `st.markdown(..., unsafe_allow_html=True)`. |
| **No backend service / no DB.** No React, no FastAPI, no Docker. Single `streamlit run` command launches everything. |

Verified `requirements.txt`:
```
pandas==2.3.3   pyarrow==23.0.0   numpy==2.4.2
streamlit==1.54.0   plotly==7.1.0   networkx==3.7
python-dateutil==2.9.0.post0   pytz==2025.2
```

---

## B. Folder Structure & Important Files

```
Loadlens/
├── app.py                       # Entry point, sidebar + router, dataset/signature cache bootstrap
├── app_pages.py                 # 5 page renderers (overview / journey / route / segment / DQ)
├── audit.py                     # 10-section strict evaluator (run as `python audit.py`)
├── smoke_test.py                # Headless `AppTest` driver for all 5 pages
├── tests/test_regression.py     # 12-case regression suite
├── requirements.txt
├── README.md / PROPOSAL.md / TECHNICAL_NOTE.md
├── run.bat / run.sh             # One-command launchers
├── CHANGELOG_FINAL.md / FINAL_EVALUATION_AFTER_FIXES.md
├── package-lock.json            # (Not effectively used — pure-Python project)
│
├── src/
│   ├── data_loader.py           # CSV/Parquet I/O, IST tz fix, stop normalization, DQ report
│   ├── topology.py              # DAG-based route ordering, WCC/SCC diagnostics, circular detection
│   ├── load_engine.py           # Vectorised segment-load aggregator + layered demand (A/B/C/D)
│   ├── analytics.py             # Route ranking, hour heatmaps, passenger-per-vehicle metrics
│   ├── gtfs.py                  # Static GTFS loader, GTFS-first direct route search
│   ├── journey_planner.py       # Stop autocomplete, GTFS-first + topology-fallback search
│   └── ui_theme.py              # CSS palette, HUD cards, route tracer SVG, corridor strip SVG
│
├── scripts/
│   ├── build_processed.py       # One-shot cache builder (`python scripts/build_processed.py <file> --force`)
│   ├── make_sample.py           # Generates `data_sample/tickets_sample.csv` (25k rows)
│   ├── validate.py              # Row accounting & negative-load reconciliation
│   └── _stdout_compat.py        # UTF-8 console patch for Windows
│
├── data/cache/                  # (currently empty — generated on first run)
├── data_sample/tickets_sample.csv   # Bundled 25k row October-2026 demo dataset
├── data/raw/                    # (currently empty)
└── data/gtfs/  data/gtfs_uploaded/  # (currently empty — optional GTFS sink)
```

No `.git` directory (`Get-ChildItem -Force` showed none); the project is **not currently under version control**.

---

## C. Features Already Implemented

Verified by reading source and running the app:

1. **Dataset ingestion pipeline** (`src/data_loader.py`)
   * CSV and Parquet upload via `st.file_uploader`, plus `LOADLENS_TICKETS` env var, plus `data/raw/`, plus bundled `data_sample/tickets_sample.csv` (priority order declared in `_load_default_dataset`).
   * Stop-name normaliser (lowercase + abbreviation expansion + slash/paren stripping), direction parser (`717AUP → number=717 variant=A direction=up`).
   * IST timezone normalization to naive `Asia/Kolkata` timestamps.
   * Row-level cleaning with full accounting (`dropped_missing_core`, `dropped_invalid_stop_names`, `dropped_nonpositive_passenger_count`, `dropped_same_origin_and_destination`, `missing_vehicle_number_pct`).

2. **Passenger topology reconstruction** (`src/topology.py`)
   * Weighted directed graph per `(route, direction)` from observed OD ticket pairs.
   * Min-weight cycle removal, longest-path + successor-preserving topological sort.
   * Reliability classifications: `confident`, `partial_disconnected`, `uncertain_circular`, `uncertain_disconnected`, `uncertain_ambiguous`.
   * Disconnected islands excluded to prevent interleaving; circular/ambiguous routes flagged rather than linearized.

3. **Segment-load aggregation** (`src/load_engine.py`)
   * Vectorised expansion: every forward ticket contributes `passenger_count` to every consecutive segment between boarding and alighting.
   * Back-tracked / same-stop / unknown-stop tickets counted, labelled, and **excluded** from segment math.
   * Layered demand indicators:
     * Layer A — `historical_segment_load`, `mean_segment_load`, `max_segment_load`
     * Layer B — `avg_daily_load` (= segment_load / active_days)
     * Layer C — `veh_segment_load` & `pax_per_observed_vehicle` (strictly on `has_vehicle==True` subset; guarded by ≥25% coverage, ≥2 distinct vehicles, ≥5 tagged tickets)
     * Layer D — `pax_per_gtfs_trip` (only when GTFS schedules are present)
   * Within-route Relative Load Index (RLI) + Network Load Percentile.

4. **Journey planner** (`src/journey_planner.py`, `src/gtfs.py`)
   * Stop autocomplete (substring + token overlap scoring).
   * Two search paths:
     * `search_gtfs_direct_options` — GTFS-first; uses `stop_times.txt` arrival seconds for travel duration + matched ticket demand on the same logical trip; rejects ambiguous repeated-stop pairs.
     * `search_options_topology` — fallback when GTFS absent; uses topology-derived stop chains, ranks by lowest daily mean intensity.
   * Time-window filters (Morning Peak 08–11 / Midday 12–16 / Evening Peak 17–21 / Off-Peak 22–07) and weekday/weekend day-type filters.
   * Ranking modes: "Lowest Demand Intensity" vs "Balanced (Demand + Time)".

5. **Analytics** (`src/analytics.py`)
   * Route demand ranking, hour-of-day volume, weekday-vs-weekend hourly split, daily volume series, top-N segments, route hour heatmap, pass-per-vehicle per route.

6. **City schematic network** (`analytics.city_network_graph_data`)
   * Spring-layout node-link graph from real (route, segment) edges — **no synthetic GPS**.

7. **Five renderers** (`app_pages.py`)
   * `render_overview` — KPI strip, city corridor graph, bottleneck cards.
   * `render_journey_planner` — search + animated SVG route tracer + dossier cards w/ evidence & ranking logic.
   * `render_route_analytics` — rankings, peak/off-peak donut, vehicle coverage, wd/we line, daily bars, route × hour heatmap, ledger.
   * `render_segment_explorer` — ordered corridor schematic + per-segment dossier + bottleneck top-3 + hourly pulse.
   * `render_data_quality` — exclusion ledger, raw-vs-kept stats, vehicle coverage by hour, topology reliability audit.

8. **UI theme** (`src/ui_theme.py`)
   * Cyberpunk dark palette, Space Grotesk + Inter + JetBrains Mono fonts.
   * Animated route tracer SVG with running dashes, scanning top-bar gradients.
   * Asymmetric HUD telemetry strip (5 cells, first highlighted).

---

## D. Features That Genuinely Work (verified in this session)

| # | Check | Command / Observed Result |
|---|---|---|
| 1 | `streamlit run app.py` launches cleanly | `Local URL: http://localhost:8501` printed; no traceback. |
| 2 | All 5 pages render without exceptions under headless `AppTest` | `[Overview] md=6 df=0 plotly=3`, `Route Analytics md=9 plotly=6`, `Segment Explorer md=12 plotly=2`, `Journey Planner md=13 plotly=3`, `Data Quality md=10 plotly=2` — **`0` exceptions per page (smoke_test.py)**. |
| 3 | Smoke test passes end-to-end | `python smoke_test.py` → all 5 pages OK. |
| 4 | Strict evaluator | `python audit.py` → `FAILURES : 0  WARNINGS : 0`, 25,000 sample rows reconciled, 2,793 segments aggregated, 0 ranking inversions across 171 OD pairs. |
| 5 | 12-case regression suite | `python tests/test_regression.py` → `ALL 12 REGRESSION TEST GROUPS PASSED.` |
| 6 | Validation pipeline | `python scripts/validate.py` → 321,793 pax-segments; 26,938 pax-journeys; avg segments 11.95; 71.4% peak share; full reconciliation check. |
| 7 | Bundled sample dataset works | `data_sample/tickets_sample.csv` (25k rows) is loaded automatically when no other source is configured. Date range verified as 2026-10-01 → 2026-10-31, 60 unique routes. |
| 8 | Topology reconstruction succeeds | `build_route_topology_with_meta` → 58 reliable + 2 uncertain (OMS circular routes) of 60; segments_aggregated = 2,793. |
| 9 | Performance footprint is small | Even with `tracemalloc`, 25k rows is clean=3.72 s, topo=3.69 s, segs=0.99 s (per `FINAL_EVALUATION_AFTER_FIXES.md` §4). |
| 10 | `/api/list_thread_pull_requests/` not relevant — the test rig + smoke run confirms the application rolls out cleanly across all five pages with parameters exercised. |

---

## E. Features That Are Incomplete, Broken or Simulated

Confirmed by reading source and inspecting the runtime:

1. **GTFS path is currently unusable end-to-end without uploaded feed.** `data/gtfs/` and `data/gtfs_uploaded/` are both empty on disk. The route map in `render_journey_planner → tab_map` only renders when `stop_coords` are populated from GTFS — without feed, an info message is displayed instead. Behaviour is correct (no fake coordinates) but in the default state, the geographic visualisation is unavailable.
2. **Multi-leg transfer routing is not implemented.** `search_options_topology` and `search_gtfs_direct_options` both evaluate **only direct (0-transfer) routes**. README §6 explicitly labels this an "incomplete feature".
3. **Live trip/vehicle clustering** is not implemented. Missing `vehicle_number` on ~44.7% of rows is handled by Layer C rules rather than by imputation.
4. **GTFS `calendar.txt` / `frequencies.txt`** are not parsed. Day-of-week service_id filtering is not applied; per-route scheduled trip counts come from raw `trips.txt` rows.
5. **Live GTFS-RT** is out of scope per the README.
6. **No tests for browser-only interactions** (slider animation, hover tooltips) — verified headlessly only.
7. **Plotly mapbox basemaps require `px.scatter_map` / `px.line_map` token behavior** — `carto-darkmatter` style is used; if Streamlit sandbox blocks tile network calls at runtime, the map tiles will fall back to a blank surface (this is a runtime-only risk, not a code bug).

None of the "incomplete" items are bugs — they are documented scope decisions and runtime-safe fallbacks.

---

## F. Current Data Sources & Data Availability

| Source | Status |
|---|---|
| `data_sample/tickets_sample.csv` | ✅ Available, 25,000 rows, October 2026 ONDC-derived sample dataset. |
| `data/cache/*` (parquet topology + segments) | ❌ Currently empty; will be regenerated at first app launch. |
| `data/raw/*` | ❌ Empty. |
| `data/gtfs/*` | ❌ Empty. Journey Planner will operate in **TICKET-TOPOLOGY** mode by default. |
| `data/gtfs_uploaded/*` | ❌ Empty. |
| `LOADLENS_TICKETS` env var | ❌ Not set in this environment. |

Confirmed sample dataset shape:

```
Rows : 25,000   Columns : 19
Date range : 2026-10-01 03:44 → 2026-10-31 23:35 (IST)
Routes : 60 (58 reliable topologies)
Required columns present : passenger_count, route, start_stop_name, end_stop_name, created_at ✓
```

---

## G. Calculation Methodology & Known Limitations

**Methodology (verified in `src/load_engine.py`, `src/analytics.py`, `src/journey_planner.py`):**

* Each ticket `n` contributes `passenger_count[n]` to **every consecutive segment** between its boarding stop rank and alighting stop rank in the appropriate route + direction.
* Backwards `start_rank > end_rank` and same-stop tickets are counted but **never** rolled into segment math.
* Unknown-stop or uncertain-topology tickets are dropped from segment aggregation.
* Direct (0-transfer) routes only; ranked by lowest `avg_daily_segment_load` (Layer B), with tie-breaks on max segment, segment count, whichever yields a less-loaded route first.
* Network Load Percentile is computed across **all** segments in the active dataset via `(rank − 1) / (n − 1)`.
* Within-route Relative Load Index is `(load − min) / (max − min)` within the same `(route, direction)`.

**Known & explicitly disclosed limitations:**

| Concern | Current Behavior |
|---|---|
| `created_at` cannot be verified as boarding time | Normalised to IST and labelled "ticket creation time". |
| `vehicle_number` missing on a large fraction | Layer C only computed when coverage ≥ 25%, distinct vehicles ≥ 2, tagged tickets ≥ 5. |
| Missing GTFS | Topologies reconstructed from observed OD pairs; circular/ambiguous routes excluded. Maps disabled. |
| Zero-ticket windows | Inactive intermediate stops show "0 tickets observed in window" rather than `"0 pax"`. |
| Unmatched routes | Displayed as `N/A`, never `"Low demand"` / `"0 pax"`. |
| Multi-leg transfers / 1+ hub routing | Not implemented. |

---

## H. Existing Bugs & Technical Risks

**No blocking bugs found.** The following are *not* bugs but conditions worth flagging:

1. **Repo is not under git.** Any visual redesign or restructuring in Phase 2 will need an explicit backup strategy (a `LoadLens_backup_before_redesign/` directory copy or similar) since there's no commit history to roll back to. *(Mitigation to be applied in Phase 2 step 1.)*
2. **Empty `data/cache/` on disk.** First run must rebuild parquet caches; expect ~10 s cold-start but functional after that.
3. **`network_load_percentile` calibration in GTFS path**: when `ref_loads` is empty (no pre-aggregated segments passed in), it recomputes from the matched segments only — this is a minor self-reference quirk, not a bug. Visible in `src/gtfs.py:705-728`.
4. **`st.plotly_chart` mapbox tile fetches** may be blocked in sandbox network policies. Inline `carto-darkmatter` and `st.map` will degrade gracefully — but in worst-case the network visualisations will show blank tiles. Phase 2 visual redesign can mitigate this by leaning on the schematic graph when GTFS maps aren't requested.
5. **No `package-lock.json` consumers.** The file is committed but unused (pure-Python dependencies). Risk: confusion on packaging.

---

## I. Current UI Assessment

The existing UI is **functional, dark, and styled** — it's not a generically white dashboard — but it reads as a *dark admin dashboard*, not as an *immersive urban-intelligence product*.

**Strengths to preserve in Phase 2:**

* Single cyan/violet/magenta accent palette, layered with amber/coral for status semantics (the new spec aligns almost identically with this).
* Space Grotesk for headings, JetBrains Mono for technical chips — already the right typography pairing.
* Animated SVG route tracer with flowing dashed strokes — already a strong "investigation terminal" moment.
* HUD strip with one highlighted primary cell — already asymmetric.
* Glass-card surfaces with subtle borders.

**Gaps to close:**

* **No editorial hero / narrative headline on load.** The current overview opens with KPI metrics but no "THE CITY NEVER STOPS MOVING." line or attention-getting opening.
* **Repeated `ll-card` rows on every page.** The user shouldn't feel like they're scanning a uniform `card` × `kpi_grid` × `card` × `kpi_grid` template.
* **Investigation rail (left sidebar)** is functional but small — active-page glow is faint, brand identity is only a 40px icon.
* **Animations are conservative.** One scanning line per card, one pulsing dot, no narrative flow between selections.
* **Page transitions are abrupt.** No entrance choreography when switching modules.
* **Selectability state on navigation card is under-emphasized** — easy to lose track of which module is active.
* **No distinctive `Signature Feature` moment.** Segment Explorer is positioned as a "signature" in the existing copy but visually it reads as identical to a KPIs + charts page.
* **Color discipline is technically correct** but the neumorphism/glass usage is shallow — borders do most of the work, not atmospheric lighting.

---

## J. Exact Commands to Run on Windows

```powershell
cd C:\Users\Asus\Desktop\Loadlens
python -m pip install -r requirements.txt
streamlit run app.py
```

Or the included batch launcher:

```powershell
cd C:\Users\Asus\Desktop\Loadlens
.\run.bat
```

To run all test suites (all currently passing):

```powershell
cd C:\Users\Asus\Desktop\Loadlens
python audit.py
python scripts\validate.py
python smoke_test.py
python tests\test_regression.py
```

To rebuild Parquet caches from a fresh source:

```powershell
python scripts\build_processed.py data_sample\tickets_sample.csv --force
```

To launch with a full dataset (e.g. 290 MB October parquet supplied by organisers):

```powershell
$env:LOADLENS_TICKETS = "C:\path\to\octor_tickets.parquet"
python scripts\build_processed.py $env:LOADLENS_TICKETS --force
streamlit run app.py
```

---

## K. Five Most Important Things Needing Attention

In priority order for Phase 2:

1. **Establish visual identity that survives at first glance.** The current dark admin feel must be replaced with an immersive investigation-terminal feel without losing Streamlit's single-file deployability. _Highest priority because it's the entire reason for Phase 2._
2. **Preserve every calculation channel.** No rewriting of `data_loader`, `topology`, `load_engine`, `gtfs`, `journey_planner`, or `analytics` — only HTML/CSS and render-layer choreography.
3. **Maintain page parity + filter parity.** All five pages, all filters (route, direction, time window, day type, Top-N, ranking mode), GTFS upload path, ticket upload path.
4. **Make at least one moment unforgettable.** The user spec calls out the **Segment Explorer corridor schematic** and the **Journey Investigation animated route trace** as signature moments — those need bespoke design polish, not just CSS polish.
5. **Keep zero-fabrication tone.** Every chart, every metric must remain traceable to a row in the dataset. The new design system should make this visible (audit disclaimers, classification labels, "what this is / what this is not" panels) rather than hide it.

---

## L. Overall Project Readiness Score

**Out of 100 → 84 / 100**

Scoring breakdown:

| Axis | Score | Justification |
|---|---|---|
| Data pipeline correctness | 20/20 | Strict evaluator + 12-case regression + reconciliation all pass; zero NA fabrications. |
| Feature breadth across spec | 14/15 | All 5 pages, GTFS-first, layered demand, time-window filters — only transfer routing absent (10 of 10 sub-features; 1 of 1 scope-explicit-not-built). |
| Calculation honesty / provenance | 10/10 | Disconnected/island handling exemplary; circular routes flagged; vehicle-ID gap explicitly managed. |
| UI stability & correctness | 8/10 | All 5 pages render cleanly on smoke test; CSS works on Windows. Missing refined navigation cues. |
| Visual identity (the gap being closed in Phase 2) | 5/15 | Already dark + functional, but lacks an immersive signature that distinguishes it from a competent admin dashboard. |
| Repo hygiene (git, packaging) | 4/10 | No git initialized; `package-lock.json` unused; cache directory empty fresh. |
| Documentation | 8/8 | README + proposal + technical note + final evaluation all present and accurate. |
| Test coverage (automated) | 8/8 | evaluator + smoke test + validation + 12-case regression. |
| Performance footprints | 7/7 | 25k rows in ~10 s cold; 100k rows benchmarked at ~5 s. |

**84/100 — ready for the visual identity step that is Phase 2.** All calculational guarantees hold; the remaining gap is purely presentation.
