"""Centralised cyberpunk urban-intelligence theme & HTML/SVG components for LoadLens."""
from __future__ import annotations

import html
import math
from typing import Iterable, Optional, Tuple

# ---- Cyberpunk Urban Intelligence Palette ---------------------------------
BG_VOID        = "#070A12"
BG_SURFACE     = "#0D1421"
BG_ELEVATED    = "#121D2C"
BG_GLASS       = "rgba(13, 20, 33, 0.78)"
BG_MUTED       = "#111A29"

CYAN_ELECTRIC  = "#42E8E0"
CYAN_SOFT      = "rgba(66, 232, 224, 0.14)"
VIOLET_NEON    = "#9B7CFF"
VIOLET_SOFT    = "rgba(155, 124, 255, 0.15)"
MAGENTA_NEON   = "#EC4DAB"
AMBER_SIGNAL   = "#F5B84B"
AMBER_SOFT     = "rgba(245, 184, 75, 0.15)"
CORAL_ALERT    = "#F26B6B"
CORAL_SOFT     = "rgba(242, 107, 107, 0.16)"

TEXT_PRIMARY   = "#F2F5FA"
TEXT_SECONDARY = "#8998AD"
TEXT_MUTED     = "#607087"

BORDER_SUBTLE  = "rgba(66, 232, 224, 0.14)"
BORDER_HAIR    = "rgba(137, 152, 173, 0.18)"
BORDER_ACTIVE  = "rgba(66, 232, 224, 0.48)"

# Backward-compatible colour aliases used by app_pages.py imports
NAVY_DEEP     = BG_ELEVATED
NAVY_MID      = "#1A2940"
TEAL_PRIMARY  = CYAN_ELECTRIC
TEAL_DARK     = CYAN_ELECTRIC
TEAL_SOFT     = CYAN_SOFT
BG_CANVAS     = BG_VOID
ACCENT_TEAL   = CYAN_ELECTRIC
ACCENT_GREEN  = "#2EE59D"
ACCENT_AMBER  = AMBER_SIGNAL
ACCENT_RED    = CORAL_ALERT
ACCENT_BLUE   = VIOLET_NEON
BG_DEEP       = BG_VOID
BG_PANEL      = BG_SURFACE
BG_CARD       = BG_ELEVATED
BORDER        = BORDER_SUBTLE

LOAD_SCALE = [
    [0.0,  "#0F2233"],
    [0.25, "#196678"],
    [0.5,  "#42E8E0"],
    [0.72, "#9B7CFF"],
    [0.88, "#F5B84B"],
    [1.0,  "#F26B6B"],
]

ROUTES_SCALE = [
    "#42E8E0", "#9B7CFF", "#F5B84B", "#EC4DAB",
    "#2EE59D", "#F26B6B", "#60A5FA", "#C084FC",
]


def demand_tier(rel: Optional[float]) -> Tuple[str, str, str]:
    """Return (label, accent color, translucent pill bg) for a 0-1 relative load."""
    if rel is None or (isinstance(rel, float) and math.isnan(rel)):
        return "Insufficient data", TEXT_SECONDARY, "rgba(137, 152, 173, 0.12)"
    if rel < 0.40:
        return "Low demand", CYAN_ELECTRIC, CYAN_SOFT
    if rel < 0.75:
        return "Moderate demand", AMBER_SIGNAL, AMBER_SOFT
    return "High demand", CORAL_ALERT, CORAL_SOFT


