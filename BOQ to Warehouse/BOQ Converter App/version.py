r"""
Version information and changelog for BOQ to Warehouse Form Converter.
"""

APP_VERSION = "1.4.1"
APP_BUILD_DATE = "2026-06-17"

CHANGELOG = [
    {
        "version": "1.4.1",
        "date": "2026-06-17",
        "changes": {
            "en": [
                "Fixed: BOQ files where multiple door codes share one schedule sheet (codes listed in column A) now correctly output all door types — previously only the sheet name was used, silently dropping the sibling codes",
            ],
            "th": [
                "แก้ไข: ไฟล์ BOQ ที่มีรหัสประตูหลายรายการในชีตเดียวกัน (รหัสอยู่ในคอลัมน์ A) ตอนนี้แสดงประตูครบทุกประเภทแล้ว — ก่อนหน้านี้ระบบใช้เฉพาะชื่อชีตเป็นรหัสเดียว ทำให้รหัสที่เหลือหายไปโดยไม่แจ้งเตือน",
            ],
        },
    },
    {
        "version": "1.4.0",
        "date": "2026-06-08",
        "changes": {
            "en": [
                "Added: Product prices (effective unit price, list price, discount rate) are now recorded in the database for every conversion — enables per-project price history and cross-project price comparison",
                "Added: BOQ Brand Usage table in Lark now shows unit price, list price, discount rate, and a 'price varies' flag when the same SKU appears at different prices within a project",
                "Added: Converting a BOQ now automatically updates the linked Sale Projects record — sets Status to 'BOQ' (if currently empty) and fills the Brands field with all brands in the BOQ",
                "Fixed: BOQ Brand Usage 'Sale Projects' link field now correctly uses the two-way link type",
            ],
            "th": [
                "เพิ่ม: ราคาสินค้า (ราคาต่อหน่วยจริง, ราคาตามรายการ, อัตราส่วนลด) ถูกบันทึกในฐานข้อมูลทุกครั้งที่แปลง — ช่วยให้ดูประวัติราคาต่อโครงการและเปรียบเทียบราคาข้ามโครงการได้",
                "เพิ่ม: ตาราง BOQ Brand Usage ใน Lark แสดงราคาต่อหน่วย, ราคาตามรายการ, อัตราส่วนลด และ flag 'price varies' เมื่อ SKU เดียวกันมีราคาต่างกันในโครงการเดียวกัน",
                "เพิ่ม: การแปลง BOQ จะอัปเดต Sale Projects ที่เชื่อมโยงโดยอัตโนมัติ — ตั้ง Status เป็น 'BOQ' (ถ้าว่างอยู่) และกรอก Brands ด้วยแบรนด์ทั้งหมดในไฟล์ BOQ",
                "แก้ไข: ฟิลด์ลิงก์ 'Sale Projects' ใน BOQ Brand Usage ใช้ประเภท two-way link ที่ถูกต้องแล้ว",
            ],
        },
    },
    {
        "version": "1.3.3",
        "date": "2026-05-25",
        "changes": {
            "en": [
                "Fixed: Duplicate rows in Lark BOQ Brand Usage (from prior category-change re-converts) are now detected and removed on the next sync",
                "Fixed: Offline-queued conversions failed to supersede prior entries when flushed — they now correctly replace the old project data",
            ],
            "th": [
                "แก้ไข: แถวซ้ำใน Lark BOQ Brand Usage (จากการแปลงซ้ำที่เคยเปลี่ยนประเภทโครงการ) จะถูกตรวจพบและลบออกในการซิงค์ครั้งถัดไป",
                "แก้ไข: การแปลงที่บันทึกไว้ขณะออฟไลน์ไม่สามารถแทนที่ข้อมูลเดิมได้เมื่ออัปโหลด — ตอนนี้จะแทนที่ข้อมูลโครงการเก่าได้ถูกต้อง",
            ],
        },
    },
    {
        "version": "1.3.2",
        "date": "2026-05-25",
        "changes": {
            "en": [
                "Fixed: Re-converting a project under a different Project Category no longer creates duplicate rows in the Lark BOQ Brand Usage table — the previous conversion is now correctly replaced regardless of category change",
            ],
            "th": [
                "แก้ไข: การแปลงโครงการเดิมซ้ำด้วยประเภทโครงการที่ต่างออกไปจะไม่สร้างแถวซ้ำใน Lark BOQ Brand Usage อีกต่อไป — การแปลงก่อนหน้าจะถูกแทนที่อย่างถูกต้องไม่ว่าประเภทโครงการจะเปลี่ยนหรือไม่",
            ],
        },
    },
    {
        "version": "1.3.1",
        "date": "2026-05-25",
        "changes": {
            "en": [
                "Fixed: Project Name field is now read-only — name is set automatically from the Lark project picker",
                "Improved: Convert button is now greyed out until all requirements are met (files loaded, parsed, project selected, category chosen)",
                "Removed: User Guide button from the header",
            ],
            "th": [
                "แก้ไข: ฟิลด์ชื่อโปรเจกต์เป็น read-only แล้ว — ชื่อจะถูกกำหนดจากการเลือกโปรเจกต์ใน Lark อัตโนมัติ",
                "ปรับปรุง: ปุ่ม Convert จะแสดงสีเทาจนกว่าจะครบเงื่อนไข (โหลดไฟล์, parse, เลือกโปรเจกต์, เลือกประเภทโปรเจกต์)",
                "ลบ: ปุ่ม User Guide ออกจากส่วนหัว",
            ],
        },
    },
    {
        "version": "1.3.0",
        "date": "2026-05-25",
        "changes": {
            "en": [
                "Changed: Project must now be selected from Lark — free-text custom project names are no longer allowed",
                "Added: If a project is missing from the list, the app now shows a clear message to create it in Lark first then Refresh",
                "Added: BOQ Brand Usage table in Lark CRM is now linked to Sale Projects via a two-way native link field",
                "Added: Model description is now tracked in BOQ Brand Usage alongside brand and model code",
            ],
            "th": [
                "เปลี่ยนแปลง: ต้องเลือกโปรเจกต์จาก Lark เท่านั้น — ไม่สามารถกรอกชื่อโปรเจกต์เองได้อีกต่อไป",
                "เพิ่ม: หากโปรเจกต์ไม่ปรากฏในรายการ แอปจะแจ้งให้สร้างโปรเจกต์ใน Lark ก่อนแล้วกด Refresh",
                "เพิ่ม: ตาราง BOQ Brand Usage ใน Lark CRM เชื่อมต่อกับ Sale Projects ผ่าน Link field แบบสองทาง",
                "เพิ่ม: คำอธิบายรุ่น (Model Description) ถูกบันทึกใน BOQ Brand Usage ควบคู่กับแบรนด์และรหัสรุ่น",
            ],
        },
    },
    {
        "version": "1.2.3",
        "date": "2026-05-22",
        "changes": {
            "en": [
                "Added: Refresh from Lark button — sync project list from Lark directly inside the app without restarting",
                "Removed: Progress bar next to Convert button",
            ],
            "th": [
                "เพิ่ม: ปุ่ม Refresh from Lark — ซิงค์รายการโครงการจาก Lark ได้โดยตรงในแอป โดยไม่ต้องรีสตาร์ท",
                "ลบ: แถบความคืบหน้าข้างปุ่ม Convert",
            ],
        },
    },
    {
        "version": "1.2.2",
        "date": "2026-05-22",
        "changes": {
            "en": [
                "Fixed: Project picker search now clears the placeholder when typing — no more characters inserted into '— Select a project —'",
                "Fixed: Project Category and Project picker dropdowns now match the dark theme (was rendering white on Windows)",
            ],
            "th": [
                "แก้ไข: การค้นหาในช่องเลือกโครงการตอนนี้ล้างข้อความ placeholder เมื่อพิมพ์ — ไม่มีอักษรแทรกเข้าใน '— เลือกโครงการ —' อีกต่อไป",
                "แก้ไข: dropdown ประเภทโครงการและเลือกโครงการตอนนี้แสดงสีตรงกับธีมสีเข้ม (เคยแสดงเป็นสีขาวบน Windows)",
            ],
        },
    },
    {
        "version": "1.2.1",
        "date": "2026-05-22",
        "changes": {
            "en": [
                "Fixed: Project Category field is now a dropdown with all 9 project types — no longer a plain text box",
            ],
            "th": [
                "แก้ไข: ฟิลด์ประเภทโครงการตอนนี้เป็น dropdown พร้อม 9 ประเภทโครงการ — ไม่ใช่กล่องข้อความธรรมดาอีกต่อไป",
            ],
        },
    },
    {
        "version": "1.2.0",
        "date": "2026-05-22",
        "changes": {
            "en": [
                "Added: Project picker — search and select from your live Lark project list before converting; name and category autofill automatically",
                "Added: Project Category field — required before converting; used to track which project types use which brands and models",
                "Added: Category write-back — if a project has no Project Type in Lark, filling it in the app syncs it back to Lark automatically",
                "Added: Conversion deduplication — re-converting the same project marks the previous conversion as superseded, keeping analytics accurate",
            ],
            "th": [
                "เพิ่ม: ตัวเลือกโครงการ — ค้นหาและเลือกโครงการจากรายการ Lark แบบเรียลไทม์ก่อนแปลง; ชื่อและประเภทจะกรอกอัตโนมัติ",
                "เพิ่ม: ฟิลด์ประเภทโครงการ — จำเป็นก่อนแปลงไฟล์; ใช้ติดตามว่าโครงการประเภทใดใช้แบรนด์และรุ่นใดบ้าง",
                "เพิ่ม: ซิงค์ประเภทโครงการกลับ — หากโครงการใน Lark ยังไม่มี Project Type การกรอกในแอปจะอัปเดตใน Lark โดยอัตโนมัติ",
                "เพิ่ม: ป้องกันข้อมูลซ้ำ — การแปลงโครงการเดิมซ้ำจะทำเครื่องหมายการแปลงก่อนหน้าว่าถูกแทนที่ เพื่อให้ข้อมูลวิเคราะห์ถูกต้อง",
            ],
        },
    },
    {
        "version": "1.1.3",
        "date": "2026-05-22",
        "changes": {
            "en": [
                "Added: total_quantity field in conversion log — each project's total hardware quantity is now recorded alongside item count and door type count",
            ],
            "th": [
                "เพิ่ม: ฟิลด์ total_quantity ในบันทึกการแปลง — ปริมาณรวมของ hardware ทั้งหมดในโครงการถูกบันทึกพร้อมกับจำนวนรายการและประเภทประตู",
            ],
        },
    },
    {
        "version": "1.1.2",
        "date": "2026-05-22",
        "changes": {
            "en": [
                "Added: Conversion analytics — every successful conversion is silently logged to a shared cloud database (brand, model, project name, quantities)",
                "Added: Offline resilience — if the network is unavailable, the log is queued locally and uploaded automatically on the next conversion",
                "No changes required on user machines — update the .exe as normal",
            ],
            "th": [
                "เพิ่ม: ระบบบันทึกข้อมูลการแปลง — ทุกการแปลงที่สำเร็จจะถูกบันทึกลงฐานข้อมูลกลาง (แบรนด์ รุ่น ชื่อโครงการ จำนวน) โดยอัตโนมัติ",
                "เพิ่ม: รองรับกรณีไม่มีอินเตอร์เน็ต — บันทึกไว้ในเครื่องและอัปโหลดอัตโนมัติเมื่อเชื่อมต่อครั้งถัดไป",
                "ผู้ใช้ไม่ต้องติดตั้งอะไรเพิ่ม — อัปเดต .exe ตามปกติ",
            ],
        },
    },
    {
        "version": "1.1.1",
        "date": "2026-05-22",
        "changes": {
            "en": [
                "Fixed: Convert button no longer disappears when the window is resized smaller — action bar is now pinned to the bottom of the window",
            ],
            "th": [
                "แก้ไข: ปุ่ม Convert ไม่หายอีกต่อไปเมื่อย่อขนาดหน้าต่าง — แถบปุ่มตอนนี้ยึดอยู่ที่ด้านล่างของหน้าต่างเสมอ",
            ],
        },
    },
    {
        "version": "1.1.0",
        "date": "2026-05-22",
        "changes": {
            "en": [
                "Added: 'Combine door types into one sheet' checkbox — when checked (default), all door categories (Aluminium Door, Door, Wood Door, Glass Door, Built-in, etc.) are merged into a single output sheet instead of separate sheets per category",
                "Behaviour: checkbox is on by default; uncheck to restore the previous per-category multi-sheet output",
            ],
            "th": [
                "เพิ่ม: ช่องทำเครื่องหมาย 'รวมประเภทประตูเป็นชีตเดียว' — เมื่อเลือก (ค่าเริ่มต้น) ประเภทประตูทั้งหมดจะรวมอยู่ในชีตเดียวแทนที่จะแยกเป็นหลายชีตตามหมวดหมู่",
                "พฤติกรรม: เปิดอยู่ตามค่าเริ่มต้น ยกเลิกการเลือกเพื่อกลับสู่การแยกชีตตามหมวดหมู่เดิม",
            ],
        },
    },
    {
        "version": "1.0.9",
        "date": "2026-05-14",
        "changes": {
            "en": [
                "Fixed: Hidden and very-hidden sheets in BOQ workbooks are now ignored during parsing, config detection, and the sheet picker",
            ],
            "th": [
                "แก้ไข: ชีตที่ถูกซ่อน (hidden / very hidden) ในไฟล์ BOQ จะถูกข้ามในการอ่านไฟล์ การตรวจหาการตั้งค่า และตัวเลือกชีต",
            ],
        },
    },
    {
        "version": "1.0.8",
        "date": "2026-04-22",
        "changes": {
            "en": [
                "Added: Error Log viewer - view, scroll, and clear application logs from the Settings section",
                "Added: Full error logging with tracebacks for parse and conversion errors (in-memory, export when needed)",
                "Fixed: Stale bytecode cache causing conversion errors after code updates",
            ],
            "th": [
                "เพิ่ม: ตัวดูบันทึกข้อผิดพลาด - ดู เลื่อน และล้างบันทึกแอปจากส่วนตั้งค่า",
                "เพิ่ม: ระบบบันทึกข้อผิดพลาดพร้อม traceback สำหรับข้อผิดพลาดในการอ่านและแปลง (เก็บในหน่วยความจำ ส่งออกได้เมื่อต้องการ)",
                "แก้ไข: แคช bytecode เก่าที่ทำให้เกิดข้อผิดพลาดในการแปลงหลังอัพเดทโค้ด",
            ],
        },
    },
    {
        "version": "1.0.7",
        "date": "2026-04-22",
        "changes": {
            "en": [
                "Fixed: Door quantities from cover sheet now correctly map to individual door codes in Group-based BOQ files",
                "Added: source_group tracking - each door code remembers which Group it belongs to, enabling accurate quantity inheritance from the cover sheet",
                "Supports multi-group sheets (e.g. Group3,5) where each sub-group has separate quantities",
            ],
            "th": [
                "แก้ไข: จำนวนประตูจากใบปะหน้าสามารถแมปไปยังรหัสประตูแต่ละบานในไฟล์ BOQ แบบ Group ได้ถูกต้อง",
                "เพิ่ม: ระบบติดตาม source_group - รหัสประตูแต่ละบานจดจำว่าอยู่ใน Group ไหน เพื่อรับจำนวนจากใบปะหน้าได้แม่นยำ",
                "รองรับชีตที่มีหลาย Group (เช่น Group3,5) โดยแต่ละ sub-group มีจำนวนแยกกัน",
            ],
        },
    },
    {
        "version": "1.0.6",
        "date": "2026-04-22",
        "changes": {
            "en": [
                "Fixed: BOQ files using Group-based sheet names (e.g. Group1, Group2A, Group3,5) now correctly extract individual door codes as column headers instead of showing group names",
                "Added: Per-sheet dynamic detection of door code rows - parser now scans each sheet independently instead of relying on a fixed start row from the first sheet",
                "Added: Group label filtering - 'Group X' section headers are recognized and skipped so they never appear as door codes in the warehouse form",
            ],
            "th": [
                "แก้ไข: ไฟล์ BOQ ที่ใช้ชื่อชีตแบบ Group (เช่น Group1, Group2A, Group3,5) สามารถดึงรหัสประตูแต่ละบานเป็นหัวคอลัมน์ได้ถูกต้อง แทนที่จะแสดงชื่อ Group",
                "เพิ่ม: ระบบตรวจจับตำแหน่งรหัสประตูแบบอัตโนมัติต่อชีต - parser สแกนแต่ละชีตแยกกัน แทนที่จะใช้ตำแหน่งเริ่มต้นจากชีตแรก",
                "เพิ่ม: กรองป้ายชื่อ Group - ระบบจะข้ามหัวข้อ 'Group X' ไม่ให้ปรากฏเป็นรหัสประตูในฟอร์มโรงงาน",
            ],
        },
    },
    {
        "version": "1.0.5",
        "date": "2026-04-08",
        "changes": {
            "en": [
                "Added: Products from BOQ OPTION sections are now labelled 'Option' in column A of the warehouse form",
                "Technical: Added is_option field to Product dataclass; set to True for all products parsed after a repeated header row within a BOQ sheet",
            ],
            "th": [
                "เพิ่ม: สินค้าจากส่วน OPTION ใน BOQ จะแสดงคำว่า 'Option' ในคอลัมน์ A ของฟอร์มโรงงาน",
                "เทคนิค: เพิ่มฟิลด์ is_option ใน Product dataclass; ตั้งค่าเป็น True สำหรับสินค้าที่ parse หลังแถวหัวตารางซ้ำในชีต BOQ",
            ],
        },
    },
    {
        "version": "1.0.4",
        "date": "2026-04-08",
        "changes": {
            "en": [
                "Fixed: Column headers (BRAND, MODEL, DESCRIPTION) no longer appear as product rows in output — caused by BOQ sheets that repeat the header row before an OPTION section",
                "Fixed: Products in secondary sections (e.g. OPTION blocks) are now captured — data scan range extended from header+25 to header+100 rows",
            ],
            "th": [
                "แก้ไข: หัวคอลัมน์ (BRAND, MODEL, DESCRIPTION) ไม่แสดงเป็นแถวสินค้าในผลลัพธ์อีกต่อไป — เกิดจาก BOQ ที่คัดลอกแถวหัวตารางซ้ำก่อนส่วน OPTION",
                "แก้ไข: สินค้าในส่วนที่สอง (เช่น ส่วน OPTION) ถูกดึงข้อมูลแล้ว — ขยายช่วงการสแกนจาก header+25 เป็น header+100 แถว",
            ],
        },
    },
    {
        "version": "1.0.3",
        "date": "2026-04-08",
        "changes": {
            "en": [
                "Fixed: Door quantity mapping now uses exact matching — codes like D2.2 no longer inherit D2's quantity (was caused by substring check in qty map builder)",
                "Fixed: D2.2 shows 2 (was 7), D4.1 shows 7 (was 21), D11.1 shows 37 (was 106)",
                "Added: 'Use UNIT price' checkbox — outputs raw col-I (UNIT) price for all products, ignoring Net After Discount column",
                "Technical: Added raw_list_price field to Product dataclass to preserve original col-I value",
            ],
            "th": [
                "แก้ไข: การจับคู่จำนวนประตูใช้การเปรียบเทียบแบบตรงตัว — รหัสเช่น D2.2 จะไม่รับจำนวนของ D2 อีกต่อไป",
                "แก้ไข: จำนวน D2.2 = 2 (เดิม 7), D4.1 = 7 (เดิม 21), D11.1 = 37 (เดิม 106)",
                "เพิ่ม: Checkbox 'ใช้ราคา UNIT' — แสดงราคาจากคอลัมน์ I สำหรับทุกผลิตภัณฑ์ ไม่สนใจคอลัมน์ Net After Discount",
                "เทคนิค: เพิ่มฟิลด์ raw_list_price ใน Product dataclass เพื่อเก็บค่าคอลัมน์ I เดิม",
            ],
        },
    },
    {
        "version": "1.0.2",
        "date": "2026-04-03",
        "changes": {
            "en": [
                "Fixed: Missing prices for items in merged Excel cells (e.g., MIWA handle/lock sets) by implementing a merged-value lookup system",
                "Improved: Parser performance by building the merged-cell lookup once per sheet before the product loop",
                "Fixed: unit_price (Col I) and net_val (Col J) now correctly fall back to merged values when a cell returns None",
                "Technical: Preserved existing logic for NET price detection in column J",
                "Changed: Default language set to Thai (th) for broader accessibility",
            ],
            "th": [
                "แก้ไข: ปัญหาราคาไม่แสดงสำหรับรายการในเซลล์ที่ถูกผสาน (Merged Cells) เช่น ชุดมือจับและตลับกุญแจ MIWA โดยการเพิ่มระบบค้นหาค่าจากเซลล์ที่ผสาน",
                "ปรับปรุง: ประสิทธิภาพการประมวลผลโดยสร้างตารางค้นหาค่าเซลล์ที่ผสานเพียงครั้งเดียวต่อชีทก่อนเริ่มอ่านข้อมูลสินค้า",
                "แก้ไข: คอลัมน์ unit_price (I) และ net_val (J) สามารถดึงราคาจากเซลล์หลักได้ถูกต้องในกรณีที่เป็นเซลล์ที่ถูกผสาน",
                "ทางเทคนิค: ยังคงรักษากฎการตรวจจับราคา NET ในคอลัมน์ J ไว้ตามเดิมโดยไม่ส่งผลกระทบ",
                "เปลี่ยนแปลง: ตั้งค่าภาษาเริ่มต้นเป็นภาษาไทย (th) เพื่อให้เข้าถึงได้ง่ายขึ้น",
            ]
        }
    },
    {
        "version": "1.0.1",
        "date": "2026-03-30",
        "changes": {
            "en": [
                "Fixed: Cover sheet (ใบปะหน้า) not mapping door quantities correctly",
                "Fixed: Door code detection now finds ALL codes (was skipping first code in some sheets)",
                "Fixed: Hyphenated door codes (D-3, D-21) now recognized correctly",
                "Fixed: Comma-separated sheet names (D1,2,5,3) now split into individual door codes (D1, D2, D5, D3)",
                "Fixed: Range notation in sheet names (D-14,17-19,33-35) expanded correctly",
                "Improved: Cell Reference Settings dialog wider for better readability",
                "Improved: Field buttons wider to show full text without truncation",
                "Added: Version info and changelog accessible from the app",
            ],
            "th": [
                "แก้ไข: ใบปะหน้าไม่ดึงจำนวนประตูมาถูกต้อง",
                "แก้ไข: ตรวจจับรหัสประตูได้ครบทุกรหัสแล้ว (ก่อนหน้านี้ข้ามรหัสแรกในบางชีท)",
                "แก้ไข: รหัสประตูที่มีขีด (D-3, D-21) ตรวจจับได้ถูกต้อง",
                "แก้ไข: ชื่อชีทที่มีจุลภาค (D1,2,5,3) แยกเป็นรหัสประตูแต่ละตัว (D1, D2, D5, D3)",
                "แก้ไข: ช่วงตัวเลขในชื่อชีท (D-14,17-19,33-35) ขยายได้ถูกต้อง",
                "ปรับปรุง: หน้าต่างตั้งค่าอ้างอิงเซลล์กว้างขึ้นอ่านง่ายขึ้น",
                "ปรับปรุง: ปุ่มฟิลด์กว้างขึ้นเห็นข้อความเต็ม",
                "เพิ่ม: ข้อมูลเวอร์ชันและบันทึกการเปลี่ยนแปลงในแอป",
            ],
        },
    },
    {
        "version": "1.0.0",
        "date": "2026-03-20",
        "changes": {
            "en": [
                "Initial release",
                "Parse BOQ Excel files and convert to warehouse picking forms",
                "Multi-file support with category auto-detection",
                "EN/TH language toggle",
                "Visual cell reference selector",
                "Pricing section toggle (show/hide prices)",
                "Brand name prefixing for all products",
                "NET price detection from column J",
                "Auto-detect cell references from BOQ files",
                "PyInstaller support for standalone .exe",
            ],
            "th": [
                "เวอร์ชันแรก",
                "อ่านไฟล์ BOQ Excel และแปลงเป็นฟอร์มหยิบสินค้าคลัง",
                "รองรับหลายไฟล์พร้อมตรวจจับหมวดหมู่อัตโนมัติ",
                "สลับภาษา EN/TH",
                "ตัวเลือกอ้างอิงเซลล์แบบภาพ",
                "เปิด/ปิดส่วนราคา",
                "แสดงชื่อแบรนด์นำหน้าสินค้าทั้งหมด",
                "ตรวจจับราคา NET จากคอลัมน์ J",
                "ตรวจจับอ้างอิงเซลล์อัตโนมัติจากไฟล์ BOQ",
                "รองรับ PyInstaller สำหรับ .exe แบบสแตนด์อโลน",
            ],
        },
    },
]
