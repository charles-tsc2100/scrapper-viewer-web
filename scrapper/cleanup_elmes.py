"""
cleanup_elmes.py — Wipe all ELMES/Art Union data for a clean re-scrape.

  1. Delete all artunion rows from Supabase products table
  2. Delete all ELMES assets from Cloudinary (prefix: elmes/)
  3. Strip output/elmes/ entries from asset_manifest.json
  4. Delete local output/elmes/ directory
"""

import os
import sys
import json
import shutil
from pathlib import Path

from dotenv import load_dotenv
from supabase import create_client
import cloudinary
import cloudinary.api

HERE = Path(__file__).parent
load_dotenv(HERE / "viewer" / ".env")

cloudinary.config(
    cloud_name=os.environ["CLOUDINARY_CLOUD_NAME"],
    api_key=os.environ["CLOUDINARY_API_KEY"],
    api_secret=os.environ["CLOUDINARY_API_SECRET"],
    secure=True,
)

client = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])

# ── 1. Delete Supabase rows ────────────────────────────────────────────────────
print("Step 1: Deleting artunion rows from Supabase...")
resp = client.table("products").select("id", count="exact").eq("source", "artunion").execute()
count = resp.count or 0
print(f"  Found {count} artunion rows")
if count > 0:
    client.table("products").delete().eq("source", "artunion").execute()
    print(f"  Deleted {count} rows")
else:
    print("  Nothing to delete")

# ── 2. Delete Cloudinary assets ────────────────────────────────────────────────
print("\nStep 2: Deleting ELMES assets from Cloudinary (prefix: elmes/)...")
deleted_total = 0
while True:
    try:
        result = cloudinary.api.delete_resources_by_prefix(
            "elmes",
            resource_type="image",
            invalidate=True,
        )
        deleted = result.get("deleted", {})
        batch = len(deleted)
        deleted_total += batch
        print(f"  Deleted batch of {batch} (total: {deleted_total})")
        if batch == 0:
            break
        # Keep looping until nothing left (API returns up to 1000 per call)
        if batch < 1000:
            break
    except Exception as exc:
        print(f"  WARNING: {exc}", file=sys.stderr)
        break

# Delete raw (non-image) resources too (e.g. PDFs uploaded as raw type)
try:
    result = cloudinary.api.delete_resources_by_prefix(
        "elmes",
        resource_type="raw",
        invalidate=True,
    )
    raw_deleted = len(result.get("deleted", {}))
    if raw_deleted:
        print(f"  Deleted {raw_deleted} raw resources")
except Exception:
    pass

# Delete the folder itself
try:
    cloudinary.api.delete_folder("elmes")
    print("  Deleted Cloudinary folder 'elmes'")
except Exception as exc:
    print(f"  Note: folder delete: {exc}")

print(f"  Total Cloudinary assets deleted: {deleted_total}")

# ── 3. Strip elmes entries from asset_manifest.json ───────────────────────────
print("\nStep 3: Stripping ELMES entries from asset_manifest.json...")
manifest_path = HERE / "viewer" / "asset_manifest.json"
if manifest_path.exists():
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    before = len(manifest)
    manifest = {k: v for k, v in manifest.items() if not k.replace("\\", "/").startswith("output/elmes/")}
    after = len(manifest)
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"  Removed {before - after} entries ({after} remaining)")
else:
    print("  asset_manifest.json not found — skipping")

# ── 4. Delete local output/elmes/ directory ───────────────────────────────────
print("\nStep 4: Deleting local output/elmes/ directory...")
elmes_dir = HERE / "output" / "elmes"
if elmes_dir.exists():
    shutil.rmtree(elmes_dir)
    print(f"  Deleted {elmes_dir}")
else:
    print("  Directory not found — skipping")

print("\nClean-up complete. Ready for fresh re-scrape.")
print("Next:")
print("  python scrape_elmes.py --cid 4 5 6 9 --delay 0.5 --workers 6")
