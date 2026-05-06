"""
Simonswerk (selector.simonswerk.com) TECTUS + ANSELMI Product Scraper
======================================================================
Scrapes all TECTUS and ANSELMI concealed hinge products from the Simonswerk
product selector. Produces one Excel/JSON row per finish variant.

Discovery strategy
------------------
The listing page at /en/products/brand/{BRAND} only renders the first 16
products in server-side HTML (remaining products require JavaScript). The
scraper therefore uses a spider approach: it starts from those 16 seed URLs,
then follows every "related product" link that points to a TECTUS (te-*) or
ANSELMI (an-*) slug, iterating until no new slugs are found.

Output layout
-------------
  output/
    simonswerk/
      images/
        hero/     {SLUG}.jpg        (main product photo)
        finish/   {SLUG}_{CODE}.jpg (per-variant finish swatch)
      docs/
        installation/   MA_{SLUG}.pdf
        adjustment/     VH_{SLUG}.pdf
        load_capacity/  HB_{SLUG}.pdf
      cad/              {SLUG}_{view}.dxf
      routing/          {SLUG}_{view}.dxf / .pdf
    simonswerk_products.xlsx
    simonswerk_products.json
"""

import re
import json
import time
import argparse
import logging
from pathlib import Path
from urllib.parse import urljoin

import requests
import pandas as pd
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor

# ─── Configuration ────────────────────────────────────────────────────────────

SELECTOR_BASE = "https://selector.simonswerk.com"
PIM_BASE      = "https://pim-sandboxapi-productselector.simonswerk.com"

BRANDS = ["TECTUS", "ANSELMI"]
# Slug prefixes that belong to each brand (used to filter related-product links)
BRAND_SLUG_PREFIXES = ("te-", "an-")

OUTPUT_DIR   = Path("output")
SIM_DIR      = OUTPUT_DIR / "simonswerk"
IMG_HERO     = SIM_DIR / "images" / "hero"
IMG_FINISH   = SIM_DIR / "images" / "finish"
DOCS_DIR     = SIM_DIR / "docs"
CAD_DIR      = SIM_DIR / "cad"
ROUTING_DIR  = SIM_DIR / "routing"

EXCEL_PATH   = SIM_DIR / "products.xlsx"
JSON_PATH    = SIM_DIR / "products.json"
SLUGS_CACHE  = SIM_DIR / "discovered_slugs.json"

REQUEST_DELAY    = 0.7
DOWNLOAD_WORKERS = 6
DOWNLOAD_TIMEOUT = 15

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": SELECTOR_BASE,
}

# ─── Setup ────────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

for d in (IMG_HERO, IMG_FINISH, DOCS_DIR, CAD_DIR, ROUTING_DIR):
    d.mkdir(parents=True, exist_ok=True)

SESSION = requests.Session()
SESSION.headers.update(HEADERS)


# ─── Helpers ──────────────────────────────────────────────────────────────────

def get(url: str, retries: int = 3) -> BeautifulSoup | None:
    for attempt in range(1, retries + 1):
        try:
            r = SESSION.get(url, timeout=20)
            r.raise_for_status()
            return BeautifulSoup(r.text, "lxml")
        except Exception as exc:
            log.warning("Attempt %d/%d failed for %s — %s", attempt, retries, url, exc)
            if attempt < retries:
                time.sleep(2 * attempt)
    log.error("Giving up on %s", url)
    return None


def safe_filename(name: str) -> str:
    return re.sub(r'[\\/*?:"<>|]', "_", name).strip()


def download_file(url: str, dest: Path, retries: int = 3) -> bool:
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


_url_registry: dict[str, str] = {}


def cached_download(url: str, dest: Path) -> str:
    if url in _url_registry:
        return _url_registry[url]
    if download_file(url, dest):
        rel = str(dest.relative_to(OUTPUT_DIR))
        _url_registry[url] = rel
        return rel
    return ""


