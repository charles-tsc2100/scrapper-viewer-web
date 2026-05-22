"""
Design System: "Today Style 2100 — Luxury Dark"
Brand-aligned theme for the BOQ → Warehouse Form Converter.

Follows the Today Style 2100 CI:
  - Dark Tone First (Luxury Minimal)
  - Brand Core: Navy #1E1E45 + Teal #4E9B8B
  - Champagne Gold #C5A059 for premium punctuation
  - Montserrat (EN) + IBM Plex Sans Thai (TH)

Drop-in replacement for the previous "Technical Curator" theme.
Public API (the names used by app.py and cell_selector.py) is preserved.
"""
import os
import sys
import tkinter as tk
from tkinter import font as tkfont

# ═══════════════════════════════════════════════════════════════
# COLOR TOKENS — Today Style 2100 brand
# ═══════════════════════════════════════════════════════════════

# ── Brand core ──────────────────────────────────────────────
TS_NAVY            = "#1E1E45"
TS_TEAL            = "#4E9B8B"

# ── Other brand tones ──────────────────────────────────────
TS_DEEP_FOREST     = "#1D3D37"
TS_DARK_SEAFOAM    = "#346B60"
TS_SOFT_SAGE       = "#82BDB1"
TS_PALE_MINT       = "#B8DDDD"
TS_MIDNIGHT        = "#0D0D1F"
TS_ROYAL_TWILIGHT  = "#34346B"
TS_MUTED_INDIGO    = "#4D4D91"
TS_SOFT_PERIWINKLE = "#7575B5"
TS_CHARCOAL        = "#1F2937"
TS_GOLD            = "#C5A059"   # Champagne Gold

# ── Surface hierarchy (dark tone) ──────────────────────────
SURFACE            = TS_MIDNIGHT          # Level 0  — app background
SURFACE_LOW        = "#14143A"            # Level 1  — cards
SURFACE_HIGH       = "#1B1B36"            # Level 2  — toolbars, table headers
SURFACE_WHITE      = "#0D0D1F"            # Input fields (still dark)

# Borders / dividers
GHOST_BORDER       = "#2A2A55"
GHOST_BORDER_FOCUS = TS_TEAL
DIVIDER            = "#34346B"

# ── Primary identity ────────────────────────────────────────
PRIMARY            = TS_TEAL
PRIMARY_ACCENT     = TS_TEAL
PRIMARY_HOVER      = TS_SOFT_SAGE
PRIMARY_DARK       = TS_DARK_SEAFOAM

# ── Text colors ────────────────────────────────────────────
TEXT_PRIMARY       = "#FFFFFF"
TEXT_SECONDARY     = "#E0E0E0"
TEXT_TERTIARY      = TS_SOFT_PERIWINKLE   # #7575B5
TEXT_ON_PRIMARY    = TS_MIDNIGHT
TEXT_ON_ACCENT     = TS_MIDNIGHT
TEXT_ACCENT_GOLD   = TS_GOLD

# ── Header ─────────────────────────────────────────────────
HEADER_BG          = SURFACE_LOW
HEADER_BG_GRADIENT = SURFACE_LOW
HEADER_TEXT        = "#FFFFFF"
HEADER_SUBTLE      = TS_SOFT_PERIWINKLE
HEADER_DIVIDER     = TS_GOLD

# ── Semantic colors ────────────────────────────────────────
SUCCESS            = TS_SOFT_SAGE          # #82BDB1
SUCCESS_BG         = "#16332D"
WARNING            = "#E5C387"
WARNING_BG         = "#3A2D14"
ERROR              = "#E57373"
ERROR_BG           = "#3F1E1E"
INFO               = "#8BA7C4"
INFO_BG            = "#1A2A4A"

# ── Field-assignment colors (Cell Selector) ────────────────
FIELD_COLORS_MAP = {
    "door_code":     {"bg": "#1A2A4A", "fg": "#8BA7C4"},
    "room_name":     {"bg": "#16332D", "fg": "#82BDB1"},
    "dimensions":    {"bg": "#3A2D14", "fg": "#E5C387"},
    "brand":         {"bg": "#252557", "fg": "#7575B5"},
    "model":         {"bg": "#3F1E1E", "fg": "#E57373"},
    "description":   {"bg": "#1E3A35", "fg": "#76C4B4"},
    "quantity":      {"bg": "#3A2F18", "fg": "#D4B574"},
    "unit_price":    {"bg": "#1E3A33", "fg": "#82BDB1"},
    "net_indicator": {"bg": "#3F1E1E", "fg": "#C67070"},
    "start_row":     {"bg": "#3D2F14", "fg": TS_GOLD},
    "cv_door_code":  {"bg": "#1A2A4A", "fg": "#8BA7C4"},
    "cv_room_name":  {"bg": "#16332D", "fg": "#82BDB1"},
    "cv_quantity":   {"bg": "#3A2F18", "fg": "#D4B574"},
    "cv_start_row":  {"bg": "#3D2F14", "fg": TS_GOLD},
}


