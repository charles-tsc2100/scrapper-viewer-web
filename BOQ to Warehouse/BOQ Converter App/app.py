"""
BOQ to Warehouse Form Converter - Desktop Application
Today Style 2100 Co., Ltd.

Design System: "Today Style 2100 — Luxury Dark"
"""
import os
import sys
import logging
import threading
import webbrowser
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from datetime import datetime

if getattr(sys, 'frozen', False):
    BASE_DIR = sys._MEIPASS
    sys.path.insert(0, BASE_DIR)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, BASE_DIR)

from boq_parser import parse_boq_file, parse_multiple_boq_files
from boq_config import BOQConfig, BOQSheetConfig, CoverSheetConfig, detect_config
from warehouse_generator import generate_warehouse_form
from cell_selector import CellSelectorDialog
from i18n import t, get_lang, set_lang, on_lang_change
from version import APP_VERSION, APP_BUILD_DATE, CHANGELOG
import theme as T
import db_logger

PROJECT_TYPES = [
    "Commercial", "Data Center", "Education", "Government",
    "Hospitality", "Industrial", "Leisure & Recreation",
    "Residential", "Wellness",
]

import io

_log_stream = io.StringIO()
_log_handler = logging.StreamHandler(_log_stream)
_log_handler.setFormatter(logging.Formatter(
    "%(asctime)s  %(levelname)-8s  %(message)s", datefmt="%Y-%m-%d %H:%M:%S"))
logger = logging.getLogger("boq_converter")
logger.setLevel(logging.DEBUG)
logger.addHandler(_log_handler)
logger.info("App started  v%s", APP_VERSION)

LOGOS_DIR = os.path.join(BASE_DIR, "logos")


def _find_logo(filename):
    candidates = [
        os.path.join(LOGOS_DIR, filename),
        os.path.join(BASE_DIR, "logos", filename),
        os.path.join(os.path.dirname(BASE_DIR), "logos", filename),
    ]
    script_dir = os.path.dirname(os.path.abspath(__file__))
    candidates.append(os.path.join(script_dir, "logos", filename))
    for path in candidates:
        if os.path.exists(path):
            return path
    return None


