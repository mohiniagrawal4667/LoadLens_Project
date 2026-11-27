"""Optional static GTFS feed loader and GTFS-first schedule & demand search.

When official GTFS files (``stops.txt``, ``routes.txt``, ``trips.txt``,
``stop_times.txt``) are supplied, this module treats GTFS as the authoritative
source of route direction, stop ordering, scheduled travel durations, and
scheduled trip counts, and matches ticket OD pairs directly onto the ordered
GTFS stop sequence.

When any required GTFS file is missing or invalid, callers fall back
gracefully to ticket-derived topology and disable schedule-based metrics.
"""
from __future__ import annotations

import functools
import io
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any, BinaryIO, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from .data_loader import normalize_stop, parse_route
from .load_engine import (
    MIN_DISTINCT_VEHICLES,
    MIN_VEHICLE_COVERAGE_PCT,
    MIN_VEHICLE_TICKETS,
    count_active_days,
    route_vehicle_reliability_stats,
)

REQUIRED_GTFS_FILES = ("stops.txt", "routes.txt", "trips.txt", "stop_times.txt")

# Hard decompression caps to protect against ZIP bombs / oversized uploads.
MAX_GTFS_MEMBER_BYTES = 150 * 1024 * 1024       # 150 MB per .txt file
MAX_GTFS_UNCOMPRESSED_BYTES = 250 * 1024 * 1024 # 250 MB total uncompressed .txt
MAX_GTFS_ARCHIVE_MEMBERS = 64

_REQUIRED_COLUMNS = {
    "stops.txt": {"stop_id", "stop_name"},
    "routes.txt": {"route_id"},
    "trips.txt": {"route_id", "trip_id"},
    "stop_times.txt": {"trip_id", "stop_id", "stop_sequence"},
}


def gtfs_status(folder: Path) -> Dict[str, Any]:
    """Inspect *folder* for the required GTFS files and validate headers."""
    if not folder.exists() or not folder.is_dir():
        return {
            "available": False,
            "missing_files": list(REQUIRED_GTFS_FILES),
            "present_files": [],
            "error": f"GTFS directory not found: {folder}",
        }

    present = [f for f in REQUIRED_GTFS_FILES if (folder / f).is_file()]
    missing = [f for f in REQUIRED_GTFS_FILES if f not in present]
    if missing:
        return {
            "available": False,
            "missing_files": missing,
            "present_files": present,
            "error": f"Missing required GTFS file(s): {', '.join(missing)}",
        }

    for fname, req_cols in _REQUIRED_COLUMNS.items():
        try:
            hdr = pd.read_csv(folder / fname, nrows=0)
        except Exception as exc:
            return {
                "available": False,
                "missing_files": [],
                "present_files": present,
                "error": f"Unable to read {fname}: {exc}",
            }
        cols = {c.strip() for c in hdr.columns}
        if not req_cols.issubset(cols):
            return {
                "available": False,
                "missing_files": [],
                "present_files": present,
                "error": f"{fname} missing required columns {sorted(req_cols - cols)}",
            }

    return {
        "available": True,
        "missing_files": [],
        "present_files": present,
        "error": None,
    }


