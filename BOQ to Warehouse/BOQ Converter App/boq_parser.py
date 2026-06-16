"""
BOQ Parser - Extracts door types and hardware products from BOQ Excel files.
"""
import openpyxl
import re
from dataclasses import dataclass, field
from typing import Optional
from boq_config import BOQConfig, BOQSheetConfig, CoverSheetConfig, _col_to_idx


@dataclass
class Product:
    model: str
    brand: str = ""
    description: str = ""
    unit_price: float = 0.0
    is_net_price: bool = False
    raw_list_price: float = 0.0  # Always the raw col-I (UNIT) value, before any J override
    is_option: bool = False       # True when product comes from an OPTION section of the BOQ


@dataclass
class DoorProduct:
    product: Product
    quantity: float = 0


@dataclass
class DoorType:
    code: str
    room_name: str = ""
    dimensions: str = ""
    products: list = field(default_factory=list)
    discount_rate: float = 0.0
    source_sheet: str = ""  # BOQ sheet this came from
    source_group: str = ""  # Group label this door code falls under (e.g. "Group 1")


@dataclass
class BOQCategory:
    name: str
    door_types: list = field(default_factory=list)
    source_file: str = ""


SKIP_SHEETS = {"ใบปะหน้า", "SUM"}


def _clean_str(val):
    if val is None:
        return ""
    return str(val).strip()


# Optional override map: lowercase key -> canonical display form.
# Empty by default (pure uppercase). Add entries like {"unifi": "UniFi"} if needed later.
BRAND_OVERRIDES: dict = {}


def normalize_brand(value):
    s = (value or "").strip()
    if not s:
        return ""
    return BRAND_OVERRIDES.get(s.lower(), s.upper())


def _to_float(val):
    if val is None:
        return 0.0
    if isinstance(val, (int, float)):
        return float(val)
    try:
        return float(str(val).replace(",", ""))
    except (ValueError, TypeError):
        return 0.0


def _is_template_sheet(ws, cfg):
    brand_col = _col_to_idx(cfg.brand_col)
    has_brand = False
    for row in ws.iter_rows(min_row=14, max_row=30, min_col=brand_col, max_col=brand_col, values_only=True):
        if row[0] is not None and str(row[0]).strip():
            has_brand = True
            break
    return not has_brand


def _find_header_row(ws):
    for row_idx in range(1, min(ws.max_row + 1, 25)):
        val = ws.cell(row=row_idx, column=2).value
        if val is not None and str(val).strip().upper() in ("NO.", "NO"):
            return row_idx
    return None


def _find_door_code_start_row(ws, header_row, door_code_col_idx):
    """Dynamically detect the first row containing door code info for THIS sheet.

    Scans upward from the header row looking for the topmost row that contains
    a non-empty, non-keyword value in the door code column. This replaces the
    global door_code_start_row config value, making it work regardless of whether
    sheets use Group-based or door-code-based naming.
    """
    skip_keywords = ["project", "zone", "design", "date", "ใบเสนอราคา",
                     "อุปกรณ์ประกอบประตู", "option",
                     "door hardware", "hardware"]

    topmost = header_row  # fallback to header_row if nothing found
    for row_idx in range(header_row - 1, max(0, header_row - 15), -1):
        val = ws.cell(row=row_idx, column=door_code_col_idx).value
        if val and isinstance(val, str):
            cleaned = val.strip()
            if cleaned and len(cleaned) < 80 and not any(
                kw in cleaned.lower() for kw in skip_keywords
            ):
                topmost = row_idx
                # Keep scanning upward to find the very first relevant row

    return topmost


def _find_discount_rate(ws, header_row, cfg):
    net_col = _col_to_idx(cfg.net_indicator_col)
    for row_idx in range(max(1, header_row - 5), header_row + 2):
        val = ws.cell(row=row_idx, column=net_col).value
        if isinstance(val, (int, float)) and 0 < val < 1:
            return val
    return 0.0


def _build_merged_value_lookup(ws):
    """Build a lookup dict: (row, col) -> value from the top-left cell of each merged range.

    In openpyxl, only the top-left cell of a merged range holds the actual value;
    all other cells in the range return None. This lookup lets callers retrieve the
    correct value for any cell that is part of a merged range.

    Use case: BOQ sheets often merge the price cells (cols I and J) across two rows
    for a paired product set (e.g. TYPE52 handle + U9LA52 lock body), so the second
    product row appears to have no price even though it shares the merged price above.
    """
    lookup = {}
    for merged_range in ws.merged_cells.ranges:
        top_value = ws.cell(row=merged_range.min_row, column=merged_range.min_col).value
        if top_value is None:
            continue  # Nothing to propagate
        for row in range(merged_range.min_row, merged_range.max_row + 1):
            for col in range(merged_range.min_col, merged_range.max_col + 1):
                if row == merged_range.min_row and col == merged_range.min_col:
                    continue  # Top-left cell already returns its own value directly
                lookup[(row, col)] = top_value
    return lookup


