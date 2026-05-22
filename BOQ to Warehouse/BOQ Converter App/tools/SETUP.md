# BOQ Analytics — Setup Guide

## Step 1: Create a free Supabase project

1. Go to https://supabase.com → "Start your project" (free, no credit card)
2. Create a new project (any name, any region)
3. Wait ~2 minutes for it to provision

## Step 2: Run the database schema

1. In your Supabase project, go to **SQL Editor** (left sidebar)
2. Click **New query**
3. Open the file `BOQ Converter App/schema.sql` and paste the entire contents
4. Click **Run** — you should see "Success. No rows returned"

## Step 3: Get your API keys

In your Supabase project → **Project Settings** → **API**:

- **Project URL**: looks like `https://abcdefghijkl.supabase.co`
- **Project API keys → anon / public**: starts with `eyJ...` (this is safe to embed)
- **Project API keys → service_role**: starts with `eyJ...` (keep this secret — only on your machine)

## Step 4: Create the config file

Create this folder and file on your machine:

**Path:** `C:\Users\charl\AppData\Roaming\BOQConverter\db_config.json`

**Contents:**
```json
{
  "url": "https://YOUR_PROJECT_ID.supabase.co",
  "anon_key": "eyJ...(your anon key)...",
  "service_key": "eyJ...(your service_role key)..."
}
```

> The `service_key` is only used by the snapshot script on your machine.
> The `.exe` only uses `anon_key` (write-only via Row Level Security).

## Step 5: Rebuild and distribute the .exe

Run PyInstaller as normal — `requests` is now in `requirements.txt`.
The new `db_logger.py` is bundled automatically.

Users run the `.exe` exactly as before. No setup on their end.

---

## Step 6 (optional): Schedule weekly local backup

To keep a local SQLite copy of all data, set up a weekly Windows Task Scheduler job.

Open PowerShell and run:

```powershell
$action = New-ScheduledTaskAction `
  -Execute "python" `
  -Argument '"C:\Users\charl\Desktop\Claude Cowork\sandbox\BOQ to Warehouse\BOQ Converter App\tools\snapshot_to_sqlite.py"'

$trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday -At 9am

Register-ScheduledTask `
  -TaskName "BOQ Archive Snapshot" `
  -Action $action `
  -Trigger $trigger `
  -Description "Weekly backup of Supabase BOQ data to local SQLite"
```

Or run the snapshot manually any time:
```
python "BOQ Converter App\tools\snapshot_to_sqlite.py"
```

The archive lands at: `BOQ Converter App\archive\boq_archive.db`
Open it with [DB Browser for SQLite](https://sqlitebrowser.org/) (free) to run queries offline.

---

## Useful analytics queries (Supabase SQL Editor)

**Top brands by specification count:**
```sql
select brand, count(*) as times_specified, sum(quantity) as total_qty
from conversion_items
group by brand
order by times_specified desc;
```

**Top models:**
```sql
select model, brand, count(*) as times_specified, sum(quantity) as total_qty
from conversion_items
where model != ''
group by model, brand
order by times_specified desc
limit 50;
```

**Which projects used a specific model:**
```sql
select distinct c.project_name, c.created_at, c.machine_name
from conversion_items i
join conversions c on c.id = i.conversion_id
where i.model ilike '%ZL-1903%';
```

**All conversions from a machine:**
```sql
select project_name, created_at, total_door_types, total_line_items
from conversions
where machine_name = 'DESKTOP-ABC123'
order by created_at desc;
```
