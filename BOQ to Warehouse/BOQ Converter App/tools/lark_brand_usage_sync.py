"""
Syncs BOQ brand/model usage aggregates from Supabase → Lark Base "CRM v1.3".

Reads:
  %APPDATA%/BOQConverter/lark_config.json  (app_id, app_secret, brand_usage_base_app_token)
  %APPDATA%/BOQConverter/db_config.json    (url, anon_key)

Called automatically from db_logger._upload() after each BOQ conversion, or run
directly for a manual refresh / dry-run:

    python -m tools.lark_brand_usage_sync
    python -m tools.lark_brand_usage_sync --dry-run

Config keys used (lark_config.json):
  Required:  app_id, app_secret, base_app_token (or brand_usage_base_app_token)
  Optional:  brand_usage_base_app_token  (defaults to base_app_token if absent)
             brand_usage_table_name      (defaults to "BOQ Brand Usage")
"""
import argparse
import json
import logging
import os
import time
from datetime import datetime, timezone

import requests

APPDATA = os.environ.get("APPDATA", os.path.expanduser("~"))
CONFIG_DIR = os.path.join(APPDATA, "BOQConverter")
LARK_CONFIG_FILE = os.path.join(CONFIG_DIR, "lark_config.json")
DB_CONFIG_FILE = os.path.join(CONFIG_DIR, "db_config.json")

LARK_HOST = "https://open.larksuite.com"

DEFAULT_TABLE_NAME = "BOQ Brand Usage"

# Lark field names — must match exactly (case-sensitive) what you created in CRM v1.3
FIELD_MAP = {
    "project_name":     "project_name",
    "project_category": "project_category",
    "brand":            "brand",
    "model":            "model",
    "times_specified":  "times_specified",
    "total_qty":        "total_qty",
    "last_updated":     "last_updated",
}

# Fields that are Single-Select in Lark and need option pre-provisioning
SELECT_FIELDS = {"project_category", "brand"}

log = logging.getLogger("lark_brand_usage_sync")


# ── Config ────────────────────────────────────────────────────────────────────

def _load_configs():
    if not os.path.exists(LARK_CONFIG_FILE):
        raise FileNotFoundError(
            f"Lark config not found: {LARK_CONFIG_FILE}. Run setup_lark_config.bat first.")
    if not os.path.exists(DB_CONFIG_FILE):
        raise FileNotFoundError(
            f"DB config not found: {DB_CONFIG_FILE}. Run setup_lark_config.bat first.")
    with open(LARK_CONFIG_FILE, "r", encoding="utf-8") as f:
        lark_cfg = json.load(f)
    with open(DB_CONFIG_FILE, "r", encoding="utf-8") as f:
        db_cfg = json.load(f)
    return lark_cfg, db_cfg


# ── Lark auth ─────────────────────────────────────────────────────────────────

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


# ── Table discovery ───────────────────────────────────────────────────────────

def _find_table_id(token, app_token, table_name):
    """Find table_id by name in the base — avoids hardcoding internal IDs."""
    page_token = None
    visible = []
    while True:
        params = {"page_size": 100}
        if page_token:
            params["page_token"] = page_token
        r = requests.get(
            f"{LARK_HOST}/open-apis/bitable/v1/apps/{app_token}/tables",
            headers={"Authorization": f"Bearer {token}"},
            params=params,
            timeout=10,
        )
        r.raise_for_status()
        data = r.json()
        if data.get("code") != 0:
            raise RuntimeError(f"Lark list_tables failed: {data}")
        for tbl in data["data"].get("items", []):
            visible.append(tbl.get("name", ""))
            if tbl.get("name") == table_name:
                return tbl["table_id"]
        if not data["data"].get("has_more"):
            break
        page_token = data["data"].get("page_token")
        if not page_token:
            break
    raise RuntimeError(
        f"Table '{table_name}' not found in base {app_token}.\n"
        f"Tables visible to this app: {visible}\n"
        f"If '{table_name}' is missing from the list, the 'BOQ Project Sync' Lark app\n"
        f"lacks permission on it. Fix: in CRM v1.3, remove and re-add the app under\n"
        f"Share → App access with 'Can edit' on the whole base, then retry."
    )


# ── Field management ──────────────────────────────────────────────────────────

def _list_fields(token, app_token, table_id):
    r = requests.get(
        f"{LARK_HOST}/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/fields",
        headers={"Authorization": f"Bearer {token}"},
        timeout=10,
    )
    r.raise_for_status()
    data = r.json()
    if data.get("code") != 0:
        raise RuntimeError(f"Lark list_fields failed: {data}")
    return data["data"]["items"]


