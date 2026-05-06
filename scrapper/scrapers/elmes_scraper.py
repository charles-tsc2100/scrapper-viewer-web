"""
ELMES / Art Union (artunion.co.jp/en) Product Scraper
=====================================================
Scrapes all product details, downloads images, and exports an Excel index.
Brand displayed to end-users is ELMES; source website is artunion.co.jp.

Output layout:
  output/
    elmes/
      images/      product photos  → {MODEL}_{n}.jpg
      drawings/    2D size sheets  → {MODEL}_drawing.jpg
      products.xlsx
      products.json
"""

import os
import re
import sys
import json
import time
import argparse
import logging
import requests
import pandas as pd
from pathlib import Path
from urllib.parse import urljoin, urlencode
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor

# ─── Configuration ────────────────────────────────────────────────────────────

BASE_URL   = "https://www.artunion.co.jp"
BRAND      = "ELMES"

OUTPUT_DIR = Path("output") / "elmes"
IMG_DIR    = OUTPUT_DIR / "images"
DWG_DIR    = OUTPUT_DIR / "drawings"
EXCEL_PATH = OUTPUT_DIR / "products.xlsx"
JSON_PATH  = OUTPUT_DIR / "products.json"
IDS_CACHE  = Path("output") / "product_ids.json"

# Polite delay between requests (seconds)
REQUEST_DELAY = 0.8

# Concurrent image downloads per product (per-product parallelism only)
DOWNLOAD_WORKERS = 5

# Timeout for image/drawing downloads — fail fast and let retries handle it
DOWNLOAD_TIMEOUT = 12

# All product category IDs discovered on the site
CATEGORY_IDS = [
    4, 5, 6, 7, 8, 9, 10, 11, 12,
    14, 15, 16, 17, 18, 19, 20, 211,
    282, 283, 318,
    1048, 1049, 1050, 1051, 1052, 1053, 1054, 1055,
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": BASE_URL,
}

# ─── Setup ────────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

IMG_DIR.mkdir(parents=True, exist_ok=True)
DWG_DIR.mkdir(parents=True, exist_ok=True)

SESSION = requests.Session()
SESSION.headers.update(HEADERS)


# ─── Helpers ──────────────────────────────────────────────────────────────────

def get(url: str, retries: int = 3) -> BeautifulSoup | None:
    """Fetch a URL and return a BeautifulSoup object, with retry logic."""
    for attempt in range(1, retries + 1):
        try:
            r = SESSION.get(url, timeout=20)
            r.raise_for_status()
            return BeautifulSoup(r.text, "lxml")
        except Exception as exc:
            log.warning("Attempt %d failed for %s — %s", attempt, url, exc)
            time.sleep(2 * attempt)
    log.error("Giving up on %s", url)
    return None


def safe_filename(name: str) -> str:
    """Strip characters that are illegal in Windows/Linux filenames."""
    return re.sub(r'[\\/*?:"<>|]', "_", name).strip()


def download_file(url: str, dest: Path, retries: int = 3) -> bool:
    """Download a binary file; skip if already present. Retries on failure."""
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
                try:
                    dest.unlink()
                except OSError:
                    pass
            if attempt < retries:
                time.sleep(1.5 * attempt)
    log.error("Giving up on download %s", url)
    return False


# Maps image URL → relative path already saved this run.
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
            seen_urls.add(url)
            pending.append((url, dest))
    if pending:
        with ThreadPoolExecutor(max_workers=DOWNLOAD_WORKERS) as pool:
            dl = list(pool.map(lambda j: (j[0], j[1], download_file(j[0], j[1])), pending))
        for url, dest, ok in dl:
            if ok:
                rel = str(dest.relative_to(OUTPUT_DIR))
                _url_registry[url] = rel
                result[url] = rel
    for url, _ in jobs:
        if url not in result and url in _url_registry:
            result[url] = _url_registry[url]
    return result


def col_text(soup: BeautifulSoup, label: str) -> str:
    """
    Many detail pages use a two-column <dl> or <table> layout.
    Search for a <th> or <dt> whose text contains the label,
    then return the sibling <td> / <dd> text.
    """
    for tag in soup.find_all(["th", "dt"]):
        if label.lower() in tag.get_text(strip=True).lower():
            sibling = tag.find_next_sibling(["td", "dd"])
            if sibling:
                return sibling.get_text(" ", strip=True)
    return ""


# ─── Listing pages ────────────────────────────────────────────────────────────

