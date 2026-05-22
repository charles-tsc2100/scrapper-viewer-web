"""
Visual Excel Cell Selector - Shows a preview of the Excel data and lets users
click to assign columns/rows to parser fields.
"""
import tkinter as tk
from tkinter import ttk
import openpyxl
from openpyxl.utils import get_column_letter

from i18n import t, get_lang
import theme as T


# Color scheme for field assignments
FIELD_COLORS = {
    "door_code":      {"bg": "#DBEAFE", "fg": "#1E40AF", "label_key": "field_door_code"},
    "room_name":      {"bg": "#DCFCE7", "fg": "#166534", "label_key": "field_room_name"},
    "dimensions":     {"bg": "#FEF9C3", "fg": "#854D0E", "label_key": "field_dimensions"},
    "brand":          {"bg": "#F3E8FF", "fg": "#6B21A8", "label_key": "field_brand"},
    "model":          {"bg": "#FFE4E6", "fg": "#9F1239", "label_key": "field_model"},
    "description":    {"bg": "#E0F2FE", "fg": "#075985", "label_key": "field_description"},
    "quantity":       {"bg": "#FED7AA", "fg": "#9A3412", "label_key": "field_qty"},
    "unit_price":     {"bg": "#BBFDE2", "fg": "#065F46", "label_key": "field_unit_price"},
    "net_indicator":  {"bg": "#FECDD3", "fg": "#881337", "label_key": "field_net_indicator"},
    "start_row":      {"bg": "#FDE68A", "fg": "#92400E", "label_key": "field_door_code_row"},
    # Cover sheet fields
    "cv_door_code":   {"bg": "#DBEAFE", "fg": "#1E40AF", "label_key": "field_door_code"},
    "cv_room_name":   {"bg": "#DCFCE7", "fg": "#166534", "label_key": "field_room_name"},
    "cv_quantity":    {"bg": "#FED7AA", "fg": "#9A3412", "label_key": "field_quantity"},
    "cv_start_row":   {"bg": "#FDE68A", "fg": "#92400E", "label_key": "field_data_start_row"},
}

# Legacy compat
HAS_BOOTSTRAP = False


def _field_label(field_key):
    """Get the translated label for a field."""
    info = FIELD_COLORS.get(field_key, {})
    label_key = info.get("label_key", field_key)
    return t(label_key)


# Default grid display constants
PREVIEW_ROWS = 20
PREVIEW_COLS = 11   # A through K
CELL_WIDTH = 14
CELL_HEIGHT = 1
ROW_NUM_WIDTH = 5
HEADER_HEIGHT = 1


