# LoadLens — Antigravity Recovery Report

> **Inspection Date:** 2026-11-27  
> **Workspace:** `C:\Users\Asus\Desktop\Loadlens`  
> **Version Control Status:** Not a Git repository (`.git` absent). A pre-redesign backup exists at `LoadLens_backup_before_redesign/` (`app.py`, `app_pages.py`, `ui_theme.py`).  
> **Inspection Rule:** No existing source code was modified during this audit. Verified facts are strictly separated from unverified scope.

---

## 1. Overall Project Status

LoadLens is a **pure-Python Streamlit 1.54.0 + Plotly 7.1.0 + NetworkX 3.7 + Pandas 2.3.3** transit demand and journey investigation application backed by a 25,000-row sample CSV (`data_sample/tickets_sample.csv`) and optional static GTFS integration (`data/gtfs/` or `.zip` upload).

The **data processing and calculation pipeline (`src/data_loader.py`, `src/topology.py`, `src/load_engine.py`, `src/analytics.py`, `src/gtfs.py`, `src/journey_planner.py`) is completely intact** and passes both `audit.py` (`FAILURES: 0`, `WARNINGS: 0`) and `scripts/validate.py` (`7/7` checks passed).

Claude Code already completed a Phase 1 audit (`CURRENT_PROJECT_STATUS.md`, written `2026-11-27 14:57`) and then performed most of a Phase 2 UI redesign (`src/ui_theme.py`, `app_pages.py`, `app.py` modified between `15:00` and `15:11`), comparing directly against `LoadLens_backup_before_redesign/`. However, Claude stopped mid-task **without re-running the test suite after its final edits**, leaving **two active regressions** (one `NameError` crash in `Journey Planner` and one date-label format assertion failure in `tests/test_regression.py`) and no live browser verification.

---

## 2. Percentage of UI Redesign Completed (With Evidence)

All numbers below are measured directly from file diffs against `LoadLens_backup_before_redesign/` and test execution in this session (no percentages are estimated beyond observed counts):

* **Pages structurally redesigned in code:** **5 / 5 pages (100% touched)** in `app_pages.py` (`1,490` → `1,416` lines; `+307 / -381` lines changed, `0.763` similarity).
* **Pages functionally working end-to-end under `AppTest`:** **4 / 5 pages (80% of pages)** — `Overview`, `Route Analytics`, `Segment Explorer`, and `Data Quality` render with `0` exceptions. `Journey Planner` (`1 / 5`, 20%) crashes on any matching direct route due to `NameError: name 'dot_cls' is not defined` in `src/ui_theme.py:1378`.
* **UI shell & theme modules:** `app.py` (`289` → `297` lines, `+48 / -40`) and `src/ui_theme.py` (`1,220` → `1,448` lines, `+722 / -494`) are redesigned; **1 / 11** HTML helper functions in `src/ui_theme.py` (`stop_timeline_html`) is broken (`dot_cls` removed at line 1373 while still referenced at line 1378).
* **Visual / browser CSS rendering:** **0% live-browser verified** in this environment because binding/probing localhost sockets inside the sandbox fails with `WinError 10013`.

### Checklist of Requested Redesign Items (Observed Code Evidence)

