"""
BOQ Conversion Logger — writes every successful conversion to Supabase.

Config file: %APPDATA%/BOQConverter/db_config.json
  { "url": "https://xxx.supabase.co", "anon_key": "eyJ..." }

If the config file is absent the logger is silently disabled (app works normally).
Failed uploads are queued to pending_uploads.jsonl and flushed on the next run.

Also exposes fetch_projects() so the app can populate the project picker from
the `projects` table (mirrored from Lark Base by tools/lark_sync.py).
"""
import os
import json
import uuid
import socket
import threading
import logging
from datetime import datetime

logger = logging.getLogger("boq_converter")

# Updated by _upload() after each Lark brand-usage sync. Read by app.py to show status.
_lark_brand_sync_status: dict = {"ok": None, "time": None, "error": None}

APPDATA = os.environ.get("APPDATA", os.path.expanduser("~"))
CONFIG_DIR = os.path.join(APPDATA, "BOQConverter")
DB_CONFIG_FILE = os.path.join(CONFIG_DIR, "db_config.json")
LARK_CONFIG_FILE = os.path.join(CONFIG_DIR, "lark_config.json")
PENDING_FILE = os.path.join(CONFIG_DIR, "pending_uploads.jsonl")
LARK_HOST = "https://open.larksuite.com"


