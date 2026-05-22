"""
Lark Base → Supabase project sync.

Pulls all rows from a Lark Bitable table (the project tracker) and upserts them
into the Supabase `projects` table. Intended to run on a schedule (e.g. Windows
Task Scheduler every 10 minutes).

Configuration: %APPDATA%/BOQConverter/lark_config.json
{
  "app_id":         "cli_xxxxx",          // Lark custom-app App ID
  "app_secret":     "xxxxxxxx",           // Lark custom-app App Secret
  "base_app_token": "bascnXXXXXXXXXX",    // Bitable app token (from base URL)
  "table_id":       "tblXXXXXXXX",        // Project tracker table id
  "field_map": {                          // map Lark field NAMES → projects columns
    "name":     "Project Name",
    "category": "Category",
    "status":   "Status"
  }
}

Supabase creds are read from the same db_config.json the desktop app uses, BUT
this script needs the service_role key (not the anon key) to write to projects.
Add a "service_role_key" field to db_config.json (kept on the sync host only —
do NOT ship service_role to end users):
{
  "url":              "https://xxx.supabase.co",
  "anon_key":         "eyJ...",
  "service_role_key": "eyJ..."
}

Usage:
    python tools/lark_sync.py
    python tools/lark_sync.py --dry-run
"""
import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone

import requests

APPDATA = os.environ.get("APPDATA", os.path.expanduser("~"))
CONFIG_DIR = os.path.join(APPDATA, "BOQConverter")
DB_CONFIG = os.path.join(CONFIG_DIR, "db_config.json")
LARK_CONFIG = os.path.join(CONFIG_DIR, "lark_config.json")

LARK_HOST = "https://open.larksuite.com"  # use https://open.feishu.cn for Feishu

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("lark_sync")


def _load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _lark_tenant_token(app_id, app_secret):
    r = requests.post(
        f"{LARK_HOST}/open-apis/auth/v3/tenant_access_token/internal",
        json={"app_id": app_id, "app_secret": app_secret},
        timeout=10,
    )
    r.raise_for_status()
    data = r.json()
    if data.get("code") != 0:
        raise RuntimeError(f"Lark auth failed: {data}")
    return data["tenant_access_token"]


def _lark_list_records(token, app_token, table_id):
    """Yield all records, paginating through Lark's API."""
    page_token = None
    while True:
        params = {"page_size": 500}
        if page_token:
            params["page_token"] = page_token
        r = requests.get(
            f"{LARK_HOST}/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records",
            headers={"Authorization": f"Bearer {token}"},
            params=params,
            timeout=15,
        )
        r.raise_for_status()
        data = r.json()
        if data.get("code") != 0:
            raise RuntimeError(f"Lark list_records failed: {data}")
        for rec in data["data"].get("items", []):
            yield rec
        if not data["data"].get("has_more"):
            return
        page_token = data["data"].get("page_token")
        if not page_token:
            return


def _extract_field(fields, field_name):
    """Lark fields come back as either a plain string or a list of cell objects."""
    val = fields.get(field_name)
    if val is None:
        return ""
    if isinstance(val, str):
        return val.strip()
    if isinstance(val, list):
        parts = []
        for cell in val:
            if isinstance(cell, dict):
                parts.append(cell.get("text") or cell.get("name") or "")
            else:
                parts.append(str(cell))
        return " ".join(p for p in parts if p).strip()
    if isinstance(val, dict):
        return (val.get("text") or val.get("name") or "").strip()
    return str(val).strip()


def _to_row(record, field_map, app_token, table_id):
    fields = record.get("fields", {})
    record_id = record["record_id"]
    name = _extract_field(fields, field_map.get("name", "Project Name"))
    if not name:
        return None  # skip blank rows
    last_modified = record.get("last_modified_time")  # ms epoch
    updated_at = None
    if last_modified:
        try:
            updated_at = datetime.fromtimestamp(
                last_modified / 1000, tz=timezone.utc
            ).isoformat()
        except Exception:
            updated_at = None
    return {
        "id": record_id,
        "name": name,
        "category": _extract_field(fields, field_map.get("category", "Category")),
        "status": _extract_field(fields, field_map.get("status", "Status")),
        "lark_url": (
            f"https://base.larksuite.com/base/{app_token}"
            f"?table={table_id}&view=&record={record_id}"
        ),
        "updated_at": updated_at,
        "synced_at": datetime.now(tz=timezone.utc).isoformat(),
    }


def _supabase_upsert(url, service_key, rows):
    """Upsert into projects (on id conflict)."""
    if not rows:
        return 0
    headers = {
        "apikey": service_key,
        "Authorization": f"Bearer {service_key}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates,return=minimal",
    }
    r = requests.post(
        f"{url}/rest/v1/projects?on_conflict=id",
        headers=headers,
        json=rows,
        timeout=30,
    )
    if not r.ok:
        log.error("Supabase upsert failed: %s %s", r.status_code, r.text[:500])
        r.raise_for_status()
    return len(rows)


