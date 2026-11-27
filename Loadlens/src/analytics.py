"""Aggregate analytics — route rankings, time patterns, heat-maps."""
from __future__ import annotations

from typing import Dict, List, Tuple

import numpy as np
import pandas as pd


# ---- Route-level ranking --------------------------------------------------

def route_demand_ranking(tickets: pd.DataFrame) -> pd.DataFrame:
    """Rank every route by aggregate passenger demand and volume."""
    if tickets is None or len(tickets) == 0:
        return pd.DataFrame(columns=[
            "route", "direction", "passenger_volume", "ticket_count",
            "avg_passenger_count", "vehicle_coverage", "unique_stops", "demand_rank",
        ])
    g = tickets.groupby(["route", "direction"], as_index=False).agg(
        passenger_volume=("passenger_count", "sum"),
        ticket_count=("passenger_count", "count"),
        avg_passenger_count=("passenger_count", "mean"),
        vehicle_coverage=("has_vehicle", "mean"),
        unique_stops=("start_norm", "nunique"),
    )
    g = g.sort_values("passenger_volume", ascending=False).reset_index(drop=True)
    g["demand_rank"] = g["passenger_volume"].rank(method="dense", ascending=False).astype(int)
    return g


# ---- Time patterns --------------------------------------------------------

def hour_of_day_demand(tickets: pd.DataFrame) -> pd.DataFrame:
    if tickets is None or len(tickets) == 0:
        return pd.DataFrame(columns=["ticket_hour", "passenger_volume", "ticket_count"])
    return (tickets.groupby(["ticket_hour"], as_index=False)
            .agg(passenger_volume=("passenger_count", "sum"),
                 ticket_count=("passenger_count", "count"))
            .sort_values("ticket_hour"))


def weekday_weekend_hourly(tickets: pd.DataFrame) -> pd.DataFrame:
    if tickets is None or len(tickets) == 0:
        return pd.DataFrame(columns=["ticket_is_weekend", "ticket_hour", "passenger_volume", "ticket_count"])
    return (tickets.groupby(["ticket_is_weekend", "ticket_hour"], as_index=False)
            .agg(passenger_volume=("passenger_count", "sum"),
                 ticket_count=("passenger_count", "count")))


def weekday_daily_volume(tickets: pd.DataFrame) -> pd.DataFrame:
    if tickets is None or len(tickets) == 0:
        return pd.DataFrame(columns=["ticket_date", "passenger_volume", "ticket_count", "dow", "is_weekend"])
    daily = (tickets.groupby(["ticket_date"], as_index=False)
             .agg(passenger_volume=("passenger_count", "sum"),
                  ticket_count=("passenger_count", "count")))
    daily["dow"] = pd.to_datetime(daily["ticket_date"]).dt.dayofweek
    daily["is_weekend"] = daily["dow"].isin([5, 6])
    return daily


def peak_vs_offpeak(tickets: pd.DataFrame) -> Dict:
    """Compare peak windows (08-11, 17-21) with off-peak hours."""
    if tickets is None or len(tickets) == 0:
        return {
            "peak_passenger_volume": 0,
            "offpeak_passenger_volume": 0,
            "peak_share_pct": 0.0,
            "peak_window_label": "08:00–11:00 and 17:00–21:00 IST",
        }
    h = tickets["ticket_hour"]
    peak_mask = ((h >= 8) & (h <= 11)) | ((h >= 17) & (h <= 21))
    peak = int(tickets.loc[peak_mask, "passenger_count"].sum())
    off = int(tickets.loc[~peak_mask, "passenger_count"].sum())
    pct_peak = peak / max(peak + off, 1) * 100
    return {
        "peak_passenger_volume": peak,
        "offpeak_passenger_volume": off,
        "peak_share_pct": round(pct_peak, 1),
        "peak_window_label": "08:00–11:00 and 17:00–21:00 IST",
    }


# ---- Segment-level --------------------------------------------------------

