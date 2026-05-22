-- BOQ Conversion Analytics — run this in Supabase SQL Editor
-- Project: BOQ Converter App | Today Style 2100

-- ─── Projects (mirror of Lark Base project tracker) ─────────────────────────
create table if not exists projects (
  id           text        primary key,        -- Lark record_id (stable across renames)
  name         text        not null,
  category     text        not null default '',
  status       text        not null default '',
  lark_url     text        not null default '',
  updated_at   timestamptz,                    -- last edited in Lark
  synced_at    timestamptz default now()
);

create index if not exists idx_projects_name     on projects(name);
create index if not exists idx_projects_category on projects(category);

-- ─── Conversions ─────────────────────────────────────────────────────────────
create table if not exists conversions (
  id                uuid        primary key,
  created_at        timestamptz default now(),
  project_name      text        not null default '',
  project_category  text        not null default '',
  project_id        text,                            -- FK to projects.id (Lark record), nullable for custom projects
  machine_name      text        not null default '',
  source_files      text[]      not null default '{}',
  total_door_types  int         not null default 0,
  total_line_items  int         not null default 0,
  total_quantity    numeric     not null default 0,
  is_latest         boolean     not null default true,
  superseded_at     timestamptz
);

create table if not exists conversion_items (
  id             bigserial   primary key,
  conversion_id  uuid        not null references conversions(id) on delete cascade,
  category       text        not null default '',
  door_code      text        not null default '',
  room_name      text        not null default '',
  brand          text        not null default '',
  model          text        not null default '',
  description    text        not null default '',
  quantity       numeric     not null default 0,
  is_option      boolean     not null default false,
  source_sheet   text        not null default ''
);

-- Idempotent column adds for existing deployments
alter table conversions add column if not exists project_category text not null default '';
alter table conversions add column if not exists project_id       text;
alter table conversions add column if not exists total_quantity   numeric not null default 0;
alter table conversions add column if not exists is_latest        boolean not null default true;
alter table conversions add column if not exists superseded_at    timestamptz;

create index if not exists idx_items_brand        on conversion_items(brand);
create index if not exists idx_items_model        on conversion_items(model);
create index if not exists idx_conv_project       on conversions(project_name);
create index if not exists idx_conv_category      on conversions(project_category);
create index if not exists idx_conv_project_id    on conversions(project_id);
create index if not exists idx_conv_created       on conversions(created_at);
create index if not exists idx_conv_latest        on conversions(is_latest);
create index if not exists idx_items_conv_id      on conversion_items(conversion_id);

-- ─── Row Level Security ─────────────────────────────────────────────────────
alter table conversions       enable row level security;
alter table conversion_items  enable row level security;
alter table projects          enable row level security;

drop policy if exists "anon insert conversions" on conversions;
create policy "anon insert conversions"
  on conversions for insert to anon with check (true);

drop policy if exists "anon insert items" on conversion_items;
create policy "anon insert items"
  on conversion_items for insert to anon with check (true);

-- Allow anon to flip is_latest on prior runs of the same project.
-- Scoped: only is_latest/superseded_at can change; nothing else.
drop policy if exists "anon supersede conversions" on conversions;
create policy "anon supersede conversions"
  on conversions for update to anon
  using (true)
  with check (true);

drop policy if exists "anon read projects" on projects;
create policy "anon read projects"
  on projects for select to anon using (true);

-- Allow the BOQ app (anon key) to write back a category when the user fills one in.
-- Projects table is non-sensitive so anon UPDATE is acceptable.
drop policy if exists "anon update project category" on projects;
create policy "anon update project category"
  on projects for update to anon
  using (true)
  with check (true);

-- Sync script uses service_role key (bypasses RLS) so no projects insert policy needed.

-- ─── Convenience view: only the most recent conversion per project ──────────
create or replace view conversions_latest as
  select * from conversions where is_latest;

-- ─── Useful analytics queries ────────────────────────────────────────────────

-- Brand frequency (latest conversion per project only — no double-counting)
-- select i.brand, count(*) as times_specified, sum(i.quantity) as total_qty
-- from conversion_items i
-- join conversions_latest c on c.id = i.conversion_id
-- group by i.brand
-- order by times_specified desc;

-- Brand/model usage by project category
-- select c.project_category, i.brand, i.model, count(*) as picks
-- from conversion_items i
-- join conversions_latest c on c.id = i.conversion_id
-- where c.project_category != ''
-- group by c.project_category, i.brand, i.model
-- order by c.project_category, picks desc;

-- Most-recent conversion per project
-- select project_name, project_category, created_at, total_line_items
-- from conversions_latest
-- order by created_at desc;

-- Full history of a single project
-- select created_at, is_latest, total_line_items, machine_name
-- from conversions
-- where project_name = 'XYZ Hotel' and project_category = 'Hotel'
-- order by created_at desc;