| Redesign Item | Status | Observed Evidence |
|---|---|---|
| Dark cyberpunk colour system | **Implemented in code** (browser render unverified) | `src/ui_theme.py:14-106` (`#070910` void, `#0B101B` surface, `#111827` panel, `#42E8E0` cyan, `#9575FF` violet, `#E84FA8` magenta, `#F5B84B` amber, `#FF6B70` coral); `.streamlit/config.toml`; Space Grotesk / Inter / JetBrains Mono fonts via `inject_css()`. |
| Premium navigation sidebar | **Implemented & verified (`AppTest`)** | `app.py:172-275`, `src/ui_theme.py:196-252,350-428,1135-1152`: `brand_header()` SVG lockup, numbered radio modules (`01 · OVERVIEW` to `05 · DATA FORENSICS`), active cyan rail/pulsing dot CSS, `Data & GTFS Sources` expander, and `SYSTEM TELEMETRY` status box. |
| Cinematic overview page | **Implemented & verified (`AppTest`)** | `app_pages.py:350-495`: `editorial_hero()`, 5-cell asymmetric `hud_metrics_strip()`, 540px City Corridor Movement Matrix, `02 · Launch Investigation` card, Top-5 corridor alert cards, `section_eyebrow` dividers, 3 Plotly charts, 4-button jump strip. |
| Journey Investigation redesign | **Partially broken (runtime crash)** | `app_pages.py:500-898`: `page_hero()`, `animated_route_tracer_html()`, `ll-route-card` dossiers, tabs. **Crashes** inside `_render_option_card` → `ui_theme.stop_timeline_html()` (`NameError: dot_cls`). |
| Route Intelligence redesign | **Implemented & verified (`AppTest`)** | `app_pages.py:903-1067`: `page_hero("Route Intelligence", ...)`, filter controls (`ra_filter`, `ra_dir`, `top_n`), `kpi_row`, 4 `section_eyebrow` dividers (`A`–`D`), 6 Plotly charts, ranking table. Note: `_date_range_label` change (`" → "`) breaks `test_regression.py:296`. |
| Segment Explorer redesign | **Implemented & verified (`AppTest`)** | `app_pages.py:1073-1262`, `src/ui_theme.py:1405-1448`: `page_hero()`, `kpi_row`, `se_seg_pick` selector with glowing highlight in `corridor_strip_html()`, `Segment Telemetry Dossier` card, `section_eyebrow` dividers, 2 Plotly charts, bottleneck cards, dataframe. |
| Data Forensics redesign | **Implemented & verified (`AppTest`)** | `app_pages.py:1268-1416`: `page_hero("Data Forensics", ...)`, 5-tile `kpi_row`, Class A/B/C evidence cards, `section_eyebrow` (`A`–`D`), exclusion ledger, 2 Plotly charts, topology reliability table. |
| Animated route visualisations | **Implemented in code** (live CSS motion unverified) | `src/ui_theme.py:805-1043,1252-1448`: `animated_route_tracer_html` (SVG `ll-tr-flow` dashed line animation + pulsing origin/target nodes) and `corridor_strip_html` (scanning beam + scaled stroke links). Both return valid HTML strings directly (`11,540` chars and `14,750–17,118` chars). |
| Interactive components | **Partially verified** | `ra_filter`, `ra_dir`, `se_sort`, and `jp_query_o` (no-match path) tested via `AppTest` with 0 errors. Default `Journey Planner` fails on `dot_cls`; `ov_go_jp`, `jp_swap`, `jp_active_trace`, uploaders, and Plotly hover/zoom were not clicked in a browser. |
| Responsive layouts | **Implemented in CSS** (viewport unverified) | `src/ui_theme.py:1106-1123`: `@media` breakpoints at `1080px`, `860px`, and `720px` for `.ll-hud-strip`, `.block-container`, `.ll-editorial-hero`, `.ll-route-metrics`, `.ll-kpi-grid`. |

---

## 3. Files Already Modified by Claude

Compared against `LoadLens_backup_before_redesign/` and file modification timestamps:

1. `CURRENT_PROJECT_STATUS.md` (`2026-11-27 14:57:19`, `20,893` bytes) — Phase 1 status report authored by Claude.
2. `src/ui_theme.py` (`2026-11-27 15:00:05`, `51,892` bytes vs backup `40,035` bytes) — Expanded CSS, added `editorial_hero`, `page_hero`, `hud_metrics_strip`, `section_eyebrow`, updated `brand_header`, `animated_route_tracer_html`, `corridor_strip_html`, and edited `stop_timeline_html`.
3. `app_pages.py` (`2026-11-27 15:02:16`, `70,017` bytes vs backup `68,566` bytes) — Updated all 5 page renderers, replaced `hero` with `editorial_hero`/`page_hero`, replaced `kpi_row` on Overview with `hud_metrics_strip`, added `section_eyebrow` and `_esc`, renamed `_meta` → `_dq_meta`, increased Overview network figure height (`440` → `540`), changed `_date_range_label` separator (`" to "` → `" → "`).
4. `app.py` (`2026-11-27 15:11:27`, `12,256` bytes vs backup `11,196` bytes) — Updated `st.set_page_config` title/icon, added `html_escape()`, refined sidebar `_NAV_LABELS` and `SYSTEM TELEMETRY` HTML block.

All calculation modules (`src/analytics.py`, `src/data_loader.py`, `src/gtfs.py`, `src/journey_planner.py`, `src/load_engine.py`, `src/topology.py`) retain their `2026-11-25` timestamps and remain untouched.

---

## 4. Pages Fully Redesigned