def extract_gtfs_zip(file_obj: BinaryIO, target_dir: Path) -> Dict[str, Any]:
    """Extract required GTFS ``.txt`` files from an uploaded zip archive safely.

    Guards against malformed archives, path traversal (``..``), symlinks,
    excessive member counts, and ZIP-bomb decompression bombs by enforcing
    bounded streaming reads.
    """
    raw_bytes = file_obj.read()
    try:
        zf = zipfile.ZipFile(io.BytesIO(raw_bytes))
    except (zipfile.BadZipFile, OSError) as exc:
        return {
            "available": False,
            "missing_files": list(REQUIRED_GTFS_FILES),
            "present_files": [],
            "error": f"Invalid GTFS ZIP archive: {exc}",
        }

    target_root = target_dir.resolve()
    target_root.mkdir(parents=True, exist_ok=True)
    extracted = 0
    total_uncompressed = 0
    with zf:
        members = zf.infolist()
        if len(members) > MAX_GTFS_ARCHIVE_MEMBERS:
            return {
                "available": False,
                "missing_files": list(REQUIRED_GTFS_FILES),
                "present_files": [],
                "error": f"GTFS ZIP contains too many entries ({len(members)} > {MAX_GTFS_ARCHIVE_MEMBERS}).",
            }
        for member in members:
            if member.is_dir():
                continue
            # Reject symlinks (Unix S_IFLNK = 0o120000) and path traversal segments
            if ((member.external_attr >> 16) & 0o170000) == 0o120000:
                return {
                    "available": False,
                    "missing_files": list(REQUIRED_GTFS_FILES),
                    "present_files": [],
                    "error": "Unsafe symlink entry detected in GTFS ZIP archive.",
                }
            posix_parts = PurePosixPath(member.filename.replace("\\", "/")).parts
            if ".." in posix_parts or "\x00" in member.filename:
                return {
                    "available": False,
                    "missing_files": list(REQUIRED_GTFS_FILES),
                    "present_files": [],
                    "error": "Unsafe path traversal entry detected in GTFS ZIP archive.",
                }
            base = Path(member.filename.replace("\\", "/")).name
            if not (base.endswith(".txt") and base):
                continue
            if member.file_size > MAX_GTFS_MEMBER_BYTES:
                return {
                    "available": False,
                    "missing_files": list(REQUIRED_GTFS_FILES),
                    "present_files": [],
                    "error": f"GTFS entry '{base}' exceeds size limit ({MAX_GTFS_MEMBER_BYTES // (1024 * 1024)} MB).",
                }
            dest_path = (target_root / base).resolve()
            if dest_path.parent != target_root:
                return {
                    "available": False,
                    "missing_files": list(REQUIRED_GTFS_FILES),
                    "present_files": [],
                    "error": f"Unsafe output path for GTFS entry '{base}'.",
                }
            # Stream-read with actual byte counting so spoofed headers cannot bypass caps
            buf = bytearray()
            with zf.open(member, "r") as src_stream:
                while True:
                    chunk = src_stream.read(65536)
                    if not chunk:
                        break
                    total_uncompressed += len(chunk)
                    if len(buf) + len(chunk) > MAX_GTFS_MEMBER_BYTES or total_uncompressed > MAX_GTFS_UNCOMPRESSED_BYTES:
                        return {
                            "available": False,
                            "missing_files": list(REQUIRED_GTFS_FILES),
                            "present_files": [],
                            "error": "GTFS ZIP uncompressed payload exceeds safety limit.",
                        }
                    buf.extend(chunk)
            dest_path.write_bytes(bytes(buf))
            extracted += 1

    if extracted == 0:
        return {
            "available": False,
            "missing_files": list(REQUIRED_GTFS_FILES),
            "present_files": [],
            "error": "ZIP archive contained no .txt GTFS files.",
        }
    return gtfs_status(target_root)


def _parse_gtfs_seconds(val: Any) -> Optional[int]:
    """Convert GTFS ``HH:MM:SS`` (supports hours >= 24) to seconds since midnight."""
    if not isinstance(val, str):
        if pd.isna(val):
            return None
        val = str(val)
    s = val.strip()
    if not s:
        return None
    parts = s.split(":")
    if len(parts) != 3:
        return None
    try:
        h, m, sec = int(parts[0]), int(parts[1]), int(parts[2])
    except ValueError:
        return None
    return h * 3600 + m * 60 + sec


def _gtfs_signature(folder: Path) -> Tuple[Any, ...]:
    items: List[Any] = [str(folder.resolve())]
    for f in REQUIRED_GTFS_FILES:
        p = folder / f
        if p.exists():
            st = p.stat()
            items.append((f, st.st_size, st.st_mtime_ns))
    return tuple(items)


@functools.lru_cache(maxsize=4)
def _load_gtfs_feed_cached(sig: Tuple[Any, ...], folder_str: str) -> Dict[str, pd.DataFrame]:
    folder = Path(folder_str)
    stops = pd.read_csv(folder / "stops.txt", dtype={"stop_id": str})
    routes = pd.read_csv(folder / "routes.txt", dtype={"route_id": str})
    trips = pd.read_csv(folder / "trips.txt", dtype={"route_id": str, "trip_id": str})
    stop_times = pd.read_csv(folder / "stop_times.txt", dtype={"trip_id": str, "stop_id": str})

    stops["stop_id"] = stops["stop_id"].astype(str).str.strip()
    uniq_names = stops["stop_name"].astype(str).unique()
    name_norm_map = {s: normalize_stop(s) for s in uniq_names}
    stops["stop_norm"] = stops["stop_name"].astype(str).map(name_norm_map).fillna("")

    routes["route_id"] = routes["route_id"].astype(str).str.strip()
    if "route_short_name" not in routes.columns:
        routes["route_short_name"] = routes.get("route_long_name", routes["route_id"])
    routes["route_label"] = (
        routes["route_short_name"].fillna(routes["route_id"]).astype(str).str.strip()
    )

    trips["route_id"] = trips["route_id"].astype(str).str.strip()
    trips["trip_id"] = trips["trip_id"].astype(str).str.strip()
    if "direction_id" not in trips.columns:
        trips["direction_id"] = np.nan
    else:
        trips["direction_id"] = pd.to_numeric(trips["direction_id"], errors="coerce")

    stop_times["trip_id"] = stop_times["trip_id"].astype(str).str.strip()
    stop_times["stop_id"] = stop_times["stop_id"].astype(str).str.strip()
    stop_times["stop_sequence"] = pd.to_numeric(stop_times["stop_sequence"], errors="coerce")
    stop_times = stop_times.dropna(subset=["stop_sequence"]).copy()
    stop_times["stop_sequence"] = stop_times["stop_sequence"].astype(int)

    for col_src, col_dst in (("arrival_time", "arr_sec"), ("departure_time", "dep_sec")):
        if col_src in stop_times.columns:
            uniq_t = stop_times[col_src].dropna().unique()
            t_map = {t: _parse_gtfs_seconds(t) for t in uniq_t}
            stop_times[col_dst] = stop_times[col_src].map(t_map)
        else:
            stop_times[col_dst] = None

    return {
        "stops": stops,
        "routes": routes,
        "trips": trips,
        "stop_times": stop_times,
    }


