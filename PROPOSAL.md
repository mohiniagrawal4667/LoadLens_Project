# LoadLens — Hackathon Proposal

**Event:** Transport Stack Hackathon 2026  
**Problem Statement 2:** Crowdedness-Aware Journey Planner  
**Target Network:** Delhi Bus Network (ONDC October 2026 e-ticketing stream + optional static GTFS)

---

## 1. Problem Statement

Urban bus commuters often face unpredictable crowding even when multiple direct routes serve the same origin–destination (OD) pair. Existing route planners optimize primarily for travel time or shortest hop count while treating all bus routes as equally comfortable. Meanwhile, transit operators lack segment-level visibility into *where* along a corridor passenger load actually accumulates, because e-ticketing records capture only boarding (`start_stop_name`) and alighting (`end_stop_name`) stops rather than per-segment occupancy counts.

---

## 2. Proposed Solution: LoadLens

**LoadLens** is an end-to-end crowdedness-aware journey planner and demand analytics platform built around a **zero-fabrication guarantee**:

1. **Ticket-Derived Topology Reconstruction (`src/topology.py`)**  
   When official GTFS schedules are unavailable, LoadLens reconstructs a directed stop ordering per `(route, direction)` directly from observed OD ticket pairs using weighted directed graphs, minimum-weight cycle breaking, and hub-anchored topological sorting.
2. **Vectorised Segment-Load Aggregation (`src/load_engine.py`)**  
   Every valid forward ticket (`start_rank < end_rank`) adds `passenger_count` across every consecutive stop-to-stop segment between boarding and alighting. Reverse-ordered tickets are accounted for and excluded rather than misattributed.
3. **Time-Window & Cross-Route Demand Ranking (`src/journey_planner.py`)**  
   Commuters select boarding/destination stops plus an IST hour-bucket window (e.g., *Morning Peak 08:00–11:59 IST*, *Midday 12:00–16:59 IST*, *Evening Peak 17:00–21:59 IST*, *Off-Peak/Night 22:00–07:59 IST*) and day type (*Weekdays* vs *Weekends*). Direct route options are ranked in ascending order of **average historical daily passenger load per traversed segment** (falling back to mean segment load when active days are unavailable) and labelled with a **Network Load Percentile** (Low / Moderate / High demand), alongside a within-route bottleneck index (`Relative Load Index`).
4. **Optional Static GTFS Integration (`src/gtfs.py`)**  
   When `stops.txt`, `routes.txt`, `trips.txt`, and `stop_times.txt` are provided, LoadLens computes scheduled travel durations from `stop_times.txt`, renders stop coordinates on an interactive map, and pairs them strictly with matched route-level ticket demand.
5. **Operator Diagnostics & Data Quality Audit (`app_pages.py`)**  
   Includes Overview KPIs, Route Analytics (hourly, weekday/weekend, heatmaps, vehicle-ID coverage), Segment Explorer (corridor bottleneck strip), and Data Quality (full row-level exclusion accounting).

---

## 3. Scope, Honesty & Explicit Non-Goals

LoadLens deliberately avoids fabricating signals that are absent from the e-ticketing stream:
- **No live bus occupancy or seat availability** is claimed (ticket timestamps are normalized to IST as `created_at` ticket-creation time, and `vehicle_number` is missing on ~44.7% of the sample / ~48.5% of the full dataset snapshot).
- **No heuristic travel times or synthetic map coordinates** are generated when GTFS is absent.
- **Direct (0-transfer) routes only** in the current release.

---

## 4. Expected Impact & Next Steps

- **For Commuters:** Identify less crowded direct bus alternatives between the same stops and see stop-by-stop bottleneck segments before boarding, filtered by time of day.
- **For Operators:** Pinpoint corridor segments with the highest passenger-segment demand and monitor `vehicle_number` telemetry coverage per route and hour.
- **Post-Hackathon Roadmap:**
  1. Integrate official Delhi GTFS `frequencies.txt` / `trips.txt` service counts to normalize segment demand by scheduled bus frequency (passengers per scheduled trip).
  2. Add 1-transfer journey routing across shared interchange hubs.
  3. Incorporate live GTFS-RT vehicle position feeds where fleet GPS is available.