def download_many(jobs: list[tuple[str, Path]]) -> dict[str, str]:
    if not jobs:
        return {}
    result: dict[str, str] = {}
    pending: list[tuple[str, Path]] = []
    seen: set[str] = set()
    for url, dest in jobs:
        if url in _url_registry:
            result[url] = _url_registry[url]
        elif url not in seen:
            seen.add(url)
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


_API_DL_PREFIX = "/api/v1/model/entries/file/download"

def resolve_url(href: str) -> str:
    """Turn a relative or absolute href into a full URL on the PIM or selector host.

    CAD drawing links use an authenticated API endpoint; we rewrite them to the
    equivalent direct /storage/ path which is publicly accessible.
    """
    if not href:
        return ""
    if href.startswith("http"):
        url = href
    elif href.startswith("/storage") or href.startswith("/api"):
        url = PIM_BASE + href
    else:
        url = SELECTOR_BASE + href
    # Rewrite authenticated API download endpoint → direct storage path
    if _API_DL_PREFIX in url:
        url = url.replace(
            PIM_BASE + _API_DL_PREFIX,
            PIM_BASE + "/storage",
        )
    return url


def parse_label_value_row(container) -> dict[str, str]:
    """Parse a Bootstrap row of col-md-4/col-lg-3 divs into {label: value}."""
    result: dict[str, str] = {}
    if container is None:
        return result
    for col in container.find_all("div", recursive=False):
        label_div = col.find("div", class_="fw-bold")
        if label_div is None:
            continue
        label = label_div.get_text(strip=True)
        value_div = label_div.find_next_sibling("div")
        value = value_div.get_text(" ", strip=True) if value_div else ""
        if label:
            result[label] = value
    return result


def section_sibling(soup: BeautifulSoup, heading_text: str):
    """Return the next sibling element after the h3 whose text matches heading_text."""
    h3 = soup.find("h3", string=re.compile(re.escape(heading_text), re.I))
    if h3 is None:
        return None
    return h3.find_next_sibling()


# ─── Product discovery ────────────────────────────────────────────────────────

DETAIL_RE = re.compile(r"/en/products/detail/([\w-]+)")


def slugs_from_page(soup: BeautifulSoup) -> list[str]:
    """Extract /en/products/detail/{slug} hrefs; return only TECTUS/ANSELMI slugs."""
    slugs: list[str] = []
    seen: set[str] = set()
    for a in soup.find_all("a", href=DETAIL_RE):
        m = DETAIL_RE.search(a["href"])
        if not m:
            continue
        slug = m.group(1)
        if slug not in seen and slug.startswith(BRAND_SLUG_PREFIXES):
            seen.add(slug)
            slugs.append(slug)
    return slugs


def seed_slugs_from_listing(brand: str) -> list[str]:
    """Fetch the brand listing page and return the initial (server-rendered) slugs."""
    url = f"{SELECTOR_BASE}/en/products/brand/{brand}"
    soup = get(url)
    if soup is None:
        return []
    slugs = slugs_from_page(soup)
    log.info("Brand %s listing → %d seed slugs", brand, len(slugs))
    time.sleep(REQUEST_DELAY)
    return slugs


