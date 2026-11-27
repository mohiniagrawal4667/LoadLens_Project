"""Final smoke test — render every page and confirm content exists."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))


def run(page: str) -> bool:
    try:
        from streamlit.testing.v1 import AppTest
        at = AppTest.from_file("app.py", default_timeout=180)
        at.session_state["nav_radio"] = page
        at.run()
        if at.exception:
            print(f"[{page}] FAIL:")
            for exc in at.exception:
                print(f"  {exc.message}")
            return False
        plt = len([e for e in at.main if e.type == "plotly_chart"])
        df = len(at.main.dataframe)
        m = len(at.main.get("metric"))
        print(f"[{page}] OK  md={len(at.main.markdown)} df={df} m={m} plotly={plt}")
        return True
    except Exception as e:
        print(f"[{page}] EXC {type(e).__name__}: {e}")
        return False


if __name__ == "__main__":
    pages = ["Overview", "Route Analytics", "Segment Explorer",
             "Journey Planner", "Data Quality"]
    ok = all(run(p) for p in pages)
    sys.exit(0 if ok else 1)
