"""
Sugatsune (global.sugatsune.com/global/en/arch) Product Scraper
================================================================
Scrapes every product *series* under the Architectural Hardware section,
expands each series into its individual variants (one Excel row per item
code), downloads images + spec-sheet PDFs, and writes a master index.

Designed so the index can be reused by a future site that displays the
images, drawings, and specs — every file path stored in the index is
relative to the output directory.

Output layout:
  output/
    sugatsune/
      images/
        series/   {MODEL}_p{n}.jpg     (series-level promo shots)
        items/    {ITEMCODE}.jpg       (per-variant images)
      drawings/   {MODEL}_d{n}.jpg     (technical drawings / dimension illustrations)
      specs/      {MODEL}_spec.pdf     (one PDF per series)
      category_ids.json                (cache of discovered categories)
      product_ids.json                 (cache of series URLs per category)
    sugatsune_products.xlsx
    sugatsune_products.json
"""

import re
import json
import time
import argparse
import logging
import requests
import pandas as pd
from pathlib import Path
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor

# ─── Configuration ────────────────────────────────────────────────────────────

BASE_URL    = "https://global.sugatsune.com"
ARCH_URL    = f"{BASE_URL}/global/en/arch"

OUTPUT_DIR   = Path("output")
SUGA_DIR     = OUTPUT_DIR / "sugatsune"
IMG_SERIES   = SUGA_DIR / "images" / "series"
IMG_ITEMS    = SUGA_DIR / "images" / "items"
DRAWINGS_DIR = SUGA_DIR / "drawings"
SPECS_DIR    = SUGA_DIR / "specs"

EXCEL_PATH  = SUGA_DIR / "products.xlsx"
JSON_PATH   = SUGA_DIR / "products.json"
CATS_CACHE  = SUGA_DIR / "category_ids.json"
IDS_CACHE   = SUGA_DIR / "product_ids.json"

REQUEST_DELAY    = 0.6
DOWNLOAD_WORKERS = 5    # concurrent image/PDF downloads per series
DOWNLOAD_TIMEOUT = 12   # seconds before a download attempt is abandoned

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": ARCH_URL,
}

# ─── Setup ────────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

for d in (IMG_SERIES, IMG_ITEMS, DRAWINGS_DIR, SPECS_DIR):
    d.mkdir(parents=True, exist_ok=True)

SESSION = requests.Session()
SESSION.headers.update(HEADERS)


# ─── Helpers ──────────────────────────────────────────────────────────────────

def get(url: str, retries: int = 3) -> BeautifulSoup | None:
    """Fetch a URL and return BeautifulSoup; retry with backoff on failure."""
    for attempt in range(1, retries + 1):
        try:
            r = SESSION.get(url, timeout=20)
            r.raise_for_status()
            return BeautifulSoup(r.text, "lxml")
        except Exception as exc:
            log.warning("Attempt %d/%d failed for %s — %s",
                        attempt, retries, url, exc)
            if attempt < retries:
                time.sleep(2 * attempt)
    log.error("Giving up on %s", url)
    return None


def safe_filename(name: str) -> str:
    return re.sub(r'[\\/*?:"<>|]', "_", name).strip()


def download_file(url: str, dest: Path, retries: int = 3) -> bool:
    """Download a binary file; skip if present. Retries with backoff."""
    if dest.exists() and dest.stat().st_size > 0:
        return True
    for attempt in range(1, retries + 1):
        try:
            r = SESSION.get(url, timeout=DOWNLOAD_TIMEOUT, stream=True)
            r.raise_for_status()
            with open(dest, "wb") as f:
                for chunk in r.iter_content(8192):
                    f.write(chunk)
            return True
        except Exception as exc:
            log.warning("Download attempt %d/%d failed %s — %s",
                        attempt, retries, url, exc)
            if dest.exists():
                try: dest.unlink()
                except OSError: pass
            if attempt < retries:
                time.sleep(1.5 * attempt)
    log.error("Giving up on download %s", url)
    return False


