"""LoadLens — Premium dark urban-intelligence design system.

Single source for colour tokens, typography, CSS injection, and the bespoke HTML
components used by the five Streamlit pages. All calculation logic and data
pipeline modules are untouched; only the presentation layer is rebuilt here.
"""
from __future__ import annotations

import html
import math
from typing import Iterable, Optional, Tuple

# ---- Visual Identity Tokens (locked palette) --------------------------------
BG_VOID          = "#070910"      # Primary canvas
BG_SURFACE       = "#0B101B"      # Secondary background
BG_PANEL         = "#111827"      # Panel background
BG_ELEVATED      = "#172234"      # Elevated panel / hover wash

CYAN_ELECTRIC    = "#42E8E0"      # Primary neon — investigation trails
VIOLET_NEON      = "#9575FF"      # Electric violet
MAGENTA_NEON     = "#E84FA8"      # Neon magenta accents
AMBER_SIGNAL     = "#F5B84B"      # Warning amber
CORAL_ALERT      = "#FF6B70"      # High-demand coral

TEXT_PRIMARY     = "#F3F6FC"      # Headings & primary text
TEXT_SECONDARY   = "#91A0B5"      # Body & secondary
TEXT_MUTED       = "#5C6B83"      # Footnotes

CYAN_SOFT        = "rgba(66, 232, 224, 0.14)"
VIOLET_SOFT      = "rgba(149, 117, 255, 0.16)"
MAGENTA_SOFT     = "rgba(232, 79, 168, 0.16)"
AMBER_SOFT       = "rgba(245, 184, 75, 0.15)"
CORAL_SOFT       = "rgba(255, 107, 112, 0.16)"

BORDER_SUBTLE    = "rgba(66, 232, 224, 0.18)"
BORDER_HAIR      = "rgba(145, 160, 181, 0.20)"
BORDER_ACTIVE    = "rgba(66, 232, 224, 0.55)"

# Legacy aliases (kept for any external imports in `app_pages.py`)
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
BG_PANEL_BG   = BG_PANEL
BG_CARD       = BG_ELEVATED
BORDER        = BORDER_SUBTLE

# Colorway scales used by Plotly charts
LOAD_SCALE = [
    [0.00, "#0F2233"],
    [0.25, "#196678"],
    [0.50, CYAN_ELECTRIC],
    [0.72, VIOLET_NEON],
    [0.88, AMBER_SIGNAL],
    [1.00, CORAL_ALERT],
]

ROUTES_SCALE = [
    CYAN_ELECTRIC, VIOLET_NEON, AMBER_SIGNAL, MAGENTA_NEON,
    "#2EE59D", CORAL_ALERT, "#60A5FA", "#C084FC",
]


def demand_tier(rel: Optional[float]) -> Tuple[str, str, str]:
    """Return ``(label, accent, translucent pill bg)`` for a 0-1 relative load."""
    if rel is None or (isinstance(rel, float) and math.isnan(rel)):
        return "Insufficient data", TEXT_SECONDARY, "rgba(145, 160, 181, 0.14)"
    if rel < 0.40:
        return "Low demand", CYAN_ELECTRIC, CYAN_SOFT
    if rel < 0.75:
        return "Moderate demand", AMBER_SIGNAL, AMBER_SOFT
    return "High demand", CORAL_ALERT, CORAL_SOFT