def discover_all_slugs(refresh: bool = False) -> list[str]:
    """
    Spider from brand listing pages, following related-product links on each
    detail page to discover all TECTUS and ANSELMI products.

    Results are cached in SLUGS_CACHE to avoid repeating discovery on resume.
    """
    if SLUGS_CACHE.exists() and not refresh:
        try:
            cached = json.loads(SLUGS_CACHE.read_text(encoding="utf-8"))
            log.info("Loaded %d slugs from cache", len(cached))
            return cached
        except Exception:
            pass

    known: set[str] = set()
    queue: list[str] = []

    # Seed from listing pages
    for brand in BRANDS:
        for slug in seed_slugs_from_listing(brand):
            if slug not in known:
                known.add(slug)
                queue.append(slug)

    log.info("Starting spider with %d seed slugs …", len(queue))
    processed: set[str] = set()

    while queue:
        slug = queue.pop(0)
        if slug in processed:
            continue
        processed.add(slug)
        url = f"{SELECTOR_BASE}/en/products/detail/{slug}"
        soup = get(url)
        if soup is None:
            time.sleep(REQUEST_DELAY)
            continue
        new_slugs = slugs_from_page(soup)
        added = 0
        for s in new_slugs:
            if s not in known:
                known.add(s)
                queue.append(s)
                added += 1
        log.info("  Spider %s → %d related, %d new (queue %d, known %d)",
                 slug, len(new_slugs), added, len(queue), len(known))
        time.sleep(REQUEST_DELAY)

    ordered = sorted(known)
    SLUGS_CACHE.write_text(json.dumps(ordered, indent=2), encoding="utf-8")
    log.info("Discovery complete: %d total TECTUS+ANSELMI slugs", len(ordered))
    return ordered


# ─── Detail page parser ───────────────────────────────────────────────────────

def infer_brand(slug: str, download_urls: list[str]) -> str:
    """Infer brand from slug prefix or first download URL containing TECTUS/ANSELMI."""
    if slug.startswith("te-"):
        return "TECTUS"
    if slug.startswith("an-"):
        return "ANSELMI"
    for url in download_urls:
        if "TECTUS" in url:
            return "TECTUS"
        if "ANSELMI" in url:
            return "ANSELMI"
    return ""


def parse_variants(soup: BeautifulSoup) -> list[dict]:
    """Parse the 'Item versions' section and return one dict per variant."""
    variants: list[dict] = []
    # Each variant lives in a div.product-surface
    for surface in soup.find_all("div", class_="product-surface"):
        v: dict[str, str] = {}

        # Finish name + code from the accordion header title
        h4 = surface.find("div", class_="h4")
        if h4:
            full_title = h4.get_text(strip=True)
            # "Polished brassed (SW 030)" → name="Polished brassed", code="SW 030"
            m = re.match(r"^(.*?)\s*\(((?:SW|AN)\s*\d+)\)\s*$", full_title)
            if m:
                v["Finish Name"] = m.group(1).strip()
                v["Finish Code"] = m.group(2).strip()
            else:
                v["Finish Name"] = full_title
                v["Finish Code"] = ""

        # Finish swatch image (thumbnail in header)
        thumb_img = surface.find("div", class_="thumbnail")
        if thumb_img:
            img = thumb_img.find("img")
            if img and img.get("src"):
                v["_finish_img_url"] = resolve_url(img["src"])

        # Detail rows inside the collapse: DIN, Packing unit, EAN, Item No., SAP
        # Use fw-bold label elements to find all key-value pairs regardless of
        # their parent div class (DIN row has no mt-3 class, others do).
        collapse = surface.find("div", class_="collapse")
        if collapse:
            for label_el in collapse.find_all("div", class_="fw-bold"):
                label = label_el.get_text(strip=True)
                if not label:
                    continue
                value_el = label_el.find_next_sibling("div")
                value = value_el.get_text(strip=True) if value_el else ""
                v.setdefault(label, value)

        variants.append(v)
    return variants


def parse_downloads(soup: BeautifulSoup) -> dict[str, list[str]]:
    """
    Parse download sections ('Product information', 'CAD drawings', 'Routing data')
    and return {category: [url, …]}.
    """
    sections = {
        "Product information": "product_info",
        "CAD drawings": "cad",
        "Routing data": "routing",
    }
    result: dict[str, list[str]] = {v: [] for v in sections.values()}

    for heading, key in sections.items():
        h3 = soup.find("h3", string=re.compile(re.escape(heading), re.I))
        if h3 is None:
            continue
        wrapper = h3.find_next_sibling()
        if wrapper is None:
            continue
        for a in wrapper.find_all("a", href=re.compile(r"\.(pdf|dxf|dwg)", re.I)):
            href = a.get("href", "")
            if href:
                result[key].append(resolve_url(href))

    return result