class ExcelPreviewGrid(tk.Frame):
    """A spreadsheet-like grid that displays actual Excel data and supports
    click-to-assign column/row selection."""

    def __init__(self, parent, on_assign_change=None, **kwargs):
        super().__init__(parent, **kwargs)
        self.on_assign_change = on_assign_change

        # Data storage
        self.cell_data = {}      # (row, col) -> str
        self.start_row = 1       # First row displayed from the file
        self.num_rows = PREVIEW_ROWS
        self.num_cols = PREVIEW_COLS

        # Assignment state
        self.active_field = None   # Currently selected field for assignment
        self.col_assignments = {}  # col_letter -> field_key
        self.row_assignments = {}  # row_number -> field_key
        self.field_to_col = {}     # field_key -> col_letter
        self.field_to_row = {}     # field_key -> row_number

        # UI storage
        self.cell_labels = {}     # (grid_row, grid_col) -> Label
        self.col_headers = {}     # grid_col -> Label
        self.row_headers = {}     # grid_row -> Label

        self._build_grid()

    def _build_grid(self):
        """Build the spreadsheet grid."""
        self.canvas = tk.Canvas(self, bg="white", highlightthickness=0)
        self.h_scroll = ttk.Scrollbar(self, orient=tk.HORIZONTAL, command=self.canvas.xview)
        self.v_scroll = ttk.Scrollbar(self, orient=tk.VERTICAL, command=self.canvas.yview)
        self.canvas.configure(xscrollcommand=self.h_scroll.set, yscrollcommand=self.v_scroll.set)

        self.v_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.h_scroll.pack(side=tk.BOTTOM, fill=tk.X)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.grid_frame = tk.Frame(self.canvas, bg="white")
        self.canvas_window = self.canvas.create_window((0, 0), window=self.grid_frame, anchor="nw")

        self.grid_frame.bind("<Configure>", lambda e: self.canvas.configure(
            scrollregion=self.canvas.bbox("all")))

        self._create_cells()

    def _create_cells(self):
        """Create the grid of label widgets."""
        corner = tk.Label(
            self.grid_frame, text="", width=ROW_NUM_WIDTH, height=HEADER_HEIGHT,
            bg="#E5E7EB", relief="solid", borderwidth=1, font=("Consolas", 9, "bold"),
        )
        corner.grid(row=0, column=0, sticky="nsew")

        for c in range(self.num_cols):
            col_letter = get_column_letter(c + 1)
            lbl = tk.Label(
                self.grid_frame, text=col_letter, width=CELL_WIDTH, height=HEADER_HEIGHT,
                bg="#E5E7EB", fg="#374151", relief="solid", borderwidth=1,
                font=("Consolas", 9, "bold"), cursor="hand2",
            )
            lbl.grid(row=0, column=c + 1, sticky="nsew")
            lbl.bind("<Button-1>", lambda e, col=col_letter: self._on_col_click(col))
            self.col_headers[c] = lbl

        for r in range(self.num_rows):
            row_num = self.start_row + r
            rh = tk.Label(
                self.grid_frame, text=str(row_num), width=ROW_NUM_WIDTH, height=CELL_HEIGHT,
                bg="#F3F4F6", fg="#6B7280", relief="solid", borderwidth=1,
                font=("Consolas", 9), cursor="hand2",
            )
            rh.grid(row=r + 1, column=0, sticky="nsew")
            rh.bind("<Button-1>", lambda e, row=row_num: self._on_row_click(row))
            self.row_headers[r] = rh

            for c in range(self.num_cols):
                cell = tk.Label(
                    self.grid_frame, text="", width=CELL_WIDTH, height=CELL_HEIGHT,
                    bg="white", fg="#111827", relief="solid", borderwidth=1,
                    font=("Consolas", 9), anchor="w", padx=3,
                    cursor="hand2",
                )
                cell.grid(row=r + 1, column=c + 1, sticky="nsew")
                col_letter = get_column_letter(c + 1)
                cell.bind("<Button-1>", lambda e, col=col_letter, row=row_num: self._on_cell_click(col, row))
                self.cell_labels[(r, c)] = cell

    def load_data(self, filepath, sheet_name, start_row=1, num_rows=PREVIEW_ROWS, num_cols=PREVIEW_COLS):
        """Load actual Excel data into the grid."""
        self.cell_data.clear()
        self.start_row = start_row
        self.num_rows = num_rows
        self.num_cols = num_cols

        try:
            wb = openpyxl.load_workbook(filepath, data_only=True)
            if sheet_name not in wb.sheetnames:
                wb.close()
                return
            ws = wb[sheet_name]

            for r in range(num_rows):
                row_num = start_row + r
                for c in range(num_cols):
                    val = ws.cell(row=row_num, column=c + 1).value
                    if val is not None:
                        self.cell_data[(row_num, c + 1)] = str(val)
                    else:
                        self.cell_data[(row_num, c + 1)] = ""
            wb.close()
        except Exception as e:
            print(f"Error loading preview: {e}")

        self._refresh_grid()

    def _refresh_grid(self):
        """Refresh the grid display with current data and assignments."""
        for widget in self.grid_frame.winfo_children():
            widget.destroy()
        self.cell_labels.clear()
        self.col_headers.clear()
        self.row_headers.clear()
        self._create_cells()

        for r in range(self.num_rows):
            row_num = self.start_row + r
            if r in self.row_headers:
                self.row_headers[r].configure(text=str(row_num))
                self.row_headers[r].bind("<Button-1>", lambda e, row=row_num: self._on_row_click(row))

        for r in range(self.num_rows):
            row_num = self.start_row + r
            for c in range(self.num_cols):
                col_idx = c + 1
                text = self.cell_data.get((row_num, col_idx), "")
                display = text[:CELL_WIDTH - 1] if len(text) > CELL_WIDTH - 1 else text

                if (r, c) in self.cell_labels:
                    self.cell_labels[(r, c)].configure(text=display)
                    if len(text) > CELL_WIDTH - 1:
                        self.cell_labels[(r, c)].bind("<Enter>", lambda e, t=text: self._show_tooltip(e, t))
                        self.cell_labels[(r, c)].bind("<Leave>", self._hide_tooltip)

        self._apply_highlights()

    def _apply_highlights(self):
        """Apply color highlighting based on assignments."""
        for r in range(self.num_rows):
            for c in range(self.num_cols):
                if (r, c) in self.cell_labels:
                    self.cell_labels[(r, c)].configure(bg="white", fg="#111827")

        for c in range(self.num_cols):
            if c in self.col_headers:
                self.col_headers[c].configure(bg="#E5E7EB", fg="#374151")
        for r in range(self.num_rows):
            if r in self.row_headers:
                self.row_headers[r].configure(bg="#F3F4F6", fg="#6B7280")

        for col_letter, field_key in self.col_assignments.items():
            color = FIELD_COLORS.get(field_key, {"bg": "#E5E7EB", "fg": "#374151"})
            col_idx = openpyxl.utils.column_index_from_string(col_letter) - 1
            if col_idx < self.num_cols:
                if col_idx in self.col_headers:
                    self.col_headers[col_idx].configure(
                        bg=color["bg"], fg=color["fg"],
                        text=f"{col_letter}\n{_field_label(field_key)}",
                    )
                for r in range(self.num_rows):
                    if (r, col_idx) in self.cell_labels:
                        self.cell_labels[(r, col_idx)].configure(bg=color["bg"], fg=color["fg"])

        for row_num, field_key in self.row_assignments.items():
            color = FIELD_COLORS.get(field_key, {"bg": "#FDE68A", "fg": "#92400E"})
            r = row_num - self.start_row
            if 0 <= r < self.num_rows:
                if r in self.row_headers:
                    self.row_headers[r].configure(bg=color["bg"], fg=color["fg"])
                for c in range(self.num_cols):
                    if (r, c) in self.cell_labels:
                        col_letter = get_column_letter(c + 1)
                        if col_letter not in self.col_assignments:
                            self.cell_labels[(r, c)].configure(bg=color["bg"], fg=color["fg"])

        if self.active_field:
            for c in range(self.num_cols):
                if c in self.col_headers:
                    col_letter = get_column_letter(c + 1)
                    if col_letter not in self.col_assignments:
                        self.col_headers[c].configure(bg="#F0F9FF")

    def _on_col_click(self, col_letter):
        if not self.active_field:
            return
        field = self.active_field
        if field in ("start_row", "cv_start_row"):
            return

        old_col = self.field_to_col.get(field)
        if old_col and old_col in self.col_assignments:
            del self.col_assignments[old_col]

        old_field = self.col_assignments.get(col_letter)
        if old_field:
            if old_field in self.field_to_col:
                del self.field_to_col[old_field]

        self.col_assignments[col_letter] = field
        self.field_to_col[field] = col_letter
        self._apply_highlights()

        if self.on_assign_change:
            self.on_assign_change()

    def _on_row_click(self, row_num):
        if not self.active_field:
            return
        field = self.active_field
        if field not in ("start_row", "cv_start_row"):
            return

        old_row = self.field_to_row.get(field)
        if old_row and old_row in self.row_assignments:
            del self.row_assignments[old_row]

        self.row_assignments[row_num] = field
        self.field_to_row[field] = row_num
        self._apply_highlights()

        if self.on_assign_change:
            self.on_assign_change()

    def _on_cell_click(self, col_letter, row_num):
        if not self.active_field:
            return
        if self.active_field in ("start_row", "cv_start_row"):
            self._on_row_click(row_num)
        else:
            self._on_col_click(col_letter)

    def set_active_field(self, field_key):
        self.active_field = field_key
        self._apply_highlights()

    def set_assignments_from_config(self, assignments):
        self.col_assignments.clear()
        self.row_assignments.clear()
        self.field_to_col.clear()
        self.field_to_row.clear()

        for field_key, value in assignments.items():
            if field_key in ("start_row", "cv_start_row"):
                row_num = int(value)
                self.row_assignments[row_num] = field_key
                self.field_to_row[field_key] = row_num
            else:
                col_letter = str(value).upper()
                self.col_assignments[col_letter] = field_key
                self.field_to_col[field_key] = col_letter

        self._apply_highlights()

    def get_assignments(self):
        result = {}
        result.update(self.field_to_col)
        result.update(self.field_to_row)
        return result

    _tooltip = None

    def _show_tooltip(self, event, text):
        if self._tooltip:
            self._tooltip.destroy()
        self._tooltip = tk.Toplevel(self)
        self._tooltip.wm_overrideredirect(True)
        self._tooltip.wm_geometry(f"+{event.x_root+10}+{event.y_root+10}")
        lbl = tk.Label(
            self._tooltip, text=text, bg="#1F2937", fg="white",
            font=("Consolas", 9), padx=8, pady=4, relief="solid", borderwidth=1,
        )
        lbl.pack()

    def _hide_tooltip(self, event=None):
        if self._tooltip:
            self._tooltip.destroy()
            self._tooltip = None


