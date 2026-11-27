# LoadLens — Performance and Scalability Report

> **Benchmark Date:** 2026-11-27  
> **Hardware / Runtime:** Windows, Python 3.14.3, Pandas 2.3.3, PyArrow 23.0.0, NumPy 2.4.2  
> **Dataset Scope Note:** The full ~290 MB (~2.56M-row) raw dataset is **not present** in this workspace. All timings and memory measurements below were directly observed using `data_sample/tickets_sample.csv` (`25,000` rows, `4.34 MB`) and deterministic `4x` (`100,000` rows) and `10x` (`250,000` rows) concatenated copies. Full 2.56M-row behavior is analyzed structurally rather than falsely claimed as executed.

---

## 1. Phase 9 Performance Optimizations Implemented

1. **OD-Collapsed Segment Expansion (`src/load_engine.py:compute_segment_loads`):**
   - **Previous Bottleneck:** Expanded every individual forward ticket row (`np.repeat(..., seg_count)`) across ~12 segments before grouping. On 2.56M rows, this would materialize ~30.7M rows in Python object/float arrays before `groupby`.
   - **Optimization:** Added pre-aggregation by `(route, direction, start_rank, end_rank)` summing `passenger_count`, ticket counts, `veh_pax`, and `veh_tkt` *prior* to `np.repeat`.
   - **Impact:** Reduces `segs` expansion work and peak traced memory dramatically while yielding bit-for-bit identical output (`2,793` segments verified against brute-force reference).
2. **Chunked CSV Ingestion (`src/data_loader.py:load_clean_csv_chunked`):**
   - **Previous Bottleneck:** Reading and copying a >250 MB raw CSV in a single DataFrame held both raw 19-column text arrays and intermediate normalized copies simultaneously.
   - **Optimization:** `load_clean()` automatically routes `.csv` files `> 25 MB` through `load_clean_csv_chunked(chunksize=250_000)`, cleaning each chunk, retaining only the 18 essential schema columns, and aggregating `dq_report` counters across chunks.

---

## 2. Measured Pipeline Benchmarks (Before vs. After Phase 9)

### End-to-End Pipeline (`clean_with_report` + `build_route_topology_with_meta` + `compute_segment_loads`)
Measured with `tracemalloc` active (note: `tracemalloc` adds overhead to Python graph loops; untrace-measured 100k time is shown separately):

| Scale | Stage | Before Phase 9 (`tracemalloc`) | After Phase 9 (`tracemalloc`) | Delta |
|---|---|---|---|---|
| **25,000 rows** (`1x` sample) | `clean` / `topo` / `segs` | `1.50s` / `1.62s` / `0.44s` | `1.64s` / `1.93s` / `0.58s` | — |
| **25,000 rows** | **Total / Peak Traced RAM** | `3.57s` / **`61.8 MB`** | `4.15s` / **`35.7 MB`** | **`-42.2%` peak RAM** |
| **100,000 rows** (`4x` sample) | `clean` / `topo` / `segs` | `4.41s` / `1.50s` / `0.69s` | `5.07s` / `1.67s` / `0.55s` | — |
| **100,000 rows** | **Total / Peak Traced RAM** | `6.60s` / **`228.0 MB`** | `7.29s` / **`70.1 MB`** | **`-69.3%` peak RAM** |
| **250,000 rows** (`10x` sample) | `clean` / `topo` / `segs` | `11.03s` / `1.63s` / `1.36s` | `14.91s` / `1.86s` / `0.68s` | `segs` **`2.0x` faster** |
| **250,000 rows** | **Total / Peak Traced RAM** | `14.01s` / **`529.3 MB`** | `17.46s` / **`174.9 MB`** | **`-67.0%` peak RAM (`3.0x` lower)** |

### Untraced 100,000-Row Pipeline Benchmark (`tests/test_regression.py` Case 11, no `tracemalloc`)
* `clean = 1.73s`, `topo = 0.72s`, `segs = 0.46s`, **`total = 2.91s`** (well under the `20.0s` regression gate).

### Chunked vs. Single-Shot CSV Disk Read (`250,000` rows, `43.4 MB` CSV, `tracemalloc` active)
* **Single-shot (`clean_with_report(pd.read_csv(...))`):** `133.99s`, peak traced RAM `177.3 MB`.
* **Chunked (`load_clean_csv_chunked(..., chunksize=50_000)`):** **`57.79s`** (`2.32x` faster), peak traced RAM **`143.2 MB`** (`-19.2%` RAM).

---

## 3. Caching & UI Runtime Characteristics

* **Dataset bootstrap (`app.py`):** `@st.cache_data` caches `_load_default_dataset` (by file size/mtime signature) and `_process_uploaded_bytes` (by uploaded buffer). Pre-built `data/cache/*.parquet` skips CSV cleaning and topology reconstruction on startup.
* **Interactive filters (`app_pages.py`):** `_cached_stop_index`, `_cached_window_slice`, and `_cached_city_network` cache derived slices per `dataset_sig`, preventing full re-aggregation on UI radio/tab switches.
* **GTFS caching (`src/gtfs.py`):** `_load_gtfs_feed_cached` uses `functools.lru_cache(maxsize=4)` keyed by `(file_size, mtime_ns)`.
* **Chart rendering caps:** Overview schematic caps at `45` nodes / `110` edges; Route Analytics heatmap caps at top `15` routes; Route Tracer caps at `24` stops; Corridor Strip caps at `35` segments.

---

## 4. Scalability Assessment for ~2.56M Rows (Unverified Directly at Full Scale)

* **Prebuilt Cache Path (`scripts/build_processed.py` → `data/cache/*.parquet`):**
  - `load_clean_csv_chunked` bounds CSV cleaning RAM to ~250k-row slices, and OD-collapsed `compute_segment_loads` prevents multi-gigabyte segment expansion arrays.
  - Once built, `app.py` loads `tickets_clean.parquet`, `segment_loads.parquet`, and `trip_graph.parquet`. Holding `2.56M` cleaned ticket rows in Pandas `object` strings typically consumes ~`600 MB–1.1 GB` RSS (estimated from `250k` footprint, not directly measured on 2.56M rows).
* **Browser Upload Path (`st.file_uploader`):**
  - Configured with `maxUploadSize = 512` MB in `.streamlit/config.toml`. However, uploading a ~290 MB CSV via the browser holds raw bytes + parsed DataFrame in memory inside the web worker (`_process_uploaded_bytes` does not use disk chunking because it reads an in-memory buffer). For full 2.56M-row datasets, CLI cache building via `scripts/build_processed.py` on a $\ge 2\text{ GB}$ RAM host is strongly recommended over in-browser CSV upload.