def _ensure_select_options(token, app_token, table_id, fields_meta, rows):
    """For each single-select field, add any missing option values before insert."""
    total_added = 0
    for field_key in SELECT_FIELDS:
        lark_field_name = FIELD_MAP[field_key]
        field = next((f for f in fields_meta if f.get("field_name") == lark_field_name), None)
        if not field:
            log.warning("Field '%s' not found in table — skipping option check", lark_field_name)
            continue

        existing_options = (field.get("property") or {}).get("options", []) or []
        existing_names = {o["name"] for o in existing_options if o}
        needed = {str(row[field_key]) for row in rows if row.get(field_key)}
        missing = needed - existing_names
        if not missing:
            continue

        # Preserve existing options (with their IDs) and append new ones
        new_options = [{"name": o} for o in sorted(missing)]
        payload = {
            "field_name": lark_field_name,
            "type": field["type"],
            "property": {"options": existing_options + new_options},
        }
        r = requests.put(
            f"{LARK_HOST}/open-apis/bitable/v1/apps/{app_token}"
            f"/tables/{table_id}/fields/{field['field_id']}",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json=payload,
            timeout=10,
        )
        r.raise_for_status()
        resp = r.json()
        if resp.get("code") not in (0, 1254606):  # 1254606 = DataNotChange (already up-to-date)
            raise RuntimeError(f"Lark patch_field failed for '{lark_field_name}': {resp}")
        log.info("Added %d new option(s) to '%s': %s",
                 len(missing), lark_field_name, sorted(missing))
        total_added += len(missing)
    return total_added


# ── Supabase read ─────────────────────────────────────────────────────────────

def _fetch_supabase_rows(db_cfg):
    url = db_cfg["url"].rstrip("/")
    anon_key = db_cfg["anon_key"]
    r = requests.get(
        f"{url}/rest/v1/v_brand_usage_by_project",
        headers={
            "apikey": anon_key,
            "Authorization": f"Bearer {anon_key}",
            "Prefer": "count=none",
        },
        params={"order": "times_specified.desc", "limit": "10000"},
        timeout=30,
    )
    r.raise_for_status()
    return r.json() or []


# ── Lark record write ─────────────────────────────────────────────────────────

def _list_all_record_ids(token, app_token, table_id):
    ids = []
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
        for rec in data["data"].get("items", []):
            ids.append(rec["record_id"])
        if not data["data"].get("has_more"):
            break
        page_token = data["data"].get("page_token")
        if not page_token:
            break
    return ids


def _batch_delete(token, app_token, table_id, record_ids):
    deleted = 0
    for i in range(0, len(record_ids), 500):
        chunk = record_ids[i:i + 500]
        r = requests.post(
            f"{LARK_HOST}/open-apis/bitable/v1/apps/{app_token}"
            f"/tables/{table_id}/records/batch_delete",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json={"records": chunk},
            timeout=30,
        )
        r.raise_for_status()
        data = r.json()
        if data.get("code") != 0:
            raise RuntimeError(f"Lark batch_delete failed: {data}")
        deleted += len(chunk)
    return deleted


def _batch_create(token, app_token, table_id, rows, now_ms):
    created = 0
    for i in range(0, len(rows), 500):
        chunk = rows[i:i + 500]
        records = []
        for row in chunk:
            records.append({"fields": {
                FIELD_MAP["project_name"]:     row.get("project_name") or "",
                FIELD_MAP["project_category"]: row.get("project_category") or "",
                FIELD_MAP["brand"]:            row.get("brand") or "",
                FIELD_MAP["model"]:            row.get("model") or "",
                FIELD_MAP["times_specified"]:  int(row.get("times_specified") or 0),
                FIELD_MAP["total_qty"]:        float(row.get("total_qty") or 0),
                FIELD_MAP["last_updated"]:     now_ms,
            }})
        r = requests.post(
            f"{LARK_HOST}/open-apis/bitable/v1/apps/{app_token}"
            f"/tables/{table_id}/records/batch_create",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json={"records": records},
            timeout=30,
        )
        r.raise_for_status()
        data = r.json()
        if data.get("code") != 0:
            raise RuntimeError(f"Lark batch_create failed: {data}")
        created += len(chunk)
    return created


# ── Main entry point ──────────────────────────────────────────────────────────