def parse_detail(slug: str) -> list[dict]:
    """
    Parse a single product detail page.
    Returns one dict per variant (finish), sharing all product-level fields.
    """
    url = f"{SELECTOR_BASE}/en/products/detail/{slug}"
    soup = get(url)
    if soup is None:
        return []

    # ── Model & subtitle ──────────────────────────────────────────────────
    h1s = soup.find_all("h1")
    model = h1s[0].get_text(strip=True) if h1s else slug

    h2s = soup.find_all("h2")
    subtitle = h2s[0].get_text(strip=True) if h2s else ""

    # ── Technical specs ───────────────────────────────────────────────────
    tech_row = None
    h3_tech = soup.find("h3", string=re.compile(r"Technical details", re.I))
    if h3_tech:
        tech_row = h3_tech.find_next_sibling("div")
    specs = parse_label_value_row(tech_row)

    # ── Suitable for ──────────────────────────────────────────────────────
    suitable_row = None
    h3_suitable = soup.find("h3", string=re.compile(r"Suitable for", re.I))
    if h3_suitable:
        suitable_row = h3_suitable.find_next_sibling("div")
    suitable = parse_label_value_row(suitable_row)

    # ── Function range ────────────────────────────────────────────────────
    functions: list[str] = []
    h3_func = soup.find("h3", string=re.compile(r"Function range", re.I))
    if h3_func:
        ul = h3_func.find_next_sibling("ul")
        if ul:
            functions = [li.get_text(strip=True) for li in ul.find_all("li") if li.get_text(strip=True)]

    # ── Hero image ────────────────────────────────────────────────────────
    hero_img_url = ""
    for img in soup.find_all("img", src=re.compile(r"/Standardbild/")):
        src = img.get("src", "")
        # Pick the one whose path contains the product's brand (TECTUS/ANSELMI)
        if any(b in src for b in BRANDS):
            hero_img_url = resolve_url(src)
            break

    # ── Downloads ─────────────────────────────────────────────────────────
    downloads = parse_downloads(soup)
    all_dl_urls = [u for urls in downloads.values() for u in urls]

    # ── Brand ─────────────────────────────────────────────────────────────
    brand = infer_brand(slug, all_dl_urls)

    # ── Variants ──────────────────────────────────────────────────────────
    variants = parse_variants(soup)
    if not variants:
        # Product has no finish variants — create a single placeholder row
        variants = [{}]

    # ── Build download jobs for parallel fetch ────────────────────────────
    hero_jobs: list[tuple[str, Path]] = []
    if hero_img_url:
        ext = Path(hero_img_url.split("?")[0]).suffix or ".jpg"
        hero_jobs = [(hero_img_url, IMG_HERO / f"{slug}{ext}")]

    finish_jobs: list[tuple[str, Path]] = []
    for v in variants:
        furl = v.pop("_finish_img_url", "")
        if furl:
            ext = Path(furl.split("?")[0]).suffix or ".jpg"
            code_safe = safe_filename(v.get("Finish Code", "unknown"))
            dest = IMG_FINISH / f"{slug}_{code_safe}{ext}"
            v["_finish_img_url_resolved"] = furl
            finish_jobs.append((furl, dest))

    doc_jobs: list[tuple[str, Path]] = []
    for dl_url in downloads.get("product_info", []):
        fname = safe_filename(Path(dl_url.split("?")[0]).name)
        if fname:
            doc_jobs.append((dl_url, DOCS_DIR / fname))

    cad_jobs: list[tuple[str, Path]] = []
    for dl_url in downloads.get("cad", []):
        fname = safe_filename(Path(dl_url.split("?")[0]).name)
        if fname:
            cad_jobs.append((dl_url, CAD_DIR / fname))

    routing_jobs: list[tuple[str, Path]] = []
    for dl_url in downloads.get("routing", []):
        fname = safe_filename(Path(dl_url.split("?")[0]).name)
        if fname:
            routing_jobs.append((dl_url, ROUTING_DIR / fname))

    all_jobs = hero_jobs + finish_jobs + doc_jobs + cad_jobs + routing_jobs
    url_map = download_many(all_jobs)

    hero_path = url_map.get(hero_img_url, "") if hero_img_url else ""

    # Restore finish image paths from url_map
    for v, (furl, dest) in zip(variants, finish_jobs):
        resolved = v.pop("_finish_img_url_resolved", "")
        v["Finish Image"] = url_map.get(resolved, "")

    # Resolve doc/cad/routing paths for Excel
    install_pdf = adj_pdf = load_pdf = ""
    other_docs: list[str] = []
    for dl_url in downloads.get("product_info", []):
        path = url_map.get(dl_url, "")
        lower = dl_url.lower()
        if "montageanleitung" in lower or "installation" in lower:
            install_pdf = install_pdf or path
        elif "verstellhinweise" in lower or "adjustment" in lower:
            adj_pdf = adj_pdf or path
        elif "belastungswert" in lower or "load" in lower:
            load_pdf = load_pdf or path
        elif path:
            other_docs.append(path)

    cad_paths  = "; ".join(url_map[u] for u in downloads.get("cad", []) if u in url_map)
    rout_paths = "; ".join(url_map[u] for u in downloads.get("routing", []) if u in url_map)

    # ── Assemble records ──────────────────────────────────────────────────
    records: list[dict] = []
    for v in variants:
        rec = {
            "Brand":               brand,
            "Model":               model,
            "Subtitle":            subtitle,
            "Slug":                slug,
            "Finish Name":         v.get("Finish Name", ""),
            "Finish Code":         v.get("Finish Code", ""),
            "DIN":                 v.get("DIN", ""),
            "Packing Unit":        v.get("Packing unit", "") or v.get("Packing Unit", ""),
            "EAN":                 v.get("EAN", ""),
            "Item No.":            v.get("Item No.", ""),
            "Item No. (SAP)":      v.get("ITEM NO. (SAP)", "") or v.get("Item No. (SAP)", ""),
            # Technical specs
            "Load Capacity":       specs.get("Load capacity", ""),
            "Overall Length (mm)": specs.get("Overall length", ""),
            "Width Door Part (mm)":specs.get("Width (door part)", ""),
            "Width Frame Part (mm)":specs.get("Width (frame part)", ""),
            "Cutter Diameter (mm)":specs.get("Cutter diameter", ""),
            "Collar Ring Dia (mm)":specs.get("Collar ring diameter", ""),
            "Opening Angle":       specs.get("Opening angle", ""),
            # Suitable for
            "Type of Door Leaf":   suitable.get("Type of door leaf", ""),
            "Rebate":              suitable.get("Rebate", ""),
            "Type of Frame":       suitable.get("Type of frame", ""),
            # Functions
            "Functions":           "; ".join(functions),
            # Media
            "Hero Image":          hero_path,
            "Finish Image":        v.get("Finish Image", ""),
            # Downloads
            "Installation PDF":    install_pdf,
            "Adjustment PDF":      adj_pdf,
            "Load Capacity PDF":   load_pdf,
            "Other Docs":          "; ".join(other_docs),
            "CAD Drawings (DXF)":  cad_paths,
            "Routing Data":        rout_paths,
            # Link
            "Product URL":         url,
        }
        records.append(rec)

    time.sleep(REQUEST_DELAY)
    return records


