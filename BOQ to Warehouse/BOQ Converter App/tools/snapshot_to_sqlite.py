"""
Weekly local backup: copies all Supabase BOQ data to a local SQLite file.

Requires the SERVICE ROLE key (kept only on your machine, never in the .exe).
Add it to %APPDATA%/BOQConverter/db_config.json:
  {
    "url": "https://xxx.supabase.co",
    "anon_key": "eyJ...",
    "service_key": "eyJ..."
  }

Run manually:  python tools/snapshot_to_sqlite.py
Schedule:      see tools/SETUP.md for Windows Task Scheduler instructions
"""
import os
import sys
import json
import sqlite3

try:
    import requests
except ImportError:
    print("Install requests first:  pip install requests")
    sys.exit(1)

APPDATA = os.environ.get("APPDATA", os.path.expanduser("~"))
CONFIG_FILE = os.path.join(APPDATA, "BOQConverter", "db_config.json")

TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
APP_DIR = os.path.dirname(TOOLS_DIR)
ARCHIVE_DIR = os.path.join(APP_DIR, "archive")
SQLITE_FILE = os.path.join(ARCHIVE_DIR, "boq_archive.db")


def load_config():
    if not os.path.exists(CONFIG_FILE):
        print(f"Config not found: {CONFIG_FILE}")
        print("Create it with your Supabase URL, anon_key, and service_key.")
        sys.exit(1)
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    if not cfg.get("url") or not cfg.get("service_key"):
        print("db_config.json must contain 'url' and 'service_key'.")
        sys.exit(1)
    return cfg


def fetch_all(url, service_key, table):
    headers = {
        "apikey": service_key,
        "Authorization": f"Bearer {service_key}",
        "Accept": "application/json",
    }
    rows = []
    offset = 0
    limit = 1000
    while True:
        resp = requests.get(
            f"{url}/rest/v1/{table}",
            headers={**headers, "Range-Unit": "items", "Range": f"{offset}-{offset + limit - 1}"},
            params={"select": "*"},
            timeout=30,
        )
        resp.raise_for_status()
        batch = resp.json()
        rows.extend(batch)
        if len(batch) < limit:
            break
        offset += limit
    return rows


def ensure_tables(conn):
    conn.executescript("""
        create table if not exists conversions (
            id                text    primary key,
            created_at        text,
            project_name      text,
            machine_name      text,
            source_files      text,
            total_door_types  integer,
            total_line_items  integer
        );
        create table if not exists conversion_items (
            id             integer primary key,
            conversion_id  text,
            category       text,
            door_code      text,
            room_name      text,
            brand          text,
            model          text,
            description    text,
            quantity       real,
            is_option      integer,
            source_sheet   text
        );
        create index if not exists idx_items_brand   on conversion_items(brand);
        create index if not exists idx_items_model   on conversion_items(model);
        create index if not exists idx_conv_project  on conversions(project_name);
    """)
    conn.commit()


def upsert_conversions(conn, rows):
    conn.executemany(
        """insert or replace into conversions
           (id, created_at, project_name, machine_name, source_files,
            total_door_types, total_line_items)
           values (?, ?, ?, ?, ?, ?, ?)""",
        [
            (
                r["id"], r.get("created_at"), r.get("project_name", ""),
                r.get("machine_name", ""),
                json.dumps(r.get("source_files", []), ensure_ascii=False),
                r.get("total_door_types", 0),
                r.get("total_line_items", 0),
            )
            for r in rows
        ],
    )
    conn.commit()


def upsert_items(conn, rows):
    conn.executemany(
        """insert or replace into conversion_items
           (id, conversion_id, category, door_code, room_name, brand, model,
            description, quantity, is_option, source_sheet)
           values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        [
            (
                r["id"], r["conversion_id"], r.get("category", ""),
                r.get("door_code", ""), r.get("room_name", ""),
                r.get("brand", ""), r.get("model", ""),
                r.get("description", ""), r.get("quantity", 0),
                1 if r.get("is_option") else 0,
                r.get("source_sheet", ""),
            )
            for r in rows
        ],
    )
    conn.commit()


def main():
    cfg = load_config()
    url = cfg["url"].rstrip("/")
    service_key = cfg["service_key"]

    os.makedirs(ARCHIVE_DIR, exist_ok=True)
    conn = sqlite3.connect(SQLITE_FILE)
    ensure_tables(conn)

    print("Fetching conversions...", end=" ", flush=True)
    conversions = fetch_all(url, service_key, "conversions")
    upsert_conversions(conn, conversions)
    print(f"{len(conversions)} records")

    print("Fetching conversion_items...", end=" ", flush=True)
    items = fetch_all(url, service_key, "conversion_items")
    upsert_items(conn, items)
    print(f"{len(items)} records")

    conn.close()
    print(f"\nArchive saved to:\n  {SQLITE_FILE}")


if __name__ == "__main__":
    main()