*(All verified to render with `0` exceptions in `AppTest`; live browser visual check still pending.)*

1. **`01 · OVERVIEW`** (`render_overview` in `app_pages.py:350-495`) — Cinematic `editorial_hero`, 5-cell `hud_metrics_strip`, 540px City Corridor Movement Matrix, quick-plan investigation card, top-5 corridor alerts, hourly & top-8 route charts (`3` Plotly figures), and 4-module jump buttons.
2. **`03 · ROUTE INTELLIGENCE`** (`render_route_analytics` in `app_pages.py:903-1067`) — `page_hero`, filter bar, 4-tile `kpi_row`, `section_eyebrow` dividers (`A`–`D`), 6 Plotly figures (ranking bar, peak donut, vehicle coverage, weekday/weekend line, daily bars, route×hour heatmap), and ranking dataframe. *(Minor polish note: redundant `####` markdown headings remain right below `section_eyebrow` calls at lines 959, 1032, 1052.)*
3. **`04 · SEGMENT EXPLORER`** (`render_segment_explorer` in `app_pages.py:1073-1262`) — `page_hero`, 4-tile `kpi_row`, segment selector synced with `corridor_strip_html` highlight, `Segment Telemetry Dossier` card, `section_eyebrow` dividers, 2 Plotly figures, top-3 bottleneck cards, and sortable dataframe.
4. **`05 · DATA FORENSICS`** (`render_data_quality` in `app_pages.py:1268-1416`) — `page_hero`, 5-tile `kpi_row`, Class A/B/C evidence cards, `section_eyebrow` dividers (`A`–`D`), exclusion ledger table, 2 Plotly figures, and topology reliability audit table.

---

## 5. Pages Partially Redesigned

1. **`02 · JOURNEY INVESTIGATION`** (`render_journey_planner` & `_render_option_card` in `app_pages.py:500-898`)
   - **Completed in code:** `page_hero`, GTFS/topology status banner, `Corridor Query Parameters` panel, KPI row, `animated_route_tracer_html`, `ll-route-card` dossier cards with `TRACING` active badge, and 3-tab expander (`Stop-by-Stop Timeline`, `Segment Load Breakdown`, `Route Geometry`).
   - **Broken / Incomplete:** Crashes at `src/ui_theme.py:1378` (`stop_timeline_html`) whenever at least one direct route option is returned. GTFS route map (`tab_map`) also has no local GTFS feed (`data/gtfs/` is empty) and displays the fallback info notice by design.

---

## 6. Pages Not Yet Redesigned

* **None** — all 5 existing pages in `app_pages.py` received Phase 2 redesign edits.
* *(Minor cleanup items only: unused CSS classes `.ll-chip`, `.ll-mono`, `.ll-skeleton` in `src/ui_theme.py`, and redundant `####` subheadings under `section_eyebrow` on Route Intelligence, Segment Explorer, and Data Forensics.)*

---

## 7. Broken or Incomplete Components

1. **`src/ui_theme.py:1373-1378` — `stop_timeline_html()` (`BROKEN`):**
   - `dot_cls = "origin" if i == 0 else ""` was accidentally removed during Claude's edit while `<div class="ll-tl-dot {dot_cls}"></div>` on line 1378 still references `dot_cls`.
   - **Impact:** Breaks `Journey Planner` whenever direct routes exist, breaks `smoke_test.py`, and breaks `tests/test_regression.py` (Case 5, line 158).
2. **`app_pages.py:134` — `_date_range_label()` (`REGRESSION FAILURE`):**
   - Changed separator from `" to "` (backup line 134) to `" → "` (`f"{dmin} → {dmax}"`).
   - **Impact:** Breaks `tests/test_regression.py:296` (`assert app_pages._date_range_label(t10, dq10) == "2026-12-01 to 2026-12-05"`), unless the test assertion is intentionally updated or the separator is restored.
3. **`data/gtfs/` & `data/gtfs_uploaded/` & `data/cache/` (`EMPTY ON DISK`):**
   - `data/cache/` is empty (caches are built dynamically in memory/on run).
   - `data/gtfs/` is empty, so `Journey Planner` defaults to `TICKET TOPOLOGY` mode and `Route Geometry` geographic maps are disabled unless a GTFS `.zip` is uploaded.