def route_segments(segments: pd.DataFrame, route: str, direction: str = "") -> pd.DataFrame:
    """Return segments for a route (and optionally a direction)."""
    if segments is None or len(segments) == 0:
        return pd.DataFrame(columns=[
            "route", "direction", "rank_a", "rank_b", "from_norm", "to_norm",
            "segment_load", "ticket_count", "relative_load_index",
        ])
    sel = segments[segments["route"] == route]
    if direction:
        sel = sel[sel["direction"] == direction]
    return sel.sort_values("rank_a").reset_index(drop=True)


def top_segments(segments: pd.DataFrame, n: int = 20) -> pd.DataFrame:
    if segments is None or len(segments) == 0:
        return pd.DataFrame(columns=[
            "route", "direction", "segment_label",
            "segment_load", "ticket_count", "relative_load_index", "network_load_percentile",
        ])
    s = segments.copy()
    s["segment_label"] = s["from_norm"].astype(str).str.title() + " → " + s["to_norm"].astype(str).str.title()
    if "network_load_percentile" not in s.columns:
        cnt = len(s)
        if cnt > 1 and s["segment_load"].nunique() > 1:
            s["network_load_percentile"] = (s["segment_load"].rank(method="min") - 1.0) / (cnt - 1.0)
        else:
            s["network_load_percentile"] = 0.0
    cols = [
        "route", "direction", "segment_label",
        "segment_load", "ticket_count", "relative_load_index", "network_load_percentile",
    ]
    if "avg_daily_load" in s.columns:
        cols.append("avg_daily_load")
    return (s.nlargest(n, "segment_load")
            .loc[:, cols]
            .reset_index(drop=True))


def route_hour_heatmap(tickets: pd.DataFrame, route: str) -> pd.DataFrame:
    sub = tickets[tickets["route"] == route]
    return (sub.groupby([sub["ticket_date"].astype(str), "ticket_hour"], as_index=False)
            ["passenger_count"].sum()
            .pivot_table(index="ticket_date", columns="ticket_hour", values="passenger_count", fill_value=0))


def route_peak_compare(tickets: pd.DataFrame, routes: List[str]) -> pd.DataFrame:
    rows = []
    for r in routes:
        sub = tickets[tickets["route"] == r]
        h = sub["ticket_hour"]
        peak_mask = ((h >= 8) & (h <= 11)) | ((h >= 17) & (h <= 21))
        rows.append({
            "route": r,
            "peak": int(sub.loc[peak_mask, "passenger_count"].sum()),
            "offpeak": int(sub.loc[~peak_mask, "passenger_count"].sum()),
        })
    return pd.DataFrame(rows)


# ---- Coverage / quality ----------------------------------------------------

def coverage_summary(tickets: pd.DataFrame, segments: pd.DataFrame, topology: Dict) -> Dict:
    n_ticket = len(tickets)
    n_with_vehicle = int(tickets["has_vehicle"].sum())
    distinct_vehicles = int(tickets.loc[tickets["has_vehicle"], "vehicle_number"].nunique())
    n_routes_topology = len(topology)
    n_segment_rows = len(segments)
    seg_load_max = float(segments["segment_load"].max()) if len(segments) else 0.0
    return {
        "n_tickets": int(n_ticket),
        "tickets_with_vehicle_pct": round(n_with_vehicle / max(n_ticket, 1) * 100, 2),
        "distinct_vehicles": distinct_vehicles,
        "n_route_directions_in_topology": n_routes_topology,
        "n_segments_aggregated": n_segment_rows,
        "max_segment_load": seg_load_max,
    }