def inject_css() -> None:
    """Inject cyberpunk dark urban-intelligence CSS, grid/noise layers, and animations."""
    import streamlit as st

    css_body = f"""@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;600;700&family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap');
:root {{
    --ll-void: {BG_VOID};
    --ll-surface: {BG_SURFACE};
    --ll-elevated: {BG_ELEVATED};
    --ll-cyan: {CYAN_ELECTRIC};
    --ll-violet: {VIOLET_NEON};
    --ll-magenta: {MAGENTA_NEON};
    --ll-amber: {AMBER_SIGNAL};
    --ll-coral: {CORAL_ALERT};
    --ll-text: {TEXT_PRIMARY};
    --ll-text-sec: {TEXT_SECONDARY};
    --ll-muted: {TEXT_MUTED};
    --ll-border: {BORDER_SUBTLE};
    --ll-hair: {BORDER_HAIR};
}}

@keyframes ll-fade-up {{
    from {{ opacity: 0; transform: translateY(8px); }}
    to   {{ opacity: 1; transform: translateY(0); }}
}}
@keyframes ll-scan {{
    0%   {{ transform: translateX(-100%); opacity: 0; }}
    20%  {{ opacity: 0.75; }}
    80%  {{ opacity: 0.75; }}
    100% {{ transform: translateX(220%); opacity: 0; }}
}}
@keyframes ll-pulse-node {{
    0%, 100% {{ box-shadow: 0 0 0 0 rgba(66, 232, 224, 0.45); }}
    50%      {{ box-shadow: 0 0 0 7px rgba(66, 232, 224, 0.0); }}
}}
@keyframes ll-trace-dash {{
    to {{ stroke-dashoffset: -28; }}
}}
@keyframes ll-node-in {{
    from {{ opacity: 0; transform: scale(0.75); }}
    to   {{ opacity: 1; transform: scale(1); }}
}}

/* Global Dark City Grid Canvas + Subtle Noise */
html, body, .stApp {{
    background-color: var(--ll-void) !important;
    background-image:
        radial-gradient(ellipse 80% 55% at 18% -5%, rgba(66, 232, 224, 0.09), transparent 60%),
        radial-gradient(ellipse 70% 50% at 88% 8%, rgba(155, 124, 255, 0.08), transparent 60%),
        linear-gradient(rgba(66, 232, 224, 0.03) 1px, transparent 1px),
        linear-gradient(90deg, rgba(66, 232, 224, 0.03) 1px, transparent 1px) !important;
    background-size: 100% 100%, 100% 100%, 44px 44px, 44px 44px !important;
    background-attachment: fixed !important;
    color: var(--ll-text) !important;
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
    font-size: 15px;
}}

h1, h2, h3, h4 {{
    font-family: 'Space Grotesk', 'Inter', sans-serif !important;
    color: var(--ll-text) !important;
    font-weight: 700 !important;
    letter-spacing: -0.02em;
}}
p, li, span, label, td, th {{
    color: var(--ll-text);
}}
code {{
    font-family: 'JetBrains Mono', ui-monospace, monospace !important;
    color: {CYAN_ELECTRIC} !important;
    background: rgba(66, 232, 224, 0.08) !important;
    padding: 0.12rem 0.36rem;
    border-radius: 5px;
    font-size: 0.86em;
}}
.block-container {{
    padding-top: 1.25rem !important;
    padding-bottom: 3rem !important;
    max-width: 1400px;
    animation: ll-fade-up 0.35s cubic-bezier(0.16, 1, 0.3, 1);
}}

#MainMenu {{ visibility: hidden; }}
footer {{ visibility: hidden; }}
header[data-testid="stHeader"] {{
    background: transparent !important;
}}

/* Left Investigation Rail (Sidebar) */
section[data-testid="stSidebar"] {{
    background: linear-gradient(180deg, #090E19 0%, #070A12 100%) !important;
    border-right: 1px solid rgba(66, 232, 224, 0.16) !important;
}}
section[data-testid="stSidebar"] > div {{
    padding-top: 1.15rem;
}}
section[data-testid="stSidebar"] div[role="radiogroup"] {{
    gap: 0.32rem;
}}
section[data-testid="stSidebar"] div[role="radiogroup"] label {{
    background: rgba(18, 29, 44, 0.35);
    border: 1px solid rgba(137, 152, 173, 0.12);
    border-left: 3px solid transparent;
    border-radius: 8px;
    padding: 0.58rem 0.82rem !important;
    margin: 0 !important;
    transition: all 160ms ease;
    cursor: pointer;
}}
section[data-testid="stSidebar"] div[role="radiogroup"] label:hover {{
    background: rgba(66, 232, 224, 0.07);
    border-color: rgba(66, 232, 224, 0.25);
    transform: translateX(2px);
}}
section[data-testid="stSidebar"] div[role="radiogroup"] label:has(input:checked) {{
    background: linear-gradient(90deg, rgba(66, 232, 224, 0.16) 0%, rgba(18, 29, 44, 0.85) 100%) !important;
    border-color: rgba(66, 232, 224, 0.36) !important;
    border-left: 3px solid {CYAN_ELECTRIC} !important;
    box-shadow: 0 0 18px rgba(66, 232, 224, 0.14);
}}
section[data-testid="stSidebar"] div[role="radiogroup"] label p,
section[data-testid="stSidebar"] div[role="radiogroup"] label span {{
    font-family: 'JetBrains Mono', ui-monospace, monospace !important;
    font-size: 0.79rem !important;
    letter-spacing: 0.04em;
    color: {TEXT_SECONDARY} !important;
}}
section[data-testid="stSidebar"] div[role="radiogroup"] label:has(input:checked) p,
section[data-testid="stSidebar"] div[role="radiogroup"] label:has(input:checked) span {{
    color: {CYAN_ELECTRIC} !important;
    font-weight: 600 !important;
}}
section[data-testid="stSidebar"] div[role="radiogroup"] label > div:first-child {{
    display: none;
}}

/* Inputs, Selectboxes, Sliders */
.stTextInput input,
.stNumberInput input,
.stSelectbox div[data-baseweb="select"] > div,
.stMultiSelect div[data-baseweb="select"] > div {{
    background-color: {BG_ELEVATED} !important;
    color: {TEXT_PRIMARY} !important;
    border: 1px solid {BORDER_HAIR} !important;
    border-radius: 9px !important;
    min-height: 42px;
    transition: border-color 150ms ease, box-shadow 150ms ease;
}}
.stTextInput input::placeholder {{
    color: {TEXT_MUTED} !important;
}}
.stTextInput input:focus,
.stSelectbox div[data-baseweb="select"] > div:focus-within {{
    border-color: {CYAN_ELECTRIC} !important;
    box-shadow: 0 0 0 2px rgba(66, 232, 224, 0.18) !important;
}}
ul[data-baseweb="menu"] {{
    background-color: {BG_ELEVATED} !important;
    border: 1px solid {BORDER_SUBTLE} !important;
}}

/* Buttons */
.stButton > button {{
    background: linear-gradient(135deg, #132136 0%, #0D1421 100%) !important;
    color: {TEXT_PRIMARY} !important;
    border: 1px solid rgba(66, 232, 224, 0.28) !important;
    border-radius: 9px !important;
    font-family: 'Space Grotesk', 'Inter', sans-serif !important;
    font-weight: 600 !important;
    letter-spacing: 0.01em;
    padding: 0.5rem 1rem !important;
    transition: all 160ms ease !important;
}}
.stButton > button:hover {{
    border-color: {CYAN_ELECTRIC} !important;
    box-shadow: 0 0 18px rgba(66, 232, 224, 0.22) !important;
    transform: translateY(-1px);
}}
.stButton > button[kind="primary"] {{
    background: linear-gradient(135deg, {CYAN_ELECTRIC} 0%, #24B8B5 100%) !important;
    border-color: {CYAN_ELECTRIC} !important;
    color: #050911 !important;
    box-shadow: 0 4px 20px rgba(66, 232, 224, 0.25) !important;
}}
.stButton > button[kind="primary"]:hover {{
    box-shadow: 0 6px 26px rgba(66, 232, 224, 0.42) !important;
}}
.stButton > button[kind="primary"] p {{
    color: #050911 !important;
    font-weight: 700 !important;
}}

/* Expanders, Tabs & DataFrames */
div[data-testid="stExpander"] {{
    background-color: {BG_SURFACE} !important;
    border: 1px solid {BORDER_HAIR} !important;
    border-radius: 12px !important;
}}
div[data-testid="stTabs"] button[role="tab"] {{
    font-family: 'JetBrains Mono', ui-monospace, monospace !important;
    font-size: 0.78rem !important;
    letter-spacing: 0.04em;
    color: {TEXT_SECONDARY} !important;
}}
div[data-testid="stTabs"] button[aria-selected="true"] {{
    color: {CYAN_ELECTRIC} !important;
    border-bottom-color: {CYAN_ELECTRIC} !important;
}}
.stDataFrame {{
    background-color: {BG_SURFACE} !important;
    border: 1px solid {BORDER_HAIR} !important;
    border-radius: 12px !important;
    overflow: hidden;
}}

/* Sidebar Brand & System Rail */
.ll-brand {{
    display: flex;
    align-items: center;
    gap: 0.75rem;
    padding: 0.25rem 0 0.6rem 0;
}}
.ll-brand-icon {{
    width: 40px;
    height: 40px;
    border-radius: 10px;
    background: linear-gradient(135deg, rgba(66, 232, 224, 0.18), rgba(155, 124, 255, 0.18));
    border: 1px solid rgba(66, 232, 224, 0.42);
    box-shadow: 0 0 18px rgba(66, 232, 224, 0.16);
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
}}
.ll-brand-title {{
    font-family: 'Space Grotesk', sans-serif;
    font-size: 1.24rem;
    font-weight: 700;
    color: {TEXT_PRIMARY};
    letter-spacing: -0.02em;
    line-height: 1.05;
}}
.ll-brand-sub {{
    font-family: 'JetBrains Mono', ui-monospace, monospace;
    font-size: 0.68rem;
    color: {CYAN_ELECTRIC};
    letter-spacing: 0.08em;
    text-transform: uppercase;
    margin-top: 0.2rem;
}}
.ll-sys-status {{
    background: rgba(18, 29, 44, 0.55);
    border: 1px solid {BORDER_HAIR};
    border-radius: 10px;
    padding: 0.7rem 0.8rem;
    font-family: 'JetBrains Mono', ui-monospace, monospace;
    font-size: 0.73rem;
    line-height: 1.65;
    color: {TEXT_SECONDARY};
}}
.ll-sys-dot {{
    display: inline-block;
    width: 7px;
    height: 7px;
    border-radius: 999px;
    background: {CYAN_ELECTRIC};
    margin-right: 0.45rem;
    animation: ll-pulse-node 2.4s infinite ease-in-out;
}}
.ll-divider {{
    border-top: 1px solid rgba(137, 152, 173, 0.16);
    margin: 0.8rem 0;
}}
.ll-muted {{
    color: {TEXT_MUTED} !important;
    font-size: 0.82rem;
}}
.ll-mono-tag {{
    font-family: 'JetBrains Mono', ui-monospace, monospace;
    font-size: 0.72rem;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: {CYAN_ELECTRIC};
}}

/* Editorial & Command Hero */
.ll-editorial-hero {{
    position: relative;
    overflow: hidden;
    background:
        radial-gradient(circle at 82% 24%, rgba(155, 124, 255, 0.18), transparent 45%),
        radial-gradient(circle at 12% 85%, rgba(66, 232, 224, 0.14), transparent 48%),
        linear-gradient(135deg, #0D1421 0%, #080D18 100%);
    border: 1px solid rgba(66, 232, 224, 0.22);
    border-radius: 16px;
    padding: 2rem 2.1rem 1.75rem 2.1rem;
    margin-bottom: 1.1rem;
    box-shadow: 0 18px 48px rgba(0, 0, 0, 0.45);
}}
.ll-editorial-hero::after {{
    content: "";
    position: absolute;
    top: 0;
    left: 0;
    width: 38%;
    height: 2px;
    background: linear-gradient(90deg, transparent, {CYAN_ELECTRIC}, {VIOLET_NEON}, transparent);
    animation: ll-scan 7.5s infinite linear;
}}
.ll-editorial-eyebrow {{
    font-family: 'JetBrains Mono', ui-monospace, monospace;
    font-size: 0.74rem;
    letter-spacing: 0.12em;
    color: {CYAN_ELECTRIC};
    text-transform: uppercase;
    margin-bottom: 0.55rem;
}}
.ll-editorial-h1 {{
    font-family: 'Space Grotesk', sans-serif !important;
    font-size: clamp(2rem, 3.6vw, 3.05rem) !important;
    line-height: 1.04 !important;
    font-weight: 700 !important;
    letter-spacing: -0.03em !important;
    color: {TEXT_PRIMARY} !important;
    margin: 0 0 0.65rem 0 !important;
}}
.ll-editorial-sub {{
    color: {TEXT_SECONDARY} !important;
    font-size: 1.02rem;
    max-width: 680px;
    line-height: 1.5;
    margin: 0;
}}
.ll-hero {{
    position: relative;
    overflow: hidden;
    background:
        radial-gradient(circle at 88% 20%, rgba(155, 124, 255, 0.14), transparent 45%),
        linear-gradient(135deg, #0E1625 0%, #090E18 100%);
    border: 1px solid rgba(66, 232, 224, 0.20);
    border-radius: 14px;
    padding: 1.35rem 1.65rem;
    margin-bottom: 1rem;
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex-wrap: wrap;
    gap: 1rem;
}}
.ll-hero h1 {{
    color: {TEXT_PRIMARY} !important;
    margin: 0 0 0.25rem 0 !important;
    font-size: 1.7rem !important;
    line-height: 1.15;
}}
.ll-hero .sub {{
    color: {TEXT_SECONDARY} !important;
    font-size: 0.94rem;
    margin: 0;
}}
.ll-hero-badge {{
    font-family: 'JetBrains Mono', ui-monospace, monospace;
    background: rgba(66, 232, 224, 0.11);
    border: 1px solid rgba(66, 232, 224, 0.38);
    color: {CYAN_ELECTRIC} !important;
    padding: 0.38rem 0.78rem;
    border-radius: 999px;
    font-size: 0.74rem;
    font-weight: 600;
    letter-spacing: 0.04em;
    white-space: nowrap;
}}

/* Asymmetric HUD Telemetry Strip (replaces uniform card grids) */
.ll-hud-strip {{
    display: grid;
    grid-template-columns: 1.4fr repeat(4, 1fr);
    background: {BG_GLASS};
    backdrop-filter: blur(10px);
    border: 1px solid {BORDER_HAIR};
    border-radius: 12px;
    margin-bottom: 1.15rem;
    overflow: hidden;
}}
.ll-hud-cell {{
    padding: 0.9rem 1.05rem;
    border-right: 1px solid rgba(137, 152, 173, 0.12);
    transition: background-color 160ms ease;
}}
.ll-hud-cell:last-child {{
    border-right: none;
}}
.ll-hud-cell.primary {{
    background: linear-gradient(135deg, rgba(66, 232, 224, 0.10), rgba(18, 29, 44, 0.65));
    border-left: 3px solid {CYAN_ELECTRIC};
}}
.ll-hud-cell:hover {{
    background: rgba(66, 232, 224, 0.05);
}}
.ll-hud-label {{
    font-family: 'JetBrains Mono', ui-monospace, monospace;
    font-size: 0.68rem;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: {TEXT_SECONDARY};
}}
.ll-hud-val {{
    font-family: 'Space Grotesk', sans-serif;
    font-size: 1.48rem;
    font-weight: 700;
    color: {TEXT_PRIMARY};
    font-variant-numeric: tabular-nums;
    margin-top: 0.22rem;
    line-height: 1.1;
}}
.ll-hud-cell.primary .ll-hud-val {{
    color: {CYAN_ELECTRIC};
}}
.ll-hud-sub {{
    font-family: 'JetBrains Mono', ui-monospace, monospace;
    font-size: 0.71rem;
    color: {TEXT_MUTED};
    margin-top: 0.25rem;
}}

/* Standard KPI Grid (used on secondary sub-pages) */
.ll-kpi-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(175px, 1fr));
    gap: 0.75rem;
    margin-bottom: 1.1rem;
}}
.ll-kpi {{
    background: linear-gradient(180deg, rgba(18, 29, 44, 0.85), rgba(13, 20, 33, 0.92));
    border: 1px solid {BORDER_HAIR};
    border-top: 2px solid {CYAN_ELECTRIC};
    border-radius: 10px;
    padding: 0.88rem 1rem;
    transition: transform 160ms ease, border-color 160ms ease, box-shadow 160ms ease;
}}
.ll-kpi:hover {{
    transform: translateY(-2px);
    border-color: rgba(66, 232, 224, 0.42);
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.35);
}}
.ll-kpi .label {{
    font-family: 'JetBrains Mono', ui-monospace, monospace;
    color: {TEXT_SECONDARY} !important;
    font-size: 0.69rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.08em;
}}
.ll-kpi .value {{
    color: {TEXT_PRIMARY} !important;
    font-family: 'Space Grotesk', sans-serif;
    font-size: 1.48rem;
    font-weight: 700;
    font-variant-numeric: tabular-nums;
    line-height: 1.15;
    margin-top: 0.28rem;
}}
.ll-kpi .delta {{
    font-family: 'JetBrains Mono', ui-monospace, monospace;
    color: {TEXT_MUTED} !important;
    font-size: 0.72rem;
    margin-top: 0.24rem;
}}

/* Elevated Glass Panels & Intelligence Notices */
.ll-card {{
    background: {BG_GLASS};
    backdrop-filter: blur(8px);
    border: 1px solid {BORDER_HAIR};
    border-radius: 12px;
    padding: 1.05rem 1.2rem;
    margin-bottom: 0.85rem;
    transition: border-color 150ms ease, transform 150ms ease;
}}
.ll-card:hover {{
    border-color: rgba(66, 232, 224, 0.28);
}}
.ll-notice {{
    background: rgba(18, 29, 44, 0.72);
    border: 1px solid rgba(245, 184, 75, 0.28);
    border-left: 3px solid {AMBER_SIGNAL};
    border-radius: 10px;
    padding: 0.78rem 1rem;
    margin-bottom: 1rem;
    font-size: 0.88rem;
    color: {TEXT_SECONDARY};
}}
.ll-notice strong {{
    color: {AMBER_SIGNAL};
}}

/* Schematic Frame Header */
.ll-panel-head {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding-bottom: 0.5rem;
    margin-bottom: 0.45rem;
    border-bottom: 1px solid rgba(137, 152, 173, 0.14);
}}
.ll-panel-title {{
    font-family: 'Space Grotesk', sans-serif;
    font-size: 1.04rem;
    font-weight: 700;
    color: {TEXT_PRIMARY};
}}
.ll-panel-meta {{
    font-family: 'JetBrains Mono', ui-monospace, monospace;
    font-size: 0.70rem;
    color: {CYAN_ELECTRIC};
    letter-spacing: 0.06em;
    text-transform: uppercase;
}}

/* Journey Route Dossier Cards */
.ll-route-card {{
    position: relative;
    background: linear-gradient(135deg, rgba(18, 29, 44, 0.92), rgba(11, 17, 29, 0.96));
    border: 1px solid {BORDER_HAIR};
    border-radius: 14px;
    padding: 1.15rem 1.35rem;
    margin-bottom: 0.6rem;
    transition: transform 160ms ease, box-shadow 160ms ease, border-color 160ms ease;
    animation: ll-fade-up 0.3s ease;
}}
.ll-route-card:hover {{
    transform: translateY(-2px);
    box-shadow: 0 12px 32px rgba(0, 0, 0, 0.45);
}}
.ll-route-card.selected {{
    border-color: rgba(66, 232, 224, 0.55);
    box-shadow: 0 0 28px rgba(66, 232, 224, 0.12);
}}
.ll-route-head {{
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    flex-wrap: wrap;
    gap: 0.85rem;
}}
.ll-route-left {{
    display: flex;
    align-items: center;
    gap: 0.75rem;
    flex-wrap: wrap;
}}
.ll-route-pill {{
    font-family: 'JetBrains Mono', ui-monospace, monospace;
    background: rgba(66, 232, 224, 0.12);
    border: 1px solid rgba(66, 232, 224, 0.38);
    color: {CYAN_ELECTRIC} !important;
    font-weight: 700;
    font-size: 0.92rem;
    padding: 0.36rem 0.78rem;
    border-radius: 8px;
}}
.ll-dir-pill {{
    font-family: 'JetBrains Mono', ui-monospace, monospace;
    background: rgba(155, 124, 255, 0.14);
    border: 1px solid rgba(155, 124, 255, 0.32);
    color: {VIOLET_NEON} !important;
    font-size: 0.71rem;
    font-weight: 600;
    padding: 0.24rem 0.58rem;
    border-radius: 999px;
    text-transform: uppercase;
}}
.ll-demand-pill {{
    display: inline-flex;
    align-items: center;
    gap: 0.45rem;
    padding: 0.34rem 0.78rem;
    border-radius: 999px;
    font-family: 'JetBrains Mono', ui-monospace, monospace;
    font-size: 0.75rem;
    font-weight: 600;
}}
.ll-demand-dot {{
    width: 8px;
    height: 8px;
    border-radius: 999px;
    display: inline-block;
}}
.ll-route-od {{
    font-family: 'Space Grotesk', sans-serif;
    font-size: 0.98rem;
    font-weight: 600;
    color: {TEXT_PRIMARY};
}}
.ll-route-metrics {{
    display: grid;
    grid-template-columns: repeat(4, minmax(110px, 1fr));
    gap: 0.75rem;
    margin-top: 0.95rem;
    padding-top: 0.85rem;
    border-top: 1px solid rgba(137, 152, 173, 0.14);
}}
.ll-rm-label {{
    font-family: 'JetBrains Mono', ui-monospace, monospace;
    font-size: 0.68rem;
    color: {TEXT_SECONDARY};
    text-transform: uppercase;
    letter-spacing: 0.06em;
}}
.ll-rm-val {{
    font-family: 'Space Grotesk', sans-serif;
    font-size: 1.08rem;
    font-weight: 700;
    color: {TEXT_PRIMARY};
    font-variant-numeric: tabular-nums;
    margin-top: 0.18rem;
}}

/* Animated Horizontal Route Tracer (Journey Planner Hero) */
.ll-tracer-box {{
    position: relative;
    overflow: hidden;
    background: linear-gradient(180deg, rgba(13, 20, 33, 0.94), rgba(7, 10, 18, 0.98));
    border: 1px solid rgba(66, 232, 224, 0.28);
    border-radius: 14px;
    padding: 1.1rem 1.25rem;
    margin: 0.8rem 0 1rem 0;
    box-shadow: 0 12px 34px rgba(0, 0, 0, 0.45);
}}
.ll-tracer-box::after {{
    content: "";
    position: absolute;
    top: 0;
    left: 0;
    width: 35%;
    height: 2px;
    background: linear-gradient(90deg, transparent, {CYAN_ELECTRIC}, transparent);
    animation: ll-scan 5.5s infinite linear;
}}
.ll-tracer-track {{
    display: flex;
    align-items: flex-start;
    gap: 0;
    overflow-x: auto;
    padding: 0.7rem 0.25rem 0.5rem 0.25rem;
}}
.ll-tr-node-wrap {{
    position: relative;
    display: flex;
    flex-direction: column;
    align-items: center;
    min-width: 108px;
    max-width: 128px;
    flex-shrink: 0;
    animation: ll-node-in 0.35s ease backwards;
    animation-delay: calc(var(--idx, 0) * 85ms);
}}
.ll-tr-dot {{
    width: 16px;
    height: 16px;
    border-radius: 999px;
    background: {BG_VOID};
    border: 3px solid {CYAN_ELECTRIC};
    transition: transform 150ms ease, box-shadow 150ms ease;
    z-index: 2;
}}
.ll-tr-node-wrap:hover .ll-tr-dot {{
    transform: scale(1.28);
    box-shadow: 0 0 14px {CYAN_ELECTRIC};
}}
.ll-tr-dot.origin {{
    background: {CYAN_ELECTRIC};
    animation: ll-pulse-node 2.2s infinite ease-in-out;
}}
.ll-tr-dot.dest {{
    border-color: {MAGENTA_NEON};
    background: {MAGENTA_NEON};
    box-shadow: 0 0 14px rgba(236, 77, 171, 0.55);
}}
.ll-tr-name {{
    font-size: 0.76rem;
    font-weight: 600;
    color: {TEXT_PRIMARY};
    text-align: center;
    margin-top: 0.45rem;
    line-height: 1.25;
}}
.ll-tr-sub {{
    font-family: 'JetBrains Mono', ui-monospace, monospace;
    font-size: 0.66rem;
    color: {TEXT_SECONDARY};
    margin-top: 0.18rem;
}}
.ll-tr-link {{
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    min-width: 68px;
    padding-top: 2px;
    flex-shrink: 0;
}}
.ll-tr-svg {{
    width: 68px;
    height: 14px;
    overflow: visible;
}}
.ll-tr-flow {{
    stroke-dasharray: 8 6;
    animation: ll-trace-dash 1.2s linear infinite;
}}

/* Stop-by-stop Metro Timeline */
.ll-timeline {{
    padding: 0.45rem 0.25rem;
}}
.ll-tl-step {{
    display: grid;
    grid-template-columns: 24px 1fr auto;
    gap: 0.75rem;
    align-items: start;
}}
.ll-tl-rail {{
    display: flex;
    flex-direction: column;
    align-items: center;
}}
.ll-tl-dot {{
    width: 12px;
    height: 12px;
    border-radius: 999px;
    border: 3px solid {CYAN_ELECTRIC};
    background: {BG_VOID};
    margin-top: 3px;
}}
.ll-tl-dot.origin {{
    border-color: {CYAN_ELECTRIC};
    background: {CYAN_ELECTRIC};
    box-shadow: 0 0 10px {CYAN_ELECTRIC};
}}
.ll-tl-dot.dest {{
    border-color: {MAGENTA_NEON};
    background: {MAGENTA_NEON};
    box-shadow: 0 0 10px {MAGENTA_NEON};
}}
.ll-tl-line {{
    width: 3px;
    min-height: 28px;
    border-radius: 2px;
    margin: 2px 0;
}}
.ll-tl-stop {{
    font-family: 'Space Grotesk', sans-serif;
    font-weight: 600;
    color: {TEXT_PRIMARY};
    font-size: 0.92rem;
    line-height: 1.3;
}}
.ll-tl-seg {{
    font-family: 'JetBrains Mono', ui-monospace, monospace;
    font-size: 0.75rem;
    color: {TEXT_SECONDARY};
    padding: 0.2rem 0 0.55rem 0;
}}
.ll-tl-badge {{
    font-family: 'JetBrains Mono', ui-monospace, monospace;
    font-size: 0.73rem;
    font-weight: 600;
    padding: 0.22rem 0.58rem;
    border-radius: 999px;
    font-variant-numeric: tabular-nums;
    white-space: nowrap;
}}

/* Futuristic Corridor Strip (Segment Explorer Signature) */
.ll-corridor-shell {{
    position: relative;
    overflow: hidden;
    background: linear-gradient(180deg, rgba(13, 20, 33, 0.92), rgba(7, 10, 18, 0.96));
    border: 1px solid rgba(66, 232, 224, 0.22);
    border-radius: 14px;
    padding: 1rem 1.1rem;
    margin-bottom: 1rem;
}}
.ll-corridor-shell::after {{
    content: "";
    position: absolute;
    top: 0;
    left: 0;
    width: 30%;
    height: 2px;
    background: linear-gradient(90deg, transparent, {VIOLET_NEON}, {CYAN_ELECTRIC}, transparent);
    animation: ll-scan 6.5s infinite linear;
}}
.ll-corridor {{
    display: flex;
    align-items: center;
    gap: 0;
    overflow-x: auto;
    padding: 0.55rem 0.25rem 0.75rem 0.25rem;
}}
.ll-corr-item {{
    display: flex;
    align-items: center;
    flex-shrink: 0;
}}
.ll-corr-stop {{
    background: {BG_ELEVATED};
    border: 1px solid rgba(66, 232, 224, 0.24);
    border-radius: 9px;
    padding: 0.48rem 0.72rem;
    font-size: 0.8rem;
    font-weight: 600;
    color: {TEXT_PRIMARY};
    max-width: 148px;
    text-align: center;
    transition: border-color 150ms ease, box-shadow 150ms ease;
}}
.ll-corr-stop:hover {{
    border-color: {CYAN_ELECTRIC};
    box-shadow: 0 0 14px rgba(66, 232, 224, 0.22);
}}
.ll-corr-link {{
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: 0 0.35rem;
    min-width: 86px;
}}
.ll-corr-vol {{
    font-family: 'JetBrains Mono', ui-monospace, monospace;
    font-size: 0.72rem;
    font-weight: 700;
    font-variant-numeric: tabular-nums;
}}

/* Mobile Responsiveness */
@media (max-width: 980px) {{
    .ll-hud-strip {{
        grid-template-columns: repeat(2, 1fr);
    }}
    .ll-hud-cell.primary {{
        grid-column: span 2;
    }}
}}
@media (max-width: 768px) {{
    .block-container {{
        padding-left: 0.8rem !important;
        padding-right: 0.8rem !important;
        padding-top: 0.9rem !important;
    }}
    .ll-editorial-hero {{
        padding: 1.35rem 1.2rem;
    }}
    .ll-route-metrics {{
        grid-template-columns: repeat(2, minmax(100px, 1fr));
    }}
    .ll-kpi-grid {{
        grid-template-columns: repeat(2, minmax(130px, 1fr));
    }}
}}
"""
    compact_css = "\n".join(line for line in css_body.splitlines() if line.strip())
    if hasattr(st, "html"):
        st.html(f"<style>{compact_css}</style>")
    else:
        st.markdown(f"<style>{compact_css}</style>", unsafe_allow_html=True)


