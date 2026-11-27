@echo off
REM One-command launcher for Windows users.
SETLOCAL
IF NOT EXIST data\cache\tickets_clean.parquet (
    IF DEFINED LOADLENS_TICKETS (
        echo First-run: building processed caches from LOADLENS_TICKETS...
        python scripts\build_processed.py
        IF ERRORLEVEL 1 (
            echo Cache build failed. Check the error above.
            EXIT /B 1
        )
    )
)
echo Starting LoadLens Streamlit dashboard...
streamlit run app.py
ENDLOCAL
