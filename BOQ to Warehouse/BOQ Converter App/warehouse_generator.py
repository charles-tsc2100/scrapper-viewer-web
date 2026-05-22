"""
Warehouse Form Generator - Creates Excel warehouse forms from parsed BOQ data.
"""
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from boq_parser import BOQCategory, DoorType, Product
from datetime import datetime


HEADER_FILL = PatternFill("solid", fgColor="4472C4")
HEADER_FONT = Font(name="Arial", size=10, bold=True, color="FFFFFF")
SUBHEADER_FILL = PatternFill("solid", fgColor="D6E4F0")
SUBHEADER_FONT = Font(name="Arial", size=10, bold=True)
DATA_FONT = Font(name="Arial", size=10)
PRICE_FONT = Font(name="Arial", size=10, color="0000FF")
TOTAL_FILL = PatternFill("solid", fgColor="E2EFDA")
TOTAL_FONT = Font(name="Arial", size=10, bold=True)
THIN_BORDER = Border(
    left=Side(style="thin"),
    right=Side(style="thin"),
    top=Side(style="thin"),
    bottom=Side(style="thin"),
)
CENTER = Alignment(horizontal="center", vertical="center", wrap_text=True)
LEFT = Alignment(horizontal="left", vertical="center", wrap_text=True)
NUM_FMT = '#,##0'


MAJOR_BRANDS = {"TECTUS", "MIWA", "CCE", "H-ONE", "INDOOR", "RYOBI", "ELMES"}


def _product_display_name(product):
    """Generate display name for a product, always prefixing brand name."""
    brand = product.brand if product.brand else ""
    model = product.model

    parts = []
    if brand:
        # Always prefix brand, but avoid duplicating if model already starts with brand
        if not model.upper().startswith(brand.upper()):
            parts.append(brand.upper())
    parts.append(model)
    # Add Thai description for non-major brands (LOCAL, GCC, etc.)
    if product.is_net_price and product.description:
        brand_upper = brand.upper() if brand else ""
        if brand_upper not in {b.upper() for b in MAJOR_BRANDS}:
            parts.append(product.description)
    return " ".join(p for p in parts if p)


def _build_product_matrix(category):
    """Build a unified product list and quantity matrix from a category."""
    door_codes = list(category.door_types)

    # Collect unique products by display name
    product_map = {}  # display_name -> Product
    display_names = {}  # model -> display_name
    for dt in door_codes:
        for dp in dt.products:
            dname = _product_display_name(dp.product)
            if dname not in product_map:
                product_map[dname] = dp.product
                display_names[dp.product.model] = dname
            else:
                existing = product_map[dname]
                if dp.product.unit_price > 0 and existing.unit_price == 0:
                    product_map[dname] = dp.product
                if dp.product.brand and not existing.brand:
                    existing.brand = dp.product.brand
                # A product is only truly OPTION if ALL occurrences are from option sections
                if not dp.product.is_option:
                    existing.is_option = False
                display_names[dp.product.model] = dname

    product_list = list(product_map.values())
    display_name_list = list(product_map.keys())

    # Build quantity matrix: display_name -> door_code -> qty
    qty_matrix = {}
    for dt in door_codes:
        for dp in dt.products:
            dname = display_names.get(dp.product.model, dp.product.model)
            if dname not in qty_matrix:
                qty_matrix[dname] = {}
            if dp.quantity > 0:
                qty_matrix[dname][dt.code] = dp.quantity

    return product_list, display_name_list, door_codes, qty_matrix