4. **Unused CSS classes in `src/ui_theme.py`:**
   - `.ll-chip`, `.ll-mono`, and `.ll-skeleton` are defined in CSS (`src/ui_theme.py:177,1046,1056`) but not referenced in `app.py` or `app_pages.py`.
5. **Unquoted HTML `style=` attribute in `app.py:267`:**
   - `style=color:{ui_theme.AMBER_SIGNAL};` (missing quotes around `color:...;`) works in lenient HTML parsers but should be quoted (`style="color:...;"`) for strict HTML validity.

---

## 8. Runtime Errors

Observed directly by running all test scripts, AST checks, and `AppTest` in this session:

1. **`python smoke_test.py` (Exit code `1`):**
   - `Overview`, `Route Analytics`, `Segment Explorer`, `Data Quality`: **PASS** (`0` exceptions).
   - `Journey Planner`: **FAIL** — `NameError: name 'dot_cls' is not defined` at `app.py:287` → `app_pages.py:709` → `app_pages.py:828` → `src/ui_theme.py:1378`.
2. **`python tests/test_regression.py` (Exit code `1`):**
   - Cases 1–4: **PASS**.
   - Case 5 (`line 158`): **FAIL** — `NameError: name 'dot_cls' is not defined` in `ui_theme.stop_timeline_html`.
   - Cases 6–12 were not reached because `_run_tests()` aborted at Case 5 (and Case 10 at `line 296` will also fail on `_date_range_label` `" → "` vs `" to "` mismatch).
3. **AST undefined-name & syntax compilation checks:**
   - `python -m py_compile` on `app.py`, `app_pages.py`, and all 7 `src/*.py` files: **PASS** (`COMPILE_EXIT=0`, zero import or syntax errors).
   - Static AST scan flagged `dot_cls` in `src/ui_theme.py:1378` as the sole real undefined variable across the entire codebase.
4. **Live HTTP server probe (`streamlit run app.py --server.port 8512`):**
   - Blocked in sandbox with `WinError 10013` (`PermissionError` on socket probe), so live browser DOM, Google Fonts loading, Plotly WebGL/SVG layout, and CSS animations could **not** be visually verified in this environment.

---

## 9. Existing Working Features

### Verified in this session
* **`python audit.py` (`AUDIT_EXIT=0`):** `FAILURES: 0`, `WARNINGS: 0`. Verified 25,000 sample rows (`24,215` forward + `24` backward + `761` excluded uncertain/disconnected = `25,000`), `2,793` segments, `0` cross-route ranking inversions across `171` multi-route OD pairs, synthetic CSV exclusions, IST conversion, Layer C reliability guards, and GTFS duration/demand pairing.
* **`python scripts/validate.py` (`VALIDATE_EXIT=0`):** All `7` checks passed (`321,793` pax-segments, `26,938` pax-journeys, `avg segments = 11.95`, `71.4%` peak share, hourly sum `26,938 == 26,938`).
* **Pages rendering cleanly via `AppTest`:**
  * `Overview` (`8` markdown blocks, `3` Plotly charts)
  * `Route Analytics` (`13` markdown blocks, `1` dataframe, `6` Plotly charts)
  * `Segment Explorer` (`15` markdown blocks, `1` dataframe, `2` Plotly charts)
  * `Data Quality` (`10`+ markdown blocks, `2` dataframes, `2` Plotly charts)
* **Interactive filters verified via `AppTest`:**
  * `Route Analytics`: `ra_filter="717"` and `ra_dir="up"` (`0` exceptions).
  * `Segment Explorer`: `se_sort="segment_load"` (`0` exceptions).
  * `Journey Planner`: unmatched query `jp_query_o="zzzz_nonexistent"` shows clean warning (`0` exceptions).
* **Underlying upload pipelines verified via direct Python calls:**
  * Ticket CSV upload path (`load_raw_buffer` → `clean_with_report` → `build_route_topology_with_meta` → `compute_segment_loads`): processed `25,000` sample rows → `60` routes, `2,793` segments.
  * GTFS ZIP upload path (`extract_gtfs_zip` → `gtfs_status` → `search_options_with_gtfs`): extracted synthetic GTFS ZIP, detected `available=True`, returned `1` option with `10.0` min scheduled duration.
* **HTML component builders verified directly:**
  * `ui_theme.animated_route_tracer_html(opt)` (`11,540` chars on `badarpur border` → `kalkaji mandir`).
  * `ui_theme.corridor_strip_html(seg_route, highlight_idx=0)` (`14,750–17,118` chars on routes `258DOWN`, `427DOWN`, `427UP`).

