-- =============================================================================
-- Blackridge Platform — 0001_init
-- Core schema + Row-Level Security. Plain Postgres — works on Supabase PG15/17.
--
-- NOTE: we deliberately do NOT use timescaledb. Supabase deprecated it on
-- Postgres 17 (the default for new projects). When the snapshot table grows
-- enough to need partitioning, 0002_partitioning.sql converts it to native
-- Postgres range partitioning managed by pg_partman (Supabase's recommended
-- path) + pg_cron for maintenance. Your data volume does not need it to start.
--
-- Apply via Supabase SQL editor, `supabase db push`, or the apply_migration MCP.
-- =============================================================================

-- ----------------------------------------------------------------------------
-- Extensions
-- ----------------------------------------------------------------------------
create extension if not exists pgcrypto;        -- gen_random_uuid()

-- ----------------------------------------------------------------------------
-- Enums
-- ----------------------------------------------------------------------------
do $$ begin
  create type instrument_type as enum ('index', 'stock', 'commodity', 'currency');
exception when duplicate_object then null; end $$;

do $$ begin
  create type option_side as enum ('CE', 'PE');
exception when duplicate_object then null; end $$;

do $$ begin
  create type buildup_label as enum
    ('long_buildup', 'short_buildup', 'long_unwinding', 'short_covering', 'neutral');
exception when duplicate_object then null; end $$;

-- ============================================================================
-- 1. instruments — catalog of tradable instruments (shared)
-- ============================================================================
create table if not exists public.instruments (
  id          smallint generated always as identity primary key,
  symbol      text not null unique,                 -- 'NIFTY', 'BANKNIFTY'
  name        text not null,
  type        instrument_type not null default 'index',
  segment     text,                                 -- 'NSE-OPT', etc.
  lot_size    integer,
  tick_size   numeric(10,2),
  active      boolean not null default true,
  created_at  timestamptz not null default now()
);

-- ============================================================================
-- 2. option_snapshots — raw per-strike grain (shared, append-only)
--    One row per (instrument, expiry, strike, time). CE_* and PE_* inline,
--    matching the existing wide CSV layout.
-- ============================================================================
create table if not exists public.option_snapshots (
  time            timestamptz not null,
  instrument_id   smallint not null references public.instruments(id),
  expiry          date not null,
  strike          numeric(12,2) not null,
  underlying      numeric(12,2),

  -- Call (CE)
  ce_oi           bigint,
  ce_oi_change    bigint,
  ce_iv           numeric(8,2),
  ce_ltp          numeric(12,2),
  ce_volume       bigint,
  ce_change       numeric(12,2),
  ce_pchange      numeric(10,2),
  ce_buy_qty      bigint,
  ce_sell_qty     bigint,

  -- Put (PE)
  pe_oi           bigint,
  pe_oi_change    bigint,
  pe_iv           numeric(8,2),
  pe_ltp          numeric(12,2),
  pe_volume       bigint,
  pe_change       numeric(12,2),
  pe_pchange      numeric(10,2),
  pe_buy_qty      bigint,
  pe_sell_qty     bigint,

  source          text not null default 'nse',
  ingested_at     timestamptz not null default now(),

  -- PK includes `time`: required if/when this table is converted to native
  -- range partitioning on `time` (0002) — the partition key must be in every
  -- unique constraint. It's also the correct natural key regardless.
  primary key (instrument_id, expiry, strike, time)
);

create index if not exists idx_snapshots_instrument_time
  on public.option_snapshots (instrument_id, time desc);
-- BRIN is tiny and ideal for an append-only, time-ordered table; cheap to keep.
create index if not exists idx_snapshots_time_brin
  on public.option_snapshots using brin (time);