# ═══════════════════════════════════════════════════════════════
# TYPOGRAPHY — per Today Style 2100 CI
# ═══════════════════════════════════════════════════════════════

FONT_HEADLINE = "Montserrat"
FONT_BODY     = "IBM Plex Sans Thai"
FONT_FALLBACK = "Segoe UI"
FONT_MONO     = "Consolas"

SIZE_HEADLINE_LG = 18
SIZE_HEADLINE_MD = 14
SIZE_HEADLINE_SM = 12
SIZE_BODY_MD     = 10
SIZE_BODY_SM     = 9
SIZE_LABEL_SM    = 8


# ═══════════════════════════════════════════════════════════════
# SPACING TOKENS
# ═══════════════════════════════════════════════════════════════

SPACE_1 = 4
SPACE_2 = 8
SPACE_3 = 12
SPACE_4 = 16
SPACE_5 = 20
SPACE_6 = 24
SPACE_8 = 32

RADIUS_SM = 4
RADIUS_MD = 6
RADIUS_LG = 10


# ═══════════════════════════════════════════════════════════════
# FONT LOADING (Windows private install via GDI32)
# ═══════════════════════════════════════════════════════════════

_fonts_loaded = False


def _get_fonts_dir():
    if getattr(sys, "frozen", False):
        base = sys._MEIPASS
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, "fonts")


def load_fonts():
    """Load bundled brand fonts on Windows."""
    global _fonts_loaded
    if _fonts_loaded:
        return

    fonts_dir = _get_fonts_dir()
    if not os.path.isdir(fonts_dir):
        _fonts_loaded = True
        return

    if sys.platform == "win32":
        try:
            import ctypes
            FR_PRIVATE = 0x10
            gdi32 = ctypes.windll.gdi32
            for fname in os.listdir(fonts_dir):
                if fname.lower().endswith((".ttf", ".otf")):
                    fpath = os.path.join(fonts_dir, fname)
                    if gdi32.AddFontResourceExW(fpath, FR_PRIVATE, 0) > 0:
                        print(f"Loaded font: {fname}")
        except Exception as e:
            print(f"Font loading warning: {e}")

    _fonts_loaded = True


def get_font(role="body", size=None, bold=False):
    """Get a font tuple for the given role.
    Roles: 'headline', 'body', 'mono', 'label'
    """
    if role == "headline":
        family = FONT_HEADLINE
        sz = size or SIZE_HEADLINE_MD
    elif role == "mono":
        family = FONT_MONO
        sz = size or SIZE_BODY_MD
    elif role == "label":
        family = FONT_BODY
        sz = size or SIZE_LABEL_SM
    else:
        family = FONT_BODY
        sz = size or SIZE_BODY_MD

    return (family, sz, "bold" if bold else "normal")


def font_available(name):
    try:
        return name in tkfont.families()
    except Exception:
        return False


def resolve_fonts():
    """After Tk is initialized, fall back if brand fonts aren't installed."""
    global FONT_HEADLINE, FONT_BODY
    if not font_available(FONT_HEADLINE):
        FONT_HEADLINE = FONT_FALLBACK
    if not font_available(FONT_BODY):
        if font_available("Sarabun"):
            FONT_BODY = "Sarabun"
        else:
            FONT_BODY = FONT_FALLBACK


# ═══════════════════════════════════════════════════════════════
# TTK STYLES — Luxury Dark
# ═══════════════════════════════════════════════════════════════