# Maps image/PDF URL → relative path already saved this run.
# Prevents the same URL being downloaded to multiple files.
_url_registry: dict[str, str] = {}


def cached_download(url: str, dest: Path) -> str:
    """Download url to dest; return relative path or '' on failure.
    If this URL was already fetched this run, return the existing path."""
    if url in _url_registry:
        return _url_registry[url]
    if download_file(url, dest):
        rel = str(dest.relative_to(OUTPUT_DIR))
        _url_registry[url] = rel
        return rel
    return ""


def download_many(jobs: list[tuple[str, Path]]) -> dict[str, str]:
    """Download (url, dest) jobs in parallel.
    Returns {url: relative_path} for every successful download.
    URLs already in _url_registry are skipped (no duplicate files)."""
    if not jobs:
        return {}
    result: dict[str, str] = {}
    pending: list[tuple[str, Path]] = []
    seen_urls: set[str] = set()
    for url, dest in jobs:
        if url in _url_registry:
            result[url] = _url_registry[url]
        elif url not in seen_urls:
            # First occurrence of this URL in this batch — download it
            seen_urls.add(url)
            pending.append((url, dest))
        # Duplicate URL in same batch: result will be filled after download
    if pending:
        with ThreadPoolExecutor(max_workers=DOWNLOAD_WORKERS) as pool:
            dl = list(pool.map(lambda j: (j[0], j[1], download_file(j[0], j[1])), pending))
        for url, dest, ok in dl:
            if ok:
                rel = str(dest.relative_to(OUTPUT_DIR))
                _url_registry[url] = rel
                result[url] = rel
    # Fill in any same-batch duplicate URLs that now have a registry entry
    for url, _ in jobs:
        if url not in result and url in _url_registry:
            result[url] = _url_registry[url]
    return result


def img_real_src(img) -> str | None:
    """Return the lazy-loaded image URL (data-src), falling back to src."""
    src = img.get("data-src") or img.get("data-original") or img.get("src")
    if not src:
        return None
    if "spacer.gif" in src or src.startswith("data:"):
        return None
    return src


# ─── Category discovery ───────────────────────────────────────────────────────

CAT_RE = re.compile(r"/global/en/arch/categories/(\d{6})\b")

def discover_categories() -> dict[str, str]:
    """Scrape the /arch landing page for all category IDs and titles."""
    soup = get(ARCH_URL)
    if soup is None:
        return {}
    cats: dict[str, str] = {}
    for a in soup.find_all("a", href=True):
        m = CAT_RE.search(a["href"])
        if m:
            cid = m.group(1)
            label = a.get_text(strip=True) or cid
            # First mention usually has the cleanest label
            cats.setdefault(cid, label)
    return cats


# ─── Listing pages ────────────────────────────────────────────────────────────

PROD_RE = re.compile(r"/global/en/arch/products/([\w_-]+)")

def get_series_urls_from_page(soup: BeautifulSoup) -> list[str]:
    urls: list[str] = []
    seen: set[str] = set()
    for a in soup.find_all("a", href=True):
        m = PROD_RE.search(a["href"])
        if not m:
            continue
        full = urljoin(BASE_URL, a["href"].split("?")[0])
        if full not in seen:
            seen.add(full)
            urls.append(full)
    return urls


def scrape_category(cid: str, max_pages: int | None = None) -> list[str]:
    """Walk every page of a category, returning unique series URLs."""
    series_urls: list[str] = []
    seen: set[str] = set()
    page = 1
    while True:
        if max_pages is not None and page > max_pages:
            break
        url = f"{ARCH_URL}/categories/{cid}?page={page}"
        soup = get(url)
        if soup is None:
            break
        page_urls = get_series_urls_from_page(soup)
        new_urls = [u for u in page_urls if u not in seen]
        if not new_urls:
            break
        for u in new_urls:
            seen.add(u)
            series_urls.append(u)
        log.info("  cat %s page %d → %d new (total %d)",
                 cid, page, len(new_urls), len(series_urls))
        time.sleep(REQUEST_DELAY)
        page += 1
    return series_urls


