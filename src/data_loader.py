"""Data loading, cleaning and normalization for LoadLens.

Reads the October Delhi e-ticketing parquet, applies cleaning, and writes
processed artefacts to ``data/cache`` so the Streamlit app starts instantly.
"""
from __future__ import annotations

import os
import re
import json
import hashlib
from pathlib import Path
from typing import Any, BinaryIO, Dict, Optional, Tuple, Union

import numpy as np
import pandas as pd

# ---- Paths ----------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
CACHE_DIR = DATA_DIR / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
SAMPLE_DIR = PROJECT_ROOT / "data_sample"
SAMPLE_CSV = SAMPLE_DIR / "tickets_sample.csv"

TICKETS_PARQUET = CACHE_DIR / "tickets_clean.parquet"
SEGMENTS_PARQUET = CACHE_DIR / "segment_loads.parquet"
TRIP_GRAPH_PARQUET = CACHE_DIR / "trip_graph.parquet"
DQ_REPORT_JSON = CACHE_DIR / "data_quality.json"
SEGMENT_META_JSON = CACHE_DIR / "segment_meta.json"


# ---- Stop-name normalization ---------------------------------------------
# Stop names in the e-ticketing export appear with inconsistent punctuation,
# abbreviations, and transcribed variants (e.g. "Sation" instead of "Station",
# "Bdr" instead of "Border", slashes joining alternate names). The normaliser
# applies a sequence of safe, reversible-friendly transforms.

_DIR_SLASH = re.compile(r"\s*/\s*")           # split "A / B" alternates
_DIR_SUFFIX = re.compile(r"\s*\([A-Za-z]+\)\s*$")  # "(T)", "(E)" terminal markers
_NON_ALNUM = re.compile(r"[^a-z0-9 ]+")
_MULTI_SPACE = re.compile(r"\s+")
_TYPO_MAP = {
    "sation": "station",
    "stn": "station",
    "stn.": "station",
    "rd": "road",
    "ave": "avenue",
    "bdr": "border",
    "ext": "extension",
    "extn": "extension",
    "mkt": "market",
    "appt": "apartment",
    "apt": "apartment",
    "appartment": "apartment",
    "appartments": "apartment",
    "distrist": "district",
    "pkt": "pocket",
    "sec": "sector",
    "blk": "block",
    "mg": "marg",
    "xing": "crossing",
    "hosp": "hospital",
    "opp": "opposite",
    "nr": "near",
}


def normalize_stop(name: str) -> str:
    """Normalise a raw stop name for matching purposes.

    The function does *not* try to auto-correct arbitrary misspellings — that
    is left to the optional fuzzy-matching step in :mod:`gtfs_matcher`.
    """
    if not isinstance(name, str):
        return ""
    s = name.strip()
    if not s:
        return ""

    # Some stops record alternates: "X / Y". Keep the LEFT-side anchor — the
    # boarding tag in tickets usually corresponds to the first mentioned name.
    s = _DIR_SLASH.split(s)[0]

    # Strip terminal letters in parens — direction markers, not part of name.
    s = _DIR_SUFFIX.sub("", s)

    s = s.lower()

    # Expand a small whitelist of abbreviations used by sign writers.
    tokens = []
    for tok in s.split():
        clean = _NON_ALNUM.sub("", tok).strip()
        if not clean:
            continue
        if clean in _TYPO_MAP:
            tokens.append(_TYPO_MAP[clean])
        else:
            tokens.append(clean)
    return _MULTI_SPACE.sub(" ", " ".join(tokens)).strip()


# ---- Direction detection --------------------------------------------------
_DIRECTION_MAP = {
    "UP": "up",
    "DOWN": "down",
    "U": "up",
    "D": "down",
    "NORTH": "up",
    "SOUTH": "down",
}

_NULL_STRINGS = {"", "nan", "none", "null", "na", "n/a", "<na>"}


