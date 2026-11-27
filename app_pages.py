"""LOADLENS — Premium renderers for all five investigation modules.

Every existing calculation channel is preserved verbatim: only the chrome,
layout, narrative ordering, and bespoke HTML components were redesigned for
the premium dark urban-intelligence aesthetic.
"""
from __future__ import annotations

import html as _html
import json
from pathlib import Path
from typing import Dict, Optional

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src import analytics, ui_theme
from src.gtfs import gtfs_status, load_gtfs_feed
from src.journey_planner import (
    search_options_topology,
    search_options_with_gtfs,
    stop_index,
    suggest_stop,
)
from src.load_engine import (
    DAY_TYPES,
    TIME_WINDOWS,
    compute_segment_loads,
    filter_tickets_by_window,
)
from src.ui_theme import (
    AMBER_SIGNAL,
    BG_ELEVATED,
    BG_PANEL,
    BG_VOID,
    BORDER_SUBTLE,
    CORAL_ALERT,
    CYAN_ELECTRIC,
    LOAD_SCALE,
    MAGENTA_NEON,
    ROUTES_SCALE,
    TEXT_MUTED,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    VIOLET_NEON,
)

GTFS_DIR = Path(__file__).resolve().parent / "data" / "gtfs"
_GRID_COLOR = "rgba(66, 232, 224, 0.08)"


# ============================================================================
# Shared Plotly dark theme
# ============================================================================
def _plotly_defaults():
    return dict(
        paper_bgcolor="rgba(11, 16, 27, 0.72)",
        plot_bgcolor="rgba(7, 9, 16, 0.78)",
        font=dict(color=TEXT_PRIMARY, family="Inter, -apple-system, sans-serif", size=12),
        title_font=dict(color=TEXT_PRIMARY, family="Space Grotesk, Inter, sans-serif", size=15),
        margin=dict(l=14, r=14, t=42, b=14),
        colorway=ROUTES_SCALE,
        hoverlabel=dict(
            bgcolor="#0B1220",
            font_color=CYAN_ELECTRIC,
            bordercolor=CYAN_ELECTRIC,
            font_family="JetBrains Mono, monospace",
        ),
    )


def _grid(fig: go.Figure) -> go.Figure:
    fig.update_xaxes(
        gridcolor=_GRID_COLOR,
        linecolor="rgba(145, 160, 181, 0.22)",
        zerolinecolor=_GRID_COLOR,
        tickfont=dict(color=TEXT_SECONDARY),
        title_font=dict(color=TEXT_SECONDARY),
    )
    fig.update_yaxes(
        gridcolor=_GRID_COLOR,
        linecolor="rgba(145, 160, 181, 0.22)",
        zerolinecolor=_GRID_COLOR,
        tickfont=dict(color=TEXT_SECONDARY),
        title_font=dict(color=TEXT_SECONDARY),
    )
    return fig


def _hour_chart(tickets: pd.DataFrame, title: str, highlight_peak: bool = False) -> go.Figure:
    if tickets is None or len(tickets) == 0:
        counts = pd.Series(0, index=range(24))
    else:
        h = tickets["ticket_hour"].astype(int)
        counts = tickets.groupby(h)["passenger_count"].sum().reindex(range(24), fill_value=0)

    if highlight_peak:
        colors = [
            AMBER_SIGNAL if (8 <= hr <= 11 or 17 <= hr <= 21) else CYAN_ELECTRIC
            for hr in counts.index
        ]
    else:
        colors = CYAN_ELECTRIC

    fig = go.Figure(
        go.Bar(
            x=list(counts.index),
            y=list(counts.values),
            marker_color=colors,
            marker_line=dict(color=BG_VOID, width=0.8),
            hovertemplate="Hour %{x:02d}:00 IST<br>Passengers: %{y:,}<extra></extra>",
        )
    )
    fig.update_layout(
        **_plotly_defaults(),
        title=title,
        xaxis_title="Hour of day (IST)",
        yaxis_title="Passenger volume",
    )
    return fig


def _date_range_label(tickets: pd.DataFrame, dq: Optional[Dict] = None) -> str:
    """Derive a human-readable date range from the active dataset."""
    dmin = dq.get("date_min") if dq else None
    dmax = dq.get("date_max") if dq else None
    if (not dmin or dmin == "—") and tickets is not None and len(tickets) > 0 and "ticket_date" in tickets.columns:
        dmin = str(tickets["ticket_date"].min())
        dmax = str(tickets["ticket_date"].max())
    if dmin and dmin != "—":
        return dmin if dmin == dmax else f"{dmin} → {dmax}"
    return "Active Dataset"


def _esc(value) -> str:
    return _html.escape(str(value))


def _ordinal(n: int) -> str:
    if 11 <= (n % 100) <= 13:
        return f"{n}th"
    return f"{n}{ {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th') }"


# ============================================================================
# Cache helpers
# ============================================================================
@st.cache_data(show_spinner=False)
def _cached_stop_index(dataset_sig: str, _tickets: pd.DataFrame) -> pd.DataFrame:
    return stop_index(_tickets)


@st.cache_data(show_spinner=False)
def _cached_window_slice(
    dataset_sig: str, time_window: str, day_type: str,
    _tickets: pd.DataFrame, _topology: Dict,
):
    filtered = filter_tickets_by_window(_tickets, time_window=time_window, day_type=day_type)
    segs, meta = compute_segment_loads(filtered, _topology)
    return filtered, segs, meta


@st.cache_data(show_spinner=False)
def _cached_city_network(dataset_sig: str, _tickets: pd.DataFrame, _segments: pd.DataFrame):
    return analytics.city_network_graph_data(_tickets, _segments)


