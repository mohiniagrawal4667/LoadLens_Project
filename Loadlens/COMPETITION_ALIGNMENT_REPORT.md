# LoadLens — Competition Alignment Report

> **Competition:** Transport Stack Hackathon 2026  
> **Problem Statement 2:** Crowdedness-Aware Journey Planner  
> **Evaluation Policy:** Scored strictly on verified codebase behavior and live inspection.

---

## 1. Alignment Assessment Against Problem Statement

| Criterion | Evaluation | Evidence in Codebase |
|---|---|---|
| **Does it solve the stated problem?** | **Yes (within direct-route scope)** | Compares competing bus routes between any two stops using segment-level historical ticket demand across selectable IST time windows and day types (`src/journey_planner.py`, `src/gtfs.py`, `app_pages.py`). |
| **Does it genuinely help commuters compare journey options?** | **Yes** | Displays ranked route cards with Layer A/B/C/D demand metrics, Network Load Percentile tiers, stop-by-stop timelines highlighting bottlenecks, and (when GTFS is present) scheduled travel durations and `+X.Xm` time trade-offs (`_render_option_card`). |
| **Does it use passenger demand at segment level?** | **Yes** | Implements exact consecutive segment accumulation $L_s = \sum \text{passenger\_count}$ for $b \le s < e$ in `src/load_engine.py` and `src/gtfs.py`, avoiding naive origin-to-destination-only counts. |
| **Are the rankings meaningful?** | **Yes** | Zero cross-route `mean_segment_load` inversions across `171` multi-route OD pairs in `audit.py`; ranks by comparable daily/trip intensity, prioritizes adequate GTFS coverage (`>=50%`) over sparse partial matches, and isolates inactive windows (`N/A`). |
| **Is the GTFS integration technically valid?** | **Yes** | Matches ticket OD pairs directly onto `stop_times.txt` sequences, supports `>=24:00:00` GTFS times, rejects ambiguous repeated-stop pairs (`ambiguous_stop_tickets`), computes real `stop_times.txt` durations, and maps `stop_lat`/`stop_lon`. |
| **Does it provide useful operator insights?** | **Yes** | `Route Intelligence`, `Segment Explorer`, and `Data Forensics` surface top bottleneck segments, hourly/weekday-weekend surges, `vehicle_number` telemetry gaps by route/hour, and topology reliability diagnostics (`uncertain_circular`, `partial_disconnected`). |
| **Is the solution feasible using available data?** | **Yes** | Handles missing GTFS, ~44.7% missing `vehicle_number`, circular routes (`OMS`), and unverified boarding timestamps transparently via explicit reliability thresholds and Class A/B/C evidence separation. |
| **What differentiates it from a conventional planner?** | **Strong differentiation** | Conventional planners optimize shortest time/hops and ignore load accumulation along intermediate stops; LoadLens quantifies segment-level crowding intensity, protects against circular/disconnected topology hallucinations, and surfaces data provenance honestly. |

---

## 2. Value vs. Cosmetic Feature Audit

* **High-value functional features:** Vectorised OD segment accumulation (`src/load_engine.py`), chain-preserving DAG + uncertainty guards (`src/topology.py`), zero-ticket window denominator preservation (`src/journey_planner.py`), GTFS-first sequence matching & Balanced vs. Demand ranking (`src/gtfs.py`), and `Data Forensics` Class A/B/C transparency (`app_pages.py`).
* **Polished visual features that serve comprehension:** `animated_route_tracer_html` and `corridor_strip_html` (`src/ui_theme.py`) directly visualize per-segment demand intensity and bottlenecks along a route; `City Corridor Movement Matrix` (`src/analytics.py`) highlights high-degree interchange hubs.
* **Lower-value / decorative elements:** CSS scanning-line animations (`@keyframes ll-scan-x`) and glowing hero borders add cyberpunk urban-intelligence polish without distorting or obscuring metrics.

---

## 3. Gaps & Missing Functionality That Could Affect Judging

1. **No 1-transfer / multi-leg routing (Biggest functional gap):** Only direct (0-transfer) bus routes are evaluated. Commuters between unconnected corridors receive an honest "direct routes only" message instead of transfer options.
2. **Bundled demo ships without local GTFS (`data/gtfs/` empty):** Out of the box, the app launches in `TICKET TOPOLOGY` mode where durations (`Requires GTFS`) and geographic maps (`Route Geometry`) are disabled until the user uploads a GTFS `.zip`.
3. **GTFS `calendar.txt` / `frequencies.txt` not parsed:** Layer D (`pax_per_gtfs_trip`) divides by total trips in `trips.txt` rather than day-of-week-filtered service schedules.
4. **No live vehicle / trip-ID inference:** Missing `vehicle_number` (~44.7% of sample) is rightly never fabricated, leaving physical bus occupancy out of scope.

---

## 4. Competition Alignment Score: **86 / 100**

| Axis | Score | Max | Evidence |
|---|---|---|---|
| Problem-Statement Fit & Commuter Utility | 22 | 25 | Direct segment-level comparison, time/day filtering, GTFS duration trade-offs; `-3` for 0-transfer-only scope. |
| Mathematical & Data Integrity | 24 | 25 | Exact $L_s$ segment math, strict uncertainty flags (`uncertain_circular`, `partial_disconnected`), zero fake occupancy/GPS; `-1` for `calendar.txt` absence. |
| Operator Intelligence & Forensics | 15 | 15 | Route rankings, heatmaps, corridor bottleneck strip, vehicle telemetry coverage audit, row-exclusion ledger. |
| GTFS Technical Validity | 13 | 15 | GTFS-first sequence matching, repeated-stop protection, partial-match guard, hardened ZIP ingestion; `-2` for empty default `data/gtfs/` and unparsed `calendar.txt`. |
| Presentation & Differentiated UX | 12 | 20 | Cohesive dark urban-intelligence UI, responsive layouts, interactive tracers; `-8` because out-of-the-box sample lacks GTFS map/duration visuals until a feed is supplied and 1-transfer routing is absent. |
| **Total** | **86** | **100** | **Strong, technically honest solution well aligned with Problem Statement 2.** |