def generate_warehouse_form(categories, project_name="", output_path="warehouse_form.xlsx", include_pricing=True, qty_map=None, use_unit_price=False):
    """Generate a warehouse form Excel file from parsed BOQ categories."""
    wb = openpyxl.Workbook()
    wb.remove(wb.active)

    for cat in categories:
        product_list, display_names, door_types, qty_matrix = _build_product_matrix(cat)
        if not product_list or not door_types:
            continue

        # Create sheet
        sheet_name = cat.name[:31]  # Excel sheet name limit
        ws = wb.create_sheet(title=sheet_name)

        # Determine column layout
        # With pricing: B=Product, C=net, D=ราคา, E+=doors, last=total qty
        # Without pricing: B=Product, C+=doors, last=total qty (no price columns)
        if include_pricing:
            door_start_col = 5  # Column E
        else:
            door_start_col = 3  # Column C (skip net/ราคา columns)
        door_end_col = door_start_col + len(door_types) - 1
        # Leave a gap column, then total
        total_col = door_end_col + 2

        # Row 1: Project name and date
        ws.cell(row=1, column=2, value=f"PROJECT : {project_name}")
        ws.cell(row=1, column=2).font = Font(name="Arial", size=12, bold=True)
        ws.cell(row=1, column=total_col, value="Date")
        ws.cell(row=1, column=total_col).font = DATA_FONT

        # Row 3: Headers
        # Product name header always present
        cell = ws.cell(row=3, column=2, value="รายการอุปกรณ์")
        cell.font = HEADER_FONT
        cell.fill = HEADER_FILL
        cell.alignment = CENTER
        cell.border = THIN_BORDER

        # Price columns only when pricing is on
        if include_pricing:
            for col, label in [(3, "net"), (4, "ราคา")]:
                cell = ws.cell(row=3, column=col, value=label)
                cell.font = HEADER_FONT
                cell.fill = HEADER_FILL
                cell.alignment = CENTER
                cell.border = THIN_BORDER

        # Door type headers
        for i, dt in enumerate(door_types):
            col = door_start_col + i
            cell = ws.cell(row=3, column=col, value=dt.code)
            cell.font = HEADER_FONT
            cell.fill = HEADER_FILL
            cell.alignment = CENTER
            cell.border = THIN_BORDER

        # Total column header
        total_header = ws.cell(row=3, column=total_col, value="จำนวน")
        total_header.font = HEADER_FONT
        total_header.fill = HEADER_FILL
        total_header.alignment = CENTER
        total_header.border = THIN_BORDER

        # Row 4: Category label
        ws.cell(row=4, column=2, value=cat.name)
        ws.cell(row=4, column=2).font = Font(name="Arial", size=10, bold=True, italic=True)

        # Data rows (products) - start from row 5, use every other row for spacing
        data_start_row = 5
        current_row = data_start_row

        for idx, product in enumerate(product_list):
            dname = display_names[idx]

            # Column A: "Option" label for products from BOQ OPTION sections
            if product.is_option:
                cell_a = ws.cell(row=current_row, column=1, value="Option")
                cell_a.font = Font(name="Arial", size=8, italic=True, color="888888")
                cell_a.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

            # Product name (display name)
            cell = ws.cell(row=current_row, column=2, value=dname)
            cell.font = DATA_FONT
            cell.border = THIN_BORDER

            # Price columns only when pricing is on
            if include_pricing:
                if use_unit_price:
                    # Unit price mode: always output raw col-I value in ราคา (col D),
                    # ignore NET / discount logic entirely
                    price_val = product.raw_list_price if product.raw_list_price > 0 else product.unit_price
                    if price_val > 0:
                        cell = ws.cell(row=current_row, column=4, value=price_val)
                        cell.font = PRICE_FONT
                        cell.number_format = NUM_FMT
                        cell.border = THIN_BORDER
                else:
                    # Net price (col C) - for items with NET pricing
                    if product.is_net_price and product.unit_price > 0:
                        cell = ws.cell(row=current_row, column=3, value=product.unit_price)
                        cell.font = PRICE_FONT
                        cell.number_format = NUM_FMT
                        cell.border = THIN_BORDER

                    # List price (col D) - for items with discount pricing
                    if not product.is_net_price and product.unit_price > 0:
                        cell = ws.cell(row=current_row, column=4, value=product.unit_price)
                        cell.font = PRICE_FONT
                        cell.number_format = NUM_FMT
                        cell.border = THIN_BORDER

            # Door quantities
            model_qtys = qty_matrix.get(dname, {})
            for i, dt in enumerate(door_types):
                col = door_start_col + i
                qty = model_qtys.get(dt.code, 0)
                if qty > 0:
                    cell = ws.cell(row=current_row, column=col, value=qty)
                    cell.font = DATA_FONT
                    cell.alignment = CENTER
                    cell.number_format = NUM_FMT
                cell_ref = ws.cell(row=current_row, column=col)
                cell_ref.border = THIN_BORDER

            # Total quantity formula (SUMPRODUCT with QUANTITY row - will be set later)
            # For now, simple SUM across door columns
            first_door_letter = get_column_letter(door_start_col)
            last_door_letter = get_column_letter(door_end_col)
            # We'll use SUMPRODUCT with the QUANTITY row later
            cell = ws.cell(row=current_row, column=total_col)
            cell.border = THIN_BORDER
            cell.font = TOTAL_FONT
            cell.number_format = NUM_FMT

            current_row += 1

        data_end_row = current_row - 1

        first_dl = get_column_letter(door_start_col)
        last_dl = get_column_letter(door_end_col)

        if include_pricing:
            # ── PER DOOR row (pricing mode only) ──
            # Only ราคา (col D) prices - net prices are shown separately below
            current_row += 1
            per_door_row = current_row
            ws.cell(row=per_door_row, column=2, value="PER DOOR")
            ws.cell(row=per_door_row, column=2).font = TOTAL_FONT
            ws.cell(row=per_door_row, column=2).fill = SUBHEADER_FILL
            ws.cell(row=per_door_row, column=2).border = THIN_BORDER

            for i in range(len(door_types)):
                col = door_start_col + i
                col_letter = get_column_letter(col)
                formula = f"=SUMPRODUCT($D${data_start_row}:$D${data_end_row},{col_letter}{data_start_row}:{col_letter}{data_end_row})"
                cell = ws.cell(row=per_door_row, column=col, value=formula)
                cell.font = TOTAL_FONT
                cell.fill = SUBHEADER_FILL
                cell.number_format = NUM_FMT
                cell.border = THIN_BORDER

        # ── QUANTITY row (always present) ──
        current_row += 1
        qty_row = current_row
        ws.cell(row=qty_row, column=2, value="QUANTITY")
        ws.cell(row=qty_row, column=2).font = TOTAL_FONT
        ws.cell(row=qty_row, column=2).fill = TOTAL_FILL
        ws.cell(row=qty_row, column=2).border = THIN_BORDER

        for i, dt in enumerate(door_types):
            col = door_start_col + i
            cell = ws.cell(row=qty_row, column=col)
            cell.font = TOTAL_FONT
            cell.fill = TOTAL_FILL
            cell.number_format = NUM_FMT
            cell.border = THIN_BORDER
            if qty_map and dt.code in qty_map:
                cell.value = qty_map[dt.code]

        cell = ws.cell(row=qty_row, column=total_col,
                       value=f"=SUM({first_dl}{qty_row}:{last_dl}{qty_row})")
        cell.font = TOTAL_FONT
        cell.fill = TOTAL_FILL
        cell.number_format = NUM_FMT
        cell.border = THIN_BORDER

        # ── Set SUMPRODUCT formulas for product จำนวน column ──
        for row_idx in range(data_start_row, data_end_row + 1):
            formula = f"=SUMPRODUCT({first_dl}{row_idx}:{last_dl}{row_idx},${first_dl}${qty_row}:${last_dl}${qty_row})"
            ws.cell(row=row_idx, column=total_col, value=formula)
            ws.cell(row=row_idx, column=total_col).font = TOTAL_FONT
            ws.cell(row=row_idx, column=total_col).number_format = NUM_FMT
            ws.cell(row=row_idx, column=total_col).border = THIN_BORDER

        if include_pricing:
            # ── TOTAL row = QUANTITY x PER DOOR (pricing mode only) ──
            current_row += 1
            total_row = current_row
            ws.cell(row=total_row, column=2, value="TOTAL")
            ws.cell(row=total_row, column=2).font = TOTAL_FONT
            ws.cell(row=total_row, column=2).fill = TOTAL_FILL
            ws.cell(row=total_row, column=2).border = THIN_BORDER

            for i in range(len(door_types)):
                col = door_start_col + i
                col_letter = get_column_letter(col)
                formula = f"={col_letter}{qty_row}*{col_letter}{per_door_row}"
                cell = ws.cell(row=total_row, column=col, value=formula)
                cell.font = TOTAL_FONT
                cell.fill = TOTAL_FILL
                cell.number_format = NUM_FMT
                cell.border = THIN_BORDER

            total_total = ws.cell(row=total_row, column=total_col,
                                  value=f"=SUM({first_dl}{total_row}:{last_dl}{total_row})")
            total_total.font = TOTAL_FONT
            total_total.fill = TOTAL_FILL
            total_total.number_format = NUM_FMT
            total_total.border = THIN_BORDER

        if include_pricing:
            # ── ราคา net row - sum of net prices (col C) per door ──
            current_row += 1
            net_price_row = current_row
            ws.cell(row=net_price_row, column=4, value="ราคา net")
            ws.cell(row=net_price_row, column=4).font = Font(name="Arial", size=10, bold=True, color="0000FF")
            ws.cell(row=net_price_row, column=4).border = THIN_BORDER

            for i in range(len(door_types)):
                col = door_start_col + i
                col_letter = get_column_letter(col)
                formula = f"=SUMPRODUCT($C${data_start_row}:$C${data_end_row},{col_letter}{data_start_row}:{col_letter}{data_end_row})"
                cell = ws.cell(row=net_price_row, column=col, value=formula)
                cell.font = PRICE_FONT
                cell.number_format = NUM_FMT
                cell.border = THIN_BORDER

            # ── Net total row = ราคา net * QUANTITY ──
            current_row += 1
            net_total_row = current_row

            for i in range(len(door_types)):
                col = door_start_col + i
                col_letter = get_column_letter(col)
                formula = f"={col_letter}{net_price_row}*{col_letter}{qty_row}"
                cell = ws.cell(row=net_total_row, column=col, value=formula)
                cell.font = DATA_FONT
                cell.number_format = NUM_FMT
                cell.border = THIN_BORDER

            # ── Gap row ──
            current_row += 1

            # ── DISCOUNT row = PER DOOR * discount % (only on ราคา items) ──
            current_row += 1
            discount_row = current_row
            discount_rate = 0.0
            for dt in door_types:
                if dt.discount_rate > 0:
                    discount_rate = dt.discount_rate
                    break

            ws.cell(row=discount_row, column=2, value="DISCOUNT")
            ws.cell(row=discount_row, column=2).font = TOTAL_FONT
            ws.cell(row=discount_row, column=2).border = THIN_BORDER
            ws.cell(row=discount_row, column=4, value=discount_rate)
            ws.cell(row=discount_row, column=4).font = PRICE_FONT
            ws.cell(row=discount_row, column=4).number_format = '0%'
            ws.cell(row=discount_row, column=4).border = THIN_BORDER

            for i in range(len(door_types)):
                col = door_start_col + i
                col_letter = get_column_letter(col)
                formula = f"={col_letter}{per_door_row}*$D${discount_row}"
                cell = ws.cell(row=discount_row, column=col, value=formula)
                cell.font = DATA_FONT
                cell.number_format = NUM_FMT
                cell.border = THIN_BORDER

            # ── After discount row = PER DOOR - DISCOUNT ──
            current_row += 1
            after_disc_row = current_row

            for i in range(len(door_types)):
                col = door_start_col + i
                col_letter = get_column_letter(col)
                formula = f"={col_letter}{per_door_row}-{col_letter}{discount_row}"
                cell = ws.cell(row=after_disc_row, column=col, value=formula)
                cell.font = TOTAL_FONT
                cell.number_format = NUM_FMT
                cell.border = THIN_BORDER

            # ── Final total row = (after discount * QTY) + net total ──
            current_row += 1
            final_total_row = current_row

            for i in range(len(door_types)):
                col = door_start_col + i
                col_letter = get_column_letter(col)
                # = (after_disc * qty) + (net_price * qty)
                formula = f"={col_letter}{after_disc_row}*{col_letter}{qty_row}+{col_letter}{net_total_row}"
                cell = ws.cell(row=final_total_row, column=col, value=formula)
                cell.font = TOTAL_FONT
                cell.fill = TOTAL_FILL
                cell.number_format = NUM_FMT
                cell.border = THIN_BORDER

            grand_total = ws.cell(row=final_total_row, column=total_col,
                                  value=f"=SUM({first_dl}{final_total_row}:{last_dl}{final_total_row})")
            grand_total.font = TOTAL_FONT
            grand_total.fill = TOTAL_FILL
            grand_total.number_format = NUM_FMT
            grand_total.border = THIN_BORDER

        # Column widths
        ws.column_dimensions["A"].width = 7
        ws.column_dimensions["B"].width = 35
        if include_pricing:
            ws.column_dimensions["C"].width = 10
            ws.column_dimensions["D"].width = 10
        for i in range(len(door_types)):
            col_letter = get_column_letter(door_start_col + i)
            ws.column_dimensions[col_letter].width = 12
        ws.column_dimensions[get_column_letter(total_col)].width = 12

        # Freeze panes
        ws.freeze_panes = f"{get_column_letter(door_start_col)}4"

        # Add "Stock" column header after total
        stock_col = total_col + 1
        cell = ws.cell(row=3, column=stock_col, value="Stock")
        cell.font = HEADER_FONT
        cell.fill = HEADER_FILL
        cell.alignment = CENTER
        cell.border = THIN_BORDER
        ws.column_dimensions[get_column_letter(stock_col)].width = 10

    if not wb.sheetnames:
        ws = wb.create_sheet("Empty")
        ws.cell(row=1, column=1, value="No data found in BOQ files")

    wb.save(output_path)
    return output_path