def _get_merged_row_sets(ws, data_start, data_end, cfg):
    merge_col_indices = set()
    for c in cfg.merge_check_cols.split(","):
        c = c.strip()
        if c:
            merge_col_indices.add(_col_to_idx(c))

    merged_sets = {}
    merge_rows = {}
    for merged_range in ws.merged_cells.ranges:
        min_row = merged_range.min_row
        max_row = merged_range.max_row
        min_col = merged_range.min_col
        max_col = merged_range.max_col
        if max_row - min_row != 1:
            continue
        if min_row < data_start or max_row > data_end:
            continue
        for col in range(min_col, max_col + 1):
            if col in merge_col_indices:
                if min_row not in merge_rows:
                    merge_rows[min_row] = set()
                merge_rows[min_row].add(col)

    qty_col = _col_to_idx(cfg.quantity_col)
    for first_row, cols in merge_rows.items():
        if qty_col in cols:
            merged_sets[first_row] = first_row + 1
    return merged_sets


def _derive_door_label(sheet_name, base_code):
    """When a sheet name contains more info than the base code, create a richer label."""
    sn = sheet_name.strip()
    for sep in ["-", " ", "_"]:
        if base_code + sep in sn:
            suffix = sn.split(base_code + sep, 1)[1].strip(" -_")
            if suffix:
                return f"{base_code} {suffix}"
            break
    sn_upper = sn.upper()
    bc_upper = base_code.upper()
    for sep in ["-", " ", "_"]:
        if bc_upper + sep in sn_upper:
            idx = sn_upper.index(bc_upper + sep) + len(base_code) + 1
            suffix = sn[idx:].strip(" -_")
            if suffix:
                return f"{base_code} {suffix}"
            break
    return base_code


def _expand_comma_sheet_name(sheet_name):
    """Expand a comma-separated sheet name into individual door codes.

    Examples:
        "D1,2,5,3"         -> ["D1", "D2", "D5", "D3"]
        "D-3,21"           -> ["D-3", "D-21"]
        "D-9,22-23,25,30"  -> ["D-9", "D-22", "D-23", "D-25", "D-30"]
        "D4,D4A,D9"        -> ["D4", "D4A", "D9"]
        "WD6-7,9,11"       -> ["WD6", "WD7", "WD9", "WD11"]
        "A"                -> None (not comma-separated)
    """
    if "," not in sheet_name:
        return None

    parts = [p.strip() for p in sheet_name.split(",")]
    if not parts:
        return None

    # Extract the prefix from the first part (letters + optional hyphen before first digit)
    first = parts[0]
    prefix_match = re.match(r'^([A-Za-z]+[-]?)', first)
    if not prefix_match:
        return None
    prefix = prefix_match.group(1)

    results = []
    for part in parts:
        # If part already starts with a letter prefix, keep it as-is
        if re.match(r'^[A-Za-z]', part):
            # Could be "D4A" or "D-3" - expand ranges within it
            range_match = re.match(r'^([A-Za-z]+[-]?)(\d+)[-](\d+)$', part)
            if range_match:
                p, start, end = range_match.group(1), int(range_match.group(2)), int(range_match.group(3))
                for n in range(start, end + 1):
                    results.append(f"{p}{n}")
            else:
                results.append(part)
        else:
            # Just a number or number range - apply the prefix
            range_match = re.match(r'^(\d+)[-](\d+)$', part)
            if range_match:
                start, end = int(range_match.group(1)), int(range_match.group(2))
                for n in range(start, end + 1):
                    results.append(f"{prefix}{n}")
            else:
                results.append(f"{prefix}{part}")

    return results if results else None


def _is_group_label(text):
    """Check if a string is a Group label like 'Group 1', 'Group 2A', 'Group 3', etc."""
    if not text:
        return False
    return bool(re.match(r'^Group\s*\d', text.strip(), re.IGNORECASE))


