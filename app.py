"""LOADLENS — Crowdedness-aware journey planner & demand intelligence terminal.

Streamlit shell, dataset bootstrap, and module router. Calculation pipeline is
preserved untouched (``src/``); only the visualisation layer is the redesigned
premium urban-intelligence experience.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))


def html_escape(value) -> str:
    """Local HTML escape helper used inside the sidebar status block."""
    import html as _html
    return _html.escape(str(value))

import pandas as pd
import streamlit as st

from src import ui_theme
from src.data_loader import (
    DQ_REPORT_JSON,
    RAW_DIR,
    SAMPLE_CSV,
    SEGMENT_META_JSON,
    SEGMENTS_PARQUET,
    TICKETS_PARQUET,
    TRIP_GRAPH_PARQUET,
    clean_with_report,
    load_raw,
    load_raw_buffer,
)
from src.gtfs import extract_gtfs_zip, gtfs_status
from src.load_engine import compute_segment_loads, load_segments
from src.topology import (
    build_route_topology_with_meta,
    load_topology,
    load_topology_meta,
)
from app_pages import (
    render_data_quality,
    render_journey_planner,
    render_overview,
    render_route_analytics,
    render_segment_explorer,
)


# Page config — singular, distinctive identity from the first browser tab.
st.set_page_config(
    page_title="LOADLENS — Investigate the Movement of the City",
    page_icon="◬",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Inject the design system (single CSS payload, premium palette).
ui_theme.inject_css()


GTFS_DIR = PROJECT_ROOT / "data" / "gtfs"
UPLOADED_GTFS_DIR = PROJECT_ROOT / "data" / "gtfs_uploaded"


# ============================================================================
# DATASET CACHE LAYER (preserved from original; only signature added)
# ============================================================================
@st.cache_data(show_spinner="Processing uploaded ticket dataset...")
def _process_uploaded_bytes(raw_bytes: bytes, filename: str):
    import io
    if not raw_bytes:
        raise ValueError(f"Uploaded file '{filename}' is empty (0 bytes).")
    raw_df = load_raw_buffer(io.BytesIO(raw_bytes), filename)
    tickets, dq = clean_with_report(
        raw_df, source_signature=f"uploaded:{filename}", write_dq=False
    )
    topology, topology_meta = build_route_topology_with_meta(tickets)
    segments, seg_meta = compute_segment_loads(tickets, topology)
    sig = hashlib.md5(raw_bytes).hexdigest()[:12]
    info = {"mode": "uploaded", "label": f"Uploaded: {filename}", "sig": f"up:{sig}"}
    return tickets, segments, topology, topology_meta, dq, seg_meta, info


@st.cache_data(show_spinner="Loading ticket dataset & building route topology...")
def _load_default_dataset(cache_sig: str):
    env_src = os.environ.get("LOADLENS_TICKETS", "").strip()
    if env_src:
        p = Path(env_src)
        if not p.exists():
            raise FileNotFoundError(f"LOADLENS_TICKETS points to missing file: {p}")
        raw_df = load_raw(p)
        tickets, dq = clean_with_report(raw_df, source_signature=str(p), write_dq=False)
        topology, topology_meta = build_route_topology_with_meta(tickets)
        segments, seg_meta = compute_segment_loads(tickets, topology)
        return tickets, segments, topology, topology_meta, dq, seg_meta, {
            "mode": "env",
            "label": f"Env LOADLENS_TICKETS ({p.name})",
            "sig": f"env:{cache_sig}",
        }

    if (
        TICKETS_PARQUET.exists()
        and SEGMENTS_PARQUET.exists()
        and TRIP_GRAPH_PARQUET.exists()
    ):
        tickets = pd.read_parquet(TICKETS_PARQUET)
        segments = load_segments()
        topology = load_topology()
        topology_meta = load_topology_meta()
        if not topology_meta and len(tickets) > 0:
            _, topology_meta = build_route_topology_with_meta(tickets)
        dq = json.loads(DQ_REPORT_JSON.read_text(encoding="utf-8")) if DQ_REPORT_JSON.exists() else {}
        seg_meta = json.loads(SEGMENT_META_JSON.read_text(encoding="utf-8")) if SEGMENT_META_JSON.exists() else {}
        return tickets, segments, topology, topology_meta, dq, seg_meta, {
            "mode": "cache",
            "label": "Processed cache (data/cache/)",
            "sig": f"cache:{cache_sig}",
        }

    if RAW_DIR.exists():
        for ext in ("*.parquet", "*.pq", "*.csv"):
            matches = sorted(RAW_DIR.glob(ext))
            if matches:
                p = matches[0]
                raw_df = load_raw(p)
                tickets, dq = clean_with_report(raw_df, source_signature=str(p), write_dq=False)
                topology, topology_meta = build_route_topology_with_meta(tickets)
                segments, seg_meta = compute_segment_loads(tickets, topology)
                return tickets, segments, topology, topology_meta, dq, seg_meta, {
                    "mode": "raw",
                    "label": f"Raw file ({p.name})",
                    "sig": f"raw:{p.name}:{cache_sig}",
                }

    if SAMPLE_CSV.exists():
        raw_df = load_raw(SAMPLE_CSV)
        tickets, dq = clean_with_report(
            raw_df, source_signature="data_sample/tickets_sample.csv", write_dq=False
        )
        topology, topology_meta = build_route_topology_with_meta(tickets)
        segments, seg_meta = compute_segment_loads(tickets, topology)
        return tickets, segments, topology, topology_meta, dq, seg_meta, {
            "mode": "sample",
            "label": "Bundled sample (25,000 rows)",
            "sig": f"sample:{cache_sig}",
        }

    raise FileNotFoundError(
        "No ticket dataset found. Upload a CSV/Parquet in the sidebar, set "
        "LOADLENS_TICKETS, or provide data_sample/tickets_sample.csv."
    )


def _cache_signature() -> str:
    env_src = os.environ.get("LOADLENS_TICKETS", "").strip()
    parts = [env_src]
    for p in (TICKETS_PARQUET, SEGMENTS_PARQUET, TRIP_GRAPH_PARQUET, SAMPLE_CSV):
        if p.exists():
            stat = p.stat()
            parts.append(f"{p.name}:{stat.st_size}:{int(stat.st_mtime)}")
    return "|".join(parts)


# ============================================================================
# LEFT INVESTIGATION RAIL (sidebar)
# ============================================================================
_NAV_LABELS = {
    "Overview":        "01 · OVERVIEW",
    "Journey Planner": "02 · JOURNEY INVESTIGATION",
    "Route Analytics": "03 · ROUTE INTELLIGENCE",
    "Segment Explorer":"04 · SEGMENT EXPLORER",
    "Data Quality":    "05 · DATA FORENSICS",
}

with st.sidebar:
    st.markdown(ui_theme.brand_header(), unsafe_allow_html=True)
    st.markdown('<div class="ll-divider"></div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="ll-mono-tag" style="margin-bottom:0.55rem;">Investigation Modules</div>',
        unsafe_allow_html=True,
    )

    page = st.radio(
        "Navigation",
        ["Overview", "Journey Planner", "Route Analytics", "Segment Explorer", "Data Quality"],
        format_func=lambda k: _NAV_LABELS.get(k, k),
        label_visibility="collapsed",
        key="nav_radio",
    )

    st.markdown('<div class="ll-divider"></div>', unsafe_allow_html=True)
    with st.expander("Data & GTFS Sources", expanded=False):
        uploaded_tickets = st.file_uploader(
            "Ticket dataset CSV / Parquet",
            type=["csv", "parquet", "pq"],
            key="ticket_uploader",
        )
        uploaded_gtfs = st.file_uploader(
            "Optional GTFS feed (.zip)",
            type=["zip"],
            key="gtfs_uploader",
        )

    active_gtfs_dir = GTFS_DIR
    gtfs_upload_error = None
    if uploaded_gtfs is not None:
        gtfs_bytes = uploaded_gtfs.getvalue()
        gtfs_hash = hashlib.md5(gtfs_bytes).hexdigest()[:10]
        target = UPLOADED_GTFS_DIR / gtfs_hash
        if not gtfs_status(target).get("available"):
            try:
                extract_res = extract_gtfs_zip(uploaded_gtfs, target)
                if not extract_res.get("available"):
                    gtfs_upload_error = extract_res.get("error") or "Incomplete GTFS archive."
                    if target.exists():
                        shutil.rmtree(target, ignore_errors=True)
            except Exception as exc:
                gtfs_upload_error = f"GTFS ZIP error: {exc}"
                if target.exists():
                    shutil.rmtree(target, ignore_errors=True)
        if gtfs_upload_error is None:
            active_gtfs_dir = target

    if gtfs_upload_error:
        st.error(gtfs_upload_error)
    gtfs_info = gtfs_status(active_gtfs_dir)

    try:
        if uploaded_tickets is not None:
            tickets, segments, topology, topology_meta, dq, seg_meta, ds_info = _process_uploaded_bytes(
                uploaded_tickets.getvalue(), uploaded_tickets.name
            )
        else:
            tickets, segments, topology, topology_meta, dq, seg_meta, ds_info = _load_default_dataset(
                _cache_signature()
            )
    except Exception as exc:
        st.error(
            f"Unable to load ticket dataset: {exc}. "
            "Ensure the file is a valid CSV or Parquet containing required columns "
            "(passenger_count, route, start_stop_name, end_stop_name, created_at)."
        )
        st.stop()

    st.markdown('<div class="ll-divider"></div>', unsafe_allow_html=True)
    unique_routes = dq.get("unique_routes", int(tickets["route"].nunique()) if len(tickets) else 0)
    uncertain_cnt = sum(1 for m in topology_meta.values() if not m.get("reliable", True))
    gtfs_state = "ACTIVE · GTFS-FIRST" if gtfs_info["available"] else "TICKET TOPOLOGY"
    gtfs_col = ui_theme.CYAN_ELECTRIC if gtfs_info["available"] else ui_theme.AMBER_SIGNAL

    st.markdown(
        f'<div class="ll-sys-status">'
        f'<div style="color:{ui_theme.TEXT_PRIMARY};font-weight:600;margin-bottom:0.40rem;letter-spacing:0.10em;font-size:0.70rem;">'
        f'<span class="ll-sys-dot"></span>SYSTEM TELEMETRY</div>'
        f'<div style="font-size:0.62rem;letter-spacing:0.16em;color:{ui_theme.CYAN_ELECTRIC};text-transform:uppercase;margin-bottom:0.42rem;">SOURCE</div>'
        f'<div style="color:{ui_theme.TEXT_PRIMARY};margin-bottom:0.55rem;line-height:1.40;font-size:0.72rem;">{html_escape(ds_info["label"])}</div>'
        f'<div style="font-size:0.62rem;letter-spacing:0.16em;color:{ui_theme.CYAN_ELECTRIC};text-transform:uppercase;margin-bottom:0.35rem;">DATASET</div>'
        f'<div style="line-height:1.65;">'
        f'TICKETS · <span style="color:{ui_theme.CYAN_ELECTRIC};">{len(tickets):,}</span> cleaned<br>'
        f'ROUTES · <span style="color:{ui_theme.TEXT_PRIMARY};">{unique_routes:,}</span> · <span style="color:{ui_theme.CYAN_ELECTRIC};">{len(topology):,}</span> chains'
        f'{f" · <span style=\'color:{ui_theme.AMBER_SIGNAL};\'>{uncertain_cnt} uncertain</span>" if uncertain_cnt else ""}<br>'
        f'SEGMENTS · <span style="color:{ui_theme.TEXT_PRIMARY};">{len(segments):,}</span> mapped<br>'
        f'MODE · <span style="color:{gtfs_col};">{gtfs_state}</span>'
        f'</div></div>',
        unsafe_allow_html=True,
    )
    if ds_info["mode"] == "sample":
        st.caption("Bundled 25k sample active. Upload CSV/Parquet above or set `LOADLENS_TICKETS` to switch.")


# ============================================================================
# ROUTER
# ============================================================================
ds_sig = ds_info.get("sig", "default")
if page == "Overview":
    render_overview(
        tickets, segments, topology, dq, ds_info,
        gtfs_dir=active_gtfs_dir, gtfs_info=gtfs_info,
    )
elif page == "Journey Planner":
    render_journey_planner(
        tickets, segments, topology,
        topology_meta=topology_meta, dataset_sig=ds_sig,
        gtfs_dir=active_gtfs_dir, gtfs_info=gtfs_info,
    )
elif page == "Route Analytics":
    render_route_analytics(tickets, segments, topology, dq=dq)
elif page == "Segment Explorer":
    render_segment_explorer(tickets, segments, topology, topology_meta=topology_meta)
elif page == "Data Quality":
    render_data_quality(tickets, segments, topology, dq, seg_meta, topology_meta=topology_meta)
