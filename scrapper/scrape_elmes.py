"""
scrape_elmes.py — Scrape Art Union / ELMES products from artunion.co.jp

Targets only: Door Handle (cid=4), Lever Handle (cid=5),
              Door Equipment (cid=6), Sanitary Hardware (cid=9)

Usage:
  python scrape_elmes.py [--dry-run] [--cid 4] [--delay 0.3]

Output:
  output/elmes/products.json      (one record per product)
  output/elmes/images/            product images (item + detail + size drawings)
"""

import re
import sys
import json
import time
import argparse
import os
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from bs4 import BeautifulSoup
from tqdm import tqdm

BASE        = "https://www.artunion.co.jp"
OUT_DIR     = Path(__file__).parent / "output" / "elmes"
HEADERS     = {"User-Agent": "Mozilla/5.0 (compatible; catalogue-scraper/1.0)"}
SESSION     = requests.Session()
SESSION.headers.update(HEADERS)

CATEGORIES = {
    4: "Door Handle",
    5: "Lever Handle",
    6: "Door Equipment",
    9: "Sanitary Hardware",
}


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _download(url: str, dest: Path) -> bool:
    if dest.exists():
        return True
    try:
        r = SESSION.get(url, timeout=30, stream=True)
        if r.status_code == 404:
            return False
        r.raise_for_status()
        dest.parent.mkdir(parents=True, exist_ok=True)
        with open(dest, "wb") as f:
            for chunk in r.iter_content(8192):
                f.write(chunk)
        return True
    except Exception as exc:
        print(f"  WARNING: {url}: {exc}", file=sys.stderr)
        return False


