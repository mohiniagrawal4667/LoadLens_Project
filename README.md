# LoadLens — Historical Demand & Direct Journey Comparator for Delhi Buses

> **Hackathon Submission · Transport Stack 2026 · Problem Statement 2**  
> Built from historical ONDC bus e-ticketing streams (with optional static GTFS integration).

LoadLens estimates **historical ticketed passenger demand on consecutive bus route segments** in Delhi and compares **direct (0-transfer)** bus route options between any two stops across selectable IST hour-bucket windows and weekday/weekend filters.

> **Proxy & Zero-Fabrication Guarantee:** Historical ticket demand is a **demand proxy for crowdedness**, not a direct measurement of physical onboard bus occupancy, bus capacity, or seat availability. Every figure is computed strictly from the active ticket dataset (and optional user-supplied static GTFS files). Live GPS positions, missing `vehicle_number` values, and uncertain route topologies are never fabricated.

---

## Documentation

* **Proposal:** [PROPOSAL.md](PROPOSAL.md)
* **Technical Note:** [TECHNICAL_NOTE.md](TECHNICAL_NOTE.md)
* **Configuration:** [.env.example](.env.example), [.streamlit/config.toml](.streamlit/config.toml), [Dockerfile](Dockerfile), [.dockerignore](.dockerignore)

---

## Key Features

* **Segment-load reconstruction (`src/load_engine.py`):** Every valid forward ticket (`start_rank < end_rank`) adds `passenger_count` to every consecutive segment $s$ where $b \le s < e$ (pre-aggregated by OD rank pairs). Back-tracked (`start_rank > end_rank`), same-stop, and uncertain-topology rows are counted separately and excluded.
* **Journey ranking (`src/journey_planner.py`, `src/gtfs.py`):**
  * **Without GTFS (topology mode):** Competing direct routes are ranked in **ascending order of historical average daily segment demand** (`avg_daily_segment_load`, defined as `mean_segment_load / active_days`, falling back to `mean_segment_load` if `active_days` is unavailable), with ties broken by `max_segment_load` and `segment_count`. Inactive routes with zero tickets in the selected window sort last and display `N/A`.
  * **With supplied GTFS (`trips.txt`, `stop_times.txt`):** Ranks adequately matched routes (`>= 50%` eligible stop match) first by `pax_per_gtfs_trip` (or `avg_daily_segment_load` / `mean_segment_load`), with an optional `"Balanced (Demand + Time)"` ranking (`0.65 * normalized_demand + 0.35 * normalized_duration`).
  * Lower-ranked routes represent **lower historical ticketed segment demand**, not verified lower physical onboard occupancy.
* **Time-window hour buckets (`src/load_engine.py`, `src/analytics.py`):** Filtering slices `ticket_hour` (IST `Asia/Kolkata` ticket-creation hour) using inclusive hour buckets:
  * **Morning Peak:** `08:00–11:59 IST` (`ticket_hour` 8, 9, 10, 11)
  * **Midday:** `12:00–16:59 IST` (`ticket_hour` 12, 13, 14, 15, 16)
  * **Evening Peak:** `17:00–21:59 IST` (`ticket_hour` 17, 18, 19, 20, 21)
  * **Off-Peak / Night:** `22:00–07:59 IST` (`ticket_hour` 22, 23, 0–7)
  * **All Peak:** `08:00–11:59 & 17:00–21:59 IST`
* **Safe topology & optional static GTFS (`src/topology.py`, `src/gtfs.py`):** When static GTFS (`stops.txt`, `routes.txt`, `trips.txt`, `stop_times.txt`) is supplied, ticket OD pairs match directly onto canonical trip sequences with scheduled median durations and stop coordinates (`stop_lat`, `stop_lon`). Without GTFS, a chain-preserving DAG orders linear chains while isolating minor disconnected islands (`partial_disconnected`) and flagging circular/ambiguous routes (`uncertain_circular`, `uncertain_ambiguous`, `uncertain_disconnected`) without fabricating intermediate loads.
* **Resilient ingestion & upload limits (`src/data_loader.py`, `src/gtfs.py`):** Supports `.csv` and `.parquet`/`.pq` via sidebar upload (configured up to `512 MB` in `.streamlit/config.toml`), `LOADLENS_TICKETS`, `data/raw/`, or `data/cache/`, with automatic chunked CSV ingestion (`> 25 MB` on disk) and bounded GTFS ZIP extraction (rejecting path traversal, symlinks, and decompression bombs).
* **Five-module dashboard (`app.py`, `app_pages.py`, `src/ui_theme.py`):** Overview, Journey Investigation, Route Intelligence, Segment Explorer, and Data Forensics.

---

## Architecture & Technology Stack

