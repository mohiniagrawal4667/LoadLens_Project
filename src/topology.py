"""Route topology reconstruction from ticket OD pairs (when GTFS is absent).

When official GTFS files are supplied, LoadLens uses ``trips.txt`` and
``stop_times.txt`` as the authoritative stop sequence (see :mod:`src.gtfs`).
When GTFS is unavailable, this module recovers a cautious partial-to-linear
ordering from observed ``start -> end`` ticket pairs while explicitly detecting:

  - **Disconnected components**: minor isolated islands are never merged into
    the main chain; if no single dominant connected component exists, the
    route topology is marked uncertain.
  - **Cycles & circular routes**: strongly connected components and removed
    cycle weight are measured. Known/heavy circular routes (e.g. ring routes)
    cannot be safely linearized from OD tickets without GTFS and are marked
    ``uncertain_circular`` so intermediate segment movement is not invented.
  - **Ordering ambiguity**: uses a chain-preserving, longest-path topological
    order instead of hub-volume interleaving, and flags graphs whose
    consecutive pairs lack DAG reachability.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

import networkx as nx
import pandas as pd

from .data_loader import CACHE_DIR, TRIP_GRAPH_PARQUET

TOPOLOGY_META_JSON = CACHE_DIR / "topology_meta.json"


# ---------------------------------------------------------------------------
# Graph building
# ---------------------------------------------------------------------------

def _build_graphs(tickets: pd.DataFrame) -> Dict[Tuple[str, str], nx.DiGraph]:
    """Return ``{(route, direction): weighted DiGraph}``."""
    out: Dict[Tuple[str, str], nx.DiGraph] = {}
    if tickets is None or len(tickets) == 0:
        return out
    counts = tickets.groupby(["route", "direction", "start_norm", "end_norm"], sort=False).size()
    for (route, direction, a, b), w in counts.items():
        if not a or not b or a == b:
            continue
        key = (str(route), str(direction))
        g = out.get(key)
        if g is None:
            g = nx.DiGraph()
            out[key] = g
        if g.has_edge(a, b):
            g[a][b]["weight"] += int(w)
        else:
            g.add_edge(a, b, weight=int(w))
    return out


# ---------------------------------------------------------------------------
# Cycle removal + chain-preserving topological ordering
# ---------------------------------------------------------------------------

def _acyclicise(g: nx.DiGraph) -> nx.DiGraph:
    """Return a copy of *g* with the smallest-weight cycle edges removed."""
    h = g.copy()
    while True:
        try:
            cycle = nx.find_cycle(h, orientation="original")
        except nx.NetworkXNoCycle:
            return h
        weakest = min(
            cycle,
            key=lambda e: (h[e[0]][e[1]]["weight"], str(e[0]), str(e[1])),
        )
        h.remove_edge(weakest[0], weakest[1])


def _hubs(g: nx.DiGraph) -> Dict[str, float]:
    """Incident ticket weight per stop (secondary deterministic tie-breaker)."""
    score: Dict[str, float] = {}
    for n in g.nodes:
        w_out = sum(d["weight"] for _, _, d in g.out_edges(n, data=True))
        w_in = sum(d["weight"] for _, _, d in g.in_edges(n, data=True))
        score[n] = float(w_out + w_in)
    return score


def _topo_chain_aware(g: nx.DiGraph, hub_score: Dict[str, float]) -> List[str]:
    """Longest-path & successor-preserving topological sort on a connected DAG.

    Prefers direct successors of the previously placed stop (preserving linear
    corridor chains) and nodes with the longest remaining directed path to a
    sink, preventing local low-volume stops from being pushed past unrelated
    downstream hubs.
    """
    if g.number_of_nodes() == 0:
        return []
    rev_topo = list(reversed(list(nx.topological_sort(g))))
    height: Dict[str, int] = {n: 0 for n in g.nodes}
    for u in rev_topo:
        best_h = 0
        for v in g.successors(u):
            cand = height[v] + 1
            if cand > best_h:
                best_h = cand
        height[u] = best_h

    indeg = dict(g.in_degree())
    ready = [n for n, d in indeg.items() if d == 0]
    order: List[str] = []
    last: str | None = None
    while ready:
        ready.sort(
            key=lambda n: (
                0 if (last is not None and g.has_edge(last, n)) else 1,
                -height[n],
                -hub_score.get(n, 0.0),
                str(n),
            )
        )
        n = ready.pop(0)
        order.append(n)
        last = n
        for m in g.successors(n):
            indeg[m] -= 1
            if indeg[m] == 0:
                ready.append(m)
    return order


def _topo_with_ties(g: nx.DiGraph, hub_score: Dict[str, float]) -> List[str]:
    """Backward-compatible alias calling the chain-aware topological sorter."""
    return _topo_chain_aware(g, hub_score)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def _is_circular_name(route: str) -> bool:
    u = str(route).upper()
    return ("OMS" in u) or ("MUDRIKA" in u) or ("RING" in u)


def build_route_topology_with_meta(
    tickets: pd.DataFrame,
) -> Tuple[Dict[Tuple[str, str], Dict[str, int]], Dict[Tuple[str, str], Dict[str, Any]]]:
    """Reconstruct reliable linear topologies + per-route structural diagnostics.

    Routes whose ticket OD graph is circular, severely disconnected, or
    order-ambiguous are omitted from the reliable ``ordering`` map and flagged
    in ``meta`` so downstream segment aggregation never invents intermediate
    passenger movement across unrelated stops.
    """
    if tickets is None or len(tickets) == 0:
        return {}, {}

    graphs = _build_graphs(tickets)
    ordering: Dict[Tuple[str, str], Dict[str, int]] = {}
    meta: Dict[Tuple[str, str], Dict[str, Any]] = {}

    for key, g in graphs.items():
        if g.number_of_edges() == 0:
            continue
        route, direction = key
        total_weight = sum(d["weight"] for _, _, d in g.edges(data=True))

        # 1. Weakly connected components (never merge disconnected components)
        wccs = list(nx.weakly_connected_components(g))
        wcc_stats = []
        for comp in wccs:
            sub = g.subgraph(comp)
            cw = sum(d["weight"] for _, _, d in sub.edges(data=True))
            wcc_stats.append((cw, len(comp), sorted(comp)[0], comp))
        wcc_stats.sort(key=lambda x: (-x[0], -x[1], x[2]))

        primary_w, _, _, primary_nodes = wcc_stats[0]
        primary_weight_pct = (primary_w / max(total_weight, 1)) * 100.0
        excluded_stops = sorted(n for _, _, _, comp in wcc_stats[1:] for n in comp)

        g_main = g.subgraph(primary_nodes).copy()
        sccs = [c for c in nx.strongly_connected_components(g_main) if len(c) > 1]
        max_scc_size = max((len(c) for c in sccs), default=1)

        ga = _acyclicise(g_main)
        kept_w = sum(d["weight"] for _, _, d in ga.edges(data=True))
        rem_w = primary_w - kept_w
        cycle_edges_removed = g_main.number_of_edges() - ga.number_of_edges()
        cycle_weight_pct = (rem_w / max(primary_w, 1)) * 100.0

        topo = _topo_chain_aware(ga, _hubs(ga))
        n_pairs = max(len(topo) - 1, 1)
        adj_edge_cnt = sum(1 for a, b in zip(topo[:-1], topo[1:]) if ga.has_edge(a, b))
        adj_reach_cnt = sum(1 for a, b in zip(topo[:-1], topo[1:]) if nx.has_path(ga, a, b))
        adj_edge_pct = (adj_edge_cnt / n_pairs) * 100.0 if len(topo) > 1 else 100.0
        adj_reach_pct = (adj_reach_cnt / n_pairs) * 100.0 if len(topo) > 1 else 100.0

        # 2. Classify topology reliability
        is_circ = (
            (_is_circular_name(route) and max_scc_size >= 5)
            or (max_scc_size >= 30 and cycle_edges_removed >= 3)
            or (len(g_main) >= 10 and cycle_weight_pct >= 15.0 and max_scc_size >= 6)
        )
        if is_circ:
            status = "uncertain_circular"
            reliable = False
            reason = (
                f"Circular/loop structure detected ({max_scc_size}-stop cycle core); "
                "cannot safely infer intermediate segment loads without GTFS."
            )
        elif len(wccs) > 1 and primary_weight_pct < 75.0:
            status = "uncertain_disconnected"
            reliable = False
            reason = (
                f"Disconnected ticket graph ({len(wccs)} components, primary={primary_weight_pct:.1f}% weight); "
                "linear stop sequence uncertain without GTFS."
            )
        elif len(topo) >= 10 and adj_reach_pct < 25.0:
            status = "uncertain_ambiguous"
            reliable = False
            reason = (
                f"Ambiguous stop ordering (only {adj_reach_pct:.1f}% consecutive DAG reachability); "
                "cannot safely expand intermediate segments without GTFS."
            )
        elif len(wccs) > 1:
            status = "partial_disconnected"
            reliable = True
            reason = (
                f"Primary connected chain ordered ({len(topo)} stops); "
                f"{len(excluded_stops)} isolated stop(s) excluded to prevent interleaving."
            )
        else:
            status = "confident"
            reliable = True
            reason = "Single connected DAG backbone."

        meta[key] = {
            "route": route,
            "direction": direction,
            "status": status,
            "reliable": reliable,
            "reason": reason,
            "total_stops": int(g.number_of_nodes()),
            "ordered_stops": int(len(topo)) if reliable else 0,
            "excluded_disconnected_stops": int(len(excluded_stops)),
            "n_wcc": int(len(wccs)),
            "primary_weight_pct": round(primary_weight_pct, 1),
            "max_scc_size": int(max_scc_size),
            "cycle_edges_removed": int(cycle_edges_removed),
            "cycle_weight_pct": round(cycle_weight_pct, 1),
            "adj_edge_pct": round(adj_edge_pct, 1),
            "adj_reach_pct": round(adj_reach_pct, 1),
            "ticket_count": int(total_weight),
        }

        if reliable and len(topo) >= 2:
            ordering[key] = {stop: i for i, stop in enumerate(topo)}

    return ordering, meta


def build_route_topology(tickets: pd.DataFrame) -> Dict[Tuple[str, str], Dict[str, int]]:
    """Return ``{(route, direction): {stop_norm: rank}}`` for reliable chains."""
    ordering, _ = build_route_topology_with_meta(tickets)
    return ordering


# Cached artefact helpers ---------------------------------------------------

def save_topology(tickets: pd.DataFrame) -> Dict[Tuple[str, str], Dict[str, int]]:
    """Compute topology + diagnostics, and persist both to cache."""
    ordering, meta = build_route_topology_with_meta(tickets)
    rows = []
    for key, ranks in ordering.items():
        route, direction = key
        for stop, rank in ranks.items():
            rows.append({
                "route": route,
                "direction": direction,
                "stop_norm": stop,
                "rank": int(rank),
            })
    df = pd.DataFrame(rows, columns=["route", "direction", "stop_norm", "rank"])
    df.to_parquet(TRIP_GRAPH_PARQUET, index=False)

    serializable_meta = {f"{r}||{d}": v for (r, d), v in meta.items()}
    TOPOLOGY_META_JSON.write_text(json.dumps(serializable_meta, indent=2), encoding="utf-8")
    return ordering


def load_topology() -> Dict[Tuple[str, str], Dict[str, int]]:
    """Re-hydrate topology ordering from the parquet cache."""
    if not TRIP_GRAPH_PARQUET.exists():
        raise FileNotFoundError(
            "Trip-graph cache missing — run scripts/build_processed.py first."
        )
    df = pd.read_parquet(TRIP_GRAPH_PARQUET)
    if len(df) == 0:
        return {}
    out: Dict[Tuple[str, str], Dict[str, int]] = {}
    for (route, direction), sub in df.groupby(["route", "direction"], sort=False):
        out[(route, direction)] = dict(zip(sub["stop_norm"], sub["rank"].astype(int)))
    return out


def load_topology_meta() -> Dict[Tuple[str, str], Dict[str, Any]]:
    """Load persisted topology diagnostics if present."""
    if not TOPOLOGY_META_JSON.exists():
        return {}
    raw = json.loads(TOPOLOGY_META_JSON.read_text(encoding="utf-8"))
    out: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for k, v in raw.items():
        if "||" in k:
            r, d = k.split("||", 1)
            out[(r, d)] = v
    return out