def parse_boq_sheet(ws, sheet_name, cfg=None):
    """Parse a single BOQ sheet and return a list of DoorType objects."""
    if cfg is None:
        cfg = BOQSheetConfig()

    if _is_template_sheet(ws, cfg):
        return []

    header_row = _find_header_row(ws)
    if header_row is None:
        return []

    discount_rate = _find_discount_rate(ws, header_row, cfg)

    # Column indices from config
    door_code_col = _col_to_idx(cfg.door_code_col)
    room_col = _col_to_idx(cfg.room_name_col)
    dim_col = _col_to_idx(cfg.dimensions_col)
    brand_col = _col_to_idx(cfg.brand_col)
    model_col = _col_to_idx(cfg.model_col)
    desc_col = _col_to_idx(cfg.description_col)
    qty_col = _col_to_idx(cfg.quantity_col)
    price_col = _col_to_idx(cfg.unit_price_col)
    net_col = _col_to_idx(cfg.net_indicator_col)

    # --- PER-SHEET dynamic detection of door code start row ---
    # Instead of relying on cfg.door_code_start_row (detected from the first sheet),
    # scan upward from this sheet's own header row.
    door_code_start = _find_door_code_start_row(ws, header_row, door_code_col)

    # Extract door codes from door_code_start..header_row
    skip_keywords = ["project", "zone", "design", "date", "เลขบาน", "ชื่อห้อง", "option",
                      "door hardware", "hardware"]
    raw_door_codes = []
    current_group = ""  # Track which Group label each door code falls under
    for row_idx in range(door_code_start, header_row):
        code = _clean_str(ws.cell(row=row_idx, column=door_code_col).value)
        dim = _clean_str(ws.cell(row=row_idx, column=dim_col).value)
        room = _clean_str(ws.cell(row=row_idx, column=room_col).value)
        if code and not any(kw in code.lower() for kw in skip_keywords):
            # Track "Group X" labels as the current group context
            if _is_group_label(code):
                current_group = code
                continue
            raw_door_codes.append({"code": code, "room": room, "dimensions": dim, "group": current_group})

    # Filter: if we have real door schedule codes (D101, D-3, WD1, AD1, etc.),
    # remove entries that are just sheet names or single letters
    # Pattern: optional prefix letters, then D (or just a letter prefix), optional hyphen, then digit
    _schedule_re = r'^[A-Z]*D[-]?\d'
    schedule_codes = [dc for dc in raw_door_codes if re.match(_schedule_re, dc["code"], re.IGNORECASE)]
    non_schedule = [dc for dc in raw_door_codes if not re.match(_schedule_re, dc["code"], re.IGNORECASE)]

    if schedule_codes:
        # We have proper door schedule codes, use only those
        raw_door_codes = schedule_codes
    elif non_schedule:
        # No schedule codes found, keep whatever we have
        raw_door_codes = non_schedule

    if not raw_door_codes:
        # Fallback: try to expand comma-separated sheet name (e.g., "D1,2,5,3" -> D1, D2, D5, D3)
        expanded = _expand_comma_sheet_name(sheet_name)
        if expanded:
            raw_door_codes = [{"code": c, "room": "", "dimensions": "", "group": ""} for c in expanded]
        else:
            raw_door_codes = [{"code": sheet_name, "room": "", "dimensions": "", "group": ""}]

    # Consolidate: unique codes only
    unique_codes = {}
    for dc in raw_door_codes:
        if dc["code"] not in unique_codes:
            unique_codes[dc["code"]] = dc
    door_codes = list(unique_codes.values())

    # Find data range
    # Use a generous limit so multi-section sheets (e.g. main + OPTION block) are fully captured.
    # Repeated header rows within the range are skipped inside the loop below.
    data_start = header_row + 2
    data_end = min(ws.max_row, header_row + 100)

    # Detect merged product sets
    merged_sets = _get_merged_row_sets(ws, data_start, data_end, cfg)
    skip_rows = set(merged_sets.values())

    # Build merged cell value lookup so that price cells merged across two product rows
    # (e.g. I17:I18, J17:J18 for a handle+lock pair) return the correct value even on
    # the second row, which openpyxl would otherwise report as None.
    merged_value_lookup = _build_merged_value_lookup(ws)

    # Parse products
    in_option_section = False  # flips to True once a repeated header row is detected
    products = []
    for row_idx in range(data_start, data_end + 1):
        if row_idx in skip_rows:
            continue

        brand = normalize_brand(ws.cell(row=row_idx, column=brand_col).value)
        model = _clean_str(ws.cell(row=row_idx, column=model_col).value)
        desc = _clean_str(ws.cell(row=row_idx, column=desc_col).value)

        # Skip repeated header rows (some BOQ sheets copy the column-header row before
        # each new section, e.g. an OPTION block). Detect by checking whether the brand
        # or model cell contains a known header keyword.
        # When we skip such a row, everything that follows is treated as OPTION.
        _HEADER_WORDS = {"brand", "model", "no.", "no", "picture", "description",
                         "unit", "amount", "q.ty", "qty"}
        if brand.lower().strip() in _HEADER_WORDS or model.lower().strip() in _HEADER_WORDS:
            in_option_section = True
            continue

        qty = _to_float(ws.cell(row=row_idx, column=qty_col).value)

        # Read price and net columns, falling back to merged cell value if the cell
        # is part of a merged range (e.g. a lock body row sharing the handle row's price)
        raw_price = ws.cell(row=row_idx, column=price_col).value
        if raw_price is None:
            raw_price = merged_value_lookup.get((row_idx, price_col))
        unit_price = _to_float(raw_price)

        # raw_list_price always holds the col-I value before any J override
        raw_list_price = unit_price

        net_val = ws.cell(row=row_idx, column=net_col).value
        if net_val is None:
            net_val = merged_value_lookup.get((row_idx, net_col))
        is_net = False
        if isinstance(net_val, str) and "NET" in net_val.upper():
            # Column J says "NET" -> net price, use column I value
            is_net = True
        elif isinstance(net_val, (int, float)) and net_val > 0:
            # Column J is NET AFTER DISCOUNT — keep col I as the list price (unit_price).
            # The output's DISCOUNT row handles the per-door discount; col D should show
            # the original UNIT (col I) price, not the already-discounted J value.
            is_net = False

        # Merged companion row
        if row_idx in merged_sets:
            companion_row = merged_sets[row_idx]
            companion_model = _clean_str(ws.cell(row=companion_row, column=model_col).value)
            if companion_model:
                model = f"{model}, {companion_model}"

        if not model and not brand and qty == 0:
            if desc and products and not desc.startswith("-") and "หมายเหตุ" not in desc:
                products[-1].product.description += " " + desc
            continue

        if not model and not brand:
            continue
        if any(kw in str(brand).lower() + str(model).lower() for kw in ["หมายเหตุ", "-ยืนยัน"]):
            continue
        if brand.startswith("-") or model.startswith("-"):
            continue
        if qty == 0 and unit_price == 0 and not is_net:
            continue

        product = Product(
            model=model, brand=brand, description=desc,
            unit_price=unit_price, is_net_price=is_net,
            raw_list_price=raw_list_price,
            is_option=in_option_section,
        )
        products.append(DoorProduct(product=product, quantity=qty))

    # Create DoorType objects
    door_types = []
    for dc in door_codes:
        dt = DoorType(
            code=dc["code"],
            room_name=dc["room"],
            dimensions=dc["dimensions"],
            products=[DoorProduct(
                product=Product(
                    model=p.product.model, brand=p.product.brand,
                    description=p.product.description,
                    unit_price=p.product.unit_price,
                    is_net_price=p.product.is_net_price,
                    raw_list_price=p.product.raw_list_price,
                    is_option=p.product.is_option,
                ),
                quantity=p.quantity,
            ) for p in products],
            discount_rate=discount_rate,
            source_sheet=sheet_name,
            source_group=dc.get("group", ""),
        )
        door_types.append(dt)

    return door_types


