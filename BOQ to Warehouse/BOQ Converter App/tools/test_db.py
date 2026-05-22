"""Quick end-to-end test: inserts a fake conversion and verifies it landed in Supabase."""
import sys, time, json, requests
sys.path.insert(0, "..")

from boq_parser import BOQCategory, DoorType, DoorProduct, Product
import db_logger

cat = BOQCategory(name="Door", source_file="TEST_BOQ.xlsx")
p1 = Product(model="ZL-1903", brand="Sugatsune", description="Sliding door handle", unit_price=1200.0)
p2 = Product(model="TYPE52", brand="ELMES", description="Lock body", unit_price=850.0)
dt = DoorType(code="D-101", room_name="Master Bedroom", source_sheet="D1")
dt.products = [DoorProduct(product=p1, quantity=2), DoorProduct(product=p2, quantity=2)]
cat.door_types = [dt]

print("Sending test conversion...")
db_logger.log_conversion("TEST PROJECT - End to End Check", [cat], ["TEST_BOQ.xlsx"])
time.sleep(4)

import os, json as _json
APPDATA = os.environ.get("APPDATA", "")
with open(os.path.join(APPDATA, "BOQConverter", "db_config.json")) as f:
    cfg = _json.load(f)

url = cfg["url"].rstrip("/")
sk = cfg["service_key"]
h = {"apikey": sk, "Authorization": "Bearer " + sk}

conv = requests.get(
    url + "/rest/v1/conversions?project_name=eq.TEST PROJECT - End to End Check&select=*",
    headers=h).json()

if not conv:
    print("FAIL: conversion not found in Supabase")
    sys.exit(1)

cid = conv[0]["id"]
items = requests.get(
    url + "/rest/v1/conversion_items?conversion_id=eq." + cid + "&select=brand,model,quantity",
    headers=h).json()

print("Conversion record:")
print(json.dumps(conv[0], indent=2))
print("\nLine items:")
print(json.dumps(items, indent=2))
print("\nPASS — logger is working correctly.")