# ============================================================================
# CSS INJECTION — the entire visual identity compiled into one stylesheet
# ============================================================================
def inject_css() -> None:
    import streamlit as st

    css_body = f"""@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap');
:root {{
    --ll-void: {BG_VOID};
    --ll-surface: {BG_SURFACE};
    --ll-panel: {BG_PANEL};
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
    --ll-active: {BORDER_ACTIVE};
}}

/* === Subtle entrance animation ========================================== */
@keyframes ll-fade-up {{
    from {{ opacity: 0; transform: translateY(10px); }}
    to   {{ opacity: 1; transform: translateY(0); }}
}}
@keyframes ll-fade-in {{
    from {{ opacity: 0; }}
    to   {{ opacity: 1; }}
}}
@keyframes ll-pulse-node {{
    0%, 100% {{ box-shadow: 0 0 0 0 rgba(66, 232, 224, 0.55); }}
    50%      {{ box-shadow: 0 0 0 10px rgba(66, 232, 224, 0); }}
}}
@keyframes ll-pulse-violet {{
    0%, 100% {{ box-shadow: 0 0 0 0 rgba(149, 117, 255, 0.55); }}
    50%      {{ box-shadow: 0 0 0 10px rgba(149, 117, 255, 0); }}
}}
@keyframes ll-scan-x {{
    0%   {{ transform: translateX(-110%); opacity: 0; }}
    10%  {{ opacity: 1; }}
    90%  {{ opacity: 1; }}
    100% {{ transform: translateX(220%); opacity: 0; }}
}}
@keyframes ll-scan-slow {{
    0%   {{ transform: translateX(-110%); }}
    100% {{ transform: translateX(220%); }}
}}
@keyframes ll-trace-dash {{
    to {{ stroke-dashoffset: -28; }}
}}
@keyframes ll-glow-pulse {{
    0%, 100% {{ filter: drop-shadow(0 0 4px rgba(66,232,224,0.5)); }}
    50%      {{ filter: drop-shadow(0 0 10px rgba(66,232,224,0.85)); }}
}}
@keyframes ll-flicker {{
    0%, 96%, 100% {{ opacity: 1; }}
    97%           {{ opacity: 0.55; }}
    98%           {{ opacity: 0.92; }}
}}

/* === Window & App chrome ================================================ */
html, body, .stApp {{
    background-color: var(--ll-void) !important;
    background-image:
        radial-gradient(ellipse 80% 55% at 16% -8%, rgba(66, 232, 224, 0.085), transparent 60%),
        radial-gradient(ellipse 70% 50% at 90% 6%,  rgba(149, 117, 255, 0.075), transparent 60%),
        radial-gradient(ellipse 60% 50% at 50% 110%, rgba(232, 79, 168, 0.055), transparent 65%),
        linear-gradient(rgba(66, 232, 224, 0.028) 1px, transparent 1px),
        linear-gradient(90deg, rgba(66, 232, 224, 0.028) 1px, transparent 1px) !important;
    background-size: 100% 100%, 100% 100%, 100% 100%, 48px 48px, 48px 48px !important;
    background-attachment: fixed !important;
    color: var(--ll-text) !important;
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
    font-size: 14.5px;
    line-height: 1.55;
}}

h1, h2, h3, h4, h5, h6 {{
    font-family: 'Space Grotesk', 'Inter', sans-serif !important;
    color: var(--ll-text) !important;
    font-weight: 700 !important;
    letter-spacing: -0.025em;
}}
h1 {{ font-weight: 700 !important; }}
p, li, span, label, td, th, div {{ color: var(--ll-text); }}
code, .ll-mono {{
    font-family: 'JetBrains Mono', ui-monospace, monospace !important;
    color: var(--ll-cyan) !important;
    background: rgba(66, 232, 224, 0.07) !important;
    padding: 0.10rem 0.36rem;
    border-radius: 4px;
    font-size: 0.86em;
}}

.block-container {{
    padding-top: 1.0rem !important;
    padding-bottom: 3rem !important;
    max-width: 1480px;
    animation: ll-fade-up 0.45s cubic-bezier(0.16, 1, 0.3, 1);
}}

#MainMenu, footer {{ visibility: hidden; }}
header[data-testid="stHeader"] {{ background: transparent !important; }}

/* === Left Investigation Rail (Sidebar) ================================= */
section[data-testid="stSidebar"] {{
    background: linear-gradient(180deg, #060911 0%, {BG_VOID} 75%, #060911 100%) !important;
    border-right: 1px solid rgba(66, 232, 224, 0.20) !important;
    box-shadow: inset -1px 0 0 rgba(66, 232, 224, 0.06), 14px 0 60px -20px rgba(66, 232, 224, 0.15) !important;
}}
section[data-testid="stSidebar"] > div {{ padding-top: 1.1rem; }}
section[data-testid="stSidebar"] hr {{ border-color: rgba(145, 160, 181, 0.18); }}
section[data-testid="stSidebar"] div[role="radiogroup"] {{ gap: 0.36rem; }}
section[data-testid="stSidebar"] div[role="radiogroup"] label {{
    background: rgba(17, 24, 39, 0.55);
    border: 1px solid rgba(145, 160, 181, 0.10);
    border-left: 3px solid transparent;
    border-radius: 9px;
    padding: 0.62rem 1.85rem 0.62rem 0.86rem !important;
    margin: 0 !important;
    transition: background-color 180ms ease, border-color 180ms ease, transform 180ms ease, box-shadow 180ms ease;
    cursor: pointer;
    position: relative;
}}
section[data-testid="stSidebar"] div[role="radiogroup"] label:hover {{
    background: rgba(66, 232, 224, 0.06);
    border-color: rgba(66, 232, 224, 0.28);
    transform: translateX(3px);
    box-shadow: 0 0 14px rgba(66, 232, 224, 0.10);
}}
section[data-testid="stSidebar"] div[role="radiogroup"] label:has(input:checked) {{
    background: linear-gradient(90deg, rgba(66, 232, 224, 0.22) 0%, rgba(17, 24, 39, 0.85) 100%) !important;
    border-color: rgba(66, 232, 224, 0.55) !important;
    border-left: 3px solid {CYAN_ELECTRIC} !important;
    box-shadow: 0 0 22px rgba(66, 232, 224, 0.20), inset 0 0 0 1px rgba(66, 232, 224, 0.10);
}}
section[data-testid="stSidebar"] div[role="radiogroup"] label:has(input:checked)::after {{
    content: "";
    position: absolute;
    right: 12px; top: 50%;
    width: 6px; height: 6px;
    margin-top: -3px;
    border-radius: 999px;
    background: {CYAN_ELECTRIC};
    box-shadow: 0 0 10px {CYAN_ELECTRIC};
    animation: ll-pulse-node 2.0s infinite ease-in-out;
}}
section[data-testid="stSidebar"] div[role="radiogroup"] label p,
section[data-testid="stSidebar"] div[role="radiogroup"] label span {{
    font-family: 'JetBrains Mono', ui-monospace, monospace !important;
    font-size: 0.78rem !important;
    letter-spacing: 0.04em;
    color: {TEXT_SECONDARY} !important;
}}
section[data-testid="stSidebar"] div[role="radiogroup"] label:has(input:checked) p,
section[data-testid="stSidebar"] div[role="radiogroup"] label:has(input:checked) span {{
    color: {CYAN_ELECTRIC} !important;
    font-weight: 600 !important;
}}
section[data-testid="stSidebar"] div[role="radiogroup"] label > div:first-child {{ display: none; }}

/* === Inputs / Select / Text ============================================== */
.stTextInput input,
.stNumberInput input,
.stSelectbox div[data-baseweb="select"] > div,
.stMultiSelect div[data-baseweb="select"] > div {{
    background-color: {BG_PANEL} !important;
    color: {TEXT_PRIMARY} !important;
    border: 1px solid {BORDER_HAIR} !important;
    border-radius: 9px !important;
    min-height: 42px;
    transition: border-color 160ms ease, box-shadow 160ms ease;
}}
.stTextInput input::placeholder {{ color: {TEXT_MUTED} !important; }}
.stTextInput input:focus,
.stSelectbox div[data-baseweb="select"] > div:focus-within,
.stNumberInput input:focus {{
    border-color: {CYAN_ELECTRIC} !important;
    box-shadow: 0 0 0 3px rgba(66, 232, 224, 0.18) !important;
}}
ul[data-baseweb="menu"] {{
    background-color: {BG_PANEL} !important;
    border: 1px solid {BORDER_SUBTLE} !important;
    border-radius: 8px !important;
}}

/* === Buttons ============================================================ */
.stButton > button {{
    background: linear-gradient(135deg, #11203A 0%, {BG_PANEL} 100%) !important;
    color: {TEXT_PRIMARY} !important;
    border: 1px solid rgba(66, 232, 224, 0.30) !important;
    border-radius: 9px !important;
    font-family: 'Space Grotesk', 'Inter', sans-serif !important;
    font-weight: 600 !important;
    letter-spacing: 0.01em;
    padding: 0.55rem 1.05rem !important;
    transition: all 180ms ease !important;
}}
.stButton > button:hover {{
    border-color: {CYAN_ELECTRIC} !important;
    box-shadow: 0 0 22px rgba(66, 232, 224, 0.25) !important;
    transform: translateY(-1px);
}}
.stButton > button[kind="primary"] {{
    background: linear-gradient(135deg, {CYAN_ELECTRIC} 0%, #1FB9B5 80%, {VIOLET_NEON} 100%) !important;
    border-color: {CYAN_ELECTRIC} !important;
    color: #04060E !important;
    box-shadow: 0 6px 22px rgba(66, 232, 224, 0.35) !important;
    font-weight: 700 !important;
}}
.stButton > button[kind="primary"]:hover {{
    box-shadow: 0 8px 30px rgba(66, 232, 224, 0.55) !important;
    transform: translateY(-1px);
}}
.stButton > button[kind="primary"] p {{
    color: #04060E !important;
    font-weight: 700 !important;
}}

/* === Expanders, Tabs, DataFrames ======================================== */
div[data-testid="stExpander"] {{
    background-color: {BG_PANEL} !important;
    border: 1px solid {BORDER_HAIR} !important;
    border-radius: 12px !important;
    overflow: hidden;
}}
div[data-testid="stExpander"] summary {{
    font-family: 'Space Grotesk', sans-serif !important;
    color: {TEXT_PRIMARY} !important;
    font-weight: 600 !important;
}}
div[data-testid="stTabs"] button[role="tab"] {{
    font-family: 'JetBrains Mono', ui-monospace, monospace !important;
    font-size: 0.74rem !important;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: {TEXT_SECONDARY} !important;
    padding: 0.6rem 1.0rem !important;
}}
div[data-testid="stTabs"] button[aria-selected="true"] {{
    color: {CYAN_ELECTRIC} !important;
    border-bottom: 2px solid {CYAN_ELECTRIC} !important;
}}
.stDataFrame {{
    background-color: {BG_PANEL} !important;
    border: 1px solid {BORDER_HAIR} !important;
    border-radius: 12px !important;
    overflow: hidden;
}}
.stDataFrame table thead th {{
    background: {BG_ELEVATED} !important;
    color: {CYAN_ELECTRIC} !important;
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 0.72rem !important;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}}

/* === Sidebar brand + system telemetry rail ============================== */
.ll-brand {{
    display: flex;
    align-items: center;
    gap: 0.72rem;
    padding: 0.25rem 0.1rem 0.55rem 0.1rem;
    margin-bottom: 0.4rem;
}}
.ll-brand-icon {{
    width: 44px;
    height: 44px;
    border-radius: 11px;
    background: linear-gradient(135deg, rgba(66, 232, 224, 0.20), rgba(149, 117, 255, 0.22));
    border: 1px solid rgba(66, 232, 224, 0.55);
    box-shadow: 0 0 22px rgba(66, 232, 224, 0.25), inset 0 0 0 1px rgba(66, 232, 224, 0.10);
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
    animation: ll-glow-pulse 4s infinite ease-in-out;
}}
.ll-brand-title {{
    font-family: 'Space Grotesk', sans-serif;
    font-size: 1.30rem;
    font-weight: 700;
    color: {TEXT_PRIMARY};
    letter-spacing: -0.025em;
    line-height: 1.05;
}}
.ll-brand-sub {{
    font-family: 'JetBrains Mono', ui-monospace, monospace;
    font-size: 0.66rem;
    color: {CYAN_ELECTRIC};
    letter-spacing: 0.18em;
    text-transform: uppercase;
    margin-top: 0.18rem;
    opacity: 0.85;
}}
.ll-sys-status {{
    background: linear-gradient(180deg, rgba(17, 24, 39, 0.85), rgba(11, 16, 27, 0.95));
    border: 1px solid {BORDER_HAIR};
    border-radius: 10px;
    padding: 0.78rem 0.85rem;
    font-family: 'JetBrains Mono', ui-monospace, monospace;
    font-size: 0.72rem;
    line-height: 1.7;
    color: {TEXT_SECONDARY};
    position: relative;
    overflow: hidden;
}}
.ll-sys-status::before {{
    content: "";
    position: absolute;
    top: 0; left: 0;
    width: 35%; height: 1px;
    background: linear-gradient(90deg, transparent, {CYAN_ELECTRIC}, transparent);
    animation: ll-scan-x 6s infinite ease-in-out;
}}
.ll-sys-dot {{
    display: inline-block;
    width: 7px; height: 7px;
    border-radius: 999px;
    background: {CYAN_ELECTRIC};
    margin-right: 0.45rem;
    animation: ll-pulse-node 2.4s infinite ease-in-out;
}}
.ll-divider {{
    border-top: 1px solid rgba(145, 160, 181, 0.16);
    margin: 0.85rem 0;
}}
.ll-muted {{ color: {TEXT_MUTED} !important; font-size: 0.82rem; }}
.ll-mono-tag {{
    font-family: 'JetBrains Mono', ui-monospace, monospace;
    font-size: 0.70rem;
    letter-spacing: 0.18em;
    text-transform: uppercase;
    color: {CYAN_ELECTRIC};
    opacity: 0.85;
}}

/* === Editorial / cinematic hero (used on Overview & page headers) ========= */
.ll-editorial-hero {{
    position: relative;
    overflow: hidden;
    background:
        radial-gradient(circle at 84% 22%, rgba(149, 117, 255, 0.20), transparent 50%),
        radial-gradient(circle at 10% 90%, rgba(66, 232, 224, 0.16), transparent 50%),
        linear-gradient(135deg, {BG_PANEL} 0%, {BG_VOID} 100%);
    border: 1px solid rgba(66, 232, 224, 0.22);
    border-radius: 18px;
    padding: 2.4rem 2.5rem 2.0rem 2.5rem;
    margin-bottom: 1.4rem;
    box-shadow: 0 24px 60px rgba(0, 0, 0, 0.45), inset 0 1px 0 rgba(66, 232, 224, 0.08);
}}
.ll-editorial-hero::before {{
    content: "";
    position: absolute;
    top: 0; left: 0; right: 0; height: 1px;
    background: linear-gradient(90deg, transparent, {CYAN_ELECTRIC}, {VIOLET_NEON}, {MAGENTA_NEON}, transparent);
    opacity: 0.7;
}}
.ll-editorial-hero::after {{
    content: "";
    position: absolute;
    top: 0; left: 0;
    width: 32%; height: 2px;
    background: linear-gradient(90deg, transparent, {CYAN_ELECTRIC}, transparent);
    animation: ll-scan-x 6.5s infinite linear;
}}
.ll-editorial-eyebrow {{
    font-family: 'JetBrains Mono', ui-monospace, monospace;
    font-size: 0.72rem;
    letter-spacing: 0.20em;
    color: {CYAN_ELECTRIC};
    text-transform: uppercase;
    margin-bottom: 0.85rem;
    display: inline-flex;
    align-items: center;
    gap: 0.6rem;
}}
.ll-editorial-eyebrow::before {{
    content: "";
    display: inline-block;
    width: 28px; height: 1px;
    background: {CYAN_ELECTRIC};
    box-shadow: 0 0 8px {CYAN_ELECTRIC};
}}
.ll-editorial-h1 {{
    font-family: 'Space Grotesk', sans-serif !important;
    font-size: clamp(2.4rem, 4.4vw, 3.6rem) !important;
    line-height: 1.02 !important;
    font-weight: 700 !important;
    letter-spacing: -0.035em !important;
    color: {TEXT_PRIMARY} !important;
    margin: 0 0 0.85rem 0 !important;
    text-shadow: 0 0 24px rgba(66, 232, 224, 0.18);
}}
.ll-editorial-sub {{
    color: {TEXT_SECONDARY} !important;
    font-size: 1.05rem;
    max-width: 720px;
    line-height: 1.5;
    margin: 0;
}}
.ll-hero-badge {{
    font-family: 'JetBrains Mono', ui-monospace, monospace;
    background: rgba(66, 232, 224, 0.10);
    border: 1px solid rgba(66, 232, 224, 0.45);
    color: {CYAN_ELECTRIC} !important;
    padding: 0.42rem 0.85rem;
    border-radius: 999px;
    font-size: 0.72rem;
    font-weight: 600;
    letter-spacing: 0.10em;
    text-transform: uppercase;
    white-space: nowrap;
    box-shadow: 0 0 16px rgba(66, 232, 224, 0.15);
}}

/* === Compact page hero (sub-pages) ===================================== */
.ll-page-hero {{
    position: relative;
    overflow: hidden;
    background:
        linear-gradient(135deg, rgba(66, 232, 224, 0.07) 0%, rgba(149, 117, 255, 0.06) 100%),
        linear-gradient(135deg, {BG_PANEL} 0%, {BG_VOID} 100%);
    border: 1px solid rgba(66, 232, 224, 0.20);
    border-radius: 14px;
    padding: 1.6rem 1.85rem;
    margin-bottom: 1.2rem;
    box-shadow: 0 14px 40px rgba(0, 0, 0, 0.35);
}}
.ll-page-hero::after {{
    content: "";
    position: absolute;
    top: 0; left: 0;
    width: 28%; height: 1px;
    background: linear-gradient(90deg, transparent, {CYAN_ELECTRIC}, transparent);
    animation: ll-scan-x 5.5s infinite linear;
}}
.ll-page-hero h1 {{
    color: {TEXT_PRIMARY} !important;
    margin: 0 0 0.45rem 0 !important;
    font-size: 2.0rem !important;
    letter-spacing: -0.03em !important;
}}
.ll-page-hero .sub {{
    color: {TEXT_SECONDARY} !important;
    font-size: 0.96rem;
    margin: 0;
    max-width: 720px;
}}

/* === Asymmetric HUD telemetry strip (replaces uniform card grids) ======= */
.ll-hud-strip {{
    display: grid;
    grid-template-columns: 1.55fr repeat(4, 1fr);
    background: linear-gradient(180deg, rgba(17, 24, 39, 0.72), rgba(11, 16, 27, 0.92));
    backdrop-filter: blur(10px);
    border: 1px solid {BORDER_HAIR};
    border-radius: 14px;
    margin-bottom: 1.4rem;
    overflow: hidden;
    position: relative;
    box-shadow: 0 14px 40px rgba(0, 0, 0, 0.30);
}}
.ll-hud-strip::before {{
    content: "";
    position: absolute;
    top: 0; left: 0;
    width: 100%; height: 1px;
    background: linear-gradient(90deg, transparent, {CYAN_ELECTRIC} 30%, {VIOLET_NEON} 70%, transparent);
    opacity: 0.55;
}}
.ll-hud-cell {{
    padding: 1.05rem 1.15rem;
    border-right: 1px solid rgba(145, 160, 181, 0.10);
    transition: background-color 180ms ease;
    position: relative;
}}
.ll-hud-cell:last-child {{ border-right: none; }}
.ll-hud-cell.primary {{
    background: linear-gradient(135deg, rgba(66, 232, 224, 0.14) 0%, rgba(17, 24, 39, 0.7) 100%);
    border-left: 3px solid {CYAN_ELECTRIC};
}}
.ll-hud-cell:hover {{ background: rgba(66, 232, 224, 0.06); }}
.ll-hud-label {{
    font-family: 'JetBrains Mono', ui-monospace, monospace;
    font-size: 0.66rem;
    letter-spacing: 0.16em;
    text-transform: uppercase;
    color: {TEXT_SECONDARY};
}}
.ll-hud-val {{
    font-family: 'Space Grotesk', sans-serif;
    font-size: 1.62rem;
    font-weight: 700;
    color: {TEXT_PRIMARY};
    font-variant-numeric: tabular-nums;
    margin-top: 0.28rem;
    line-height: 1.05;
    letter-spacing: -0.02em;
}}
.ll-hud-cell.primary .ll-hud-val {{ color: {CYAN_ELECTRIC}; }}
.ll-hud-sub {{
    font-family: 'JetBrains Mono', ui-monospace, monospace;
    font-size: 0.70rem;
    color: {TEXT_MUTED};
    margin-top: 0.30rem;
    line-height: 1.3;
}}

/* === Standard KPI grid (sub-pages) ===================================== */
.ll-kpi-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(175px, 1fr));
    gap: 0.85rem;
    margin-bottom: 1.3rem;
}}
.ll-kpi {{
    background: linear-gradient(180deg, rgba(17, 24, 39, 0.85), rgba(11, 16, 27, 0.92));
    border: 1px solid {BORDER_HAIR};
    border-top: 2px solid {CYAN_ELECTRIC};
    border-radius: 11px;
    padding: 0.95rem 1.05rem;
    transition: transform 180ms ease, border-color 180ms ease, box-shadow 180ms ease;
}}
.ll-kpi:hover {{
    transform: translateY(-2px);
    border-color: rgba(66, 232, 224, 0.45);
    box-shadow: 0 8px 28px rgba(0, 0, 0, 0.40);
}}
.ll-kpi .label {{
    font-family: 'JetBrains Mono', ui-monospace, monospace;
    color: {TEXT_SECONDARY} !important;
    font-size: 0.66rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.16em;
}}
.ll-kpi .value {{
    color: {TEXT_PRIMARY} !important;
    font-family: 'Space Grotesk', sans-serif;
    font-size: 1.55rem;
    font-weight: 700;
    font-variant-numeric: tabular-nums;
    line-height: 1.10;
    margin-top: 0.32rem;
}}
.ll-kpi .delta {{
    font-family: 'JetBrains Mono', ui-monospace, monospace;
    color: {TEXT_MUTED} !important;
    font-size: 0.71rem;
    margin-top: 0.28rem;
}}

/* === Card primitives ===================================================== */
.ll-card {{
    background: linear-gradient(180deg, rgba(17, 24, 39, 0.78), rgba(11, 16, 27, 0.92));
    backdrop-filter: blur(8px);
    border: 1px solid {BORDER_HAIR};
    border-radius: 12px;
    padding: 1.10rem 1.25rem;
    margin-bottom: 0.95rem;
    transition: border-color 160ms ease, transform 160ms ease, box-shadow 160ms ease;
    position: relative;
}}
.ll-card:hover {{
    border-color: rgba(66, 232, 224, 0.32);
    box-shadow: 0 0 24px rgba(66, 232, 224, 0.10);
}}
.ll-notice {{
    background: linear-gradient(135deg, rgba(245, 184, 75, 0.08), rgba(17, 24, 39, 0.85));
    border: 1px solid rgba(245, 184, 75, 0.32);
    border-left: 3px solid {AMBER_SIGNAL};
    border-radius: 10px;
    padding: 0.86rem 1.10rem;
    margin-bottom: 1.10rem;
    font-size: 0.88rem;
    color: {TEXT_SECONDARY};
    line-height: 1.55;
}}
.ll-notice strong {{ color: {AMBER_SIGNAL}; }}

/* === Panel header (chart / dossier frame) =============================== */
.ll-panel-head {{
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    padding-bottom: 0.55rem;
    margin-bottom: 0.55rem;
    border-bottom: 1px solid rgba(145, 160, 181, 0.16);
}}
.ll-panel-title {{
    font-family: 'Space Grotesk', sans-serif;
    font-size: 1.06rem;
    font-weight: 700;
    color: {TEXT_PRIMARY};
    letter-spacing: -0.015em;
}}
.ll-panel-meta {{
    font-family: 'JetBrains Mono', ui-monospace, monospace;
    font-size: 0.68rem;
    color: {CYAN_ELECTRIC};
    letter-spacing: 0.10em;
    text-transform: uppercase;
    opacity: 0.85;
}}

/* === Journey route dossier card ========================================= */
.ll-route-card {{
    position: relative;
    background: linear-gradient(135deg, rgba(17, 24, 39, 0.95), rgba(11, 16, 27, 0.98));
    border: 1px solid {BORDER_HAIR};
    border-radius: 14px;
    padding: 1.20rem 1.40rem;
    margin-bottom: 0.7rem;
    transition: transform 180ms ease, box-shadow 180ms ease, border-color 180ms ease;
    animation: ll-fade-up 0.35s ease;
}}
.ll-route-card:hover {{
    transform: translateY(-2px);
    box-shadow: 0 14px 38px rgba(0, 0, 0, 0.50);
}}
.ll-route-card.selected {{
    border-color: rgba(66, 232, 224, 0.60);
    box-shadow: 0 0 32px rgba(66, 232, 224, 0.16), inset 0 0 0 1px rgba(66, 232, 224, 0.10);
}}
.ll-route-card.selected::before {{
    content: "";
    position: absolute;
    top: 0; left: -1px; bottom: 0;
    width: 4px;
    background: linear-gradient(180deg, {CYAN_ELECTRIC}, {VIOLET_NEON});
    border-radius: 14px 0 0 14px;
}}
.ll-route-head {{
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    flex-wrap: wrap;
    gap: 0.85rem;
}}
.ll-route-left {{ display: flex; align-items: center; gap: 0.85rem; flex-wrap: wrap; }}
.ll-route-pill {{
    font-family: 'JetBrains Mono', ui-monospace, monospace;
    background: rgba(66, 232, 224, 0.10);
    border: 1px solid rgba(66, 232, 224, 0.42);
    color: {CYAN_ELECTRIC} !important;
    font-weight: 700;
    font-size: 0.96rem;
    padding: 0.36rem 0.78rem;
    border-radius: 8px;
    letter-spacing: 0.02em;
}}
.ll-dir-pill {{
    font-family: 'JetBrains Mono', ui-monospace, monospace;
    background: rgba(149, 117, 255, 0.14);
    border: 1px solid rgba(149, 117, 255, 0.40);
    color: {VIOLET_NEON} !important;
    font-size: 0.70rem;
    font-weight: 600;
    padding: 0.24rem 0.58rem;
    border-radius: 999px;
    text-transform: uppercase;
    letter-spacing: 0.08em;
}}
.ll-demand-pill {{
    display: inline-flex;
    align-items: center;
    gap: 0.50rem;
    padding: 0.36rem 0.82rem;
    border-radius: 999px;
    font-family: 'JetBrains Mono', ui-monospace, monospace;
    font-size: 0.74rem;
    font-weight: 600;
    letter-spacing: 0.04em;
}}
.ll-demand-dot {{
    width: 8px; height: 8px;
    border-radius: 999px;
    display: inline-block;
}}
.ll-route-od {{
    font-family: 'Space Grotesk', sans-serif;
    font-size: 1.0rem;
    font-weight: 600;
    color: {TEXT_PRIMARY};
    letter-spacing: -0.015em;
}}
.ll-route-metrics {{
    display: grid;
    grid-template-columns: repeat(4, minmax(110px, 1fr));
    gap: 0.85rem;
    margin-top: 1.0rem;
    padding-top: 0.95rem;
    border-top: 1px solid rgba(145, 160, 181, 0.16);
}}
.ll-rm-label {{
    font-family: 'JetBrains Mono', ui-monospace, monospace;
    font-size: 0.66rem;
    color: {TEXT_SECONDARY};
    text-transform: uppercase;
    letter-spacing: 0.10em;
}}
.ll-rm-val {{
    font-family: 'Space Grotesk', sans-serif;
    font-size: 1.10rem;
    font-weight: 700;
    color: {TEXT_PRIMARY};
    font-variant-numeric: tabular-nums;
    margin-top: 0.22rem;
}}

/* === Animated horizontal route tracer (Journey Planner hero) ============ */
.ll-tracer-box {{
    position: relative;
    overflow: hidden;
    background:
        radial-gradient(circle at 90% 50%, rgba(149, 117, 255, 0.08), transparent 50%),
        linear-gradient(180deg, rgba(11, 16, 27, 0.95), rgba(7, 9, 16, 0.99));
    border: 1px solid rgba(66, 232, 224, 0.32);
    border-radius: 14px;
    padding: 1.20rem 1.30rem;
    margin: 0.85rem 0 1.10rem 0;
    box-shadow: 0 14px 40px rgba(0, 0, 0, 0.50), inset 0 1px 0 rgba(66, 232, 224, 0.10);
}}
.ll-tracer-box::before {{
    content: "";
    position: absolute;
    top: 0; left: 0;
    width: 35%; height: 2px;
    background: linear-gradient(90deg, transparent, {CYAN_ELECTRIC}, transparent);
    animation: ll-scan-x 5.0s infinite linear;
}}
.ll-tracer-box::after {{
    content: "";
    position: absolute;
    inset: 0;
    background: repeating-linear-gradient(
        90deg,
        transparent 0,
        transparent 23px,
        rgba(66, 232, 224, 0.05) 23px,
        rgba(66, 232, 224, 0.05) 24px
    );
    pointer-events: none;
    z-index: 0;
    opacity: 0.45;
}}
.ll-tracer-track {{
    display: flex;
    align-items: flex-start;
    gap: 0;
    overflow-x: auto;
    padding: 0.85rem 0.25rem 0.55rem 0.25rem;
    position: relative;
    z-index: 1;
}}
.ll-tr-node-wrap {{
    position: relative;
    display: flex;
    flex-direction: column;
    align-items: center;
    min-width: 110px;
    max-width: 130px;
    flex-shrink: 0;
    animation: ll-fade-in 0.4s ease backwards;
    animation-delay: calc(var(--idx, 0) * 80ms);
}}
.ll-tr-dot {{
    width: 16px; height: 16px;
    border-radius: 999px;
    background: {BG_VOID};
    border: 3px solid {CYAN_ELECTRIC};
    transition: transform 160ms ease, box-shadow 160ms ease;
    z-index: 2;
    position: relative;
}}
.ll-tr-node-wrap:hover .ll-tr-dot {{
    transform: scale(1.35);
    box-shadow: 0 0 18px {CYAN_ELECTRIC};
}}
.ll-tr-dot.origin {{
    background: {CYAN_ELECTRIC};
    box-shadow: 0 0 16px {CYAN_ELECTRIC};
    animation: ll-pulse-node 2.0s infinite ease-in-out;
}}
.ll-tr-dot.dest {{
    border-color: {MAGENTA_NEON};
    background: {MAGENTA_NEON};
    box-shadow: 0 0 16px rgba(232, 79, 168, 0.60);
    animation: ll-pulse-violet 2.0s infinite ease-in-out;
}}
.ll-tr-name {{
    font-size: 0.78rem;
    font-weight: 600;
    color: {TEXT_PRIMARY};
    text-align: center;
    margin-top: 0.55rem;
    line-height: 1.25;
}}
.ll-tr-sub {{
    font-family: 'JetBrains Mono', ui-monospace, monospace;
    font-size: 0.64rem;
    color: {TEXT_SECONDARY};
    margin-top: 0.20rem;
    letter-spacing: 0.05em;
}}
.ll-tr-link {{
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    min-width: 70px;
    padding-top: 4px;
    flex-shrink: 0;
}}
.ll-tr-svg {{ width: 70px; height: 16px; overflow: visible; }}
.ll-tr-flow {{
    stroke-dasharray: 8 6;
    animation: ll-trace-dash 1.4s linear infinite;
}}

/* === Stop-by-stop vertical metro timeline =============================== */
.ll-timeline {{ padding: 0.5rem 0.25rem; }}
.ll-tl-step {{
    display: grid;
    grid-template-columns: 30px 1fr auto;
    gap: 0.85rem;
    align-items: start;
}}
.ll-tl-rail {{ display: flex; flex-direction: column; align-items: center; }}
.ll-tl-dot {{
    width: 14px; height: 14px;
    border-radius: 999px;
    border: 2.5px solid {CYAN_ELECTRIC};
    background: {BG_VOID};
    margin-top: 4px;
}}
.ll-tl-dot.origin {{
    border-color: {CYAN_ELECTRIC};
    background: {CYAN_ELECTRIC};
    box-shadow: 0 0 12px {CYAN_ELECTRIC};
}}
.ll-tl-dot.dest {{
    border-color: {MAGENTA_NEON};
    background: {MAGENTA_NEON};
    box-shadow: 0 0 12px {MAGENTA_NEON};
}}
.ll-tl-line {{ width: 2.5px; min-height: 30px; border-radius: 2px; margin: 3px 0; opacity: 0.55; }}
.ll-tl-stop {{
    font-family: 'Space Grotesk', sans-serif;
    font-weight: 600;
    color: {TEXT_PRIMARY};
    font-size: 0.94rem;
    line-height: 1.30;
}}
.ll-tl-seg {{
    font-family: 'JetBrains Mono', ui-monospace, monospace;
    font-size: 0.74rem;
    color: {TEXT_SECONDARY};
    padding: 0.20rem 0 0.55rem 0;
    letter-spacing: 0.02em;
}}
.ll-tl-badge {{
    font-family: 'JetBrains Mono', ui-monospace, monospace;
    font-size: 0.72rem;
    font-weight: 600;
    padding: 0.22rem 0.58rem;
    border-radius: 999px;
    font-variant-numeric: tabular-nums;
    white-space: nowrap;
}}

/* === Animated corridor schematic (Segment Explorer signature) =========== */
.ll-corridor-shell {{
    position: relative;
    overflow: hidden;
    background:
        radial-gradient(circle at 50% 0%, rgba(149, 117, 255, 0.10), transparent 50%),
        linear-gradient(180deg, rgba(11, 16, 27, 0.95), rgba(7, 9, 16, 0.99));
    border: 1px solid rgba(149, 117, 255, 0.32);
    border-radius: 15px;
    padding: 1.20rem 1.20rem;
    margin-bottom: 1.20rem;
    box-shadow: 0 16px 44px rgba(0, 0, 0, 0.45), inset 0 1px 0 rgba(149, 117, 255, 0.08);
}}
.ll-corridor-shell::before {{
    content: "";
    position: absolute;
    top: 0; left: 0;
    width: 50%; height: 2px;
    background: linear-gradient(90deg, transparent, {VIOLET_NEON}, {CYAN_ELECTRIC}, transparent);
    animation: ll-scan-x 5.5s infinite linear;
}}
.ll-corridor-shell::after {{
    content: "";
    position: absolute;
    inset: 0;
    background: repeating-linear-gradient(
        90deg,
        transparent 0,
        transparent 47px,
        rgba(149, 117, 255, 0.06) 47px,
        rgba(149, 117, 255, 0.06) 48px
    );
    pointer-events: none;
    z-index: 0;
    opacity: 0.5;
}}
.ll-corridor {{
    display: flex;
    align-items: center;
    gap: 0;
    overflow-x: auto;
    padding: 0.7rem 0.30rem 0.85rem 0.30rem;
    position: relative;
    z-index: 1;
}}
.ll-corr-item {{ display: flex; align-items: center; flex-shrink: 0; }}
.ll-corr-stop {{
    background: linear-gradient(180deg, {BG_ELEVATED} 0%, {BG_PANEL} 100%);
    border: 1px solid rgba(66, 232, 224, 0.28);
    border-radius: 10px;
    padding: 0.50rem 0.80rem;
    font-family: 'Space Grotesk', sans-serif;
    font-size: 0.80rem;
    font-weight: 600;
    color: {TEXT_PRIMARY};
    max-width: 148px;
    text-align: center;
    transition: border-color 160ms ease, box-shadow 160ms ease, transform 160ms ease;
    white-space: nowrap;
}}
.ll-corr-stop:hover {{
    border-color: {CYAN_ELECTRIC};
    box-shadow: 0 0 18px rgba(66, 232, 224, 0.30);
    transform: translateY(-2px);
}}
.ll-corr-link {{
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: 0 0.40rem;
    min-width: 90px;
}}
.ll-corr-vol {{
    font-family: 'JetBrains Mono', ui-monospace, monospace;
    font-size: 0.72rem;
    font-weight: 700;
    font-variant-numeric: tabular-nums;
    letter-spacing: 0.02em;
}}

/* === Section divider eyebrow ============================================ */
.ll-section-eyebrow {{
    display: flex;
    align-items: center;
    gap: 0.7rem;
    margin: 1.4rem 0 0.85rem 0;
}}
.ll-section-eyebrow .num {{
    font-family: 'JetBrains Mono', ui-monospace, monospace;
    font-size: 0.72rem;
    color: {CYAN_ELECTRIC};
    background: rgba(66, 232, 224, 0.10);
    border: 1px solid rgba(66, 232, 224, 0.42);
    padding: 0.30rem 0.66rem;
    border-radius: 6px;
    letter-spacing: 0.10em;
}}
.ll-section-eyebrow .lbl {{
    font-family: 'Space Grotesk', sans-serif;
    font-size: 1.12rem;
    font-weight: 700;
    color: {TEXT_PRIMARY};
    letter-spacing: -0.015em;
}}
.ll-section-eyebrow .line {{
    flex: 1;
    height: 1px;
    background: linear-gradient(90deg, rgba(66, 232, 224, 0.35), transparent);
}}

/* === Mobile / responsive ================================================ */
@media (max-width: 1080px) {{
    .ll-hud-strip {{ grid-template-columns: repeat(3, 1fr); }}
    .ll-hud-cell.primary {{ grid-column: span 3; }}
}}
@media (max-width: 860px) {{
    .ll-hud-strip {{ grid-template-columns: repeat(2, 1fr); }}
    .ll-hud-cell.primary {{ grid-column: span 2; }}
}}
@media (max-width: 720px) {{
    .block-container {{
        padding-left: 0.9rem !important;
        padding-right: 0.9rem !important;
        padding-top: 0.7rem !important;
    }}
    .ll-editorial-hero {{ padding: 1.5rem 1.3rem; }}
    .ll-route-metrics {{ grid-template-columns: repeat(2, minmax(100px, 1fr)); }}
    .ll-kpi-grid {{ grid-template-columns: repeat(2, minmax(130px, 1fr)); }}
}}
"""
    compact_css = "\n".join(line for line in css_body.splitlines() if line.strip())
    if hasattr(st, "html"):
        st.html(f"<style>{compact_css}</style>")
    else:
        st.markdown(f"<style>{compact_css}</style>", unsafe_allow_html=True)