def load_gtfs_feed(folder: Path) -> Dict[str, pd.DataFrame]:
    """Read and minimally normalise the four core GTFS tables (cached by mtime)."""
    status = gtfs_status(folder)
    if not status["available"]:
        raise FileNotFoundError(status["error"] or "GTFS feed incomplete")
    return _load_gtfs_feed_cached(_gtfs_signature(folder), str(folder))


def _match_tickets_for_gtfs_route(
    tickets: pd.DataFrame,
    route_label: str,
    direction_str: str,
) -> pd.DataFrame:
    """Return ticket rows matching *route_label* and *direction_str* without cross-route leakage."""
    if tickets is None or len(tickets) == 0:
        return tickets
    r_upper = str(route_label).strip().upper()
    parsed = parse_route(r_upper)
    gtfs_base = f"{parsed['number']}{parsed['variant']}".strip().upper()
    gtfs_dir = parsed["direction"] or (direction_str if direction_str in ("up", "down") else "")

    t_routes = tickets["route"].astype(str).str.strip().str.upper()
    t_dirs = tickets["direction"].astype(str).str.strip().str.lower()

    if gtfs_dir in ("up", "down"):
        exact_mask = (t_routes == r_upper) & ((t_dirs == gtfs_dir) | (t_dirs == "unknown"))
        if exact_mask.any():
            return tickets.loc[exact_mask]
        if gtfs_base:
            alt_label = f"{gtfs_base}{gtfs_dir.upper()}"
            alt_mask = (t_routes == alt_label) & ((t_dirs == gtfs_dir) | (t_dirs == "unknown"))
            if alt_mask.any():
                return tickets.loc[alt_mask]
            # Base match using parsed ticket number+variant + direction
            t_base = (
                tickets["number"].astype(str).str.strip().str.upper()
                + tickets["variant"].astype(str).str.strip().str.upper()
            )
            base_mask = (t_base == gtfs_base) & (t_dirs == gtfs_dir)
            if base_mask.any():
                return tickets.loc[base_mask]
        return tickets.iloc[0:0]

    # Directionless GTFS route_id (direction_id missing & no UP/DOWN in label)
    exact_mask = t_routes == r_upper
    if exact_mask.any():
        return tickets.loc[exact_mask]
    return tickets.iloc[0:0]


