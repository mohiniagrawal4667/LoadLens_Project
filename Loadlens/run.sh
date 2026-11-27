#!/usr/bin/env bash
# One-command launcher for Linux/macOS users.
set -e
cd "$(dirname "$0")"
if [ ! -f data/cache/tickets_clean.parquet ] && [ -n "${LOADLENS_TICKETS:-}" ]; then
    echo "First-run: building processed caches from LOADLENS_TICKETS..."
    python3 scripts/build_processed.py
fi
echo "Starting LoadLens Streamlit dashboard..."
python3 -m streamlit run app.py