def brand_header() -> str:
    """Return cyberpunk LoadLens radar-bus emblem + wordmark HTML for the left rail."""
    return (
        '<div class="ll-brand">'
        '<div class="ll-brand-icon">'
        '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">'
        '<circle cx="12" cy="12" r="9" stroke="#42E8E0" stroke-width="1.5" stroke-dasharray="3 2"/>'
        '<path d="M7 15L10.5 11.5L13.5 13.5L17 9" stroke="#9B7CFF" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>'
        '<circle cx="7" cy="15" r="1.6" fill="#42E8E0"/>'
        '<circle cx="17" cy="9" r="1.6" fill="#EC4DAB"/>'
        '</svg>'
        '</div>'
        '<div>'
        '<div class="ll-brand-title">LoadLens</div>'
        '<div class="ll-brand-sub">City Mobility Intel</div>'
        '</div>'
        '</div>'
    )


def editorial_hero(eyebrow: str, title: str, subtitle: str, badge: str | None = None) -> None:
    import streamlit as st
    badge_html = f'<div class="ll-hero-badge" style="margin-top:0.9rem;display:inline-block;">{html.escape(badge)}</div>' if badge else ""
    st.markdown(
        '<div class="ll-editorial-hero">'
        f'<div class="ll-editorial-eyebrow">{html.escape(eyebrow)}</div>'
        f'<h1 class="ll-editorial-h1">{html.escape(title)}</h1>'
        f'<p class="ll-editorial-sub">{html.escape(subtitle)}</p>'
        f'{badge_html}'
        '</div>',
        unsafe_allow_html=True,
    )


