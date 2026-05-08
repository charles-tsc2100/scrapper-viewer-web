"""
scrape_simonswerk.py — Scrape ANSELMI and TECTUS products from selector.simonswerk.com

Usage:
  python scrape_simonswerk.py [--dry-run] [--workers 4] [--brand ANSELMI|TECTUS|all]

Output:
  output/simonswerk/products.json      (one record per finish variant)
  output/simonswerk/images/hero/       hero images
  output/simonswerk/images/finish/     per-finish swatch images
  output/simonswerk/docs/              installation PDFs
  output/simonswerk/cad/               CAD drawings (DXF)
  output/simonswerk/routing/           routing data files

The output matches the format expected by viewer/seed_db.py normalise_simonswerk().
"""

import re
import sys
import json
import time
import argparse
import urllib.parse
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from bs4 import BeautifulSoup
from tqdm import tqdm

BASE_URL   = "https://selector.simonswerk.com"
PIM_BASE   = "https://pim-sandboxapi-productselector.simonswerk.com"
OUT_DIR    = Path(__file__).parent / "output" / "simonswerk"
HEADERS    = {"User-Agent": "Mozilla/5.0 (compatible; catalogue-scraper/1.0)"}
SESSION    = requests.Session()
SESSION.headers.update(HEADERS)

# Known product slugs per brand.
# These are discovered from the existing products.json; add new ones as needed.
ANSELMI_SLUGS = [
    "an-107-3d-c40", "an-107-3d-c60", "an-108-3d-sc45", "an-130-2d",
    "an-140-3d", "an-140-3d-alu", "an-140-3d-fz", "an-141-3d-fvz-12-38",
    "an-141-3d-fvz-12-45", "an-141-3d-fvz-14-40", "an-141-3d-fvz-14-44",
    "an-142-3d", "an-150-3d", "an-150-3d-28", "an-150-3d-40", "an-150-3d-44",
    "an-150-3d-alu", "an-160-3d", "an-160-3d-alu", "an-161-3d-fvz-12-38",
    "an-161-3d-fvz-12-45", "an-161-3d-fvz-14-40", "an-164-3d-fvz-12-38",
    "an-164-3d-fvz-14-40", "an-170-3d", "an-170-3d-40", "an-170-3d-44",
    "an-170-3d-alu", "an-172-3d", "an-172-3d-fz", "an-172-3d-sz",
    "an-180-3d", "an-192-3d",
]

TECTUS_SLUGS = [
    "te-240-3d", "te-240-3d-energy", "te-240-3d-fz", "te-240-3d-st",
    "te-240-3d-sz", "te-311-3d-fvz-40", "te-311-3d-fvz-44", "te-311-3d-fvz-fz",
    "te-311-3d-fvz-sz", "te-340-3d", "te-340-3d-energy", "te-340-3d-fr",
    "te-340-3d-fz", "te-340-3d-st", "te-340-3d-sz", "te-380-3d",
    "te-380-3d-fz", "te-380-3d-sz", "te-440-3d", "te-526-3d",
    "te-526-3d-energy", "te-526-527-3d-fz", "te-526-527-3d-st", "te-526-527-3d-sz",
    "te-527-3d", "te-527-3d-energy", "te-540-3d", "te-540-3d-a8",
    "te-540-3d-a8-energy", "te-540-3d-a8-fr", "te-540-3d-a8-sz", "te-540-3d-energy",
    "te-540-3d-fr", "te-540-3d-fz", "te-540-3d-st", "te-540-3d-sz",
    "te-541-3d-fvz", "te-541-3d-fvz-fr", "te-541-3d-fvz-fz", "te-541-3d-fvz-st",
    "te-541-3d-fvz-sz", "te-626-3d-a8", "te-626-3d-a8-bw-1", "te-626-3d-a8-energy",
    "te-640-3d", "te-640-3d-a8", "te-640-3d-a8-bw-1", "te-640-3d-a8-energy",
    "te-640-3d-a8-fr", "te-640-3d-a8-sz", "te-640-3d-bw-16", "te-640-3d-bw-20",
    "te-640-3d-energy", "te-640-3d-fr", "te-640-3d-fz", "te-640-3d-st",
    "te-640-3d-sz", "te-645-3d", "te-645-3d-energy", "te-645-3d-st",
    "te-645-3d-sz", "te-680-3d-fd",
]


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _safe_filename(url: str) -> str:
    """Extract a safe local filename from a URL."""
    path = urllib.parse.urlparse(url).path
    return Path(path).name


