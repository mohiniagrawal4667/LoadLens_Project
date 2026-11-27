# LoadLens — Crowdedness-Aware Journey Planner for Delhi Buses

> **Hackathon Submission · Transport Stack 2026 · Problem Statement 2**  
> Built end-to-end from historical ONDC bus e-ticketing streams (with optional static GTFS integration).

LoadLens estimates **historical passenger demand on every consecutive bus route segment** in Delhi and uses it to compare direct (0-transfer) journey options between any two stops across selectable IST time windows (Morning Peak, Midday, Evening Peak, Off-Peak/Night, Weekdays vs. Weekends).

> **Zero-Fabrication Guarantee:** No live capacity, physical bus occupancy, or seat availability is ever claimed. Every figure is a *historical ticket-derived demand signal* computed strictly from the active ticket dataset (and optional supplied GTFS files). Missing `vehicle_number` values, absent GPS coordinates, and uncertain route topologies are never fabricated.

---

## Documentation & Audit Artifacts

- **Proposal:** [PROPOSAL.md](PROPOSAL.md)
- **Technical Note:** [TECHNICAL_NOTE.md](TECHNICAL_NOTE.md)
- **Engineering & Competition Reports:**
  - [FINAL_ARCHITECTURE_AUDIT.md](FINAL_ARCHITECTURE_AUDIT.md)
  - [COMPETITION_ALIGNMENT_REPORT.md](COMPETITION_ALIGNMENT_REPORT.md)
  - [ALGORITHM_AND_DATA_VALIDATION.md](ALGORITHM_AND_DATA_VALIDATION.md)
  - [PERFORMANCE_REPORT.md](PERFORMANCE_REPORT.md)
  - [DEPLOYMENT_READINESS_REPORT.md](DEPLOYMENT_READINESS_REPORT.md)
  - [FINAL_TEST_REPORT.md](FINAL_TEST_REPORT.md)
  - [FINAL_CHANGELOG.md](FINAL_CHANGELOG.md)

---

## Key Features

* **Mathematical segment-load reconstruction (`src/load_engine.py`):** Every valid forward ticket (`start_rank < end_rank`) adds `passenger_count` to every consecutive segment $s$ where $b \le s < e$ (pre-aggregated by OD rank pairs for low memory overhead on multi-million-row streams). Back-tracked (`start_rank > end_rank`), same-stop, and uncertain-topology rows are tracked separately and excluded.
* **Layered demand model:** Ranks competing direct routes using raw segment totals (Layer A), **average daily segment intensity** over observed `active_days` (Layer B), **vehicle-tagged demand per observed vehicle ID** where coverage $\ge 25\%$, distinct vehicles $\ge 2$, and tagged tickets $\ge 5$ (Layer C), and **daily demand per scheduled GTFS trip** when GTFS is supplied (Layer D), with optional `"Balanced (Demand + Time)"` ranking.
* **Safe topology & GTFS-first sequencing (`src/gtfs.py`, `src/topology.py`):** When GTFS is supplied (`stops.txt`, `routes.txt`, `trips.txt`, `stop_times.txt`), ticket OD pairs match directly onto canonical trip sequences with real scheduled travel durations and stop geometry maps. Without GTFS, a chain-preserving DAG reconstructs linear chains while isolating minor disconnected islands (`partial_disconnected`) and flagging circular/ambiguous routes (`uncertain_circular`, `uncertain_ambiguous`, `uncertain_disconnected`) without fabricating intermediate loads.
* **Resilient ingestion & upload security (`src/data_loader.py`, `src/gtfs.py`):** Supports `.csv` and `.parquet`/`.pq` via sidebar upload (up to `512 MB`), `LOADLENS_TICKETS`, `data/raw/`, or `data/cache/`, plus automatic chunked CSV processing (`> 25 MB`) and bounded ZIP extraction (rejecting path traversal, symlinks, and decompression bombs).
* **Five-module dark urban-intelligence UI (`app.py`, `app_pages.py`, `src/ui_theme.py`):**
  1. `01 · OVERVIEW` — Cinematic hero, 5-cell telemetry HUD, City Corridor Movement Matrix, quick-plan console, top-5 corridor alerts.
  2. `02 · JOURNEY INVESTIGATION` — Stop autocomplete, animated SVG route trace, stop-by-stop timeline, time/day filters, layered dossier cards, GTFS geometry map.
  3. `03 · ROUTE INTELLIGENCE` — Route rankings, peak/off-peak split, vehicle telemetry coverage, weekday/weekend dynamics, route × hour heatmap.
  4. `04 · SEGMENT EXPLORER` — Animated corridor demand schematic, per-segment dossier, bottleneck isolation, hourly pulse.
  5. `05 · DATA FORENSICS` — Class A/B/C evidence classification, row-level exclusion ledger, hourly telemetry coverage, topology reliability audit.

