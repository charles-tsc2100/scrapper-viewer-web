"""
BOQ Parser Configuration - Cell reference settings with smart defaults.
"""
from dataclasses import dataclass, field
from typing import Optional
import openpyxl
import re


@dataclass
class BOQSheetConfig:
    """Cell reference config for a single BOQ sheet."""
    # Door code area
    door_code_col: str = "B"            # Column for door codes (e.g. "B")
    door_code_start_row: int = 12       # First row to look for door codes
    room_name_col: str = "C"            # Column for room names
    dimensions_col: str = "E"           # Column for door dimensions

    # Product data area
    brand_col: str = "D"                # Column for brand
    model_col: str = "E"                # Column for model
    description_col: str = "F"          # Column for description
    quantity_col: str = "G"             # Column for quantity per door
    unit_price_col: str = "I"           # Column for unit price
    net_indicator_col: str = "J"        # Column that shows "NET" or discount value

    # Merged cell detection columns (for product sets like handle+lock)
    merge_check_cols: str = "G,H,I,J,K"  # Columns to check for merged cells


@dataclass
class CoverSheetConfig:
    """Cell reference config for the ใบปะหน้า (cover sheet)."""
    door_code_col: str = "E"            # Column with door codes
    room_name_col: str = "F"            # Column with room/location names
    quantity_col: str = "G"             # Column with quantities
    data_start_row: int = 10            # First row to scan


@dataclass
class BOQConfig:
    """Full configuration for BOQ parsing."""
    sheet_config: BOQSheetConfig = field(default_factory=BOQSheetConfig)
    cover_config: CoverSheetConfig = field(default_factory=CoverSheetConfig)

    def to_dict(self):
        """Serialize to dict for display/storage."""
        return {
            "sheet": {
                "door_code_col": self.sheet_config.door_code_col,
                "door_code_start_row": self.sheet_config.door_code_start_row,
                "room_name_col": self.sheet_config.room_name_col,
                "dimensions_col": self.sheet_config.dimensions_col,
                "brand_col": self.sheet_config.brand_col,
                "model_col": self.sheet_config.model_col,
                "description_col": self.sheet_config.description_col,
                "quantity_col": self.sheet_config.quantity_col,
                "unit_price_col": self.sheet_config.unit_price_col,
                "net_indicator_col": self.sheet_config.net_indicator_col,
                "merge_check_cols": self.sheet_config.merge_check_cols,
            },
            "cover": {
                "door_code_col": self.cover_config.door_code_col,
                "room_name_col": self.cover_config.room_name_col,
                "quantity_col": self.cover_config.quantity_col,
                "data_start_row": self.cover_config.data_start_row,
            },
        }


def _col_to_idx(col_letter):
    """Convert column letter(s) to 1-based index. E.g., 'A'->1, 'B'->2, 'AA'->27."""
    return openpyxl.utils.column_index_from_string(col_letter.upper())


def _idx_to_col(idx):
    """Convert 1-based index to column letter."""
    return openpyxl.utils.get_column_letter(idx)


def detect_config(filepath):
    """Auto-detect cell references from a BOQ file.

    Opens the file, examines one data sheet and the cover sheet,
    and returns a BOQConfig with detected values.
    """
    config = BOQConfig()

    try:
        wb = openpyxl.load_workbook(filepath, data_only=True)

        # --- Detect BOQ sheet layout from first non-cover sheet ---
        skip = {"ใบปะหน้า", "SUM"}
        data_sheet = None
        for name in wb.sheetnames:
            if name in skip or name.startswith("FM-"):
                continue
            ws = wb[name]
            if ws.sheet_state != "visible":
                continue
            data_sheet = ws
            break

        if data_sheet:
            config.sheet_config = _detect_sheet_config(data_sheet)

        # --- Detect cover sheet layout ---
        if "ใบปะหน้า" in wb.sheetnames:
            cover_ws = wb["ใบปะหน้า"]
            config.cover_config = _detect_cover_config(cover_ws)

        wb.close()
    except Exception as e:
        print(f"Config detection warning: {e}")

    return config


def _detect_sheet_config(ws):
    """Detect cell references from a BOQ data sheet."""
    cfg = BOQSheetConfig()

    # Find header row by looking for "NO." in column B
    header_row = None
    for row_idx in range(1, 25):
        val = ws.cell(row=row_idx, column=2).value
        if val is not None and str(val).strip().upper() in ("NO.", "NO"):
            header_row = row_idx
            break

    if header_row is None:
        return cfg

    # Door codes are in the rows above the header row
    # Scan upward from header to find the TOPMOST row with a door-code-like value in col B
    topmost_door_row = None
    for row_idx in range(header_row - 1, max(0, header_row - 10), -1):
        val = ws.cell(row=row_idx, column=2).value
        if val and isinstance(val, str):
            cleaned = val.strip()
            if cleaned and len(cleaned) < 20 and not any(
                kw in cleaned.lower() for kw in ["project", "zone", "design", "date", "option",
                                                   "door hardware", "hardware", "access control"]
            ):
                topmost_door_row = row_idx
                # Don't break - keep scanning upward to find the very first row

    if topmost_door_row is not None:
        cfg.door_code_start_row = topmost_door_row
        cfg.door_code_col = "B"

    # Detect product columns from header row labels
    # Scan header row for known labels
    header_labels = {}
    for col in range(1, 15):
        val = ws.cell(row=header_row, column=col).value
        if val:
            header_labels[col] = str(val).strip().upper()

    # Map known headers to config fields
    for col, label in header_labels.items():
        letter = _idx_to_col(col)
        if label in ("BRAND",):
            cfg.brand_col = letter
        elif label in ("MODEL",):
            cfg.model_col = letter
        elif label in ("DESCRIPTION", "DESC"):
            cfg.description_col = letter
        elif label in ("Q.TY", "QTY", "Q.TY/SET", "จำนวน"):
            cfg.quantity_col = letter
        elif label in ("UNIT", "UNIT PRICE", "ราคา/หน่วย"):
            cfg.unit_price_col = letter
        elif label in ("NET", "NET AFTER", "NET AFTER DISCOUNT"):
            cfg.net_indicator_col = letter

    return cfg


def _detect_cover_config(ws):
    """Detect cell references from the cover sheet (ใบปะหน้า)."""
    cfg = CoverSheetConfig()

    # Look for the first row with a door-code-like value and a numeric quantity
    for row_idx in range(5, min(ws.max_row + 1, 50)):
        for col in range(3, 10):
            val = ws.cell(row=row_idx, column=col).value
            if val and isinstance(val, str) and len(val.strip()) < 10:
                code = val.strip()
                # Check if it looks like a door code (alphanumeric, may have hyphens)
                if re.match(r'^[A-Za-z]+[-]?\d', code):
                    # Found a door code - check for qty nearby
                    for qty_col in range(col + 1, col + 5):
                        qty_val = ws.cell(row=row_idx, column=qty_col).value
                        if isinstance(qty_val, (int, float)) and qty_val > 0:
                            cfg.door_code_col = _idx_to_col(col)
                            cfg.quantity_col = _idx_to_col(qty_col)
                            cfg.data_start_row = row_idx
                            # Room name is typically between door code and qty
                            if qty_col > col + 1:
                                cfg.room_name_col = _idx_to_col(col + 1)
                            return cfg

    return cfg
