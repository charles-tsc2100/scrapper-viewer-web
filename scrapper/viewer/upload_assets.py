"""
upload_assets.py — Mirror local output/<source>/ assets to Cloudflare R2.

Usage:
  python viewer/upload_assets.py --source elmes [--dry-run] [--workers 8]

After a successful run, writes viewer/asset_manifest.json mapping
  local relative path  →  public R2 URL
The seed script reads this manifest to rewrite paths before inserting to Supabase.
"""

import os
import sys
import json
import argparse
import mimetypes
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv
from tqdm import tqdm

HERE = Path(__file__).parent
ROOT = HERE.parent

load_dotenv(HERE / ".env")

R2_ENDPOINT  = os.environ["R2_ACCOUNT_ENDPOINT"]
R2_KEY_ID    = os.environ["R2_ACCESS_KEY_ID"]
R2_SECRET    = os.environ["R2_SECRET_ACCESS_KEY"]
R2_BUCKET    = os.environ["R2_BUCKET"]
R2_PUBLIC    = os.environ["R2_PUBLIC_BASE"].rstrip("/")

MANIFEST_PATH = HERE / "asset_manifest.json"

SOURCES = {
    "elmes":      ROOT / "output" / "elmes",
    "sugatsune":  ROOT / "output" / "sugatsune",
    "simonswerk": ROOT / "output" / "simonswerk",
}


def make_client():
    return boto3.client(
        "s3",
        endpoint_url=R2_ENDPOINT,
        aws_access_key_id=R2_KEY_ID,
        aws_secret_access_key=R2_SECRET,
        region_name="auto",
    )


def already_uploaded(client, key: str, local_size: int) -> bool:
    try:
        head = client.head_object(Bucket=R2_BUCKET, Key=key)
        return head["ContentLength"] == local_size
    except ClientError as e:
        if e.response["Error"]["Code"] in ("404", "NoSuchKey"):
            return False
        raise


def upload_file(client, local_path: Path, key: str, dry_run: bool) -> tuple[str, str]:
    """Upload one file; return (local_rel_path, public_url)."""
    mime, _ = mimetypes.guess_type(str(local_path))
    mime = mime or "application/octet-stream"
    if not dry_run:
        client.upload_file(
            str(local_path),
            R2_BUCKET,
            key,
            ExtraArgs={"ContentType": mime},
        )
    public_url = f"{R2_PUBLIC}/{key}"
    return str(local_path), public_url


def collect_files(source_dir: Path, prefix: str) -> list[tuple[Path, str]]:
    """Walk source_dir and return (local_path, r2_key) pairs for uploadable files."""
    skip_extensions = {".xlsx", ".json"}
    pairs = []
    for p in source_dir.rglob("*"):
        if p.is_file() and p.suffix.lower() not in skip_extensions:
            rel = p.relative_to(source_dir)
            key = f"{prefix}/{rel}".replace("\\", "/")
            pairs.append((p, key))
    return pairs


def main():
    ap = argparse.ArgumentParser(description="Upload assets to Cloudflare R2")
    ap.add_argument("--source", required=True, choices=list(SOURCES), help="Which brand to upload")
    ap.add_argument("--dry-run", action="store_true", help="Print plan without uploading")
    ap.add_argument("--workers", type=int, default=8, help="Concurrent upload threads")
    args = ap.parse_args()

    source_dir = SOURCES[args.source]
    if not source_dir.exists():
        print(f"ERROR: source directory not found: {source_dir}", file=sys.stderr)
        sys.exit(1)

    pairs = collect_files(source_dir, args.source)
    total_bytes = sum(p.stat().st_size for p, _ in pairs)
    print(f"Found {len(pairs):,} files  ({total_bytes / 1_048_576:.1f} MB)  in {source_dir}")

    if args.dry_run:
        for p, k in pairs[:20]:
            print(f"  {k}  ({p.stat().st_size:,} B)")
        if len(pairs) > 20:
            print(f"  ... and {len(pairs)-20} more")
        print("Dry run complete — nothing uploaded.")
        return

    client = make_client()

    # Load existing manifest so re-runs are additive
    manifest: dict[str, str] = {}
    if MANIFEST_PATH.exists():
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

    skipped = uploaded = errors = 0
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {}
        for local_path, key in pairs:
            size = local_path.stat().st_size
            if already_uploaded(client, key, size):
                manifest[str(local_path.relative_to(ROOT))] = f"{R2_PUBLIC}/{key}"
                skipped += 1
                continue
            futures[pool.submit(upload_file, client, local_path, key, False)] = local_path

        with tqdm(total=len(futures), unit="file", desc="Uploading") as bar:
            for fut in as_completed(futures):
                try:
                    local_str, pub_url = fut.result()
                    rel = str(Path(local_str).relative_to(ROOT))
                    manifest[rel] = pub_url
                    uploaded += 1
                except Exception as exc:
                    print(f"\nERROR uploading {futures[fut]}: {exc}", file=sys.stderr)
                    errors += 1
                finally:
                    bar.update(1)

    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nDone. Uploaded: {uploaded}  Skipped: {skipped}  Errors: {errors}")
    print(f"Manifest written to {MANIFEST_PATH}")


if __name__ == "__main__":
    main()
