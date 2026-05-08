"""
cleanup_sugatsune.py — Wipe all Sugatsune data for a clean re-scrape.

  1. Delete all sugatsune rows from Supabase products table
  2. Delete all Sugatsune assets from Cloudinary (prefix: sugatsune/)
  3. Strip output/sugatsune/ entries from asset_manifest.json
  4. Delete local output/sugatsune/ directory
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
print("Step 1: Deleting sugatsune rows from Supabase...")
resp = client.table("products").select("id", count="exact").eq("source", "sugatsune").execute()
count = resp.count or 0
print(f"  Found {count} sugatsune rows")
if count > 0:
    client.table("products").delete().eq("source", "sugatsune").execute()
    print(f"  Deleted {count} rows")
else:
    print("  Nothing to delete")

# ── 2. Delete Cloudinary assets ────────────────────────────────────────────────
print("\nStep 2: Deleting Sugatsune assets from Cloudinary (prefix: sugatsune/)...")
deleted_total = 0
while True:
    try:
        result = cloudinary.api.delete_resources_by_prefix(
            "sugatsune",
            resource_type="image",
            invalidate=True,
        )
        deleted = result.get("deleted", {})
        batch = len(deleted)
        deleted_total += batch
        print(f"  Deleted batch of {batch} (total: {deleted_total})")
        if batch < 1000:
            break
    except Exception as exc:
        print(f"  WARNING: {exc}", file=sys.stderr)
        break

try:
    result = cloudinary.api.delete_resources_by_prefix(
        "sugatsune",
        resource_type="raw",
        invalidate=True,
    )
    raw_deleted = len(result.get("deleted", {}))
    if raw_deleted:
        print(f"  Deleted {raw_deleted} raw resources")
except Exception:
    pass

try:
    cloudinary.api.delete_folder("sugatsune")
    print("  Deleted Cloudinary folder 'sugatsune'")
except Exception as exc:
    print(f"  Note: folder delete: {exc}")

print(f"  Total Cloudinary assets deleted: {deleted_total}")

# ── 3. Strip sugatsune entries from asset_manifest.json ───────────────────────
print("\nStep 3: Stripping Sugatsune entries from asset_manifest.json...")
manifest_path = HERE / "viewer" / "asset_manifest.json"
if manifest_path.exists():
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    before = len(manifest)
    manifest = {k: v for k, v in manifest.items() if not k.replace("\\", "/").startswith("output/sugatsune/")}
    after = len(manifest)
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"  Removed {before - after} entries ({after} remaining)")
else:
    print("  asset_manifest.json not found — skipping")

# ── 4. Delete local output/sugatsune/ directory ───────────────────────────────
print("\nStep 4: Deleting local output/sugatsune/ directory...")
sugatsune_dir = HERE / "output" / "sugatsune"
if sugatsune_dir.exists():
    shutil.rmtree(sugatsune_dir)
    print(f"  Deleted {sugatsune_dir}")
else:
    print("  Directory not found — skipping")

print("\nClean-up complete. Ready for fresh re-scrape.")
print("Next:")
print("  python scrape_sugatsune.py --no-prompt --delay 0.6 --workers 3")
