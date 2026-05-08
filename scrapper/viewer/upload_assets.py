"""
upload_assets.py — Mirror local output/<source>/ assets to cloud storage.

Images  -> Cloudinary (free 25 GB, no credit card)
Drawings -> Supabase Storage bucket "drawings" (free 1 GB, no credit card)

Usage:
  python viewer/upload_assets.py --source elmes [--dry-run] [--workers 6]

After a successful run, writes viewer/asset_manifest.json mapping
  local relative path  ->  public CDN URL
The seed script reads this manifest to rewrite paths before inserting to Supabase.
"""

import os
import sys
import json
import argparse
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

import io
import cloudinary
import cloudinary.uploader
from PIL import Image
from supabase import create_client
from dotenv import load_dotenv
from tqdm import tqdm

HERE = Path(__file__).parent
ROOT = HERE.parent

load_dotenv(HERE / ".env")

cloudinary.config(
    cloud_name=os.environ["CLOUDINARY_CLOUD_NAME"],
    api_key=os.environ["CLOUDINARY_API_KEY"],
    api_secret=os.environ["CLOUDINARY_API_SECRET"],
    secure=True,
)

_supabase = create_client(
    os.environ["SUPABASE_URL"],
    os.environ["SUPABASE_SERVICE_KEY"],
)

MANIFEST_PATH = HERE / "asset_manifest.json"

SOURCES = {
    "elmes":      ROOT / "output" / "elmes",
    "sugatsune":  ROOT / "output" / "sugatsune",
    "simonswerk": ROOT / "output" / "simonswerk",
}

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg"}
SKIP_EXTS  = {".xlsx", ".json"}


def _is_image(path: Path) -> bool:
    return path.suffix.lower() in IMAGE_EXTS


def _should_skip(path: Path) -> bool:
    return path.suffix.lower() in SKIP_EXTS


def collect_files(source_dir: Path, source: str) -> list[tuple[Path, str, bool]]:
    results = []
    for p in source_dir.rglob("*"):
        if not p.is_file() or _should_skip(p):
            continue
        rel = p.relative_to(source_dir)
        key = f"{source}/{rel}".replace("\\", "/")
        results.append((p, key, _is_image(p)))
    return results


_MAX_BYTES = 9 * 1024 * 1024  # 9 MB — compress before hitting Cloudinary's 10 MB limit


def _compress_image(local_path: Path) -> bytes | None:
    """Return JPEG-compressed bytes if file exceeds _MAX_BYTES, else None."""
    if local_path.stat().st_size <= _MAX_BYTES:
        return None
    with Image.open(local_path) as img:
        if img.mode not in ("RGB", "L"):
            img = img.convert("RGB")
        for quality in (85, 70, 55, 40):
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=quality, optimize=True)
            if buf.tell() <= _MAX_BYTES:
                return buf.getvalue()
        # Last resort: scale down
        buf = io.BytesIO()
        img.thumbnail((3000, 3000), Image.LANCZOS)
        img.save(buf, format="JPEG", quality=40, optimize=True)
        return buf.getvalue()


def upload_image(local_path: Path, public_id: str, dry_run: bool) -> str:
    if dry_run:
        return f"https://res.cloudinary.com/<cloud>/image/upload/{public_id}"
    compressed = _compress_image(local_path)
    result = cloudinary.uploader.upload(
        compressed if compressed is not None else str(local_path),
        public_id=public_id,
        overwrite=True,
        resource_type="auto",
    )
    return result["secure_url"]


def _sanitize_storage_key(key: str) -> str:
    """Replace characters that Supabase Storage rejects (non-ASCII, spaces)."""
    import unicodedata
    # Normalize unicode then encode to ASCII, dropping non-ASCII chars
    normalized = unicodedata.normalize("NFKD", key)
    sanitized = normalized.encode("ascii", errors="ignore").decode("ascii")
    # Replace spaces with underscores
    return sanitized.replace(" ", "_")


def upload_drawing(local_path: Path, storage_key: str, dry_run: bool) -> str:
    safe_key = _sanitize_storage_key(storage_key)
    if dry_run:
        return f"<SUPABASE_URL>/storage/v1/object/public/drawings/{safe_key}"
    with open(local_path, "rb") as f:
        data = f.read()
    _supabase.storage.from_("drawings").upload(safe_key, data, {"upsert": "true"})
    return _supabase.storage.from_("drawings").get_public_url(safe_key)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", required=True, choices=list(SOURCES))
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--workers", type=int, default=6)
    args = ap.parse_args()

    source_dir = SOURCES[args.source]
    if not source_dir.exists():
        print(f"ERROR: source directory not found: {source_dir}", file=sys.stderr)
        sys.exit(1)

    all_files = collect_files(source_dir, args.source)
    images   = [(p, k) for p, k, is_img in all_files if is_img]
    drawings = [(p, k) for p, k, is_img in all_files if not is_img]

    img_bytes = sum(p.stat().st_size for p, _ in images)
    dwg_bytes = sum(p.stat().st_size for p, _ in drawings)
    print(f"Images:   {len(images):,} files  ({img_bytes / 1_048_576:.1f} MB)  -> Cloudinary")
    print(f"Drawings: {len(drawings):,} files  ({dwg_bytes / 1_048_576:.1f} MB)  -> Supabase Storage")

    if args.dry_run:
        print("\nImages (first 10):")
        for p, k in images[:10]:
            print(f"  {k}")
        print("\nDrawings (first 10):")
        for p, k in drawings[:10]:
            print(f"  {k}")
        print("\nDry run complete - nothing uploaded.")
        return

    manifest: dict[str, str] = {}
    if MANIFEST_PATH.exists():
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

    skipped = uploaded = errors = 0

    def upload_one_image(args_tuple):
        local_path, key = args_tuple
        rel = str(local_path.relative_to(ROOT)).replace("\\", "/")
        if rel in manifest:
            return rel, manifest[rel], True
        public_id = key.rsplit(".", 1)[0] if "." in key else key
        url = upload_image(local_path, public_id, False)
        return rel, url, False

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(upload_one_image, (p, k)): (p, k) for p, k in images}
        with tqdm(total=len(futures), unit="img", desc="Images -> Cloudinary") as bar:
            for fut in as_completed(futures):
                try:
                    rel, url, was_skipped = fut.result()
                    manifest[rel] = url
                    if was_skipped:
                        skipped += 1
                    else:
                        uploaded += 1
                except Exception as exc:
                    print(f"\nERROR: {futures[fut][0]}: {exc}", file=sys.stderr)
                    errors += 1
                finally:
                    bar.update(1)

    with tqdm(total=len(drawings), unit="file", desc="Drawings -> Supabase Storage") as bar:
        for local_path, key in drawings:
            rel = str(local_path.relative_to(ROOT)).replace("\\", "/")
            try:
                url = upload_drawing(local_path, key, False)
                manifest[rel] = url
                uploaded += 1
            except Exception as exc:
                print(f"\nERROR: {local_path}: {exc}", file=sys.stderr)
                errors += 1
            finally:
                bar.update(1)

    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nDone. Uploaded: {uploaded}  Skipped: {skipped}  Errors: {errors}")
    print(f"Manifest written to {MANIFEST_PATH}")


if __name__ == "__main__":
    main()