# ============================================================================
# BRAND & HEADER HELPERS
# ============================================================================
def brand_header() -> str:
    """Return the LOADLENS logo lockup for the sidebar."""
    return (
        '<div class="ll-brand">'
        '<div class="ll-brand-icon">'
        '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">'
        '<circle cx="12" cy="12" r="9" stroke="#42E8E0" stroke-width="1.4" stroke-dasharray="3 2"/>'
        '<path d="M7 15L10.5 11.5L13.5 13.5L17 9" stroke="#9575FF" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>'
        '<circle cx="7" cy="15" r="1.6" fill="#42E8E0"/>'
        '<circle cx="17" cy="9" r="1.6" fill="#E84FA8"/>'
        '</svg>'
        '</div>'
        '<div>'
        '<div class="ll-brand-title">LOADLENS</div>'
        '<div class="ll-brand-sub">Urban Intelligence // 02.626</div>'
        '</div>'
        '</div>'
    )


def editorial_hero(eyebrow: str, title: str, subtitle: str, badge: str | None = None) -> None:
    """Render the cinematic opening hero used on the Overview page."""
    import streamlit as st
    badge_html = (
        f'<div class="ll-hero-badge" style="margin-top:1.1rem;display:inline-block;">{html.escape(badge)}</div>'
        if badge else ""
    )
    st.markdown(
        '<div class="ll-editorial-hero">'
        f'<div class="ll-editorial-eyebrow">{html.escape(eyebrow)}</div>'
        f'<h1 class="ll-editorial-h1">{html.escape(title)}</h1>'
        f'<p class="ll-editorial-sub">{html.escape(subtitle)}</p>'
        f'{badge_html}'
        '</div>',
        unsafe_allow_html=True,
    )