def configure_ttk_styles(style):
    """Configure ttk styles to match the Luxury Dark design system."""

    style.configure(".", background=SURFACE, font=get_font("body"))

    # Frames
    style.configure("TFrame",            background=SURFACE)
    style.configure("Surface.TFrame",    background=SURFACE)
    style.configure("SurfaceLow.TFrame", background=SURFACE_LOW)
    style.configure("White.TFrame",      background=SURFACE_LOW)
    style.configure("Header.TFrame",     background=HEADER_BG)

    # Labels
    style.configure("TLabel",
                    background=SURFACE,
                    foreground=TEXT_PRIMARY,
                    font=get_font("body"))
    style.configure("Secondary.TLabel",
                    background=SURFACE,
                    foreground=TEXT_SECONDARY,
                    font=get_font("body"))
    style.configure("Hint.TLabel",
                    background=SURFACE,
                    foreground=TEXT_TERTIARY,
                    font=get_font("label"))
    style.configure("SurfaceLow.TLabel",
                    background=SURFACE_LOW,
                    foreground=TEXT_PRIMARY,
                    font=get_font("body"))
    style.configure("Gold.TLabel",
                    background=SURFACE,
                    foreground=TS_GOLD,
                    font=get_font("body", bold=True))

    # LabelFrames
    style.configure("TLabelframe",
                    background=SURFACE_LOW,
                    foreground=TEXT_PRIMARY,
                    borderwidth=0, relief="flat")
    style.configure("TLabelframe.Label",
                    background=SURFACE,
                    foreground=TS_GOLD,
                    font=get_font("headline", SIZE_HEADLINE_SM, bold=True))

    # Entry
    style.configure("TEntry",
                    fieldbackground=SURFACE_WHITE,
                    foreground=TEXT_PRIMARY,
                    insertcolor=TS_TEAL,
                    bordercolor=GHOST_BORDER,
                    lightcolor=GHOST_BORDER,
                    darkcolor=GHOST_BORDER,
                    borderwidth=1, relief="solid")
    style.map("TEntry",
              bordercolor=[("focus", GHOST_BORDER_FOCUS)],
              lightcolor=[("focus", GHOST_BORDER_FOCUS)],
              darkcolor=[("focus", GHOST_BORDER_FOCUS)])

    # Checkbutton
    style.configure("TCheckbutton",
                    background=SURFACE_LOW,
                    foreground=TEXT_PRIMARY,
                    font=get_font("body"))
    style.map("TCheckbutton",
              background=[("active", SURFACE_LOW)],
              foreground=[("active", TEXT_PRIMARY)])

    # Buttons
    style.configure("Primary.TButton",
                    background=PRIMARY_ACCENT,
                    foreground=TEXT_ON_ACCENT,
                    font=get_font("body", bold=True),
                    borderwidth=0, relief="flat",
                    padding=(SPACE_4, SPACE_2))
    style.map("Primary.TButton",
              background=[("active", PRIMARY_HOVER), ("pressed", PRIMARY_DARK)])

    style.configure("Secondary.TButton",
                    background=SURFACE_LOW,
                    foreground=TEXT_SECONDARY,
                    font=get_font("body"),
                    borderwidth=1, relief="solid",
                    padding=(SPACE_3, SPACE_2))
    style.map("Secondary.TButton",
              background=[("active", SURFACE_HIGH)],
              foreground=[("active", TEXT_PRIMARY)])

    style.configure("Tertiary.TButton",
                    background=SURFACE,
                    foreground=TS_TEAL,
                    font=get_font("body"),
                    borderwidth=0, relief="flat",
                    padding=(SPACE_3, SPACE_2))
    style.map("Tertiary.TButton",
              foreground=[("active", TS_SOFT_SAGE)])

    style.configure("Accent.TButton",
                    background=PRIMARY_ACCENT,
                    foreground=TEXT_ON_ACCENT,
                    font=get_font("body", bold=True),
                    borderwidth=0, relief="flat",
                    padding=(SPACE_4, SPACE_2))
    style.map("Accent.TButton",
              background=[("active", PRIMARY_HOVER), ("pressed", PRIMARY_DARK)])

    style.configure("Gold.TButton",
                    background=TS_GOLD,
                    foreground=TS_MIDNIGHT,
                    font=get_font("body", bold=True),
                    borderwidth=0, relief="flat",
                    padding=(SPACE_4, SPACE_2))
    style.map("Gold.TButton",
              background=[("active", "#D4B574"), ("pressed", "#B8954D")])

    # Scrollbar
    style.configure("TScrollbar",
                    background=SURFACE_LOW,
                    troughcolor=SURFACE,
                    bordercolor=SURFACE,
                    arrowcolor=TEXT_TERTIARY,
                    borderwidth=0)
    style.map("TScrollbar",
              background=[("active", DIVIDER)])

    # Progressbar
    style.configure("TProgressbar",
                    background=TS_TEAL,
                    troughcolor=SURFACE_LOW,
                    bordercolor=SURFACE_LOW,
                    lightcolor=TS_TEAL,
                    darkcolor=TS_TEAL,
                    borderwidth=0)

    # Notebook
    style.configure("TNotebook",
                    background=SURFACE,
                    borderwidth=0,
                    tabmargins=(0, 0, 0, 0))
    style.configure("TNotebook.Tab",
                    background=SURFACE,
                    foreground=TEXT_TERTIARY,
                    font=get_font("body"),
                    padding=(SPACE_4, SPACE_2),
                    borderwidth=0)
    style.map("TNotebook.Tab",
              background=[("selected", SURFACE_LOW)],
              foreground=[("selected", TEXT_PRIMARY)],
              expand=[("selected", (0, 0, 0, 0))])