# ─── Excel + JSON export ──────────────────────────────────────────────────────

CORE_COLS = [
    "Brand", "Model", "Subtitle", "Slug",
    "Finish Name", "Finish Code", "DIN", "Packing Unit",
    "EAN", "Item No.", "Item No. (SAP)",
    "Load Capacity", "Overall Length (mm)", "Width Door Part (mm)",
    "Width Frame Part (mm)", "Cutter Diameter (mm)", "Collar Ring Dia (mm)",
    "Opening Angle",
    "Type of Door Leaf", "Rebate", "Type of Frame",
    "Functions",
    "Hero Image", "Finish Image",
    "Installation PDF", "Adjustment PDF", "Load Capacity PDF",
    "Other Docs", "CAD Drawings (DXF)", "Routing Data",
    "Product URL",
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
                ws.column_dimensions[col_cells[0].column_letter].width = min(max_len + 4, 60)
            ws.freeze_panes = "A2"
            ws.auto_filter.ref = ws.dimensions
    except PermissionError:
        log.warning("Excel file is open — skipping .xlsx save (JSON still saved)")

    JSON_PATH.write_text(
        json.dumps(records, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    log.info("Saved → %s  (%d variants)", JSON_PATH, len(records))


# ─── Resume support ───────────────────────────────────────────────────────────

def load_existing_records() -> tuple[list[dict], set[str]]:
    if not JSON_PATH.exists():
        return [], set()
    try:
        records = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    except Exception as exc:
        log.warning("Could not read %s (%s) — starting fresh", JSON_PATH, exc)
        return [], set()
    done = {r.get("Slug", "") for r in records if r.get("Slug")}
    return records, done


# ─── CLI ─────────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Scrape TECTUS + ANSELMI products from selector.simonswerk.com",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--refresh-slugs", action="store_true",
                   help="Re-run slug discovery even if cache exists.")
    p.add_argument("--no-resume", action="store_true",
                   help="Ignore existing JSON — re-scrape everything.")
    p.add_argument("--max-products", "-n", type=int, default=None,
                   help="Stop after scraping this many product pages.")
    p.add_argument("--test", action="store_true",
                   help="Quick test: scrape only the first 3 discovered slugs.")
    return p.parse_args()


# ─── Main ────────────────────────────────────────────────────────────────────

def main() -> None:
    args = parse_args()

    log.info("=== Simonswerk Scraper starting ===")
    log.info("Output: %s", OUTPUT_DIR.resolve())

    # Phase 1: discover all product slugs
    log.info("Phase 1: discovering TECTUS + ANSELMI product slugs …")
    all_slugs = discover_all_slugs(refresh=args.refresh_slugs)
    log.info("  → %d slugs to process", len(all_slugs))

    if args.test:
        all_slugs = all_slugs[:3]
        log.info("TEST MODE: limiting to first 3 slugs")

    # Phase 2: load resume state
    if args.no_resume:
        records, done_slugs = [], set()
    else:
        records, done_slugs = load_existing_records()
        if done_slugs:
            log.info("Resume: %d slugs already scraped (%d variants)",
                     len(done_slugs), len(records))

    todo = [s for s in all_slugs if s not in done_slugs]
    if args.max_products:
        todo = todo[:args.max_products]

    log.info("Phase 2: parsing %d product pages (%d done, %d to scrape) …",
             len(all_slugs), len(done_slugs), len(todo))

    total_new = 0
    for i, slug in enumerate(todo, start=1):
        log.info("[%d/%d] %s", i, len(todo), slug)
        try:
            recs = parse_detail(slug)
        except KeyboardInterrupt:
            log.warning("Interrupted — saving progress and exiting.")
            break
        records.extend(recs)
        done_slugs.add(slug)
        total_new += 1
        if total_new % 10 == 0:
            save_outputs(records)

    log.info("Phase 3: writing final Excel + JSON …")
    save_outputs(records)

    log.info("=== Done ===")
    log.info("  Hero images:    %s", IMG_HERO.resolve())
    log.info("  Finish images:  %s", IMG_FINISH.resolve())
    log.info("  Documents:      %s", DOCS_DIR.resolve())
    log.info("  CAD drawings:   %s", CAD_DIR.resolve())
    log.info("  Routing data:   %s", ROUTING_DIR.resolve())
    log.info("  Excel:          %s", EXCEL_PATH.resolve())
    log.info("  JSON index:     %s", JSON_PATH.resolve())


if __name__ == "__main__":
    main()
