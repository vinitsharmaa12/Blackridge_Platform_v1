-- =============================================================================
-- Blackridge Platform — 0002_partitioning  (OPTIONAL / "scale as we go")
-- Native Postgres range partitioning for the high-volume snapshot table,
-- automated with pg_partman, maintained on a schedule with pg_cron.
-- This is Supabase's recommended replacement for timescaledb hypertables.
--
-- DO NOT run this on day one. Apply only when option_snapshots is large enough
-- that a single table hurts (tens of millions of rows). Until then, the plain
-- table from 0001 + its BRIN index is more than enough.
--
-- IMPORTANT: native partitioning must be declared at CREATE TABLE time — you
-- cannot ALTER an existing plain table into a partitioned one. So this migration
-- creates a NEW partitioned table, copies data in, and swaps it. Test on a
-- staging/branch project first. Ref:
--   https://supabase.com/docs/guides/database/migrating-to-pg-partman
-- =============================================================================

-- ----------------------------------------------------------------------------
-- 1. Extensions (Supabase-supported)
-- ----------------------------------------------------------------------------
create schema if not exists partman;
create extension if not exists pg_partman with schema partman;
create extension if not exists pg_cron;          -- enable from Dashboard if needed

-- ----------------------------------------------------------------------------
-- 2. New partitioned parent (same columns as public.option_snapshots).
--    Partitioned BY RANGE on `time`; partition key must be in the PK.
-- ----------------------------------------------------------------------------
create table if not exists public.option_snapshots_part (
  time            timestamptz not null,
  instrument_id   smallint not null references public.instruments(id),
  expiry          date not null,
  strike          numeric(12,2) not null,
  underlying      numeric(12,2),
  ce_oi bigint, ce_oi_change bigint, ce_iv numeric(8,2), ce_ltp numeric(12,2),
  ce_volume bigint, ce_change numeric(12,2), ce_pchange numeric(10,2),
  ce_buy_qty bigint, ce_sell_qty bigint,
  pe_oi bigint, pe_oi_change bigint, pe_iv numeric(8,2), pe_ltp numeric(12,2),
  pe_volume bigint, pe_change numeric(12,2), pe_pchange numeric(10,2),
  pe_buy_qty bigint, pe_sell_qty bigint,
  source text not null default 'nse',
  ingested_at timestamptz not null default now(),
  primary key (instrument_id, expiry, strike, time)
) partition by range (time);

create index if not exists idx_snap_part_instrument_time
  on public.option_snapshots_part (instrument_id, time desc);
create index if not exists idx_snap_part_time_brin
  on public.option_snapshots_part using brin (time);

-- ----------------------------------------------------------------------------
-- 3. Hand the parent to pg_partman: weekly partitions, pre-create a few ahead.
-- ----------------------------------------------------------------------------
select partman.create_parent(
  p_parent_table    => 'public.option_snapshots_part',
  p_control         => 'time',
  p_type            => 'range',
  p_interval        => '1 week',
  p_premake         => 4
);

-- Optional retention: drop raw snapshot partitions older than 1 year.
update partman.part_config
   set retention = '12 months',
       retention_keep_table = false
 where parent_table = 'public.option_snapshots_part';

-- ----------------------------------------------------------------------------
-- 4. Backfill from the plain table, then swap names.
--    (Run during a quiet window; ingestion should be paused briefly.)
-- ----------------------------------------------------------------------------
insert into public.option_snapshots_part
  select * from public.option_snapshots;

alter table public.option_snapshots      rename to option_snapshots_old;
alter table public.option_snapshots_part rename to option_snapshots;
-- After verifying counts:  drop table public.option_snapshots_old;

-- Re-apply RLS on the new table (policies don't follow a rename of a different table).
alter table public.option_snapshots enable row level security;
create policy "read snapshots" on public.option_snapshots
  for select to authenticated using (true);

-- ----------------------------------------------------------------------------
-- 5. Schedule pg_partman maintenance (creates future partitions, runs retention).
-- ----------------------------------------------------------------------------
select cron.schedule(
  'partman-maintenance',
  '@hourly',
  $$ call partman.run_maintenance_proc() $$
);

-- ----------------------------------------------------------------------------
-- 6. (Optional) 5-minute chart rollup as a plain materialized view, refreshed
--    by pg_cron. Replaces the timescaledb continuous aggregate.
-- ----------------------------------------------------------------------------
create materialized view if not exists public.metrics_5m as
select
  date_trunc('minute', time)
    - (extract(minute from time)::int % 5) * interval '1 minute' as bucket,
  instrument_id,
  avg(pcr_oi)     as pcr_oi,
  avg(atm_iv)     as atm_iv,
  avg(iv_skew)    as iv_skew,
  max(max_pain)   as max_pain,
  max(sentiment_score) as sentiment_score
from public.metrics
group by 1, 2
with no data;

create unique index if not exists idx_metrics_5m
  on public.metrics_5m (instrument_id, bucket);

select cron.schedule(
  'refresh-metrics-5m',
  '*/5 * * * *',
  $$ refresh materialized view concurrently public.metrics_5m $$
);