def categorize_sheets(sheet_names):
    categories = {}
    for name in sheet_names:
        if name in SKIP_SHEETS:
            continue
        if name.startswith("FM-"):
            continue

        name_upper = name.upper()
        if name_upper.startswith("AD") or "ALU" in name_upper:
            cat = "Aluminium Door"
        elif name_upper.startswith("WD") or "WOOD" in name_upper:
            cat = "Wood Door"
        elif name_upper.startswith("GD") or "GLASS" in name_upper:
            cat = "Glass Door"
        elif name_upper.startswith("BLT"):
            cat = "Built-in"
        elif name_upper.startswith("D") and len(name) <= 5:
            cat = "Door"
        elif "ACCESS" in name_upper or "CCTV" in name_upper:
            cat = "Access & CCTV"
        else:
            cat = "Door"

        if cat not in categories:
            categories[cat] = []
        categories[cat].append(name)

    return categories


def _differentiate_door_codes(door_types):
    """When multiple door types share the same code but come from different sheets,
    differentiate them using the sheet name."""
    code_groups = {}
    for dt in door_types:
        if dt.code not in code_groups:
            code_groups[dt.code] = []
        code_groups[dt.code].append(dt)

    for code, dts in code_groups.items():
        if len(dts) <= 1:
            continue

        for dt in dts:
            new_label = _derive_door_label(dt.source_sheet, code)
            if new_label != code:
                dt.code = new_label

        seen = {}
        for dt in dts:
            if dt.code in seen:
                if dt.source_sheet != dt.code:
                    dt.code = f"{code} {dt.source_sheet}"
            seen[dt.code] = dt