def parse_route(route: str) -> Dict[str, str]:
    """Decompose a route label like ``'717AUP'`` into number + variant + direction.

    Routes in the dataset have the layout ``<number><variant><direction>``
    where ``<variant>`` is an optional trailing letter/tag used by DTC for
    sub-routes. Examples::

        717AUP     -> number=717, variant=A, direction=up
        729DOWN    -> number=729, variant='',  direction=down
        ML-72UP    -> number=ML-72, variant='', direction=up
    """
    out = {"number": "", "variant": "", "direction": ""}
    if not isinstance(route, str):
        return out
    s = route.strip().upper()
    if not s:
        return out
    # Match explicit direction suffixes (or single U/D immediately after digit/separator).
    m = re.search(r"(UP|DOWN|NORTH|SOUTH|(?<=[\d_-])[UD])$", s)
    if m:
        out["direction"] = _DIRECTION_MAP.get(m.group(1), "")
        s = s[: m.start()].rstrip("-_")
    # Variant is an optional trailing alpha tag on a numeric route prefix (e.g. 717A, 525STL).
    vm = re.match(r"^(\d+)([A-Z]+)$", s)
    if vm:
        out["number"] = vm.group(1)
        out["variant"] = vm.group(2)
    else:
        out["number"] = s
    return out


# ---- Loader ---------------------------------------------------------------

def resolve_source(source: Optional[Union[str, Path]] = None) -> Tuple[Path, str]:
    """Locate the best available ticket dataset without hardcoding machine paths.

    Priority:
      1. Explicit *source* path passed by caller.
      2. ``LOADLENS_TICKETS`` environment variable.
      3. First ``.parquet``/``.pq``/``.csv`` file placed in ``data/raw/``.
      4. Bundled ``data_sample/tickets_sample.csv`` fallback.
    """
    if source is not None:
        p = Path(source)
        if not p.exists():
            raise FileNotFoundError(f"Ticket source not found: {p}")
        return p, "custom"

    env_src = os.environ.get("LOADLENS_TICKETS", "").strip()
    if env_src:
        p = Path(env_src)
        if not p.exists():
            raise FileNotFoundError(
                f"LOADLENS_TICKETS points to missing file: {p}"
            )
        return p, "env"

    if RAW_DIR.exists():
        for ext in ("*.parquet", "*.pq", "*.csv"):
            matches = sorted(RAW_DIR.glob(ext))
            if matches:
                return matches[0], "raw"

    if SAMPLE_CSV.exists():
        return SAMPLE_CSV, "sample"

    raise FileNotFoundError(
        "No ticket dataset found. Supply a CSV/Parquet via LOADLENS_TICKETS, "
        "place it in data/raw/, or ensure data_sample/tickets_sample.csv exists."
    )


def load_raw(source: Optional[Union[str, Path]] = None) -> pd.DataFrame:
    """Read the raw e-ticketing file. Supports ``.parquet`` and ``.csv``."""
    src_path, _ = resolve_source(source)
    suf = src_path.suffix.lower()
    if suf in (".parquet", ".pq"):
        return pd.read_parquet(src_path)
    if suf == ".csv":
        return pd.read_csv(src_path, low_memory=False)
    raise ValueError(f"Unsupported source extension: {src_path.suffix}")


def load_raw_buffer(file_obj: BinaryIO, filename: str) -> pd.DataFrame:
    """Read an uploaded ticket CSV or Parquet buffer."""
    suf = Path(filename).suffix.lower()
    if suf in (".parquet", ".pq"):
        return pd.read_parquet(file_obj)
    if suf == ".csv":
        return pd.read_csv(file_obj, low_memory=False)
    raise ValueError(f"Unsupported uploaded file extension: {suf}. Use .csv or .parquet.")


def _clean_text_col(series: pd.Series) -> pd.Series:
    """Strip text values while preserving missing/null markers as ``pd.NA``."""
    out = series.where(series.notna(), other=pd.NA)
    mask = out.notna()
    cleaned = out.loc[mask].astype(str).str.strip()
    cleaned = cleaned.where(~cleaned.str.lower().isin(_NULL_STRINGS), other=pd.NA)
    out = out.astype("object")
    out.loc[mask] = cleaned
    return out