def sync_brand_usage_to_lark(dry_run=False) -> dict:
    """
    Pull brand/model aggregates from Supabase and push to Lark Base.
    Returns {deleted, inserted, options_added, took_ms}.
    Raises on config or API errors.
    """
    t0 = time.time()
    lark_cfg, db_cfg = _load_configs()

    app_token = lark_cfg.get("brand_usage_base_app_token") or lark_cfg["base_app_token"]
    table_name = lark_cfg.get("brand_usage_table_name") or DEFAULT_TABLE_NAME

    token = _lark_token(lark_cfg)
    table_id = _find_table_id(token, app_token, table_name)
    log.info("Resolved '%s' → table_id=%s", table_name, table_id)

    rows = _fetch_supabase_rows(db_cfg)
    log.info("Fetched %d rows from Supabase v_brand_usage_by_project", len(rows))

    if dry_run:
        _dry_run_report(token, app_token, table_id, table_name, rows, t0)
        return {"deleted": 0, "inserted": 0, "options_added": 0,
                "took_ms": int((time.time() - t0) * 1000), "dry_run": True}

    fields_meta = _list_fields(token, app_token, table_id)

    # Validate all mapped field names exist
    missing_fields = [fn for fn in FIELD_MAP.values()
                      if not any(f.get("field_name") == fn for f in fields_meta)]
    if missing_fields:
        raise RuntimeError(
            f"These fields are missing from the Lark table '{table_name}': {missing_fields}. "
            f"Check field names match FIELD_MAP in lark_brand_usage_sync.py.")

    options_added = _ensure_select_options(token, app_token, table_id, fields_meta, rows)

    record_ids = _list_all_record_ids(token, app_token, table_id)
    deleted = _batch_delete(token, app_token, table_id, record_ids) if record_ids else 0
    log.info("Deleted %d existing rows", deleted)

    now_ms = int(datetime.now(tz=timezone.utc).timestamp() * 1000)
    inserted = _batch_create(token, app_token, table_id, rows, now_ms) if rows else 0
    log.info("Inserted %d rows", inserted)

    took_ms = int((time.time() - t0) * 1000)
    log.info("Lark brand usage sync complete in %dms: deleted=%d inserted=%d options_added=%d",
             took_ms, deleted, inserted, options_added)
    return {"deleted": deleted, "inserted": inserted, "options_added": options_added,
            "took_ms": took_ms}


def _dry_run_report(token, app_token, table_id, table_name, rows, t0):
    record_ids = _list_all_record_ids(token, app_token, table_id)
    fields_meta = _list_fields(token, app_token, table_id)

    print(f"\nDRY RUN — no writes will be made")
    print(f"  Table : {table_name} ({table_id})")
    print(f"  Delete: {len(record_ids)} existing row(s)")
    print(f"  Insert: {len(rows)} row(s) from Supabase")

    # Lark field type IDs: 1=Text, 2=Number, 3=Single-Select, 5=DateTime, 99001=Auto-number
    EXPECTED_TYPES = {
        "project_name": (1,),
        "project_category": (3,),
        "brand": (3,),
        "model": (1,),
        "times_specified": (2,),
        "total_qty": (2,),
        "last_updated": (5,),
    }
    print(f"\nField validation:")
    for field_key, lark_fn in FIELD_MAP.items():
        field = next((f for f in fields_meta if f.get("field_name") == lark_fn), None)
        if not field:
            print(f"  MISSING  {lark_fn}")
            continue
        ftype = field.get("type")
        expected = EXPECTED_TYPES.get(field_key, ())
        type_ok = not expected or ftype in expected
        status = "OK    " if type_ok else f"WRONG TYPE (got {ftype}, want {expected})"
        print(f"  {status}  {lark_fn}")

    print(f"\nSingle-select option check:")
    for field_key in SELECT_FIELDS:
        lark_fn = FIELD_MAP[field_key]
        field = next((f for f in fields_meta if f.get("field_name") == lark_fn), None)
        existing = {o["name"] for o in ((field.get("property") or {}).get("options") or []) if o}
        needed = {str(r[field_key]) for r in rows if r.get(field_key)}
        missing = needed - existing
        print(f"  '{lark_fn}': {len(existing)} existing, {len(missing)} new: "
              f"{sorted(missing)[:10]}{'...' if len(missing) > 10 else ''}")

    if rows:
        print(f"\nSample rows (first 5):")
        for row in rows[:5]:
            print(f"  {row.get('project_name','')!r:30s}  "
                  f"{row.get('brand','')!r:15s}  "
                  f"{row.get('model','')!r:20s}  "
                  f"x{row.get('times_specified',0)}")

    print(f"\nDry run complete in {int((time.time()-t0)*1000)}ms. Run without --dry-run to apply.")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-7s  %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    parser = argparse.ArgumentParser(description="Sync BOQ brand usage → Lark Base CRM v1.3")
    parser.add_argument("--dry-run", action="store_true",
                        help="Preview what would be written without making any changes.")
    args = parser.parse_args()

    try:
        result = sync_brand_usage_to_lark(dry_run=args.dry_run)
        if not args.dry_run:
            print(f"Done. deleted={result['deleted']} inserted={result['inserted']} "
                  f"options_added={result['options_added']} took={result['took_ms']}ms")
    except Exception as exc:
        print(f"ERROR: {exc}")
        raise SystemExit(1)
