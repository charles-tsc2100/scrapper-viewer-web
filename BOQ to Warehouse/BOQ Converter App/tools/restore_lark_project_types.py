"""
One-shot script: restore the "Project Type" single-select options in Lark Base.

Reads credentials from %APPDATA%/BOQConverter/lark_config.json.

Usage:
    python tools/restore_lark_project_types.py
"""
import json
import os
import sys

import requests

APPDATA = os.environ.get("APPDATA", os.path.expanduser("~"))
LARK_CONFIG = os.path.join(APPDATA, "BOQConverter", "lark_config.json")
LARK_HOST = "https://open.larksuite.com"

PROJECT_TYPES = [
    "Commercial",
    "Data Center",
    "Education",
    "Government",
    "Hospitality",
    "Industrial",
    "Leisure & Recreation",
    "Residential",
    "Wellness",
]

FIELD_NAME = "Project Type"


def load_config():
    if not os.path.exists(LARK_CONFIG):
        print(f"ERROR: Config not found at {LARK_CONFIG}")
        sys.exit(1)
    with open(LARK_CONFIG, "r", encoding="utf-8") as f:
        return json.load(f)


def get_token(cfg):
    r = requests.post(
        f"{LARK_HOST}/open-apis/auth/v3/tenant_access_token/internal",
        json={"app_id": cfg["app_id"], "app_secret": cfg["app_secret"]},
        timeout=10,
    )
    r.raise_for_status()
    data = r.json()
    if data.get("code") != 0:
        print(f"ERROR: Lark auth failed: {data}")
        sys.exit(1)
    return data["tenant_access_token"]


def list_fields(token, app_token, table_id):
    r = requests.get(
        f"{LARK_HOST}/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/fields",
        headers={"Authorization": f"Bearer {token}"},
        timeout=10,
    )
    r.raise_for_status()
    data = r.json()
    if data.get("code") != 0:
        print(f"ERROR: list fields failed: {data}")
        sys.exit(1)
    return data["data"]["items"]


def patch_field(token, app_token, table_id, field_id, options):
    payload = {
        "field_name": FIELD_NAME,
        "type": 3,  # 3 = single select
        "property": {
            "options": [{"name": o} for o in options]
        },
    }
    r = requests.put(
        f"{LARK_HOST}/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/fields/{field_id}",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json=payload,
        timeout=10,
    )
    r.raise_for_status()
    data = r.json()
    if data.get("code") != 0:
        print(f"ERROR: patch field failed: {data}")
        sys.exit(1)
    return data


def main():
    cfg = load_config()
    app_token = cfg["base_app_token"]
    table_id = cfg["table_id"]

    print("Getting Lark token...")
    token = get_token(cfg)

    print("Listing fields...")
    fields = list_fields(token, app_token, table_id)

    field = next((f for f in fields if f.get("field_name") == FIELD_NAME), None)
    if not field:
        print(f"ERROR: Field '{FIELD_NAME}' not found in table. Available fields:")
        for f in fields:
            print(f"  - {f['field_name']} (type={f['type']}, id={f['field_id']})")
        sys.exit(1)

    field_id = field["field_id"]
    print(f"Found '{FIELD_NAME}' — field_id: {field_id}")
    print(f"Restoring {len(PROJECT_TYPES)} options: {', '.join(PROJECT_TYPES)}")

    patch_field(token, app_token, table_id, field_id, PROJECT_TYPES)
    print(f"\nSuccess! '{FIELD_NAME}' now has {len(PROJECT_TYPES)} options in Lark Base.")


if __name__ == "__main__":
    main()