class BOQConverterApp:
    def __init__(self):
        T.load_fonts()

        self.root = tk.Tk()
        self.root.title(t("app_title"))
        self.root.geometry("1100x760")
        self.root.minsize(900, 640)
        self.root.configure(bg=T.SURFACE)

        T.resolve_fonts()

        style = ttk.Style(self.root)
        T.configure_ttk_styles(style)

        # Style the Combobox popdown listbox (classic Tk widget, not themed by ttk)
        self.root.option_add("*TCombobox*Listbox.background",       T.SURFACE_LOW)
        self.root.option_add("*TCombobox*Listbox.foreground",       T.TEXT_PRIMARY)
        self.root.option_add("*TCombobox*Listbox.selectBackground", T.PRIMARY_ACCENT)
        self.root.option_add("*TCombobox*Listbox.selectForeground", T.TEXT_ON_ACCENT)
        self.root.option_add("*TCombobox*Listbox.font",             T.get_font("body"))

        icon_path = _find_logo("app_icon.ico")
        if icon_path:
            try:
                self.root.iconbitmap(icon_path)
            except Exception:
                pass

        self.boq_files = []
        self.parsed_categories = []
        self.qty_map = {}
        self.include_pricing = tk.BooleanVar(value=True)
        self.use_unit_price = tk.BooleanVar(value=False)
        self.combine_door_types = tk.BooleanVar(value=True)
        self.project_name = tk.StringVar(value="")
        self.project_category = tk.StringVar(value="")
        self.project_id = None         # Lark record_id, or None for custom projects
        self._original_category = ""   # category from Lark at pick time; "" means write-back needed if user fills it
        self._projects_cache = []      # list of dicts: {id, name, category, status, ...}
        self.config = BOQConfig()
        self.config_detected = False
        self._images = {}

        self._build_ui()
        on_lang_change(self._on_language_change)

    # ─────────────────────────────────────────────────────────
    # UI CONSTRUCTION
    # ─────────────────────────────────────────────────────────

    def _build_ui(self):
        self.main = tk.Frame(self.root, bg=T.SURFACE)
        self.main.pack(fill=tk.BOTH, expand=True)
        self._build_header()
        self._build_stepper()
        self._build_action_bar()
        self._build_main_content()

    def _build_header(self):
        header = tk.Frame(self.main, bg=T.SURFACE_LOW)
        header.pack(fill=tk.X)
        self._header_frame = header

        inner = tk.Frame(header, bg=T.SURFACE_LOW, padx=T.SPACE_6, pady=T.SPACE_4)
        inner.pack(fill=tk.X)

        # Logo
        logo_path = _find_logo("logo_title.png")
        if logo_path:
            try:
                self._images["title_logo"] = tk.PhotoImage(file=logo_path)
                tk.Label(inner, image=self._images["title_logo"],
                         bg=T.SURFACE_LOW).pack(side=tk.LEFT, padx=(0, T.SPACE_4))
            except Exception:
                self._text_logo(inner)
        else:
            self._text_logo(inner)

        # Gold divider
        tk.Frame(inner, width=1, bg=T.TS_GOLD).pack(
            side=tk.LEFT, fill=tk.Y, padx=(0, T.SPACE_4), pady=2)

        # Title block
        title_block = tk.Frame(inner, bg=T.SURFACE_LOW)
        title_block.pack(side=tk.LEFT, fill=tk.Y)

        self._title_label = tk.Label(
            title_block, text=t("header_title"),
            font=T.get_font("headline", T.SIZE_HEADLINE_LG, bold=True),
            fg=T.TEXT_PRIMARY, bg=T.SURFACE_LOW)
        self._title_label.pack(anchor="w")

        self._subtitle_label = tk.Label(
            title_block, text=t("header_subtitle"),
            font=T.get_font("body", T.SIZE_BODY_SM),
            fg=T.TEXT_TERTIARY, bg=T.SURFACE_LOW)
        self._subtitle_label.pack(anchor="w")

        # Right side: lang button (teal pill)
        self._lang_btn = tk.Button(
            inner, text=t("lang_btn"),
            font=T.get_font("body", T.SIZE_BODY_SM, bold=True),
            fg=T.TEXT_ON_PRIMARY, bg=T.PRIMARY,
            activebackground=T.PRIMARY_HOVER, activeforeground=T.TEXT_ON_PRIMARY,
            relief="flat", borderwidth=0, cursor="hand2",
            padx=12, pady=4,
            command=self._toggle_language)
        self._lang_btn.pack(side=tk.RIGHT, padx=(T.SPACE_2, 0))

        self._about_btn = tk.Button(
            inner, text=t("about_btn"),
            font=T.get_font("body", T.SIZE_BODY_SM),
            fg=T.TEXT_SECONDARY, bg=T.SURFACE_LOW,
            activebackground=T.SURFACE_LOW, activeforeground=T.TEXT_PRIMARY,
            relief="flat", borderwidth=0, cursor="hand2",
            padx=8, pady=4,
            command=self._show_about)
        self._about_btn.pack(side=tk.RIGHT)

        self._guide_btn = tk.Button(
            inner, text=t("user_guide_btn"),
            font=T.get_font("body", T.SIZE_BODY_SM),
            fg=T.TEXT_SECONDARY, bg=T.SURFACE_LOW,
            activebackground=T.SURFACE_LOW, activeforeground=T.TEXT_PRIMARY,
            relief="flat", borderwidth=0, cursor="hand2",
            padx=8, pady=4,
            command=self._open_user_guide)
        self._guide_btn.pack(side=tk.RIGHT)

        # Version pill with gold border
        ver_outer = tk.Frame(inner, bg=T.TS_GOLD, padx=1, pady=1)
        ver_outer.pack(side=tk.RIGHT, padx=(0, T.SPACE_3))
        ver_inner = tk.Frame(ver_outer, bg=T.SURFACE_LOW, padx=8, pady=2)
        ver_inner.pack()
        self._version_label = tk.Label(
            ver_inner,
            text=t("version_label", version=APP_VERSION),
            font=T.get_font("label", T.SIZE_LABEL_SM, bold=True),
            fg=T.TS_GOLD, bg=T.SURFACE_LOW)
        self._version_label.pack()

        tk.Frame(header, height=1, bg=T.GHOST_BORDER).pack(fill=tk.X)

    def _build_stepper(self):
        stepper_wrap = tk.Frame(self.main, bg=T.SURFACE)
        stepper_wrap.pack(fill=tk.X)

        inner = tk.Frame(stepper_wrap, bg=T.SURFACE, padx=T.SPACE_6, pady=T.SPACE_3)
        inner.pack(side=tk.LEFT)

        # Step 1
        self._step1_frame = tk.Frame(inner, bg=T.SURFACE, padx=T.SPACE_3, pady=4)
        self._step1_frame.pack(side=tk.LEFT)
        self._step1_num = tk.Label(self._step1_frame, text="01",
                                   font=T.get_font("label", T.SIZE_LABEL_SM, bold=True),
                                   fg=T.TEXT_TERTIARY, bg=T.SURFACE)
        self._step1_num.pack(side=tk.LEFT, padx=(0, T.SPACE_1))
        self._step1_label = tk.Label(self._step1_frame, text=t("step1_label"),
                                     font=T.get_font("body", T.SIZE_BODY_SM),
                                     fg=T.TEXT_TERTIARY, bg=T.SURFACE)
        self._step1_label.pack(side=tk.LEFT)

        tk.Frame(inner, width=24, height=1, bg=T.DIVIDER).pack(side=tk.LEFT, padx=4, pady=8)

        # Step 2
        self._step2_frame = tk.Frame(inner, bg=T.SURFACE, padx=T.SPACE_3, pady=4)
        self._step2_frame.pack(side=tk.LEFT)
        self._step2_num = tk.Label(self._step2_frame, text="02",
                                   font=T.get_font("label", T.SIZE_LABEL_SM, bold=True),
                                   fg=T.TEXT_TERTIARY, bg=T.SURFACE)
        self._step2_num.pack(side=tk.LEFT, padx=(0, T.SPACE_1))
        self._step2_label = tk.Label(self._step2_frame, text=t("step2_label"),
                                     font=T.get_font("body", T.SIZE_BODY_SM),
                                     fg=T.TEXT_TERTIARY, bg=T.SURFACE)
        self._step2_label.pack(side=tk.LEFT)

        tk.Frame(inner, width=24, height=1, bg=T.DIVIDER).pack(side=tk.LEFT, padx=4, pady=8)

        # Step 3
        self._step3_frame = tk.Frame(inner, bg=T.SURFACE, padx=T.SPACE_3, pady=4)
        self._step3_frame.pack(side=tk.LEFT)
        self._step3_num = tk.Label(self._step3_frame, text="03",
                                   font=T.get_font("label", T.SIZE_LABEL_SM, bold=True),
                                   fg=T.TEXT_TERTIARY, bg=T.SURFACE)
        self._step3_num.pack(side=tk.LEFT, padx=(0, T.SPACE_1))
        self._step3_label = tk.Label(self._step3_frame, text=t("step3_label"),
                                     font=T.get_font("body", T.SIZE_BODY_SM),
                                     fg=T.TEXT_TERTIARY, bg=T.SURFACE)
        self._step3_label.pack(side=tk.LEFT)

        tk.Frame(stepper_wrap, height=1, bg=T.GHOST_BORDER).pack(fill=tk.X, side=tk.BOTTOM)

        self._set_step(1)

    def _set_step(self, current):
        DONE_BG    = "#0A1A16"
        ACTIVE_BG  = "#18150A"
        IDLE_BG    = T.SURFACE

        steps = [
            (self._step1_frame, self._step1_num, self._step1_label),
            (self._step2_frame, self._step2_num, self._step2_label),
            (self._step3_frame, self._step3_num, self._step3_label),
        ]
        for i, (frame, num_lbl, text_lbl) in enumerate(steps):
            n = i + 1
            if n < current:
                frame.config(bg=DONE_BG)
                num_lbl.config(fg=T.PRIMARY, bg=DONE_BG)
                text_lbl.config(fg=T.SUCCESS, bg=DONE_BG)
            elif n == current:
                frame.config(bg=ACTIVE_BG)
                num_lbl.config(fg=T.TEXT_TERTIARY, bg=ACTIVE_BG)
                text_lbl.config(fg=T.TEXT_PRIMARY, bg=ACTIVE_BG)
            else:
                frame.config(bg=IDLE_BG)
                num_lbl.config(fg=T.TEXT_TERTIARY, bg=IDLE_BG)
                text_lbl.config(fg=T.TEXT_TERTIARY, bg=IDLE_BG)

    def _build_main_content(self):
        content = tk.Frame(self.main, bg=T.SURFACE)
        content.pack(fill=tk.BOTH, expand=True, padx=T.SPACE_6, pady=(T.SPACE_4, T.SPACE_3))
        content.columnconfigure(0, weight=1, minsize=300)
        content.columnconfigure(1, weight=14, minsize=460)
        content.rowconfigure(0, weight=1)

        # Left column — files card
        left_outer = tk.Frame(content, bg=T.GHOST_BORDER, padx=1, pady=1)
        left_outer.grid(row=0, column=0, sticky="nsew", padx=(0, T.SPACE_3))
        left_outer.rowconfigure(0, weight=1)
        left_outer.columnconfigure(0, weight=1)
        left_card = tk.Frame(left_outer, bg=T.SURFACE_LOW,
                             padx=T.SPACE_4, pady=T.SPACE_4)
        left_card.grid(row=0, column=0, sticky="nsew")
        left_card.rowconfigure(0, weight=1)
        self._build_file_section(left_card)

        # Right column
        right = tk.Frame(content, bg=T.SURFACE)
        right.grid(row=0, column=1, sticky="nsew")
        right.rowconfigure(0, weight=0)
        right.rowconfigure(1, weight=1)
        right.columnconfigure(0, weight=1)

        # Settings card (top of right)
        settings_outer = tk.Frame(right, bg=T.GHOST_BORDER, padx=1, pady=1)
        settings_outer.grid(row=0, column=0, sticky="ew", pady=(0, T.SPACE_3))
        settings_outer.columnconfigure(0, weight=1)
        settings_card = tk.Frame(settings_outer, bg=T.SURFACE_LOW,
                                 padx=T.SPACE_4, pady=T.SPACE_4)
        settings_card.grid(row=0, column=0, sticky="ew")
        self._build_settings_section(settings_card)

        # Preview card (bottom of right)
        preview_outer = tk.Frame(right, bg=T.GHOST_BORDER, padx=1, pady=1)
        preview_outer.grid(row=1, column=0, sticky="nsew")
        preview_outer.rowconfigure(0, weight=1)
        preview_outer.columnconfigure(0, weight=1)
        preview_card = tk.Frame(preview_outer, bg=T.SURFACE_LOW,
                                padx=T.SPACE_4, pady=T.SPACE_4)
        preview_card.grid(row=0, column=0, sticky="nsew")
        preview_card.rowconfigure(1, weight=1)
        self._build_preview_section(preview_card)

    def _build_file_section(self, card):
        self._file_card = card

        # Card header row
        head_row = tk.Frame(card, bg=T.SURFACE_LOW)
        head_row.pack(fill=tk.X, pady=(0, T.SPACE_3))

        title_block = tk.Frame(head_row, bg=T.SURFACE_LOW)
        title_block.pack(side=tk.LEFT)

        tk.Label(title_block, text="STEP 01",
                 font=T.get_font("label", T.SIZE_LABEL_SM, bold=True),
                 fg=T.TS_GOLD, bg=T.SURFACE_LOW).pack(anchor="w")

        self._file_section_label = tk.Label(
            title_block, text=t("boq_files_label").strip(),
            font=T.get_font("headline", T.SIZE_HEADLINE_SM, bold=True),
            fg=T.TEXT_PRIMARY, bg=T.SURFACE_LOW)
        self._file_section_label.pack(anchor="w")

        # File count (right)
        self.file_count_label = tk.Label(
            head_row, text=t("no_files_selected"),
            font=T.get_font("body", T.SIZE_BODY_SM),
            fg=T.TEXT_TERTIARY, bg=T.SURFACE_LOW)
        self.file_count_label.pack(side=tk.RIGHT, anchor="n", pady=4)

        # File list (dark scrollable)
        list_outer = tk.Frame(card, bg=T.GHOST_BORDER, padx=1, pady=1)
        list_outer.pack(fill=tk.X, pady=(0, T.SPACE_3))
        list_inner = tk.Frame(list_outer, bg=T.SURFACE)
        list_inner.pack(fill=tk.X)

        self.file_listbox = tk.Listbox(
            list_inner, height=4,
            font=T.get_font("body", T.SIZE_BODY_SM),
            selectmode=tk.EXTENDED,
            borderwidth=0, relief="flat",
            bg=T.SURFACE, fg=T.TEXT_PRIMARY,
            selectbackground=T.PRIMARY, selectforeground=T.TEXT_ON_PRIMARY,
            highlightthickness=0)
        self.file_listbox.pack(fill=tk.X, side=tk.LEFT, expand=True)

        scrollbar = ttk.Scrollbar(list_inner, orient=tk.VERTICAL,
                                  command=self.file_listbox.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.file_listbox.config(yscrollcommand=scrollbar.set)

        # Drop zone (dashed Canvas border)
        drop_frame = tk.Frame(card, bg=T.SURFACE_LOW)
        drop_frame.pack(fill=tk.X, pady=(0, T.SPACE_2))

        self._drop_canvas = tk.Canvas(
            drop_frame, bg=T.SURFACE_LOW,
            height=72, highlightthickness=0)
        self._drop_canvas.pack(fill=tk.X)
        self._drop_canvas.bind("<Configure>", self._redraw_drop_zone)

        self._add_btn = tk.Button(
            drop_frame, text=t("add_files_btn"),
            font=T.get_font("body", bold=True),
            fg=T.TEXT_ON_PRIMARY, bg=T.PRIMARY,
            activebackground=T.PRIMARY_HOVER, activeforeground=T.TEXT_ON_PRIMARY,
            relief="flat", borderwidth=0, cursor="hand2",
            padx=T.SPACE_4, pady=T.SPACE_2,
            command=self._add_files)
        self._add_btn.pack(pady=(T.SPACE_1, 0))

        tk.Label(drop_frame, text=".xlsx, .xls  ·  รองรับหลายไฟล์",
                 font=T.get_font("label", T.SIZE_LABEL_SM),
                 fg=T.TEXT_TERTIARY, bg=T.SURFACE_LOW).pack(pady=(2, 0))

        # Clear button (subtle)
        self._clear_btn = tk.Button(
            card, text=t("clear_all_btn"),
            font=T.get_font("body", T.SIZE_BODY_SM),
            fg=T.TEXT_TERTIARY, bg=T.SURFACE_LOW,
            activebackground=T.SURFACE_LOW, activeforeground=T.TEXT_PRIMARY,
            relief="flat", borderwidth=0, cursor="hand2",
            command=self._clear_files)
        self._clear_btn.pack(anchor="e", pady=(0, T.SPACE_2))

        # Note (gold left-bar accent)
        note_outer = tk.Frame(card, bg=T.SURFACE_HIGH)
        note_outer.pack(fill=tk.X, side=tk.BOTTOM)
        tk.Frame(note_outer, width=3, bg=T.TS_GOLD).pack(side=tk.LEFT, fill=tk.Y)
        note_content = tk.Frame(note_outer, bg=T.SURFACE_HIGH,
                                padx=T.SPACE_2, pady=T.SPACE_2)
        note_content.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self._note_label = tk.Label(
            note_content, text=t("cover_sheet_note"),
            font=T.get_font("label", T.SIZE_LABEL_SM, bold=True),
            fg=T.TS_GOLD, bg=T.SURFACE_HIGH,
            anchor="w", wraplength=280, justify="left")
        self._note_label.pack(fill=tk.X)

        self._schedule_note_label = tk.Label(
            note_content, text=t("door_schedule_note"),
            font=T.get_font("label", T.SIZE_LABEL_SM),
            fg=T.WARNING, bg=T.SURFACE_HIGH,
            anchor="w", wraplength=280, justify="left")
        self._schedule_note_label.pack(fill=tk.X)

    def _redraw_drop_zone(self, event=None):
        c = self._drop_canvas
        w = c.winfo_width()
        h = c.winfo_height()
        if w < 10:
            return
        c.delete("all")
        c.create_rectangle(3, 3, w - 3, h - 3,
                           outline=T.PRIMARY, dash=(5, 4), width=1)
        drop_text = ("ลากไฟล์ BOQ มาที่นี่"
                     if get_lang() == "th"
                     else "Drop BOQ files here")
        c.create_text(w // 2, h // 2,
                      text=f"↑   {drop_text}",
                      fill=T.TEXT_TERTIARY,
                      font=T.get_font("body", T.SIZE_BODY_SM))

    def _build_settings_section(self, card):
        self._settings_card = card

        # Card header row
        head_row = tk.Frame(card, bg=T.SURFACE_LOW)
        head_row.pack(fill=tk.X, pady=(0, T.SPACE_3))

        title_block = tk.Frame(head_row, bg=T.SURFACE_LOW)
        title_block.pack(side=tk.LEFT)

        tk.Label(title_block, text="STEP 02",
                 font=T.get_font("label", T.SIZE_LABEL_SM, bold=True),
                 fg=T.TS_GOLD, bg=T.SURFACE_LOW).pack(anchor="w")

        self._settings_section_label = tk.Label(
            title_block, text=t("settings_label").strip(),
            font=T.get_font("headline", T.SIZE_HEADLINE_SM, bold=True),
            fg=T.TEXT_PRIMARY, bg=T.SURFACE_LOW)
        self._settings_section_label.pack(anchor="w")

        # Cell References button (outlined secondary)
        btn_wrap = tk.Frame(head_row, bg=T.DIVIDER, padx=1, pady=1)
        btn_wrap.pack(side=tk.RIGHT, anchor="n")
        self.config_btn = tk.Button(
            btn_wrap, text=t("cell_references_btn"),
            font=T.get_font("body", T.SIZE_BODY_SM),
            fg=T.SUCCESS, bg=T.SURFACE_LOW,
            activebackground=T.SURFACE_HIGH, activeforeground=T.TEXT_PRIMARY,
            relief="flat", borderwidth=0, cursor="hand2",
            padx=T.SPACE_2, pady=2,
            command=self._open_config)
        self.config_btn.pack()

        # Project name field with teal left accent
        field_frame = tk.Frame(card, bg=T.SURFACE_LOW)
        field_frame.pack(fill=tk.X, pady=(0, T.SPACE_3))

        self._project_name_label = tk.Label(
            field_frame, text=t("project_name_label"),
            font=T.get_font("label", T.SIZE_LABEL_SM, bold=True),
            fg=T.SUCCESS, bg=T.SURFACE_LOW)
        self._project_name_label.pack(anchor="w", pady=(0, 4))

        entry_container = tk.Frame(field_frame, bg=T.SURFACE_LOW)
        entry_container.pack(fill=tk.X)
        tk.Frame(entry_container, width=2, bg=T.PRIMARY).pack(side=tk.LEFT, fill=tk.Y)
        entry_border = tk.Frame(entry_container, bg=T.GHOST_BORDER, padx=1, pady=1)
        entry_border.pack(side=tk.LEFT, fill=tk.X, expand=True)
        name_entry = tk.Entry(
            entry_border, textvariable=self.project_name,
            font=T.get_font("body"),
            bg=T.SURFACE, fg=T.TEXT_PRIMARY,
            insertbackground=T.PRIMARY,
            borderwidth=0, relief="flat",
            highlightthickness=0)
        name_entry.pack(fill=tk.X, ipady=5, padx=T.SPACE_2)

        # ── Project picker (loads from Supabase `projects`, mirrored from Lark) ──
        picker_frame = tk.Frame(card, bg=T.SURFACE_LOW)
        picker_frame.pack(fill=tk.X, pady=(T.SPACE_2, T.SPACE_3))

        self._project_picker_label = tk.Label(
            picker_frame, text=t("project_picker_label"),
            font=T.get_font("label", T.SIZE_LABEL_SM, bold=True),
            fg=T.SUCCESS, bg=T.SURFACE_LOW)
        self._project_picker_label.pack(anchor="w", pady=(0, 4))

        self._project_picker_var = tk.StringVar(value=t("project_picker_loading"))
        self._picker_showing_placeholder = True
        self._project_picker = ttk.Combobox(
            picker_frame, textvariable=self._project_picker_var,
            state="normal", font=T.get_font("body"))
        self._project_picker.pack(fill=tk.X, ipady=2)
        self._project_picker.bind("<<ComboboxSelected>>", self._on_project_picked)
        self._project_picker.bind("<KeyRelease>", self._on_picker_search)
        self._project_picker.bind("<FocusIn>",  self._on_picker_focus_in)
        self._project_picker.bind("<FocusOut>", self._on_picker_focus_out)

        # ── Project category ──
        cat_frame = tk.Frame(card, bg=T.SURFACE_LOW)
        cat_frame.pack(fill=tk.X, pady=(0, T.SPACE_3))

        self._project_category_label = tk.Label(
            cat_frame, text=t("project_category_label"),
            font=T.get_font("label", T.SIZE_LABEL_SM, bold=True),
            fg=T.SUCCESS, bg=T.SURFACE_LOW)
        self._project_category_label.pack(anchor="w", pady=(0, 4))

        cat_container = tk.Frame(cat_frame, bg=T.SURFACE_LOW)
        cat_container.pack(fill=tk.X)
        tk.Frame(cat_container, width=2, bg=T.PRIMARY).pack(side=tk.LEFT, fill=tk.Y)
        cat_border = tk.Frame(cat_container, bg=T.GHOST_BORDER, padx=1, pady=1)
        cat_border.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self._cat_combo = ttk.Combobox(
            cat_border, textvariable=self.project_category,
            values=PROJECT_TYPES,
            state="normal", font=T.get_font("body"))
        self._cat_combo.pack(fill=tk.X, ipady=2, padx=T.SPACE_2)

        # Kick off background project fetch so the combobox populates after launch.
        self._reload_projects_async()

        # Toggle rows for the three checkbuttons
        TBKG = T.SURFACE_HIGH

        def _toggle_row(parent, var, key):
            row = tk.Frame(parent, bg=TBKG, padx=T.SPACE_2, pady=4)
            row.pack(fill=tk.X, pady=1)
            cb = tk.Checkbutton(
                row, text=t(key), variable=var,
                font=T.get_font("body", T.SIZE_BODY_MD),
                fg=T.TEXT_PRIMARY, bg=TBKG,
                activebackground=TBKG, activeforeground=T.TEXT_PRIMARY,
                selectcolor=T.DIVIDER, cursor="hand2")
            cb.pack(side=tk.LEFT)
            return cb

        toggle_wrap = tk.Frame(card, bg=T.SURFACE_LOW)
        toggle_wrap.pack(fill=tk.X, pady=(0, T.SPACE_2))

        self._pricing_check = _toggle_row(toggle_wrap, self.include_pricing,
                                          "include_pricing_check")
        self._unit_price_check = _toggle_row(toggle_wrap, self.use_unit_price,
                                             "use_unit_price_check")
        self._combine_check = _toggle_row(toggle_wrap, self.combine_door_types,
                                          "combine_door_types_check")

        # Status bar
        tk.Frame(card, height=1, bg=T.DIVIDER).pack(fill=tk.X, pady=(T.SPACE_1, T.SPACE_2))

        status_row = tk.Frame(card, bg=T.SURFACE_LOW)
        status_row.pack(fill=tk.X)

        # Dot indicator
        status_left = tk.Frame(status_row, bg=T.SURFACE_LOW)
        status_left.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self._status_dot = tk.Canvas(
            status_left, width=9, height=9,
            bg=T.SURFACE_LOW, highlightthickness=0)
        self._status_dot.create_oval(1, 1, 8, 8,
                                     fill=T.TEXT_TERTIARY, outline="", tags="dot")
        self._status_dot.pack(side=tk.LEFT, padx=(0, T.SPACE_1))

        self.config_status = tk.Label(
            status_left, text="",
            font=T.get_font("label", T.SIZE_LABEL_SM),
            fg=T.TEXT_TERTIARY, bg=T.SURFACE_LOW)
        self.config_status.pack(side=tk.LEFT)

        # Error log button
        self._error_log_btn = tk.Button(
            status_row, text=t("error_log_btn"),
            font=T.get_font("body", T.SIZE_BODY_SM),
            fg=T.TEXT_TERTIARY, bg=T.SURFACE_LOW,
            activebackground=T.SURFACE_LOW, activeforeground=T.TEXT_PRIMARY,
            relief="flat", borderwidth=0, cursor="hand2",
            padx=T.SPACE_2,
            command=self._show_error_log)
        self._error_log_btn.pack(side=tk.RIGHT)

    def _build_preview_section(self, card):
        self._preview_card = card

        # Card header row
        head_row = tk.Frame(card, bg=T.SURFACE_LOW)
        head_row.pack(fill=tk.X, pady=(0, T.SPACE_2))

        title_block = tk.Frame(head_row, bg=T.SURFACE_LOW)
        title_block.pack(side=tk.LEFT)

        tk.Label(title_block, text="PREVIEW",
                 font=T.get_font("label", T.SIZE_LABEL_SM, bold=True),
                 fg=T.TS_GOLD, bg=T.SURFACE_LOW).pack(anchor="w")

        self._preview_section_label = tk.Label(
            title_block, text=t("preview_label").strip(),
            font=T.get_font("headline", T.SIZE_HEADLINE_SM, bold=True),
            fg=T.TEXT_PRIMARY, bg=T.SURFACE_LOW)
        self._preview_section_label.pack(anchor="w")

        # Preview text area (dark monospace)
        preview_outer = tk.Frame(card, bg=T.GHOST_BORDER, padx=1, pady=1)
        preview_outer.pack(fill=tk.BOTH, expand=True)

        self.preview_text = tk.Text(
            preview_outer, height=8,
            font=T.get_font("mono", T.SIZE_BODY_SM),
            wrap=tk.WORD,
            borderwidth=0, relief="flat",
            state=tk.DISABLED,
            bg=T.SURFACE, fg=T.TEXT_SECONDARY,
            insertbackground=T.PRIMARY,
            padx=T.SPACE_4, pady=T.SPACE_3,
            highlightthickness=0)
        self.preview_text.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)

        preview_scroll = ttk.Scrollbar(preview_outer, orient=tk.VERTICAL,
                                       command=self.preview_text.yview)
        preview_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.preview_text.config(yscrollcommand=preview_scroll.set)

    def _build_action_bar(self):
        bar = tk.Frame(self.main, bg=T.SURFACE_LOW, padx=T.SPACE_6, pady=T.SPACE_3)
        bar.pack(side=tk.BOTTOM, fill=tk.X)
        tk.Frame(self.main, height=1, bg=T.GHOST_BORDER).pack(side=tk.BOTTOM, fill=tk.X)

        # Left: status dot + label
        status_block = tk.Frame(bar, bg=T.SURFACE_LOW)
        status_block.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self._action_dot = tk.Canvas(
            status_block, width=9, height=9,
            bg=T.SURFACE_LOW, highlightthickness=0)
        self._action_dot.create_oval(1, 1, 8, 8,
                                     fill=T.TEXT_TERTIARY, outline="", tags="dot")
        self._action_dot.pack(side=tk.LEFT, padx=(0, T.SPACE_2))

        self.status_label = tk.Label(
            status_block, text=t("ready_status"),
            font=T.get_font("body", T.SIZE_BODY_SM, bold=True),
            fg=T.TEXT_SECONDARY, bg=T.SURFACE_LOW)
        self.status_label.pack(side=tk.LEFT)

        # Right: progress + convert button
        action_right = tk.Frame(bar, bg=T.SURFACE_LOW)
        action_right.pack(side=tk.RIGHT)

        self.progress = ttk.Progressbar(action_right, mode="indeterminate", length=140)
        self.progress.pack(side=tk.LEFT, padx=(0, T.SPACE_3))

        self.convert_btn = tk.Button(
            action_right, text=t("convert_btn"),
            font=T.get_font("body", T.SIZE_BODY_MD, bold=True),
            fg=T.TEXT_ON_PRIMARY, bg=T.PRIMARY,
            activebackground=T.PRIMARY_HOVER, activeforeground=T.TEXT_ON_PRIMARY,
            relief="flat", borderwidth=0, cursor="hand2",
            padx=T.SPACE_8, pady=T.SPACE_2,
            command=self._convert)
        self.convert_btn.pack(side=tk.LEFT)

    def _text_logo(self, parent):
        lf = tk.Frame(parent, bg=T.SURFACE_LOW)
        lf.pack(side=tk.LEFT, padx=(0, T.SPACE_4))
        tk.Label(lf, text="TODAY STYLE 2100",
                 font=T.get_font("headline", T.SIZE_HEADLINE_MD, bold=True),
                 fg=T.TEXT_PRIMARY, bg=T.SURFACE_LOW).pack()

    # ─────────────────────────────────────────────────────────
    # LANGUAGE
    # ─────────────────────────────────────────────────────────

    def _toggle_language(self):
        new_lang = "th" if get_lang() == "en" else "en"
        set_lang(new_lang)

    def _on_language_change(self, lang):
        self.root.title(t("app_title"))

        # Header
        self._title_label.config(text=t("header_title"))
        self._subtitle_label.config(text=t("header_subtitle"))
        self._lang_btn.config(text=t("lang_btn"))
        self._about_btn.config(text=t("about_btn"))
        self._guide_btn.config(text=t("user_guide_btn"))
        self._version_label.config(text=t("version_label", version=APP_VERSION))

        # Stepper
        self._step1_label.config(text=t("step1_label"))
        self._step2_label.config(text=t("step2_label"))
        self._step3_label.config(text=t("step3_label"))

        # File section
        self._file_section_label.config(text=t("boq_files_label").strip())
        self._add_btn.config(text=t("add_files_btn"))
        self._clear_btn.config(text=t("clear_all_btn"))
        self._note_label.config(text=t("cover_sheet_note"))
        self._schedule_note_label.config(text=t("door_schedule_note"))
        self._redraw_drop_zone()

        count = len(self.boq_files)
        if count == 0:
            self.file_count_label.config(text=t("no_files_selected"))
        else:
            self.file_count_label.config(
                text=t("files_selected", count=count, s="s" if count != 1 else ""))

        # Settings
        self._settings_section_label.config(text=t("settings_label").strip())
        self._project_name_label.config(text=t("project_name_label"))
        self._project_picker_label.config(text=t("project_picker_label"))
        self._project_category_label.config(text=t("project_category_label"))
        # Refresh picker values so placeholder/custom labels swap language.
        self._apply_projects(self._projects_cache)
        self._pricing_check.config(text=t("include_pricing_check"))
        self._unit_price_check.config(text=t("use_unit_price_check"))
        self._combine_check.config(text=t("combine_door_types_check"))
        self.config_btn.config(text=t("cell_references_btn"))
        self._error_log_btn.config(text=t("error_log_btn"))

        if self.config_detected:
            status_text = self.config_status.cget("text")
            if status_text in ("Auto-detected", "ตรวจจับอัตโนมัติ"):
                self.config_status.config(text=t("auto_detected"))
            elif status_text in ("Custom config", "ตั้งค่าเอง"):
                self.config_status.config(text=t("custom_config"))
        elif self.config_status.cget("text") in ("Using defaults", "ใช้ค่าเริ่มต้น"):
            self.config_status.config(text=t("using_defaults"))

        # Preview
        self._preview_section_label.config(text=t("preview_label").strip())

        # Action bar
        self.convert_btn.config(text=t("convert_btn"))
        status_text = self.status_label.cget("text")
        if status_text in ("Ready", "พร้อม"):
            self.status_label.config(text=t("ready_status"))
        elif status_text in ("Ready to convert", "พร้อมแปลง"):
            self.status_label.config(text=t("ready_to_convert"))

        if self.parsed_categories:
            self._parse_preview()

    # ─────────────────────────────────────────────────────────
    # FILE MANAGEMENT
    # ─────────────────────────────────────────────────────────

    def _add_files(self):
        files = filedialog.askopenfilenames(
            title=t("select_boq_files_title"),
            filetypes=[("Excel Files", "*.xlsx *.xls"), ("All Files", "*.*")])
        for f in files:
            if f not in self.boq_files:
                self.boq_files.append(f)
                self.file_listbox.insert(tk.END, os.path.basename(f))

        count = len(self.boq_files)
        if count > 0:
            self.file_count_label.config(
                text=t("files_selected", count=count, s="s" if count != 1 else ""),
                fg=T.SUCCESS)
            self._set_step(2)
        else:
            self.file_count_label.config(text=t("no_files_selected"), fg=T.TEXT_TERTIARY)

        if self.boq_files and not self.config_detected:
            self._auto_detect_config()
        if self.boq_files:
            self._parse_preview()

    def _auto_detect_config(self):
        try:
            self.config = detect_config(self.boq_files[0])
            self.config_detected = True
            self.config_status.config(text=t("auto_detected"), fg=T.SUCCESS)
            self._status_dot.itemconfig("dot", fill=T.SUCCESS)
        except Exception:
            self.config_status.config(text=t("using_defaults"), fg=T.TEXT_TERTIARY)
            self._status_dot.itemconfig("dot", fill=T.TEXT_TERTIARY)

    def _open_config(self):
        if not self.boq_files:
            messagebox.showwarning(t("no_files_title"), t("no_files_config_msg"))
            return

        def on_save(new_config):
            self.config = new_config
            self.config_detected = True
            self.config_status.config(text=t("custom_config"), fg=T.INFO)
            self._status_dot.itemconfig("dot", fill=T.INFO)
            if self.boq_files:
                self._parse_preview()

        CellSelectorDialog(self.root, self.config, self.boq_files, on_save)

    # ─────────────────────────────────────────────────────────
    # PROJECT PICKER (Lark mirror)
    # ─────────────────────────────────────────────────────────

    def _reload_projects_async(self):
        def worker():
            projects = db_logger.fetch_projects()
            self.root.after(0, lambda: self._apply_projects(projects))
        threading.Thread(target=worker, daemon=True).start()

    def _apply_projects(self, projects):
        self._projects_cache = projects or []
        custom = t("project_picker_custom")
        self._picker_placeholder = (t("project_picker_placeholder")
                                    if self._projects_cache
                                    else t("project_picker_unavailable"))
        values = [p["name"] for p in self._projects_cache] + [custom]
        self._project_picker["values"] = values
        self._project_picker_var.set(self._picker_placeholder)
        self._picker_showing_placeholder = True
        self._project_picker.configure(foreground=T.TEXT_TERTIARY)

    def _on_picker_focus_in(self, _event=None):
        if self._picker_showing_placeholder:
            self._project_picker_var.set("")
            self._picker_showing_placeholder = False
            self._project_picker.configure(foreground=T.TEXT_PRIMARY)
            # Show full list when field is cleared on focus
            custom = t("project_picker_custom")
            self._project_picker["values"] = (
                [p["name"] for p in self._projects_cache] + [custom]
            )

    def _on_picker_focus_out(self, _event=None):
        if not self._project_picker_var.get().strip():
            placeholder = getattr(self, "_picker_placeholder",
                                  t("project_picker_placeholder"))
            self._project_picker_var.set(placeholder)
            self._picker_showing_placeholder = True
            self._project_picker.configure(foreground=T.TEXT_TERTIARY)

    def _on_picker_search(self, event=None):
        """Filter combobox list as the user types."""
        if event and event.keysym in ("Return", "Tab", "Escape", "Down", "Up"):
            return
        if self._picker_showing_placeholder:
            return
        typed = self._project_picker_var.get().strip().lower()
        custom = t("project_picker_custom")
        if not typed:
            filtered = [p["name"] for p in self._projects_cache]
        else:
            filtered = [p["name"] for p in self._projects_cache
                        if typed in p["name"].lower()]
        self._project_picker["values"] = filtered + [custom]

    def _on_project_picked(self, _event=None):
        selected = self._project_picker_var.get()
        custom = t("project_picker_custom")
        self._picker_showing_placeholder = False
        self._project_picker.configure(foreground=T.TEXT_PRIMARY)
        if selected == custom:
            self.project_id = None
            self._original_category = ""
            # Leave name + category for user to fill manually.
            return
        match = next((p for p in self._projects_cache if p["name"] == selected), None)
        if not match:
            return
        self.project_id = match.get("id")
        self._original_category = match.get("category") or ""
        self.project_name.set(match.get("name", ""))
        if self._original_category:
            self.project_category.set(self._original_category)
        else:
            # Category is empty in Lark — clear field so user knows to fill it
            self.project_category.set("")

    def _clear_files(self):
        self.boq_files.clear()
        self.file_listbox.delete(0, tk.END)
        self.file_count_label.config(text=t("no_files_selected"), fg=T.TEXT_TERTIARY)
        self.parsed_categories.clear()
        self.qty_map.clear()
        self._update_preview("")
        self.project_name.set("")
        self.project_category.set("")
        self.project_id = None
        self._original_category = ""
        if hasattr(self, "_project_picker_var"):
            placeholder = (t("project_picker_placeholder") if self._projects_cache
                           else t("project_picker_unavailable"))
            self._project_picker_var.set(placeholder)
            self._picker_showing_placeholder = True
            self._project_picker.configure(foreground=T.TEXT_TERTIARY)
        self.config = BOQConfig()
        self.config_detected = False
        self.config_status.config(text="", fg=T.TEXT_TERTIARY)
        self._status_dot.itemconfig("dot", fill=T.TEXT_TERTIARY)
        self._set_step(1)

    # ─────────────────────────────────────────────────────────
    # PARSING & PREVIEW
    # ─────────────────────────────────────────────────────────

    def _parse_preview(self):
        self.status_label.config(text=t("parsing_status"), fg=T.INFO)
        self._action_dot.itemconfig("dot", fill=T.INFO)
        self.progress.start()
        config = self.config

        def do_parse():
            try:
                cats, qty_map = parse_multiple_boq_files(self.boq_files, config)
                self.parsed_categories = cats
                self.qty_map = qty_map

                lines = []
                total_doors = 0
                total_products = 0
                for cat in cats:
                    lines.append(t("preview_category", name=cat.name))
                    lines.append(t("preview_doors", count=len(cat.door_types)))
                    door_names = [dt.code for dt in cat.door_types]
                    lines.append(t("preview_door_types", types=", ".join(door_names)))
                    total_doors += len(cat.door_types)

                    models = set()
                    for dt in cat.door_types:
                        for dp in dt.products:
                            if dp.quantity > 0:
                                models.add(dp.product.model)
                    total_products += len(models)
                    lines.append(t("preview_products", count=len(models)))

                    qty_parts = []
                    for dt in cat.door_types:
                        q = qty_map.get(dt.code, "?")
                        qty_parts.append(f"{dt.code}={q}")
                    if qty_parts:
                        lines.append(t("preview_quantities", qtys=", ".join(qty_parts)))
                    lines.append("")

                    if not self.project_name.get():
                        for dt in cat.door_types:
                            if dt.code:
                                fname = os.path.basename(cat.source_file)
                                name = fname.replace("BOQ ", "").replace(".xlsx", "").replace(".xls", "")
                                self.project_name.set(name)
                                break

                lines.append(t("preview_total", doors=total_doors, products=total_products))
                lines.append("")
                lines.append(t("preview_cell_refs"))
                sc = config.sheet_config
                lines.append(t("preview_door_codes", col=sc.door_code_col, row=sc.door_code_start_row))
                lines.append(t("preview_product_cfg", brand=sc.brand_col, model=sc.model_col,
                                desc=sc.description_col, qty=sc.quantity_col))
                lines.append(t("preview_pricing_cfg", price=sc.unit_price_col, net=sc.net_indicator_col))
                cc = config.cover_config
                lines.append(t("preview_cover_cfg", code=cc.door_code_col,
                                qty=cc.quantity_col, row=cc.data_start_row))

                preview = "\n".join(lines)
                self.root.after(0, lambda: self._update_preview(preview))
                self.root.after(0, lambda: self.status_label.config(
                    text=t("ready_to_convert"), fg=T.SUCCESS))
                self.root.after(0, lambda: self._action_dot.itemconfig("dot", fill=T.SUCCESS))
                self.root.after(0, lambda: self._set_step(3))

            except Exception as e:
                logger.exception("Parse error: %s", e)
                self.root.after(0, lambda: self._update_preview(t("error_parsing", error=str(e))))
                self.root.after(0, lambda: self.status_label.config(
                    text=t("parse_error"), fg=T.ERROR))
                self.root.after(0, lambda: self._action_dot.itemconfig("dot", fill=T.ERROR))

            self.root.after(0, self.progress.stop)

        threading.Thread(target=do_parse, daemon=True).start()

    def _update_preview(self, text):
        self.preview_text.config(state=tk.NORMAL)
        self.preview_text.delete("1.0", tk.END)
        self.preview_text.insert("1.0", text)
        self.preview_text.config(state=tk.DISABLED)

    # ─────────────────────────────────────────────────────────
    # CONVERSION
    # ─────────────────────────────────────────────────────────

    def _convert(self):
        if not self.boq_files:
            messagebox.showwarning(t("no_files_title"), t("no_files_msg"))
            return
        if not self.parsed_categories:
            messagebox.showwarning(t("not_parsed_title"), t("not_parsed_msg"))
            return
        if not self.project_category.get().strip():
            messagebox.showwarning(
                t("project_category_required_title"),
                t("project_category_required_msg"))
            return

        output_path = filedialog.asksaveasfilename(
            title=t("save_as_title"),
            defaultextension=".xlsx",
            filetypes=[("Excel Files", "*.xlsx")],
            initialfile=f"warehouse form_{self.project_name.get().replace(' ', '_')}.xlsx"
            if self.project_name.get() else "warehouse form.xlsx")
        if not output_path:
            return

        self.status_label.config(text=t("generating_status"), fg=T.INFO)
        self._action_dot.itemconfig("dot", fill=T.INFO)
        self.progress.start()
        self.convert_btn.config(state=tk.DISABLED)

        def do_convert():
            try:
                cats_to_emit = self.parsed_categories
                if self.combine_door_types.get() and cats_to_emit:
                    from boq_parser import BOQCategory
                    merged = BOQCategory(
                        name="Door",
                        source_file=cats_to_emit[0].source_file,
                    )
                    for c in cats_to_emit:
                        merged.door_types.extend(c.door_types)
                    cats_to_emit = [merged]

                generate_warehouse_form(
                    cats_to_emit,
                    project_name=self.project_name.get(),
                    output_path=output_path,
                    include_pricing=self.include_pricing.get(),
                    qty_map=self.qty_map,
                    use_unit_price=self.use_unit_price.get())

                entered_category = self.project_category.get().strip()
                db_logger.log_conversion(
                    self.project_name.get(),
                    self.parsed_categories,
                    self.boq_files,
                    project_category=entered_category,
                    project_id=self.project_id)

                # Write category back to Lark + Supabase if user filled a blank field
                if self.project_id and not self._original_category and entered_category:
                    db_logger.write_back_category(
                        self.project_id, self.project_id, entered_category)
                    self._original_category = entered_category  # prevent duplicate writes

                self.root.after(0, lambda: self.status_label.config(
                    text=t("saved_status", filename=os.path.basename(output_path)),
                    fg=T.SUCCESS))
                self.root.after(0, lambda: self._action_dot.itemconfig("dot", fill=T.SUCCESS))
                self.root.after(0, lambda: messagebox.showinfo(
                    t("success_title"),
                    t("success_msg", path=output_path, count=len(self.parsed_categories))))
                try:
                    if sys.platform == "win32":
                        os.startfile(output_path)
                    elif sys.platform == "darwin":
                        os.system(f'open "{output_path}"')
                except Exception:
                    pass
            except Exception as e:
                logger.exception("Conversion error: %s", e)
                self.root.after(0, lambda: self.status_label.config(
                    text=t("conversion_error"), fg=T.ERROR))
                self.root.after(0, lambda: self._action_dot.itemconfig("dot", fill=T.ERROR))
                self.root.after(0, lambda: messagebox.showerror(
                    t("error_title"), t("error_msg", error=str(e))))

            self.root.after(0, self.progress.stop)
            self.root.after(0, lambda: self.convert_btn.config(state=tk.NORMAL))

        threading.Thread(target=do_convert, daemon=True).start()

    # ─────────────────────────────────────────────────────────
    # ERROR LOG VIEWER
    # ─────────────────────────────────────────────────────────

    def _show_error_log(self):
        dlg = tk.Toplevel(self.root)
        dlg.title(t("error_log_title"))
        dlg.geometry("760x520")
        dlg.resizable(True, True)
        dlg.transient(self.root)
        dlg.grab_set()
        dlg.configure(bg=T.SURFACE)

        dlg.update_idletasks()
        px = self.root.winfo_x() + (self.root.winfo_width() - 760) // 2
        py = self.root.winfo_y() + (self.root.winfo_height() - 520) // 2
        dlg.geometry(f"+{max(0,px)}+{max(0,py)}")

        # Header
        hdr = tk.Frame(dlg, bg=T.SURFACE_LOW, padx=T.SPACE_5, pady=T.SPACE_4)
        hdr.pack(fill=tk.X)
        tk.Label(hdr, text="RUNTIME LOG",
                 font=T.get_font("label", T.SIZE_LABEL_SM, bold=True),
                 fg=T.TS_GOLD, bg=T.SURFACE_LOW, anchor="w").pack(anchor="w")
        tk.Label(hdr, text=t("error_log_title"),
                 font=T.get_font("headline", T.SIZE_HEADLINE_SM, bold=True),
                 fg=T.TEXT_PRIMARY, bg=T.SURFACE_LOW, anchor="w").pack(anchor="w")
        tk.Frame(dlg, height=1, bg=T.GHOST_BORDER).pack(fill=tk.X)

        # Log text area
        main = tk.Frame(dlg, bg=T.SURFACE, padx=T.SPACE_5, pady=T.SPACE_3)
        main.pack(fill=tk.BOTH, expand=True)

        log_outer = tk.Frame(main, bg=T.GHOST_BORDER, padx=1, pady=1)
        log_outer.pack(fill=tk.BOTH, expand=True)

        log_text = tk.Text(
            log_outer,
            font=T.get_font("mono", T.SIZE_BODY_SM),
            wrap=tk.WORD,
            borderwidth=0, relief="flat",
            bg=T.SURFACE, fg=T.TEXT_SECONDARY,
            padx=T.SPACE_3, pady=T.SPACE_3,
            highlightthickness=0)
        log_scroll = ttk.Scrollbar(log_outer, orient=tk.VERTICAL, command=log_text.yview)
        log_text.configure(yscrollcommand=log_scroll.set)
        log_text.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)
        log_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        content = _log_stream.getvalue()
        log_text.insert("1.0", content if content.strip() else t("error_log_empty"))
        log_text.config(state=tk.DISABLED)
        log_text.see(tk.END)

        # Footer buttons
        tk.Frame(dlg, height=1, bg=T.GHOST_BORDER).pack(fill=tk.X)
        btn_row = tk.Frame(dlg, bg=T.SURFACE_LOW, padx=T.SPACE_5, pady=T.SPACE_3)
        btn_row.pack(fill=tk.X)

        def clear_log():
            _log_stream.truncate(0)
            _log_stream.seek(0)
            logger.info("Log cleared by user")
            log_text.config(state=tk.NORMAL)
            log_text.delete("1.0", tk.END)
            log_text.insert("1.0", t("error_log_empty"))
            log_text.config(state=tk.DISABLED)

        def export_log():
            save_path = filedialog.asksaveasfilename(
                title=t("error_log_export_title"),
                defaultextension=".log",
                filetypes=[("Log Files", "*.log"), ("Text Files", "*.txt"), ("All Files", "*.*")],
                initialfile="boq_converter.log")
            if not save_path:
                return
            try:
                with open(save_path, "w", encoding="utf-8") as f:
                    f.write(_log_stream.getvalue())
                messagebox.showinfo(t("success_title"), t("error_log_exported", path=save_path))
            except Exception as ex:
                messagebox.showerror(t("error_title"), str(ex))

        # Ghost-style clear
        clear_wrap = tk.Frame(btn_row, bg=T.DIVIDER, padx=1, pady=1)
        clear_wrap.pack(side=tk.LEFT)
        tk.Button(clear_wrap, text=t("error_log_clear"),
                  font=T.get_font("body", T.SIZE_BODY_SM),
                  fg=T.TEXT_SECONDARY, bg=T.SURFACE_LOW,
                  activebackground=T.SURFACE_HIGH,
                  relief="flat", borderwidth=0, cursor="hand2",
                  padx=T.SPACE_3, pady=T.SPACE_1,
                  command=clear_log).pack()

        # Teal export
        tk.Button(btn_row, text=t("error_log_export"),
                  font=T.get_font("body", T.SIZE_BODY_SM, bold=True),
                  fg=T.TEXT_ON_PRIMARY, bg=T.PRIMARY,
                  activebackground=T.PRIMARY_HOVER, activeforeground=T.TEXT_ON_PRIMARY,
                  relief="flat", borderwidth=0, cursor="hand2",
                  padx=T.SPACE_4, pady=T.SPACE_1,
                  command=export_log).pack(side=tk.LEFT, padx=(T.SPACE_2, 0))

        # Ghost close
        close_wrap = tk.Frame(btn_row, bg=T.DIVIDER, padx=1, pady=1)
        close_wrap.pack(side=tk.RIGHT)
        tk.Button(close_wrap, text=t("close_btn"),
                  font=T.get_font("body", T.SIZE_BODY_SM),
                  fg=T.TEXT_SECONDARY, bg=T.SURFACE_LOW,
                  activebackground=T.SURFACE_HIGH,
                  relief="flat", borderwidth=0, cursor="hand2",
                  padx=T.SPACE_5, pady=T.SPACE_1,
                  command=dlg.destroy).pack()

    # ─────────────────────────────────────────────────────────
    # ABOUT DIALOG
    # ─────────────────────────────────────────────────────────

    def _open_user_guide(self):
        guide_path = os.path.join(BASE_DIR, "user_guide.html")
        webbrowser.open(f"file:///{guide_path.replace(os.sep, '/')}")

    def _show_about(self):
        about = tk.Toplevel(self.root)
        about.title(t("about_title"))
        about.geometry("600x520")
        about.resizable(True, True)
        about.transient(self.root)
        about.grab_set()
        about.configure(bg=T.SURFACE)

        about.update_idletasks()
        px = self.root.winfo_x() + (self.root.winfo_width() - 600) // 2
        py = self.root.winfo_y() + (self.root.winfo_height() - 520) // 2
        about.geometry(f"+{max(0,px)}+{max(0,py)}")

        # Hero header
        hero = tk.Frame(about, bg=T.SURFACE_LOW, padx=T.SPACE_6, pady=T.SPACE_5)
        hero.pack(fill=tk.X)

        logo_path = _find_logo("logo_title.png")
        if logo_path:
            try:
                img = tk.PhotoImage(file=logo_path)
                about._logo_img = img
                tk.Label(hero, image=img, bg=T.SURFACE_LOW).pack(side=tk.LEFT,
                                                                   padx=(0, T.SPACE_4))
            except Exception:
                tk.Label(hero, text="TODAY STYLE 2100",
                         font=T.get_font("headline", T.SIZE_HEADLINE_MD, bold=True),
                         fg=T.TEXT_PRIMARY, bg=T.SURFACE_LOW).pack(side=tk.LEFT,
                                                                     padx=(0, T.SPACE_4))
        else:
            tk.Label(hero, text="TODAY STYLE 2100",
                     font=T.get_font("headline", T.SIZE_HEADLINE_MD, bold=True),
                     fg=T.TEXT_PRIMARY, bg=T.SURFACE_LOW).pack(side=tk.LEFT,
                                                                 padx=(0, T.SPACE_4))

        tk.Frame(hero, width=1, bg=T.TS_GOLD).pack(side=tk.LEFT, fill=tk.Y,
                                                     padx=(0, T.SPACE_4), pady=2)
        hero_text = tk.Frame(hero, bg=T.SURFACE_LOW)
        hero_text.pack(side=tk.LEFT)
        tk.Label(hero_text, text="BOQ TOOLING",
                 font=T.get_font("label", T.SIZE_LABEL_SM, bold=True),
                 fg=T.TS_GOLD, bg=T.SURFACE_LOW).pack(anchor="w")
        tk.Label(hero_text, text=t("about_app_name"),
                 font=T.get_font("headline", T.SIZE_HEADLINE_MD, bold=True),
                 fg=T.TEXT_PRIMARY, bg=T.SURFACE_LOW).pack(anchor="w")
        tk.Label(hero_text, text=t("about_company"),
                 font=T.get_font("label", T.SIZE_LABEL_SM),
                 fg=T.TEXT_TERTIARY, bg=T.SURFACE_LOW).pack(anchor="w")

        tk.Frame(about, height=1, bg=T.GHOST_BORDER).pack(fill=tk.X)

        # Version badge
        main = tk.Frame(about, bg=T.SURFACE, padx=T.SPACE_6, pady=T.SPACE_4)
        main.pack(fill=tk.BOTH, expand=True)

        ver_outer = tk.Frame(main, bg=T.TS_GOLD, padx=1, pady=1)
        ver_outer.pack(anchor="w", pady=(0, T.SPACE_4))
        ver_inner = tk.Frame(ver_outer, bg=T.SURFACE_LOW, padx=T.SPACE_4, pady=T.SPACE_1)
        ver_inner.pack()
        tk.Label(ver_inner,
                 text=t("about_version_info", version=APP_VERSION, date=APP_BUILD_DATE),
                 font=T.get_font("body", T.SIZE_BODY_SM, bold=True),
                 fg=T.TS_GOLD, bg=T.SURFACE_LOW).pack()

        # Changelog card
        log_card = tk.Frame(main, bg=T.SURFACE_LOW, padx=T.SPACE_4, pady=T.SPACE_4)
        log_card.pack(fill=tk.BOTH, expand=True)

        tk.Label(log_card, text="CHANGELOG  ·  ประวัติเวอร์ชัน",
                 font=T.get_font("label", T.SIZE_LABEL_SM, bold=True),
                 fg=T.TS_GOLD, bg=T.SURFACE_LOW, anchor="w").pack(fill=tk.X,
                                                                    pady=(0, T.SPACE_2))

        log_outer = tk.Frame(log_card, bg=T.GHOST_BORDER, padx=1, pady=1)
        log_outer.pack(fill=tk.BOTH, expand=True)

        log_text = tk.Text(
            log_outer,
            font=T.get_font("body", T.SIZE_BODY_SM),
            wrap=tk.WORD,
            borderwidth=0, relief="flat",
            bg=T.SURFACE, fg=T.TEXT_SECONDARY,
            padx=T.SPACE_3, pady=T.SPACE_3,
            highlightthickness=0)
        log_scroll = ttk.Scrollbar(log_outer, orient=tk.VERTICAL, command=log_text.yview)
        log_text.configure(yscrollcommand=log_scroll.set)
        log_text.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)
        log_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        lang = get_lang()
        for i, entry in enumerate(CHANGELOG):
            tag = "ver_current" if i == 0 else "ver"
            log_text.insert(tk.END, f"v{entry['version']}  ({entry['date']})\n", tag)
            changes = entry["changes"].get(lang, entry["changes"].get("en", []))
            for change in changes:
                log_text.insert(tk.END, f"  · {change}\n")
            log_text.insert(tk.END, "\n")

        log_text.tag_configure("ver",
                               font=T.get_font("body", T.SIZE_BODY_MD, bold=True),
                               foreground=T.SUCCESS)
        log_text.tag_configure("ver_current",
                               font=T.get_font("body", T.SIZE_BODY_MD, bold=True),
                               foreground=T.TS_GOLD)
        log_text.config(state=tk.DISABLED)

        # Footer
        tk.Frame(about, height=1, bg=T.GHOST_BORDER).pack(fill=tk.X)
        foot = tk.Frame(about, bg=T.SURFACE_LOW, padx=T.SPACE_6, pady=T.SPACE_3)
        foot.pack(fill=tk.X)
        tk.Label(foot, text="© 2026 Today Style 2100 Co., Ltd.",
                 font=T.get_font("label", T.SIZE_LABEL_SM),
                 fg=T.TEXT_TERTIARY, bg=T.SURFACE_LOW).pack(side=tk.LEFT)

        close_wrap = tk.Frame(foot, bg=T.DIVIDER, padx=1, pady=1)
        close_wrap.pack(side=tk.RIGHT)
        tk.Button(close_wrap, text=t("close_btn"),
                  font=T.get_font("body", T.SIZE_BODY_SM),
                  fg=T.TEXT_SECONDARY, bg=T.SURFACE_LOW,
                  activebackground=T.SURFACE_HIGH,
                  relief="flat", borderwidth=0, cursor="hand2",
                  padx=T.SPACE_5, pady=T.SPACE_1,
                  command=about.destroy).pack()


def main():
    app = BOQConverterApp()
    app.root.mainloop()


if __name__ == "__main__":
    main()
