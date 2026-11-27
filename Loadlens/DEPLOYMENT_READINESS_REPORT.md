# LoadLens — Deployment Readiness Report

> **Assessment Date:** 2026-11-27  
> **Target Application:** `app.py` (Streamlit `1.54.0` single-process web server, port `8501`)

---

## 1. Security Review Findings & Hardening Applied

| Security Area | Status | Details & Evidence |
|---|---|---|
| **Hardcoded credentials / secrets** | **PASS** | Zero API keys, tokens, passwords, or private host paths in source (`LOADLENS_TICKETS` is the sole optional env var, documented in `.env.example`). |
| **GTFS ZIP extraction (`src/gtfs.py:extract_gtfs_zip`)** | **HARDENED** | Enforces ZIP integrity checks, rejects `..` traversal and null bytes, rejects Unix symlink members (`S_IFLNK`), caps archive member count (`<= 64`), and performs streaming reads capped at `150 MB` per `.txt` file / `250 MB` total uncompressed payload (immune to spoofed ZIP header sizes). Verified by `test_regression.py` Case 13. |
| **GTFS upload cache validation (`app.py:218`)** | **HARDENED** | Checks full `gtfs_status(target)["available"]` rather than `(target / "stops.txt").exists()`, removing partial/failed extraction directories cleanly. |
| **HTML/XSS escaping (`app.py`, `app_pages.py`, `src/ui_theme.py`)** | **PASS** | Dataset labels, route names, stop names, and status text rendered inside `unsafe_allow_html=True` pass through `html.escape` (`_esc` / `html_escape`). |
| **Raw data & secrets exposure** | **PASS** | `.gitignore` and `.dockerignore` exclude `.env`, `data/raw/`, `data/cache/`, `data/gtfs/`, `data/gtfs_uploaded/`, `*.parquet`, `*.zip`, and raw `*.csv` (except `data_sample/tickets_sample.csv`). |
| **Unused packaging artifacts** | **CLEANED** | Removed unused empty `package-lock.json`. |
| **Debug / telemetry settings** | **PASS** | `.streamlit/config.toml` sets `gatherUsageStats = false`, `maxUploadSize = 512`, and dark theme tokens. |
| **Dependency vulnerability scan** | **NOT RUN** | `pip-audit` / `safety` are not installed in this environment; packages are pinned to exact versions in `requirements.txt`. |

### Public Exposure Recommendations (If Deployed Openly)
1. **Rate-limiting / Upload Size Cap:** `.streamlit/config.toml` allows `maxUploadSize = 512` MB to accommodate hackathon datasets. For an unauthenticated public demo, lower `maxUploadSize` (e.g. `50`–`100` MB) or enforce upload/rate limits at a reverse proxy (Nginx / Cloudflare / Cloud Run).
2. **Ephemeral `data/gtfs_uploaded/` cleanup:** Public multi-user deployments should mount ephemeral storage or periodically prune `data/gtfs_uploaded/` on container restart.

---

## 2. Deployment Configuration Added & Verified

* **`.env.example`**: Documents optional `LOADLENS_TICKETS` override.
* **`Dockerfile`**: Based on `python:3.12-slim`, installs `requirements.txt`, exposes `8501`, configures `HEALTHCHECK` against `/_stcore/health`, and launches `streamlit run app.py --server.port=8501 --server.address=0.0.0.0 --server.headless=true`. *(Note: Docker image build was not executed here because Docker daemon availability was not used/tested; local Streamlit startup and `/_stcore/health` were verified.)*
* **`.dockerignore`**: Excludes `.git/`, caches, raw data, backups, and virtualenvs from the build context.
* **Local Startup Verification:** Running `streamlit run app.py --server.port 8501 --server.headless true` starts cleanly and serves all 5 pages in Chromium (`http://localhost:8501`).

---

## 3. Platform Evaluation & Recommendation

| Platform | Fit for Sample (`25k` rows) | Fit for Full Dataset (`~2.56M` rows) | Technical Rationale |
|---|---|---|---|
| **Container Host with $\ge 2\text{ GB}$ RAM** (Render Standard, Fly.io `2GB`, Railway, Google Cloud Run) | **Excellent** | **Recommended** | Supports prebuilt `data/cache/*.parquet` (or `LOADLENS_TICKETS` + `build_processed.py` in build/init), persistent/mounted volume option, and enough RAM for `2.56M` ticket analytics + Plotly rendering. |
| **Streamlit Community Cloud (Free Tier, ~1 GB RAM)** | **Good** | **Not Suitable** | Works cleanly with bundled `25,000`-row `tickets_sample.csv` and small GTFS `.zip` uploads; `1 GB` RAM ceiling will likely OOM on `2.56M` ticket rows + in-browser CSV uploads. |

**Recommendation:** Deploy using the provided [Dockerfile](Dockerfile) on a **2 GB+ RAM container platform** (Cloud Run / Render / Fly.io) with prebuilt Parquet caches (`scripts/build_processed.py`) if serving the full 2.56M-row dataset, or use Streamlit Community Cloud strictly for the bundled 25k-row sample showcase. *(No external cloud deployment was executed in this session.)*
