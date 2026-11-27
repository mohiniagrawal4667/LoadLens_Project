# LoadLens — Final QA Report

> **Completion Date:** 2026-11-27  
> **Repository:** `C:\Users\Asus\Desktop\Loadlens`  
> **Git Checkpoint:** `a6f9069` (`chore: checkpoint pre-QA LoadLens state`) created prior to edits; `LoadLens_backup_before_redesign/` preserved untouched.  
> **App Server State:** Running at `http://localhost:8501` (Streamlit `1.54.0`).

---

## 1. Fixes Completed

| # | Target | Fix Applied | Verification |
|---|---|---|---|
| 1 | `src/ui_theme.py:1372-1378` (`stop_timeline_html`) | Restored `dot_cls = "origin" if i == 0 else ""` immediately before `<div class="ll-tl-dot {dot_cls}"></div>`, fixing the `NameError` crash in `Journey Planner` and restoring origin dot highlighting on the first stop. | Verified via `smoke_test.py`, `tests/test_regression.py` (`assert 'class="ll-tl-dot origin"' in tl_html`), `AppTest`, and live browser inspection. |
| 2 | `tests/test_regression.py:296` | Updated `_date_range_label` expectation from `"2026-12-01 to 2026-12-05"` to `"2026-12-01 → 2026-12-05"` to match the intentional redesigned UI separator in `app_pages.py:134` without altering working UI. | Verified via `tests/test_regression.py` Case 10 (`PASS`). |
| 3 | `app.py:267` | Quoted the inline `style` attribute (`style='color:...;'`) inside the sidebar `SYSTEM TELEMETRY` HTML block. | Verified via `AppTest` and live browser inspection. |
| 4 | `app_pages.py` (`958`, `1030`, `1049`, `1230`, `1358`, `1374`) | Removed 6 redundant `####` markdown headings directly below `ui_theme.section_eyebrow(...)` dividers across `Route Intelligence`, `Segment Explorer`, and `Data Forensics` (preserving column subheaders). | Verified via `AppTest` and live browser inspection (`1` `<h1>` per page, clean section hierarchy). |
| 5 | `src/ui_theme.py:147,1045-1073` | Removed unused dead CSS classes (`.ll-skeleton`, `.ll-chip*`, `@keyframes ll-march`) while keeping `code, .ll-mono`. | Verified all active `.ll-*` classes still apply in live browser DOM. |
| 6 | `src/ui_theme.py:210` | Increased right padding on sidebar radio labels (`padding: 0.62rem 1.85rem 0.62rem 0.86rem !important;`) so the active cyan pulsing dot no longer overlaps label text. | Verified in live browser (`01 · OVERVIEW`, `02 · JOURNEY INVESTIGATION`, `03 · ROUTE INTELLIGENCE`). |
| 7 | `app_pages.py:307,971,987,1005,1018,1029,1048,1355,1373` | Added explicit `title=""` to untitled Plotly layouts using `_plotly_defaults()` so Plotly.js does not render `"undefined"` at the top-left of charts. | Verified in live browser (`0` `"undefined"` occurrences across Overview and Route Intelligence). |
| 8 | `app_pages.py:338-346` (`_swap_jp_queries`) | Updated `_swap_jp_queries()` to fall back to `origin_choice` / `destination_choice` when `jp_query_o` / `jp_query_d` is blank, so swapping works for dropdown-selected stops as well as typed searches. | Verified Python state and reverse route search (`Kalkaji Mandir → Badarpur Border`, 3 corridors) via `AppTest` and live browser. *(See Remaining Bugs for BaseWeb selectbox display lag.)* |

---

## 2. Journey Planner Test Results (`Badarpur Border → Kalkaji Mandir`)

All 13 interactive flows were verified after the final edits using `AppTest` and/or the live browser at `http://localhost:8501`:

| # | Flow | Status | Observed Result |
|---|---|---|---|
| 1 | Valid origin & destination selection (`Badarpur Border → Kalkaji Mandir`) | **PASS** | Returns 3 real direct routes from `data_sample/tickets_sample.csv`: `#1 · 774UP (UP)`, `#2 · 433DOWN (DOWN)`, `#3 · 511AUP (UP)`. |
| 2 | Invalid origin/destination combinations | **PASS** | Non-existent stop query triggers clean warning; identical origin/destination shows clean warning without traceback. |
| 3 | `jp_active_trace` radio switching | **PASS** | Switching to `#2 · 433DOWN (DOWN)` updates `Active Route Trace · 433DOWN (DOWN)` (`20 segments`), collapses `#1`, and expands `#2` with `TRACING` badge. |
| 4 | `TIME_WINDOWS` filtering | **PASS** | `Morning Peak (08–11 IST)` updates `#1 774UP` from `3.6 pax/day` (`348` records) to `1.6 pax/day` (`145` records); `Off-Peak / Night (22–07 IST)` renders cleanly. |
| 5 | `DAY_TYPES` filtering | **PASS** | `Weekdays (Mon–Fri)` and `Weekends (Sat–Sun)` re-slice segment demand cleanly with `0` exceptions. |
| 6 | `ov_go_jp` quick-plan redirect | **PASS** | Selecting `Badarpur Border` and `Kalkaji Mandir` on Overview and clicking `LAUNCH JOURNEY INVESTIGATION →` switches `nav_radio` to `Journey Planner` and populates both stops. |
| 7 | `jp_swap` button (`⇄`) | **PASS (with UI label lag)** | Swaps queries to `Kalkaji Mandir → Badarpur Border` and computes the 3 reverse corridors (`#1 · 774DOWN`, `#2 · 433UP`, `#3 · 511ADOWN`), verified in `AppTest` and live browser. *(Visible selectbox display text lags in BaseWeb; see Section 5.)* |
| 8 | GTFS active mode | **PASS** | Verified via synthetic GTFS feed in `AppTest` (`440UP`, `433UP`) and live browser upload of `sample_gtfs.zip` (`GTFS AUTHORITATIVE MODE` badge + durations `18.0 min` / `25.0 min`). |
| 9 | Balanced ranking mode | **PASS** | `Balanced (Demand + Time)` executes cleanly in GTFS mode via `AppTest`. |
| 10 | Lowest Demand Intensity ranking mode | **PASS** | Default ranking orders lower-demand routes first (`440UP` before `433UP` in synthetic GTFS test; `774UP` before `433DOWN` and `511AUP` in sample mode). |
| 11 | Route Geometry map | **PASS** | Renders `Route Geometry` Plotly map tab (`793.3 x 380 px`) when GTFS coordinates are active; displays honest unavailable-coordinates message when GTFS is absent. |
| 12 | Multiple journey options | **PASS** | Displays all 3 competing direct routes for `Badarpur Border → Kalkaji Mandir` with per-route Layer A/B/C metrics and dossier expanders. |
| 13 | Empty results & unavailable data | **PASS** | Unconnected stop pair (`Badarpur Border → Inder Lok Metro Station`) displays explicit no-direct-route info message; inactive routes/windows report `N/A` without fabricating `0 pax`. |

---

## 3. Automated Test Results

All automated suites were executed **after the final code edits**:

| Test Suite | Command | Result | Key Observed Output |
|---|---|---|---|
| **Evaluator Suite** | `python audit.py` | **PASS** | `FAILURES : 0`, `WARNINGS : 0`; `25,000` sample rows reconciled (`24,215` forward + `24` backward + `761` excluded); `2,793` segments; `0` ranking inversions across `171` OD pairs. |
| **Validation Suite** | `python scripts\validate.py` | **PASS** | All `7` checks passed (`321,793` pax-segments, `26,938` pax-journeys, avg `11.95` segments, `71.4%` peak share, hourly sum `26,938 == 26,938`). |
| **Streamlit Smoke Test** | `python smoke_test.py` | **PASS** | All `5` pages passed (`Overview`, `Route Analytics`, `Segment Explorer`, `Journey Planner`, `Data Quality`) with `0` exceptions. |
| **12-Case Regression Suite** | `python tests\test_regression.py` | **PASS** | `ALL 12 REGRESSION TEST GROUPS PASSED.` (`100k-row pipeline: clean=1.82s, topo=0.75s, segs=0.99s, total=3.56s`; all `5` AppTest pages + empty CSV passed). |
| **Journey Planner Swap & Multi-Option AppTest** | Inline `AppTest` on `app.py` | **PASS** | Verified `ov_go_jp` redirect (`3` options for `Badarpur Border → Kalkaji Mandir`), `jp_swap` both with typed queries and dropdown-only state (`origin_choice` / `destination_choice` swapped). |

---

## 4. Browser QA Results (`http://localhost:8501`)

Inspected directly in a live Chromium browser (`1440x900` desktop + `1080x800`, `860x800`, `720x800` viewports) with `0` console/page errors and `0` `.stException` tracebacks:

| Area | Status | Observed Browser Behavior |
|---|---|---|
| **CSS Injection (`st.html`) & Dark Grid** | **PASS** | `31,361`-char custom `<style>` block injected; dark `#070910` (`rgb(7, 9, 16)`) grid canvas active; Space Grotesk, Inter, and JetBrains Mono fonts referenced. |
| **Sidebar Active Radio Glow & Telemetry** | **PASS** | Cyan active left border, glow, and pulsing dot render cleanly with clear spacing after the padding fix; `SYSTEM TELEMETRY` box displays source, counts, and mode. |
| **All 5 Pages Navigation** | **PASS** | `01 · OVERVIEW`, `02 · JOURNEY INVESTIGATION`, `03 · ROUTE INTELLIGENCE`, `04 · SEGMENT EXPLORER`, and `05 · DATA FORENSICS` all render cleanly with `1` `<h1>` per page and `0` horizontal page overflow. |
| **Plotly Dark Backgrounds & Legends** | **PASS** | All Plotly charts render with dark backgrounds, readable legends, and no `"undefined"` chart titles after the `title=""` fix. |
| **Horizontal Tracer & Corridor Scrolling** | **PASS** | Both `.ll-tracer-track` (`Journey Investigation`) and `.ll-corridor` (`Segment Explorer`) scroll horizontally inside their containers without overflowing the page. |
| **Responsive Breakpoints (`1080px`, `860px`, `720px`)** | **PASS** | Tested on `01 · OVERVIEW` and `02 · JOURNEY INVESTIGATION`: `.stApp` width matched viewport (`1080`, `860`, `720`) with `0` horizontal overflow; `.ll-hud-strip` adapted to `3+1` (`1080px`) and `2x2` (`860px`, `720px`); `.ll-kpi-grid` adapted cleanly. |
| **Ticket CSV Upload (`tickets_sample.csv`)** | **PASS** | Uploaded `tickets_sample.csv` (`4.1 MB`) via `Data & GTFS Sources`; `SYSTEM TELEMETRY` updated to `Uploaded: tickets_sample.csv` and hero badge updated cleanly. |
| **GTFS ZIP Upload (`sample_gtfs.zip`)** | **PASS** | Uploaded synthetic `sample_gtfs.zip` (`0.8 KB`); `SYSTEM TELEMETRY` switched to `MODE · ACTIVE · GTFS-FIRST`, Overview matrix switched to GTFS Geographic Network, and Journey Investigation rendered GTFS durations and `Route Geometry` map tab. |

---

## 5. Remaining Bugs / Minor Polish Notes

1. **Client-side `st.selectbox` label lag on `⇄` swap (`app_pages.py:561,587`):** Clicking `⇄` swaps `jp_query_o`/`jp_query_d`, updates `Direct Corridors` and `Active Route Trace` accurately to the reverse direction (`Kalkaji Mandir → Badarpur Border`), and passes Python `AppTest` state checks, but Streamlit/BaseWeb's selectbox DOM display retains the pre-swap text label until interacted with.
2. **Ordinal percentile grammar (`app_pages.py:758`):** Evidence text formats percentiles as `{int(round(net_pct * 100))}th pct` (producing e.g. `91th pct`, `94th pct` instead of `91st` / `94th`).
3. **Dense central scatter label overlap & `860px` clipping (`app_pages.py:283-291`):** In `City Corridor Movement Matrix` (without GTFS), top-12 hub labels can overlap in the central spring-layout cluster and slightly clip near right edges at `860px` width.
4. **CARTO basemap tiles in restricted environments (`app_pages.py:220,886`):** `carto-darkmatter` map panels render the Plotly markers/stops cleanly, while external map tile imagery appears as a dark gray surface if external tile requests are blocked or fail.
5. **Expanded sidebar overlay at `720px`:** Default Streamlit behavior overlays the expanded sidebar over the left portion of the main canvas at `720px` until collapsed by the user.

---

## 6. Unverified Features

* **Full ~290 MB October ONDC dataset (~2.5M rows):** Not present in the workspace (`data/raw/` and `data/cache/` are empty); performance was benchmarked up to `100,000` rows (`3.56s` total in `tests/test_regression.py` Case 11).
* **`.parquet` / `.pq` file upload via browser UI:** Verified `.csv` upload in the live browser and Parquet read support in `src/data_loader.py` / `audit.py`, but did not upload a `.parquet` file through the browser widget.
* **GTFS `Balanced (Demand + Time)` ranking switch in live browser:** Verified via `AppTest` (`test_gtfs_flows.py`); in the live browser, `Lowest Demand Intensity` GTFS mode and `Route Geometry` tab were verified after uploading `sample_gtfs.zip`.
* **Multi-leg transfer routing, vehicle trip-ID clustering, `calendar.txt`/`frequencies.txt` parsing, and GTFS-RT:** Intentionally unimplemented per project scope (`README.md` / `TECHNICAL_NOTE.md`).

---

## 7. Exact Windows Run Commands

### Launch Dashboard (PowerShell)
```powershell
cd C:\Users\Asus\Desktop\Loadlens
python -m pip install -r requirements.txt
streamlit run app.py
```
Or via the included launcher:
```powershell
cd C:\Users\Asus\Desktop\Loadlens
.\run.bat
```

### Run All Automated Tests (PowerShell)
```powershell
cd C:\Users\Asus\Desktop\Loadlens
python audit.py
python scripts\validate.py
python smoke_test.py
python tests\test_regression.py
```