def _aggregate_tickets_on_gtfs_sequence(
    route_tickets: pd.DataFrame,
    full_norms: List[str],
    o_idx: int,
    d_idx: int,
    active_days: int,
    veh_stats: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """Match ticket OD pairs onto *full_norms* and aggregate onto segments [o_idx..d_idx)."""
    n_seg_trip = d_idx - o_idx
    if route_tickets is None or len(route_tickets) == 0:
        return {
            "has_matched_load": False,
            "seg_loads": [np.nan] * n_seg_trip,
            "seg_tickets": [0] * n_seg_trip,
            "veh_seg_loads": [np.nan] * n_seg_trip,
            "route_tickets": 0,
            "matched_forward_tickets": 0,
            "unmatched_stop_tickets": 0,
            "ambiguous_stop_tickets": 0,
            "backward_tickets": 0,
            "gtfs_stop_match_pct": 0.0,
            "load_match_status": "No matching ticket records for this GTFS route/direction",
            "pax_per_observed_vehicle": None,
            "route_vehicle_coverage_pct": None,
            "distinct_vehicles": 0,
            "active_days": active_days,
        }

    positions: Dict[str, List[int]] = {}
    for idx_s, s_norm in enumerate(full_norms):
        positions.setdefault(s_norm, []).append(idx_s)

    seg_load_full = np.zeros(max(len(full_norms) - 1, 1), dtype=np.float64)
    seg_tkt_full = np.zeros(max(len(full_norms) - 1, 1), dtype=np.int32)
    veh_load_full = np.zeros(max(len(full_norms) - 1, 1), dtype=np.float64)

    n_fwd = 0
    n_back = 0
    n_unmatched = 0
    n_ambig = 0

    for row in route_tickets.itertuples(index=False):
        p_o = positions.get(row.start_norm)
        p_d = positions.get(row.end_norm)
        if not p_o or not p_d:
            n_unmatched += 1
            continue
        valid_pairs = [(i, j) for i in p_o for j in p_d if i < j]
        if len(valid_pairs) == 1:
            i, j = valid_pairs[0]
            pax = float(row.passenger_count)
            seg_load_full[i:j] += pax
            seg_tkt_full[i:j] += 1
            if bool(row.has_vehicle):
                veh_load_full[i:j] += pax
            n_fwd += 1
        elif len(valid_pairs) > 1:
            # Repeated stop creates ambiguous forward interpretation; do not guess
            n_ambig += 1
        else:
            n_back += 1

    total_t = len(route_tickets)
    eligible = max(total_t - n_back, 1)
    match_pct = round((n_fwd / eligible) * 100.0, 1) if total_t > 0 else 0.0

    if n_fwd == 0:
        return {
            "has_matched_load": False,
            "seg_loads": [np.nan] * n_seg_trip,
            "seg_tickets": [0] * n_seg_trip,
            "veh_seg_loads": [np.nan] * n_seg_trip,
            "route_tickets": int(total_t),
            "matched_forward_tickets": 0,
            "unmatched_stop_tickets": int(n_unmatched),
            "ambiguous_stop_tickets": int(n_ambig),
            "backward_tickets": int(n_back),
            "gtfs_stop_match_pct": 0.0,
            "load_match_status": (
                f"0/{total_t} tickets matched GTFS stop sequence "
                f"(unmatched stops: {n_unmatched}, ambiguous: {n_ambig}, reverse: {n_back})"
            ),
            "pax_per_observed_vehicle": None,
            "route_vehicle_coverage_pct": veh_stats["vehicle_coverage_pct"] if veh_stats else None,
            "distinct_vehicles": veh_stats["distinct_vehicles"] if veh_stats else 0,
            "active_days": active_days,
        }

    sl = seg_load_full[o_idx:d_idx].tolist()
    st = seg_tkt_full[o_idx:d_idx].tolist()
    vl = veh_load_full[o_idx:d_idx].tolist()

    pax_per_veh: Optional[float] = None
    if veh_stats and veh_stats["vehicle_metric_reliable"]:
        mean_v_load = float(np.mean(vl))
        pax_per_veh = round(mean_v_load / float(veh_stats["distinct_vehicles"]), 2)

    status_txt = f"Matched {n_fwd:,}/{eligible:,} eligible route tickets ({match_pct:.1f}%) onto GTFS stop sequence"
    if n_ambig > 0:
        status_txt += f"; {n_ambig:,} ambiguous repeated-stop ticket(s) excluded"

    return {
        "has_matched_load": True,
        "seg_loads": sl,
        "seg_tickets": st,
        "veh_seg_loads": vl,
        "route_tickets": int(total_t),
        "matched_forward_tickets": int(n_fwd),
        "unmatched_stop_tickets": int(n_unmatched),
        "ambiguous_stop_tickets": int(n_ambig),
        "backward_tickets": int(n_back),
        "gtfs_stop_match_pct": match_pct,
        "load_match_status": status_txt,
        "pax_per_observed_vehicle": pax_per_veh,
        "route_vehicle_coverage_pct": veh_stats["vehicle_coverage_pct"] if veh_stats else None,
        "distinct_vehicles": veh_stats["distinct_vehicles"] if veh_stats else 0,
        "active_days": active_days,
    }


def search_gtfs_direct_options(
    folder: Path,
    segments: pd.DataFrame,
    origin_norm: str,
    dest_norm: str,
    *,
    max_options: int = 5,
    tickets: Optional[pd.DataFrame] = None,
    rank_mode: str = "demand",
) -> Dict[str, Any]:
    """Find direct GTFS routes from *origin_norm* to *dest_norm* with schedule & demand."""
    feed = load_gtfs_feed(folder)
    stops = feed["stops"]
    routes = feed["routes"]
    trips = feed["trips"]
    st_df = feed["stop_times"]

    orig_ids = set(stops.loc[stops["stop_norm"] == origin_norm, "stop_id"])
    dest_ids = set(stops.loc[stops["stop_norm"] == dest_norm, "stop_id"])
    if not orig_ids or not dest_ids:
        return {
            "options": [],
            "mode": "gtfs",
            "message": "Origin or destination stop not found in GTFS stops.txt.",
        }

    st_orig = st_df[st_df["stop_id"].isin(orig_ids)][
        ["trip_id", "stop_sequence", "dep_sec", "arr_sec"]
    ].rename(columns={"stop_sequence": "seq_o", "dep_sec": "dep_o", "arr_sec": "arr_o"})
    st_dest = st_df[st_df["stop_id"].isin(dest_ids)][
        ["trip_id", "stop_sequence", "arr_sec", "dep_sec"]
    ].rename(columns={"stop_sequence": "seq_d", "arr_sec": "arr_d", "dep_sec": "dep_d"})

    pairs = st_orig.merge(st_dest, on="trip_id", how="inner")
    pairs = pairs[pairs["seq_o"] < pairs["seq_d"]].copy()
    if len(pairs) == 0:
        return {
            "options": [],
            "mode": "gtfs",
            "message": "No direct GTFS trip connects the selected stops in that direction.",
        }

    # Handle repeated stops within a single trip cleanly (keep shortest valid span per trip)
    pairs["span"] = pairs["seq_d"] - pairs["seq_o"]
    pairs = pairs.sort_values(["trip_id", "span", "seq_o"]).drop_duplicates(
        subset=["trip_id"], keep="first"
    )

    pairs["start_sec"] = pairs["dep_o"].fillna(pairs["arr_o"])
    pairs["end_sec"] = pairs["arr_d"].fillna(pairs["dep_d"])
    pairs["dur_min"] = (pairs["end_sec"] - pairs["start_sec"]) / 60.0
    pairs.loc[pairs["dur_min"] < 0, "dur_min"] = np.nan

    pairs = pairs.merge(trips[["trip_id", "route_id", "direction_id"]], on="trip_id", how="left")
    pairs = pairs.merge(routes[["route_id", "route_label"]], on="route_id", how="left")

    stop_name_map = dict(zip(stops["stop_id"], stops["stop_norm"]))
    has_coords = {"stop_lat", "stop_lon"}.issubset(stops.columns)
    coord_map: Dict[str, tuple[float, float]] = {}
    if has_coords:
        stops["stop_lat"] = pd.to_numeric(stops["stop_lat"], errors="coerce")
        stops["stop_lon"] = pd.to_numeric(stops["stop_lon"], errors="coerce")
        valid_c = stops.dropna(subset=["stop_lat", "stop_lon"])
        coord_map = {
            r.stop_id: (float(r.stop_lat), float(r.stop_lon))
            for r in valid_c.itertuples(index=False)
        }

    # Fallback lookup table if caller passed pre-aggregated segments without raw tickets
    seg_exact: Dict[tuple[str, str, str, str], tuple[float, int, float, float]] = {}
    seg_no_dir: Dict[tuple[str, str, str], tuple[float, int, float, float]] = {}
    seg_base_dir: Dict[tuple[str, str, str, str], tuple[float, int, float, float]] = {}
    if tickets is None and segments is not None and len(segments) > 0:
        segs_work = segments.copy()
        if "network_load_percentile" not in segs_work.columns:
            n_s = len(segs_work)
            if n_s > 1 and segs_work["segment_load"].nunique() > 1:
                segs_work["network_load_percentile"] = (
                    (segs_work["segment_load"].rank(method="min") - 1.0) / (n_s - 1.0)
                ).astype(float)
            else:
                segs_work["network_load_percentile"] = 0.0
        for row in segs_work.itertuples(index=False):
            r_up = str(row.route).strip().upper()
            r_dir = str(getattr(row, "direction", "")).strip().lower()
            vals = (
                float(row.segment_load),
                int(row.ticket_count),
                float(row.relative_load_index),
                float(row.network_load_percentile),
            )
            a_n, b_n = str(row.from_norm), str(row.to_norm)
            seg_exact.setdefault((r_up, r_dir, a_n, b_n), vals)
            seg_no_dir.setdefault((r_up, a_n, b_n), vals)
            parsed = parse_route(r_up)
            base_code = f"{parsed['number']}{parsed['variant']}".strip().upper()
            if base_code:
                seg_base_dir.setdefault((base_code, r_dir, a_n, b_n), vals)

    active_days = count_active_days(tickets) if tickets is not None else 0
    veh_stats_map = route_vehicle_reliability_stats(tickets) if tickets is not None else {}

    # Pre-compute route+direction scheduled trip counts in GTFS trips.txt
    rd_trip_counts = (
        trips.groupby(["route_id", "direction_id"], dropna=False)["trip_id"]
        .nunique()
        .to_dict()
    )

    options: List[Dict[str, Any]] = []
    for (route_id, route_label, dir_id), grp in pairs.groupby(
        ["route_id", "route_label", "direction_id"], dropna=False
    ):
        rep = grp.sort_values("dur_min", na_position="last").iloc[len(grp) // 2]
        trip_id = rep["trip_id"]
        full_trip_stops = st_df[st_df["trip_id"] == trip_id].sort_values("stop_sequence")
        full_stop_ids = list(full_trip_stops["stop_id"])
        full_seqs = list(full_trip_stops["stop_sequence"])
        full_norms = [stop_name_map.get(sid, sid) for sid in full_stop_ids]

        try:
            o_idx = full_seqs.index(int(rep["seq_o"]))
            d_idx = full_seqs.index(int(rep["seq_d"]))
        except ValueError:
            continue
        if o_idx >= d_idx:
            continue

        sub_stop_ids = full_stop_ids[o_idx : d_idx + 1]
        sub_norms = full_norms[o_idx : d_idx + 1]
        if len(sub_norms) < 2:
            continue

        direction_str = (
            "up" if dir_id == 0 else ("down" if dir_id == 1 else "gtfs")
        )
        gtfs_trips_od = int(grp["trip_id"].nunique())
        gtfs_trips_route = int(rd_trip_counts.get((route_id, dir_id), gtfs_trips_od))

        if tickets is not None:
            rt_tkt = _match_tickets_for_gtfs_route(tickets, str(route_label), direction_str)
            # Determine vehicle reliability for matched ticket subset
            v_stat = None
            if len(rt_tkt) > 0:
                first_r = str(rt_tkt["route"].iloc[0])
                first_d = str(rt_tkt["direction"].iloc[0])
                v_stat = veh_stats_map.get((first_r, first_d))
                if rt_tkt["route"].nunique() > 1 or rt_tkt["direction"].nunique() > 1:
                    n_t = len(rt_tkt)
                    v_t = int(rt_tkt["has_vehicle"].sum())
                    cov_pct = round((v_t / max(n_t, 1)) * 100.0, 1)
                    n_dv = int(rt_tkt.loc[rt_tkt["has_vehicle"], "vehicle_number"].nunique())
                    v_stat = {
                        "route_tickets": n_t,
                        "vehicle_tickets": v_t,
                        "vehicle_coverage_pct": cov_pct,
                        "distinct_vehicles": n_dv,
                        "vehicle_metric_reliable": (
                            cov_pct >= MIN_VEHICLE_COVERAGE_PCT
                            and n_dv >= MIN_DISTINCT_VEHICLES
                            and v_t >= MIN_VEHICLE_TICKETS
                        ),
                    }

            agg_res = _aggregate_tickets_on_gtfs_sequence(
                rt_tkt, full_norms, o_idx, d_idx, active_days, v_stat
            )
            has_matched = agg_res["has_matched_load"]
            seg_rows = []
            for idx_seg, (a, b) in enumerate(zip(sub_norms[:-1], sub_norms[1:])):
                lv = agg_res["seg_loads"][idx_seg]
                tc = agg_res["seg_tickets"][idx_seg]
                seg_rows.append({
                    "from_norm": a,
                    "to_norm": b,
                    "segment_load": lv,
                    "ticket_count": tc,
                    "relative_load_index": np.nan,
                    "network_load_percentile": np.nan,
                    "obs_status": (
                        "unmatched_route" if not has_matched
                        else ("observed" if tc > 0 else "zero_observed_in_window")
                    ),
                })
            seg_df = pd.DataFrame(seg_rows)
            if has_matched and len(seg_df) > 0:
                s_vals = seg_df["segment_load"].astype(float)
                s_min, s_max = float(s_vals.min()), float(s_vals.max())
                seg_df["relative_load_index"] = (s_vals - s_min) / max(s_max - s_min, 1.0)
                seg_load = float(s_vals.sum())
                seg_cnt = len(seg_df)
                mean_load = round(seg_load / max(seg_cnt, 1), 1)
                max_load = float(s_vals.max())
                rel = round(float(seg_df["relative_load_index"].mean()), 3)
                avg_daily = round(mean_load / active_days, 2) if active_days >= 1 else None
                pax_per_gtfs_trip = (
                    round(avg_daily / float(gtfs_trips_od), 3)
                    if (avg_daily is not None and gtfs_trips_od >= 1)
                    else None
                )
            else:
                seg_load = None
                seg_cnt = len(seg_df)
                mean_load = None
                max_load = None
                rel = None
                avg_daily = None
                pax_per_gtfs_trip = None

            match_status = agg_res["load_match_status"]
            gtfs_match_pct = agg_res["gtfs_stop_match_pct"]
            matched_cnt = seg_cnt if has_matched else 0
            r_tickets = agg_res["route_tickets"]
            r_veh_pct = agg_res["route_vehicle_coverage_pct"]
            pax_per_veh = agg_res["pax_per_observed_vehicle"]
            distinct_veh = agg_res["distinct_vehicles"]
        else:
            # Backward-compatible pre-aggregated segment fallback (when tickets is None)
            r_upper = str(route_label).strip().upper()
            parsed_gtfs = parse_route(r_upper)
            gtfs_base = f"{parsed_gtfs['number']}{parsed_gtfs['variant']}".strip().upper()
            gtfs_dir = parsed_gtfs["direction"] or (direction_str if direction_str in ("up", "down") else "")
            seg_rows = []
            matched_cnt = 0
            for a, b in zip(sub_norms[:-1], sub_norms[1:]):
                hit = None
                if gtfs_dir:
                    hit = seg_exact.get((r_upper, gtfs_dir, a, b))
                if hit is None:
                    hit = seg_no_dir.get((r_upper, a, b))
                if hit is None and gtfs_base and gtfs_dir:
                    hit = seg_base_dir.get((gtfs_base, gtfs_dir, a, b))
                if hit is None and gtfs_base and gtfs_dir:
                    hit = seg_no_dir.get((f"{gtfs_base}{gtfs_dir.upper()}", a, b))
                if hit is not None:
                    load_val, t_cnt, rli_val, net_val = hit
                    matched_cnt += 1
                    status_s = "observed"
                else:
                    load_val, t_cnt, rli_val, net_val = (np.nan, 0, np.nan, np.nan)
                    status_s = "unmatched_segment"
                seg_rows.append({
                    "from_norm": a,
                    "to_norm": b,
                    "segment_load": load_val,
                    "ticket_count": t_cnt,
                    "relative_load_index": rli_val,
                    "network_load_percentile": net_val,
                    "obs_status": status_s,
                })
            seg_df = pd.DataFrame(seg_rows)
            seg_cnt = len(seg_df)
            has_matched = matched_cnt > 0
            gtfs_match_pct = round((matched_cnt / max(seg_cnt, 1)) * 100.0, 1)
            if has_matched:
                valid_loads = seg_df["segment_load"].dropna()
                seg_load = float(valid_loads.sum())
                mean_load = round(seg_load / max(len(valid_loads), 1), 1)
                max_load = float(valid_loads.max())
                rel = round(float(seg_df["relative_load_index"].dropna().mean()), 3)
            else:
                seg_load = None
                mean_load = None
                max_load = None
                rel = None
            avg_daily = None
            pax_per_gtfs_trip = None
            pax_per_veh = None
            r_tickets = None
            r_veh_pct = None
            distinct_veh = 0
            if matched_cnt == seg_cnt:
                match_status = f"Matched {matched_cnt}/{seg_cnt} GTFS segments to ticket route"
            elif matched_cnt > 0:
                match_status = f"Partial match ({matched_cnt}/{seg_cnt} GTFS segments matched; unmatched shown as N/A)"
            else:
                match_status = "No matching ticket records for this GTFS route/direction"

        med_dur = grp["dur_min"].median()
        est_dur = round(float(med_dur), 1) if pd.notna(med_dur) else None
        stop_coords = None
        if coord_map and all(sid in coord_map for sid in sub_stop_ids):
            stop_coords = [
                {"stop": stop_name_map.get(sid, sid), "lat": coord_map[sid][0], "lon": coord_map[sid][1]}
                for sid in sub_stop_ids
            ]

        incomplete_coverage = bool(has_matched and gtfs_match_pct < 50.0)
        options.append({
            "route": str(route_label),
            "direction": direction_str,
            "origin": origin_norm,
            "destination": dest_norm,
            "segment_count": seg_cnt,
            "matched_segments": matched_cnt,
            "has_matched_load": has_matched,
            "incomplete_coverage": incomplete_coverage,
            "gtfs_stop_match_pct": gtfs_match_pct,
            "load_match_status": match_status,
            "historical_segment_load": seg_load,
            "mean_segment_load": mean_load,
            "max_segment_load": max_load,
            "avg_daily_segment_load": avg_daily,
            "active_days": active_days,
            "pax_per_observed_vehicle": pax_per_veh,
            "pax_per_gtfs_trip": pax_per_gtfs_trip,
            "gtfs_scheduled_trips": gtfs_trips_od,
            "gtfs_route_trips": gtfs_trips_route,
            "relative_load_index": rel,
            "network_load_percentile": None,  # calibrated below across matched segments / network
            "estimated_duration_min": est_dur,
            "duration_source": "GTFS stop_times.txt" if est_dur is not None else "Unavailable",
            "route_tickets": r_tickets,
            "route_vehicle_coverage_pct": r_veh_pct,
            "distinct_vehicles": distinct_veh,
            "stop_coords": stop_coords,
            "segments": seg_df,
        })

    if not options:
        return {
            "options": [],
            "mode": "gtfs",
            "message": "No direct GTFS route matched between the selected stops. LoadLens evaluates direct (0-transfer) routes only.",
        }

    # Calibrate network_load_percentile against active network segments (when available)
    ref_loads = (
        np.sort(segments["segment_load"].dropna().to_numpy(dtype=float))
        if (segments is not None and len(segments) > 0 and "segment_load" in segments.columns)
        else np.array([], dtype=float)
    )
    if len(ref_loads) == 0:
        matched_seg_vals = [
            float(v)
            for o in options if o["has_matched_load"]
            for v in o["segments"]["segment_load"].dropna().tolist()
        ]
        ref_loads = np.sort(np.asarray(matched_seg_vals, dtype=float))

    for o in options:
        if not o["has_matched_load"]:
            o["network_load_percentile"] = None
            continue
        seg_df = o["segments"]
        if tickets is not None:
            if len(ref_loads) > 1:
                pcts = [
                    float(np.searchsorted(ref_loads, float(v), side="left") / max(len(ref_loads) - 1, 1))
                    if pd.notna(v) else np.nan
                    for v in seg_df["segment_load"]
                ]
                seg_df["network_load_percentile"] = np.clip(pcts, 0.0, 1.0)
            else:
                seg_df["network_load_percentile"] = 0.5
        valid_pct = seg_df["network_load_percentile"].dropna()
        o["network_load_percentile"] = round(float(valid_pct.mean()), 3) if len(valid_pct) else None

    # Travel-time trade-off comparison against fastest GTFS option
    durs = [o["estimated_duration_min"] for o in options if o["estimated_duration_min"] is not None]
    min_dur = min(durs) if durs else None
    for o in options:
        if o["estimated_duration_min"] is not None and min_dur is not None:
            o["duration_delta_min"] = round(o["estimated_duration_min"] - min_dur, 1)
        else:
            o["duration_delta_min"] = None

    # Comparable demand metric & ranking (never let unmatched or <50% partial matches jump ahead)
    matched_opts = [o for o in options if o["has_matched_load"]]
    all_have_trip_norm = bool(matched_opts) and all(o["pax_per_gtfs_trip"] is not None for o in matched_opts)
    all_have_daily = bool(matched_opts) and all(o["avg_daily_segment_load"] is not None for o in matched_opts)

    def _demand_key(o: Dict[str, Any]) -> float:
        if not o["has_matched_load"]:
            return float("inf")
        if all_have_trip_norm and o["pax_per_gtfs_trip"] is not None:
            return float(o["pax_per_gtfs_trip"])
        if all_have_daily and o["avg_daily_segment_load"] is not None:
            return float(o["avg_daily_segment_load"])
        return float(o["mean_segment_load"]) if o["mean_segment_load"] is not None else float("inf")

    if rank_mode == "balanced" and len(matched_opts) >= 1 and durs:
        dem_vals = [_demand_key(o) for o in matched_opts]
        d_min, d_max = min(dem_vals), max(dem_vals)
        t_min, t_max = min(durs), max(durs)
        for o in options:
            if o["has_matched_load"]:
                nd = (_demand_key(o) - d_min) / max(d_max - d_min, 1e-9)
                nt = (
                    (o["estimated_duration_min"] - t_min) / max(t_max - t_min, 1e-9)
                    if o["estimated_duration_min"] is not None
                    else 0.5
                )
                o["_rank_score"] = round(0.65 * nd + 0.35 * nt, 4)
            else:
                o["_rank_score"] = float("inf")
    else:
        for o in options:
            o["_rank_score"] = _demand_key(o)

    options.sort(key=lambda o: (
        0 if (o["has_matched_load"] and not o["incomplete_coverage"]) else (1 if o["has_matched_load"] else 2),
        o["_rank_score"],
        o["estimated_duration_min"] if o["estimated_duration_min"] is not None else float("inf"),
        o["max_segment_load"] if o["max_segment_load"] is not None else float("inf"),
        o["segment_count"],
    ))
    for o in options:
        o.pop("_rank_score", None)

    return {
        "options": options[:max_options],
        "mode": "gtfs",
        "rank_mode": rank_mode,
        "demand_metric_used": (
            "pax_per_gtfs_trip" if all_have_trip_norm
            else ("avg_daily_segment_load" if all_have_daily else "mean_segment_load")
        ),
        "message": "",
    }