def _parse_timestamps_ist(series: pd.Series) -> pd.Series:
    """Parse timestamps and normalise tz-aware values to IST (Asia/Kolkata) naive."""
    if pd.api.types.is_datetime64_any_dtype(series):
        parsed = series
    else:
        has_tz = series.dropna().astype(str).str.contains(
            r"(?:Z|[+-]\d{2}:?\d{2})$", regex=True
        ).any()
        if has_tz:
            parsed = pd.to_datetime(series, format="mixed", errors="coerce", utc=True)
        else:
            parsed = pd.to_datetime(series, format="mixed", errors="coerce")

    tz = getattr(parsed.dt, "tz", None)
    if tz is not None:
        parsed = parsed.dt.tz_convert("Asia/Kolkata").dt.tz_localize(None)
    return parsed


def clean_with_report(
    df: pd.DataFrame,
    source_signature: Optional[str] = None,
    write_dq: bool = True,
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """Apply cleaning and normalisation, returning ``(cleaned_df, dq_report)``."""
    df = df.copy()
    n_raw = len(df)

    # Required columns
    required = [
        "passenger_count", "route", "start_stop_name", "end_stop_name",
        "created_at",
    ]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    # Coerce types safely without turning NaN into literal "nan"
    df["passenger_count"] = pd.to_numeric(df["passenger_count"], errors="coerce")
    if "amount" in df.columns:
        df["amount"] = pd.to_numeric(df["amount"], errors="coerce")
    else:
        df["amount"] = np.nan
    if "ticket_type_id" in df.columns:
        df["ticket_type_id"] = pd.to_numeric(df["ticket_type_id"], errors="coerce")
    else:
        df["ticket_type_id"] = np.nan
    if "vehicle_number" not in df.columns:
        df["vehicle_number"] = pd.NA

    df["route"] = _clean_text_col(df["route"])
    df["start_stop_name"] = _clean_text_col(df["start_stop_name"])
    df["end_stop_name"] = _clean_text_col(df["end_stop_name"])
    df["created_at"] = _parse_timestamps_ist(df["created_at"])

    # Drop rows with critical nulls before string normalization
    pre_drop = len(df)
    df = df.dropna(subset=[
        "passenger_count", "route", "start_stop_name", "end_stop_name", "created_at",
    ])
    dropped_missing_core = pre_drop - len(df)

    # Normalise stop names via unique-value lookup (avoids repeated per-row regex work)
    uniq_stops = pd.unique(
        pd.concat([df["start_stop_name"], df["end_stop_name"]], ignore_index=True).dropna()
    )
    stop_norm_map = {s: normalize_stop(s) for s in uniq_stops}
    df["start_norm"] = df["start_stop_name"].map(stop_norm_map).fillna("")
    df["end_norm"] = df["end_stop_name"].map(stop_norm_map).fillna("")

    # Drop rows whose stop names normalise to empty (e.g. punctuation-only strings)
    pre_drop = len(df)
    df = df[(df["start_norm"] != "") & (df["end_norm"] != "")]
    dropped_invalid_stops = pre_drop - len(df)

    # Parse unique route labels once and map back (orders of magnitude faster than apply(pd.Series))
    existing_dir = df["direction"].astype(str).str.strip().str.lower() if "direction" in df.columns else None
    if len(df) == 0:
        for col in ("number", "variant", "direction"):
            df[col] = pd.Series(dtype="object")
    else:
        uniq_routes = df["route"].dropna().unique()
        parsed_cache = {r: parse_route(r) for r in uniq_routes}
        num_map = {r: p["number"] for r, p in parsed_cache.items()}
        var_map = {r: p["variant"] for r, p in parsed_cache.items()}
        dir_map = {r: p["direction"] for r, p in parsed_cache.items()}
        df["number"] = df["route"].map(num_map).fillna("")
        df["variant"] = df["route"].map(var_map).fillna("")
        df["direction"] = df["route"].map(dir_map).fillna("")
        if existing_dir is not None:
            keep_existing = (df["direction"] == "") & existing_dir.isin(["up", "down"])
            df.loc[keep_existing, "direction"] = existing_dir.loc[keep_existing]
        df["direction"] = df["direction"].replace("", "unknown")

    # Derived local IST calendar fields (compact integer dtypes for large datasets)
    df["ticket_date"] = df["created_at"].dt.date
    df["ticket_hour"] = df["created_at"].dt.hour.astype(np.int8)
    df["ticket_dow"] = df["created_at"].dt.dayofweek.astype(np.int8)  # 0=Mon
    df["ticket_is_weekend"] = df["ticket_dow"].isin([5, 6])

    # Cleanliness flags for vehicle_number (never impute missing vehicles)
    veh_clean = df["vehicle_number"].astype(str).str.strip()
    df["has_vehicle"] = df["vehicle_number"].notna() & (~veh_clean.str.lower().isin(_NULL_STRINGS))

    # Filter non-positive passenger counts
    pre_drop = len(df)
    n_neg = int((df["passenger_count"] <= 0).sum())
    df = df[df["passenger_count"] > 0]
    dropped_nonpositive = pre_drop - len(df)

    # Filter rows where start == end (no segment)
    pre_drop = len(df)
    df = df[df["start_norm"] != df["end_norm"]]
    dropped_same_stop = pre_drop - len(df)

    df = df.reset_index(drop=True)

    has_rows = len(df) > 0
    missing_v_count = int((~df["has_vehicle"]).sum()) if has_rows else 0
    missing_v_pct = float((~df["has_vehicle"]).mean() * 100) if has_rows else 0.0
    active_days = int(df["ticket_date"].nunique()) if has_rows else 0
    pax_min = df["passenger_count"].min() if has_rows else 0
    pax_max = df["passenger_count"].max() if has_rows else 0

    dq: Dict[str, Any] = {
        "source_path": str(source_signature or "in-memory"),
        "raw_rows": int(n_raw),
        "kept_rows": int(len(df)),
        "dropped_missing_core": int(dropped_missing_core),
        "dropped_invalid_stop_names": int(dropped_invalid_stops),
        "dropped_nonpositive_passenger_count": int(dropped_nonpositive),
        "dropped_nonpositive_passenger_count_observed": int(n_neg),
        "dropped_same_origin_and_destination": int(dropped_same_stop),
        "missing_vehicle_number": missing_v_count,
        "missing_vehicle_number_count": missing_v_count,
        "missing_vehicle_number_pct": missing_v_pct,
        "unique_routes": int(df["route"].nunique()) if has_rows else 0,
        "unique_normalized_starts": int(df["start_norm"].nunique()) if has_rows else 0,
        "unique_normalized_ends": int(df["end_norm"].nunique()) if has_rows else 0,
        "date_min": str(df["ticket_date"].min()) if has_rows else "—",
        "date_max": str(df["ticket_date"].max()) if has_rows else "—",
        "active_days": active_days,
        "distinct_vehicles_with_id": int(df.loc[df["has_vehicle"], "vehicle_number"].nunique()) if has_rows else 0,
        "passenger_count_min": int(pax_min) if has_rows and float(pax_min).is_integer() else (float(pax_min) if has_rows else 0),
        "passenger_count_max": int(pax_max) if has_rows and float(pax_max).is_integer() else (float(pax_max) if has_rows else 0),
        "passenger_count_mean": float(df["passenger_count"].mean()) if has_rows else 0.0,
    }
    if write_dq:
        DQ_REPORT_JSON.write_text(json.dumps(dq, indent=2, default=str), encoding="utf-8")
    return df, dq


def clean(
    df: pd.DataFrame,
    source_signature: Optional[str] = None,
    write_dq: bool = True,
) -> pd.DataFrame:
    """Apply cleaning and normalisation to the ticket frame."""
    cleaned, _ = clean_with_report(df, source_signature=source_signature, write_dq=write_dq)
    return cleaned


_ESSENTIAL_CLEAN_COLS = [
    "passenger_count", "route", "start_stop_name", "end_stop_name", "created_at",
    "vehicle_number", "amount", "ticket_type_id",
    "start_norm", "end_norm", "number", "variant", "direction",
    "ticket_date", "ticket_hour", "ticket_dow", "ticket_is_weekend", "has_vehicle",
]


def load_clean_csv_chunked(
    csv_path: Union[str, Path],
    *,
    chunksize: int = 250_000,
    write_dq: bool = True,
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """Ingest and clean a large CSV in bounded memory chunks.

    Produces the same cleaned schema and ``dq_report`` accounting as
    :func:`clean_with_report` while keeping peak RAM well below single-shot
    290 MB+ CSV loading.
    """
    p = Path(csv_path)
    chunks: list[pd.DataFrame] = []
    agg_dq: Dict[str, Any] = {
        "source_path": str(p),
        "raw_rows": 0,
        "kept_rows": 0,
        "dropped_missing_core": 0,
        "dropped_invalid_stop_names": 0,
        "dropped_nonpositive_passenger_count": 0,
        "dropped_nonpositive_passenger_count_observed": 0,
        "dropped_same_origin_and_destination": 0,
        "missing_vehicle_number": 0,
    }
    for chunk in pd.read_csv(p, chunksize=chunksize, low_memory=False):
        cln, cdq = clean_with_report(chunk, source_signature=str(p), write_dq=False)
        for k in (
            "raw_rows", "kept_rows", "dropped_missing_core",
            "dropped_invalid_stop_names", "dropped_nonpositive_passenger_count",
            "dropped_nonpositive_passenger_count_observed",
            "dropped_same_origin_and_destination", "missing_vehicle_number",
        ):
            agg_dq[k] += int(cdq[k])
        keep_cols = [c for c in _ESSENTIAL_CLEAN_COLS if c in cln.columns]
        chunks.append(cln[keep_cols])

    if chunks:
        df = pd.concat(chunks, ignore_index=True)
    else:
        df = pd.DataFrame(columns=_ESSENTIAL_CLEAN_COLS)

    has_rows = len(df) > 0
    mv_cnt = int(agg_dq["missing_vehicle_number"])
    pax_min = df["passenger_count"].min() if has_rows else 0
    pax_max = df["passenger_count"].max() if has_rows else 0
    agg_dq.update({
        "missing_vehicle_number_count": mv_cnt,
        "missing_vehicle_number_pct": float((~df["has_vehicle"]).mean() * 100) if has_rows else 0.0,
        "unique_routes": int(df["route"].nunique()) if has_rows else 0,
        "unique_normalized_starts": int(df["start_norm"].nunique()) if has_rows else 0,
        "unique_normalized_ends": int(df["end_norm"].nunique()) if has_rows else 0,
        "date_min": str(df["ticket_date"].min()) if has_rows else "—",
        "date_max": str(df["ticket_date"].max()) if has_rows else "—",
        "active_days": int(df["ticket_date"].nunique()) if has_rows else 0,
        "distinct_vehicles_with_id": int(df.loc[df["has_vehicle"], "vehicle_number"].nunique()) if has_rows else 0,
        "passenger_count_min": int(pax_min) if has_rows and float(pax_min).is_integer() else (float(pax_min) if has_rows else 0),
        "passenger_count_max": int(pax_max) if has_rows and float(pax_max).is_integer() else (float(pax_max) if has_rows else 0),
        "passenger_count_mean": float(df["passenger_count"].mean()) if has_rows else 0.0,
    })
    if write_dq:
        DQ_REPORT_JSON.write_text(json.dumps(agg_dq, indent=2, default=str), encoding="utf-8")
    return df, agg_dq


def load_clean(force: bool = False, source: Optional[Union[str, Path]] = None) -> pd.DataFrame:
    """Return the cleaned ticket frame, building the cache on first use."""
    if (not force) and source is None and TICKETS_PARQUET.exists():
        return pd.read_parquet(TICKETS_PARQUET)
    src_path, src_kind = resolve_source(source)
    if src_path.suffix.lower() == ".csv" and src_path.stat().st_size > 25 * 1024 * 1024:
        df, _ = load_clean_csv_chunked(src_path, write_dq=True)
    else:
        raw = load_raw(src_path)
        df, _ = clean_with_report(raw, source_signature=str(src_path), write_dq=True)
    if src_kind != "sample" or force:
        df.to_parquet(TICKETS_PARQUET, index=False)
    return df