# ============================================================================
# Overview network figure (data-driven schematic, no synthetic GPS)
# ============================================================================
def _overview_network_figure(
    tickets: pd.DataFrame, segments: pd.DataFrame, dataset_sig: str,
    gtfs_dir: Path, gtfs_available: bool,
) -> tuple[go.Figure, str]:
    if gtfs_available:
        try:
            feed = load_gtfs_feed(gtfs_dir)
            stops = feed["stops"]
            if {"stop_lat", "stop_lon"}.issubset(stops.columns):
                stops_geo = stops.copy()
                stops_geo["stop_lat"] = pd.to_numeric(stops_geo["stop_lat"], errors="coerce")
                stops_geo["stop_lon"] = pd.to_numeric(stops_geo["stop_lon"], errors="coerce")
                stops_geo = stops_geo.dropna(subset=["stop_lat", "stop_lon"]).drop_duplicates(subset=["stop_norm"])
                coord_lookup = {
                    r.stop_norm: (float(r.stop_lat), float(r.stop_lon))
                    for r in stops_geo.itertuples(index=False)
                }
                matched_segs = (
                    segments[
                        segments["from_norm"].isin(coord_lookup)
                        & segments["to_norm"].isin(coord_lookup)
                    ].nlargest(160, "segment_load") if len(segments) > 0 else pd.DataFrame()
                )
                if len(coord_lookup) > 0:
                    fig = go.Figure()
                    if len(matched_segs) > 0:
                        for row in matched_segs.itertuples(index=False):
                            lat0, lon0 = coord_lookup[row.from_norm]
                            lat1, lon1 = coord_lookup[row.to_norm]
                            pct = float(getattr(row, "network_load_percentile", 0.3))
                            _, col, _ = ui_theme.demand_tier(pct)
                            fig.add_trace(
                                go.Scattermap(
                                    lat=[lat0, lat1], lon=[lon0, lon1],
                                    mode="lines",
                                    line=dict(width=2.5, color=col),
                                    hoverinfo="text",
                                    text=f"{row.route}: {str(row.from_norm).title()} → {str(row.to_norm).title()} ({int(row.segment_load):,} pax)",
                                    showlegend=False,
                                )
                            )
                    fig.add_trace(
                        go.Scattermap(
                            lat=stops_geo["stop_lat"], lon=stops_geo["stop_lon"],
                            mode="markers",
                            marker=dict(size=6, color=CYAN_ELECTRIC, opacity=0.8),
                            text=stops_geo["stop_norm"].astype(str).str.title(),
                            hoverinfo="text", showlegend=False,
                        )
                    )
                    fig.update_layout(
                        map=dict(
                            style="carto-darkmatter",
                            center=dict(lat=float(stops_geo["stop_lat"].mean()), lon=float(stops_geo["stop_lon"].mean())),
                            zoom=10.5,
                        ),
                        paper_bgcolor="rgba(11, 16, 27, 0.72)",
                        margin=dict(l=0, r=0, t=0, b=0),
                        height=540,
                    )
                    return fig, "GTFS Geographic Network (carto-darkmatter · matched stop coordinates)"
        except Exception:
            pass

    nodes_df, edges_df = _cached_city_network(dataset_sig, tickets, segments)
    fig = go.Figure()
    if len(nodes_df) == 0 or len(edges_df) == 0:
        fig.update_layout(**_plotly_defaults(), height=540, title="Network schematic unavailable (no segments)")
        return fig, "No segment topology available"

    tier_bins = [
        ("Low demand (<40th pct)", CYAN_ELECTRIC, "rgba(66, 232, 224, 0.16)", edges_df[edges_df["network_load_percentile"] < 0.40]),
        ("Moderate (40–75th pct)", AMBER_SIGNAL, "rgba(245, 184, 75, 0.20)", edges_df[(edges_df["network_load_percentile"] >= 0.40) & (edges_df["network_load_percentile"] < 0.75)]),
        ("High demand (≥75th pct)", CORAL_ALERT, "rgba(255, 107, 112, 0.24)", edges_df[edges_df["network_load_percentile"] >= 0.75]),
    ]
    for label, core_col, halo_col, sub_e in tier_bins:
        if len(sub_e) == 0:
            continue
        xs, ys = [], []
        for r in sub_e.itertuples(index=False):
            xs.extend([r.x0, r.x1, None])
            ys.extend([r.y0, r.y1, None])
        fig.add_trace(
            go.Scatter(x=xs, y=ys, mode="lines", line=dict(width=6.5, color=halo_col),
                       hoverinfo="skip", showlegend=False)
        )
        fig.add_trace(
            go.Scatter(x=xs, y=ys, mode="lines", line=dict(width=1.8, color=core_col),
                       name=label, hoverinfo="skip")
        )
    fig.add_trace(
        go.Scatter(
            x=(edges_df["x0"] + edges_df["x1"]) / 2.0,
            y=(edges_df["y0"] + edges_df["y1"]) / 2.0,
            mode="markers",
            marker=dict(size=8, color="rgba(0,0,0,0)"),
            customdata=np.stack([
                edges_df["from_disp"], edges_df["to_disp"],
                edges_df["segment_load"], edges_df["n_routes"], edges_df["routes"],
            ], axis=-1),
            hovertemplate=(
                "<b>%{customdata[0]} ↔ %{customdata[1]}</b><br>"
                "Combined seg volume: %{customdata[2]:,.0f} pax<br>"
                "Corridor routes (%{customdata[3]}): %{customdata[4]}<extra></extra>"
            ),
            showlegend=False,
        )
    )

    vols = nodes_df["volume"].to_numpy(dtype=float)
    sizes = 9 + 18 * ((vols - vols.min()) / max(vols.max() - vols.min(), 1.0))
    node_cols = [
        CORAL_ALERT if d >= 6 else (VIOLET_NEON if d >= 3 else CYAN_ELECTRIC)
        for d in nodes_df["degree"]
    ]
    top_hubs = set(nodes_df.nlargest(12, "volume")["stop_norm"])
    labels = [r.display if r.stop_norm in top_hubs else "" for r in nodes_df.itertuples(index=False)]

    fig.add_trace(
        go.Scatter(
            x=nodes_df["x"], y=nodes_df["y"],
            mode="markers+text", text=labels, textposition="top center",
            textfont=dict(size=10, color=TEXT_PRIMARY, family="Space Grotesk, sans-serif"),
            marker=dict(size=sizes, color=node_cols, line=dict(width=1.5, color=BG_VOID), opacity=0.94),
            customdata=np.stack([
                nodes_df["display"], nodes_df["volume"],
                nodes_df["routes_count"], nodes_df["degree"],
            ], axis=-1),
            hovertemplate=(
                "<b>%{customdata[0]}</b><br>"
                "Observed throughput: %{customdata[1]:,.0f} pax<br>"
                "Active routes: %{customdata[2]} · Corridor links: %{customdata[3]}<extra></extra>"
            ),
            name="Transit Hubs", showlegend=False,
        )
    )

    layout_cfg = _plotly_defaults()
    layout_cfg["margin"] = dict(l=8, r=8, t=12, b=8)
    fig.update_layout(
        **layout_cfg, title="", height=540,
        legend=dict(
            orientation="h", yanchor="bottom", y=0.01, xanchor="left", x=0.01,
            bgcolor="rgba(7, 9, 16, 0.72)", font=dict(size=10, color=TEXT_SECONDARY),
        ),
        xaxis=dict(showgrid=True, gridcolor="rgba(66, 232, 224, 0.05)", zeroline=False, showticklabels=False),
        yaxis=dict(showgrid=True, gridcolor="rgba(66, 232, 224, 0.05)", zeroline=False, showticklabels=False),
    )
    return fig, "Data-driven schematic topology from observed OD corridors (no synthetic GPS)"


# ============================================================================
# Navigation helpers
# ============================================================================
def _nav_to(page_name: str) -> None:
    st.session_state["nav_radio"] = page_name


def _quick_plan_callback() -> None:
    o_val = st.session_state.get("ov_from", "")
    d_val = st.session_state.get("ov_to", "")
    if o_val:
        st.session_state["jp_query_o"] = o_val
        st.session_state.pop("origin_choice", None)
    if d_val:
        st.session_state["jp_query_d"] = d_val
        st.session_state.pop("destination_choice", None)
    st.session_state["nav_radio"] = "Journey Planner"


def _swap_jp_queries() -> None:
    qo = st.session_state.get("jp_query_o", "")
    qd = st.session_state.get("jp_query_d", "")
    co = st.session_state.get("origin_choice")
    cd = st.session_state.get("destination_choice")
    new_o = qd if str(qd).strip() else (str(cd) if cd else "")
    new_d = qo if str(qo).strip() else (str(co) if co else "")
    st.session_state["jp_query_o"] = new_o
    st.session_state["jp_query_d"] = new_d
    st.session_state["_prev_jp_query_o"] = new_o
    st.session_state["_prev_jp_query_d"] = new_d
    if cd:
        st.session_state["origin_choice"] = str(cd)
    else:
        st.session_state.pop("origin_choice", None)
    if co:
        st.session_state["destination_choice"] = str(co)
    else:
        st.session_state.pop("destination_choice", None)