def city_network_graph_data(
    tickets: pd.DataFrame,
    segments: pd.DataFrame,
    *,
    max_nodes: int = 45,
    max_edges: int = 110,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Build a schematic node-link network from real segment relationships.

    Never fabricates geographic coordinates; layout positions come strictly
    from deterministic graph topology spring coordinates weighted by observed
    segment demand.
    """
    import networkx as nx

    if segments is None or len(segments) == 0:
        return pd.DataFrame(), pd.DataFrame()

    # Aggregate undirected corridor edges across routes to reveal interchange hubs
    s = segments.copy()
    if "network_load_percentile" not in s.columns:
        cnt = len(s)
        s["network_load_percentile"] = (
            (s["segment_load"].rank(method="min") - 1.0) / max(cnt - 1.0, 1.0)
            if cnt > 1 else 0.0
        )

    s["u"] = np.minimum(s["from_norm"].astype(str), s["to_norm"].astype(str))
    s["v"] = np.maximum(s["from_norm"].astype(str), s["to_norm"].astype(str))
    s = s[s["u"] != s["v"]]
    if len(s) == 0:
        return pd.DataFrame(), pd.DataFrame()

    edges_agg = (
        s.groupby(["u", "v"], as_index=False)
        .agg(
            segment_load=("segment_load", "sum"),
            peak_route_load=("segment_load", "max"),
            network_load_percentile=("network_load_percentile", "max"),
            n_routes=("route", "nunique"),
            routes=("route", lambda rs: ", ".join(sorted(set(rs))[:4])),
        )
        .sort_values("segment_load", ascending=False)
        .head(max_edges)
    )

    # Compute node throughput from tickets
    stop_vol: Dict[str, float] = {}
    stop_routes: Dict[str, int] = {}
    if tickets is not None and len(tickets) > 0:
        sv1 = tickets.groupby("start_norm")["passenger_count"].sum()
        sv2 = tickets.groupby("end_norm")["passenger_count"].sum()
        for k, val in sv1.add(sv2, fill_value=0).items():
            stop_vol[str(k)] = float(val)
        r1 = tickets.groupby("start_norm")["route"].nunique()
        r2 = tickets.groupby("end_norm")["route"].nunique()
        for k, val in r1.combine(r2, max, fill_value=0).items():
            stop_routes[str(k)] = int(val)

    g = nx.Graph()
    for row in edges_agg.itertuples(index=False):
        g.add_edge(row.u, row.v, weight=max(float(row.segment_load), 1.0))

    # Keep top nodes if graph exceeds max_nodes
    if g.number_of_nodes() > max_nodes:
        ranked_nodes = sorted(
            g.nodes,
            key=lambda n: (
                sum(d["weight"] for _, _, d in g.edges(n, data=True)),
                stop_vol.get(n, 0.0),
            ),
            reverse=True,
        )[:max_nodes]
        g = g.subgraph(ranked_nodes).copy()

    if g.number_of_nodes() == 0:
        return pd.DataFrame(), pd.DataFrame()

    # Keep largest connected component for cohesive city web + place any small components neatly
    pos = nx.spring_layout(g, seed=42, weight="weight", k=1.45 / np.sqrt(max(g.number_of_nodes(), 2)), iterations=60)

    node_rows = []
    for n in g.nodes:
        x, y = pos[n]
        deg = g.degree(n)
        inc_load = sum(d["weight"] for _, _, d in g.edges(n, data=True))
        node_rows.append({
            "stop_norm": n,
            "display": str(n).title(),
            "x": float(x),
            "y": float(y),
            "volume": stop_vol.get(n, inc_load),
            "incident_load": float(inc_load),
            "routes_count": stop_routes.get(n, 1),
            "degree": int(deg),
        })
    nodes_df = pd.DataFrame(node_rows)

    valid_edges = edges_agg[edges_agg["u"].isin(g.nodes) & edges_agg["v"].isin(g.nodes)].copy()
    valid_edges["x0"] = valid_edges["u"].map(lambda n: float(pos[n][0]))
    valid_edges["y0"] = valid_edges["u"].map(lambda n: float(pos[n][1]))
    valid_edges["x1"] = valid_edges["v"].map(lambda n: float(pos[n][0]))
    valid_edges["y1"] = valid_edges["v"].map(lambda n: float(pos[n][1]))
    valid_edges["from_disp"] = valid_edges["u"].astype(str).str.title()
    valid_edges["to_disp"] = valid_edges["v"].astype(str).str.title()
    return nodes_df, valid_edges.reset_index(drop=True)