def parse_cover_sheet(filepath, cfg=None):
    """Parse ใบปะหน้า to extract door quantities.

    Returns two dicts:
    - qty_by_code: {door_code: total_qty} - aggregated by resolved door code
    - qty_by_sheet: {sheet_name: {door_code: qty}} - per source sheet
    """
    if cfg is None:
        cfg = CoverSheetConfig()

    qty_by_code = {}
    qty_by_sheet = {}

    code_col_idx = _col_to_idx(cfg.door_code_col)
    room_col_idx = _col_to_idx(cfg.room_name_col)
    qty_col_idx = _col_to_idx(cfg.quantity_col)

    try:
        wb_data = openpyxl.load_workbook(filepath, data_only=True)
        if "ใบปะหน้า" not in wb_data.sheetnames:
            wb_data.close()
            return qty_by_code, qty_by_sheet

        ws_data = wb_data["ใบปะหน้า"]

        # Also load formulas to get sheet references
        wb_formula = openpyxl.load_workbook(filepath, data_only=False)
        ws_formula = wb_formula["ใบปะหน้า"]

        for row_idx in range(cfg.data_start_row, ws_data.max_row + 1):
            qty = ws_data.cell(row=row_idx, column=qty_col_idx).value
            if not isinstance(qty, (int, float)) or qty <= 0:
                continue

            # Get door code from configured code column (resolved value)
            door_code = _clean_str(ws_data.cell(row=row_idx, column=code_col_idx).value)

            # Extract source sheet from formula
            source_sheet = None
            for col in [code_col_idx, room_col_idx]:  # Try code col first, then room col
                formula = ws_formula.cell(row=row_idx, column=col).value
                if formula and isinstance(formula, str) and "!" in formula:
                    match = re.match(r"^=?'?([^'!]+)'?!([A-Z]+)(\d+)$", formula.strip("="))
                    if match:
                        source_sheet = match.group(1)
                        if not door_code:
                            ref_col = openpyxl.utils.column_index_from_string(match.group(2))
                            ref_row = int(match.group(3))
                            if source_sheet in wb_data.sheetnames:
                                resolved = _clean_str(wb_data[source_sheet].cell(row=ref_row, column=ref_col).value)
                                if resolved and len(resolved) < 20 and " " not in resolved.strip():
                                    door_code = resolved
                                else:
                                    # F column pointed to room name; try B column for door code
                                    for try_row in range(ref_row, ref_row - 3, -1):
                                        candidate = _clean_str(wb_data[source_sheet].cell(row=try_row, column=2).value)
                                        if candidate and len(candidate) < 20 and not any(
                                            kw in candidate.lower() for kw in ["project", "zone", "design", "date", "เลขบาน", "ชื่อห้อง"]
                                        ):
                                            door_code = candidate
                                            break
                        break

            if not door_code:
                continue
            if door_code.startswith("=") or "SUM" in door_code.upper():
                continue

            qty_int = int(qty)
            qty_by_code[door_code] = qty_by_code.get(door_code, 0) + qty_int

            if source_sheet:
                if source_sheet not in qty_by_sheet:
                    qty_by_sheet[source_sheet] = {}
                qty_by_sheet[source_sheet][door_code] = qty_by_sheet[source_sheet].get(door_code, 0) + qty_int

        wb_data.close()
        wb_formula.close()

    except Exception as e:
        print(f"Warning: Could not parse cover sheet from {filepath}: {e}")

    return qty_by_code, qty_by_sheet