# ============================================================================
# 01 — OVERVIEW (City Intelligence Landing)
# ============================================================================
def render_overview(
    tickets, segments, topology, dq, ds_info=None, *,
    gtfs_dir: Path = GTFS_DIR, gtfs_info: Optional[Dict] = None,
):
    date_lbl = _date_range_label(tickets, dq)
    badge = ds_info["label"] if ds_info else date_lbl
    ds_sig = ds_info.get("sig", "default") if ds_info else "default"
    g_status = gtfs_info if gtfs_info is not None else gtfs_status(gtfs_dir)

    # Cinematic editorial hero
    ui_theme.editorial_hero(
        f"DELHI TRANSIT TELEMETRY // {date_lbl}",
        "THE CITY NEVER STOPS MOVING.",
        "Investigate passenger movement. Reveal high-demand corridors. Make smarter journey decisions using strictly observed ticket signals — never synthetic occupancy.",
        badge=f"ACTIVE STREAM · {badge.upper()}",
    )

    pq = analytics.peak_vs_offpeak(tickets)
    cov = analytics.coverage_summary(tickets, segments, topology)
    unique_routes = dq.get("unique_routes", int(tickets["route"].nunique()) if len(tickets) else 0)
    active_days = dq.get("active_days") or (int(tickets["ticket_date"].nunique()) if len(tickets) else 0)

    ui_theme.hud_metrics_strip([
        ("Cleaned Ticket Stream", f"{len(tickets):,}", f"of {dq.get('raw_rows', len(tickets)):,} raw · {active_days} active day(s)"),
        ("Active Routes",         f"{unique_routes:,}", f"{len(topology):,} reliable chains"),
        ("Mapped Segments",       f"{len(segments):,}", "consecutive stop links"),
        ("Vehicle ID Coverage",   f"{cov['tickets_with_vehicle_pct']:.1f}%", f"{cov['distinct_vehicles']:,} distinct IDs"),
        ("Peak Window Share",     f"{pq['peak_share_pct']:.1f}%", pq["peak_window_label"]),
    ])

    # Asymmetric: City Corridor Network (left, large) + Investigation Console (right)
    col_net, col_action = st.columns([7, 5])
    with col_net:
        st.markdown(
            '<div class="ll-panel-head">'
            '<div class="ll-panel-title">City Corridor Movement Matrix</div>'
            '<div class="ll-panel-meta">Observed OD topology · live interactions</div>'
            '</div>',
            unsafe_allow_html=True,
        )
        fig_net, net_caption = _overview_network_figure(
            tickets, segments, ds_sig, gtfs_dir, bool(g_status["available"])
        )
        st.plotly_chart(fig_net, width="stretch")
        st.caption(f"{net_caption}. Historical ticket-derived demand only — live buses & seat occupancy are never fabricated.")

    with col_action:
        idx = _cached_stop_index(ds_sig, tickets)
        st.markdown(
            '<div class="ll-card" style="border-left:3px solid #42E8E0;background:linear-gradient(180deg, rgba(17,24,39,0.85), rgba(11,16,27,0.96));">'
            '<div class="ll-mono-tag">02 · Launch Investigation</div>'
            '<div style="font-family:\'Space Grotesk\',sans-serif;font-size:1.18rem;font-weight:700;margin-top:0.30rem;letter-spacing:-0.020em;">Investigate a Direct Corridor</div>'
            '<div class="ll-muted" style="margin-top:0.30rem;">Select boarding and destination stops to trace historical crowding.</div>'
            '</div>',
            unsafe_allow_html=True,
        )
        stop_opts = idx["stop_norm"].tolist()[:150] if len(idx) else []
        def_o = stop_opts[0] if len(stop_opts) > 0 else ""
        st.selectbox(
            "Origin stop",
            options=stop_opts,
            index=0 if def_o else None,
            format_func=lambda s: s.title() if s else "",
            key="ov_from",
        )
        st.selectbox(
            "Destination stop",
            options=stop_opts,
            index=1 if len(stop_opts) > 1 else (0 if stop_opts else None),
            format_func=lambda s: s.title() if s else "",
            key="ov_to",
        )
        st.button(
            "LAUNCH JOURNEY INVESTIGATION →",
            type="primary",
            use_container_width=True,
            on_click=_quick_plan_callback,
            key="ov_go_jp",
        )

        st.markdown(
            '<div class="ll-panel-head" style="margin-top:1.30rem;">'
            '<div class="ll-panel-title">High-Demand Corridor Alerts</div>'
            '<div class="ll-panel-meta">Top 5 network segments</div>'
            '</div>',
            unsafe_allow_html=True,
        )
        top_seg = analytics.top_segments(segments, n=5)
        if len(top_seg) == 0:
            st.info("No segments aggregated yet.")
        else:
            cards_html = []
            for idx_i, row in enumerate(top_seg.itertuples(index=False), start=1):
                net_p = float(getattr(row, "network_load_percentile", row.relative_load_index))
                lbl, col, bg = ui_theme.demand_tier(net_p)
                cards_html.append(
                    f'<div class="ll-card" style="padding:0.70rem 0.95rem;margin-bottom:0.50rem;'
                    f'border-left:3px solid {col};background:linear-gradient(180deg, rgba(17,24,39,0.85), rgba(11,16,27,0.96));">'
                    f'<div style="display:flex;justify-content:space-between;align-items:center;gap:0.6rem;flex-wrap:wrap;">'
                    f'<div>'
                    f'<span style="font-family:\'JetBrains Mono\',monospace;color:{CYAN_ELECTRIC};font-size:0.66rem;letter-spacing:0.10em;">#{idx_i:02d}</span> '
                    f'<span class="ll-route-pill" style="font-size:0.74rem;padding:0.22rem 0.55rem;margin-left:0.35rem;">{_esc(row.route)}</span> '
                    f'<span style="font-weight:600;font-size:0.86rem;color:{TEXT_PRIMARY};margin-left:0.45rem;">{_esc(row.segment_label)}</span>'
                    f'</div>'
                    f'<div style="display:flex;align-items:center;gap:0.50rem;">'
                    f'<span style="font-family:\'JetBrains Mono\',monospace;font-weight:700;font-size:0.86rem;color:{TEXT_PRIMARY};">{int(row.segment_load):,} pax</span>'
                    f'<span class="ll-demand-pill" style="color:{col};background:{bg};padding:0.20rem 0.55rem;font-size:0.68rem;">'
                    f'<span class="ll-demand-dot" style="background:{col};"></span>{_esc(lbl)}</span>'
                    f'</div></div></div>'
                )
            st.markdown("".join(cards_html), unsafe_allow_html=True)

    # Lower analytics row — asymmetric split
    ui_theme.section_eyebrow("03", "Hourly pulse · Top routes")
    c_left, c_right = st.columns([7, 5])
    with c_left:
        fig = _grid(_hour_chart(tickets, "Hourly demand pulse · IST (amber = peak 08–11 & 17–21)", highlight_peak=True))
        fig.update_layout(height=380)
        st.plotly_chart(fig, width="stretch")

    with c_right:
        ranking = analytics.route_demand_ranking(tickets)
        if len(ranking) > 0:
            top8 = ranking.head(8).copy()
            top8["label"] = top8["route"] + " (" + top8["direction"] + ")"
            fig_r = px.bar(
                top8.sort_values("passenger_volume"),
                x="passenger_volume", y="label", orientation="h",
                color="direction",
                color_discrete_map={"up": CYAN_ELECTRIC, "down": VIOLET_NEON, "unknown": TEXT_MUTED},
                labels={"passenger_volume": "Passengers", "label": ""},
                title="Top 8 corridors by passenger volume",
            )
            fig_r.update_layout(**_plotly_defaults(), height=380, showlegend=True, legend_title_text="Dir")
            st.plotly_chart(_grid(fig_r), width="stretch")
        else:
            st.info("No route volume data available.")

    # Module jump strip — slim, editorial
    ui_theme.section_eyebrow("04", "Continue investigation")
    b1, b2, b3, b4 = st.columns(4)
    b1.button("→ Journey Investigation", use_container_width=True, on_click=_nav_to, args=("Journey Planner",), key="sc_jp")
    b2.button("→ Route Intelligence",   use_container_width=True, on_click=_nav_to, args=("Route Analytics",), key="sc_ra")
    b3.button("→ Segment Explorer",     use_container_width=True, on_click=_nav_to, args=("Segment Explorer",), key="sc_se")
    b4.button("→ Data Forensics",       use_container_width=True, on_click=_nav_to, args=("Data Quality",), key="sc_dq")