### Unverified in this session
* Live browser rendering of CSS, animations, Google Fonts, `carto-darkmatter` map tiles, and responsive `@media` breakpoints (blocked by `WinError 10013` socket restriction).
* Interactive `st.file_uploader` UI widget triggers inside Streamlit browser session (underlying functions verified directly; UI widget event not exercised).
* Cross-page buttons (`ov_go_jp`, `jp_swap`, `sc_jp`–`sc_dq`), `jp_active_trace` switching, time-window/day-type UI dropdowns on `Journey Planner`, and `tests/test_regression.py` Cases 6–12 (blocked by Case 5 failure).
* Full ~290 MB dataset processing (not present in workspace).

---

## 10. Features That Need Regression Testing

Once `dot_cls` and `_date_range_label` are resolved, the following must be re-tested:

1. **Full `tests/test_regression.py` (all 12 cases)** — especially Case 5 (`stop_timeline_html`), Case 8 (GTFS-first matching & ranking), Case 10 (`_date_range_label`), Case 11 (100k-row performance benchmark), and Case 12 (all 5 `AppTest` pages + zero-row CSV).
2. **`python smoke_test.py`** — confirm all 5 pages pass with `0` exceptions.
3. **Journey Planner interactive UI flows** — valid OD pair selection, `jp_active_trace` radio switching, `TIME_WINDOWS` & `DAY_TYPES` filtering, `ov_go_jp` quick-plan redirect, `jp_swap` button, and GTFS active mode (`Balanced` vs `Lowest Demand Intensity` ranking + `Route Geometry` map).
4. **Live browser visual QA (`http://localhost:8501`)** — verify CSS injection (`st.html`), dark grid background, sidebar active radio glow, Plotly dark backgrounds/legends, horizontal tracer/corridor scrolling, mobile/tablet responsive breakpoints (`1080px`, `860px`, `720px`), and `st.file_uploader` for both ticket CSV/Parquet and GTFS `.zip`.

---

## 11. Exact Next Development Steps

1. **Step 1 (Immediate fix — restore broken timeline):**
   - In `src/ui_theme.py` inside `stop_timeline_html()` (around line 1373), restore `dot_cls = "origin" if i == 0 else ""` right before line 1378 (`<div class="ll-tl-dot {dot_cls}"></div>`).
2. **Step 2 (Resolve regression assertion mismatch):**
   - Either revert `app_pages.py:134` `_date_range_label` separator from `" → "` back to `" to "` (matching `tests/test_regression.py:296` and `LoadLens_backup_before_redesign/app_pages.py:134`), **or** update `tests/test_regression.py:296` if `" → "` is the intended UI string.
3. **Step 3 (Re-run the entire automated suite):**
   - Run `python audit.py`, `python scripts/validate.py`, `python smoke_test.py`, and `python tests/test_regression.py`, plus an `AppTest` check on `Journey Planner` with a valid multi-option OD pair (e.g., `badarpur border` → `kalkaji mandir`).
4. **Step 4 (Minor HTML/UI cleanup):**
   - Quote `style="color:..."` in `app.py:267`.
   - Optionally remove redundant `####` markdown headings directly below `ui_theme.section_eyebrow(...)` in `app_pages.py` (`Route Analytics`, `Segment Explorer`, `Data Quality`), and remove or wire unused CSS classes (`.ll-chip`, `.ll-mono`, `.ll-skeleton`).
5. **Step 5 (Live browser QA outside sandbox):**
   - Launch `streamlit run app.py` locally and inspect all 5 pages, animated route tracer, corridor strip, file uploaders, and responsive widths in a real browser.

---

## 12. Exact Commands to Run the Application

### Launch Dashboard (Windows PowerShell)
```powershell
cd C:\Users\Asus\Desktop\Loadlens
python -m pip install -r requirements.txt
streamlit run app.py
```
Or using the Windows launcher:
```powershell
cd C:\Users\Asus\Desktop\Loadlens
.\run.bat
```

### Run Validation & Test Suites
```powershell
cd C:\Users\Asus\Desktop\Loadlens
python audit.py
python scripts\validate.py
python smoke_test.py
python tests\test_regression.py
```

### Optional: Pre-build Cache for Full Dataset or Sample
```powershell
python scripts\build_processed.py data_sample\tickets_sample.csv --force
```
