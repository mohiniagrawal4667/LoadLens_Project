"""Passenger segment-load calculation (fully vectorised, layered demand model).

For every valid ticket journey the engine adds ``passenger_count`` to every
consecutive route segment between its boarding stop and intended destination
along the selected direction.

A ticket is *valid* if and only if the boarding stop precedes the destination
in the topology of the route in the selected direction. Opposite-direction
journeys are rejected (counted separately) and we never invent segment
counts for backtracked or uncertain-topology trips.

Layered demand tracking:
  - Layer A: Raw historical ticketed passenger-segment totals.
  - Layer B: Average daily passenger-segment demand across observed active dates.
  - Layer C: Vehicle-tagged demand per distinct observed vehicle ID (computed
    strictly from tickets with valid ``vehicle_number`` when coverage is reliable;
    never mixes missing-vehicle rows into the numerator or fabricates trips).
"""
from __future__ import annotations

import json
from typing import Any, Dict, Optional, Tuple

import numpy as np
import pandas as pd

from .data_loader import CACHE_DIR, SEGMENTS_PARQUET

# Reliability thresholds for Layer C (observed-vehicle demand normalization)
MIN_VEHICLE_COVERAGE_PCT = 25.0
MIN_DISTINCT_VEHICLES = 2
MIN_VEHICLE_TICKETS = 5


# ---------------------------------------------------------------------------
# Time-window & day-type filters (for crowdedness-aware journey planning)
# ---------------------------------------------------------------------------

TIME_WINDOWS: Dict[str, Optional[Tuple[int, ...]]] = {
    "All hours (24h)": None,
    "All Peak (08–11 & 17–21 IST)": (8, 9, 10, 11, 17, 18, 19, 20, 21),
    "Morning Peak (08–11 IST)": (8, 9, 10, 11),
    "Midday (12–16 IST)": (12, 13, 14, 15, 16),
    "Evening Peak (17–21 IST)": (17, 18, 19, 20, 21),
    "Off-Peak / Night (22–07 IST)": (22, 23, 0, 1, 2, 3, 4, 5, 6, 7),
}

DAY_TYPES: Tuple[str, ...] = (
    "All days",
    "Weekdays (Mon–Fri)",
    "Weekends (Sat–Sun)",
)


def filter_tickets_by_window(
    tickets: pd.DataFrame,
    time_window: str = "All hours (24h)",
    day_type: str = "All days",
) -> pd.DataFrame:
    """Slice *tickets* by IST hour window and weekday/weekend day type."""
    if tickets is None or len(tickets) == 0:
        return tickets
    if time_window == "All hours (24h)" and day_type == "All days":
        return tickets
    mask = pd.Series(True, index=tickets.index)
    hours = TIME_WINDOWS.get(time_window)
    if hours is not None and "ticket_hour" in tickets.columns:
        mask &= tickets["ticket_hour"].isin(hours)
    if day_type == "Weekdays (Mon–Fri)" and "ticket_is_weekend" in tickets.columns:
        mask &= ~tickets["ticket_is_weekend"].astype(bool)
    elif day_type == "Weekends (Sat–Sun)" and "ticket_is_weekend" in tickets.columns:
        mask &= tickets["ticket_is_weekend"].astype(bool)
    return tickets.loc[mask]


def count_active_days(tickets: pd.DataFrame) -> int:
    """Return actual number of distinct observed service dates in *tickets*."""
    if tickets is None or len(tickets) == 0 or "ticket_date" not in tickets.columns:
        return 0
    return int(tickets["ticket_date"].nunique())


# ---------------------------------------------------------------------------
# Core segment-load aggregator
# ---------------------------------------------------------------------------