def _build_qty_map_for_warehouse(door_types, qty_by_code, qty_by_sheet):
    qty_map = {}
    for dt in door_types:
        # 1 & 2: Sheet-level lookup (most specific)
        if dt.source_sheet in qty_by_sheet:
            sheet_qtys = qty_by_sheet[dt.source_sheet]
            if dt.code in sheet_qtys:
                qty_map[dt.code] = sheet_qtys[dt.code]
            else:
                for base_code, qty in sheet_qtys.items():
                    if dt.code.startswith(base_code + " "):
                        qty_map[dt.code] = qty
                        break

        # 3 & 4: Aggregated qty_by_code fallback
        if dt.code not in qty_map:
            if dt.code in qty_by_code:
                qty_map[dt.code] = qty_by_code[dt.code]
            else:
                for base_code, qty in qty_by_code.items():
                    if dt.code.startswith(base_code + " "):
                        qty_map[dt.code] = qty
                        break

        # 5: Normalized match (strips hyphens and spaces)
        if dt.code not in qty_map:
            dt_normalized = dt.code.replace("-", "").replace(" ", "").upper()
            for base_code, qty in qty_by_code.items():
                bc_normalized = base_code.replace("-", "").replace(" ", "").upper()
                if dt_normalized == bc_normalized:
                    qty_map[dt.code] = qty
                    break

        # 6: Group-based fallback for Group-named BOQ sheets.
        # When the cover sheet lists quantities by group name (e.g. "Group 1": 1)
        # rather than by door code, match via the door type's source_group.
        if dt.code not in qty_map and dt.source_group:
            # Try exact match on source_group (e.g. "Group 1")
            if dt.source_group in qty_by_code:
                qty_map[dt.code] = qty_by_code[dt.source_group]
            else:
                # Try sheet-level: source_group may appear in qty_by_sheet
                if dt.source_sheet in qty_by_sheet:
                    sheet_qtys = qty_by_sheet[dt.source_sheet]
                    if dt.source_group in sheet_qtys:
                        qty_map[dt.code] = sheet_qtys[dt.source_group]

    return qty_map


def parse_boq_file(filepath, config=None):
    """Parse an entire BOQ file and return categories + quantity info."""
    if config is None:
        config = BOQConfig()

    sheet_cfg = config.sheet_config
    cover_cfg = config.cover_config

    # Use data_only=True so formulas in the NET column resolve to their computed values
    wb = openpyxl.load_workbook(filepath, data_only=True)
    sheet_names = [
        n for n in wb.sheetnames
        if n not in SKIP_SHEETS and wb[n].sheet_state == "visible"
    ]

    categories_map = categorize_sheets(sheet_names)
    results = []

    for cat_name, sheets in categories_map.items():
        cat = BOQCategory(name=cat_name, source_file=str(filepath))
        for sheet_name in sheets:
            ws = wb[sheet_name]
            door_types = parse_boq_sheet(ws, sheet_name, sheet_cfg)
            cat.door_types.extend(door_types)

        if cat.door_types:
            _differentiate_door_codes(cat.door_types)
            results.append(cat)

    wb.close()

    qty_by_code, qty_by_sheet = parse_cover_sheet(filepath, cover_cfg)

    return results, qty_by_code, qty_by_sheet


def parse_multiple_boq_files(filepaths, config=None):
    """Parse multiple BOQ files and merge categories.

    Returns (categories_list, merged_qty_map).
    """
    if config is None:
        config = BOQConfig()

    all_categories = {}
    all_qty_by_code = {}
    all_qty_by_sheet = {}

    for fp in filepaths:
        try:
            cats, qty_by_code, qty_by_sheet = parse_boq_file(fp, config)
            for cat in cats:
                if cat.name not in all_categories:
                    all_categories[cat.name] = BOQCategory(
                        name=cat.name,
                        source_file=cat.source_file,
                    )
                existing_keys = {
                    (dt.code, dt.source_sheet) for dt in all_categories[cat.name].door_types
                }
                for dt in cat.door_types:
                    key = (dt.code, dt.source_sheet)
                    if key not in existing_keys:
                        all_categories[cat.name].door_types.append(dt)
                        existing_keys.add(key)

            for code, qty in qty_by_code.items():
                all_qty_by_code[code] = all_qty_by_code.get(code, 0) + qty
            for sheet, codes in qty_by_sheet.items():
                if sheet not in all_qty_by_sheet:
                    all_qty_by_sheet[sheet] = {}
                for code, qty in codes.items():
                    all_qty_by_sheet[sheet][code] = all_qty_by_sheet[sheet].get(code, 0) + qty

        except Exception as e:
            print(f"Error parsing {fp}: {e}")
            raise

    categories = list(all_categories.values())

    all_door_types = []
    for cat in categories:
        all_door_types.extend(cat.door_types)

    qty_map = _build_qty_map_for_warehouse(all_door_types, all_qty_by_code, all_qty_by_sheet)

    return categories, qty_map