def get_product_ids_from_page(soup: BeautifulSoup) -> list[str]:
    """Extract all product IDs from a search-result page."""
    ids = []
    for a in soup.select("ul.product-list li a, #product-list li a, .item-list li a, li.item a"):
        href = a.get("href", "")
        m = re.search(r"id=([^&]+)", href)
        if m:
            ids.append(m.group(1))

    # Fallback: any link to detail.php
    if not ids:
        for a in soup.find_all("a", href=re.compile(r"detail\.php\?id=")):
            m = re.search(r"id=([^&]+)", a["href"])
            if m:
                ids.append(m.group(1))
    return list(dict.fromkeys(ids))  # deduplicate, preserve order


def get_max_page(soup: BeautifulSoup) -> int:
    """Return the last page number for a category listing."""
    # Look for pagination "Last" link or page links
    last_link = soup.find("a", string=re.compile(r"last|≫|>>", re.I))
    if last_link:
        m = re.search(r"pageID=(\d+)", last_link.get("href", ""))
        if m:
            return int(m.group(1))

    # Fall back: collect all numeric pageID values
    pages = []
    for a in soup.find_all("a", href=re.compile(r"pageID=\d+")):
        m = re.search(r"pageID=(\d+)", a["href"])
        if m:
            pages.append(int(m.group(1)))
    return max(pages) if pages else 1


def scrape_category(cid: int, max_pages: int | None = None) -> list[str]:
    """Return every product ID for a given category ID.

    If max_pages is set, only scrape that many listing pages (useful for tests).
    """
    product_ids = []
    first_url = f"{BASE_URL}/en/products/search.php?cid={cid}"
    soup = get(first_url)
    if soup is None:
        return []

    max_page = get_max_page(soup)
    if max_pages is not None:
        max_page = min(max_page, max_pages)
    log.info("  Category %d → scraping %d page(s)", cid, max_page)

    product_ids.extend(get_product_ids_from_page(soup))
    time.sleep(REQUEST_DELAY)

    for page in range(2, max_page + 1):
        url = f"{BASE_URL}/en/products/search.php?cid={cid}&pageID={page}"
        soup = get(url)
        if soup:
            product_ids.extend(get_product_ids_from_page(soup))
        time.sleep(REQUEST_DELAY)

    return list(dict.fromkeys(product_ids))


# ─── Detail page ──────────────────────────────────────────────────────────────