def hero(title: str, subtitle: str, badge: str | None = None) -> None:
    import streamlit as st
    t = html.escape(title)
    s = html.escape(subtitle)
    badge_html = f'<div class="ll-hero-badge">{html.escape(badge)}</div>' if badge else ""
    st.markdown(
        f'<div class="ll-hero"><div><h1>{t}</h1><p class="sub">{s}</p></div>{badge_html}</div>',
        unsafe_allow_html=True,
    )


def hud_metrics_strip(items: Iterable[Tuple[str, str, str]]) -> None:
    """Render an asymmetric 5-cell HUD telemetry bar (1st cell highlighted)."""
    import streamlit as st
    cells = []
    for i, (label, value, sub) in enumerate(items):
        cls = "ll-hud-cell primary" if i == 0 else "ll-hud-cell"
        cells.append(
            f'<div class="{cls}">'
            f'<div class="ll-hud-label">{html.escape(label)}</div>'
            f'<div class="ll-hud-val">{html.escape(value)}</div>'
            f'<div class="ll-hud-sub">{html.escape(sub)}</div>'
            '</div>'
        )
    st.markdown(f'<div class="ll-hud-strip">{"".join(cells)}</div>', unsafe_allow_html=True)


def card(content_html: str) -> None:
    import streamlit as st
    st.markdown(f'<div class="ll-card">{content_html}</div>', unsafe_allow_html=True)


