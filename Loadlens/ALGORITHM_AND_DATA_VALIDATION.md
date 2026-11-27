# LoadLens — Algorithm and Data Validation Report

> **Validation Date:** 2026-11-27  
> **Modules Audited:** `src/data_loader.py`, `src/topology.py`, `src/load_engine.py`, `src/gtfs.py`, `src/journey_planner.py`, `src/analytics.py`

---

## 1. Mathematical Model & Proof of Segment Load Calculation

### Formal Definition
For each ordered `(route, direction)` chain with stop positions $0, 1, \dots, M-1$, consecutive directed segments are indexed by $s \in \{0, \dots, M-2\}$ connecting stop $s$ (`rank_a = s`) to stop $s + 1$ (`rank_b = s + 1`).

For every cleaned ticket $t$ on `(route, direction)` with boarding rank $b_t$ and destination rank $e_t$ where $b_t < e_t$:

$$L_s = \sum_{\substack{t \text{ on } (r,d) \\ b_t \le s < e_t}} \text{passenger\_count}_t$$

### Implementation Verification (`src/load_engine.py:129-189`)
1. `valid_mask = both_known & (sub["start_rank"] < sub["end_rank"])` enforces $b_t < e_t$.
2. OD pre-aggregation collapses identical `(route, direction, start_rank, end_rank)` pairs by summing `passenger_count`, ticket counts (`tkt_one`), `veh_pax`, and `veh_tkt`. Because segment membership $[b_t, e_t)$ depends solely on `(start_rank, end_rank)`, summation over grouped OD pairs is algebraically identical to summing per ticket.
3. NumPy expansion sets `seg_count = end_r - start_r`, `local_idx = 0 .. seg_count - 1`, `rank_a = start_r + local_idx`, and `rank_b = rank_a + 1`, covering exactly $s \in \{b_t, b_t + 1, \dots, e_t - 1\}$, i.e. $b_t \le s < e_t$.
4. **Independent Brute-Force Cross-Check:** Verified in this session against an explicit Python row-by-row reference loop (`for s in range(b, e): ref[...] += passenger_count`) across all `25,000` sample rows — **all `2,793` segments matched bit-for-bit** (`MATH_PROOF_EXACT`).

### Derived Indicators & Equations
* **Layer A (Cumulative & Mean Span Load):**
  $$\bar{L}_{\text{span}} = \frac{1}{e - b} \sum_{s=b}^{e-1} L_s$$
  Crucially, zero-ticket intermediate segments on an active route in a filtered time window remain in the $e - b$ denominator (`obs_status = "zero_observed_in_window"`), preventing missing segments from inflating/deflating averages.
* **Layer B (Daily Segment Intensity):**
  $$L_{\text{daily}} = \frac{\bar{L}_{\text{span}}}{\text{active\_days}}$$
  where `active_days` is the observed count of distinct `ticket_date` values in the active slice (`0` → `None`).
* **Layer C (Vehicle-Tagged Demand per Observed Vehicle):**
  Computed **strictly** on rows with `has_vehicle == True` (`veh_segment_load`) and guarded by `vehicle_coverage_pct >= 25.0`, `distinct_vehicles >= 2`, and `vehicle_tickets >= 5` (otherwise `None` / `N/A`). Never assumes 1 vehicle ID equals 1 physical trip.
* **Layer D (GTFS Trip-Normalized Daily Demand):**
  $$L_{\text{trip}} = \frac{L_{\text{daily}}}{\text{gtfs\_scheduled\_trips}}$$
  Computed only when GTFS is active and `has_matched_load == True`.
* **Within-Route Relative Load Index (RLI) vs. Network Load Percentile:**
  $$\text{RLI}_s = \frac{L_s - L_{\min}^{(r,d)}}{\max(L_{\max}^{(r,d)} - L_{\min}^{(r,d)}, 1)}, \qquad \text{NetPct}_s = \frac{\text{rank}_{\min}(L_s) - 1}{\max(N - 1, 1)}$$

---

## 2. Explicit Data Integrity & Honesty Audit

