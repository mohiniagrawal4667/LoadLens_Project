"""Journey planning built on top of GTFS or reconstructed route topology.

These functions produce *historical ticket-derived* demand estimates across
every consecutive segment a candidate direct trip traverses. They never invent
capacity thresholds, live physical occupancy numbers, or fabricated heuristic
durations.

When official GTFS files (``stops.txt``, ``routes.txt``, ``trips.txt``,
``stop_times.txt``) are supplied, :func:`search_options_with_gtfs` uses GTFS as
the authoritative stop sequence and matches tickets directly onto GTFS
segments. Otherwise, :func:`search_options_topology` uses reliable
ticket-derived stop chains, preserves every intermediate stop across filtered
time windows, and warns transparently when circular/ambiguous routes are
excluded.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from .data_loader import normalize_stop
from .gtfs import gtfs_status, search_gtfs_direct_options
from .load_engine import count_active_days, route_vehicle_reliability_stats
from .topology import load_topology


def _reset_cache() -> None:
    """No-op kept for backward compatibility with callers/tests."""
    return None


def stop_index(tickets: pd.DataFrame) -> pd.DataFrame:
    """Build a ranked list of unique stops for UI autocomplete."""
    if tickets is None or len(tickets) == 0:
        return pd.DataFrame(columns=["stop_norm", "as_start", "as_end", "volume", "display"])
    s = tickets["start_norm"].value_counts().rename_axis("stop_norm").reset_index(name="as_start")
    e = tickets["end_norm"].value_counts().rename_axis("stop_norm").reset_index(name="as_end")
    df = s.merge(e, on="stop_norm", how="outer").fillna(0)
    df["volume"] = df["as_start"] + df["as_end"]
    df["display"] = df["stop_norm"].astype(str).str.title()
    return df.sort_values("volume", ascending=False).reset_index(drop=True)


def suggest_stop(query: str, stops: pd.DataFrame, k: int = 8) -> pd.DataFrame:
    """Return up to *k* stop suggestions matching *query*."""
    if stops is None or len(stops) == 0:
        return pd.DataFrame(columns=["stop_norm", "as_start", "as_end", "volume", "display"])
    if not query or not isinstance(query, str) or not query.strip():
        return stops.head(k)
    q = normalize_stop(query)
    if not q:
        return stops.iloc[0:0]

    def _score(s: str) -> int:
        if not isinstance(s, str) or not s:
            return 0
        if s == q:
            return 100
        if s.startswith(q):
            return 80
        if q in s or s in q:
            return 60
        qs = set(q.split())
        ss = set(s.split())
        overlap = len(qs & ss)
        return 20 * overlap if overlap > 0 else 0

    s = stops.copy()
    s["score"] = s["stop_norm"].map(_score)
    s = s[s["score"] > 0]
    if len(s) == 0:
        return s.drop(columns=["score"])
    sort_cols = ["score", "volume"] if "volume" in s.columns else ["score"]
    return s.sort_values(sort_cols, ascending=False).head(k).reset_index(drop=True)


def _ensure_network_percentile(segments: pd.DataFrame) -> pd.DataFrame:
    if segments is None or len(segments) == 0:
        return segments
    if "network_load_percentile" in segments.columns:
        return segments
    out = segments.copy()
    n = len(out)
    if n > 1 and out["segment_load"].nunique() > 1:
        out["network_load_percentile"] = (
            (out["segment_load"].rank(method="min") - 1.0) / (n - 1.0)
        ).astype(float)
    else:
        out["network_load_percentile"] = 0.0
    return out


def search_options_topology(
    tickets: pd.DataFrame,
    segments: pd.DataFrame,
    origin_norm: str,
    dest_norm: str,
    *,
    topology: Optional[Dict] = None,
    topology_meta: Optional[Dict] = None,
    max_options: int = 5,
) -> Dict[str, Any]:
    """Find candidate direct trips using reliable ticket-derived topologies."""
    orig = normalize_stop(origin_norm) if isinstance(origin_norm, str) else ""
    dest = normalize_stop(dest_norm) if isinstance(dest_norm, str) else ""

    if not orig or not dest:
        return {
            "options": [],
            "mode": "topology",
            "uncertain_routes": [],
            "message": "Select both a valid origin stop and destination stop.",
        }
    if orig == dest:
        return {
            "options": [],
            "mode": "topology",
            "uncertain_routes": [],
            "message": "Origin and destination resolve to the same stop; no trip needed.",
        }

    topo = topology if topology is not None else load_topology()
    if not topo and not topology_meta:
        return {
            "options": [],
            "mode": "topology",
            "uncertain_routes": [],
            "message": "No route topology is available for the current dataset.",
        }

    # Check whether any excluded uncertain (e.g., circular) routes serve both stops
    uncertain_hits: List[Dict[str, Any]] = []
    if topology_meta and tickets is not None and len(tickets) > 0:
        uncertain_keys = {k for k, m in topology_meta.items() if not m.get("reliable", True)}
        if uncertain_keys:
            u_route_names = {r for r, _ in uncertain_keys}
            sub_u = tickets[
                tickets["route"].isin(u_route_names)
                & (tickets["start_norm"].isin([orig, dest]) | tickets["end_norm"].isin([orig, dest]))
            ]
            for (r, d), grp in sub_u.groupby(["route", "direction"], sort=False):
                if (str(r), str(d)) not in uncertain_keys:
                    continue
                stops_seen = set(grp["start_norm"]).union(set(grp["end_norm"]))
                if orig in stops_seen and dest in stops_seen:
                    m = topology_meta[(str(r), str(d))]
                    direct_od = grp[(grp["start_norm"] == orig) & (grp["end_norm"] == dest)]
                    uncertain_hits.append({
                        "route": str(r),
                        "direction": str(d),
                        "status": m.get("status", "uncertain"),
                        "reason": m.get("reason", "Uncertain topology"),
                        "direct_od_tickets": int(len(direct_od)),
                        "direct_od_pax": float(direct_od["passenger_count"].sum()) if len(direct_od) else 0.0,
                    })

    known_stops = {stop for ranks in topo.values() for stop in ranks}
    if orig not in known_stops or dest not in known_stops:
        missing = []
        if orig not in known_stops:
            missing.append(f"origin '{orig}'")
        if dest not in known_stops:
            missing.append(f"destination '{dest}'")
        msg = (
            f"Stop not found in reliable route topology ({', '.join(missing)}). "
            "No direct options can be computed."
        )
        if uncertain_hits:
            u_names = ", ".join(f"{h['route']} ({h['direction']})" for h in uncertain_hits)
            msg += (
                f" Note: stops appear on circular/uncertain route(s) [{u_names}], "
                "whose intermediate segment order cannot be verified without GTFS."
            )
        return {
            "options": [],
            "mode": "topology",
            "uncertain_routes": uncertain_hits,
            "message": msg,
        }

    # Identify candidate routes matching origin -> destination in topology first
    candidates = []
    for (route, direction), ranks in topo.items():
        if orig not in ranks or dest not in ranks:
            continue
        a = int(ranks[orig])
        b = int(ranks[dest])
        if a >= b:
            continue
        rank_to_stop = {int(rk): stp for stp, rk in ranks.items()}
        if not all(r in rank_to_stop for r in range(a, b + 1)):
            continue
        candidates.append((str(route), str(direction), a, b, rank_to_stop))

    if not candidates:
        msg = (
            "No direct option found between the selected stops in this direction "
            "(or no observed tickets in the selected time window). "
            "LoadLens currently evaluates direct, 0-transfer bus routes only."
        )
        if uncertain_hits:
            u_names = ", ".join(f"{h['route']} ({h['direction']})" for h in uncertain_hits)
            msg += (
                f" Excluded circular/uncertain route(s): {u_names} "
                "(supply GTFS to enable schedule-accurate segment loads on circular routes)."
            )
        return {
            "options": [],
            "mode": "topology",
            "uncertain_routes": uncertain_hits,
            "message": msg,
        }

    segs_all = _ensure_network_percentile(segments)
    cand_routes = {r for r, _, _, _, _ in candidates}
    segs_by_rd: Dict[tuple[str, str], Dict[tuple[int, int], Dict[str, Any]]] = {}
    if segs_all is not None and len(segs_all) > 0:
        segs_cand = segs_all[segs_all["route"].isin(cand_routes)]
        has_veh_col = "veh_segment_load" in segs_cand.columns
        for (r, d), grp in segs_cand.groupby(["route", "direction"], sort=False):
            seg_map: Dict[tuple[int, int], Dict[str, Any]] = {}
            for row in grp.itertuples(index=False):
                seg_map[(int(row.rank_a), int(row.rank_b))] = {
                    "segment_load": float(row.segment_load),
                    "ticket_count": int(row.ticket_count),
                    "veh_segment_load": float(row.veh_segment_load) if has_veh_col else 0.0,
                    "relative_load_index": float(row.relative_load_index),
                    "network_load_percentile": float(row.network_load_percentile),
                }
            segs_by_rd[(str(r), str(d))] = seg_map

    active_days = count_active_days(tickets)
    sub_t = tickets[tickets["route"].isin(cand_routes)] if (tickets is not None and len(tickets) > 0) else tickets
    veh_stats = route_vehicle_reliability_stats(sub_t)

    options: List[Dict[str, Any]] = []
    for route, direction, a, b, rank_to_stop in candidates:
        rd_segs = segs_by_rd.get((route, direction), {})
        vs = veh_stats.get((route, direction))
        has_tickets_in_slice = (
            (vs is not None and vs["route_tickets"] > 0)
            if (tickets is not None)
            else bool(rd_segs)
        )

        # Build EVERY consecutive segment from a to b (never omit zero-load intermediate stops!)
        seg_rows = []
        for r_idx in range(a, b):
            from_s = rank_to_stop[r_idx]
            to_s = rank_to_stop[r_idx + 1]
            hit = rd_segs.get((r_idx, r_idx + 1))
            if not has_tickets_in_slice:
                seg_rows.append({
                    "from_norm": from_s,
                    "to_norm": to_s,
                    "segment_load": np.nan,
                    "ticket_count": 0,
                    "veh_segment_load": np.nan,
                    "relative_load_index": np.nan,
                    "network_load_percentile": np.nan,
                    "obs_status": "no_tickets_in_window",
                })
            elif hit is not None:
                seg_rows.append({
                    "from_norm": from_s,
                    "to_norm": to_s,
                    "segment_load": hit["segment_load"],
                    "ticket_count": hit["ticket_count"],
                    "veh_segment_load": hit["veh_segment_load"],
                    "relative_load_index": hit["relative_load_index"],
                    "network_load_percentile": hit["network_load_percentile"],
                    "obs_status": "observed",
                })
            else:
                seg_rows.append({
                    "from_norm": from_s,
                    "to_norm": to_s,
                    "segment_load": 0.0,
                    "ticket_count": 0,
                    "veh_segment_load": 0.0,
                    "relative_load_index": 0.0,
                    "network_load_percentile": 0.0,
                    "obs_status": "zero_observed_in_window",
                })

        seg_df = pd.DataFrame(seg_rows)
        seg_count = int(b - a)

        if has_tickets_in_slice and len(rd_segs) > 0:
            seg_load = float(seg_df["segment_load"].sum())
            mean_load = round(seg_load / max(seg_count, 1), 1)
            max_load = float(seg_df["segment_load"].max())
            rel = round(float(seg_df["relative_load_index"].mean()), 3)
            net_pct = round(float(seg_df["network_load_percentile"].mean()), 3)
            avg_daily = round(mean_load / active_days, 2) if active_days >= 1 else None
            pax_per_veh = None
            if vs and vs["vehicle_metric_reliable"]:
                mean_veh_load = float(seg_df["veh_segment_load"].mean())
                pax_per_veh = round(mean_veh_load / float(vs["distinct_vehicles"]), 2)
            has_matched = True
            zero_seg_cnt = int((seg_df["obs_status"] == "zero_observed_in_window").sum())
            t_meta = topology_meta.get((route, direction), {}) if topology_meta else {}
            topo_status = t_meta.get("status", "confident")
            match_status = f"Full {seg_count}-segment span evaluated"
            if zero_seg_cnt > 0:
                match_status += f" ({zero_seg_cnt} zero-ticket segment(s) in selected window included in denominator)"
            if topo_status == "partial_disconnected":
                match_status += f" · {t_meta.get('excluded_disconnected_stops', 0)} isolated stop(s) excluded"
        else:
            seg_load = None
            mean_load = None
            max_load = None
            rel = None
            net_pct = None
            avg_daily = None
            pax_per_veh = None
            has_matched = False
            match_status = "No observed tickets on this route in the selected time window (insufficient data)"

        r_tickets = vs["route_tickets"] if vs else 0
        r_veh_pct = vs["vehicle_coverage_pct"] if vs else None
        distinct_veh = vs["distinct_vehicles"] if vs else 0

        options.append({
            "route": route,
            "direction": direction,
            "origin": orig,
            "destination": dest,
            "segment_count": seg_count,
            "has_matched_load": has_matched,
            "incomplete_coverage": False,
            "load_match_status": match_status,
            "historical_segment_load": seg_load,
            "mean_segment_load": mean_load,
            "max_segment_load": max_load,
            "avg_daily_segment_load": avg_daily,
            "active_days": active_days,
            "pax_per_observed_vehicle": pax_per_veh,
            "pax_per_gtfs_trip": None,
            "gtfs_scheduled_trips": None,
            "relative_load_index": rel,
            "network_load_percentile": net_pct,
            "estimated_duration_min": None,
            "duration_delta_min": None,
            "duration_source": "Unavailable (GTFS stop_times.txt required)",
            "route_tickets": r_tickets,
            "route_vehicle_coverage_pct": r_veh_pct,
            "distinct_vehicles": distinct_veh,
            "stop_coords": None,
            "segments": seg_df,
        })

    # Rank active options first by comparable daily/mean segment demand (lowest first),
    # breaking ties by bottleneck peak segment load and fewest segments; inactive options last.
    options.sort(key=lambda o: (
        0 if o["has_matched_load"] else 1,
        o["avg_daily_segment_load"] if o["avg_daily_segment_load"] is not None else float("inf"),
        o["mean_segment_load"] if o["mean_segment_load"] is not None else float("inf"),
        o["max_segment_load"] if o["max_segment_load"] is not None else float("inf"),
        o["segment_count"],
    ))
    return {
        "options": options[:max_options],
        "mode": "topology",
        "uncertain_routes": uncertain_hits,
        "message": "",
    }


def search_options_with_gtfs(
    gtfs_dir: Path,
    segments: pd.DataFrame,
    origin_norm: str,
    dest_norm: str,
    *,
    max_options: int = 5,
    tickets: Optional[pd.DataFrame] = None,
    rank_mode: str = "demand",
) -> Dict[str, Any]:
    """Find candidate trips using official GTFS schedules + historical ticket demand."""
    orig = normalize_stop(origin_norm) if isinstance(origin_norm, str) else ""
    dest = normalize_stop(dest_norm) if isinstance(dest_norm, str) else ""
    if not orig or not dest:
        return {
            "options": [],
            "mode": "gtfs",
            "message": "Select both a valid origin stop and destination stop.",
        }
    if orig == dest:
        return {
            "options": [],
            "mode": "gtfs",
            "message": "Origin and destination resolve to the same stop; no trip needed.",
        }
    return search_gtfs_direct_options(
        gtfs_dir,
        segments,
        orig,
        dest,
        max_options=max_options,
        tickets=tickets,
        rank_mode=rank_mode,
    )


def gtfs_available(folder: Path) -> bool:
    return bool(gtfs_status(folder)["available"])