def parse_detail(product_id: str) -> dict:
    """Scrape a product detail page and return a data dict."""
    url = f"{BASE_URL}/en/products/detail.php?id={product_id}"
    soup = get(url)
    if soup is None:
        return {}

    data: dict = {"Model": product_id, "URL": url}

    # ── Category: prefer the <dl><dt>Category</dt><dd>...</dd></dl> block
    # which holds the FULL path (e.g. "Architectural Hardware [Archism]
    # ＞ Door Handle ＞ Door Pulls"). Fall back to the breadcrumb <ul>.
    cat_value = col_text(soup, "category")
    if cat_value:
        # Normalize separators (fullwidth ＞, regular >, ›) to a single ' > '
        normalized = re.sub(r"\s*[＞>›»]\s*", " > ", cat_value)
        data["Category"] = re.sub(r"\s+", " ", normalized).strip()
        # Last segment = leaf subcategory (e.g. "Door Pulls")
        data["Subcategory"] = data["Category"].split(" > ")[-1].strip()
    else:
        for ul in soup.find_all("ul"):
            items = ul.find_all("li", recursive=False)
            if not (3 <= len(items) <= 8):
                continue
            last_li = items[-1]
            if last_li.find("a"):
                continue
            if product_id.lower() not in last_li.get_text(strip=True).lower():
                continue
            crumb_parts = [
                li.find("a").get_text(strip=True)
                for li in items[:-1]
                if li.find("a") and li.find("a").get_text(strip=True)
                   not in ("HOME", "Product", "Products")
            ]
            data["Category"] = " > ".join(crumb_parts)
            if crumb_parts:
                data["Subcategory"] = crumb_parts[-1]
            break

    # ── Product title / model: the site uses <h2> for the model code ───────
    h2 = soup.find("h2")
    if h2:
        # Strip "NEW" badge text if present
        name = re.sub(r"\s*NEW\s*$", "", h2.get_text(strip=True), flags=re.I)
        data["Name"] = name.strip()

    # ── Spec table: try labelled approach first ────────────────────────────
    # The page uses definition-list style: <dt>Label</dt><dd>Value</dd>
    # or <th>Label</th><td>Value</td> in a table.
    spec_labels = {
        "Material & Finish":      ["material", "素材", "仕上"],
        "Size":                   ["size", "寸法", "l600", "length", "全長"],
        "Center-to-Center (mm)":  ["center", "c/c", "c-c", "芯々"],
        "Weight":                 ["weight", "重量"],
        "Installation":           ["installation", "mounting", "取付"],
        "Series":                 ["series", "シリーズ"],
        "Price":                  ["price", "価格"],
    }
    for field, keywords in spec_labels.items():
        for kw in keywords:
            val = col_text(soup, kw)
            if val:
                data[field] = val
                break

    # ── Fallback: dump all <th>/<dt> → <td>/<dd> pairs ───────────────────
    if not data.get("Material & Finish"):
        for row in soup.find_all("tr"):
            cells = row.find_all(["th", "td"])
            if len(cells) == 2:
                key = cells[0].get_text(strip=True)
                val = cells[1].get_text(" ", strip=True)
                if key and val:
                    data.setdefault(key, val)
        # Also try <dl><dt><dd> pairs
        for dl in soup.find_all("dl"):
            dts = dl.find_all("dt")
            dds = dl.find_all("dd")
            for dt, dd in zip(dts, dds):
                key = dt.get_text(strip=True)
                val = dd.get_text(" ", strip=True)
                if key and val:
                    data.setdefault(key, val)

    # ── Images ────────────────────────────────────────────────────────────
    product_images = []
    drawing_images = []

    for img in soup.find_all("img", src=True):
        src = img["src"].strip()
        # Skip empty, placeholder, or icon-sized images
        if not src or src in ("/imgs/item/", "/imgs/size/", "/imgs/image/"):
            continue
        if not re.search(r"\.(jpe?g|png|gif|webp)$", src, re.I):
            continue
        full = urljoin(BASE_URL, src)
        if "/imgs/size/" in src:
            drawing_images.append(full)
        elif "/imgs/item/" in src or "/imgs/image/" in src:
            product_images.append(full)

    # Deduplicate: same URL can appear multiple times in the page HTML
    # (thumbnail + full-size + lightbox all pointing to the same file)
    product_images = list(dict.fromkeys(product_images))
    drawing_images = list(dict.fromkeys(drawing_images))

    # Build download jobs; use visible model code for filenames
    name_for_files = safe_filename(data.get("Name") or product_id)

    img_jobs: list[tuple[str, Path]] = [
        (url, IMG_DIR / f"{name_for_files}_{i}{Path(url).suffix or '.jpg'}")
        for i, url in enumerate(product_images, start=1)
    ]
    dwg_jobs: list[tuple[str, Path]] = [
        (url, DWG_DIR / f"{name_for_files}_drawing_{i}{Path(url).suffix or '.jpg'}")
        for i, url in enumerate(drawing_images, start=1)
    ]

    img_map = download_many(img_jobs)
    dwg_map = download_many(dwg_jobs)

    # Filenames stored in the index — use registry path so cross-product
    # shared images correctly point to wherever the file was first saved
    saved_images   = [img_map[url].split("\\")[-1].split("/")[-1]
                      for url, _ in img_jobs if url in img_map]
    saved_drawings = [dwg_map[url].split("\\")[-1].split("/")[-1]
                      for url, _ in dwg_jobs if url in dwg_map]

    data["Images"]   = "; ".join(saved_images)
    data["Drawings"] = "; ".join(saved_drawings)
    data["Has 2D Drawing"] = "Yes" if saved_drawings else "No"

    time.sleep(REQUEST_DELAY)
    return data


# ─── Excel export ─────────────────────────────────────────────────────────────

COLUMN_ORDER = [
    "Model", "Name", "Category", "Subcategory", "Series",
    "Material & Finish", "Size", "Center-to-Center (mm)", "Weight",
    "Installation",
    "Has 2D Drawing", "Images", "Drawings",
    "Price", "URL",
]


