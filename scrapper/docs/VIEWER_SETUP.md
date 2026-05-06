# Product Viewer — Setup Guide

Complete runbook for deploying the cloud-hosted internal product catalogue.
Estimated time: ~90 minutes (mostly waiting for the asset upload).

---

## 0. Prerequisites

Install once on the Windows machine:

- **Python 3.10+** (already present for the scrapers)
- **Git** + a free [GitHub](https://github.com) account
- Free accounts: **[Cloudflare](https://dash.cloudflare.com)**, **[Supabase](https://supabase.com)**

Open a terminal at `C:\Users\charl\Desktop\sandbox\scrapper` and install Python dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install boto3 supabase python-dotenv tqdm
```

---

## 1. Create the Cloudflare R2 bucket (asset storage)

1. Sign in to **dash.cloudflare.com** → sidebar → **R2 Object Storage** → **Create bucket**.
2. Bucket name: `scrapper-assets`. Location: Automatic. Click **Create bucket**.
3. Open the bucket → **Settings** → **Public access** → **Allow Access** under "R2.dev subdomain".
   - Copy the public URL (looks like `https://pub-<hash>.r2.dev`). This is your `R2_PUBLIC_BASE`.
4. Back on R2 home → **Manage R2 API Tokens** (top-right) → **Create API token**.
   - Permissions: **Object Read & Write**.
   - Specify bucket: `scrapper-assets`. TTL: forever.
   - Click **Create**. Copy the **Access Key ID**, **Secret Access Key**, and **endpoint URL**
     (looks like `https://<account_id>.r2.cloudflarestorage.com`).
   - **These are shown only once — save them now.**

---

## 2. Create the Supabase project (database)

1. Sign in to **supabase.com** → **New project**.
2. Name: `scrapper-viewer`. Region: Singapore (closest for SE Asia). Set a strong password.
3. Wait ~2 minutes for provisioning.
4. Go to **Project Settings → API**. Copy:
   - **Project URL** (`https://<ref>.supabase.co`)
   - **anon public** key
   - **service_role** key  ← keep this secret; never put it in frontend code.
5. Open **SQL Editor → New query**, paste the contents of `viewer/schema.sql`, and click **Run**.
   - Verify the `products` table appears under **Table Editor**.

---

## 3. Configure credentials

Create `viewer/.env` (this file is in `.gitignore` — never commit it):

```ini
R2_ACCOUNT_ENDPOINT=https://<account_id>.r2.cloudflarestorage.com
R2_ACCESS_KEY_ID=<your_access_key_id>
R2_SECRET_ACCESS_KEY=<your_secret_access_key>
R2_BUCKET=scrapper-assets
R2_PUBLIC_BASE=https://pub-<hash>.r2.dev

SUPABASE_URL=https://<ref>.supabase.co
SUPABASE_SERVICE_KEY=eyJ...
SUPABASE_ANON_KEY=eyJ...
```

---

## 4. Upload ELMES assets to R2

```powershell
# Dry run first — prints what will be uploaded
python viewer\upload_assets.py --source elmes --dry-run

# Actual upload (~2.8 GB; takes 1–3 hours on a typical connection)
python viewer\upload_assets.py --source elmes
```

- The script is **resumable** — re-running skips files already in R2 with matching size.
- Lower concurrency if your connection slows down: `--workers 4`
- On completion, `viewer/asset_manifest.json` is created — keep it, the seed script needs it.

Verify: open the R2 dashboard. You should see thousands of objects under the `elmes/` prefix.
Open one image URL in a browser to confirm public reads work.

---

## 5. Seed the database with ELMES products

```powershell
python viewer\seed_db.py --source elmes
```

Verify in Supabase **Table Editor → products**: ~20 rows should appear.

Run in SQL Editor to confirm:

```sql
select source, brand, count(*) from products group by source, brand;
select brand, model, image_urls[1] from products limit 5;
```

---

## 6. Edit the frontend with your Supabase credentials

Open `web/index.html` and `web/product.html`. In each file, replace the placeholder values:

```js
window.ENV = {
  SUPABASE_URL:      "%%SUPABASE_URL%%",       // ← paste your Project URL
  SUPABASE_ANON_KEY: "%%SUPABASE_ANON_KEY%%"  // ← paste your anon key
};
```

> The `anon` key is safe to put in frontend code — it only allows read access
> (enforced by the Row Level Security policy in `schema.sql`).

---

## 7. Deploy the frontend to Cloudflare Pages

1. Create a **new private GitHub repo** called `scrapper-viewer-web`.
2. Push the contents of the `web/` folder to it:
   ```powershell
   cd C:\Users\charl\Desktop\sandbox\scrapper\web
   git init
   git add .
   git commit -m "Initial frontend"
   git remote add origin https://github.com/<you>/scrapper-viewer-web.git
   git push -u origin main
   ```
3. In Cloudflare dashboard → **Workers & Pages → Create application → Pages → Connect to Git**
   → authorise GitHub → pick `scrapper-viewer-web`.
4. Build settings:
   - Framework preset: **None**
   - Build command: *(leave empty)*
   - Build output directory: `/`
5. Click **Save and Deploy**. After ~30 seconds, a `*.pages.dev` URL is live.

---

## 8. Lock it down with Cloudflare Access

1. Cloudflare dashboard → **Zero Trust** (sidebar). First-time setup: pick a team name.
   Free plan supports 50 users.
2. **Access → Applications → Add an application → Self-hosted**.
3. Application name: `Product Viewer`. Application domain: your `*.pages.dev` URL.
4. **Identity providers**: enable **One-time PIN** (email magic link — no SSO setup needed).
5. **Policies → Add a policy**: name `Staff`, action **Allow**, rule **Emails** →
   list each staff email address.
6. Save. Test in an incognito window — you should be prompted for email + PIN.

---

## 9. Optional: custom domain

In the Pages project → **Custom domains → Set up a domain** → enter e.g.
`products.todaystyle2100.com` and follow the CNAME instructions.
Re-add the custom domain to the Cloudflare Access policy in step 8.

---

## 10. Re-syncing after future scrapes

After re-running any scraper, just run:

```powershell
python viewer\upload_assets.py --source elmes     # uploads only new/changed files
python viewer\seed_db.py       --source elmes     # upserts changed records
```

No frontend redeploy needed — data is read live from Supabase.

---

## 11. Adding Phase 2 brands (Sugatsune / Simonswerk)

No code changes needed. Just:

```powershell
python viewer\upload_assets.py --source sugatsune
python viewer\seed_db.py       --source sugatsune

python viewer\upload_assets.py --source simonswerk
python viewer\seed_db.py       --source simonswerk
```

The brand filter on the list page updates automatically from the database.

---

## 12. Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| Images return 403 | R2 public access not enabled | Bucket → Settings → R2.dev subdomain → Allow |
| `seed_db.py` fails "JWT expired" | Wrong key | Use `SUPABASE_SERVICE_KEY` (not anon) in `.env` |
| Search returns nothing | `search_tsv` column empty | Add `generated always as` to schema or run a manual `UPDATE` |
| Pages loads but shows no data | Env vars wrong / missing | Check `window.ENV` values in index.html; redeploy |
| Access login loops on iPhone | Third-party cookies blocked | Use a custom domain on the same root as your Cloudflare team |
| Upload very slow | 8 workers saturating uplink | Run with `--workers 4` or leave running overnight |

---

## 13. Staying free — cost guardrails

| Service | Free limit | Current usage |
|---|---|---|
| Cloudflare R2 | 10 GB storage, zero egress | ~2.8 GB (ELMES only) |
| Supabase Postgres | 500 MB DB, pauses after 7d inactivity | < 10 MB |
| Cloudflare Pages | 500 builds/month, unlimited bandwidth | minimal |
| Cloudflare Access | 50 users free | internal staff only |

**Keep Supabase active:** it pauses after 7 days of inactivity on the free plan.
Add a free GitHub Action to ping the API weekly:

```yaml
# .github/workflows/keep-alive.yml
on:
  schedule:
    - cron: "0 8 * * 1"   # every Monday 08:00 UTC
jobs:
  ping:
    runs-on: ubuntu-latest
    steps:
      - run: curl -s "${{ secrets.SUPABASE_URL }}/rest/v1/products?select=id&limit=1" \
               -H "apikey: ${{ secrets.SUPABASE_ANON_KEY }}" > /dev/null
```