def kpi(label: str, value: str, delta: str = "") -> str:
    return (
        '<div class="ll-kpi">'
        f'<div class="label">{html.escape(label)}</div>'
        f'<div class="value">{html.escape(value)}</div>'
        f'<div class="delta">{html.escape(delta)}</div>'
        '</div>'
    )


def kpi_row(items: Iterable[Tuple[str, str, str]]) -> None:
    import streamlit as st
    tiles = "".join(kpi(label, value, delta) for label, value, delta in items)
    st.markdown(f'<div class="ll-kpi-grid">{tiles}</div>', unsafe_allow_html=True)


def muted(text: str) -> str:
    return f'<span class="ll-muted">{html.escape(text)}</span>'


def limitation_banner(text: str) -> None:
    import streamlit as st
    st.markdown(f'<div class="ll-notice">{text}</div>', unsafe_allow_html=True)


def animated_route_tracer_html(opt: dict, max_nodes: int = 24) -> str:
    """Render an animated SVG/HTML route trace for the currently selected journey option."""
    seg_df = opt.get("segments")
    if seg_df is None or len(seg_df) == 0:
        return ""

    has_load = opt.get("has_matched_load", True)
    route_lbl = html.escape(str(opt.get("route", "")))
    dir_lbl = html.escape(str(opt.get("direction", "")))
    dur = opt.get("estimated_duration_min")
    dur_txt = f"{dur:.1f} min (GTFS)" if dur is not None else "Duration N/A (no GTFS)"

    rows = list(seg_df.itertuples(index=False))
    truncated = len(rows) > max_nodes
    view_rows = rows[:max_nodes]
    has_net = "network_load_percentile" in seg_df.columns
    has_obs = "obs_status" in seg_df.columns

    parts = [
        '<div class="ll-tracer-box">'
        '<div class="ll-panel-head">'
        f'<div class="ll-panel-title">Active Route Trace · {route_lbl} ({dir_lbl.upper()})</div>'
        f'<div class="ll-panel-meta">{len(rows)} segments · {html.escape(dur_txt)}</div>'
        '</div>'
        '<div class="ll-tracer-track">'
    ]

    for i, row in enumerate(view_rows):
        raw_load = getattr(row, "segment_load", None)
        is_na = (not has_load) or raw_load is None or (isinstance(raw_load, float) and math.isnan(raw_load))
        raw_net = getattr(row, "network_load_percentile", None) if has_net else getattr(row, "relative_load_index", None)
        obs_st = getattr(row, "obs_status", "observed") if has_obs else "observed"
        net = None if (raw_net is None or (isinstance(raw_net, float) and math.isnan(raw_net))) else float(raw_net)

        if is_na or obs_st in ("unmatched_route", "unmatched_segment", "no_tickets_in_window"):
            color = TEXT_MUTED
            link_lbl = "N/A"
        elif obs_st == "zero_observed_in_window" or int(round(float(raw_load))) == 0:
            color = CYAN_ELECTRIC
            link_lbl = "0 pax"
        else:
            _, color, _ = demand_tier(net)
            link_lbl = f"{int(round(float(raw_load))):,}"

        stop_from = html.escape(str(row.from_norm).title())
        dot_cls = "origin" if i == 0 else ""
        sub_txt = "ORIGIN" if i == 0 else f"STOP {i + 1}"
        parts.append(
            f'<div class="ll-tr-node-wrap" style="--idx:{i};" title="{stop_from} → {html.escape(str(row.to_norm).title())}: {link_lbl}">'
            f'<div class="ll-tr-dot {dot_cls}"></div>'
            f'<div class="ll-tr-name">{stop_from}</div>'
            f'<div class="ll-tr-sub">{sub_txt}</div>'
            f'</div>'
        )
        parts.append(
            f'<div class="ll-tr-link">'
            f'<svg class="ll-tr-svg" viewBox="0 0 68 14">'
            f'<line x1="0" y1="7" x2="68" y2="7" stroke="{color}" stroke-opacity="0.28" stroke-width="4" stroke-linecap="round"/>'
            f'<line class="ll-tr-flow" x1="0" y1="7" x2="68" y2="7" stroke="{color}" stroke-width="2.5" stroke-linecap="round"/>'
            f'</svg>'
            f'<div class="ll-tr-sub" style="color:{color};font-weight:600;">{link_lbl}</div>'
            f'</div>'
        )
        if i == len(view_rows) - 1:
            dest_name = html.escape(str(row.to_norm).title())
            parts.append(
                f'<div class="ll-tr-node-wrap" style="--idx:{i + 1};" title="Destination: {dest_name}">'
                f'<div class="ll-tr-dot dest"></div>'
                f'<div class="ll-tr-name">{dest_name}</div>'
                f'<div class="ll-tr-sub" style="color:{MAGENTA_NEON};">TARGET</div>'
                f'</div>'
            )

    if truncated:
        parts.append(
            f'<div class="ll-tr-link"><div class="ll-tr-sub">+{len(rows) - max_nodes} more</div></div>'
        )
    parts.append('</div></div>')
    return "".join(parts)