def _supabase_prune(url, service_key, live_ids):
    """Delete projects rows whose id is no longer in Lark (project removed)."""
    headers = {
        "apikey": service_key,
        "Authorization": f"Bearer {service_key}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal",
    }
    # PostgREST: delete where id not in (...)
    if not live_ids:
        return 0
    # PostgREST 'in' filter: id=not.in.(a,b,c) — quote values
    quoted = ",".join(f'"{i}"' for i in live_ids)
    r = requests.delete(
        f"{url}/rest/v1/projects",
        headers=headers,
        params={"id": f"not.in.({quoted})"},
        timeout=30,
    )
    if not r.ok:
        log.warning("Supabase prune failed: %s %s", r.status_code, r.text[:300])
        return 0
    return 1


def _load_config_from_env():
    """Build lark_cfg and db_cfg dicts from environment variables.

    GitHub Actions (and other CI) injects secrets as env vars instead of
    writing config files. Returns (lark_cfg, db_cfg) or (None, None) if any
    required variable is missing.

    Required env vars:
        LARK_APP_ID, LARK_APP_SECRET, LARK_BASE_APP_TOKEN, LARK_TABLE_ID
        SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY
    Optional:
        LARK_FIELD_NAME (default "Project"), LARK_FIELD_CATEGORY (default "Project Type"),
        LARK_FIELD_STATUS (default "Status")
    """
    required = ["LARK_APP_ID", "LARK_APP_SECRET", "LARK_BASE_APP_TOKEN",
                "LARK_TABLE_ID", "SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY"]
    missing = [k for k in required if not os.environ.get(k)]
    if missing:
        return None, None

    lark_cfg = {
        "app_id":         os.environ["LARK_APP_ID"],
        "app_secret":     os.environ["LARK_APP_SECRET"],
        "base_app_token": os.environ["LARK_BASE_APP_TOKEN"],
        "table_id":       os.environ["LARK_TABLE_ID"],
        "field_map": {
            "name":     os.environ.get("LARK_FIELD_NAME",     "Project"),
            "category": os.environ.get("LARK_FIELD_CATEGORY", "Project Type"),
            "status":   os.environ.get("LARK_FIELD_STATUS",   "Status"),
        },
    }
    db_cfg = {
        "url":              os.environ["SUPABASE_URL"],
        "service_role_key": os.environ["SUPABASE_SERVICE_ROLE_KEY"],
    }
    return lark_cfg, db_cfg


def main():
    parser = argparse.ArgumentParser(description="Sync Lark Base projects → Supabase.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Fetch from Lark and print, but do not write to Supabase.")
    parser.add_argument("--no-prune", action="store_true",
                        help="Do not delete Supabase rows for projects removed from Lark.")
    args = parser.parse_args()

    # Try env vars first (cloud/CI), fall back to config files (local machine).
    lark_cfg, db_cfg = _load_config_from_env()
    if lark_cfg is None:
        if not os.path.exists(LARK_CONFIG):
            log.error("Missing %s. See docstring at top of this file.", LARK_CONFIG)
            sys.exit(2)
        if not os.path.exists(DB_CONFIG):
            log.error("Missing %s. Create it with url + service_role_key.", DB_CONFIG)
            sys.exit(2)
        lark_cfg = _load_json(LARK_CONFIG)
        db_cfg = _load_json(DB_CONFIG)
        log.info("Loaded config from files.")
    else:
        log.info("Loaded config from environment variables.")

    url = db_cfg.get("url", "").rstrip("/")
    # Accept either "service_role_key" or "service_key" for backwards compat.
    service_key = db_cfg.get("service_role_key") or db_cfg.get("service_key")
    if not args.dry_run and (not url or not service_key):
        log.error("db_config.json needs both 'url' and 'service_role_key' for syncing.")
        sys.exit(2)

    field_map = lark_cfg.get("field_map", {})
    app_token = lark_cfg["base_app_token"]
    table_id = lark_cfg["table_id"]

    t0 = time.time()
    token = _lark_tenant_token(lark_cfg["app_id"], lark_cfg["app_secret"])
    log.info("Got Lark tenant token.")

    rows = []
    for rec in _lark_list_records(token, app_token, table_id):
        row = _to_row(rec, field_map, app_token, table_id)
        if row:
            rows.append(row)
    log.info("Fetched %d project rows from Lark in %.1fs.", len(rows), time.time() - t0)

    if args.dry_run:
        for r in rows[:10]:
            log.info("  %s | %s | %s", r["name"], r["category"], r["status"])
        if len(rows) > 10:
            log.info("  ... (+%d more)", len(rows) - 10)
        return

    n = _supabase_upsert(url, service_key, rows)
    log.info("Upserted %d rows.", n)

    if not args.no_prune:
        _supabase_prune(url, service_key, [r["id"] for r in rows])
        log.info("Pruned removed projects.")


if __name__ == "__main__":
    main()