def save_excel(records: list[dict]) -> None:
    df = pd.DataFrame(records)

    # Ensure all expected columns exist (fill missing with empty string)
    for col in COLUMN_ORDER:
        if col not in df.columns:
            df[col] = ""

    # Put known columns first, then any extra columns scraped from spec tables
    extra_cols = [c for c in df.columns if c not in COLUMN_ORDER]
    df = df[COLUMN_ORDER + extra_cols]

    try:
        with pd.ExcelWriter(EXCEL_PATH, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="Products")

            ws = writer.sheets["Products"]

            for col_cells in ws.columns:
                max_len = max(
                    len(str(cell.value)) if cell.value else 0
                    for cell in col_cells
                )
                ws.column_dimensions[col_cells[0].column_letter].width = min(max_len + 4, 60)

            ws.freeze_panes = "A2"
            ws.auto_filter.ref = ws.dimensions
    except PermissionError:
        log.warning("Excel file is open — skipping .xlsx save (JSON still saved)")

    JSON_PATH.write_text(
        json.dumps(records, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    log.info("Saved → %s  (%d products)", JSON_PATH, len(records))


def load_existing_records() -> tuple[list[dict], set[str]]:
    """Load previously scraped records (if any) so reruns can resume."""
    if not JSON_PATH.exists():
        return [], set()
    try:
        records = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    except Exception as exc:
        log.warning("Could not read %s (%s) — starting fresh", JSON_PATH, exc)
        return [], set()
    done = {r.get("Model", "") for r in records if r.get("Model")}
    return records, done


# ─── Main ─────────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Scrape product data from artunion.co.jp/en",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument(
        "--categories", "-c",
        help="Comma-separated category IDs to scrape (default: all 28). "
             "Example: --categories 4,5",
    )
    p.add_argument(
        "--max-pages", "-p", type=int, default=None,
        help="Limit listing pages per category (e.g. 1 for a quick test).",
    )
    p.add_argument(
        "--max-products", "-n", type=int, default=None,
        help="Stop after scraping this many product detail pages.",
    )
    p.add_argument(
        "--refresh-ids", action="store_true",
        help="Force rescraping category listings even if product_ids.json exists.",
    )
    p.add_argument(
        "--no-resume", action="store_true",
        help="Ignore existing products.json — re-scrape every product.",
    )
    p.add_argument(
        "--test", action="store_true",
        help="Shortcut: scrape only category 4, page 1, first 5 products.",
    )
    return p.parse_args()


def main() -> None:
    args = parse_args()

    # ── Resolve test mode / CLI args ───────────────────────────────────────
    if args.test:
        categories  = [4]
        max_pages   = 1
        max_products = 5
        log.info("TEST MODE: cid=4, 1 page, 5 products")
    else:
        if args.categories:
            categories = [int(c.strip()) for c in args.categories.split(",") if c.strip()]
        else:
            categories = CATEGORY_IDS
        max_pages    = args.max_pages
        max_products = args.max_products

    log.info("=== Art Union Scraper starting ===")
    log.info("Output directory: %s", OUTPUT_DIR.resolve())
    log.info("Categories: %s", categories)
    log.info("Max pages/category: %s", max_pages or "ALL")
    log.info("Max products: %s", max_products or "ALL")

    # ── Phase 1: collect all unique product IDs across selected categories
    # Cache is a dict {cid: [ids]} so that different --categories selections
    # can share the cache, and only missing categories are scraped.
    cache: dict[str, list[str]] = {}
    if IDS_CACHE.exists() and not args.refresh_ids and not args.test:
        try:
            cache = json.loads(IDS_CACHE.read_text(encoding="utf-8"))
            log.info("Loaded ID cache (%d categories) from %s", len(cache), IDS_CACHE)
        except Exception as exc:
            log.warning("Could not read cache (%s) — rescraping", exc)
            cache = {}

    log.info("Phase 1: collecting product IDs from %d categories …", len(categories))
    all_ids: list[str] = []
    seen: set[str] = set()

    for cid in categories:
        key = str(cid)
        if key in cache and not args.refresh_ids:
            ids = cache[key]
            log.info("Category %d → %d cached IDs (skip listing)", cid, len(ids))
        else:
            log.info("Scraping category %d …", cid)
            ids = scrape_category(cid, max_pages=max_pages)
            log.info("  → %d products found", len(ids))
            if not args.test:
                cache[key] = ids
                IDS_CACHE.write_text(json.dumps(cache, indent=2), encoding="utf-8")
        for pid in ids:
            if pid not in seen:
                seen.add(pid)
                all_ids.append(pid)

    if max_products:
        all_ids = all_ids[:max_products]

    log.info("Total unique products to scrape: %d", len(all_ids))

    # ── Phase 2: scrape detail pages ──────────────────────────────────────
    if args.no_resume:
        records, done_ids = [], set()
    else:
        records, done_ids = load_existing_records()
        if done_ids:
            log.info("Resume: %d products already in JSON — will skip those",
                     len(done_ids))

    todo_ids = [pid for pid in all_ids if pid not in done_ids]
    log.info("Phase 2: scraping %d product detail pages (%d already done) …",
             len(todo_ids), len(done_ids))

    for i, pid in enumerate(todo_ids, start=1):
        log.info("[%d/%d] %s", i, len(todo_ids), pid)
        data = parse_detail(pid)
        if data:
            records.append(data)

        # Save checkpoint every 25 products (cheaper now since per-product is faster)
        if i % 25 == 0:
            save_excel(records)
            log.info("Checkpoint saved (%d products total)", len(records))

    # ── Phase 3: final Excel export ───────────────────────────────────────
    log.info("Phase 3: saving final Excel index …")
    save_excel(records)

    log.info("=== Done ===")
    log.info("  Images:   %s", IMG_DIR.resolve())
    log.info("  Drawings: %s", DWG_DIR.resolve())
    log.info("  Excel:    %s", EXCEL_PATH.resolve())


if __name__ == "__main__":
    main()