def stop_timeline_html(segments_df, origin: str, destination: str) -> str:
    """Render a vertical Metro-style stop-by-stop timeline from real segment rows."""
    if segments_df is None or len(segments_df) == 0:
        return ""
    parts = ['<div class="ll-timeline">']
    n = len(segments_df)
    has_net = "network_load_percentile" in segments_df.columns
    has_obs = "obs_status" in segments_df.columns
    for i, row in enumerate(segments_df.itertuples(index=False)):
        raw_load = getattr(row, "segment_load", None)
        is_na_load = raw_load is None or (isinstance(raw_load, float) and math.isnan(raw_load))
        raw_rel = getattr(row, "relative_load_index", None)
        raw_net = getattr(row, "network_load_percentile", None) if has_net else raw_rel
        obs_st = getattr(row, "obs_status", "observed") if has_obs else "observed"

        rel = None if (raw_rel is None or (isinstance(raw_rel, float) and math.isnan(raw_rel))) else float(raw_rel)
        net = None if (raw_net is None or (isinstance(raw_net, float) and math.isnan(raw_net))) else float(raw_net)

        if is_na_load or obs_st in ("unmatched_route", "unmatched_segment", "no_tickets_in_window"):
            tier_lbl, color, bg = ("Data unavailable", TEXT_SECONDARY, "rgba(137, 152, 173, 0.12)")
            seg_desc = "No matched ticket demand data for this segment (N/A)"
            badge_txt = "N/A"
        elif obs_st == "zero_observed_in_window" or int(round(float(raw_load))) == 0:
            tier_lbl, color, bg = ("Zero tickets in window", CYAN_ELECTRIC, CYAN_SOFT)
            seg_desc = "0 tickets observed in selected window"
            badge_txt = "0 pax"
        else:
            tier_lbl, color, bg = demand_tier(net if net is not None else rel)
            vol = int(round(float(raw_load)))
            seg_desc = f"{vol:,} historical pax on next segment ({tier_lbl.lower()})"
            if net is not None and rel is not None:
                badge_txt = f"P{int(round(net * 100))} · RLI {rel:.2f}"
            elif rel is not None:
                badge_txt = f"RLI {rel:.2f}"
            else:
                badge_txt = f"{vol:,} pax"

        dot_cls = "origin" if i == 0 else ""
        stop_name = html.escape(str(row.from_norm).title())
        tag = "Boarding stop" if i == 0 else f"Stop {i + 1}"
        parts.append(
            f'<div class="ll-tl-step">'
            f'<div class="ll-tl-rail">'
            f'<div class="ll-tl-dot {dot_cls}"></div>'
            f'<div class="ll-tl-line" style="background:{color};"></div>'
            f'</div>'
            f'<div>'
            f'<div class="ll-tl-stop">{stop_name}</div>'
            f'<div class="ll-tl-seg">{tag} · {seg_desc}</div>'
            f'</div>'
            f'<div class="ll-tl-badge" style="color:{color};background:{bg};">{badge_txt}</div>'
            f'</div>'
        )
        if i == n - 1:
            dest_name = html.escape(str(row.to_norm).title())
            parts.append(
                f'<div class="ll-tl-step">'
                f'<div class="ll-tl-rail"><div class="ll-tl-dot dest"></div></div>'
                f'<div><div class="ll-tl-stop">{dest_name}</div>'
                f'<div class="ll-tl-seg">Destination stop ({n} segments traversed)</div></div>'
                f'<div></div>'
                f'</div>'
            )
    parts.append("</div>")
    return "".join(parts)