def _get_page_ids(cid: int, page: int) -> list[str]:
    url  = f"{BASE}/en/products/search.php?cid={cid}&pageID={page}"
    resp = SESSION.get(url, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    ids  = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "detail.php?id=" in href:
            pid = href.split("id=")[-1].strip()
            if pid and pid not in ids:
                ids.append(pid)
    return ids


def _last_page(cid: int) -> int:
    url  = f"{BASE}/en/products/search.php?cid={cid}&pageID=1"
    resp = SESSION.get(url, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    last = 1
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if f"cid={cid}" in href and "pageID=" in href:
            try:
                n = int(href.split("pageID=")[-1].split("&")[0])
                if n > last:
                    last = n
            except ValueError:
                pass
    # Also check "Last" link text
    for a in soup.find_all("a", href=True):
        if a.get_text(strip=True).lower() == "last" and f"cid={cid}" in a["href"]:
            try:
                n = int(a["href"].split("pageID=")[-1].split("&")[0])
                if n > last:
                    last = n
            except ValueError:
                pass
    return last


# ─── Product detail parser ────────────────────────────────────────────────────

def parse_product(pid: str, dry_run: bool) -> dict | None:
    url  = f"{BASE}/en/products/detail.php?id={pid}"
    resp = SESSION.get(url, timeout=30)
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    # ── Specs from dl elements ─────────────────────────────────────────────
    specs = {}
    detail_div = soup.find("div", class_=lambda c: c and "wDetail" in str(c))
    if detail_div:
        for dl in detail_div.find_all("dl"):
            dt = dl.find("dt")
            dd = dl.find("dd")
            if dt and dd:
                key = dt.get_text(strip=True)
                val = dd.get_text(separator=" ", strip=True)
                specs[key] = val

    # ── Category from breadcrumb ───────────────────────────────────────────
    raw_cat = specs.get("Category", "")
    # Replace full-width ＞ with >
    raw_cat = raw_cat.replace("＞", ">").replace("＞", ">").strip()
    parts   = [p.strip() for p in raw_cat.split(">")]
    # parts[0] = "Architectural Hardware [Archism]", parts[1] = "Door Handle", parts[2] = subcategory
    category    = " > ".join(parts[:3]) if len(parts) >= 3 else raw_cat
    subcategory = parts[-1] if len(parts) >= 3 else (parts[-1] if parts else "")

    # ── Product images from #detailImgInner ───────────────────────────────
    img_div = soup.find("div", id="detailImgInner")
    img_files = []
    drawing_files = []
    if img_div:
        for li in img_div.find_all("li"):
            img = li.find("img")
            if not img:
                continue
            src = img.get("src", "")
            if not src or "/common/" in src:
                continue
            fname = os.path.basename(src)
            if "/size/" in src:
                drawing_files.append(fname)
            else:
                img_files.append(fname)

    # ── Download images in parallel ────────────────────────────────────────
    # Try multiple URL path patterns; _download stops at first that succeeds
    IMG_PATTERNS = ["/imgs/item/{f}", "/imgs/image/{f}", "/imgs/detail/{f}"]
    DWG_PATTERNS = ["/imgs/size/{f}", "/imgs/drawing/{f}"]

    def _try_download(fname: str, patterns: list[str], dest: Path) -> None:
        if dest.exists():
            return
        for pat in patterns:
            if _download(BASE + pat.format(f=fname), dest):
                return

    jobs_img = [(f, OUT_DIR / "images"   / f, IMG_PATTERNS) for f in img_files
                if not (OUT_DIR / "images" / f).exists()]
    jobs_dwg = [(f, OUT_DIR / "drawings" / f, DWG_PATTERNS) for f in drawing_files
                if not (OUT_DIR / "drawings" / f).exists()]

    if not dry_run:
        with ThreadPoolExecutor(max_workers=4) as pool:
            futs = [pool.submit(_try_download, f, pats, dest)
                    for f, dest, pats in jobs_img + jobs_dwg]
            for fut in as_completed(futs):
                fut.result()
    else:
        for f, dest, _ in (jobs_img + jobs_dwg)[:2]:
            print(f"  [dry-run] {BASE}/imgs/item/{f} -> {dest}")

    # Build relative paths for manifest resolution
    img_rels = []
    for fname in img_files:
        dest = OUT_DIR / "images" / fname
        if dest.exists() or dry_run:
            img_rels.append(fname)
    drawing_rels = []
    for fname in drawing_files:
        dest = OUT_DIR / "drawings" / fname
        if dest.exists() or dry_run:
            drawing_rels.append(fname)

    return {
        "Model":               pid,
        "URL":                 url,
        "Category":            category,
        "Subcategory":         subcategory,
        "Name":                specs.get("Name", ""),
        "Material & Finish":   specs.get("Material & Finish", ""),
        "Size":                specs.get("Size", ""),
        "Center-to-Center (mm)": specs.get("Center-to-Center", ""),
        "Installation":        specs.get("Installation Mathod", specs.get("Installation Method", "")),
        "Weight":              specs.get("Weight", ""),
        "Images":              "; ".join(img_rels),
        "Drawings":            "; ".join(drawing_rels),
        "Has 2D Drawing":      "Yes" if drawing_rels else "",
    }


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description="Scrape Art Union / ELMES products")
    ap.add_argument("--cid",      type=int, nargs="+", default=list(CATEGORIES),
                    help="Category IDs to scrape (default: 4 5 6 9)")
    ap.add_argument("--dry-run",  action="store_true")
    ap.add_argument("--delay",    type=float, default=0.3)
    ap.add_argument("--workers",  type=int, default=1,
                    help="Parallel workers for product page fetching (default: 1)")
    ap.add_argument("--resume",   action="store_true", help="Skip products already in output JSON")
    args = ap.parse_args()

    for sub in ("images", "drawings"):
        (OUT_DIR / sub).mkdir(parents=True, exist_ok=True)

    # Load existing records if resuming
    out_path  = OUT_DIR / "products.json"
    existing  = {}
    if args.resume and out_path.exists():
        for r in json.loads(out_path.read_text(encoding="utf-8")):
            existing[r["Model"]] = r
        print(f"Resuming: {len(existing)} existing records loaded")

    # Discover all product IDs per category
    all_ids = []
    for cid in args.cid:
        cat_name = CATEGORIES.get(cid, f"cid={cid}")
        print(f"Discovering {cat_name} (cid={cid})…")
        last = _last_page(cid)
        print(f"  {last} pages")
        cat_ids = []
        for page in tqdm(range(1, last + 1), desc=cat_name, unit="page"):
            ids = _get_page_ids(cid, page)
            for pid in ids:
                if pid not in cat_ids:
                    cat_ids.append(pid)
            time.sleep(args.delay)
        print(f"  {len(cat_ids)} products found")
        all_ids.extend(cat_ids)

    # Deduplicate (some products appear in multiple categories)
    seen = set()
    unique_ids = []
    for pid in all_ids:
        if pid not in seen:
            seen.add(pid)
            unique_ids.append(pid)
    print(f"\nTotal unique products: {len(unique_ids)}")

    # Scrape each product
    records = dict(existing)
    errors  = []
    lock    = __import__("threading").Lock()

    to_scrape = [pid for pid in unique_ids
                 if not (args.resume and pid in existing)]

    def _scrape_one(pid: str):
        time.sleep(args.delay)
        try:
            rec = parse_product(pid, dry_run=args.dry_run)
            if rec:
                with lock:
                    records[pid] = rec
        except Exception as exc:
            print(f"\nERROR {pid}: {exc}", file=sys.stderr)
            with lock:
                errors.append(pid)

    with tqdm(total=len(to_scrape), unit="product") as bar:
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            futs = {pool.submit(_scrape_one, pid): pid for pid in to_scrape}
            for fut in as_completed(futs):
                bar.set_description(futs[fut])
                bar.update(1)
                fut.result()  # re-raise any unhandled exception

    # Filter to only target categories (discard non-target products from output)
    target_names = set(CATEGORIES.values())  # {"Door Handle", "Lever Handle", ...}
    result = []
    for rec in records.values():
        raw_cat = rec.get("Category", "")
        parts   = [p.strip() for p in raw_cat.replace("＞", ">").split(">")]
        cat2    = parts[1] if len(parts) >= 2 else raw_cat
        if cat2 in target_names:
            result.append(rec)

    if not args.dry_run:
        out_path.write_text(
            json.dumps(result, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )
        print(f"\nWrote {len(result)} records to {out_path}")
    else:
        print(f"\nDry run: {len(result)} records parsed (target categories only)")
        if result:
            print("Sample:", json.dumps(result[0], indent=2, ensure_ascii=False))

    if errors:
        print(f"Failed ({len(errors)}): {errors[:10]}", file=sys.stderr)

    print(f"Done. {len(result)} records, {len(errors)} errors.")


if __name__ == "__main__":
    main()