-- ============================================================================
-- 3. metrics — one instrument-level row per snapshot (shared)
-- ============================================================================
create table if not exists public.metrics (
  time                  timestamptz not null,
  instrument_id         smallint not null references public.instruments(id),
  expiry                date not null,
  dte                   integer,                    -- days to expiry
  underlying            numeric(12,2),

  -- Put/Call ratios
  pcr_oi                numeric(8,3),
  pcr_volume            numeric(8,3),

  -- Center of gravity
  ce_cog                numeric(12,2),
  pe_cog                numeric(12,2),
  cog_shift             numeric(12,2),

  -- Volatility
  atm_strike            numeric(12,2),
  atm_iv                numeric(8,2),
  iv_skew               numeric(8,2),               -- pe_iv - ce_iv (equidistant OTM)
  india_vix             numeric(8,2),

  -- Expected move
  atm_straddle          numeric(12,2),
  expected_move         numeric(12,2),

  -- OI structure
  max_pain              numeric(12,2),
  total_ce_oi           bigint,
  total_pe_oi           bigint,
  net_ce_oi_change      bigint,
  net_pe_oi_change      bigint,
  total_ce_volume       bigint,
  total_pe_volume       bigint,

  -- Flow / structure
  buy_sell_imbalance    numeric(8,3),               -- buy_qty / sell_qty
  buildup               buildup_label,

  -- Support / resistance
  immediate_support     numeric(12,2),
  major_support         numeric(12,2),
  immediate_resistance  numeric(12,2),
  major_resistance      numeric(12,2),

  -- Sentiment (metrics.py)
  sentiment_score       integer,                    -- -100..100
  sentiment_label       text,
  drivers               jsonb,                      -- list of driver strings

  created_at            timestamptz not null default now(),

  primary key (instrument_id, time)
);

create index if not exists idx_metrics_instrument_time
  on public.metrics (instrument_id, time desc);

-- ============================================================================
-- 4. insights — agent-generated narrative (shared; user_id null = system)
-- ============================================================================
create table if not exists public.insights (
  id              uuid primary key default gen_random_uuid(),
  time            timestamptz not null default now(),
  instrument_id   smallint not null references public.instruments(id),
  expiry          date,
  title           text not null,
  narrative       text not null,
  sentiment_label text,
  confidence      numeric(4,3),                     -- 0..1
  cited_metrics   jsonb,                            -- the rows/values the agent used
  model           text,                             -- e.g. 'claude-opus-4-8'
  user_id         uuid references auth.users(id) on delete cascade,  -- null = system-wide
  created_at      timestamptz not null default now()
);

create index if not exists idx_insights_instrument_time
  on public.insights (instrument_id, time desc);

-- ============================================================================
-- 5. profiles — mirrors auth.users (per-user)
-- ============================================================================
create table if not exists public.profiles (
  id            uuid primary key references auth.users(id) on delete cascade,
  email         text,
  display_name  text,
  created_at    timestamptz not null default now()
);

-- Auto-create a profile row when a new auth user signs up.
create or replace function public.handle_new_user()
returns trigger language plpgsql security definer set search_path = public as $$
begin
  insert into public.profiles (id, email)
  values (new.id, new.email)
  on conflict (id) do nothing;
  return new;
end $$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function public.handle_new_user();

-- ============================================================================
-- 6. watchlists — per-user instrument follows
-- ============================================================================
create table if not exists public.watchlists (
  id            uuid primary key default gen_random_uuid(),
  user_id       uuid not null references auth.users(id) on delete cascade,
  instrument_id smallint not null references public.instruments(id),
  created_at    timestamptz not null default now(),
  unique (user_id, instrument_id)
);

create index if not exists idx_watchlists_user on public.watchlists (user_id);

-- ============================================================================
-- Row-Level Security
--   Shared market data: authenticated users may SELECT; writes only via the
--   service role (which bypasses RLS) used by ingestion + insights workers.
--   User-owned data: full CRUD restricted to the owning user.
-- ============================================================================

-- ---- shared, read-only to authenticated ----
alter table public.instruments       enable row level security;
alter table public.option_snapshots  enable row level security;
alter table public.metrics           enable row level security;
alter table public.insights          enable row level security;

create policy "read instruments"  on public.instruments
  for select to authenticated using (true);
create policy "read snapshots"    on public.option_snapshots
  for select to authenticated using (true);
create policy "read metrics"      on public.metrics
  for select to authenticated using (true);
-- system insights visible to all; personal insights only to their owner
create policy "read insights"     on public.insights
  for select to authenticated using (user_id is null or user_id = auth.uid());

-- ---- per-user ----
alter table public.profiles   enable row level security;
alter table public.watchlists enable row level security;

create policy "own profile select" on public.profiles
  for select to authenticated using (id = auth.uid());
create policy "own profile update" on public.profiles
  for update to authenticated using (id = auth.uid()) with check (id = auth.uid());

create policy "own watchlist all" on public.watchlists
  for all to authenticated using (user_id = auth.uid()) with check (user_id = auth.uid());

-- ============================================================================
-- Seed: instrument #1
-- ============================================================================
insert into public.instruments (symbol, name, type, segment, lot_size)
values ('NIFTY', 'Nifty 50', 'index', 'NSE-OPT', 75)
on conflict (symbol) do nothing;
