# Future Scraper Pattern — Required Checklist

Every new scraper in this project must implement these features.
Use `artunion_scraper.py` or `sugatsune_scraper.py` as a template.

---

## Mandatory features

### Config block (top of file)
```python
REQUEST_DELAY    = 0.6      # seconds between page requests
DOWNLOAD_WORKERS = 5        # parallel downloads per product/series
DOWNLOAD_TIMEOUT = 12       # seconds before a download attempt fails
```

### Page fetching — `get(url, retries=3)`
- Retry 3× with `time.sleep(2 * attempt)` backoff
- Return `BeautifulSoup` or `None` on total failure

### File downloading — `download_file(url, dest, retries=3)`
- Skip if `dest.exists() and dest.stat().st_size > 0`
- Use `timeout=DOWNLOAD_TIMEOUT`
- Delete partial file before each retry
- Backoff: `time.sleep(1.5 * attempt)`

### Parallel downloads — `download_many(jobs) -> dict[Path, bool]`
```python
def download_many(jobs: list[tuple[str, Path]]) -> dict[Path, bool]:
    with ThreadPoolExecutor(max_workers=DOWNLOAD_WORKERS) as pool:
        results = list(pool.map(lambda j: (j[1], download_file(j[0], j[1])), jobs))
    return dict(results)
```
Build ALL download jobs for a product/series first, then submit once.
Never download serially in a loop inside a per-product function.

### Category/listing cache — `product_ids.json`
- Cache per-category URL/ID lists to a JSON file in the output folder
- Write after every category so partial runs survive crashes
- `--refresh-ids` flag bypasses the cache

### Resume support — `load_existing_records()`
- On startup, read the existing JSON index if present
- Build a `done` set (keyed on the unique product URL or model code)
- Skip done items in Phase 2
- `--no-resume` flag forces a full rescrape

### Interactive category picker (when `--categories` not set)
- Show numbered list with `Done/Total` progress per category
- Accept: `1,3,5-8`, `200711`, `all`, or blank to cancel
- `--no-prompt` flag skips the picker and scrapes all

### Per-category progress logging
```
[Category 2/5] 200711 (Handles and Pulls) — 171 total, 45 done, 126 to scrape
  [200711 1/126] https://...
```

### Dual output — Excel + JSON index
- Excel: `output/{site}_products.xlsx` with frozen header, auto-filter, auto-width
- JSON: `output/{site}_products.json` — identical data, easy for a website to consume
- Save after every 3–5 items (checkpoint), not just at the end

### CLI flags (standard set)
| Flag | Purpose |
|---|---|
| `--categories` / `-c` | Comma-separated IDs, skips picker |
| `--max-pages` / `-p` | Limit listing pages per category |
| `--max-products` / `-n` | Stop after N products/series |
| `--refresh-ids` | Bust listing cache |
| `--refresh-categories` | Re-discover categories |
| `--no-prompt` | Skip interactive picker |
| `--no-resume` | Ignore existing JSON, rescrape everything |
| `--test` | 1 category, 1 page, 3–5 items |

---

## Filename rules

1. **Use the human-visible model/SKU code** as the filename stem, never an
   opaque URL parameter (e.g. `?id=12345`). Extract the visible name first,
   fall back to URL slug only if the page has no visible model.
2. Run all names through `safe_filename()` to strip illegal characters.
3. For per-variant images, key the image-to-variant lookup on **Item Name**,
   not on row index. Row indices desync when two parallel tables filter rows
   differently.
4. **Store relative paths only** in the JSON/Excel index so a future website
   can resolve them from any base URL.
5. Append `_p{n}` for numbered series images, `_drawing_{n}` for drawings,
   `_spec` for spec-sheet PDFs.

---

## Polite-scraping defaults

- `REQUEST_DELAY = 0.6–0.8` between HTML page requests (not between image downloads)
- Single browser-style `User-Agent` + `Accept-Language` header
- `DOWNLOAD_WORKERS = 5` keeps concurrent connections reasonable
- Don't parallelise at the product level (one product at a time, images in parallel)

---

## Output directory layout

```
output/
  {site}/
    images/
      series/   {MODEL}_p{n}.jpg        series-level promo shots
      items/    {ITEM_NAME}.jpg          per-SKU images
    drawings/   {MODEL}_drawing_{n}.jpg  2D size sheets
    specs/      {MODEL}_spec.pdf         spec-sheet PDFs
    category_ids.json
    product_ids.json
  {site}_products.xlsx
  {site}_products.json
```

---

## Verification recipe for every new scraper

1. `python {scraper}.py --test` — completes without errors, creates files
2. Check 3 random output images: filename should match the Item Name/Model
   shown on the live product page
3. Open the JSON: every record's `Item Image` path should point to an
   existing file
4. Run a second time without `--no-resume` — should skip all done items
   instantly (0 new fetches)
5. Run with `-c <one_category>` — should only scrape that category