# ============================================================================
# 02 — JOURNEY PLANNER (Investigation hero)
# ============================================================================
def render_journey_planner(
    tickets, segments, topology, *,
    topology_meta: Optional[Dict] = None,
    dataset_sig: str = "default",
    gtfs_dir: Path = GTFS_DIR,
    gtfs_info: Optional[Dict] = None,
):
    status = gtfs_info if gtfs_info is not None else gtfs_status(gtfs_dir)
    use_gtfs = bool(status["available"])

    ui_theme.page_hero(
        "Journey Investigation",
        "Trace direct corridors. Compare layered historical demand intensity. Inspect stop-level bottlenecks.",
        "Passenger-demand signals from real records — every layer of evidence is labelled, never synthesised.",
        badge="GTFS AUTHORITATIVE MODE" if use_gtfs else "TICKET TOPOLOGY MODE",
    )

    if use_gtfs:
        st.success(
            f"Official GTFS feed active ({gtfs_dir.name}). Ordered stop sequences and scheduled durations come from "
            "`trips.txt` + `stop_times.txt`, matched directly to historical ticket OD records (0-transfer direct routes)."
        )
    else:
        missing_list = ", ".join(status.get("missing_files", []))
        detail = f"Missing {missing_list}" if missing_list else (status.get("error") or "No GTFS directory")
        ui_theme.limitation_banner(
            f"<strong>Telemetry &amp; schedule notice:</strong> GTFS files unavailable ({_html.escape(detail)}). "
            "Routes come from reliable ticket-derived stop chains ranked by <strong>daily demand intensity</strong>. "
            "Circular/ambiguous routes are flagged rather than linearized; scheduled durations &amp; GPS maps remain disabled."
        )

    idx = _cached_stop_index(dataset_sig, tickets)
    if len(idx) < 2:
        st.warning("At least two distinct stops in the dataset are required to investigate journeys.")
        return

    default_origin = idx["stop_norm"].iloc[0]
    dest_pool = idx[idx["stop_norm"] != default_origin]
    default_destination = dest_pool["stop_norm"].iloc[0]

    st.markdown(
        '<div class="ll-panel-head">'
        '<div class="ll-panel-title">Corridor Query Parameters</div>'
        '<div class="ll-panel-meta">Select origin · destination · time window</div>'
        '</div>',
        unsafe_allow_html=True,
    )

    c1, c_swap, c2, c3 = st.columns([5, 1, 5, 2])
    with c1:
        query_o = st.text_input("Origin stop search", value="", placeholder="e.g. Badarpur Border", key="jp_query_o")
        if st.session_state.get("_prev_jp_query_o") != query_o:
            st.session_state["_prev_jp_query_o"] = query_o
            st.session_state.pop("origin_choice", None)
        suggestions_o = suggest_stop(query_o, idx, k=8)
        if query_o.strip() and len(suggestions_o) == 0:
            st.warning(f"No stops matched origin query: '{query_o.strip()}'")
            choice_o = None
        else:
            opts_o = suggestions_o["stop_norm"].tolist()
            if st.session_state.get("origin_choice") not in opts_o:
                st.session_state.pop("origin_choice", None)
            default_idx_o = opts_o.index(default_origin) if (not query_o.strip() and default_origin in opts_o) else 0
            choice_o = st.selectbox(
                "Boarding stop", options=opts_o, index=default_idx_o,
                format_func=lambda n: n.title() if n else "", key="origin_choice",
            )

    with c_swap:
        st.markdown("<div style='height:1.75rem;'></div>", unsafe_allow_html=True)
        st.button("⇄", help="Swap origin and destination", on_click=_swap_jp_queries, use_container_width=True, key="jp_swap")

    with c2:
        query_d = st.text_input("Destination stop search", value="", placeholder="e.g. Kalkaji Mandir", key="jp_query_d")
        if st.session_state.get("_prev_jp_query_d") != query_d:
            st.session_state["_prev_jp_query_d"] = query_d
            st.session_state.pop("destination_choice", None)
        suggestions_d = suggest_stop(query_d, idx, k=8)
        if query_d.strip() and len(suggestions_d) == 0:
            st.warning(f"No stops matched destination query: '{query_d.strip()}'")
            choice_d = None
        else:
            opts_d = suggestions_d["stop_norm"].tolist()
            if choice_o and choice_o in opts_d and len(opts_d) > 1:
                opts_d = [s for s in opts_d if s != choice_o]
            if st.session_state.get("destination_choice") not in opts_d:
                st.session_state.pop("destination_choice", None)
            default_idx_d = (
                opts_d.index(default_destination)
                if (not query_d.strip() and default_destination in opts_d) else 0
            )
            choice_d = st.selectbox(
                "Destination stop", options=opts_d, index=default_idx_d,
                format_func=lambda n: n.title() if n else "", key="destination_choice",
            )

    with c3:
        max_opts = st.slider("Max options", 1, 10, 5)

    if use_gtfs:
        tw_col1, tw_col2, tw_col3 = st.columns([3, 2, 2])
    else:
        tw_col1, tw_col2 = st.columns([3, 2])
        tw_col3 = None

    with tw_col1:
        time_window = st.selectbox(
            "Travel time window (IST)", options=list(TIME_WINDOWS.keys()),
            index=0, key="jp_time_window",
            help="Filter historical demand to a specific time of day.",
        )
    with tw_col2:
        day_type = st.selectbox(
            "Day type", options=list(DAY_TYPES),
            index=0, key="jp_day_type",
            help="Compare weekday commuter demand vs weekend demand.",
        )

    rank_mode = "demand"
    if tw_col3 is not None:
        with tw_col3:
            rank_choice = st.selectbox(
                "Ranking priority",
                options=["Lowest Demand Intensity", "Balanced (Demand + Time)"],
                index=0, key="jp_rank_mode",
                help="Balance historical demand intensity against scheduled GTFS travel duration.",
            )
            rank_mode = "balanced" if rank_choice.startswith("Balanced") else "demand"

    if not choice_o or not choice_d:
        st.info("Select matching boarding and destination stops above to launch investigation.")
        return
    if choice_o == choice_d:
        st.warning("Origin and destination are the same stop. Choose two distinct stops.")
        return

    if time_window == "All hours (24h)" and day_type == "All days":
        active_tickets = tickets
        active_segments = segments
    else:
        active_tickets, active_segments, _ = _cached_window_slice(
            dataset_sig, time_window, day_type, tickets, topology
        )

    if use_gtfs:
        result = search_options_with_gtfs(
            gtfs_dir, active_segments, choice_o, choice_d,
            max_options=max_opts, tickets=active_tickets, rank_mode=rank_mode,
        )
    else:
        result = search_options_topology(
            active_tickets, active_segments, choice_o, choice_d,
            topology=topology, topology_meta=topology_meta, max_options=max_opts,
        )

    uncertain_routes = result.get("uncertain_routes") or []
    if uncertain_routes:
        names = ", ".join(f"{u['route']} ({u['direction']})" for u in uncertain_routes)
        st.info(
            f"Circular/uncertain route(s) also serve these stops ({names}), but intermediate segment "
            "loads are omitted without GTFS to avoid inventing cross-city passenger movement."
        )

    if not result["options"]:
        st.info(result["message"])
        return

    opts = result["options"]
    matched_opts = [o for o in opts if o.get("has_matched_load", True)]
    if matched_opts:
        best_daily_vals = [o["avg_daily_segment_load"] for o in matched_opts if o.get("avg_daily_segment_load") is not None]
        if best_daily_vals:
            best_dem_val = f"{min(best_daily_vals):,.1f} pax/day"
        else:
            best_mean = min(o["mean_segment_load"] for o in matched_opts if o.get("mean_segment_load") is not None)
            best_dem_val = f"{best_mean:,.1f} pax"
        first_net = matched_opts[0].get("network_load_percentile")
        best_tier = ui_theme.demand_tier(first_net)[0] if first_net is not None else "Matched demand"
    else:
        best_dem_val = "N/A"
        best_tier = "Insufficient ticket data"

    min_segs = min(o["segment_count"] for o in opts)
    dur_vals = [o["estimated_duration_min"] for o in opts if o.get("estimated_duration_min") is not None]
    dur_summary = f"{min(dur_vals):.1f} min" if dur_vals else "Requires GTFS"
    window_note = "all days & hours" if (time_window == "All hours (24h)" and day_type == "All days") else f"{time_window} · {day_type}"

    ui_theme.kpi_row([
        ("Direct Corridors",     str(len(opts)),              f"{choice_o.title()} → {choice_d.title()}"),
        ("Lowest Daily Intensity", best_dem_val,             f"{best_tier} ({window_note})"),
        ("Shortest Stop Span",   f"{min_segs}",               "segments traversed"),
        ("Travel Duration",      dur_summary,                 "GTFS stop_times.txt" if dur_vals else "Disabled without GTFS"),
    ])

    trace_labels = [
        f"#{i + 1} · {o['route']} ({o['direction'].upper()})"
        for i, o in enumerate(opts)
    ]
    sel_trace_lbl = st.radio(
        "Select route to animate trace",
        options=trace_labels, index=0, horizontal=True, key="jp_active_trace",
    )
    sel_trace_idx = trace_labels.index(sel_trace_lbl) if sel_trace_lbl in trace_labels else 0

    st.markdown(ui_theme.animated_route_tracer_html(opts[sel_trace_idx]), unsafe_allow_html=True)

    rank_heading = (
        "Ranked Direct Routes · Balanced Demand & Travel Time"
        if (use_gtfs and rank_mode == "balanced")
        else "Ranked Direct Routes · Comparable Historical Demand Intensity"
    )
    ui_theme.section_eyebrow("DOSSIER", rank_heading)
    for idx_, opt in enumerate(opts, start=1):
        _render_option_card(idx_, opt, is_selected=(idx_ - 1 == sel_trace_idx))