def _download(url: str, dest: Path, dry_run: bool) -> bool:
    """Download url to dest. Return True on success/skip, False on error."""
    if dest.exists():
        return True
    if dry_run:
        print(f"  [dry-run] would download {url} -> {dest}")
        return True
    try:
        r = SESSION.get(url, timeout=30, stream=True)
        if r.status_code == 404:
            return False  # silently skip missing drawing images
        r.raise_for_status()
        dest.parent.mkdir(parents=True, exist_ok=True)
        with open(dest, "wb") as f:
            for chunk in r.iter_content(8192):
                f.write(chunk)
        return True
    except Exception as exc:
        print(f"  WARNING: download failed {url}: {exc}", file=sys.stderr)
        return False


def _rel(dest: Path) -> str:
    """Return path relative to output/ as a string with forward slashes."""
    return str(dest.relative_to(OUT_DIR.parent)).replace("\\", "/")


# ─── Page parser ──────────────────────────────────────────────────────────────

def _text(el) -> str:
    return el.get_text(strip=True) if el else ""


def parse_detail(slug: str, dry_run: bool) -> list[dict]:
    """
    Fetch and parse a product detail page.
    Returns a list of records (one per finish variant) in the existing products.json format.
    """
    url  = f"{BASE_URL}/en/products/detail/{slug}"
    resp = SESSION.get(url, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    # ── Top-level product fields ───────────────────────────────────────────
    brand    = _text(soup.find("span", id="brand_name"))
    model_el = soup.find("h1")
    model    = _text(model_el)
    subtitle = _text(model_el.find_next_sibling("h2") if model_el else None)

    # Hero image
    hero_img_el = soup.find("img", class_="preview-image")
    hero_img_url = hero_img_el["src"] if hero_img_el else ""

    # ── Technical specs (General tab) ─────────────────────────────────────
    general_tab = soup.find("div", id="general")
    specs = {}
    if general_tab:
        for col in general_tab.find_all("div", class_=lambda c: c and "col-md-4" in c):
            label_el = col.find("div", class_="fw-bold")
            val_el   = label_el.find_next_sibling("div") if label_el else None
            if label_el and val_el:
                specs[_text(label_el)] = _text(val_el)

    # ── Downloads ─────────────────────────────────────────────────────────
    dl_tab = soup.find("div", id="downloads")
    install_pdf_url  = ""
    adjust_pdf_url   = ""
    load_pdf_url     = ""
    other_docs_urls  = []
    cad_urls         = []
    routing_urls     = []

    if dl_tab:
        for a in dl_tab.find_all("a", href=True):
            href = a["href"]
            if not href or href in ("#", "#!"):
                continue
            name_lower = href.lower()
            filename   = _safe_filename(href).lower()

            # CAD drawings via download endpoint
            if "/api/v1/model/entries/file/download/" in href and "cad_zeichnung" in name_lower:
                cad_urls.append(href)
            elif "/api/v1/model/entries/file/download/" in href and "fraesdaten" in name_lower:
                routing_urls.append(href)
            elif "fraesdaten" in name_lower:
                routing_urls.append(href)
            elif "montageanleitung" in name_lower or "installation" in filename:
                install_pdf_url = href
            elif "einstellanleitung" in name_lower or "adjustment" in filename:
                adjust_pdf_url = href
            elif "belastungswert" in name_lower or "load_capacity" in filename:
                load_pdf_url = href
            elif name_lower.endswith(".pdf"):
                other_docs_urls.append(href)

    # ── Build drawing JPG URLs from CAD DXF filenames ─────────────────────
    # Drawing images live at Ansichtszeichnungen/{BRAND}/{stem}.jpg
    # Not every DXF has a matching JPG — we probe and skip 404s.
    DRAWING_BASE = f"{PIM_BASE}/storage/fileadmin/user_upload/Ansichtszeichnungen"
    drawing_jpg_urls = []
    for cad_url in cad_urls:
        stem = Path(_safe_filename(cad_url)).stem  # e.g. TE_340_3D_V01
        jpg_url = f"{DRAWING_BASE}/{brand}/{stem}.jpg"
        drawing_jpg_urls.append(jpg_url)

    # ── Collect all files to download ─────────────────────────────────────
    def _dest_for(u: str, subdir: str) -> Path:
        return OUT_DIR / subdir / _safe_filename(u)

    file_jobs = {}  # url -> dest Path
    if hero_img_url:
        file_jobs[hero_img_url] = _dest_for(hero_img_url, "images/hero")
    for u in [install_pdf_url, adjust_pdf_url, load_pdf_url] + other_docs_urls:
        if u: file_jobs[u] = _dest_for(u, "docs")
    for u in cad_urls:
        file_jobs[u] = _dest_for(u, "cad")
    for u in routing_urls:
        file_jobs[u] = _dest_for(u, "routing")
    for u in drawing_jpg_urls:
        file_jobs[u] = _dest_for(u, "images/drawings")

    # ── Download all files in parallel ────────────────────────────────────
    if not dry_run:
        with ThreadPoolExecutor(max_workers=6) as pool:
            futs = {pool.submit(_download, u, d, False): u for u, d in file_jobs.items()}
            for f in as_completed(futs):
                pass  # errors already printed inside _download
    else:
        for u, d in file_jobs.items():
            _download(u, d, dry_run=True)

    def _rel_or_empty(u: str, subdir: str) -> str:
        if not u: return ""
        d = _dest_for(u, subdir)
        return "simonswerk\\" + str(d.relative_to(OUT_DIR)).replace("/", "\\") if d.exists() or dry_run else ""

    hero_rel     = _rel_or_empty(hero_img_url, "images/hero")
    install_rel  = _rel_or_empty(install_pdf_url, "docs")
    adjust_rel   = _rel_or_empty(adjust_pdf_url, "docs")
    load_rel     = _rel_or_empty(load_pdf_url, "docs")
    other_rels   = [_rel_or_empty(u, "docs") for u in other_docs_urls if u]
    cad_rels     = [_rel_or_empty(u, "cad") for u in cad_urls]
    routing_rels = [_rel_or_empty(u, "routing") for u in routing_urls]
    drawing_rels = [_rel_or_empty(u, "images/drawings") for u in drawing_jpg_urls]

    cad_str     = "; ".join(r for r in cad_rels if r)
    routing_str = "; ".join(r for r in routing_rels if r)
    drawings_str = "; ".join(r for r in drawing_rels if r)

    # ── Pre-download all finish images in parallel ────────────────────────
    item_tab = soup.find("div", id="item")
    surfaces = item_tab.find_all("div", class_="product-surface") if item_tab else []

    finish_img_jobs = {}  # (slug, safe_code) -> (url, dest)
    for surface in surfaces:
        thumb_img = surface.find("img")
        if not thumb_img: continue
        finish_raw = thumb_img.get("title", "")
        m = re.match(r"^(.+?)\s*\(([^)]+)\)\s*$", finish_raw)
        finish_code = m.group(2).strip() if m else ""
        finish_img_url = thumb_img["src"]
        if finish_img_url:
            ext       = Path(_safe_filename(finish_img_url)).suffix or ".jpg"
            safe_code = re.sub(r"[^a-zA-Z0-9_-]", "_", finish_code)
            fname     = f"{slug}_{safe_code}{ext}"
            dest      = OUT_DIR / "images" / "finish" / fname
            finish_img_jobs[(slug, safe_code)] = (finish_img_url, dest)

    if not dry_run:
        with ThreadPoolExecutor(max_workers=6) as pool:
            futs = {pool.submit(_download, u, d, False): k for k, (u, d) in finish_img_jobs.items()}
            for f in as_completed(futs):
                pass
    else:
        for k, (u, d) in finish_img_jobs.items():
            _download(u, d, dry_run=True)

    records = []
    for surface in surfaces:
        # Finish name + code from the image title "Satin Chrome (AN 014)"
        thumb_img  = surface.find("img")
        finish_raw = thumb_img["title"] if thumb_img else ""
        # Parse "Satin Chrome (AN 014)" → name="Satin Chrome", code="AN 014"
        m = re.match(r"^(.+?)\s*\(([^)]+)\)\s*$", finish_raw)
        if m:
            finish_name = m.group(1).strip()
            finish_code = m.group(2).strip()
        else:
            finish_name = finish_raw
            finish_code = ""

        # Surface image
        finish_img_url = thumb_img["src"] if thumb_img else ""

        # Spec fields from the collapse panel
        detail_map = {}
        for div in surface.find_all("div", class_="fw-bold"):
            label = _text(div)
            val_el = div.find_next_sibling("div")
            if val_el:
                detail_map[label] = _text(val_el)

        ean      = detail_map.get("EAN", "")
        din      = detail_map.get("DIN", "")
        packing  = detail_map.get("Packing unit", "")
        item_no  = detail_map.get("Item No.", "")

        # Look up already-downloaded finish image
        finish_rel = ""
        safe_code_key = re.sub(r"[^a-zA-Z0-9_-]", "_", finish_code)
        job = finish_img_jobs.get((slug, safe_code_key))
        if job:
            _, dest = job
            if dest.exists() or dry_run:
                finish_rel = "simonswerk\\" + str(dest.relative_to(OUT_DIR)).replace("/", "\\")

        record = {
            "Brand":               brand,
            "Model":               model,
            "Subtitle":            subtitle,
            "Slug":                slug,
            "Finish Name":         finish_name,
            "Finish Code":         finish_code,
            "DIN":                 din,
            "Packing Unit":        packing,
            "EAN":                 ean,
            "Item No.":            item_no,
            "Item No. (SAP)":      "",
            "Load Capacity":       specs.get("Load capacity", specs.get("Max. load capacity", "")),
            "Overall Length (mm)": specs.get("Overall length", ""),
            "Width Door Part (mm)":  specs.get("Width (door part)", ""),
            "Width Frame Part (mm)": specs.get("Width (frame part)", ""),
            "Cutter Diameter (mm)":  specs.get("Cutter diameter", ""),
            "Collar Ring Dia (mm)":  specs.get("Collar ring diameter", ""),
            "Opening Angle":         specs.get("Opening angle", ""),
            "Type of Door Leaf":     specs.get("Type of door leaf", ""),
            "Rebate":                specs.get("Rebate", ""),
            "Type of Frame":         specs.get("Type of frame", ""),
            "Functions":             specs.get("Functions", ""),
            "Hero Image":            hero_rel,
            "Finish Image":          finish_rel,
            "Installation PDF":      install_rel,
            "Adjustment PDF":        adjust_rel,
            "Load Capacity PDF":     load_rel,
            "Other Docs":            "; ".join(other_rels),
            "CAD Drawings (DXF)":   cad_str,
            "Routing Data":          routing_str,
            "Drawings":              drawings_str,
            "Product URL":           url,
        }
        records.append(record)

    # If no finish variants found, emit one record with empty finish fields
    if not records:
        records.append({
            "Brand": brand, "Model": model, "Subtitle": subtitle,
            "Slug": slug, "Finish Name": "", "Finish Code": "",
            "DIN": "", "Packing Unit": "", "EAN": "", "Item No.": "",
            "Item No. (SAP)": "",
            "Load Capacity":       specs.get("Load capacity", ""),
            "Overall Length (mm)": specs.get("Overall length", ""),
            "Width Door Part (mm)":  specs.get("Width (door part)", ""),
            "Width Frame Part (mm)": specs.get("Width (frame part)", ""),
            "Cutter Diameter (mm)":  specs.get("Cutter diameter", ""),
            "Collar Ring Dia (mm)":  specs.get("Collar ring diameter", ""),
            "Opening Angle":         specs.get("Opening angle", ""),
            "Type of Door Leaf":     specs.get("Type of door leaf", ""),
            "Rebate":                specs.get("Rebate", ""),
            "Type of Frame":         specs.get("Type of frame", ""),
            "Functions":             specs.get("Functions", ""),
            "Hero Image": hero_rel, "Finish Image": "",
            "Installation PDF": install_rel, "Adjustment PDF": adjust_rel,
            "Load Capacity PDF": load_rel, "Other Docs": "; ".join(other_rels),
            "CAD Drawings (DXF)": cad_str, "Routing Data": routing_str,
            "Drawings": drawings_str,
            "Product URL": url,
        })

    return records


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description="Scrape Simonswerk ANSELMI + TECTUS products")
    ap.add_argument("--brand", choices=["ANSELMI", "TECTUS", "all"], default="all")
    ap.add_argument("--dry-run", action="store_true", help="Parse only, no file downloads")
    ap.add_argument("--workers", type=int, default=3, help="Parallel download workers")
    ap.add_argument("--delay", type=float, default=0.5, help="Seconds between page fetches")
    args = ap.parse_args()

    slugs = []
    if args.brand in ("ANSELMI", "all"): slugs.extend(ANSELMI_SLUGS)
    if args.brand in ("TECTUS",  "all"): slugs.extend(TECTUS_SLUGS)

    print(f"Scraping {len(slugs)} products (brand={args.brand}, dry_run={args.dry_run})")

    # Create output dirs
    for sub in ("images/hero", "images/finish", "docs", "cad", "routing"):
        (OUT_DIR / sub).mkdir(parents=True, exist_ok=True)

    all_records = []
    errors = []

    with tqdm(slugs, unit="product") as bar:
        for slug in bar:
            bar.set_description(slug)
            try:
                records = parse_detail(slug, dry_run=args.dry_run)
                all_records.extend(records)
            except Exception as exc:
                print(f"\nERROR scraping {slug}: {exc}", file=sys.stderr)
                errors.append(slug)
            time.sleep(args.delay)

    out_path = OUT_DIR / "products.json"
    if not args.dry_run:
        out_path.write_text(
            json.dumps(all_records, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        print(f"\nWrote {len(all_records)} records to {out_path}")
    else:
        print(f"\nDry run: {len(all_records)} records parsed (not written)")
        if all_records:
            print("Sample record:")
            print(json.dumps(all_records[0], indent=2, ensure_ascii=False))

    if errors:
        print(f"\nFailed slugs ({len(errors)}): {errors}", file=sys.stderr)

    print(f"Done. {len(all_records)} total records, {len(errors)} errors.")


if __name__ == "__main__":
    main()