class CellSelectorDialog(tk.Toplevel):
    """Modal dialog with Excel preview grid and field assignment panel."""

    def __init__(self, parent, config, boq_files, on_save):
        super().__init__(parent)
        self.title(t("cell_ref_title"))
        self.geometry("1150x720")
        self.minsize(1000, 620)
        self.configure(bg=T.SURFACE)
        self.transient(parent)
        self.grab_set()

        self.config = config
        self.boq_files = boq_files
        self.on_save = on_save

        self.available_sheets = []
        self.cover_sheets = []
        self._scan_sheets()

        self._build_ui()
        self._load_initial_data()

        self.update_idletasks()
        px = parent.winfo_x() + (parent.winfo_width() - self.winfo_width()) // 2
        py = parent.winfo_y() + (parent.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{max(0,px)}+{max(0,py)}")

    def _scan_sheets(self):
        skip = {"\u0e43\u0e1a\u0e1b\u0e30\u0e2b\u0e19\u0e49\u0e32", "SUM"}
        for fp in self.boq_files:
            try:
                wb = openpyxl.load_workbook(fp, read_only=True)
                for name in wb.sheetnames:
                    if name == "\u0e43\u0e1a\u0e1b\u0e30\u0e2b\u0e19\u0e49\u0e32":
                        self.cover_sheets.append((fp, name))
                    elif (
                        name not in skip
                        and not name.startswith("FM-")
                        and wb[name].sheet_state == "visible"
                    ):
                        self.available_sheets.append((fp, name))
                wb.close()
            except Exception:
                pass

    def _build_ui(self):
        main = tk.Frame(self, bg=T.SURFACE, padx=T.SPACE_4, pady=T.SPACE_4)
        main.pack(fill=tk.BOTH, expand=True)

        self.notebook = ttk.Notebook(main)
        self.notebook.pack(fill=tk.BOTH, expand=True, pady=(0, T.SPACE_3))

        # --- BOQ Sheet Tab ---
        boq_tab = tk.Frame(self.notebook, bg=T.SURFACE)
        self.notebook.add(boq_tab, text=t("boq_sheet_tab"))
        self._build_boq_tab(boq_tab)

        # --- Cover Sheet Tab ---
        cover_tab = tk.Frame(self.notebook, bg=T.SURFACE)
        self.notebook.add(cover_tab, text=t("cover_sheet_tab"))
        self._build_cover_tab(cover_tab)

        # Bottom buttons - design system styled
        btn_frame = tk.Frame(main, bg=T.SURFACE)
        btn_frame.pack(fill=tk.X)

        save_btn = tk.Button(
            btn_frame, text=t("save_reparse_btn"), command=self._save,
            font=T.get_font("body", bold=True),
            fg=T.TEXT_ON_ACCENT, bg=T.PRIMARY_ACCENT,
            activebackground=T.PRIMARY_HOVER,
            relief="flat", borderwidth=0, cursor="hand2",
            padx=T.SPACE_5, pady=T.SPACE_2)
        cancel_btn = tk.Button(
            btn_frame, text=t("cancel_btn"), command=self._cancel,
            font=T.get_font("body"),
            fg=T.TEXT_SECONDARY, bg=T.SURFACE_HIGH,
            activebackground=T.GHOST_BORDER,
            relief="flat", borderwidth=0, cursor="hand2",
            padx=T.SPACE_4, pady=T.SPACE_2)

        save_btn.pack(side=tk.RIGHT, padx=(T.SPACE_3, 0))
        cancel_btn.pack(side=tk.RIGHT)

    def _build_boq_tab(self, parent):
        top = tk.Frame(parent, bg=T.SURFACE, padx=T.SPACE_2, pady=T.SPACE_2)
        top.pack(fill=tk.X)

        tk.Label(top, text=t("preview_sheet_label"),
                 font=T.get_font("body", T.SIZE_BODY_SM),
                 fg=T.TEXT_SECONDARY, bg=T.SURFACE).pack(side=tk.LEFT)
        self.sheet_var = tk.StringVar()
        sheet_names = [f"{s[1]}  ({s[0].split('/')[-1].split(chr(92))[-1]})" for s in self.available_sheets]
        self.sheet_combo = ttk.Combobox(top, textvariable=self.sheet_var, values=sheet_names, width=45, state="readonly")
        self.sheet_combo.pack(side=tk.LEFT, padx=(T.SPACE_2, 0))
        self.sheet_combo.bind("<<ComboboxSelected>>", self._on_sheet_change)

        tk.Label(top, text=t("start_from_row_label"),
                 font=T.get_font("body", T.SIZE_BODY_SM),
                 fg=T.TEXT_SECONDARY, bg=T.SURFACE).pack(side=tk.LEFT, padx=(T.SPACE_5, 0))
        self.start_row_var = tk.StringVar(value="10")
        start_spin = ttk.Spinbox(top, textvariable=self.start_row_var, from_=1, to=50, width=5,
                                 command=self._on_start_row_change)
        start_spin.pack(side=tk.LEFT, padx=(T.SPACE_1, 0))
        start_spin.bind("<Return>", lambda e: self._on_start_row_change())

        content = tk.Frame(parent, bg=T.SURFACE)
        content.pack(fill=tk.BOTH, expand=True, padx=T.SPACE_2, pady=T.SPACE_2)

        self.boq_field_panel = tk.Frame(content, bg=T.SURFACE_LOW, padx=T.SPACE_3, pady=T.SPACE_3)
        self.boq_field_panel.pack(side=tk.LEFT, fill=tk.Y, padx=(0, T.SPACE_3))
        self._build_boq_fields()

        grid_frame = tk.Frame(content, bg=T.SURFACE)
        grid_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.boq_grid = ExcelPreviewGrid(grid_frame, on_assign_change=self._on_boq_assign_change)
        self.boq_grid.pack(fill=tk.BOTH, expand=True)

        tk.Label(parent, text=t("grid_instruction"),
                 font=T.get_font("label"), fg=T.TEXT_TERTIARY,
                 bg=T.SURFACE, wraplength=1000).pack(fill=tk.X, padx=T.SPACE_2, pady=(T.SPACE_1, T.SPACE_2))

    def _build_boq_fields(self):
        tk.Label(self.boq_field_panel, text=t("click_field_instruction"),
                 font=T.get_font("label"), fg=T.TEXT_TERTIARY,
                 bg=T.SURFACE_LOW).pack(pady=(0, T.SPACE_2))

        self.boq_field_btns = {}
        fields = [
            ("door_code", "door_code_col"),
            ("start_row", "door_code_row"),
            ("room_name", "room_name_col"),
            ("dimensions", "dimensions_col"),
            None,
            ("brand", "brand_col"),
            ("model", "model_col"),
            ("description", "description_col"),
            ("quantity", "qty_col"),
            None,
            ("unit_price", "unit_price_col"),
            ("net_indicator", "net_indicator_col"),
        ]

        for item in fields:
            if item is None:
                tk.Frame(self.boq_field_panel, height=1, bg=T.GHOST_BORDER).pack(fill=tk.X, pady=T.SPACE_2)
                continue

            key, label_key = item
            color = FIELD_COLORS[key]
            btn = tk.Button(
                self.boq_field_panel, text=f"  {t(label_key)}  ", anchor="w",
                bg=color["bg"], fg=color["fg"], activebackground=color["bg"],
                font=T.get_font("body", T.SIZE_BODY_SM),
                relief="flat", borderwidth=0,
                cursor="hand2", width=26,
                padx=T.SPACE_2, pady=3,
            )
            btn.pack(fill=tk.X, pady=2)
            btn.bind("<Button-1>", lambda e, k=key: self._activate_boq_field(k))
            self.boq_field_btns[key] = (btn, label_key)

    def _activate_boq_field(self, field_key):
        for k, (btn, _) in self.boq_field_btns.items():
            color = FIELD_COLORS[k]
            btn.configure(relief="flat", borderwidth=0,
                          font=T.get_font("body", T.SIZE_BODY_SM))

        if field_key in self.boq_field_btns:
            btn, _ = self.boq_field_btns[field_key]
            btn.configure(relief="solid", borderwidth=2,
                          font=T.get_font("body", T.SIZE_BODY_SM, bold=True))

        self.boq_grid.set_active_field(field_key)

    def _build_cover_tab(self, parent):
        top = tk.Frame(parent, bg=T.SURFACE, padx=T.SPACE_2, pady=T.SPACE_2)
        top.pack(fill=tk.X)

        tk.Label(top, text=t("preview_cover_label"),
                 font=T.get_font("body", T.SIZE_BODY_SM),
                 fg=T.TEXT_SECONDARY, bg=T.SURFACE).pack(side=tk.LEFT)
        self.cover_var = tk.StringVar()
        cover_names = [f"\u0e43\u0e1a\u0e1b\u0e30\u0e2b\u0e19\u0e49\u0e32  ({s[0].split('/')[-1].split(chr(92))[-1]})" for s in self.cover_sheets]
        self.cover_combo = ttk.Combobox(top, textvariable=self.cover_var, values=cover_names, width=45, state="readonly")
        self.cover_combo.pack(side=tk.LEFT, padx=(T.SPACE_2, 0))
        self.cover_combo.bind("<<ComboboxSelected>>", self._on_cover_change)

        content = tk.Frame(parent, bg=T.SURFACE)
        content.pack(fill=tk.BOTH, expand=True, padx=T.SPACE_2, pady=T.SPACE_2)

        self.cover_field_panel = tk.Frame(content, bg=T.SURFACE_LOW, padx=T.SPACE_3, pady=T.SPACE_3)
        self.cover_field_panel.pack(side=tk.LEFT, fill=tk.Y, padx=(0, T.SPACE_3))
        self._build_cover_fields()

        grid_frame = tk.Frame(content, bg=T.SURFACE)
        grid_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.cover_grid = ExcelPreviewGrid(grid_frame, on_assign_change=self._on_cover_assign_change)
        self.cover_grid.pack(fill=tk.BOTH, expand=True)

        tk.Label(parent, text=t("grid_instruction"),
                 font=T.get_font("label"), fg=T.TEXT_TERTIARY,
                 bg=T.SURFACE, wraplength=1000).pack(fill=tk.X, padx=T.SPACE_2, pady=(T.SPACE_1, T.SPACE_2))

    def _build_cover_fields(self):
        tk.Label(self.cover_field_panel, text=t("click_field_instruction"),
                 font=T.get_font("label"), fg=T.TEXT_TERTIARY,
                 bg=T.SURFACE_LOW).pack(pady=(0, T.SPACE_2))

        self.cover_field_btns = {}
        fields = [
            ("cv_door_code", "cv_door_code_col"),
            ("cv_room_name", "cv_room_name_col"),
            ("cv_quantity", "cv_quantity_col"),
            ("cv_start_row", "cv_data_start_row"),
        ]

        for key, label_key in fields:
            color = FIELD_COLORS[key]
            btn = tk.Button(
                self.cover_field_panel, text=f"  {t(label_key)}  ", anchor="w",
                bg=color["bg"], fg=color["fg"], activebackground=color["bg"],
                font=T.get_font("body", T.SIZE_BODY_SM),
                relief="flat", borderwidth=1,
                cursor="hand2", width=28,
                wraplength=180,
            )
            btn.pack(fill=tk.X, pady=2)
            btn.bind("<Button-1>", lambda e, k=key: self._activate_cover_field(k))
            self.cover_field_btns[key] = (btn, label_key)

    def _activate_cover_field(self, field_key):
        for k, (btn, _) in self.cover_field_btns.items():
            color = FIELD_COLORS[k]
            btn.configure(relief="flat", borderwidth=1,
                          font=T.get_font("body", T.SIZE_BODY_SM))

        if field_key in self.cover_field_btns:
            btn, _ = self.cover_field_btns[field_key]
            btn.configure(relief="solid", borderwidth=2,
                          font=T.get_font("body", T.SIZE_BODY_SM, bold=True))

        self.cover_grid.set_active_field(field_key)

    def _load_initial_data(self):
        if self.available_sheets:
            self.sheet_combo.current(0)
            self._load_boq_sheet(0)

        if self.cover_sheets:
            self.cover_combo.current(0)
            self._load_cover_sheet(0)

    def _load_boq_sheet(self, idx):
        if idx >= len(self.available_sheets):
            return
        fp, sheet_name = self.available_sheets[idx]
        start_row = int(self.start_row_var.get()) if self.start_row_var.get().isdigit() else 10
        self.boq_grid.load_data(fp, sheet_name, start_row=start_row, num_rows=PREVIEW_ROWS, num_cols=PREVIEW_COLS)

        cfg = self.config.sheet_config
        assignments = {
            "door_code": cfg.door_code_col,
            "start_row": cfg.door_code_start_row,
            "room_name": cfg.room_name_col,
            "dimensions": cfg.dimensions_col,
            "brand": cfg.brand_col,
            "model": cfg.model_col,
            "description": cfg.description_col,
            "quantity": cfg.quantity_col,
            "unit_price": cfg.unit_price_col,
            "net_indicator": cfg.net_indicator_col,
        }
        self.boq_grid.set_assignments_from_config(assignments)
        self._update_boq_field_labels()

    def _load_cover_sheet(self, idx):
        if idx >= len(self.cover_sheets):
            return
        fp, sheet_name = self.cover_sheets[idx]
        self.cover_grid.load_data(fp, sheet_name, start_row=5, num_rows=PREVIEW_ROWS, num_cols=10)

        cfg = self.config.cover_config
        assignments = {
            "cv_door_code": cfg.door_code_col,
            "cv_room_name": cfg.room_name_col,
            "cv_quantity": cfg.quantity_col,
            "cv_start_row": cfg.data_start_row,
        }
        self.cover_grid.set_assignments_from_config(assignments)
        self._update_cover_field_labels()

    def _on_sheet_change(self, event=None):
        idx = self.sheet_combo.current()
        if idx >= 0:
            self._load_boq_sheet(idx)

    def _on_cover_change(self, event=None):
        idx = self.cover_combo.current()
        if idx >= 0:
            self._load_cover_sheet(idx)

    def _on_start_row_change(self, event=None):
        idx = self.sheet_combo.current()
        if idx >= 0:
            fp, sheet_name = self.available_sheets[idx]
            start_row = int(self.start_row_var.get()) if self.start_row_var.get().isdigit() else 10
            self.boq_grid.load_data(fp, sheet_name, start_row=start_row, num_rows=PREVIEW_ROWS, num_cols=PREVIEW_COLS)
            self.boq_grid._apply_highlights()

    def _on_boq_assign_change(self):
        self._update_boq_field_labels()

    def _on_cover_assign_change(self):
        self._update_cover_field_labels()

    def _update_boq_field_labels(self):
        assignments = self.boq_grid.get_assignments()
        for key, (btn, label_key) in self.boq_field_btns.items():
            base_label = t(label_key)
            val = assignments.get(key, "?")
            if key == "start_row":
                btn.configure(text=f"  {base_label}: Row {val}  ")
            else:
                btn.configure(text=f"  {base_label}: Col {val}  ")

    def _update_cover_field_labels(self):
        assignments = self.cover_grid.get_assignments()
        for key, (btn, label_key) in self.cover_field_btns.items():
            base_label = t(label_key)
            val = assignments.get(key, "?")
            if key == "cv_start_row":
                btn.configure(text=f"  {base_label}: Row {val}  ")
            else:
                btn.configure(text=f"  {base_label}: Col {val}  ")

    def _save(self):
        from boq_config import BOQConfig, BOQSheetConfig, CoverSheetConfig

        cfg = BOQConfig()

        ba = self.boq_grid.get_assignments()
        if "door_code" in ba:
            cfg.sheet_config.door_code_col = ba["door_code"]
        if "start_row" in ba:
            cfg.sheet_config.door_code_start_row = int(ba["start_row"])
        if "room_name" in ba:
            cfg.sheet_config.room_name_col = ba["room_name"]
        if "dimensions" in ba:
            cfg.sheet_config.dimensions_col = ba["dimensions"]
        if "brand" in ba:
            cfg.sheet_config.brand_col = ba["brand"]
        if "model" in ba:
            cfg.sheet_config.model_col = ba["model"]
        if "description" in ba:
            cfg.sheet_config.description_col = ba["description"]
        if "quantity" in ba:
            cfg.sheet_config.quantity_col = ba["quantity"]
        if "unit_price" in ba:
            cfg.sheet_config.unit_price_col = ba["unit_price"]
        if "net_indicator" in ba:
            cfg.sheet_config.net_indicator_col = ba["net_indicator"]

        qty_col = cfg.sheet_config.quantity_col
        qty_idx = openpyxl.utils.column_index_from_string(qty_col)
        merge_cols = [get_column_letter(i) for i in range(qty_idx, min(qty_idx + 5, 27))]
        cfg.sheet_config.merge_check_cols = ",".join(merge_cols)

        ca = self.cover_grid.get_assignments()
        if "cv_door_code" in ca:
            cfg.cover_config.door_code_col = ca["cv_door_code"]
        if "cv_room_name" in ca:
            cfg.cover_config.room_name_col = ca["cv_room_name"]
        if "cv_quantity" in ca:
            cfg.cover_config.quantity_col = ca["cv_quantity"]
        if "cv_start_row" in ca:
            cfg.cover_config.data_start_row = int(ca["cv_start_row"])

        self.on_save(cfg)
        self.destroy()

    def _cancel(self):
        self.destroy()
