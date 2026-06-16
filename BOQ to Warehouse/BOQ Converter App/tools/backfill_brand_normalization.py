"""
One-off backfill: uppercase all brand values in Supabase and clean up Lark CRM.

Steps:
  1. Find all distinct non-canonical brands in conversion_items and PATCH them to upper().
  2. Read all Sale Projects Lark records, re-write any whose Brands chips contain
     non-canonical values (e.g. "Elmes" -> "ELMES").
  3. Prune orphan options from the Brands multi-select field on Sale Projects.

Run once after deploying the normalize_brand() change:
    python -m tools.backfill_brand_normalization
    python -m tools.backfill_brand_normalization --dry-run
"""
import argparse
import json
import logging
import os
import sys

import requests

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger("backfill_brand")

APPDATA = os.environ.get("APPDATA", os.path.expanduser("~"))
CONFIG_DIR = os.path.join(APPDATA, "BOQConverter")
DB_CONFIG_FILE = os.path.join(CONFIG_DIR, "db_config.json")
LARK_CONFIG_FILE = os.path.join(CONFIG_DIR, "lark_config.json")
LARK_HOST = "https://open.larksuite.com"


def _normalize(value):
    s = (value or "").strip()
    return s.upper() if s else ""


def _load_configs():
    with open(DB_CONFIG_FILE, encoding="utf-8") as f:
        db_cfg = json.load(f)
    with open(LARK_CONFIG_FILE, encoding="utf-8") as f:
        lark_cfg = json.load(f)
    return db_cfg, lark_cfg


def _lark_token(lark_cfg):
    r = requests.post(
        f"{LARK_HOST}/open-apis/auth/v3/tenant_access_token/internal",
        json={"app_id": lark_cfg["app_id"], "app_secret": lark_cfg["app_secret"]},
        timeout=10,
    )
    r.raise_for_status()
    data = r.json()
    if data.get("code") != 0:
        raise RuntimeError(f"Lark auth failed: {data}")
    return data["tenant_access_token"]


# ── 1. Supabase backfill ──────────────────────────────────────────────────────

def backfill_supabase(db_cfg, dry_run):
    url = db_cfg["url"].rstrip("/")
    # Use service_role_key for read+write access
    key = db_cfg.get("service_role_key") or db_cfg["anon_key"]
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal",
    }

    # Fetch all distinct brand values
    r = requests.get(
        f"{url}/rest/v1/conversion_items",
        headers={**headers, "Prefer": "count=none"},
        params={"select": "brand", "limit": "200000"},
        timeout=30,
    )
    r.raise_for_status()
    rows = r.json()
    distinct = {(row.get("brand") or "").strip() for row in rows}
    distinct.discard("")

    non_canonical = {b for b in distinct if b != b.upper()}
    if not non_canonical:
        log.info("Supabase: all brands already canonical — nothing to do")
        return

    log.info("Supabase: found %d non-canonical brand(s): %s", len(non_canonical), sorted(non_canonical))
    for brand in sorted(non_canonical):
        canonical = brand.upper()
        log.info("  PATCH brand=%r -> %r", brand, canonical)
        if not dry_run:
            r = requests.patch(
                f"{url}/rest/v1/conversion_items",
                headers=headers,
                params={"brand": f"eq.{brand}"},
                json={"brand": canonical},
                timeout=30,
            )
            r.raise_for_status()
    log.info("Supabase backfill %s", "skipped (dry-run)" if dry_run else "done")


# ── 2 & 3. Lark Sale Projects cleanup ────────────────────────────────────────

def _extract_brand_list(field_val):
    """Extract list of brand strings from a Lark multi/single-select field value."""
    if not field_val:
        return []
    if isinstance(field_val, str):
        return [field_val.strip()] if field_val.strip() else []
    if isinstance(field_val, list):
        names = []
        for item in field_val:
            if isinstance(item, str):
                names.append(item.strip())
            elif isinstance(item, dict):
                names.append((item.get("name") or item.get("text") or item.get("value") or "").strip())
        return [n for n in names if n]
    if isinstance(field_val, dict):
        name = (field_val.get("name") or field_val.get("text") or field_val.get("value") or "").strip()
        return [name] if name else []
    return []