def _render_option_card(rank: int, opt: dict, *, is_selected: bool = False):
    has_load = opt.get("has_matched_load", True)
    incomplete_cov = bool(opt.get("incomplete_coverage", False))
    rel = opt.get("relative_load_index")
    net_pct = opt.get("network_load_percentile")

    if not has_load:
        tier_lbl, color, bg = ("No matched ticket data", TEXT_SECONDARY, "rgba(145, 160, 181, 0.14)")
    else:
        tier_lbl, color, bg = ui_theme.demand_tier(net_pct if net_pct is not None else rel)

    seg = opt["segments"]
    seg_cnt = int(opt["segment_count"])
    cum_load = opt.get("historical_segment_load")
    avg_seg_load = opt.get("mean_segment_load")
    avg_daily = opt.get("avg_daily_segment_load")
    pax_veh = opt.get("pax_per_observed_vehicle")
    pax_gtfs = opt.get("pax_per_gtfs_trip")
    gtfs_trips = opt.get("gtfs_scheduled_trips")
    dur = opt.get("estimated_duration_min")
    dur_delta = opt.get("duration_delta_min")

    if dur is not None:
        dur_str = f"{dur:.1f} min"
        if dur_delta is not None and dur_delta > 0.0:
            dur_str += f" (+{dur_delta:.1f}m)"
        elif dur_delta == 0.0:
            dur_str += " (fastest)"
    else:
        dur_str = "Unavailable"
    daily_str = f"{avg_daily:,.1f} pax/day" if avg_daily is not None else "N/A"
    veh_str = f"{pax_veh:,.2f} pax/veh" if pax_veh is not None else "N/A"
    if pax_gtfs is not None and gtfs_trips is not None:
        trip_str = f"{pax_gtfs:,.2f} / trip ({gtfs_trips} trips)"
    else:
        avg_str = f"{avg_seg_load:,.1f} pax" if avg_seg_load is not None else "N/A"
        trip_str = avg_str

    r_tickets = opt.get("route_tickets")
    r_veh_pct = opt.get("route_vehicle_coverage_pct")
    distinct_v = opt.get("distinct_vehicles")
    active_days = opt.get("active_days")
    match_status = opt.get("load_match_status")

    conf_parts = []
    if has_load and avg_seg_load is not None:
        pct_txt = f"network {_ordinal(int(round(net_pct * 100)))} pct" if net_pct is not None else "unranked pct"
        rli_txt = f"within-route RLI {rel:.2f}" if rel is not None else "RLI N/A"
        conf_parts.append(
            f"Layer A: {avg_seg_load:,.1f} pax/seg ({cum_load:,.0f} cumulative) across {seg_cnt} segment(s) "
            f"on {opt['route']} ({opt['direction']}); {pct_txt}, {rli_txt}"
        )
        if avg_daily is not None and active_days:
            conf_parts.append(f"Layer B: {avg_daily:,.1f} pax/seg/day over {active_days} observed date(s)")
        if pax_veh is not None and distinct_v:
            conf_parts.append(
                f"Layer C: {pax_veh:,.2f} pax/observed vehicle (vehicle-tagged subset across {distinct_v:,} distinct IDs; not trip count)"
            )
        elif r_veh_pct is not None:
            conf_parts.append(f"Layer C: N/A (vehicle ID coverage {r_veh_pct:.1f}% below reliability threshold)")
        if pax_gtfs is not None and gtfs_trips:
            conf_parts.append(f"Layer D: {pax_gtfs:,.2f} daily pax/GTFS trip ({gtfs_trips} scheduled trips)")
    else:
        conf_parts.append("Demand metrics marked N/A because no matching ticket records were observed for this route/window")
    if match_status: conf_parts.append(match_status)
    if r_tickets is not None and r_tickets > 0:
        conf_parts.append(f"{r_tickets:,} route ticket records in window")
    conf_text = "; ".join(conf_parts) + "."

    seg_unit = "segment" if seg_cnt == 1 else "segments"
    if not has_load:
        pill_label = "N/A · No ticket data"
    elif incomplete_cov:
        pill_label = f"Partial match ({opt.get('gtfs_stop_match_pct', 0):.0f}%) · {tier_lbl}"
    elif net_pct is not None:
        pill_label = f"{tier_lbl} · P{int(round(net_pct * 100))}"
    else:
        pill_label = tier_lbl

    fourth_label = "Daily / GTFS Trip" if (pax_gtfs is not None and gtfs_trips is not None) else "Total Avg / Seg"
    sel_cls = " selected" if is_selected else ""
    active_badge = (
        '<span class="ll-dir-pill" style="color:#42E8E0;border-color:rgba(66,232,224,0.45);background:rgba(66,232,224,0.12);">TRACING</span>'
        if is_selected else ""
    )

    st.markdown(
        f'<div class="ll-route-card{sel_cls}" style="border-left: 4px solid {color};">'
        f'<div class="ll-route-head">'
        f'<div class="ll-route-left">'
        f'<span class="ll-route-pill">#{rank} · {_esc(opt["route"])}</span>'
        f'<span class="ll-dir-pill">{_esc(opt["direction"])}</span>'
        f'{active_badge}'
        f'<div><div class="ll-route-od">{_esc(opt["origin"]).title()} → {_esc(opt["destination"]).title()}</div></div>'
        f'</div>'
        f'<div style="text-align:right;">'
        f'<span class="ll-demand-pill" style="color:{color};background:{bg};">'
        f'<span class="ll-demand-dot" style="background:{color};"></span>{_esc(pill_label)}</span>'
        f'</div>'
        f'</div>'
        f'<div class="ll-route-metrics">'
        f'<div><div class="ll-rm-label">Duration · Span</div><div class="ll-rm-val">{_esc(dur_str)} · {seg_cnt} {seg_unit}</div></div>'
        f'<div><div class="ll-rm-label">Daily Seg Intensity</div><div class="ll-rm-val">{_esc(daily_str)}</div></div>'
        f'<div><div class="ll-rm-label">Per Obs. Vehicle</div><div class="ll-rm-val">{_esc(veh_str)}</div></div>'
        f'<div><div class="ll-rm-label">{fourth_label}</div><div class="ll-rm-val">{_esc(trip_str)}</div></div>'
        f'</div>'
        f'<div style="margin-top:0.85rem;font-size:0.80rem;color:{TEXT_SECONDARY};line-height:1.55;">'
        f'<strong style="color:{TEXT_PRIMARY};">Evidence &amp; ranking logic:</strong> {_esc(conf_text)}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

    with st.expander(f"Dossier · Stop timeline · Segment chart · Route map · Route {opt['route']}", expanded=is_selected):
        tab_tl, tab_chart, tab_map = st.tabs(["Stop-by-Stop Timeline", "Segment Load Breakdown", "Route Geometry"])
        with tab_tl:
            st.markdown(
                ui_theme.stop_timeline_html(seg, opt["origin"], opt["destination"]),
                unsafe_allow_html=True,
            )
        with tab_chart:
            if not has_load or seg["segment_load"].dropna().empty:
                st.info("No matched historical ticket demand data available to chart for this route/window.")
            else:
                plot_seg = seg.copy()
                plot_seg["segment_load_plot"] = plot_seg["segment_load"].fillna(0.0)
                has_net_col = "network_load_percentile" in plot_seg.columns and plot_seg["network_load_percentile"].notna().any()
                color_col = "network_load_percentile" if has_net_col else "relative_load_index"
                color_lbl = "Network %ile" if color_col == "network_load_percentile" else "Within-Route RLI"
                fig = px.bar(
                    plot_seg, x="from_norm", y="segment_load_plot",
                    color=color_col, color_continuous_scale=LOAD_SCALE, range_color=[0, 1],
                    labels={"from_norm": "Boarding / Segment Start", "segment_load_plot": "Historical pax volume", color_col: color_lbl},
                    title=f"Segment demand profile along Route {opt['route']}",
                )
                fig.update_layout(**_plotly_defaults(), height=320)
                st.plotly_chart(_grid(fig), width="stretch")

            cols_to_show = {
                "From Stop": seg["from_norm"].astype(str).str.title(),
                "To Stop": seg["to_norm"].astype(str).str.title(),
                "Passenger Volume": seg["segment_load"].map(lambda v: f"{int(round(v)):,}" if pd.notna(v) else "N/A"),
                "Within-Route RLI": seg["relative_load_index"].map(lambda v: f"{float(v):.3f}" if pd.notna(v) else "N/A"),
            }
            if "network_load_percentile" in seg.columns:
                cols_to_show["Network %ile"] = seg["network_load_percentile"].map(
                    lambda v: f"{float(v) * 100:.1f}%" if pd.notna(v) else "N/A"
                )
            if "ticket_count" in seg.columns:
                cols_to_show["Tickets"] = seg["ticket_count"].astype(int)
            if "obs_status" in seg.columns:
                status_map = {
                    "observed": "Observed",
                    "zero_observed_in_window": "0 tickets in window",
                    "unmatched_route": "No ticket data (N/A)",
                    "unmatched_segment": "Unmatched (N/A)",
                    "no_tickets_in_window": "No route tickets (N/A)",
                }
                cols_to_show["Data Status"] = seg["obs_status"].map(lambda s: status_map.get(s, s))
            st.dataframe(pd.DataFrame(cols_to_show), width="stretch", hide_index=True)

        with tab_map:
            coords = opt.get("stop_coords")
            if coords and len(coords) >= 2:
                cdf = pd.DataFrame(coords)
                fig_map = px.line_map(cdf, lat="lat", lon="lon", hover_name="stop", zoom=11, height=380)
                fig_map.update_traces(line=dict(width=4, color=VIOLET_NEON))
                fig_map.add_trace(
                    go.Scattermap(
                        lat=cdf["lat"], lon=cdf["lon"], mode="markers",
                        marker=dict(size=9, color=CYAN_ELECTRIC),
                        text=cdf["stop"].str.title(), hoverinfo="text", name="Stops",
                    )
                )
                fig_map.update_layout(
                    map=dict(style="carto-darkmatter"),
                    paper_bgcolor="rgba(11, 16, 27, 0.72)",
                    margin=dict(l=0, r=0, t=0, b=0),
                )
                st.plotly_chart(fig_map, width="stretch")
            else:
                st.info(
                    "Geographic route map unavailable — the active dataset does not include "
                    "stop coordinates (`stop_lat`, `stop_lon` in GTFS `stops.txt`). LoadLens "
                    "never draws synthetic geographic coordinates — inspect the Animated Route "
                    "Trace or Stop-by-Stop Timeline above."
                )


# ============================================================================
# 03 — ROUTE INTELLIGENCE (analytical workspace)
# ============================================================================
def render_route_analytics(tickets, segments, topology, *, dq: Optional[Dict] = None):
    date_lbl = _date_range_label(tickets, dq)
    ui_theme.page_hero(
        "Route Intelligence",
        "City-wide corridor investigation: demand rankings, peak surges, weekday/weekend dynamics, telemetry coverage.",
        "Filter, compare, and audit route performance with strict evidence layers.",
        badge="OPERATOR INTELLIGENCE",
    )

    if tickets is None or len(tickets) == 0:
        st.warning("No cleaned ticket rows available for the current dataset.")
        return

    ranking_all = analytics.route_demand_ranking(tickets)
    if len(ranking_all) == 0:
        st.warning("No route records available.")
        return

    fc1, fc2, fc3 = st.columns([3, 2, 3])
    with fc1:
        route_filter = st.text_input("Filter routes by number / label", value="", placeholder="e.g. 717 or 543", key="ra_filter")
    with fc2:
        dir_options = ["All"] + sorted(ranking_all["direction"].unique().tolist())
        dir_filter = st.selectbox("Direction filter", dir_options, key="ra_dir")
    ranking = ranking_all.copy()
    if dir_filter != "All":
        ranking = ranking[ranking["direction"] == dir_filter]
    if route_filter.strip():
        q = route_filter.strip().upper()
        ranking = ranking[ranking["route"].str.upper().str.contains(q, regex=False)]

    if len(ranking) == 0:
        st.info("No routes match the active filters. Clear the route or direction filter above.")
        return

    with fc3:
        max_slider = min(len(ranking), 100)
        if max_slider <= 5:
            top_n = max_slider
            st.caption(f"Showing all {max_slider} matching route(s)")
        else:
            top_n = st.slider("Top N routes displayed", 5, max_slider, min(20, max_slider))

    filtered_tickets = tickets[tickets["route"].isin(ranking["route"])]
    if dir_filter != "All":
        filtered_tickets = filtered_tickets[filtered_tickets["direction"] == dir_filter]

    pq = analytics.peak_vs_offpeak(filtered_tickets)
    ui_theme.kpi_row([
        ("Matching Routes",      f"{len(ranking):,}",                            "route+direction combinations"),
        ("Filtered Passengers",  f"{int(filtered_tickets['passenger_count'].sum()):,}", f"{len(filtered_tickets):,} tickets"),
        ("Peak Share",           f"{pq['peak_share_pct']:.1f}%",                pq["peak_window_label"]),
        ("Top Route Volume",     f"{int(ranking['passenger_volume'].iloc[0]):,}", f"{ranking['route'].iloc[0]} ({ranking['direction'].iloc[0]})"),
    ])

    ui_theme.section_eyebrow("A", "Route Demand Ranking")
    top = ranking.head(top_n).copy()
    top["label"] = top["route"] + " · " + top["direction"]
    top["veh_cov_pct"] = (top["vehicle_coverage"] * 100).round(1)
    fig = px.bar(
        top.sort_values("passenger_volume"), x="passenger_volume", y="label", orientation="h",
        color="direction",
        hover_data={"ticket_count": ":,", "avg_passenger_count": ":.2f", "veh_cov_pct": ":.1f", "label": False},
        color_discrete_map={"up": CYAN_ELECTRIC, "down": VIOLET_NEON, "unknown": TEXT_MUTED},
        labels={"passenger_volume": "Passenger volume", "label": "Route · Direction", "veh_cov_pct": "Vehicle ID %"},
    )
    fig.update_layout(**_plotly_defaults(), title="", height=max(420, min(540, 28 * top_n + 80)))
    st.plotly_chart(_grid(fig), width="stretch")

    ui_theme.section_eyebrow("B", "Peak dynamics & telemetry coverage")
    c1, c2 = st.columns([7, 5])
    with c1:
        st.markdown("#### Peak vs. Off-peak split")
        fig_pk = go.Figure(
            go.Pie(
                labels=["Peak (08–11, 17–21 IST)", "Off-peak"],
                values=[pq["peak_passenger_volume"], pq["offpeak_passenger_volume"]],
                hole=0.64,
                marker=dict(colors=[AMBER_SIGNAL, CYAN_ELECTRIC], line=dict(color=BG_VOID, width=2)),
                textinfo="label+percent", textfont=dict(color=TEXT_PRIMARY),
            )
        )
        fig_pk.update_layout(
            **_plotly_defaults(), title="", height=320, showlegend=False,
            annotations=[dict(
                text=f"<b>{pq['peak_share_pct']:.1f}%</b><br>peak", x=0.5, y=0.5,
                font_size=14, font_color=TEXT_PRIMARY, showarrow=False,
            )],
        )
        st.plotly_chart(fig_pk, width="stretch")

        st.markdown("#### Vehicle ID telemetry coverage (Top 12)")
        cov_route = ranking.head(12).sort_values("vehicle_coverage", ascending=False).copy()
        cov_route["label"] = cov_route["route"] + " · " + cov_route["direction"]
        cov_route["pct"] = (cov_route["vehicle_coverage"] * 100).round(1)
        fig_cov = px.bar(
            cov_route, x="label", y="pct",
            color="pct", color_continuous_scale=LOAD_SCALE, range_color=[0, 100],
            labels={"label": "Route", "pct": "Has vehicle ID (%)"},
        )
        fig_cov.update_layout(**_plotly_defaults(), title="", height=290, showlegend=False, xaxis_tickangle=-35)
        st.plotly_chart(_grid(fig_cov), width="stretch")

    with c2:
        st.markdown("#### Weekday vs. Weekend hourly pulse")
        wd_we = analytics.weekday_weekend_hourly(filtered_tickets)
        wd_we["day_type"] = wd_we["ticket_is_weekend"].map({True: "Weekend", False: "Weekday"})
        fig_wd = px.line(
            wd_we, x="ticket_hour", y="passenger_volume", color="day_type", markers=True,
            color_discrete_map={"Weekday": CYAN_ELECTRIC, "Weekend": AMBER_SIGNAL},
            labels={"ticket_hour": "Hour of day (IST)", "passenger_volume": "Passenger volume", "day_type": "Day type"},
        )
        fig_wd.update_traces(line=dict(width=2.6), marker=dict(size=6))
        fig_wd.update_layout(**_plotly_defaults(), title="", height=290)
        st.plotly_chart(_grid(fig_wd), width="stretch")

        st.markdown(f"#### Daily passenger volume ({_esc(date_lbl)})")
        daily = analytics.weekday_daily_volume(filtered_tickets)
        daily["day_type"] = daily["is_weekend"].map({True: "Weekend", False: "Weekday"})
        fig_day = px.bar(
            daily, x="ticket_date", y="passenger_volume", color="day_type",
            color_discrete_map={"Weekday": VIOLET_NEON, "Weekend": AMBER_SIGNAL},
            labels={"ticket_date": "Date", "passenger_volume": "Passenger volume", "day_type": "Day type"},
        )
        fig_day.update_layout(**_plotly_defaults(), title="", height=290, xaxis_tickangle=-30)
        st.plotly_chart(_grid(fig_day), width="stretch")

    ui_theme.section_eyebrow("C", "Route × Hour Demand Heatmap (Top 15 matching routes)")
    top_routes = ranking["route"].drop_duplicates().head(15).tolist()
    sub = filtered_tickets[filtered_tickets["route"].isin(top_routes)]
    if len(sub) > 0:
        hm = sub.groupby(["route", "ticket_hour"], as_index=False)["passenger_count"].sum()
        pivot = (
            hm.pivot(index="route", columns="ticket_hour", values="passenger_count")
            .reindex(columns=range(24), fill_value=0)
            .fillna(0)
        )
        fig_hm = px.imshow(
            pivot.values, x=list(pivot.columns), y=list(pivot.index),
            color_continuous_scale=LOAD_SCALE,
            labels=dict(x="Hour (IST)", y="Route", color="Passengers"),
            aspect="auto",
        )
        fig_hm.update_layout(**_plotly_defaults(), title="", height=460)
        st.plotly_chart(_grid(fig_hm), width="stretch")

    ui_theme.section_eyebrow("D", "Route Intelligence Ledger")
    rank_disp = ranking.head(50).copy()
    rank_disp["vehicle_coverage"] = (rank_disp["vehicle_coverage"] * 100).round(1)
    rank_disp["avg_passenger_count"] = rank_disp["avg_passenger_count"].round(2)
    st.dataframe(
        rank_disp[[
            "demand_rank", "route", "direction", "passenger_volume",
            "ticket_count", "avg_passenger_count", "vehicle_coverage", "unique_stops",
        ]].rename(columns={
            "demand_rank": "Rank", "route": "Route", "direction": "Direction",
            "passenger_volume": "Passengers", "ticket_count": "Tickets",
            "avg_passenger_count": "Avg Pax/Ticket", "vehicle_coverage": "Vehicle ID %",
            "unique_stops": "Boarding Stops",
        }),
        width="stretch", hide_index=True,
    )


# ============================================================================
# 04 — SEGMENT EXPLORER (signature corridor schematic)
# ============================================================================
def render_segment_explorer(tickets, segments, topology, *, topology_meta: Optional[Dict] = None):
    ui_theme.page_hero(
        "Segment Explorer",
        "Animated corridor schematic · bottleneck isolation · stop-to-stop segment forensics.",
        "Where on a corridor does the load accumulate? Select a route, walk the chain.",
        badge="VISUAL SIGNATURE // CORRIDOR DIAGNOSTICS",
    )

    if topology_meta:
        uncertain = [
            f"{m['route']} ({m['direction']} — {m['status'].replace('uncertain_', '')})"
            for m in topology_meta.values()
            if not m.get("reliable", True)
        ]
        if uncertain:
            ui_theme.limitation_banner(
                f"<strong>Topology safety notice:</strong> {len(uncertain)} circular/ambiguous route(s) "
                f"({_html.escape(', '.join(sorted(uncertain)[:6]))}{'...' if len(uncertain) > 6 else ''}) "
                "are omitted from synthetic linear segment expansion without GTFS to prevent assigning "
                "demand across unrelated stops."
            )

    if segments is None or len(segments) == 0:
        st.warning("No segments available for the current dataset.")
        return

    routes = sorted(segments["route"].unique())
    c1, c2, c3 = st.columns([3, 2, 2])
    with c1:
        route = st.selectbox("Select route", routes, index=0, key="se_route")
    avail_dirs = sorted(segments.loc[segments["route"] == route, "direction"].unique())
    with c2:
        sel_dir = st.selectbox("Direction", avail_dirs, index=0, key="se_dir")
    with c3:
        sort_metric = st.selectbox(
            "Sort table by",
            ["rank (stop order)", "segment_load", "network_load_percentile", "relative_load_index"],
            key="se_sort",
        )

    seg_route = analytics.route_segments(segments, route, sel_dir)
    if len(seg_route) == 0:
        st.warning(f"No segments for {route} ({sel_dir}).")
        return

    if topology_meta and (route, sel_dir) in topology_meta:
        tm = topology_meta[(route, sel_dir)]
        if tm.get("excluded_disconnected_stops", 0) > 0:
            st.info(tm["reason"])

    peak_row = seg_route.loc[seg_route["segment_load"].idxmax()]
    avg_load = float(seg_route["segment_load"].mean())
    route_tickets = tickets[(tickets["route"] == route) & (tickets["direction"] == sel_dir)]
    veh_cov = float(route_tickets["has_vehicle"].mean() * 100) if len(route_tickets) else 0.0

    ui_theme.kpi_row([
        ("Corridor Segments",     f"{len(seg_route)}", f"{route} · {sel_dir.upper()}"),
        ("Peak Segment Load",     f"{int(peak_row['segment_load']):,}",
         f"{str(peak_row['from_norm']).title()} → {str(peak_row['to_norm']).title()}"),
        ("Avg Segment Load",      f"{avg_load:,.1f}", "historical passengers / segment"),
        ("Route Vehicle Coverage",f"{veh_cov:.1f}%", f"{len(route_tickets):,} observed tickets"),
    ])

    seg_labels = [
        f"Rank {int(r.rank_a)}→{int(r.rank_b)} · {str(r.from_norm).title()} → {str(r.to_norm).title()}"
        for r in seg_route.itertuples(index=False)
    ]
    peak_idx = int(seg_route["segment_load"].idxmax())
    sel_seg_lbl = st.selectbox(
        "Inspect individual segment (highlighted in corridor schematic below)",
        options=seg_labels,
        index=peak_idx if peak_idx < len(seg_labels) else 0,
        key="se_seg_pick",
    )
    sel_seg_idx = seg_labels.index(sel_seg_lbl) if sel_seg_lbl in seg_labels else 0

    st.markdown(
        '<div class="ll-panel-head" style="margin-top:0.85rem;">'
        f'<div class="ll-panel-title">Animated Stop-to-Stop Demand Corridor · {_esc(route)} ({_esc(sel_dir.upper())})</div>'
        '<div class="ll-panel-meta">Beam colour = demand tier · thicker = higher</div>'
        '</div>',
        unsafe_allow_html=True,
    )
    st.caption("Ordered by reliable topology rank; animated beam thickness and colour reflect demand tier (Cyan = low, Amber = moderate, Coral = high).")
    st.markdown(ui_theme.corridor_strip_html(seg_route, highlight_idx=sel_seg_idx), unsafe_allow_html=True)

    s_row = seg_route.iloc[sel_seg_idx]
    s_net = float(s_row["network_load_percentile"]) if "network_load_percentile" in seg_route.columns else float(s_row["relative_load_index"])
    s_lbl, s_col, s_bg = ui_theme.demand_tier(s_net)
    s_veh_load = float(s_row["veh_segment_load"]) if "veh_segment_load" in seg_route.columns else 0.0
    s_veh_tkts = int(s_row["veh_ticket_count"]) if "veh_ticket_count" in seg_route.columns else 0
    s_daily = float(s_row["avg_daily_load"]) if ("avg_daily_load" in seg_route.columns and pd.notna(s_row["avg_daily_load"])) else None
    peak_share = (float(s_row["segment_load"]) / max(float(peak_row["segment_load"]), 1.0)) * 100.0
    st.markdown(
        f'<div class="ll-card" style="border-left:4px solid {s_col};background:linear-gradient(180deg, rgba(17,24,39,0.85), rgba(11,16,27,0.96));">'
        f'<div class="ll-panel-head">'
        f'<div class="ll-panel-title">Segment Telemetry Dossier · {_esc(s_row["from_norm"]).title()} → {_esc(s_row["to_norm"]).title()}</div>'
        f'<span class="ll-demand-pill" style="color:{s_col};background:{s_bg};"><span class="ll-demand-dot" style="background:{s_col};"></span>{_esc(s_lbl)} · P{int(round(s_net * 100))}</span>'
        f'</div>'
        f'<div class="ll-route-metrics" style="margin-top:0.6rem;padding-top:0.7rem;">'
        f'<div><div class="ll-rm-label">Total Segment Pax</div><div class="ll-rm-val">{int(s_row["segment_load"]):,} ({int(s_row["ticket_count"]):,} tkts)</div></div>'
        f'<div><div class="ll-rm-label">Avg Daily Load</div><div class="ll-rm-val">{f"{s_daily:,.1f} pax/day" if s_daily is not None else "N/A"}</div></div>'
        f'<div><div class="ll-rm-label">Vehicle-Tagged Subset</div><div class="ll-rm-val">{int(s_veh_load):,} pax ({s_veh_tkts:,} tkts)</div></div>'
        f'<div><div class="ll-rm-label">Share of Route Peak · RLI</div><div class="ll-rm-val">{peak_share:.1f}% · {float(s_row["relative_load_index"]):.2f}</div></div>'
        f'</div></div>',
        unsafe_allow_html=True,
    )

    ui_theme.section_eyebrow("CHART", "Segment load profile along route")
    hover_labels = (
        seg_route["from_norm"].astype(str).str.title() + " → "
        + seg_route["to_norm"].astype(str).str.title()
    )
    tier_col = "network_load_percentile" if "network_load_percentile" in seg_route.columns else "relative_load_index"
    bar_colors = [ui_theme.demand_tier(float(r))[1] for r in seg_route[tier_col]]
    fig = go.Figure(
        go.Bar(
            x=seg_route["rank_a"].astype(str) + "→" + seg_route["rank_b"].astype(str),
            y=seg_route["segment_load"],
            customdata=hover_labels,
            marker_color=bar_colors,
            hovertemplate="Rank %{x}<br>%{customdata}<br>Historical volume: %{y:,}<extra></extra>",
        )
    )
    fig.update_layout(
        **_plotly_defaults(),
        title=f"Segment load profile · {route} ({sel_dir.upper()})",
        xaxis_title="Consecutive stop rank pair",
        yaxis_title="Historical passenger volume",
        height=400,
    )
    st.plotly_chart(_grid(fig), width="stretch")

    ui_theme.section_eyebrow("FOCUS", "Bottlenecks · Hourly pulse")
    cb1, cb2 = st.columns([1, 1])
    with cb1:
        st.markdown("#### Highest-demand bottlenecks")
        top3 = seg_route.nlargest(3, "segment_load")
        for row in top3.itertuples(index=False):
            rel = float(row.relative_load_index)
            net_v = float(getattr(row, "network_load_percentile", rel))
            lbl, col, bg = ui_theme.demand_tier(net_v)
            st.markdown(
                f'<div class="ll-card" style="padding:0.78rem 1.05rem;margin-bottom:0.55rem;'
                f'border-left:4px solid {col};background:linear-gradient(180deg, rgba(17,24,39,0.85), rgba(11,16,27,0.96));">'
                f'<div style="display:flex;justify-content:space-between;align-items:center;gap:0.5rem;">'
                f'<div><strong>{_esc(row.from_norm).title()} → {_esc(row.to_norm).title()}</strong><br>'
                f'<span class="ll-muted">Rank {int(row.rank_a)}→{int(row.rank_b)} · {int(row.ticket_count):,} tickets · RLI {rel:.2f}</span></div>'
                f'<div style="text-align:right;"><strong style="color:{TEXT_PRIMARY};">{int(row.segment_load):,} pax</strong><br>'
                f'<span class="ll-demand-pill" style="color:{col};background:{bg};padding:0.20rem 0.55rem;font-size:0.70rem;">{_esc(lbl)} · P{int(round(net_v * 100))}</span></div>'
                f'</div></div>',
                unsafe_allow_html=True,
            )

    with cb2:
        st.markdown(f"#### Hourly pulse · {route} ({sel_dir.upper()})")
        fig_h = _grid(_hour_chart(route_tickets, f"{route} · {sel_dir.upper()} hourly demand (IST)", highlight_peak=True))
        fig_h.update_layout(height=320)
        st.plotly_chart(fig_h, width="stretch")

    ui_theme.section_eyebrow("LEDGER", "Complete segment breakdown")
    if sort_metric == "segment_load":
        seg_view = seg_route.sort_values("segment_load", ascending=False)
    elif sort_metric == "network_load_percentile" and "network_load_percentile" in seg_route.columns:
        seg_view = seg_route.sort_values("network_load_percentile", ascending=False)
    elif sort_metric == "relative_load_index":
        seg_view = seg_route.sort_values("relative_load_index", ascending=False)
    else:
        seg_view = seg_route.copy()

    disp = seg_view.copy()
    disp["from"] = disp["from_norm"].astype(str).str.title()
    disp["to"] = disp["to_norm"].astype(str).str.title()
    disp["tier"] = disp[tier_col].map(lambda r: ui_theme.demand_tier(float(r))[0])
    disp["relative_load_index"] = disp["relative_load_index"].astype(float).round(3)
    show_cols = ["rank_a", "rank_b", "from", "to", "segment_load", "ticket_count", "relative_load_index", "tier"]
    rename_map = {
        "rank_a": "Rank A", "rank_b": "Rank B", "from": "From stop", "to": "To stop",
        "segment_load": "Volume", "ticket_count": "Tickets",
        "relative_load_index": "Within-Route RLI", "tier": "Network Demand Tier",
    }
    if "network_load_percentile" in disp.columns:
        disp["net_pct_disp"] = (disp["network_load_percentile"].astype(float) * 100).round(1)
        show_cols.insert(6, "net_pct_disp")
        rename_map["net_pct_disp"] = "Network %ile"
    st.dataframe(
        disp[show_cols].rename(columns=rename_map),
        width="stretch", hide_index=True,
    )


# ============================================================================
# 05 — DATA FORENSICS (featured investigation report)
# ============================================================================
def render_data_quality(tickets, segments, topology, dq, seg_meta=None, *, topology_meta: Optional[Dict] = None):
    ui_theme.page_hero(
        "Data Forensics",
        "Row-level exclusion ledger · vehicle telemetry gaps · topology reliability · observed vs inferred boundaries.",
        "Transparency is a product feature — what we report, and what we deliberately do not fabricate.",
        badge="FORENSIC AUDIT REPORT",
    )

    if not dq:
        st.warning("Quality report not available for the active dataset.")
        return

    meta = seg_meta if seg_meta is not None else _dq_meta()

    ui_theme.kpi_row([
        ("Raw Ticket Rows",        f"{dq['raw_rows']:,}",                       "ingested from source"),
        ("Kept Rows",              f"{dq['kept_rows']:,}",
         f"{dq['kept_rows']/max(dq['raw_rows'],1)*100:.1f}% retained"),
        ("Missing Vehicle ID",     f"{dq['missing_vehicle_pct'] if 'missing_vehicle_pct' in dq else dq['missing_vehicle_number_pct']:.2f}%",
         f"{dq.get('missing_vehicle_number_count', 0):,} rows without vehicle_number"),
        ("Reliable Chains",        f"{len(topology):,}",                        f"across {dq['unique_routes']:,} unique route labels"),
        ("Back-Tracked Rejected",  f"{meta.get('skipped_backward_journeys', 0):,}",
         f"{meta.get('skipped_unknown_stops', 0):,} unmatched/uncertain rows"),
    ])

    ui_theme.section_eyebrow("A", "Evidence classification")
    st.markdown("#### What LoadLens treats as directly observed, derived, or unavailable")
    o1, o2, o3 = st.columns(3)
    with o1:
        ui_theme.card(
            f"<div class='ll-mono-tag'>EVIDENCE CLASS A</div>"
            f"<h4 style='margin:0.25rem 0 0.5rem 0;color:{CYAN_ELECTRIC};font-family:Space Grotesk,sans-serif;'>Directly Observed</h4>"
            "<ul style='padding-left:1.1rem;margin-bottom:0;font-size:0.86rem;color:#91A0B5;'>"
            "<li><code>route</code>, <code>start_stop_name</code>, <code>end_stop_name</code></li>"
            "<li><code>passenger_count</code> (exact ticket count, never extrapolated)</li>"
            "<li><code>created_at</code> (normalised to IST, labelled ticket-creation time)</li>"
            "<li>Partial <code>vehicle_number</code> (kept separate from missing rows)</li>"
            "</ul>"
        )
    with o2:
        ui_theme.card(
            f"<div class='ll-mono-tag' style='color:{AMBER_SIGNAL};'>EVIDENCE CLASS B</div>"
            f"<h4 style='margin:0.25rem 0 0.5rem 0;color:{AMBER_SIGNAL};font-family:Space Grotesk,sans-serif;'>Derived &amp; Estimated</h4>"
            "<ul style='padding-left:1.1rem;margin-bottom:0;font-size:0.86rem;color:#91A0B5;'>"
            "<li>Chain-preserving stop order (or GTFS <code>stop_times.txt</code> when supplied)</li>"
            "<li>Consecutive segment passenger sums &amp; daily rates (<code>active_days</code>)</li>"
            "<li>Vehicle-tagged demand / observed vehicle ID (where coverage &ge; 25%)</li>"
            "<li>Network Load Percentile &amp; Within-Route Relative Load Index</li>"
            "</ul>"
        )
    with o3:
        ui_theme.card(
            f"<div class='ll-mono-tag' style='color:#FF6B70;'>EVIDENCE CLASS C</div>"
            f"<h4 style='margin:0.25rem 0 0.5rem 0;color:#FF6B70;font-family:Space Grotesk,sans-serif;'>Unavailable · Never Fabricated</h4>"
            "<ul style='padding-left:1.1rem;margin-bottom:0;font-size:0.86rem;color:#91A0B5;'>"
            "<li>Live GPS vehicle locations &amp; real-time physical occupancy</li>"
            "<li>Seat capacity / &ldquo;overcrowded&rdquo; thresholds</li>"
            "<li>Travel durations &amp; geographic maps without supplied GTFS</li>"
            "<li>Intermediate segment loads on circular/ambiguous routes without GTFS</li>"
            "</ul>"
        )

    ui_theme.section_eyebrow("B", "Row accounting & telemetry")
    c1, c2 = st.columns([1, 1])
    with c1:
        st.markdown("#### Row accounting & exclusion ledger")
        rows = [
            ("Missing core fields",                    dq.get("dropped_missing_core", 0)),
            ("Invalid / empty stop names",            dq.get("dropped_invalid_stop_names", 0)),
            ("Non-positive `passenger_count`",        dq.get("dropped_nonpositive_passenger_count", 0)),
            ("Same origin == destination",             dq.get("dropped_same_origin_and_destination", 0)),
            ("Back-tracked in topology (start_rank > end_rank)", meta.get("skipped_backward_journeys", 0)),
            ("Same rank in topology",                  meta.get("skipped_same_stop", 0)),
            ("Unknown / uncertain-topology / excluded stops",   meta.get("skipped_unknown_stops", 0)),
        ]
        df_excl = pd.DataFrame(rows, columns=["Exclusion Reason", "Rows Excluded"])
        df_excl["Rows Excluded"] = df_excl["Rows Excluded"].map(lambda v: f"{int(v):,}")
        st.dataframe(df_excl, width="stretch", hide_index=True)

    with c2:
        st.markdown("#### Passengers per ticket distribution")
        if len(tickets) > 0:
            ct = tickets["passenger_count"].astype(int).value_counts().sort_index().reset_index()
            ct.columns = ["passenger_count", "n_tickets"]
            fig = px.bar(
                ct, x="passenger_count", y="n_tickets",
                color_discrete_sequence=[VIOLET_NEON],
                labels={"passenger_count": "Passengers on ticket", "n_tickets": "Ticket count"},
            )
            fig.update_layout(**_plotly_defaults(), title="", height=320, showlegend=False)
            st.plotly_chart(_grid(fig), width="stretch")
        else:
            st.info("No cleaned ticket rows to display.")

    ui_theme.section_eyebrow("C", "Vehicle ID telemetry coverage by hour-of-day (IST)")
    if len(tickets) > 0:
        cov_hour = (
            tickets.assign(has_veh=tickets["has_vehicle"].astype(int))
            .groupby("ticket_hour", as_index=False)["has_veh"]
            .mean()
        )
        cov_hour["pct"] = (cov_hour["has_veh"] * 100).round(1)
        fig = px.bar(
            cov_hour, x="ticket_hour", y="pct",
            color="pct", color_continuous_scale=LOAD_SCALE, range_color=[0, 100],
            labels={"ticket_hour": "Hour of day (IST)", "pct": "% with vehicle_number"},
        )
        fig.update_layout(**_plotly_defaults(), title="", height=320, showlegend=False)
        st.plotly_chart(_grid(fig), width="stretch")

    if topology_meta:
        ui_theme.section_eyebrow("D", "Ticket-derived topology reliability audit")
        meta_df = pd.DataFrame(list(topology_meta.values()))
        if len(meta_df) > 0:
            counts = meta_df["status"].value_counts().to_dict()
            st.caption(
                f"Summary across {len(meta_df)} route+direction chains: "
                + ", ".join(f"{k}: {v}" for k, v in sorted(counts.items()))
            )
            flagged = meta_df[
                (~meta_df["reliable"])
                | (meta_df["excluded_disconnected_stops"] > 0)
                | (meta_df["cycle_edges_removed"] > 0)
            ]
            if len(flagged) > 0:
                st.dataframe(
                    flagged[[
                        "route", "direction", "status", "reliable", "n_wcc",
                        "excluded_disconnected_stops", "max_scc_size", "cycle_edges_removed",
                        "adj_reach_pct", "reason",
                    ]].rename(columns={
                        "route": "Route", "direction": "Dir", "status": "Status",
                        "reliable": "Usable Chain", "n_wcc": "Components",
                        "excluded_disconnected_stops": "Isolated Excluded",
                        "max_scc_size": "Max SCC", "cycle_edges_removed": "Cycles Broken",
                        "adj_reach_pct": "DAG Reach %", "reason": "Diagnostic Note",
                    }),
                    width="stretch", hide_index=True,
                )


@st.cache_data
def _dq_meta() -> dict:
    p = Path(__file__).resolve().parent / "data" / "cache" / "segment_meta.json"
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))