def compute_segment_loads(
    tickets: pd.DataFrame,
    topology: Dict[Tuple[str, str], Dict[str, int]],
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """Aggregate per-segment passenger demand + vehicle-tagged subset totals."""
    active_days = count_active_days(tickets)
    if not topology or tickets is None or len(tickets) == 0:
        n_in = len(tickets) if tickets is not None else 0
        return _empty_segments(), {
            "used_ticket_rows": 0,
            "skipped_backward_journeys": 0,
            "skipped_same_stop": 0,
            "skipped_unknown_stops": int(n_in),
            "segments_aggregated": 0,
            "input_rows": int(n_in),
            "active_days": active_days,
        }

    # ---- 1. Vectorised lookup of start/end ranks ----------------------------
    rk = pd.DataFrame(
        [
            (route, dire, stop, int(rank))
            for (route, dire), ranks in topology.items()
            for stop, rank in ranks.items()
        ],
        columns=["route", "direction", "stop_norm", "rank"],
    )

    sub = tickets[[
        "route", "direction", "start_norm", "end_norm", "passenger_count", "has_vehicle"
    ]].merge(
        rk.rename(columns={"stop_norm": "start_norm", "rank": "start_rank"}),
        on=["route", "direction", "start_norm"],
        how="left",
    ).merge(
        rk.rename(columns={"stop_norm": "end_norm", "rank": "end_rank"}),
        on=["route", "direction", "end_norm"],
        how="left",
    )

    n_total = len(sub)
    both_known = sub["start_rank"].notna() & sub["end_rank"].notna()
    valid_mask = both_known & (sub["start_rank"] < sub["end_rank"])
    back_mask = both_known & (sub["start_rank"] > sub["end_rank"])
    same_mask = both_known & (sub["start_rank"] == sub["end_rank"])
    n_valid = int(valid_mask.sum())
    n_back = int(back_mask.sum())
    n_same = int(same_mask.sum())
    n_unknown = int(n_total - n_valid - n_back - n_same)

    sel = sub.loc[
        valid_mask,
        ["route", "direction", "start_rank", "end_rank", "passenger_count", "has_vehicle"],
    ].copy()

    if len(sel) == 0:
        return _empty_segments(), {
            "used_ticket_rows": n_valid,
            "skipped_backward_journeys": n_back,
            "skipped_same_stop": n_same,
            "skipped_unknown_stops": n_unknown,
            "segments_aggregated": 0,
            "input_rows": int(n_total),
            "active_days": active_days,
        }

    # ---- 2. Pre-aggregate identical (route, direction, start_rank, end_rank) OD pairs
    # Every ticket sharing the same OD rank pair traverses the exact same consecutive
    # segments [start_rank..end_rank), so collapsing OD groups first preserves exact
    # mathematical segment totals while cutting expansion memory by 5x-50x at scale.
    has_veh_col = sel["has_vehicle"].to_numpy(dtype=bool)
    pax_col = sel["passenger_count"].to_numpy(dtype=np.float64)
    sel["veh_pax"] = np.where(has_veh_col, pax_col, 0.0)
    sel["veh_tkt"] = has_veh_col.astype(np.int32)
    sel["tkt_one"] = np.ones(len(sel), dtype=np.int32)

    od_agg = sel.groupby(
        ["route", "direction", "start_rank", "end_rank"],
        as_index=False,
        sort=False,
    ).agg(
        passenger_count=("passenger_count", "sum"),
        ticket_count=("tkt_one", "sum"),
        veh_pax=("veh_pax", "sum"),
        veh_tkt=("veh_tkt", "sum"),
    )

    start_r = od_agg["start_rank"].to_numpy(dtype=np.int32)
    end_r = od_agg["end_rank"].to_numpy(dtype=np.int32)
    pax_vals = od_agg["passenger_count"].to_numpy(dtype=np.float64)
    tkt_vals = od_agg["ticket_count"].to_numpy(dtype=np.int32)
    veh_pax_vals = od_agg["veh_pax"].to_numpy(dtype=np.float64)
    veh_tkt_vals = od_agg["veh_tkt"].to_numpy(dtype=np.int32)

    # ---- 3. Expand each unique OD group into N consecutive segments ---------
    seg_count = (end_r - start_r).astype(np.int32)
    total = int(seg_count.sum())
    row_idx = np.repeat(np.arange(len(od_agg), dtype=np.int32), seg_count)
    offsets = np.concatenate(([0], np.cumsum(seg_count[:-1]))).astype(np.int32)
    local_idx = np.arange(total, dtype=np.int32) - np.repeat(offsets, seg_count)

    rank_a = start_r[row_idx] + local_idx
    rank_b = rank_a + 1

    segs = pd.DataFrame({
        "route": np.repeat(od_agg["route"].to_numpy(), seg_count),
        "direction": np.repeat(od_agg["direction"].to_numpy(), seg_count),
        "rank_a": rank_a,
        "rank_b": rank_b,
        "seg_passengers": pax_vals[row_idx],
        "seg_tickets": tkt_vals[row_idx],
        "veh_seg_passengers": veh_pax_vals[row_idx],
        "veh_seg_tickets": veh_tkt_vals[row_idx],
    })

    # ---- 4. Aggregate by (route, direction, rank pair) ----------------------
    agg = segs.groupby(["route", "direction", "rank_a", "rank_b"], as_index=False).agg(
        segment_load=("seg_passengers", "sum"),
        ticket_count=("seg_tickets", "sum"),
        veh_segment_load=("veh_seg_passengers", "sum"),
        veh_ticket_count=("veh_seg_tickets", "sum"),
    )

    # ---- 4. Map rank -> stop names ------------------------------------------
    name_map = rk.set_index(["route", "direction", "rank"])["stop_norm"]
    agg_index = list(zip(agg["route"], agg["direction"], agg["rank_a"]))
    agg["from_norm"] = [name_map.get(k, "") for k in agg_index]
    agg["to_norm"] = [
        name_map.get((r, d, rb), "")
        for r, d, rb in zip(agg["route"], agg["direction"], agg["rank_b"])
    ]

    # ---- 5. Layered indicators: daily rate, within-route RLI & network %ile -
    if active_days >= 1:
        agg["avg_daily_load"] = (agg["segment_load"] / float(active_days)).astype(float)
    else:
        agg["avg_daily_load"] = np.nan

    agg["relative_load_index"] = agg.groupby(["route", "direction"])["segment_load"].transform(
        lambda s: (s - s.min()) / max(s.max() - s.min(), 1.0)
    ).astype(float)

    n_segs = len(agg)
    if n_segs > 1 and agg["segment_load"].nunique() > 1:
        agg["network_load_percentile"] = (
            (agg["segment_load"].rank(method="min") - 1.0) / (n_segs - 1.0)
        ).astype(float)
    else:
        agg["network_load_percentile"] = 0.0

    agg = agg.sort_values(["route", "direction", "rank_a"]).reset_index(drop=True)

    meta: Dict[str, Any] = {
        "used_ticket_rows": int(n_valid),
        "skipped_backward_journeys": int(n_back),
        "skipped_same_stop": int(n_same),
        "skipped_unknown_stops": int(n_unknown),
        "segments_aggregated": int(len(agg)),
        "input_rows": int(n_total),
        "active_days": int(active_days),
    }
    return agg, meta


def route_vehicle_reliability_stats(tickets: pd.DataFrame) -> Dict[Tuple[str, str], Dict[str, Any]]:
    """Compute per-(route, direction) ticket & observed-vehicle coverage stats.

    Used for Layer C demand-per-observed-vehicle normalization without mixing
    missing-vehicle tickets into the observed-vehicle numerator.
    """
    if tickets is None or len(tickets) == 0:
        return {}
    out: Dict[Tuple[str, str], Dict[str, Any]] = {}
    base = tickets.groupby(["route", "direction"], sort=False).agg(
        n_tickets=("passenger_count", "count"),
        veh_tickets=("has_vehicle", "sum"),
        active_days=("ticket_date", "nunique"),
    )
    veh_sub = tickets[tickets["has_vehicle"]]
    if len(veh_sub) > 0:
        dv = veh_sub.groupby(["route", "direction"], sort=False)["vehicle_number"].nunique()
    else:
        dv = pd.Series(dtype=int)

    for (r, d), row in base.iterrows():
        n_t = int(row["n_tickets"])
        v_t = int(row["veh_tickets"])
        cov_pct = round((v_t / max(n_t, 1)) * 100.0, 1)
        n_dv = int(dv.get((r, d), 0))
        reliable = (
            cov_pct >= MIN_VEHICLE_COVERAGE_PCT
            and n_dv >= MIN_DISTINCT_VEHICLES
            and v_t >= MIN_VEHICLE_TICKETS
        )
        out[(str(r), str(d))] = {
            "route_tickets": n_t,
            "vehicle_tickets": v_t,
            "vehicle_coverage_pct": cov_pct,
            "distinct_vehicles": n_dv,
            "route_active_days": int(row["active_days"]),
            "vehicle_metric_reliable": bool(reliable),
        }
    return out


def _empty_segments() -> pd.DataFrame:
    return pd.DataFrame(columns=[
        "route", "direction", "rank_a", "rank_b", "from_norm", "to_norm",
        "segment_load", "ticket_count", "veh_segment_load", "veh_ticket_count",
        "avg_daily_load", "relative_load_index", "network_load_percentile",
    ])


def save_segments(tickets: pd.DataFrame, topology) -> Dict[str, Any]:
    segs, meta = compute_segment_loads(tickets, topology)
    segs.to_parquet(SEGMENTS_PARQUET, index=False)
    (CACHE_DIR / "segment_meta.json").write_text(json.dumps(meta, indent=2))
    return meta


def load_segments() -> pd.DataFrame:
    return pd.read_parquet(SEGMENTS_PARQUET)
