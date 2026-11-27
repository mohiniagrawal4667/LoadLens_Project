# LoadLens — Final Changelog (Recovery, QA & Competition Readiness)

> **Date:** 2026-11-27  
> **Baseline Commits:** `a6f9069` (pre-QA state) → `8de71ef` (post-QA UI fixes) → final Phase 9–10 working tree.

---

## 1. Critical & High-Priority Engineering Fixes (P0 / P1)

### P0 — Broken Journey Planner Stop Timeline (`src/ui_theme.py`)
* **What was wrong:** During the prior partial redesign, `dot_cls = "origin" if i == 0 else ""` was deleted inside `stop_timeline_html()` while `<div class="ll-tl-dot {dot_cls}"></div>` remained, causing a `NameError` crash whenever `Journey Planner` matched a direct route.
* **What changed:** Restored `dot_cls = "origin" if i == 0 else ""` before the dot element and added a `ll-tl-dot origin` assertion in `tests/test_regression.py` Case 5.
* **Why correct:** Restores both runtime stability and visual origin styling.
* **Tested via:** `smoke_test.py`, `tests/test_regression.py` Case 5, `AppTest`, and live Chromium (`Badarpur Border → Kalkaji Mandir`).

### P0 — GTFS ZIP Extraction Security Hardening (`src/gtfs.py`, `app.py`)
* **What was wrong:** `extract_gtfs_zip()` read entire archive members unbounded (`zf.read(member)`) with no decompression-bomb cap, member-count cap, or explicit symlink / `..` traversal rejection; `app.py` checked only `(target / "stops.txt").exists()` before skipping extraction.
* **What changed:** Added `MAX_GTFS_MEMBER_BYTES` (`150 MB`), `MAX_GTFS_UNCOMPRESSED_BYTES` (`250 MB`), `MAX_GTFS_ARCHIVE_MEMBERS` (`64`), `..` / null-byte / Unix symlink rejection, streaming byte-counted reads, and `gtfs_status(target)["available"]` verification + partial folder cleanup in `app.py`.
* **Why correct:** Protects public deployments against ZIP bombs and malformed/unsafe archive entries.
* **Tested via:** `tests/test_regression.py` Cases 7 & 13 and live browser GTFS `.zip` upload.

### P1 — Scalability Optimizations for Multi-Million-Row Datasets (`src/load_engine.py`, `src/data_loader.py`)
* **What was wrong:** `compute_segment_loads()` expanded every valid individual ticket row across ~12 segments before grouping (`~30.7M` rows at `2.56M` scale), and `load_clean()` always loaded entire CSV files in one shot.
* **What changed:**
  - Added OD pre-aggregation by `(route, direction, start_rank, end_rank)` before `np.repeat` segment expansion in `compute_segment_loads()`.
  - Added `load_clean_csv_chunked()` (`chunksize=250_000`) automatically triggered by `load_clean()` for `.csv` files `> 25 MB`.
* **Why correct:** Mathematically identical segment/vehicle sums ($L_s = \sum \text{passenger\_count}$ for $b \le s < e$) with `3.0x` lower peak traced memory (`529.3 MB` → `174.9 MB` at `250k` rows) and `2.3x` faster chunked CSV ingestion.
* **Tested via:** Brute-force naive $L_s$ reference proof (`2,793/2,793` segments exact), `25k`/`100k`/`250k` benchmarks, and `tests/test_regression.py` Case 14.

### P1 — `⇄` Swap Button State & BaseWeb Selectbox Label Sync (`app_pages.py`)
* **What was wrong:** `_swap_jp_queries()` swapped only `jp_query_o` / `jp_query_d` and popped `origin_choice` / `destination_choice`, failing when dropdown-only stops were selected and causing BaseWeb selectbox display labels to remain stale after clicking `⇄`.
* **What changed:** Updated `_swap_jp_queries()` to fall back to `origin_choice` / `destination_choice`, align `_prev_jp_query_*`, and assign the swapped stops directly (with membership validation guards in `render_journey_planner`).
* **Why correct:** Keeps both Python search state and BaseWeb visible labels synchronized when swapping stops.
* **Tested via:** `AppTest` (`ov_go_jp` + `jp_swap` + dropdown-only swap) and live Chromium browser (`Badarpur Border → Kalkaji Mandir` → `⇄` → `Kalkaji Mandir → Badarpur Border`).

---

## 2. Medium & Low-Priority Fixes (P2 / P3)

* **Date-range test expectation alignment (`tests/test_regression.py:296`):** Updated assertion from `"2026-12-01 to 2026-12-05"` to `"2026-12-01 → 2026-12-05"` matching `app_pages.py:134`'s intentional `→` UI separator.
* **Plotly `"undefined"` chart title fix (`app_pages.py`):** Passed explicit `title=""` to untitled Plotly figures using `_plotly_defaults()` (`title_font` without `title` caused Plotly.js to render `"undefined"`). Verified `0` occurrences in live browser.
* **Sidebar active radio dot spacing (`src/ui_theme.py:210`):** Increased right padding (`1.85rem`) so the pulsing cyan indicator dot no longer overlaps label characters. Verified in live browser.
* **Ordinal percentile formatting (`app_pages.py:143,_ordinal`):** Fixed `"91th pct"` → `"91st pct"` / `"73rd pct"` etc., verified via `test_regression.py` Case 15 and live browser.
* **UI hygiene (`app.py`, `app_pages.py`, `src/ui_theme.py`):** Quoted `style` attribute in `app.py:267`, removed 6 duplicate `####` headings under `section_eyebrow` dividers, and removed unused dead CSS classes (`.ll-skeleton`, `.ll-chip*`, `@keyframes ll-march`).
* **Deployment & repo hygiene:** Removed unused empty `package-lock.json`, added `.env.example`, `Dockerfile`, `.dockerignore`, updated `.gitignore` (`.env`), and updated `README.md` to reflect actual implemented behavior and reports.