* **UI & Visualization:** Streamlit `1.54.0`, Plotly `7.1.0`, custom HTML/CSS (`src/ui_theme.py`)
* **Data & Graph Engine:** Pandas `2.3.3`, PyArrow `23.0.0`, NumPy `2.4.2`, NetworkX `3.7`, python-dateutil `2.9.0.post0`, pytz `2025.2`
* **Bundled sample dataset:** Ships with a **25,000-row sample** (`data_sample/tickets_sample.csv`, spanning `2026-10-01` to `2026-10-31`, containing **60 route-direction labels** across 35 route+variant codes / 33 base route numbers) so the dashboard runs out of the box.

---

## Quick Start (Local Execution)

### 1. Install Python 3.10+ and dependencies

```bash
python -m pip install -r requirements.txt
```

### 2. Launch the dashboard

```bash
streamlit run app.py
```

Or use the platform launchers:

```powershell
.\run.bat      # Windows
```
```bash
./run.sh       # Linux / macOS
```

Open <http://localhost:8501>. By default (when `LOADLENS_TICKETS`, `data/cache/`, and `data/raw/` are absent), LoadLens loads `data_sample/tickets_sample.csv`.

### 3. Using an external full ticket dataset (optional, not bundled)

See [.env.example](.env.example). Only the optional `LOADLENS_TICKETS` environment variable is used. To pre-build Parquet caches in `data/cache/` from a local CSV/Parquet file:

```powershell
$env:LOADLENS_TICKETS = "C:\path\to\tickets.parquet"
python scripts/build_processed.py --force
streamlit run app.py
```

Or upload `.csv`/`.parquet` and optional GTFS `.zip` archives (`stops.txt`, `routes.txt`, `trips.txt`, `stop_times.txt`) in the sidebar under **Data & GTFS Sources** (`.streamlit/config.toml` sets `maxUploadSize = 512` MB).

---

## Testing & Validation

```bash
python audit.py                  # 11-section evaluator & synthetic edge-case suite
python scripts/validate.py       # Row accounting, non-negative loads, traceability & hourly checks
python smoke_test.py             # Headless Streamlit AppTest across all 5 pages
python tests/test_regression.py  # 15-group regression suite (math, topology, GTFS, security, chunking, AppTest)
```

---

## Deployment

Includes [Dockerfile](Dockerfile), [.dockerignore](.dockerignore), and [.streamlit/config.toml](.streamlit/config.toml):

```bash
docker build -t loadlens .
docker run -p 8501:8501 loadlens
```

The container exposes port `8501` and configures a Docker `HEALTHCHECK` against `/_stcore/health`.

* **Memory sizing:** The bundled 25,000-row sample runs comfortably on ~1 GB RAM platforms (e.g., Streamlit Community Cloud). Larger multi-million-row datasets (~290 MB / ~2.56M rows) are not bundled or tested at full scale in this repository and would require container hosts with $\ge 2\text{ GB}$ RAM using prebuilt `data/cache/` Parquet files rather than in-browser CSV uploads.

---

## Explicit Methodology Limitations & Verified Scope

1. **Historical demand proxy, not onboard occupancy:** Segment loads reflect historical e-ticketing demand (`passenger_count` summed across traversed route segments), not physical bus passenger counts, vehicle capacity, or real-time seat availability.
2. **Direct (0-transfer) routes only:** Journey comparison evaluates single-bus direct routes only; transfer-aware / multi-leg routing is not implemented.
3. **No real GTFS feed bundled or independently verified:** No official Delhi GTFS feed ships in `data/gtfs/`. GTFS mode has only been tested in this repository using controlled synthetic/toy GTFS fixtures.
4. **No GPS or live vehicle-position feeds:** Live GPS / GTFS-RT feeds are not ingested or used anywhere in the repository. Geographic maps only plot static stop coordinates (`stop_lat`, `stop_lon`) when provided in an uploaded/local static GTFS `stops.txt`.
5. **Sample-scale validation (25,000 rows, not 2.56M rows):** The complete ~2.56-million-row dataset is not present in this repository and has not been validated end-to-end here; automated verification runs on the 25,000-row sample (`data_sample/tickets_sample.csv`) and synthetic/scaled fixtures (tested up to 100k–250k rows).
6. **GTFS duration, service-calendar, and timestamp limitations:**
   * Scheduled travel durations use the median `stop_times.txt` (`departure_time` to `arrival_time`) across trips serving the OD pair; trips without valid times report `Unavailable`.
   * `calendar.txt`, `calendar_dates.txt`, and `frequencies.txt` are not parsed, so `gtfs_scheduled_trips` / Layer D (`pax_per_gtfs_trip`) reflect raw `trips.txt` trip counts rather than day-of-week-filtered service schedules or headways.
   * `created_at` is normalized to IST (`Asia/Kolkata`) and represents ticket-creation time, not verified physical boarding time; missing `vehicle_number` values (~44.7% of the sample) are never imputed.
