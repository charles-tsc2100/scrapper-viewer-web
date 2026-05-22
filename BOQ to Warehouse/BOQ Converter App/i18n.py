"""
Internationalization (i18n) module - English / Thai language support.
"""

_current_lang = "th" # default language
_observers = []  # callbacks to notify on language change

TRANSLATIONS = {
    # ── App Window ──
    "app_title": {
        "en": "BOQ to Warehouse Form Converter - TodayStyle 2100",
        "th": "ตัวแปลง BOQ เป็นฟอร์มคลังสินค้า - TodayStyle 2100",
    },
    "header_title": {
        "en": "BOQ to Warehouse Form",
        "th": "BOQ เป็นฟอร์มคลังสินค้า",
    },
    "header_subtitle": {
        "en": "Convert BOQ files to warehouse picking forms",
        "th": "แปลงไฟล์ BOQ เป็นฟอร์มหยิบสินค้าคลัง",
    },

    # ── Stepper ──
    "step1_label": {
        "en": "Select BOQ Files",
        "th": "เลือกไฟล์ BOQ",
    },
    "step2_label": {
        "en": "Configure & Review",
        "th": "ตั้งค่า & ตรวจสอบ",
    },
    "step3_label": {
        "en": "Convert to Form",
        "th": "แปลงเป็นฟอร์ม",
    },

    # ── File Section ──
    "boq_files_label": {
        "en": "  BOQ Files  ",
        "th": "  ไฟล์ BOQ  ",
    },
    "add_files_btn": {
        "en": "+ Add BOQ Files",
        "th": "+ เพิ่มไฟล์ BOQ",
    },
    "clear_all_btn": {
        "en": "Clear All",
        "th": "ล้างทั้งหมด",
    },
    "no_files_selected": {
        "en": "No files selected",
        "th": "ยังไม่ได้เลือกไฟล์",
    },
    "files_selected": {
        "en": "{count} file{s} selected",
        "th": "เลือกแล้ว {count} ไฟล์",
    },
    "cover_sheet_note": {
        "en": 'Note: Each BOQ file must contain a "\u0e43\u0e1a\u0e1b\u0e30\u0e2b\u0e19\u0e49\u0e32" (cover sheet) for quantity mapping to work.',
        "th": 'หมายเหตุ: ไฟล์ BOQ แต่ละไฟล์ต้องมีชีท "ใบปะหน้า" เพื่อให้การดึงจำนวนทำงานได้',
    },
    "door_schedule_note": {
        "en": 'Door schedule codes are read from the cover sheet (col D or E) and each BOQ sheet. Only codes like D101, WD1, AD1, etc. are used.',
        "th": 'รหัส Door Schedule อ่านจากใบปะหน้า (คอลัมน์ D หรือ E) และแต่ละชีท BOQ ใช้เฉพาะรหัสเช่น D101, WD1, AD1 เป็นต้น',
    },
    "select_boq_files_title": {
        "en": "Select BOQ Files",
        "th": "เลือกไฟล์ BOQ",
    },

    # ── Settings Section ──
    "settings_label": {
        "en": "  Settings  ",
        "th": "  ตั้งค่า  ",
    },
    "project_name_label": {
        "en": "Project Name:",
        "th": "ชื่อโปรเจกต์:",
    },
    "project_picker_label": {
        "en": "Project (from Lark):",
        "th": "โปรเจกต์ (จาก Lark):",
    },
    "project_picker_placeholder": {
        "en": "— Select a project —",
        "th": "— เลือกโปรเจกต์ —",
    },
    "project_picker_custom": {
        "en": "+ Custom (not in Lark)",
        "th": "+ กำหนดเอง (ไม่อยู่ใน Lark)",
    },
    "project_picker_loading": {
        "en": "Loading projects…",
        "th": "กำลังโหลดโปรเจกต์…",
    },
    "project_picker_unavailable": {
        "en": "Project list unavailable — using custom entry",
        "th": "ไม่สามารถโหลดรายการโปรเจกต์ — ใช้การกรอกเอง",
    },
    "project_category_label": {
        "en": "Project Category:",
        "th": "ประเภทโปรเจกต์:",
    },
    "project_category_required_title": {
        "en": "Category required",
        "th": "ต้องระบุประเภท",
    },
    "project_category_required_msg": {
        "en": "Please select or enter a project category before converting.",
        "th": "กรุณาเลือกหรือกรอกประเภทโปรเจกต์ก่อนแปลงไฟล์",
    },
    "include_pricing_check": {
        "en": "Include pricing section (DISCOUNT, NET per door, TOTAL)",
        "th": "รวมส่วนราคา (ส่วนลด, ราคา NET ต่อบาน, รวม)",
    },
    "use_unit_price_check": {
        "en": "Use UNIT price (col I) — ignore Net After Discount column",
        "th": "ใช้ราคา UNIT (คอลัมน์ I) — ไม่สนใจคอลัมน์ Net After Discount",
    },
    "combine_door_types_check": {
        "en": "Combine door types into one sheet",
        "th": "รวมประเภทประตูเป็นชีตเดียว",
    },
    "cell_references_btn": {
        "en": "Cell References...",
        "th": "อ้างอิงเซลล์...",
    },
    "auto_detected": {
        "en": "Auto-detected",
        "th": "ตรวจจับอัตโนมัติ",
    },
    "using_defaults": {
        "en": "Using defaults",
        "th": "ใช้ค่าเริ่มต้น",
    },
    "custom_config": {
        "en": "Custom config",
        "th": "ตั้งค่าเอง",
    },

    # ── Preview Section ──
    "preview_label": {
        "en": "  Preview  ",
        "th": "  ตัวอย่าง  ",
    },

    # ── Action Buttons ──
    "convert_btn": {
        "en": "Convert to Warehouse Form",
        "th": "แปลงเป็นฟอร์มคลังสินค้า",
    },
    "ready_status": {
        "en": "Ready",
        "th": "พร้อม",
    },
    "parsing_status": {
        "en": "Parsing BOQ files...",
        "th": "กำลังอ่านไฟล์ BOQ...",
    },
    "ready_to_convert": {
        "en": "Ready to convert",
        "th": "พร้อมแปลง",
    },
    "parse_error": {
        "en": "Parse error",
        "th": "เกิดข้อผิดพลาดในการอ่าน",
    },
    "generating_status": {
        "en": "Generating warehouse form...",
        "th": "กำลังสร้างฟอร์มคลังสินค้า...",
    },
    "conversion_error": {
        "en": "Conversion error",
        "th": "เกิดข้อผิดพลาดในการแปลง",
    },
    "saved_status": {
        "en": "Saved: {filename}",
        "th": "บันทึกแล้ว: {filename}",
    },

    # ── Dialogs ──
    "no_files_title": {
        "en": "No Files",
        "th": "ไม่มีไฟล์",
    },
    "no_files_msg": {
        "en": "Please add BOQ files first.",
        "th": "กรุณาเพิ่มไฟล์ BOQ ก่อน",
    },
    "no_files_config_msg": {
        "en": "Please add BOQ files first so the preview can load.",
        "th": "กรุณาเพิ่มไฟล์ BOQ ก่อนเพื่อโหลดตัวอย่าง",
    },
    "not_parsed_title": {
        "en": "Not Parsed",
        "th": "ยังไม่ได้อ่าน",
    },
    "not_parsed_msg": {
        "en": "Please wait for files to finish parsing.",
        "th": "กรุณารอให้อ่านไฟล์เสร็จก่อน",
    },
    "save_as_title": {
        "en": "Save Warehouse Form As",
        "th": "บันทึกฟอร์มคลังสินค้าเป็น",
    },
    "success_title": {
        "en": "Success",
        "th": "สำเร็จ",
    },
    "success_msg": {
        "en": "Warehouse form saved to:\n{path}\n\nCategories: {count}\nYou can now open and edit it in Excel.",
        "th": "บันทึกฟอร์มคลังสินค้าที่:\n{path}\n\nหมวดหมู่: {count}\nสามารถเปิดและแก้ไขใน Excel ได้",
    },
    "error_title": {
        "en": "Error",
        "th": "ข้อผิดพลาด",
    },
    "error_msg": {
        "en": "Failed to generate:\n{error}",
        "th": "ไม่สามารถสร้างได้:\n{error}",
    },

    # ── Preview Text ──
    "preview_category": {
        "en": "Category: {name}",
        "th": "หมวดหมู่: {name}",
    },
    "preview_doors": {
        "en": "  Doors: {count}",
        "th": "  บาน: {count}",
    },
    "preview_door_types": {
        "en": "  Door types: {types}",
        "th": "  ชนิดประตู: {types}",
    },
    "preview_products": {
        "en": "  Unique products: {count}",
        "th": "  สินค้า (ไม่ซ้ำ): {count}",
    },
    "preview_quantities": {
        "en": "  Quantities: {qtys}",
        "th": "  จำนวน: {qtys}",
    },
    "preview_total": {
        "en": "Total: {doors} door types, {products} unique products",
        "th": "รวม: {doors} ชนิดประตู, {products} สินค้า (ไม่ซ้ำ)",
    },
    "preview_cell_refs": {
        "en": "--- Cell References (click 'Cell References...' to edit) ---",
        "th": "--- อ้างอิงเซลล์ (คลิก 'อ้างอิงเซลล์...' เพื่อแก้ไข) ---",
    },
    "preview_door_codes": {
        "en": "  Door codes: col {col}, starting row {row}",
        "th": "  รหัสประตู: คอลัมน์ {col}, แถวเริ่มต้น {row}",
    },
    "preview_product_cfg": {
        "en": "  Product: brand={brand}, model={model}, desc={desc}, qty={qty}",
        "th": "  สินค้า: แบรนด์={brand}, รุ่น={model}, รายละเอียด={desc}, จำนวน={qty}",
    },
    "preview_pricing_cfg": {
        "en": "  Pricing: unit price={price}, NET indicator={net}",
        "th": "  ราคา: ราคาต่อหน่วย={price}, ตัวบ่งชี้ NET={net}",
    },
    "preview_cover_cfg": {
        "en": "  Cover sheet: code={code}, qty={qty}, from row {row}",
        "th": "  ใบปะหน้า: รหัส={code}, จำนวน={qty}, จากแถว {row}",
    },
    "error_parsing": {
        "en": "Error parsing files:\n{error}",
        "th": "เกิดข้อผิดพลาดในการอ่านไฟล์:\n{error}",
    },

    # ── Error Log ──
    "error_log_btn": {
        "en": "Error Log",
        "th": "บันทึกข้อผิดพลาด",
    },
    "error_log_title": {
        "en": "Error Log",
        "th": "บันทึกข้อผิดพลาด",
    },
    "error_log_empty": {
        "en": "No log entries yet.",
        "th": "ยังไม่มีบันทึก",
    },
    "error_log_clear": {
        "en": "Clear Log",
        "th": "ล้างบันทึก",
    },
    "error_log_export": {
        "en": "Export Log...",
        "th": "ส่งออกบันทึก...",
    },
    "error_log_export_title": {
        "en": "Export Error Log",
        "th": "ส่งออกบันทึกข้อผิดพลาด",
    },
    "error_log_exported": {
        "en": "Log exported to:\n{path}",
        "th": "ส่งออกบันทึกไปที่:\n{path}",
    },

    # ── User Guide ──
    "user_guide_btn": {
        "en": "User Guide",
        "th": "คู่มือการใช้งาน",
    },

    # ── Language Toggle ──
    "lang_btn": {
        "en": "TH ไทย",
        "th": "EN English",
    },

    # ── Cell Selector Dialog ──
    "cell_ref_title": {
        "en": "Cell Reference Settings",
        "th": "ตั้งค่าอ้างอิงเซลล์",
    },
    "boq_sheet_tab": {
        "en": "  BOQ Sheet  ",
        "th": "  ชีท BOQ  ",
    },
    "cover_sheet_tab": {
        "en": "  Cover Sheet (ใบปะหน้า)  ",
        "th": "  ใบปะหน้า  ",
    },
    "save_reparse_btn": {
        "en": "Save & Re-parse",
        "th": "บันทึก & อ่านใหม่",
    },
    "cancel_btn": {
        "en": "Cancel",
        "th": "ยกเลิก",
    },
    "preview_sheet_label": {
        "en": "Preview sheet:",
        "th": "ตัวอย่างชีท:",
    },
    "start_from_row_label": {
        "en": "Start from row:",
        "th": "เริ่มจากแถว:",
    },
    "click_field_instruction": {
        "en": "Click a field,\nthen click a column",
        "th": "คลิกฟิลด์,\nแล้วคลิกคอลัมน์",
    },
    "grid_instruction": {
        "en": "1. Click a field button on the left    2. Click the matching column header or cell in the grid    3. The column highlights with that field's color",
        "th": "1. คลิกปุ่มฟิลด์ทางซ้าย    2. คลิกหัวคอลัมน์หรือเซลล์ในตาราง    3. คอลัมน์จะไฮไลท์ด้วยสีของฟิลด์",
    },
    "preview_cover_label": {
        "en": "Preview cover sheet:",
        "th": "ตัวอย่างใบปะหน้า:",
    },

    # ── Field Labels (Cell Selector) ──
    "field_door_code": {
        "en": "Door Code",
        "th": "รหัสประตู",
    },
    "field_room_name": {
        "en": "Room Name",
        "th": "ชื่อห้อง",
    },
    "field_dimensions": {
        "en": "Dimensions",
        "th": "ขนาด",
    },
    "field_brand": {
        "en": "Brand",
        "th": "แบรนด์",
    },
    "field_model": {
        "en": "Model",
        "th": "รุ่น",
    },
    "field_description": {
        "en": "Description",
        "th": "รายละเอียด",
    },
    "field_qty": {
        "en": "Qty/Set",
        "th": "จำนวน/ชุด",
    },
    "field_unit_price": {
        "en": "Unit Price",
        "th": "ราคาต่อหน่วย",
    },
    "field_net_indicator": {
        "en": "NET Indicator",
        "th": "ตัวบ่งชี้ NET",
    },
    "field_door_code_row": {
        "en": "Door Code Row",
        "th": "แถวรหัสประตู",
    },
    "field_quantity": {
        "en": "Quantity",
        "th": "จำนวน",
    },
    "field_data_start_row": {
        "en": "Data Start Row",
        "th": "แถวเริ่มข้อมูล",
    },

    # ── BOQ Field Button Labels ──
    "door_code_col": {
        "en": "Door Code Col",
        "th": "คอลัมน์รหัสประตู",
    },
    "door_code_row": {
        "en": "Door Code Row",
        "th": "แถวรหัสประตู",
    },
    "room_name_col": {
        "en": "Room Name Col",
        "th": "คอลัมน์ชื่อห้อง",
    },
    "dimensions_col": {
        "en": "Dimensions Col",
        "th": "คอลัมน์ขนาด",
    },
    "brand_col": {
        "en": "Brand Col",
        "th": "คอลัมน์แบรนด์",
    },
    "model_col": {
        "en": "Model Col",
        "th": "คอลัมน์รุ่น",
    },
    "description_col": {
        "en": "Description Col",
        "th": "คอลัมน์รายละเอียด",
    },
    "qty_col": {
        "en": "Qty/Set Col",
        "th": "คอลัมน์จำนวน/ชุด",
    },
    "unit_price_col": {
        "en": "Unit Price Col",
        "th": "คอลัมน์ราคาต่อหน่วย",
    },
    "net_indicator_col": {
        "en": "NET Indicator Col",
        "th": "คอลัมน์ตัวบ่งชี้ NET",
    },
    "cv_door_code_col": {
        "en": "Door Code Col",
        "th": "คอลัมน์รหัสประตู",
    },
    "cv_room_name_col": {
        "en": "Room Name Col",
        "th": "คอลัมน์ชื่อห้อง",
    },
    "cv_quantity_col": {
        "en": "Quantity Col",
        "th": "คอลัมน์จำนวน",
    },
    "cv_data_start_row": {
        "en": "Data Start Row",
        "th": "แถวเริ่มข้อมูล",
    },

    # ── Version / About ──
    "version_label": {
        "en": "v{version}",
        "th": "v{version}",
    },
    "about_btn": {
        "en": "About",
        "th": "เกี่ยวกับ",
    },
    "about_title": {
        "en": "About - BOQ to Warehouse Converter",
        "th": "เกี่ยวกับ - ตัวแปลง BOQ เป็นฟอร์มคลังสินค้า",
    },
    "about_app_name": {
        "en": "BOQ to Warehouse Form Converter",
        "th": "ตัวแปลง BOQ เป็นฟอร์มคลังสินค้า",
    },
    "about_company": {
        "en": "TodayStyle 2100 Co., Ltd.",
        "th": "บริษัท TodayStyle 2100 จำกัด",
    },
    "about_version_info": {
        "en": "Version {version}  |  Build {date}",
        "th": "เวอร์ชัน {version}  |  บิลด์ {date}",
    },
    "changelog_title": {
        "en": "Changelog",
        "th": "บันทึกการเปลี่ยนแปลง",
    },
    "close_btn": {
        "en": "Close",
        "th": "ปิด",
    },
}


def get_lang():
    """Get current language code."""
    return _current_lang


def set_lang(lang):
    """Set language and notify all observers."""
    global _current_lang
    _current_lang = lang
    for cb in _observers:
        try:
            cb(lang)
        except Exception:
            pass


def t(key, **kwargs):
    """Translate a key to the current language.
    Supports format placeholders: t("files_selected", count=3, s="s")
    """
    entry = TRANSLATIONS.get(key)
    if not entry:
        return key
    text = entry.get(_current_lang, entry.get("en", key))
    if kwargs:
        try:
            text = text.format(**kwargs)
        except (KeyError, IndexError):
            pass
    return text


def on_lang_change(callback):
    """Register a callback to be called when language changes. callback(lang_code)."""
    _observers.append(callback)


def remove_observer(callback):
    """Remove a language change observer."""
    if callback in _observers:
        _observers.remove(callback)