# ─── Series detail page ──────────────────────────────────────────────────────

def parse_breadcrumb(soup: BeautifulSoup) -> tuple[str, str]:
    """Return (Category, Subcategory) text from the page <title> if present.
    Sugatsune doesn't render a real breadcrumb, but the <title> is in the
    form "MODEL | SUBCATEGORY | Furniture, Architectural ...".
    """
    t = soup.find("title")
    if not t:
        return "", ""
    parts = [p.strip() for p in t.get_text().split("|")]
    if len(parts) >= 2:
        return parts[1], parts[1]
    return "", ""


def parse_series(series_url: str) -> list[dict]:
    """Parse a series page and return one record per variant (item code)."""
    soup = get(series_url)
    if soup is None:
        return []

    # Series model is the trailing path element of the URL (e.g. 21953_a)
    series_id = series_url.rstrip("/").split("/")[-1]

    # --- Spec table: contains the column headers AND every variant ---
    tables = soup.find_all("table")
    spec_table = None
    list_table = None
    for t in tables:
        header = [c.get_text(" ", strip=True)
                  for c in t.find_all("tr")[0].find_all(["th", "td"])]
        # The big "all specs" table starts with Image / Item Name / Item Code
        if "Item Code" in header and len(header) > 4:
            spec_table = t
            break
    for t in tables:
        header = [c.get_text(" ", strip=True)
                  for c in t.find_all("tr")[0].find_all(["th", "td"])]
        if header[:4] == ["Image", "Item Name", "Item Code", "Quotation"] and t is not spec_table:
            list_table = t
            break

    if spec_table is None:
        log.warning("No spec table on %s", series_url)
        return []

    headers = [c.get_text(" ", strip=True)
               for c in spec_table.find_all("tr")[0].find_all(["th", "td"])]

    # Determine the actual product model code from the title bar (e.g. "LDC-N2")
    title = soup.find("title")
    model = ""
    if title:
        first = title.get_text().split("|")[0].strip()
        # Drop any trailing markers
        model = first
    category, subcategory = parse_breadcrumb(soup)

    # --- Series-level promo images (Product Image directory) ---
    series_imgs: list[str] = []
    seen_imgs: set[str] = set()
    for img in soup.find_all("img"):
        src = img_real_src(img)
        if not src:
            continue
        if "/Product%20Image/" in src or "/Product Image/" in src:
            full = urljoin(BASE_URL, src)
            if full not in seen_imgs:
                seen_imgs.add(full)
                series_imgs.append(full)

    # --- Technical drawings / dimension illustrations ---
    # Only collect from containers whose CSS class / id / data-tab contains a
    # drawing-specific keyword (e.g. Sugatsune's "u-drowingSlide").
    # Within those containers, prefer js-smartPhoto hrefs (Slick full-size
    # links) and only fall back to <img> tags when none are present.
    drawing_imgs: list[str] = []
    seen_drawings: set[str] = set()

    def _collect_drawing_urls(container, exclude: set) -> list[str]:
        found: list[str] = []
        seen: set[str] = set()
        # Prefer js-smartPhoto anchors (Slick slider full-size links)
        for a in container.find_all("a", class_="js-smartPhoto", href=True):
            href = a["href"].strip()
            if href and not href.startswith("data:") and "spacer" not in href:
                full = urljoin(BASE_URL, href)
                if full not in seen and full not in exclude:
                    seen.add(full); found.append(full)
        if found:
            return found
        # Fall back to <img> tags only when no smartPhoto links exist
        for img in container.find_all("img"):
            src = img_real_src(img)
            if not src:
                continue
            full = urljoin(BASE_URL, src)
            if full not in seen and full not in exclude:
                seen.add(full); found.append(full)
        return found

    for container in soup.find_all(True):
        attrs = " ".join([
            container.get("class", "") if isinstance(container.get("class"), str)
            else " ".join(container.get("class") or []),
            container.get("id", ""),
            container.get("data-tab", ""),
        ]).lower()
        if not any(kw in attrs for kw in ("drawing", "drowing", "dimension", "cad")):
            continue
        for full in _collect_drawing_urls(container, seen_imgs):
            if full not in seen_drawings:
                seen_drawings.add(full)
                drawing_imgs.append(full)

    # --- Spec-sheet PDF (single per series) ---
    spec_pdf_url = ""
    pdf_anchor = soup.find("a", class_="u-pdf", href=True)
    if pdf_anchor:
        spec_pdf_url = urljoin(BASE_URL, pdf_anchor["href"])

    # --- Build list-table image lookup keyed by Item Name (not row index) ---
    # Keying by name prevents mismatches when the two tables differ in row
    # order or contain filtered/discontinued rows.
    list_imgs_by_name: dict[str, str] = {}
    if list_table is not None:
        list_headers = [c.get_text(" ", strip=True)
                        for c in list_table.find_all("tr")[0].find_all(["th", "td"])]
        name_col = next((i for i, h in enumerate(list_headers)
                         if h.lower() == "item name"), None)
        img_col  = next((i for i, h in enumerate(list_headers)
                         if h.lower() == "image"), None)
        if name_col is not None and img_col is not None:
            for tr in list_table.find_all("tr")[1:]:
                cells = tr.find_all(["th", "td"])
                if len(cells) <= max(name_col, img_col):
                    continue
                iname = cells[name_col].get_text(strip=True)
                img   = cells[img_col].find("img")
                src   = img_real_src(img) if img else None
                if iname and src:
                    list_imgs_by_name[iname] = urljoin(BASE_URL, src)

    # --- Walk spec table: collect variant metadata + image URLs ---
    proto_records: list[dict] = []  # records without file paths yet
    item_img_jobs: list[tuple[str, Path, int]] = []  # (url, dest, record_idx)

    spec_rows = spec_table.find_all("tr")[1:]
    for tr in spec_rows:
        cells = tr.find_all(["th", "td"])
        if len(cells) < 3:
            continue
        row: dict = {}
        for h, c in zip(headers, cells):
            txt = c.get_text(" ", strip=True)
            if h.lower() == "image":
                inner = c.find("img")
                src = img_real_src(inner) if inner else None
                if src:
                    row["_image_url"] = urljoin(BASE_URL, src)
            else:
                row[h] = txt

        item_name = row.get("Item Name", "").strip()
        item_code = row.get("Item Code", "").strip()
        if not item_name and not item_code:
            continue

        # Name-keyed fallback for image
        if "_image_url" not in row and item_name in list_imgs_by_name:
            row["_image_url"] = list_imgs_by_name[item_name]

        img_url = row.pop("_image_url", "")
        record = {
            "Series Model":   model,
            "Item Name":      item_name,
            "Item Code":      item_code,
            "Category":       category,
            "Subcategory":    subcategory,
            "Item Image":     "",          # filled in after parallel download
            "Series Images":  "",          # filled in after parallel download
            "Drawings":       "",          # filled in after parallel download
            "Spec Sheet PDF": "",          # filled in after parallel download
            "Series URL":     series_url,
        }
        for k, v in row.items():
            if k not in ("Item Name", "Item Code", "Quotation"):
                record[k] = v
        if img_url:
            ext  = Path(img_url.split("?")[0]).suffix or ".jpg"
            dest = IMG_ITEMS / f"{safe_filename(item_name or item_code)}{ext}"
            item_img_jobs.append((img_url, dest, len(proto_records)))
        proto_records.append(record)

    # --- Build all download jobs and run in one parallel batch ---
    key = safe_filename(model or series_id)
    series_jobs: list[tuple[str, Path]] = [
        (url, IMG_SERIES / f"{key}_p{i}{Path(url.split('?')[0]).suffix or '.jpg'}")
        for i, url in enumerate(series_imgs, start=1)
    ]
    drawing_jobs: list[tuple[str, Path]] = [
        (url, DRAWINGS_DIR / f"{key}_d{i}{Path(url.split('?')[0]).suffix or '.jpg'}")
        for i, url in enumerate(drawing_imgs, start=1)
    ]
    pdf_jobs: list[tuple[str, Path]] = []
    if spec_pdf_url:
        pdf_jobs = [(spec_pdf_url,
                     SPECS_DIR / f"{key}_spec{Path(spec_pdf_url.split('?')[0]).suffix or '.pdf'}")]

    all_jobs = series_jobs + drawing_jobs + pdf_jobs + [(u, d) for u, d, _ in item_img_jobs]
    # download_many returns {url: relative_path}; cached URLs skip re-download
    url_map = download_many(all_jobs)

    # Resolve series image paths
    saved_series_imgs = [url_map[url] for url, _ in series_jobs if url in url_map]
    series_imgs_str   = "; ".join(saved_series_imgs)

    # Resolve drawing paths
    saved_drawings    = [url_map[url] for url, _ in drawing_jobs if url in url_map]
    drawings_str      = "; ".join(saved_drawings)
    if drawing_imgs:
        log.info("    drawings: %d found, %d downloaded", len(drawing_imgs), len(saved_drawings))

    # Resolve spec PDF path
    saved_spec_pdf = url_map.get(pdf_jobs[0][0], "") if pdf_jobs else ""

    # Backfill paths into records
    records: list[dict] = []
    for rec in proto_records:
        rec["Series Images"]  = series_imgs_str
        rec["Drawings"]       = drawings_str
        rec["Spec Sheet PDF"] = saved_spec_pdf
        records.append(rec)

    for img_url, dest, rec_idx in item_img_jobs:
        if img_url in url_map:
            records[rec_idx]["Item Image"] = url_map[img_url]

    time.sleep(REQUEST_DELAY)
    return records