def cleanup_lark_sale_projects(lark_cfg, dry_run):
    token = _lark_token(lark_cfg)
    app_token = lark_cfg["base_app_token"]
    table_id = lark_cfg.get("table_id")
    if not table_id:
        log.error("lark_config.json missing 'table_id' (Sale Projects) — skipping Lark step")
        return

    field_map = lark_cfg.get("field_map") or {}
    brands_field = field_map.get("brands", "Brands")

    # List all Sale Projects records
    all_records = []
    page_token = None
    while True:
        params = {"page_size": 500}
        if page_token:
            params["page_token"] = page_token
        r = requests.get(
            f"{LARK_HOST}/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records",
            headers={"Authorization": f"Bearer {token}"},
            params=params,
            timeout=20,
        )
        r.raise_for_status()
        data = r.json()
        if data.get("code") != 0:
            raise RuntimeError(f"Lark list_records failed: {data}")
        all_records.extend(data["data"].get("items", []))
        if not data["data"].get("has_more"):
            break
        page_token = data["data"].get("page_token")
        if not page_token:
            break
    log.info("Lark Sale Projects: loaded %d records", len(all_records))

    # Re-write records whose brand chips contain non-canonical values
    all_in_use = set()
    updated = 0
    for rec in all_records:
        rec_id = rec["record_id"]
        fields = rec.get("fields", {})
        raw_brands = _extract_brand_list(fields.get(brands_field))
        if not raw_brands:
            continue
        canonical = sorted({_normalize(b) for b in raw_brands if b})
        all_in_use.update(canonical)
        if canonical == sorted(raw_brands):
            continue  # already canonical
        log.info("  Record %s: brands %r -> %r", rec_id, raw_brands, canonical)
        if not dry_run:
            r = requests.put(
                f"{LARK_HOST}/open-apis/bitable/v1/apps/{app_token}"
                f"/tables/{table_id}/records/{rec_id}",
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                json={"fields": {brands_field: canonical}},
                timeout=10,
            )
            r.raise_for_status()
            resp = r.json()
            if resp.get("code") not in (0, 1254606):
                raise RuntimeError(f"Lark patch_record failed: {resp}")
        updated += 1
    log.info("Lark Sale Projects: %d record(s) %s",
             updated, "would be updated (dry-run)" if dry_run else "updated")

    # Prune orphan options from the Brands field
    r = requests.get(
        f"{LARK_HOST}/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/fields",
        headers={"Authorization": f"Bearer {token}"},
        timeout=10,
    )
    r.raise_for_status()
    fields_meta = r.json()["data"]["items"]
    brands_meta = next((f for f in fields_meta if f.get("field_name") == brands_field), None)
    if not brands_meta:
        log.warning("Brands field '%s' not found — skipping option pruning", brands_field)
        return

    existing_options = (brands_meta.get("property") or {}).get("options", []) or []
    kept = [o for o in existing_options if o.get("name") in all_in_use]
    removed = [o["name"] for o in existing_options if o.get("name") not in all_in_use]
    if not removed:
        log.info("Lark Sale Projects Brands field: no orphan options to remove")
        return

    log.info("Lark Sale Projects: removing %d orphan option(s): %s", len(removed), sorted(removed))
    if not dry_run:
        payload = {
            "field_name": brands_field,
            "type": brands_meta["type"],
            "property": {"options": kept},
        }
        r = requests.put(
            f"{LARK_HOST}/open-apis/bitable/v1/apps/{app_token}"
            f"/tables/{table_id}/fields/{brands_meta['field_id']}",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json=payload,
            timeout=10,
        )
        r.raise_for_status()
        resp = r.json()
        if resp.get("code") not in (0, 1254606):
            raise RuntimeError(f"Lark prune Brands field failed: {resp}")
    log.info("Lark Sale Projects Brands field options pruned %s",
             "(dry-run — no changes made)" if dry_run else "successfully")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would change without writing anything")
    args = parser.parse_args()

    if args.dry_run:
        log.info("=== DRY RUN — no writes will be made ===")

    db_cfg, lark_cfg = _load_configs()

    log.info("--- Step 1: Supabase brand backfill ---")
    backfill_supabase(db_cfg, args.dry_run)

    log.info("--- Step 2 & 3: Lark Sale Projects cleanup ---")
    cleanup_lark_sale_projects(lark_cfg, args.dry_run)

    log.info("=== Backfill complete%s ===", " (dry-run)" if args.dry_run else "")


if __name__ == "__main__":
    main()
