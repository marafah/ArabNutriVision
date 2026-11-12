-- ArabNutriVision · Supabase schema for the static (GitHub Pages) edition.
-- Run once in the Supabase dashboard: SQL Editor → New query → paste this file → Run.
-- Every table carries an owner column filled from the signed-in user; row-level security lets each
-- researcher read and write only their own rows. Reference data (dishes, ingredients, supplements)
-- are not stored here: they ship with the site, so rows refer to them by code.

create table if not exists public.participants (
  id bigint generated always as identity primary key,
  owner uuid not null default auth.uid() references auth.users (id) on delete cascade,
  code text not null check (char_length(code) between 1 and 30),
  sex text not null default 'X' check (sex in ('F', 'M', 'X')),
  age_years integer check (age_years between 0 and 130),
  energy_target_kcal integer not null default 2000 check (energy_target_kcal between 500 and 6000),
  notes text not null default '' check (char_length(notes) <= 200),
  created_at timestamptz not null default now(),
  unique (owner, code)
);

create table if not exists public.records (
  id bigint generated always as identity primary key,
  owner uuid not null default auth.uid() references auth.users (id) on delete cascade,
  participant_id bigint not null references public.participants (id) on delete cascade,
  date date not null,
  method text not null default 'recall' check (method in ('recall', 'record', 'menu', 'ffq')),
  notes text not null default '' check (char_length(notes) <= 200),
  created_at timestamptz not null default now()
);

create table if not exists public.items (
  id bigint generated always as identity primary key,
  owner uuid not null default auth.uid() references auth.users (id) on delete cascade,
  record_id bigint not null references public.records (id) on delete cascade,
  meal text not null default 'lunch' check (meal in ('breakfast', 'lunch', 'dinner', 'snack')),
  dish_code text,
  ingredient_code text,
  grams real not null check (grams between 1 and 3000),
  style text not null default 'mean' check (style in ('mean', 'home', 'restaurant', 'light')),
  source text not null default 'manual' check (source in ('manual', 'photo', 'photo_corrected', 'ffq')),
  ai_image_only_kcal real,
  created_at timestamptz not null default now(),
  check (dish_code is not null or ingredient_code is not null)
);

create table if not exists public.supplement_intakes (
  id bigint generated always as identity primary key,
  owner uuid not null default auth.uid() references auth.users (id) on delete cascade,
  record_id bigint not null references public.records (id) on delete cascade,
  supplement_name text not null,
  doses real not null default 1 check (doses > 0 and doses <= 20),
  created_at timestamptz not null default now()
);

create table if not exists public.validation_samples (
  id bigint generated always as identity primary key,
  owner uuid not null default auth.uid() references auth.users (id) on delete cascade,
  session_id text not null check (char_length(session_id) between 1 and 20),
  plate_no integer not null default 1,
  dish_code text not null,
  variant text not null default 'home' check (variant in ('home', 'restaurant', 'light')),
  weight_g real not null check (weight_g > 0 and weight_g <= 3000),
  view text not null default 'top' check (view in ('top', '45deg')),
  reference_card boolean not null default false,
  phone text not null default '',
  split text not null default 'test' check (split in ('train', 'val', 'test')),
  image_file text not null default '',
  ai_dish_code text,
  ai_grams real,
  ai_style text not null default '',
  ai_direct_kcal real,
  ai_direct_fat_g real,
  created_at timestamptz not null default now()
);

create index if not exists records_participant_idx on public.records (participant_id);
create index if not exists items_record_idx on public.items (record_id);
create index if not exists supp_record_idx on public.supplement_intakes (record_id);
create index if not exists records_owner_idx on public.records (owner);
create index if not exists validation_owner_idx on public.validation_samples (owner);

-- Row-level security: a researcher sees and changes only rows they own, and can only attach
-- records to their own participants and items to their own records.
alter table public.participants enable row level security;
alter table public.records enable row level security;
alter table public.items enable row level security;
alter table public.supplement_intakes enable row level security;
alter table public.validation_samples enable row level security;

drop policy if exists own_rows on public.participants;
create policy own_rows on public.participants for all to authenticated
  using (owner = (select auth.uid())) with check (owner = (select auth.uid()));

drop policy if exists own_rows on public.records;
create policy own_rows on public.records for all to authenticated
  using (owner = (select auth.uid()))
  with check (owner = (select auth.uid()) and exists (
    select 1 from public.participants p where p.id = participant_id and p.owner = (select auth.uid())));

drop policy if exists own_rows on public.items;
create policy own_rows on public.items for all to authenticated
  using (owner = (select auth.uid()))
  with check (owner = (select auth.uid()) and exists (
    select 1 from public.records r where r.id = record_id and r.owner = (select auth.uid())));

drop policy if exists own_rows on public.supplement_intakes;
create policy own_rows on public.supplement_intakes for all to authenticated
  using (owner = (select auth.uid()))
  with check (owner = (select auth.uid()) and exists (
    select 1 from public.records r where r.id = record_id and r.owner = (select auth.uid())));

drop policy if exists own_rows on public.validation_samples;
create policy own_rows on public.validation_samples for all to authenticated
  using (owner = (select auth.uid())) with check (owner = (select auth.uid()));

-- Only signed-in researchers may use the tables; anonymous visitors get nothing.
revoke all on public.participants, public.records, public.items, public.supplement_intakes, public.validation_samples from anon;
grant select, insert, update, delete on public.participants, public.records, public.items, public.supplement_intakes,
  public.validation_samples to authenticated;

-- Tiny function for the keep-alive workflow (.github/workflows/keepalive.yml). It touches the database
-- once a day so the free project is not paused for inactivity. It reveals no data.
create or replace function public.ping() returns integer
  language sql stable security invoker set search_path = '' as $$ select 1 $$;
revoke all on function public.ping() from public;
grant execute on function public.ping() to anon, authenticated;