def _load_db_config():
    if not os.path.exists(DB_CONFIG_FILE):
        return None
    try:
        with open(DB_CONFIG_FILE, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        if cfg.get("url") and cfg.get("anon_key"):
            return cfg
    except Exception:
        pass
    return None


def _headers(anon_key, prefer="return=minimal"):
    return {
        "apikey": anon_key,
        "Authorization": f"Bearer {anon_key}",
        "Content-Type": "application/json",
        "Prefer": prefer,
    }


def _post(url, anon_key, endpoint, payload):
    import requests as _requests
    resp = _requests.post(
        f"{url}/rest/v1/{endpoint}",
        headers=_headers(anon_key),
        json=payload,
        timeout=10,
    )
    resp.raise_for_status()


def _patch(url, anon_key, endpoint, payload, params):
    """PATCH rows matching the given PostgREST filter params."""
    import requests as _requests
    resp = _requests.patch(
        f"{url}/rest/v1/{endpoint}",
        headers=_headers(anon_key),
        params=params,
        json=payload,
        timeout=10,
    )
    resp.raise_for_status()


def _get(url, anon_key, endpoint, params):
    import requests as _requests
    resp = _requests.get(
        f"{url}/rest/v1/{endpoint}",
        headers=_headers(anon_key, prefer="count=none"),
        params=params,
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


def _build_record(project_name, project_category, project_id, categories, source_files):
    conversion_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat() + "Z"

    total_door_types = sum(len(c.door_types) for c in categories)
    total_line_items = sum(
        len(dt.products) for c in categories for dt in c.door_types
    )
    total_quantity = sum(
        float(dp.quantity) for c in categories for dt in c.door_types for dp in dt.products
    )

    conversion = {
        "id": conversion_id,
        "created_at": now,
        "project_name": project_name or "",
        "project_category": project_category or "",
        "project_id": project_id or None,
        "machine_name": socket.gethostname(),
        "source_files": [os.path.basename(f) for f in source_files],
        "total_door_types": total_door_types,
        "total_line_items": total_line_items,
        "total_quantity": total_quantity,
        "is_latest": True,
    }

    items = []
    for cat in categories:
        for dt in cat.door_types:
            for dp in dt.products:
                items.append({
                    "conversion_id": conversion_id,
                    "category": cat.name,
                    "door_code": dt.code,
                    "room_name": dt.room_name or "",
                    "brand": dp.product.brand or "",
                    "model": dp.product.model or "",
                    "description": dp.product.description or "",
                    "quantity": float(dp.quantity),
                    "is_option": bool(dp.product.is_option),
                    "source_sheet": dt.source_sheet or "",
                })

    return conversion, items


def _save_pending(record):
    os.makedirs(CONFIG_DIR, exist_ok=True)
    try:
        with open(PENDING_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception as e:
        logger.warning("db_logger: could not save pending record: %s", e)


def _flush_pending(url, anon_key):
    if not os.path.exists(PENDING_FILE):
        return
    try:
        with open(PENDING_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()
        if not lines:
            return

        remaining = []
        flushed = 0
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
                conv = record["conversion"]
                _supersede_prior(url, anon_key,
                                 conv.get("project_name", ""),
                                 conv.get("project_category", ""),
                                 conv["id"])
                _post(url, anon_key, "conversions", [conv])
                if record.get("items"):
                    _post(url, anon_key, "conversion_items", record["items"])
                flushed += 1
            except Exception:
                remaining.append(line)

        with open(PENDING_FILE, "w", encoding="utf-8") as f:
            f.write("\n".join(remaining) + ("\n" if remaining else ""))

        if flushed:
            logger.info("db_logger: flushed %d pending record(s)", flushed)
    except Exception as e:
        logger.warning("db_logger: pending flush failed: %s", e)


def _supersede_prior(url, anon_key, project_name, project_category, new_id):
    """Flag prior conversions for the same (project_name, project_category) as not-latest.

    A project is considered "the same" iff both name AND category match exactly.
    Empty project_name is treated as 'untracked' and never superseded.
    """
    if not project_name:
        return
    now = datetime.utcnow().isoformat() + "Z"
    params = {
        "project_name": f"eq.{project_name}",
        "project_category": f"eq.{project_category or ''}",
        "is_latest": "eq.true",
        "id": f"neq.{new_id}",
    }
    _patch(url, anon_key, "conversions",
           {"is_latest": False, "superseded_at": now},
           params)


def _upload(url, anon_key, conversion, items):
    try:
        _flush_pending(url, anon_key)
        _supersede_prior(url, anon_key,
                         conversion.get("project_name", ""),
                         conversion.get("project_category", ""),
                         conversion["id"])
        _post(url, anon_key, "conversions", [conversion])
        if items:
            _post(url, anon_key, "conversion_items", items)
        logger.info(
            "db_logger: logged conversion %s — project '%s' / %s (%d items)",
            conversion["id"][:8],
            conversion["project_name"],
            conversion["project_category"] or "(no category)",
            len(items),
        )
    except Exception as e:
        logger.warning("db_logger: upload failed, queuing locally: %s", e)
        _save_pending({"conversion": conversion, "items": items})
        return  # skip Lark sync if Supabase upload failed (data not yet available)

    # Push updated aggregates to Lark Base CRM v1.3 (non-blocking; never raises)
    _trigger_lark_brand_sync()


def _trigger_lark_brand_sync():
    try:
        from tools.lark_brand_usage_sync import sync_brand_usage_to_lark
        result = sync_brand_usage_to_lark()
        _lark_brand_sync_status.update({
            "ok": True,
            "time": datetime.utcnow().isoformat() + "Z",
            "error": None,
        })
        logger.info("db_logger: lark brand usage sync ok — inserted=%d deleted=%d took=%dms",
                    result.get("inserted", 0), result.get("deleted", 0), result.get("took_ms", 0))
    except Exception as e:
        _lark_brand_sync_status.update({"ok": False, "time": datetime.utcnow().isoformat() + "Z",
                                        "error": str(e)})
        logger.warning("db_logger: lark brand usage sync failed: %s", e)


def log_conversion(project_name, categories, source_files,
                   project_category="", project_id=None):
    """Call this after every successful conversion. Non-blocking, never raises."""
    cfg = _load_db_config()
    if not cfg:
        return  # Not configured — silently skip

    try:
        conversion, items = _build_record(
            project_name, project_category, project_id,
            categories, source_files)
    except Exception as e:
        logger.warning("db_logger: failed to build record: %s", e)
        return

    url = cfg["url"].rstrip("/")
    anon_key = cfg["anon_key"]

    threading.Thread(
        target=_upload,
        args=(url, anon_key, conversion, items),
        daemon=True,
    ).start()


def _load_lark_config():
    if not os.path.exists(LARK_CONFIG_FILE):
        return None
    try:
        with open(LARK_CONFIG_FILE, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        if cfg.get("app_id") and cfg.get("app_secret"):
            return cfg
    except Exception:
        pass
    return None


def _lark_tenant_token(lark_cfg):
    import requests as _requests
    r = _requests.post(
        f"{LARK_HOST}/open-apis/auth/v3/tenant_access_token/internal",
        json={"app_id": lark_cfg["app_id"], "app_secret": lark_cfg["app_secret"]},
        timeout=10,
    )
    r.raise_for_status()
    data = r.json()
    if data.get("code") != 0:
        raise RuntimeError(f"Lark auth failed: {data}")
    return data["tenant_access_token"]


def _lark_patch_record(lark_cfg, token, record_id, fields):
    import requests as _requests
    r = _requests.patch(
        f"{LARK_HOST}/open-apis/bitable/v1/apps/{lark_cfg['base_app_token']}"
        f"/tables/{lark_cfg['table_id']}/records/{record_id}",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={"fields": fields},
        timeout=10,
    )
    r.raise_for_status()
    data = r.json()
    if data.get("code") != 0:
        raise RuntimeError(f"Lark patch failed: {data}")


def _write_back(project_id, lark_record_id, category):
    """Write the new category to both Supabase projects and Lark Base.
    Runs in a background thread — never raises.
    """
    # 1. Update Supabase projects table
    db_cfg = _load_db_config()
    if db_cfg:
        try:
            url = db_cfg["url"].rstrip("/")
            anon_key = db_cfg["anon_key"]
            _patch(url, anon_key, "projects",
                   {"category": category},
                   {"id": f"eq.{project_id}"})
            logger.info("db_logger: wrote category '%s' to Supabase project %s", category, project_id)
        except Exception as e:
            logger.warning("db_logger: Supabase category write-back failed: %s", e)

    # 2. Update Lark Base record
    if not lark_record_id:
        return
    lark_cfg = _load_lark_config()
    if not lark_cfg:
        return
    category_field = lark_cfg.get("field_map", {}).get("category", "Project Type")
    try:
        token = _lark_tenant_token(lark_cfg)
        _lark_patch_record(lark_cfg, token, lark_record_id, {category_field: category})
        logger.info("db_logger: wrote category '%s' to Lark record %s", category, lark_record_id)
    except Exception as e:
        logger.warning("db_logger: Lark category write-back failed: %s", e)


def write_back_category(project_id, lark_record_id, category):
    """Non-blocking: sync a newly entered category back to Supabase + Lark.
    Only called when a Lark project had no Project Type and the user supplied one.
    """
    if not project_id or not category:
        return
    threading.Thread(
        target=_write_back,
        args=(project_id, lark_record_id, category),
        daemon=True,
    ).start()


def fetch_projects(timeout=5):
    """Return [{id, name, category, status, lark_url}, ...] from Supabase, or [] on any error.

    Used by the app to populate the project picker. Safe to call from a background thread.
    """
    cfg = _load_db_config()
    if not cfg:
        return []
    try:
        rows = _get(cfg["url"].rstrip("/"), cfg["anon_key"], "projects", {
            "select": "id,name,category,status,lark_url",
            "order": "name.asc",
            "limit": "5000",
        })
        return rows or []
    except Exception as e:
        logger.info("db_logger: fetch_projects failed: %s", e)
        return []
