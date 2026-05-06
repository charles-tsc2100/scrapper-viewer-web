-- Products table: unified schema for ELMES, Sugatsune, Simonswerk
-- Run this once in the Supabase SQL editor.

create table if not exists products (
  id                text primary key,      -- "<source>:<model>:<variant>"
  source            text not null,         -- 'artunion' | 'sugatsune' | 'simonswerk'
  brand             text,
  model             text not null,
  name              text,
  category          text,
  subcategory       text,
  material          text,
  finish            text,
  load_capacity_kg  numeric,
  door_height_mm    numeric,
  door_width_mm     numeric,
  door_thickness_mm numeric,
  spec_pdf_url      text,
  drawing_urls      text[],
  image_urls        text[],
  source_url        text,
  raw               jsonb not null default '{}'::jsonb,
  search_tsv        tsvector generated always as (
    to_tsvector('english',
      coalesce(brand,    '') || ' ' ||
      coalesce(model,    '') || ' ' ||
      coalesce(name,     '') || ' ' ||
      coalesce(category, '')
    )
  ) stored
);

create index if not exists products_search_tsv_idx on products using gin(search_tsv);
create index if not exists products_source_idx     on products(source);
create index if not exists products_model_idx      on products(model);

-- Read-only access for anonymous (frontend) users.
-- Cloudflare Access gates the site; anon key is safe to expose in the frontend.
alter table products enable row level security;

create policy "Public read" on products
  for select using (true);
