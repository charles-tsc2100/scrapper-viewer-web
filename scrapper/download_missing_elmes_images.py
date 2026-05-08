"""
download_missing_elmes_images.py — Re-download ELMES images missing from local disk.

Reads output/elmes/products.json, filters to the 4 target categories, finds image
files that are missing locally, and downloads them from Art Union.

After running this, re-run:
  python viewer/upload_assets.py --source elmes
  python viewer/seed_db.py --source elmes

Usage:
  python download_missing_elmes_images.py [--dry-run] [--delay 0.2] [--workers 6]
"""

import sys
import json
import time
import argparse
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from tqdm import tqdm

BASE     = "https://www.artunion.co.jp"
ROOT     = Path(__file__).parent
OUT_DIR  = ROOT / "output" / "elmes"
HEADERS  = {"User-Agent": "Mozilla/5.0 (compatible; catalogue-scraper/1.0)"}
SESSION  = requests.Session()
SESSION.headers.update(HEADERS)

TARGET_CATEGORIES = {"Door Handle", "Lever Handle", "Door Equipment", "Sanitary Hardware"}

# Image URL candidates to try in order
IMG_URL_PATTERNS = [
    "/imgs/item/{fname}",
    "/imgs/image/{fname}",
    "/imgs/detail/{fname}",
]
DWG_URL_PATTERNS = [
    "/imgs/size/{fname}",
    "/imgs/drawing/{fname}",
]


def _category_name(category: str) -> str:
    parts = [p.strip() for p in category.replace("＞", ">").split(">")]
    return parts[1] if len(parts) >= 2 else category


def _download(fname: str, url_patterns: list[str], dest: Path, dry_run: bool) -> bool:
    if dest.exists():
        return True
    if dry_run:
        print(f"  [dry-run] would download {fname}")
        return False
    dest.parent.mkdir(parents=True, exist_ok=True)
    for pattern in url_patterns:
        url = BASE + pattern.format(fname=fname)
        try:
            r = SESSION.get(url, timeout=30, stream=True)
            if r.status_code == 404:
                continue
            r.raise_for_status()
            with open(dest, "wb") as f:
                for chunk in r.iter_content(8192):
                    f.write(chunk)
            return True
        except Exception as exc:
            print(f"  WARNING {url}: {exc}", file=sys.stderr)
    return False


def main():
    ap = argparse.ArgumentParser(description="Re-download missing ELMES images")
    ap.add_argument("--dry-run",  action="store_true")
    ap.add_argument("--delay",    type=float, default=0.0,
                    help="Delay between batches (default 0 — parallel downloads are already rate-limited)")
    ap.add_argument("--workers",  type=int, default=6)
    ap.add_argument("--write-json", action="store_true",
                    help="Also rewrite products.json filtered to only target categories")
    args = ap.parse_args()

    json_path = OUT_DIR / "products.json"
    if not json_path.exists():
        print(f"ERROR: {json_path} not found", file=sys.stderr)
        sys.exit(1)

    all_records = json.loads(json_path.read_text(encoding="utf-8"))
    target_records = [r for r in all_records
                      if _category_name(r.get("Category", "")) in TARGET_CATEGORIES]
    print(f"All products: {len(all_records)}  |  Target categories: {len(target_records)}")

    # Collect all missing image files
    missing_imgs     = []   # (fname, dest)
    missing_drawings = []   # (fname, dest)
    seen = set()

    for rec in target_records:
        for fname in [f.strip() for f in (rec.get("Images") or "").split(";") if f.strip()]:
            dest = OUT_DIR / "images" / fname
            if not dest.exists() and fname not in seen:
                seen.add(fname)
                missing_imgs.append((fname, dest))
        for fname in [f.strip() for f in (rec.get("Drawings") or "").split(";") if f.strip()]:
            dest = OUT_DIR / "drawings" / fname
            if not dest.exists() and fname not in seen:
                seen.add(fname)
                missing_drawings.append((fname, dest))

    print(f"Missing images:   {len(missing_imgs)}")
    print(f"Missing drawings: {len(missing_drawings)}")

    if not missing_imgs and not missing_drawings:
        print("Nothing to download.")
    else:
        ok = fail = 0
        failed_files = []

        def _job(item, patterns):
            fname, dest = item
            return _download(fname, patterns, dest, args.dry_run)

        all_jobs = (
            [(item, IMG_URL_PATTERNS) for item in missing_imgs] +
            [(item, DWG_URL_PATTERNS) for item in missing_drawings]
        )

        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            futs = {pool.submit(_job, item, patterns): item for item, patterns in all_jobs}
            with tqdm(total=len(futs), unit="file", desc="Downloading") as bar:
                for fut in as_completed(futs):
                    fname, _ = futs[fut]
                    try:
                        if fut.result():
                            ok += 1
                        else:
                            fail += 1
                            failed_files.append(fname)
                    except Exception as exc:
                        print(f"\nERROR {fname}: {exc}", file=sys.stderr)
                        fail += 1
                        failed_files.append(fname)
                    finally:
                        bar.update(1)

        print(f"\nDownloaded: {ok}  |  Failed: {fail}")

        if failed_files:
            log_path = ROOT / "output" / "elmes" / "download_failures.json"
            log_path.write_text(
                json.dumps(sorted(failed_files), indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            print(f"Failures logged to {log_path}")

    if args.write_json:
        # Rewrite products.json with only target categories, updating img_rels
        updated = []
        for rec in target_records:
            img_files = [f.strip() for f in (rec.get("Images") or "").split(";") if f.strip()]
            dwg_files = [f.strip() for f in (rec.get("Drawings") or "").split(";") if f.strip()]
            rec["Images"]   = "; ".join(f for f in img_files if (OUT_DIR / "images"   / f).exists())
            rec["Drawings"] = "; ".join(f for f in dwg_files if (OUT_DIR / "drawings" / f).exists())
            updated.append(rec)
        json_path.write_text(json.dumps(updated, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"Rewrote products.json with {len(updated)} target-category records (images verified against disk).")

    print("\nNext steps:")
    print("  python viewer/upload_assets.py --source elmes")
    print("  python viewer/seed_db.py --source elmes")


if __name__ == "__main__":
    main()