def page_hero(eyebrow: str, title: str, subtitle: str, badge: str | None = None) -> None:
    """Render the compact hero used on each sub-page."""
    import streamlit as st
    badge_html = (
        f'<div class="ll-hero-badge" style="margin-top:0.85rem;display:inline-block;">{html.escape(badge)}</div>'
        if badge else ""
    )
    st.markdown(
        '<div class="ll-page-hero">'
        f'<div class="ll-editorial-eyebrow" style="margin-bottom:0.55rem;">{html.escape(eyebrow)}</div>'
        f'<h1>{html.escape(title)}</h1>'
        f'<p class="sub">{html.escape(subtitle)}</p>'
        f'{badge_html}'
        '</div>',
        unsafe_allow_html=True,
    )


def hud_metrics_strip(items: Iterable[Tuple[str, str, str]]) -> None:
    """Asymmetric 5-cell telemetry strip (1st cell highlighted)."""
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


def section_eyebrow(num: str, label: str) -> None:
    import streamlit as st
    st.markdown(
        f'<div class="ll-section-eyebrow">'
        f'<div class="num">{html.escape(num)}</div>'
        f'<div class="lbl">{html.escape(label)}</div>'
        f'<div class="line"></div>'
        f'</div>',
        unsafe_allow_html=True,
    )