# ─── Excel + JSON export ──────────────────────────────────────────────────────

CORE_COLS = [
    "Series Model", "Item Name", "Item Code",
    "Category", "Subcategory",
    "Item Image", "Series Images", "Drawings", "Spec Sheet PDF",
    "Series URL",
]

def save_outputs(records: list[dict]) -> None:
    df = pd.DataFrame(records)
    for col in CORE_COLS:
        if col not in df.columns:
            df[col] = ""
    extra = [c for c in df.columns if c not in CORE_COLS]
    df = df[CORE_COLS + extra]

    try:
        with pd.ExcelWriter(EXCEL_PATH, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="Products")
            ws = writer.sheets["Products"]
            for col_cells in ws.columns:
                max_len = max(len(str(c.value)) if c.value else 0 for c in col_cells)
                ws.column_dimensions[col_cells[0].column_letter].width = min(max_len + 4, 50)
            ws.freeze_panes = "A2"
            ws.auto_filter.ref = ws.dimensions
    except PermissionError:
        log.warning("Excel file is open — skipping .xlsx save (JSON still saved)")

    JSON_PATH.write_text(
        json.dumps(records, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    log.info("Saved → %s  (%d variants)", JSON_PATH, len(records))


# ─── Main ────────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Scrape product data from global.sugatsune.com /arch",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--categories", "-c",
                   help="Comma-separated category IDs (skips interactive picker).")
    p.add_argument("--max-pages", "-p", type=int, default=None,
                   help="Limit listing pages per category.")
    p.add_argument("--max-products", "-n", type=int, default=None,
                   help="Stop after scraping this many series.")
    p.add_argument("--refresh-ids", action="store_true",
                   help="Force re-scraping listings even if cache exists.")
    p.add_argument("--refresh-categories", action="store_true",
                   help="Force re-discovery of categories.")
    p.add_argument("--no-prompt", action="store_true",
                   help="Skip interactive picker; scrape all categories.")
    p.add_argument("--no-resume", action="store_true",
                   help="Ignore existing JSON — re-scrape everything.")
    p.add_argument("--backfill-drawings", action="store_true",
                   help="Re-fetch drawings for series with an empty Drawings field.")
    p.add_argument("--test", action="store_true",
                   help="Quick test: 1 category, 1 page, 3 series.")
    return p.parse_args()


# ─── Resume support ──────────────────────────────────────────────────────────

def backfill_drawings(records: list[dict]) -> list[dict]:
    """Re-fetch drawings for every series whose Drawings field is empty."""
    to_backfill: dict[str, list[int]] = {}
    for i, rec in enumerate(records):
        if not rec.get("Drawings"):
            url = rec.get("Series URL", "")
            if url:
                to_backfill.setdefault(url, []).append(i)

    log.info("Backfill: %d series need drawings", len(to_backfill))

    def _collect_drawing_urls_bf(container, exclude: set) -> list[str]:
        found: list[str] = []
        seen: set[str] = set()
        for a in container.find_all("a", class_="js-smartPhoto", href=True):
            href = a["href"].strip()
            if href and not href.startswith("data:") and "spacer" not in href:
                full = urljoin(BASE_URL, href)
                if full not in seen and full not in exclude:
                    seen.add(full); found.append(full)
        if found:
            return found
        for img in container.find_all("img"):
            src = img_real_src(img)
            if not src:
                continue
            full = urljoin(BASE_URL, src)
            if full not in seen and full not in exclude:
                seen.add(full); found.append(full)
        return found

    for n, (url, indices) in enumerate(to_backfill.items(), 1):
        log.info("  [%d/%d] %s", n, len(to_backfill), url)
        soup = get(url)
        if soup is None:
            continue

        series_id = url.rstrip("/").split("/")[-1]
        title_tag = soup.find("title")
        model = title_tag.get_text().split("|")[0].strip() if title_tag else series_id
        key = safe_filename(model or series_id)

        drawing_imgs: list[str] = []
        seen_drawings: set[str] = set()

        for container in soup.find_all(True):
            attrs = " ".join([
                " ".join(container.get("class") or []),
                container.get("id", ""),
                container.get("data-tab", ""),
            ]).lower()
            if not any(kw in attrs for kw in ("drawing", "drowing", "dimension", "cad")):
                continue
            for full in _collect_drawing_urls_bf(container, set()):
                if full not in seen_drawings:
                    seen_drawings.add(full)
                    drawing_imgs.append(full)

        drawing_jobs = [
            (u, DRAWINGS_DIR / f"{key}_d{i}{Path(u.split('?')[0]).suffix or '.jpg'}")
            for i, u in enumerate(drawing_imgs, start=1)
        ]
        url_map = download_many(drawing_jobs)
        saved = [url_map[u] for u, _ in drawing_jobs if u in url_map]
        drawings_str = "; ".join(saved)

        log.info("    → %d drawings found, %d saved", len(drawing_imgs), len(saved))
        for idx in indices:
            records[idx]["Drawings"] = drawings_str

        time.sleep(REQUEST_DELAY)

    return records


def load_existing_records() -> tuple[list[dict], set[str]]:
    """Load previously scraped records (if any) so we can resume."""
    if not JSON_PATH.exists():
        return [], set()
    try:
        records = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    except Exception as exc:
        log.warning("Could not read %s (%s) — starting fresh", JSON_PATH, exc)
        return [], set()
    done = {r.get("Series URL", "") for r in records if r.get("Series URL")}
    return records, done


# ─── Interactive category picker ─────────────────────────────────────────────

def parse_selection(text: str, ordered_cids: list[str]) -> list[str]:
    """Parse user input like '1,3,5-8', 'all', or '200711,200712'."""
    text = text.strip().lower()
    if not text or text in ("all", "*"):
        return ordered_cids
    picked: list[str] = []
    seen: set[str] = set()
    for token in text.replace(" ", "").split(","):
        if not token:
            continue
        if "-" in token and all(p.isdigit() for p in token.split("-")):
            a, b = token.split("-", 1)
            for i in range(int(a), int(b) + 1):
                if 1 <= i <= len(ordered_cids):
                    cid = ordered_cids[i - 1]
                    if cid not in seen:
                        seen.add(cid); picked.append(cid)
        elif token.isdigit() and 1 <= int(token) <= len(ordered_cids):
            cid = ordered_cids[int(token) - 1]
            if cid not in seen:
                seen.add(cid); picked.append(cid)
        else:
            # Treat as raw category id
            if token in seen:
                continue
            seen.add(token); picked.append(token)
    return picked


def prompt_categories(cat_map: dict[str, str],
                      url_cache: dict[str, list[str]],
                      done_urls: set[str]) -> list[str]:
    """Show categories with progress and ask which to scrape."""
    ordered_cids = list(cat_map.keys())
    print()
    print("=" * 78)
    print("  SUGATSUNE — pick categories to scrape")
    print("=" * 78)
    print(f"  {'#':>3}  {'CID':<8} {'Done/Total':<14} {'Category':<40}")
    print("  " + "-" * 74)
    for i, cid in enumerate(ordered_cids, start=1):
        urls = url_cache.get(cid, [])
        total = len(urls) if urls else 0
        done = sum(1 for u in urls if u in done_urls)
        if total == 0:
            progress = "(unknown)"
        elif done == total:
            progress = f"DONE {done}/{total}"
        else:
            progress = f"{done}/{total}"
        label = cat_map.get(cid, "?")
        print(f"  {i:>3}  {cid:<8} {progress:<14} {label[:40]}")
    print("  " + "-" * 74)
    print("  Enter: numbers (e.g. 1,3,5-8), category IDs (e.g. 200711),")
    print("         'all' for everything, or blank to cancel.")
    try:
        choice = input("  > ").strip()
    except EOFError:
        choice = ""
    if not choice:
        log.info("No selection — exiting.")
        raise SystemExit(0)
    return parse_selection(choice, ordered_cids)


def main() -> None:
    args = parse_args()

    # ── Backfill-only mode: patch drawings into existing records and exit ──
    if args.backfill_drawings:
        records, _ = load_existing_records()
        if not records:
            log.error("No existing records to backfill. Run the scraper first.")
            raise SystemExit(1)
        records = backfill_drawings(records)
        save_outputs(records)
        log.info("=== Backfill complete — %d variants updated ===", len(records))
        return

    # ── Discover categories (cached) ──
    cat_map: dict[str, str] = {}
    if CATS_CACHE.exists() and not args.refresh_categories:
        try:
            cat_map = json.loads(CATS_CACHE.read_text(encoding="utf-8"))
            log.info("Loaded %d categories from cache", len(cat_map))
        except Exception:
            cat_map = {}
    if not cat_map:
        log.info("Discovering categories from %s …", ARCH_URL)
        cat_map = discover_categories()
        CATS_CACHE.write_text(json.dumps(cat_map, indent=2), encoding="utf-8")
        log.info("  → %d categories", len(cat_map))

    # ── Load series-URL cache (used by the picker for progress display) ──
    url_cache: dict[str, list[str]] = {}
    if IDS_CACHE.exists() and not args.refresh_ids and not args.test:
        try:
            url_cache = json.loads(IDS_CACHE.read_text(encoding="utf-8"))
        except Exception:
            url_cache = {}

    # ── Load previously scraped records to enable resume ──
    records, done_urls = ([], set()) if args.no_resume else load_existing_records()
    if done_urls:
        log.info("Resume: %d series already scraped (%d variants)",
                 len(done_urls), len(records))

    # ── Resolve category selection ──
    if args.test:
        categories = list(cat_map.keys())[:1]
        max_pages, max_products = 1, 3
        log.info("TEST MODE: cid=%s, 1 page, 3 series", categories)
    elif args.categories:
        categories = [c.strip() for c in args.categories.split(",") if c.strip()]
        max_pages, max_products = args.max_pages, args.max_products
    elif args.no_prompt:
        categories = list(cat_map.keys())
        max_pages, max_products = args.max_pages, args.max_products
    else:
        categories = prompt_categories(cat_map, url_cache, done_urls)
        max_pages, max_products = args.max_pages, args.max_products

    log.info("=== Sugatsune Scraper starting ===")
    log.info("Output: %s", OUTPUT_DIR.resolve())
    log.info("Selected categories (%d): %s",
             len(categories),
             ", ".join(f"{c}({cat_map.get(c, '?')[:20]})" for c in categories[:8])
             + (" …" if len(categories) > 8 else ""))

    # ── Phase 1: ensure URL cache is populated for selected categories ──
    log.info("Phase 1: collecting series URLs …")
    for cid in categories:
        if cid in url_cache and not args.refresh_ids:
            log.info("  Category %s (%s) → %d cached",
                     cid, cat_map.get(cid, "?"), len(url_cache[cid]))
            continue
        log.info("  Scraping category %s (%s) …", cid, cat_map.get(cid, "?"))
        urls = scrape_category(cid, max_pages=max_pages)
        log.info("    → %d series found", len(urls))
        url_cache[cid] = urls   # always update in-memory for Phase 2
        if not args.test:
            IDS_CACHE.write_text(json.dumps(url_cache, indent=2), encoding="utf-8")

    # ── Phase 2: scrape each category in turn, with per-category progress ──
    log.info("Phase 2: parsing series detail pages …")
    total_new = 0
    stop = False
    for ci, cid in enumerate(categories, start=1):
        if stop:
            break
        urls = url_cache.get(cid, [])
        cat_label = cat_map.get(cid, "?")
        already_done = sum(1 for u in urls if u in done_urls)
        remaining = [u for u in urls if u not in done_urls]
        log.info("─" * 70)
        log.info("[Category %d/%d] %s (%s) — %d total, %d done, %d to scrape",
                 ci, len(categories), cid, cat_label,
                 len(urls), already_done, len(remaining))

        for i, url in enumerate(remaining, start=1):
            log.info("  [%s %d/%d] %s", cid, i, len(remaining), url)
            try:
                recs = parse_series(url)
            except KeyboardInterrupt:
                log.warning("Interrupted — saving progress and exiting.")
                stop = True
                break
            records.extend(recs)
            done_urls.add(url)
            total_new += 1
            # Save after every series so a crash/Ctrl-C never loses work
            if total_new % 5 == 0:
                save_outputs(records)
            if max_products and total_new >= max_products:
                log.info("Hit --max-products limit (%d) — stopping.", max_products)
                stop = True
                break

        save_outputs(records)
        log.info("  Category %s complete — running total: %d variants",
                 cid, len(records))

    log.info("Phase 3: writing final Excel + JSON …")
    save_outputs(records)

    log.info("=== Done ===")
    log.info("  Series imgs: %s", IMG_SERIES.resolve())
    log.info("  Item imgs:   %s", IMG_ITEMS.resolve())
    log.info("  Drawings:    %s", DRAWINGS_DIR.resolve())
    log.info("  Spec PDFs:   %s", SPECS_DIR.resolve())
    log.info("  Excel:       %s", EXCEL_PATH.resolve())
    log.info("  JSON index:  %s", JSON_PATH.resolve())


if __name__ == "__main__":
    main()