| Potential Pitfall | How LoadLens Handles It | Verified? |
|---|---|---|
| Missing `vehicle_number` (~44.7% in sample) | Never imputed; flagged via `has_vehicle`, excluded from Layer C numerator, and gated behind coverage thresholds. | **Yes** (`audit.py` Test 2, `test_regression.py` Case 6) |
| Ticket `created_at` vs. boarding time | Normalized to naive `Asia/Kolkata` (IST) and explicitly labelled "ticket creation time" in UI & docs. | **Yes** (`audit.py` Test 1, `app_pages.py`) |
| Historical demand vs. live occupancy | Never labels segments "overcrowded" or claims seat counts; uses percentile demand tiers (`Low < 40th`, `Moderate 40–75th`, `High >= 75th`). | **Yes** (code audit) |
| Circular / disconnected routes without GTFS | Flagged (`uncertain_circular`, `uncertain_disconnected`, `uncertain_ambiguous`) and excluded from linear segment expansion; minor islands isolated (`partial_disconnected`). | **Yes** (`test_regression.py` Cases 2–4) |
| Inactive routes in filtered windows | Marked `has_matched_load = False` (`N/A` / insufficient data) rather than `"0 pax · Low demand"`. | **Yes** (`test_regression.py` Case 5) |
| Unmatched or partial GTFS routes | Unmatched routes carry `NaN`/`N/A`; `< 50%` stop match flagged `incomplete_coverage = True` and ranked behind full matches. | **Yes** (`test_regression.py` Case 8) |

---

## 3. Pipeline Verification & Edge-Case Matrix (All 15 Required Checks)

| # | Pipeline / Edge Case | Expected Behavior | Observed Result |
|---|---|---|---|
| 1 | Ticket ingestion (CSV & Parquet + chunked CSV) | Required columns validated; missing optional cols degrade gracefully; chunked CSV matches single-shot counts. | **PASS** (`audit.py` Test 1, `test_regression.py` Case 14) |
| 2 | Date & time parsing (IST) | UTC `Z` / offset strings converted to naive IST; unparseable dates counted in `dropped_missing_core`. | **PASS** (`audit.py` Test 1) |
| 3 | Passenger count handling | `<= 0` or `NaN` dropped and counted; positive counts summed without extrapolation. | **PASS** (`audit.py` Test 1, `validate.py`) |
| 4 | Route & stop normalization | `717AUP` → `number=717, variant=A, direction=up`; punctuation-only stops dropped; abbreviations expanded. | **PASS** (`audit.py` Test 3 & 6) |
| 5 | Same origin and destination | Dropped in `clean_with_report` (`dropped_same_origin_and_destination`); rejected in `search_options_*`. | **PASS** (`audit.py` Test 1 & 8) |
| 6 | Reversed / back-tracked destination | `start_rank > end_rank` excluded from segment loads (`24` rows in sample) and counted in `skipped_backward_journeys`. | **PASS** (`audit.py` Test 5) |
| 7 | Missing / unmatched stops | `suggest_stop` returns empty; planner returns explicit message without silent fallback. | **PASS** (`audit.py` Test 3) |
| 8 | Repeated stops (GTFS) | Shortest valid span per trip used for schedule duration; ambiguous multi-pair tickets (`len(valid_pairs) > 1`) excluded from ticket matching (`ambiguous_stop_tickets`). | **PASS** (`test_regression.py` Case 8) |
| 9 | Circular routes (`OMS`, ring cores) | Detected as `uncertain_circular`; omitted from linear topology; surfaced in `uncertain_routes` notice. | **PASS** (`test_regression.py` Case 3) |
| 10 | Disconnected route topology | Minor islands excluded (`partial_disconnected`); fragmented graphs flagged `uncertain_disconnected`. | **PASS** (`test_regression.py` Case 2) |
| 11 | Ambiguous route ordering | Sparse `< 25%` consecutive DAG reachability flagged `uncertain_ambiguous`. | **PASS** (`test_regression.py` Case 4) |
| 12 | Zero observed demand in window | Active-route zero-ticket segments stay in denominator; zero-ticket routes show `N/A`. | **PASS** (`test_regression.py` Case 5) |
| 13 | Duplicate ticket records | Summed cleanly per `(route, direction, start_norm, end_norm)` across `4,446` OD groups in sample. | **PASS** (`audit.py` Test 7) |
| 14 | Missing / partial / invalid GTFS ZIP | Missing GTFS disables duration & maps; bad/empty/path-traversal ZIPs rejected cleanly without crash. | **PASS** (`audit.py` Test 9, `test_regression.py` Cases 7, 9, 13) |
| 15 | Hand-calculated $A \to B \to C \to D$ fixture | Tickets `A->D(2), A->B(3), B->C(5), C->D(1), B->D(4)` → `A->B=5`, `B->C=11`, `C->D=7`. | **PASS** (`audit.py` Test 10, `test_regression.py` Case 1) |

---

## 4. Documented Edge-Case Caveat

* **Mixed timezone strings inside a single column:** In `src/data_loader.py:_parse_timestamps_ist`, if a single CSV mixes timezone-aware timestamps (`+05:30` or `Z`) and naive local timestamps in the same column, `utc=True` interprets the naive rows as UTC before shifting to IST. Standard ONDC exports use consistent ISO-8601 formatting, so this does not affect homogeneous streams, but mixed-offset inputs should be normalized upstream.