# ============================================================================
# ANIMATED ROUTE TRACER (Journey Planner signature hero)
# ============================================================================
def animated_route_tracer_html(opt: dict, max_nodes: int = 24) -> str:
    """Render an animated SVG/HTML route trace for the currently selected journey option."""
    seg_df = opt.get("segments")
    if seg_df is None or len(seg_df) == 0:
        return ""

    has_load = opt.get("has_matched_load", True)
    route_lbl = html.escape(str(opt.get("route", "")))
    dir_lbl = html.escape(str(opt.get("direction", "")))
    dur = opt.get("estimated_duration_min")
    dur_txt = f"{dur:.1f} min · GTFS" if dur is not None else "Duration N/A (no GTFS)"

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
            color = TEXT_SECONDARY
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


# ============================================================================
# STOP-BY-STOP METRO TIMELINE
# ============================================================================
def stop_timeline_html(segments_df, origin: str, destination: str) -> str:
    """Render a vertical metro-style stop-by-stop timeline from real segment rows."""
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
            tier_lbl, color, bg = ("Data unavailable", TEXT_SECONDARY, "rgba(145, 160, 181, 0.12)")
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


# ============================================================================
# ANIMATED CORRIDOR STRIP (Segment Explorer signature)
# ============================================================================
def corridor_strip_html(segments_df, max_segments: int = 35, highlight_idx: Optional[int] = None) -> str:
    """Render an animated futuristic corridor schematic for the Segment Explorer."""
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
        stroke_w = max(2.8, min(7.5, 2.8 + (vol / max_load) * 4.6))
        is_sel = highlight_idx is not None and i == highlight_idx
        if is_sel:
            sel_style = (
                f"border-color:{CYAN_ELECTRIC};box-shadow:0 0 22px rgba(66,232,224,0.50),"
                f" inset 0 0 0 1px rgba(66,232,224,0.30);"
                f"background:linear-gradient(180deg, rgba(66,232,224,0.18), rgba(11,16,27,0.95));"
            )
        else:
            sel_style = ""
        if i == 0:
            parts.append(
                f'<div class="ll-corr-item"><div class="ll-corr-stop" style="{sel_style}">{html.escape(str(row.from_norm).title())}</div></div>'
            )
        parts.append(
            f'<div class="ll-corr-item">'
            f'<div class="ll-corr-link">'
            f'<div class="ll-corr-vol" style="color:{color};">{vol:,}</div>'
            f'<svg width="90" height="14" viewBox="0 0 90 14" style="overflow:visible;">'
            f'<line x1="0" y1="7" x2="90" y2="7" stroke="{color}" stroke-opacity="0.28" stroke-width="{stroke_w + 2:.1f}" stroke-linecap="round"/>'
            f'<line class="ll-tr-flow" x1="0" y1="7" x2="90" y2="7" stroke="{color}" stroke-width="{stroke_w:.1f}" stroke-linecap="round"/>'
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