---

## Architecture & Technology Stack

* **UI & Visualization:** Streamlit `1.54.0`, Plotly `7.1.0`, custom HTML/CSS (`src/ui_theme.py`)
* **Data & Graph Engine:** Pandas `2.3.3`, PyArrow `23.0.0`, NumPy `2.4.2`, NetworkX `3.7`, Python-Dateutil `2.9.0.post0`, Pytz `2025.2`
* **Auto-fallback sample:** Ships with a 25,000-row sample (`data_sample/tickets_sample.csv`, 60 routes) so the dashboard runs immediately out of the box.

---

## Quick Start (Local Execution)

### 1. Install Python 3.10+ and dependencies

```bash
cd Loadlens
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

Open <http://localhost:8501>. By default, LoadLens loads `data_sample/tickets_sample.csv`.

### 3. Using a full ticket dataset (~290 MB / ~2.56M rows)

See [.env.example](.env.example). Pre-build Parquet caches before launching for instant UI startup:

```powershell
$env:LOADLENS_TICKETS = "C:\path\to\october_tickets.parquet"
python scripts/build_processed.py $env:LOADLENS_TICKETS --force
streamlit run app.py
```

Or upload `.csv`/`.parquet` and optional GTFS `.zip` archives (`stops.txt`, `routes.txt`, `trips.txt`, `stop_times.txt`) directly in the sidebar under **Data & GTFS Sources**.

---

## Testing & Validation

```bash
python audit.py                  # 11-section strict evaluator & edge-case suite
python scripts/validate.py       # Row accounting, non-negative loads & reconciliation
python smoke_test.py             # Headless Streamlit AppTest across all 5 pages
python tests/test_regression.py  # 15-group regression suite (math, topology, GTFS, security, chunking, AppTest)
```

---

## Deployment

Includes a production [Dockerfile](Dockerfile), [.dockerignore](.dockerignore), and [.streamlit/config.toml](.streamlit/config.toml):

```bash
docker build -t loadlens .
docker run -p 8501:8501 loadlens
```

* **Recommended hosting for full ~2.56M dataset:** Container platforms with $\ge 2\text{ GB}$ RAM (e.g., Render, Railway, Fly.io, Cloud Run) using prebuilt `data/cache/` Parquet files.
* **Streamlit Community Cloud (1 GB RAM):** Suitable for the bundled 25,000-row sample or smaller subsets; full 2.56M-row in-memory CSV uploads exceed free-tier 1 GB RAM limits.

---

## Explicit Methodology Limitations

| Concern | LoadLens Behavior |
|---|---|
| `created_at` vs. boarding time | Normalised to IST (`Asia/Kolkata`) and labelled as ticket-creation time. |
| Missing `vehicle_number` (~44.7% sample) | Never imputed; Layer C (`pax_per_observed_vehicle`) runs strictly on `has_vehicle == True` when coverage $\ge 25\%$, distinct vehicles $\ge 2$, tagged tickets $\ge 5$. |
| Circular / ambiguous routes without GTFS | Flagged (`uncertain_circular`, `uncertain_ambiguous`, `uncertain_disconnected`) and excluded from synthetic linear segment expansion. |
| Missing GTFS schedule files | Durations and GPS maps are disabled (`Unavailable` / `Requires GTFS`), never heuristically guessed. |
| Unmatched GTFS routes & zero-ticket windows | Unmatched routes display `N/A`; zero-ticket segments on active routes remain in the denominator (`0 tickets in window`). |
| Multi-leg transfers & live occupancy | Direct (0-transfer) bus routes only; live occupancy and seat availability are out of scope. |