def corridor_strip_html(segments_df, max_segments: int = 35, highlight_idx: Optional[int] = None) -> str:
    """Render an animated futuristic corridor schematic for Segment Explorer."""
    if segments_df is None or len(segments_df) == 0:
        return ""
    df_view = segments_df.head(max_segments)
    has_net = "network_load_percentile" in df_view.columns
    max_load = max(float(df_view["segment_load"].max()), 1.0)
    parts = ['<div class="ll-corridor-shell"><div class="ll-corridor">']
    for i, row in enumerate(df_view.itertuples(index=False)):
        metric = float(row.network_load_percentile) if has_net else float(row.relative_load_index)
        _, color, _ = demand_tier(metric)
        vol = int(row.segment_load)
        stroke_w = max(2.5, min(6.5, 2.5 + (vol / max_load) * 4.0))
        is_sel = highlight_idx is not None and i == highlight_idx
        sel_style = f"border-color:{CYAN_ELECTRIC};box-shadow:0 0 16px rgba(66,232,224,0.35);" if is_sel else ""
        if i == 0:
            parts.append(
                f'<div class="ll-corr-item"><div class="ll-corr-stop" style="{sel_style}">{html.escape(str(row.from_norm).title())}</div></div>'
            )
        parts.append(
            f'<div class="ll-corr-item">'
            f'<div class="ll-corr-link">'
            f'<div class="ll-corr-vol" style="color:{color};">{vol:,}</div>'
            f'<svg width="84" height="14" viewBox="0 0 84 14" style="overflow:visible;">'
            f'<line x1="0" y1="7" x2="84" y2="7" stroke="{color}" stroke-opacity="0.28" stroke-width="{stroke_w + 2:.1f}" stroke-linecap="round"/>'
            f'<line class="ll-tr-flow" x1="0" y1="7" x2="84" y2="7" stroke="{color}" stroke-width="{stroke_w:.1f}" stroke-linecap="round"/>'
            f'</svg>'
            f'</div>'
            f'<div class="ll-corr-stop" style="{sel_style}">{html.escape(str(row.to_norm).title())}</div>'
            f'</div>'
        )
    if len(segments_df) > max_segments:
        parts.append(
            f'<div class="ll-corr-item"><div class="ll-corr-link"><span class="ll-muted">+{len(segments_df) - max_segments} more</span></div></div>'
        )
    parts.append("</div></div>")
    return "".join(parts)
